# services/deathfinder/run_pipeline_verify.py
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import argparse
from select_chunks_embeddings import find_death_chunks
from run_prompt import run_death_prompt_on_chunk

YEAR_RE = re.compile(r"\b(1[6-9]\d{2}|20\d{2})\b")

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
    for n in ["bbc.", "reuters.", "apnews.", "nytimes.", "guardian.", "france24.", "cnn.", "aljazeera.", "ft.com"]:
        if n in d:
            return "news"
    if "wordpress." in d or "blogspot." in d or "substack." in d or "medium." in d:
        return "blog"
    return "other"

def evidence_type_from_text(text: str) -> str:
    t = (text or "").lower()
    if "obituary" in t or "memorial" in t:
        return "obituary"
    if "died" in t or "death" in t or " d. " in t:
        return "death-narrative"
    if "current" in t or "serves as" in t or "is the" in t:
        return "alive-current"
    return "other"

def quality_rank(evidence_type: str) -> int:
    order = {
        "obituary": 0,
        "death-narrative": 1,
        "alive-current": 1,
        "other": 2,
    }
    return order.get(evidence_type, 3)

def parse_death_prompt_output(text: str) -> Tuple[str, Optional[int]]:
    status = "unknown"
    year = None

    m = re.search(r"status:\s*(deceased|alive|unknown)", text, flags=re.IGNORECASE)
    if m:
        status = m.group(1).lower()

    m2 = re.search(r"death_year:\s*(null|\d{4})", text, flags=re.IGNORECASE)
    if m2:
        val = m2.group(1).lower()
        if val != "null":
            try:
                y = int(val)
                if 1600 <= y <= 2099:
                    year = y
            except Exception:
                pass

    if status == "deceased" and year is None:
        m3 = YEAR_RE.search(text)
        if m3:
            y = int(m3.group(0))
            if 1600 <= y <= 2099:
                year = y

    return status, year

def load_chunks_map(chunks_path: Path) -> Dict[str, Dict[str, Any]]:
    with open(chunks_path, "r", encoding="utf-8") as f:
        arr = json.load(f)
    return {row["chunk_id"]: row for row in arr}

def main():
    base_dir = Path(__file__).parent
    embeddings_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_embedded.jsonl")
    chunks_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_01.json")
    config_path = base_dir / "config_01.json"
    out_path = base_dir / "outputs" / "deathfinder_verified.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Deathfinder: death year or alive status verification.")
    parser.add_argument("--person", type=str, help="Target person name.")
    parser.add_argument("--topn", type=int, default=10)
    parser.add_argument("--max_scans", type=int, default=10)
    args = parser.parse_args()

    print("=" * 100)
    print("Deathfinder: embedding retrieval -> LLM extraction -> vote-based verification")
    print("=" * 100)

    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)
    if not all_chunks:
        raise ValueError("No chunks found.")

    if args.person and args.person.strip():
        person_name = args.person.strip()
    else:
        person_name = all_chunks[0]["person_name"]

    chunk_map = load_chunks_map(chunks_path)

    print(f"Retrieving top {args.topn} semantic candidates for: {person_name}")
    candidates = find_death_chunks(person_name, embeddings_path, topk=args.topn)
    candidates = [c for c in candidates if c.get("person_name") == person_name]

    if not candidates:
        output = {
            "person_name": person_name,
            "status": "unknown",
            "death_year": None,
            "verified": 0,
            "corroboration_outcome": "no_evidence",
            "scanned": 0,
        }
        with out_path.open("a", encoding="utf-8") as f_out:
            f_out.write(json.dumps(output, ensure_ascii=False) + "\n")
        print("\nResult:", json.dumps(output, ensure_ascii=False, indent=2))
        return

    year_ledgers: Dict[int, Dict[str, Any]] = {}
    alive_signals: List[Dict[str, Any]] = []
    scanned = 0

    print("\n--- Scanning for death/alive evidence ---\n")

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

        out = run_death_prompt_on_chunk(person_name, text, config_path)
        status, year = parse_death_prompt_output(out)

        etype = evidence_type_from_text(text)
        qrank = quality_rank(etype)

        if status == "deceased" and year:
            print(f"[{scanned}/{args.max_scans}] {domain} -> deceased, year={year} ({etype})")
            if year not in year_ledgers:
                year_ledgers[year] = {
                    "count": 0,
                    "domains": set(),
                    "sources": []
                }
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
            if year_ledgers[year]["count"] >= 2:
                break
        elif status == "alive":
            print(f"[{scanned}/{args.max_scans}] {domain} -> alive ({etype})")
            alive_signals.append({
                "url": url,
                "chunk_index": chunk_index,
                "domain": domain,
                "evidence_type": etype,
            })
        else:
            print(f"[{scanned}/{args.max_scans}] {domain} -> unknown")

    if year_ledgers:
        max_count = max(v["count"] for v in year_ledgers.values())
        top_years = [y for y, v in year_ledgers.items() if v["count"] == max_count]
        
        if max_count >= 2:
            winner_year = top_years[0]
            final_status = "deceased"
            verified = 2
            outcome = "verified"
        else:
            winner_year = top_years[0]
            final_status = "deceased"
            verified = 1
            outcome = "no_corroboration"
    elif alive_signals:
        alive_domains = set(s["domain"] for s in alive_signals)
        if len(alive_domains) >= 2:
            final_status = "alive"
            winner_year = None
            verified = 2
            outcome = "verified"
        else:
            final_status = "alive"
            winner_year = None
            verified = 1
            outcome = "no_corroboration"
    else:
        final_status = "unknown"
        winner_year = None
        verified = 0
        outcome = "no_evidence"

    result = {
        "person_name": person_name,
        "status": final_status,
        "death_year": winner_year,
        "verified": verified,
        "corroboration_outcome": outcome,
        "scanned": scanned,
        "death_year_sources": year_ledgers.get(winner_year, {}).get("sources", []) if winner_year else [],
        "alive_signals": alive_signals if final_status == "alive" else [],
    }

    print("\n=== SUMMARY ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    with out_path.open("a", encoding="utf-8") as f_out:
        f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"\nSaved -> {out_path.resolve()}\n")

if __name__ == "__main__":
    main()