#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
run_full_pipeline_verify_v2.py

Sequence-independent, vote-based verification:
- Retrieve up to N chunks via embedding search (diverse domains preferred via your retriever).
- For each chunk (in ranked order), run the DOB extractor prompt (unchanged).
- Collect ANY birth years found, keyed by year with independent-source counting (by domain).
- Stop early as soon as any year reaches TWO independent sources (verified).
- If multiple years appear, continue scanning up to K chunks as tie-breaker.
- Outcomes:
  - verified=2, corroboration_outcome="verified"            -> >=2 independent matches for one year
  - verified=2, corroboration_outcome="conflict_resolved"   -> conflict observed but a year won on counts/quality
  - verified=1, corroboration_outcome="no_corroboration"    -> some DOB found, never reached 2
  - verified=1, corroboration_outcome="conflict_inconclusive" -> different years observed, tie not broken
  - verified=0, corroboration_outcome="no_evidence"         -> no DOB in any scanned chunk
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import argparse
from select_birth_chunks_embeddings import find_birth_chunks
from run_birthfinder_prompt import run_birth_prompt_on_chunk

YEAR_RE = re.compile(r"\b(1[6-9]\d{2}|20\d{2})\b")  # 1600–2099

# ---------------------- Evidence classification helpers ----------------------

def authority_bucket(domain: str) -> str:
    d = (domain or "").lower()
    if not d:
        return "other"
    if "wikipedia.org" in d:
        return "wiki"
    if d.endswith(".gov") or ".gov." in d or "parliament" in d or "senate" in d or "gouv" in d:
        return "gov"
    if d.endswith(".edu") or ".edu." in d or ".ac." in d:
        return "edu"
    if d.endswith(".org") or ".org." in d:
        return "org"
    # a tiny news hint
    for n in ["bbc.", "reuters.", "apnews.", "nytimes.", "guardian.", "france24.", "cnn.", "aljazeera.", "ft.com"]:
        if n in d:
            return "news"
    if "wordpress." in d or "blogspot." in d or "substack." in d or "medium." in d:
        return "blog"
    return "other"

def evidence_type_from_text(text: str) -> str:
    t = (text or "").lower()
    if "date of birth" in t or "place and date of birth" in t:
        return "born-field"
    if "born" in t or "née" in t or "né " in t or " b. " in t:
        return "born-narrative"
    if " births" in t or "births" in t and "category" in t:
        return "category"
    return "other"

def quality_rank(evidence_type: str) -> int:
    # Lower is better
    order = {
        "born-field": 0,
        "born-narrative": 1,
        "other": 2,
        "category": 3,  # categories often weaker than explicit narrative for DOB
    }
    return order.get(evidence_type, 4)

def winner_by_quality(year_ledgers: Dict[int, Dict[str, Any]]) -> Optional[int]:
    """
    If counts tie, pick the year with the best (lowest) evidence quality among its sources.
    """
    if not year_ledgers:
        return None
    # First, compute max count across years
    max_count = max(v["count"] for v in year_ledgers.values())
    top_years = [y for y, v in year_ledgers.items() if v["count"] == max_count]
    if len(top_years) == 1:
        return top_years[0]

    # Tie on counts; compare best quality
    best_year = None
    best_quality = 999
    for y in top_years:
        srcs = year_ledgers[y]["sources"]
        # best (lowest) quality among that year's sources
        q = min((s.get("quality_rank", 999) for s in srcs), default=999)
        if q < best_quality:
            best_quality = q
            best_year = y
    return best_year

# ---------------------- Parsing prompt output ----------------------

def parse_birth_prompt_output(text: str) -> Tuple[bool, Optional[int]]:
    """
    Parse the minimal output from the birth prompt:
      reasoning: ...
      contains_birthdate: true|false
      birth_year: <YYYY or null>
    Returns (contains, year or None).
    """
    contains = False
    year = None

    m = re.search(r"contains_birthdate:\s*(true|false)", text, flags=re.IGNORECASE)
    if m and m.group(1).lower() == "true":
        contains = True

    m2 = re.search(r"birth_year:\s*(null|\d{4})", text, flags=re.IGNORECASE)
    if m2:
        val = m2.group(1).lower()
        if val != "null":
            try:
                y = int(val)
                if 1600 <= y <= 2099:
                    year = y
            except Exception:
                pass

    if contains and year is None:
        m3 = YEAR_RE.search(text)
        if m3:
            y = int(m3.group(0))
            if 1600 <= y <= 2099:
                year = y

    return contains, year

# ---------------------- IO helpers ----------------------

def load_chunks_map(chunks_path: Path) -> Dict[str, Dict[str, Any]]:
    with open(chunks_path, "r", encoding="utf-8") as f:
        arr = json.load(f)
    return {row["chunk_id"]: row for row in arr}

# ---------------------- Core pipeline ----------------------

