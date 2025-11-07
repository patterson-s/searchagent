#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Pipeline runner: combine search (chunk selection) + LLM extraction for birthyear detection.
"""

import json, time
from pathlib import Path
from select_birth_chunks import score_chunk, domain_of, greedy_diverse_topk
from run_birthfinder_prompt import run_birth_prompt_on_chunk

def load_chunks(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def search_top_chunks(chunks, person_name, topk=3, min_score=0):
    """Inline equivalent of select_birth_chunks logic, simplified for direct reuse."""
    person_chunks = [c for c in chunks if c.get("person_name") == person_name]
    scored = []
    for c in person_chunks:
        text = c.get("text") or c.get("preview") or ""
        s = score_chunk(text, person_name)
        if s >= min_score:
            scored.append({
                "score": round(s, 3),
                "domain": domain_of(c.get("source_url", "")),
                "person_name": person_name,
                "source_title": c.get("source_title"),
                "source_url": c.get("source_url"),
                "chunk_id": c.get("chunk_id"),
                "chunk_index": c.get("chunk_index"),
                "text": text
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    picked = greedy_diverse_topk(scored, k=topk)
    return picked

def main():
    chunks_path = Path("../../data/hlp_fulltext_chunks_01.json")
    config_path = Path("config_01.json")
    results_path = Path("outputs/birthfinder_results.jsonl")
    results_path.parent.mkdir(parents=True, exist_ok=True)

    all_chunks = load_chunks(chunks_path)
    person_name = all_chunks[0]["person_name"]
    top_chunks = search_top_chunks(all_chunks, person_name, topk=3)

    print("=" * 100)
    print(f"Running full pipeline for {person_name} — {len(top_chunks)} chunks")
    print("=" * 100)

    with results_path.open("w", encoding="utf-8") as f_out:
        for i, c in enumerate(top_chunks, 1):
            print(f"\n----- Chunk {i} ({c['domain']}) -----\n")
            result = run_birth_prompt_on_chunk(person_name, c["text"], config_path)
            print(result)
            record = {
                "person_name": person_name,
                "chunk_id": c["chunk_id"],
                "source_url": c["source_url"],
                "score": c["score"],
                "response": result
            }
            f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
            time.sleep(1)

    print(f"\nSaved results to {results_path.resolve()}")

if __name__ == "__main__":
    main()
