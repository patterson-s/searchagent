#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/careerfinder/inspect_timeline.py

import json
import streamlit as st
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

st.set_page_config(page_title="Career Timeline Inspector", layout="wide")

DEFAULT_RESULTS_PATH = r"C:\Users\spatt\Desktop\searchagent\services\careerfinder\outputs\careerfinder_results.jsonl"

def load_results(path: str) -> List[Dict]:
    results = []
    if not path or not Path(path).exists():
        return results
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    results.append(json.loads(line))
                except:
                    continue
    return results

def parse_year(year_str: str) -> Optional[int]:
    if not year_str:
        return None
    try:
        return int(year_str)
    except:
        return None

def get_year_range(event: Dict) -> tuple:
    start = parse_year(event.get("start_date", ""))
    end = parse_year(event.get("end_date", ""))
    return (start or 9999, end or 9999)

def format_date_range(event: Dict) -> str:
    start = event.get("start_date", "")
    end = event.get("end_date", "")
    if start and end:
        return f"{start}-{end}"
    elif start:
        return f"{start}-"
    elif end:
        return f"-{end}"
    else:
        return "Unknown dates"

st.title("Career Timeline Inspector")

with st.sidebar:
    st.header("Settings")
    results_path = st.text_input("Results file", value=DEFAULT_RESULTS_PATH)
    
results = load_results(results_path)

if not results:
    st.warning("No results found. Check the file path.")
    st.stop()

person_names = [r["person_name"] for r in results]
selected_person = st.sidebar.selectbox("Select person", person_names)

person_data = next((r for r in results if r["person_name"] == selected_person), None)

if not person_data:
    st.error("Person data not found")
    st.stop()

events = person_data.get("career_events", [])

st.subheader(f"Career Timeline: {selected_person}")
st.caption(f"Total events: {len(events)} | Chunks analyzed: {person_data.get('chunks_analyzed', 0)}")

with st.sidebar:
    st.header("Filters")
    
    all_metatypes = sorted(list(set(e.get("metatype", "unknown") for e in events)))
    selected_metatypes = st.multiselect("Metatype", all_metatypes, default=all_metatypes)
    
    all_types = sorted(list(set(e.get("type", "unknown") for e in events)))
    selected_types = st.multiselect("Type", all_types, default=all_types)
    
    show_undated = st.checkbox("Show undated events", value=True)

filtered_events = [
    e for e in events 
    if e.get("metatype") in selected_metatypes 
    and e.get("type") in selected_types
    and (show_undated or e.get("start_date") or e.get("end_date"))
]

tab1, tab2, tab3 = st.tabs(["Timeline View", "Table View", "Event Details"])

with tab1:
    st.markdown("### Chronological Timeline")
    
    sorted_events = sorted(filtered_events, key=get_year_range)
    
    for i, event in enumerate(sorted_events):
        start_year = parse_year(event.get("start_date", ""))
        end_year = parse_year(event.get("end_date", ""))
        
        col1, col2 = st.columns([1, 4])
        
        with col1:
            st.markdown(f"**{format_date_range(event)}**")
        
        with col2:
            metatype_color = {
                "govt": "🔵",
                "private": "🟢",
                "io": "🟣",
                "academic": "🟡",
                "think_tank": "🟠",
                "ngo": "🔴"
            }.get(event.get("metatype"), "⚪")
            
            st.markdown(f"{metatype_color} **{event.get('role', 'Unknown role')}** at *{event.get('organization', 'Unknown org')}*")
            
            if event.get("description"):
                st.caption(event["description"])
            
            tags = event.get("tags", [])
            if tags:
                st.caption(" • ".join(tags))
            
            with st.expander(f"Sources ({len(event.get('source_urls', []))})"):
                for url in event.get("source_urls", []):
                    st.markdown(f"- {url}")
        
        if i < len(sorted_events) - 1:
            st.divider()

with tab2:
    st.markdown("### Table View")
    
    table_data = []
    for event in sorted_events:
        table_data.append({
            "Dates": format_date_range(event),
            "Organization": event.get("organization", ""),
            "Role": event.get("role", ""),
            "Metatype": event.get("metatype", ""),
            "Type": event.get("type", ""),
            "Sources": len(event.get("source_urls", []))
        })
    
    st.dataframe(table_data, use_container_width=True, height=600)

with tab3:
    st.markdown("### Detailed Event Inspector")
    
    event_labels = [
        f"{format_date_range(e)} - {e.get('organization', 'Unknown')} - {e.get('role', 'Unknown')}"
        for e in sorted_events
    ]
    
    selected_event_idx = st.selectbox("Select event", range(len(sorted_events)), format_func=lambda i: event_labels[i])
    
    if selected_event_idx is not None:
        event = sorted_events[selected_event_idx]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Organization**")
            st.write(event.get("organization", "Unknown"))
            
            st.markdown("**Role**")
            st.write(event.get("role", "Unknown"))
            
            st.markdown("**Dates**")
            st.write(format_date_range(event))
        
        with col2:
            st.markdown("**Metatype**")
            st.write(event.get("metatype", "unknown"))
            
            st.markdown("**Type**")
            st.write(event.get("type", "unknown"))
            
            st.markdown("**Tags**")
            st.write(", ".join(event.get("tags", [])))
        
        st.markdown("**Description**")
        st.write(event.get("description", "No description"))
        
        st.markdown("**Source URLs**")
        for url in event.get("source_urls", []):
            st.markdown(f"- {url}")
        
        st.markdown("**Source Chunks**")
        st.code(", ".join(event.get("source_chunk_ids", [])))
        
        st.markdown("**Raw Event Data**")
        st.json(event)

with st.sidebar:
    st.divider()
    st.caption("Gap Analysis")
    
    dated_events = [e for e in sorted_events if parse_year(e.get("start_date", "")) or parse_year(e.get("end_date", ""))]
    
    if dated_events:
        years = []
        for e in dated_events:
            start = parse_year(e.get("start_date", ""))
            end = parse_year(e.get("end_date", ""))
            if start:
                years.append(start)
            if end:
                years.append(end)
        
        if years:
            min_year = min(years)
            max_year = max(years)
            span = max_year - min_year
            
            st.metric("Career Span", f"{min_year}-{max_year}")
            st.metric("Years Covered", f"{span} years")
            st.metric("Events with Dates", f"{len(dated_events)}/{len(events)}")