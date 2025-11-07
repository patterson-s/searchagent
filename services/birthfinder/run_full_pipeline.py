#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
run_full_pipeline.py
Full pipeline for birthfinder:
1. Retrieve top chunks using semantic embedding search
2. Send those chunks to Cohere Command-A for extraction
"""

import json
import time
from pathlib import Path
from select_birth_chunks_embeddings import find_birth_chunks
from run_birthfinder_prompt import run_birth_prompt_on_chunk


def main():
    # --- Define paths ---
    base_dir = Path(__file__).parent
    embeddings_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_embedded.jsonl")
    chunks_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_01.json")
    config_path = base_dir / "config_01.json"
    results_path = base_dir / "outputs" / "birthfinder_results.jsonl"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 100)
    print("Running full birthfinder pipeline (embedding retrieval + LLM extraction)")
    print("=" * 100)
    print(f"Chunks input : {chunks_path}")
    print(f"Embeddings   : {embeddings_path}")
    print(f"Config file  : {config_path}\n")

    # --- Step 1: Load first person name ---
    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)
    if not all_chunks:
        raise ValueError("No chunks found in input file.")
    person_name = all_chunks[0]["person_name"]

    # --- Step 2: Retrieve top chunks using embeddings ---
    selected_chunks = find_birth_chunks(person_name, embeddings_path, topk=3)

    print(f"\nRetrieved {len(selected_chunks)} candidate chunks for {person_name}.\n")

    # --- Step 3: Run Cohere prompt on each selected chunk ---
    print("\n--- Running LLM extraction on retrieved chunks ---\n")
    with results_path.open("w", encoding="utf-8") as f_out:
        for i, c in enumerate(selected_chunks, 1):
            print(f"\n===== Chunk {i} ({c['domain']}) =====\n")
            # We'll need the original chunk text from hlp_fulltext_chunks_01.json
            # find by chunk_id
            text_chunk = next((ch for ch in all_chunks if ch["chunk_id"] == c["chunk_id"]), None)
            if text_chunk is None:
                print(f"Warning: could not find text for chunk {c['chunk_id']}")
                continue
            chunk_text = text_chunk.get("text", "")

            # Run the LLM extraction
            result = run_birth_prompt_on_chunk(person_name, chunk_text, config_path)
            print(result)

            # Save results
            record = {
                "person_name": person_name,
                "chunk_id": c["chunk_id"],
                "source_url": c.get("source_url"),
                "similarity": c.get("similarity"),
                "response": result
            }
            f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
            time.sleep(1)

    print(f"\nSaved results → {results_path.resolve()}")
    print("Pipeline complete.\n")


if __name__ == "__main__":
    main()
