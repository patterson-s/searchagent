#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
report_birthfinder_summary.py
Summarize verification outcomes from birthfinder_verified_v2.jsonl:
- triangulated (verified=2)
- found but not triangulated (verified=1)
- not found (verified=0)
"""

import json
from pathlib import Path
from collections import Counter

def main():
    results_path = Path(r"C:\Users\spatt\Desktop\searchagent\services\birthfinder\outputs\birthfinder_verified_v2.jsonl")

    counts = Counter()
    total = 0
    missing = 0
    outcomes = Counter()

    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            total += 1
            verified = rec.get("verified", None)
            outcome = rec.get("corroboration_outcome", "unknown")
            outcomes[outcome] += 1

            if verified == 2:
                counts["triangulated"] += 1
            elif verified == 1:
                counts["found_not_triangulated"] += 1
            elif verified == 0:
                counts["not_found"] += 1
            else:
                missing += 1

    print("=" * 80)
    print("Birthfinder verification summary")
    print("=" * 80)
    print(f"Total people processed     : {total}")
    print(f"Triangulated (verified=2)  : {counts['triangulated']}")
    print(f"Found but not triangulated : {counts['found_not_triangulated']}")
    print(f"Not found (verified=0)     : {counts['not_found']}")
    if missing:
        print(f"Missing/other              : {missing}")
    print("-" * 80)
    print("Breakdown by corroboration_outcome:")
    for k, v in outcomes.items():
        print(f"  {k:<25} {v}")
    print("=" * 80)

if __name__ == "__main__":
    main()
