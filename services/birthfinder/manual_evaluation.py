import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st

# -------------------------------
# Config (adjust paths as needed)
# -------------------------------
DEFAULT_RESULTS_PATH = r"C:\\Users\\spatt\\Desktop\\searchagent\\services\\birthfinder\\outputs\\birthfinder_verified_v2.jsonl"
DEFAULT_CHUNKS_PATH = r"C:\\Users\\spatt\\Desktop\\searchagent\\data\\hlp_fulltext_chunks_01.json"
DEFAULT_ANNOTATIONS_OUT = r"C\\Users\\spatt\\Desktop\\searchagent\\services\\birthfinder\\outputs\\birthfinder_human_ratings.jsonl"

# -------------------------------
# Utilities
# -------------------------------
BIRTH_PATTERNS = [
    re.compile(r"\bborn\s*\(?\s*(\d{4})\s*\)?", re.IGNORECASE),
    re.compile(r"\((\d{4})\s*[–-]"),  # e.g., (1932– )
    re.compile(r"\bb\.\s*(\d{4})\b", re.IGNORECASE),
]
FOUR_DIGIT_YEAR = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")


def normalize_year(value: Optional[str]) -> Optional[str]:
    """Normalize any string like '1932-08-09' or 'Aug 9, 1932' to '1932'.
    Returns None if no 4-digit year found.
    """
    if value is None:
        return None
    if isinstance(value, int):
        val = str(value)
    else:
        val = str(value)
    m = re.search(r"(\\d{4})", val)
    return m.group(1) if m else None


def extract_candidate_years(text: str) -> List[str]:
    years = set()
    for pat in BIRTH_PATTERNS:
        for m in pat.finditer(text):
            years.add(m.group(1))
    for m in FOUR_DIGIT_YEAR.finditer(text):
        years.add(m.group(0))
    return list(years)


def safe_read_jsonl(path: str) -> List[Dict]:
    records = []
    if not path or not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def safe_write_jsonl_atomic(path: str, records: List[Dict]):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if os.path.exists(path):
        os.remove(path)
    os.replace(temp_path, path)


@st.cache_data(show_spinner=False)
def load_results(results_path: str) -> List[Dict]:
    return safe_read_jsonl(results_path)


@st.cache_data(show_spinner=False)
def load_chunks_index(chunks_path: str) -> Dict[Tuple[str, Optional[str]], List[Dict]]:
    """Index chunks by (person_name_normalized, source_url or None)."""
    index: Dict[Tuple[str, Optional[str]], List[Dict]] = {}
    if not chunks_path or not os.path.exists(chunks_path):
        return index
    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except Exception:
        return index
    for ch in chunks:
        name = (ch.get("person_name") or "").strip().lower()
        url = (ch.get("source_url") or None)
        key = (name, url)
        index.setdefault(key, []).append(ch)
        broad_key = (name, None)
        index.setdefault(broad_key, []).append(ch)
    for k in index:
        index[k].sort(key=lambda x: (x.get("source_index", 1e9), x.get("chunk_index", 1e9)))
    return index


def validating_chunks(
    person_name: str,
    predicted_year: Optional[str],
    source_url: Optional[str],
    chunks_index: Dict[Tuple[str, Optional[str]], List[Dict]],
    max_k: int = 2,
) -> Tuple[List[Dict], Optional[str]]:
    """Return (list_of_validating_chunks <= max_k, evidence_suggested_year).

    A chunk *validates* if:
      - predicted_year is set AND the chunk contains that year; OR
      - the chunk contains a birth-pattern year equal to predicted_year.

    If predicted_year is None, we'll pick up to max_k chunks with any birth pattern
    and also return the most frequent candidate year as evidence_suggested_year.
    """
    name_key = (person_name.strip().lower(), source_url or None)
    broad_key = (person_name.strip().lower(), None)

    candidates = chunks_index.get(name_key, []) or chunks_index.get(broad_key, []) or []
    if not candidates:
        return [], None

    validated: List[Dict] = []
    year_counts: Dict[str, int] = {}

    for ch in candidates:
        text = ch.get("text") or ""
        cands = extract_candidate_years(text)
        for y in cands:
            year_counts[y] = year_counts.get(y, 0) + 1
        if predicted_year:
            if predicted_year in text or predicted_year in cands:
                validated.append(ch)
        else:
            # no prediction -> accept chunks that at least show a birth-like year
            if any(y for y in cands):
                validated.append(ch)
        if len(validated) >= max_k:
            break

    suggested = None
    if not predicted_year and year_counts:
        # pick most frequent year as a soft suggestion
        suggested = sorted(year_counts.items(), key=lambda kv: kv[1], reverse=True)[0][0]

    return validated[:max_k], suggested


def bold_year(text: str, year: Optional[str]) -> str:
    if not text:
        return ""
    if not year:
        return text
    safe_text = text.replace("*", "\\*")
    return safe_text.replace(year, f"**{year}**")


# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(page_title="Birth Year Validator", layout="wide")
st.title("Birth Year Validation – Human Review")

with st.sidebar:
    st.header("Files")
    results_path = st.text_input("Results JSONL", value=DEFAULT_RESULTS_PATH)
    chunks_path = st.text_input("Chunks JSON", value=DEFAULT_CHUNKS_PATH)
    annotations_path = st.text_input("Save annotations to", value=DEFAULT_ANNOTATIONS_OUT)
    reviewer = st.text_input("Reviewer (optional)", value=os.getenv("USERNAME", "rater"))

    st.header("Filters")
    # Outcome filter: default exclude no_evidence
    allowed_outcomes_default = ["verified", "no_corroboration", "conflict_inconclusive", "conflict_resolved"]
    outcome_options = ["verified", "no_corroboration", "conflict_inconclusive", "conflict_resolved", "no_evidence"]
    selected_outcomes = st.multiselect(
        "Corroboration outcome",
        options=outcome_options,
        default=allowed_outcomes_default,
        help="Select which result types to review. 'no_evidence' is excluded by default.",
    )
    only_tiebreak = st.checkbox(
        "Only tiebreak cases (conflict_resolved / conflict_inconclusive or tie_breaker flag)",
        value=False,
    )
    unreviewed_only = st.checkbox("Only show unreviewed", value=False)

# Load data
results = load_results(results_path)
chunks_index = load_chunks_index(chunks_path)

if not results:
    st.warning("No results loaded. Check the Results path in the sidebar.")
    st.stop()

# Load existing annotations
existing_annotations = safe_read_jsonl(annotations_path)
ann_by_key: Dict[str, Dict] = {}
for rec in existing_annotations:
    key = rec.get("key")
    if key:
        ann_by_key[key] = rec


def record_key(person_name: str, source_url: Optional[str]) -> str:
    base = f"{person_name.strip().lower()}|{source_url or 'none'}"
    return base


# Build rows with robust field extraction
rows: List[Dict] = []
for r in results:
    person = r.get("person_name") or r.get("name") or ""
    predicted = r.get("predicted_birth_year") or r.get("predicted_year") or r.get("answer") or r.get("model_answer")
    predicted_norm = normalize_year(predicted)
    url = r.get("source_url") or r.get("url") or None
    outcome = (r.get("corroboration_outcome") or r.get("outcome") or "").strip() or "unknown"
    # derive tiebreak flag broadly
    tiebreak = bool(r.get("tie_breaker") or (outcome in ("conflict_resolved", "conflict_inconclusive")))

    rows.append({
        "person_name": person,
        "predicted_birth_year": predicted_norm,
        "raw_predicted": predicted,
        "source_url": url,
        "corroboration_outcome": outcome,
        "tiebreak": tiebreak,
        "raw": r,
    })

# Compute visible set according to filters
visible_indices: List[int] = []
for i, row in enumerate(rows):
    # outcome filter
    if row["corroboration_outcome"] not in selected_outcomes:
        continue
    # tiebreak filter
    if only_tiebreak and not row["tiebreak"]:
        continue
    key = record_key(row["person_name"], row["source_url"])
    if unreviewed_only and key in ann_by_key:
        continue
    visible_indices.append(i)

if not visible_indices:
    st.success("No items match the current filters.")
    st.stop()

# Progress & index state
total = len(rows)
reviewed_count = len(ann_by_key)
if "idx" not in st.session_state:
    st.session_state.idx = 0
if st.session_state.idx >= len(visible_indices):
    st.session_state.idx = 0
cur_i = visible_indices[st.session_state.idx]
row = rows[cur_i]

st.caption(
    f"Reviewed: {reviewed_count}/{total} | Showing item {st.session_state.idx+1} of {len(visible_indices)} (filtered)"
)

# Claim card, with big predicted year
with st.container(border=True):
    st.subheader(f"Claim: What is the birth year of **{row['person_name']}**?")
    # prominent predicted year
    colP, colURL, colOutcome = st.columns([1, 1.5, 1])
    with colP:
        st.markdown("**Predicted birth year**")
        st.markdown(
            f"<h2 style='margin-top:0'>{row['predicted_birth_year'] or 'N/A'}</h2>",
            unsafe_allow_html=True,
        )
    with colURL:
        st.markdown("**Source URL**")
        st.write(row["source_url"] or "(none)")
    with colOutcome:
        st.markdown("**Outcome**")
        st.write(row["corroboration_outcome"])  

# Evidence selection (only validating chunks, max 2)
chunks, suggested_year = validating_chunks(
    person_name=row["person_name"],
    predicted_year=row["predicted_birth_year"],
    source_url=row["source_url"],
    chunks_index=chunks_index,
    max_k=2,
)

