#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any

import cohere  # pip install cohere

def chunkify(lst: List[Any], size: int) -> List[List[Any]]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]

def main():
    input_path  = Path("hlp_fulltext_chunks_01.json")
    output_path = Path("hlp_fulltext_chunks_embedded.jsonl")
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise EnvironmentError("Environment variable COHERE_API_KEY is missing")

    co = cohere.Client(api_key)
    # Choose model: embed-v4.0 is the recommended version
    model_name = "embed-v4.0"

    # Load chunks
    with open(input_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    if not isinstance(chunks, list):
        raise ValueError("Expecting a list of chunks")

    batch_size = 64  # pick a comfortable size
    print(f"Total chunks to embed: {len(chunks)}")

    with open(output_path, "w", encoding="utf-8") as fout:
        for batch in chunkify(chunks, batch_size):
            texts = [c.get("text", "")[:3000] for c in batch]  # optionally truncate
            resp = co.embed(model=model_name, texts=texts)
            embeddings = resp.embeddings
            for c, emb in zip(batch, embeddings):
                out = {
                    "chunk_id"    : c.get("chunk_id"),
                    "person_name" : c.get("person_name"),
                    "source_url"  : c.get("source_url"),
                    "embedding"   : emb,
                }
                fout.write(json.dumps(out, ensure_ascii=False) + "\n")
            print(f"Embedded batch of {len(batch)} chunks — pausing")
            time.sleep(1)  # polite pause

    print(f"Finished embeddings. Wrote to {output_path}")

if __name__ == "__main__":
    main()
