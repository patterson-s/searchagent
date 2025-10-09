# app.py
import streamlit as st
from serper_client import search
from fetcher import fetch_url_text
from extractor import top_passages, score_passage
from storage import get_conn, init_db, save_source, save_passage
from requests.exceptions import RequestException
import sqlite3
from tqdm import tqdm

st.set_page_config(page_title="Prosopography Search Agent", layout="wide")
st.title("Prosopography Research Assistant (Serper + human-in-loop)")

# init DB
conn = get_conn("searchagent.db")
init_db(conn)

with st.sidebar:
    st.header("Search")
    query_name = st.text_input("Person name (e.g., 'Federica Mogherini')", value="")
    max_results = st.number_input("Number of top search results to fetch", value=6, min_value=1, max_value=20)
    run = st.button("Search")

if run and query_name.strip():
    q = f'{query_name} biography OR "born" OR "appointed" OR "PhD"'
    st.info(f"Running Serper search for: {q}")
    try:
        resp = search(q, num_results=max_results)
    except Exception as e:
        st.error(f"Search failed: {e}")
        st.stop()

    # Serper 'organic' hits
    organic = resp.get("organic", []) or resp.get("results", []) or []
    results = organic[:max_results]

    st.write(f"Found {len(results)} results. Fetching pages and extracting passages...")
    cols = st.columns([3,2])
    progress = st.progress(0)
    for i, r in enumerate(results):
        # Extract typical fields (Serper variants differ)
        url = r.get("link") or r.get("url") or r.get("snippet")
        title = r.get("title") or ""
        snippet = r.get("snippet") or r.get("description") or ""
        try:
            title, text = fetch_url_text(url)
        except Exception as e:
            st.warning(f"Failed to fetch {url}: {e}")
            continue

        # identify top passages
        best = top_passages(text, query_name=query_name, top_k=4)
        with st.expander(f"{i+1}. {title} — {url}", expanded=(i<3)):
            st.write(snippet)
            for p in best:
                s = score_passage(p, query_name=query_name)
                st.markdown(f"**Score:** {s:.2f}")
                st.write(p)
                row = st.columns([1,1,6])
                if row[0].button("Save passage", key=f"save{i}_{hash(p)}"):
                    sid = save_source(conn, url, title, snippet, query_name, i+1)
                    pid = save_passage(conn, sid, p, s)
                    st.success(f"Saved passage id={pid}")
                if row[1].button("Open source", key=f"open{i}_{hash(p)}"):
                    st.write(f"[Open {url}]({url})")
        progress.progress((i+1)/len(results))
    st.success("Done fetching and proposing passages.")

# Simple viewer for saved items
st.sidebar.markdown("---")
if st.sidebar.checkbox("Show saved items"):
    st.sidebar.write("Saved passages (most recent):")
    cur = conn.cursor()
    rows = cur.execute("""SELECT p.id, s.title, s.url, p.passage, p.score, p.saved_at
                           FROM passages p JOIN sources s ON p.source_id = s.id
                           ORDER BY p.saved_at DESC LIMIT 40""").fetchall()
    for pid, title, url, passage, score, saved_at in rows:
        st.sidebar.markdown(f"**{title}** ({saved_at}) — score {score:.2f}")
        st.sidebar.write(passage[:300] + ("..." if len(passage)>300 else ""))
        st.sidebar.markdown(f"[Open source]({url})")
