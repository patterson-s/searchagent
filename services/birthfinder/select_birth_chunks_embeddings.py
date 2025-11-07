#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
select_birth_chunks_embeddings.py
Semantic search for birthdate-relevant chunks using Cohere Embed v4.
"""

import os
import json
import time
import numpy as np
from pathlib import Path
from urllib.parse import urlparse
import cohere

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def greedy_diverse_topk(candidates, k=3):
    """Greedy pick ensuring domain diversity."""
    picked, seen_domains = [], set()
    for c in candidates:
        if len(picked) >= k:
            break
        if c["domain"] not in seen_domains:
            picked.append(c)
            seen_domains.add(c["domain"])
    if len(picked) < k:
        for c in candidates:
            if len(picked) >= k:
                break
            if c in picked:
                continue
            picked.append(c)
    return picked[:k]

# ---------------------------------------------------------------------
# Main search
# ---------------------------------------------------------------------

def find_birth_chunks(person_name: str,
                      embedded_path: Path,
                      topk: int = 3,
                      min_similarity: float = 0.2):
    """Return top-k chunks semantically similar to a birth-date query."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise EnvironmentError("Set COHERE_API_KEY first")

    co = cohere.Client(api_key)
    query = f"date of birth or birth information of {person_name}"
    q_emb = co.embed(model="embed-v4.0", texts=[query]).embeddings[0]

    # Load embedded chunks
    records = []
    with open(embedded_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("person_name") == person_name:
                rec["similarity"] = cosine_similarity(q_emb, rec["embedding"])
                rec["domain"] = domain_of(rec.get("source_url", ""))
                if rec["similarity"] >= min_similarity:
                    records.append(rec)

    records.sort(key=lambda x: x["similarity"], reverse=True)
    top = greedy_diverse_topk(records, k=topk)

    print("=" * 80)
    print(f"Top {len(top)} semantic matches for {person_name}:")
    for i, r in enumerate(top, 1):
        print(f"[{i}] sim={r['similarity']:.3f}  domain={r['domain']}")
        print(f"    url   : {r.get('source_url')}")
        print(f"    chunk : {r.get('chunk_id')}")
    print("=" * 80)

    return top

# CLI test mode -------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Semantic search for birth-date chunks.")
    parser.add_argument("--embedded", type=Path,
                        default=Path("../../data/hlp_fulltext_chunks_embedded.jsonl"))
    parser.add_argument("--person", default="Anand Panyarachun")
    parser.add_argument("--topk", type=int, default=3)
    args = parser.parse_args()

    results = find_birth_chunks(args.person, args.embedded, topk=args.topk)
    print(f"\nRetrieved {len(results)} chunks for {args.person}")
