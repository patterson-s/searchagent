#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
import argparse
from select_chunks_embeddings import find_education_chunks
from run_prompt import run_stage1_extraction, run_stage2_structuring

def parse_stage1_output(text: str) -> Tuple[bool, List[str]]:
    found = False
    mentions = []

    m = re.search(r"education_found:\s*(true|false)", text, flags=re.IGNORECASE)
    if m and m.group(1).lower() == "true":
        found = True

    m2 = re.search(r"education_mentions:\s*\[(.*?)\]", text, flags=re.IGNORECASE | re.DOTALL)
    if m2:
        mentions_str = m2.group(1)
        mentions = re.findall(r'"([^"]+)"', mentions_str)

    return found, mentions

def parse_stage2_output(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    
    try:
        data = json.loads(text)
        return data.get("education_events", [])
    except json.JSONDecodeError:
        return []

def load_chunks_map(chunks_path: Path) -> Dict[str, Dict[str, Any]]:
    with open(chunks_path, "r", encoding="utf-8") as f:
        arr = json.load(f)
    return {row["chunk_id"]: row for row in arr}

def main():
    base_dir = Path(__file__).parent
    embeddings_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_embedded.jsonl")
    chunks_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_01.json")
    config_path = base_dir / "config_01.json"
    out_path = base_dir / "outputs" / "educationfinder_results.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Educationfinder: two-stage education extraction.")
    parser.add_argument("--person", type=str, help="Target person name.")
    parser.add_argument("--topn", type=int, default=10)
    parser.add_argument("--max_scans", type=int, default=10)
    args = parser.parse_args()

    print("=" * 100)
    print("Educationfinder: Stage 1 (extract) -> Stage 2 (structure)")
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
    candidates = find_education_chunks(person_name, embeddings_path, topk=args.topn)
    candidates = [c for c in candidates if c.get("person_name") == person_name]

    if not candidates:
        output = {
            "person_name": person_name,
            "education_events": [],
            "raw_mentions": [],
            "sources": []
        }
        with out_path.open("a", encoding="utf-8") as f_out:
            f_out.write(json.dumps(output, ensure_ascii=False) + "\n")
        print("\nResult:", json.dumps(output, ensure_ascii=False, indent=2))
        return

    all_mentions = []
    sources = []
    scanned = 0

    print("\n--- Stage 1: Extracting education mentions ---\n")

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

        out = run_stage1_extraction(person_name, text, config_path)
        found, mentions = parse_stage1_output(out)

        if not found or not mentions:
            print(f"[{scanned}/{args.max_scans}] {domain} -> no education info")
            continue

        print(f"[{scanned}/{args.max_scans}] {domain} -> {len(mentions)} mention(s)")
        for m in mentions:
            all_mentions.append(m)
            sources.append({
                "url": url,
                "chunk_index": chunk_index,
                "domain": domain,
                "mention": m
            })

    if not all_mentions:
        output = {
            "person_name": person_name,
            "education_events": [],
            "raw_mentions": [],
            "sources": []
        }
        with out_path.open("a", encoding="utf-8") as f_out:
            f_out.write(json.dumps(output, ensure_ascii=False) + "\n")
        print("\nResult:", json.dumps(output, ensure_ascii=False, indent=2))
        return

    print(f"\n--- Stage 2: Structuring {len(all_mentions)} mention(s) into events ---\n")
    
    stage2_out = run_stage2_structuring(person_name, all_mentions, config_path)
    events = parse_stage2_output(stage2_out)

    result = {
        "person_name": person_name,
        "education_events": events,
        "raw_mentions": all_mentions,
        "sources": sources
    }

    print("\n=== SUMMARY ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    with out_path.open("a", encoding="utf-8") as f_out:
        f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"\nSaved -> {out_path.resolve()}\n")

if __name__ == "__main__":
    main()