def main():
    base_dir = Path(__file__).parent
    embeddings_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_embedded.jsonl")
    chunks_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_01.json")
    config_path = base_dir / "config_01.json"
    out_path = base_dir / "outputs" / "birthfinder_verified_v2.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Birthfinder v2: sequence-independent, vote-based verification.")
    parser.add_argument("--person", type=str, help="Target person name (overrides auto-detection).")
    parser.add_argument("--topn", type=int, default=10, help="Total candidates to consider from embedding search.")
    parser.add_argument("--max_scans", type=int, default=10, help="Max number of chunks to scan.")
    args = parser.parse_args()

    print("=" * 100)
    print("Birthfinder v2: embedding retrieval → LLM extraction → vote-based triangulation")
    print("=" * 100)
    print(f"Chunks input : {chunks_path}")
    print(f"Embeddings   : {embeddings_path}")
    print(f"Config file  : {config_path}\n")

    # Load chunks + determine person
    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)
    if not all_chunks:
        raise ValueError("No chunks found.")

    if args.person and args.person.strip():
        person_name = args.person.strip()
    else:
        person_name = all_chunks[0]["person_name"]

    chunk_map = load_chunks_map(chunks_path)

    # Retrieve by embeddings (top N)
    print(f"Retrieving top {args.topn} semantic candidates for: {person_name}")
    candidates = find_birth_chunks(person_name, embeddings_path, topk=args.topn)
    candidates = [c for c in candidates if c.get("person_name") == person_name]

    if not candidates:
        # No candidates from search
        output = {
            "person_name": person_name,
            "birth_year": None,
            "verified": 0,
            "corroboration_outcome": "no_evidence",
            "corroboration_attempts": 0,
            "corroboration_counts": {"match": 0, "partial": 0, "none": 0, "conflict": 0},
            "winner_year": None,
            "winner_sources": [],
            "runner_up_years": []
        }
        with out_path.open("a", encoding="utf-8") as f_out:
            f_out.write(json.dumps(output, ensure_ascii=False) + "\n")
        print("\nResult:", json.dumps(output, ensure_ascii=False, indent=2))
        return

    # Vote-based ledger
    year_ledgers: Dict[int, Dict[str, Any]] = {}
    counts = {"match": 0, "partial": 0, "none": 0, "conflict": 0}
    scanned = 0

    print("\n--- Scanning for DOB evidence (sequence-independent) ---\n")

    # Iterate top candidates up to max_scans
    for c in candidates[: args.max_scans]:
        scanned += 1
        chunk_id = c["chunk_id"]
        row = chunk_map.get(chunk_id)
        if not row:
            continue

        domain = c["domain"]
        url = row.get("source_url")
        chunk_index = row.get("chunk_index")
        text = row.get("text", "")

        out = run_birth_prompt_on_chunk(person_name, text, config_path)
        contains, year = parse_birth_prompt_output(out)

        if not contains:
            counts["none"] += 1
            print(f"[{scanned}/{args.max_scans}] {domain}  {url} -> no DOB")
            continue

        if year is None:
            counts["none"] += 1
            print(f"[{scanned}/{args.max_scans}] {domain}  {url} -> DOB present but no year parsed")
            continue

        etype = evidence_type_from_text(text)
        qrank = quality_rank(etype)
        print(f"[{scanned}/{args.max_scans}] {domain}  {url} -> year={year} ({etype})")

        if year not in year_ledgers:
            year_ledgers[year] = {
                "count": 0,
                "domains": set(),
                "sources": []  # list of dicts
            }

        # Count per independent domain
        if domain not in year_ledgers[year]["domains"]:
            year_ledgers[year]["count"] += 1
            year_ledgers[year]["domains"].add(domain)

        year_ledgers[year]["sources"].append({
            "url": url,
            "chunk_index": chunk_index,
            "domain": domain,
            "evidence_type": etype,
            "quality_rank": qrank
        })

        # Early stop: any year reached TWO independent sources?
        if year_ledgers[year]["count"] >= 2:
            winner_year = year
            outcome = "verified" if len(year_ledgers) == 1 else "conflict_resolved"
            verified = 2
            break
    else:
        # No early break; decide outcome post-hoc
        if not year_ledgers:
            winner_year = None
            outcome = "no_evidence"
            verified = 0
        else:
            # Find highest count
            max_count = max(v["count"] for v in year_ledgers.values())
            top_years = [y for y, v in year_ledgers.items() if v["count"] == max_count]

            if max_count >= 2 and len(top_years) == 1:
                winner_year = top_years[0]
                outcome = "verified" if len(year_ledgers) == 1 else "conflict_resolved"
                verified = 2
            elif len(year_ledgers) == 1:
                # Only one year seen, but never reached 2 sources
                winner_year = next(iter(year_ledgers.keys()))
                outcome = "no_corroboration"
                verified = 1
            else:
                # Conflict between multiple years
                # Try quality tie-break
                winner_year = winner_by_quality(year_ledgers)
                if winner_year is not None and year_ledgers[winner_year]["count"] >= 2:
                    outcome = "conflict_resolved"
                    verified = 2
                else:
                    outcome = "conflict_inconclusive"
                    verified = 1

    # Format summary lists
    winner_sources = year_ledgers.get(winner_year, {}).get("sources", []) if winner_year is not None else []
    runner_up_years = [
        {"year": y, "count": v["count"], "sample_source": (v["sources"][0] if v["sources"] else None)}
        for y, v in year_ledgers.items()
        if winner_year is None or y != winner_year
    ]

    result = {
        "person_name": person_name,
        "birth_year": winner_year,
        "verified": verified,
        "corroboration_outcome": outcome,
        "corroboration_attempts": scanned,
        "corroboration_counts": counts,
        "winner_year": winner_year,
        "winner_sources": winner_sources,
        "runner_up_years": runner_up_years
    }

    print("\n=== SUMMARY (v2) ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    with out_path.open("a", encoding="utf-8") as f_out:
        f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"\nSaved → {out_path.resolve()}\n")

if __name__ == "__main__":
    main()