with st.container(border=True):
    st.markdown("### Evidence (validating chunks only)")
    if not chunks:
        st.info("No validating local chunk found. Use the source URL to verify.")
        if suggested_year and not row["predicted_birth_year"]:
            st.caption(f"Evidence suggests year: {suggested_year}")
    else:
        for idx, ch in enumerate(chunks, start=1):
            text = ch.get("text") or ""
            shown = bold_year(text, row["predicted_birth_year"] or suggested_year)
            st.text_area(
                f"Validating chunk #{idx} — id: {ch.get('chunk_id')}",
                value=shown,
                height=220,
                key=f"ta_valid_{cur_i}_{idx}",
            )

# Existing annotation (if any)
key = record_key(row["person_name"], row["source_url"])
existing = ann_by_key.get(key)
prev_judgment = (existing or {}).get("judgment", "correct")
prev_correct_year = (existing or {}).get("correct_year", "")
prev_notes = (existing or {}).get("notes", "")

# If outcome is no_evidence, disable the form (should be excluded by default anyway)
form_disabled = row["corroboration_outcome"] == "no_evidence"

with st.form(key=f"form_{cur_i}"):
    st.markdown("### Validation")
    if form_disabled:
        st.warning("This record is 'no_evidence' and is not eligible for evaluation.")

    judgment = st.radio(
        "Assessment",
        options=["correct", "flag_mismatch"],
        index=0 if prev_judgment == "correct" else 1,
        help="Default is 'correct'. Choose 'flag_mismatch' if the predicted year is wrong or missing.",
        horizontal=True,
        disabled=form_disabled,
    )
    correct_year = st.text_input(
        "Correct birth year (YYYY)",
        value=str(prev_correct_year or ""),
        help="Optional. Provide the correct year if you know it.",
        disabled=form_disabled,
    )
    notes = st.text_area(
        "Notes (why is this wrong / any context?)",
        value=prev_notes,
        height=120,
        disabled=form_disabled,
    )

    nav_cols = st.columns([1, 1, 6, 1, 1])
    with nav_cols[0]:
        prev_btn = st.form_submit_button("◀ Previous")
    with nav_cols[1]:
        skip_btn = st.form_submit_button("Skip")
    with nav_cols[-2]:
        save_btn = st.form_submit_button("💾 Save", disabled=form_disabled)
    with nav_cols[-1]:
        next_btn = st.form_submit_button("Next ▶")

    if (save_btn or next_btn or prev_btn) and not form_disabled:
        cy_norm = normalize_year(correct_year) if correct_year else None
        if judgment == "flag_mismatch" and not (cy_norm or notes.strip()):
            st.warning("When flagging, please add a note or a correct year.")
        else:
            out_rec = {
                "key": key,
                "person_name": row["person_name"],
                "predicted_birth_year": row["predicted_birth_year"] or suggested_year,
                "raw_predicted": row["raw_predicted"],
                "judgment": judgment,
                "correct_year": cy_norm,
                "notes": notes,
                "source_url_used": row["source_url"],
                "evidence_chunk_id": chunks[0].get("chunk_id") if chunks else None,
                "reviewer": reviewer,
                "timestamp_iso": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "corroboration_outcome": row["corroboration_outcome"],
                "tiebreak": row["tiebreak"],
            }
            ann_by_key[key] = out_rec
            out_list = list(ann_by_key.values())
            os.makedirs(os.path.dirname(annotations_path), exist_ok=True)
            safe_write_jsonl_atomic(annotations_path, out_list)
            st.toast("Saved", icon="✅")

    # Navigation logic
    if next_btn or save_btn:
        st.session_state.idx = (st.session_state.idx + 1) % len(visible_indices)
        st.experimental_rerun()
    elif prev_btn:
        st.session_state.idx = (st.session_state.idx - 1) % len(visible_indices)
        st.experimental_rerun()
    elif skip_btn:
        st.session_state.idx = (st.session_state.idx + 1) % len(visible_indices)
        st.experimental_rerun()

# Footer
st.divider()
colA, colB, colC = st.columns(3)
with colA:
    if st.button("Export CSV of annotations"):
        import csv
        rows_out = list(ann_by_key.values())
        csv_path = Path(annotations_path).with_suffix(".csv")
        fieldnames = [
            "key",
            "person_name",
            "predicted_birth_year",
            "raw_predicted",
            "judgment",
            "correct_year",
            "notes",
            "source_url_used",
            "evidence_chunk_id",
            "reviewer",
            "timestamp_iso",
            "corroboration_outcome",
            "tiebreak",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows_out:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        st.success(f"CSV exported to: {csv_path}")
with colB:
    st.caption("Use the sidebar filters to switch between triangulated, non-triangulated, and tiebreak cases.")
with colC:
    st.caption("Evidence is limited to chunks that actually validate the claim (max 2).")
