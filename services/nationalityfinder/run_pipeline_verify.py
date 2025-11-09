#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import argparse
from select_chunks_embeddings import find_nationality_chunks
from run_prompt import run_nationality_prompt_on_chunk

def parse_nationality_prompt_output(text: str) -> Tuple[bool, List[str]]:
    found = False
    nationalities = []

    m = re.search(r"nationalities_found:\s*(true|false)", text, flags=re.IGNORECASE)
    if m and m.group(1).lower() == "true":
        found = True

    m2 = re.search(r"nationalities:\s*\[(.*?)\]", text, flags=re.IGNORECASE | re.DOTALL)
    if m2:
        codes_str = m2.group(1)
        codes = re.findall(r'"([A-Z]{3})"', codes_str)
        nationalities = list(set(codes))

    return found, nationalities

def load_chunks_map(chunks_path: Path) -> Dict[str, Dict[str, Any]]:
    with open(chunks_path, "r", encoding="utf-8") as f:
        arr = json.load(f)
    return {row["chunk_id"]: row for row in arr}

def main():
    base_dir = Path(__file__).parent
    embeddings_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_embedded.jsonl")
    chunks_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_01.json")
    config_path = base_dir / "config_01.json"
    out_path = base_dir / "outputs" / "nationalityfinder_verified.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Nationalityfinder: nationality/citizenship verification.")
    parser.add_argument("--person", type=str, help="Target person name.")
    parser.add_argument("--topn", type=int, default=10)
    parser.add_argument("--max_scans", type=int, default=10)
    args = parser.parse_args()

    print("=" * 100)
    print("Nationalityfinder: embedding retrieval -> LLM extraction -> vote-based verification")
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
    candidates = find_nationality_chunks(person_name, embeddings_path, topk=args.topn)
    candidates = [c for c in candidates if c.get("person_name") == person_name]

    if not candidates:
        output = {
            "person_name": person_name,
            "nationalities": [],
            "unverified_nationalities": [],
            "verified": 0,
            "corroboration_outcome": "no_evidence",
            "scanned": 0,
        }
        with out_path.open("a", encoding="utf-8") as f_out:
            f_out.write(json.dumps(output, ensure_ascii=False) + "\n")
        print("\nResult:", json.dumps(output, ensure_ascii=False, indent=2))
        return

    nationality_ledgers: Dict[str, Dict[str, Any]] = {}
    scanned = 0

    print("\n--- Scanning for nationality evidence ---\n")

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

        out = run_nationality_prompt_on_chunk(person_name, text, config_path)
        found, nationalities = parse_nationality_prompt_output(out)

        if not found or not nationalities:
            print(f"[{scanned}/{args.max_scans}] {domain} -> no nationality")
            continue

        print(f"[{scanned}/{args.max_scans}] {domain} -> {nationalities}")

        for nat in nationalities:
            if nat not in nationality_ledgers:
                nationality_ledgers[nat] = {
                    "count": 0,
                    "domains": set(),
                    "sources": []
                }
            if domain not in nationality_ledgers[nat]["domains"]:
                nationality_ledgers[nat]["count"] += 1
                nationality_ledgers[nat]["domains"].add(domain)
            nationality_ledgers[nat]["sources"].append({
                "url": url,
                "chunk_index": chunk_index,
                "domain": domain,
            })
        
        if any(ledger["count"] >= 2 for ledger in nationality_ledgers.values()):
            break

    verified_nats = [nat for nat, ledger in nationality_ledgers.items() if ledger["count"] >= 2]
    unverified_nats = [nat for nat, ledger in nationality_ledgers.items() if ledger["count"] == 1]

    if verified_nats:
        verified = 2
        outcome = "verified"
    elif unverified_nats:
        verified = 1
        outcome = "partial"
    else:
        verified = 0
        outcome = "no_evidence"

    result = {
        "person_name": person_name,
        "nationalities": verified_nats,
        "unverified_nationalities": unverified_nats,
        "verified": verified,
        "corroboration_outcome": outcome,
        "scanned": scanned,
        "nationality_details": {
            nat: {
                "count": ledger["count"],
                "sources": ledger["sources"]
            }
            for nat, ledger in nationality_ledgers.items()
        }
    }

    print("\n=== SUMMARY ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    with out_path.open("a", encoding="utf-8") as f_out:
        f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"\nSaved -> {out_path.resolve()}\n")

if __name__ == "__main__":
    main()