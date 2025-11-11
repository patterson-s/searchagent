#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/careerfinder/select_chunks_embeddings.py

import json
from pathlib import Path
from typing import List, Dict, Any

def find_career_chunks(person_name: str, chunks_path: Path) -> List[Dict[str, Any]]:
    """Return ALL chunks for a person - no filtering."""
    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)
    
    person_chunks = [c for c in all_chunks if c.get("person_name") == person_name]
    
    print("=" * 80)
    print(f"Found {len(person_chunks)} total chunks for {person_name}")
    print("=" * 80)
    
    return person_chunks

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Get all chunks for a person.")
    parser.add_argument("--chunks", type=Path,
                        default=Path("../../data/hlp_fulltext_chunks_01.json"))
    parser.add_argument("--person", default="Anand Panyarachun")
    args = parser.parse_args()

    results = find_career_chunks(args.person, args.chunks)
    print(f"\nRetrieved {len(results)} chunks for {args.person}")