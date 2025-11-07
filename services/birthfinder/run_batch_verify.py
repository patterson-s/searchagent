#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
run_batch_verify.py
Run the sequence-independent birthfinder v2 verification for the first N distinct names.
"""

import json
import subprocess
from pathlib import Path
from tkinter.font import names

def main():
    base_dir = Path(__file__).parent
    verify_script = base_dir / "run_full_pipeline_verify_v2.py"
    chunks_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_01.json")

    # load unique names in order
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    seen, names = set(), []
    for c in chunks:
        nm = (c.get("person_name") or "").strip()
        if nm and nm not in seen:
            seen.add(nm)
            names.append(nm)

    #N = 5
    #target_names = names[:N]
    target_names = names

    print("=" * 100)
    print(f"Batch v2: will run for {len(target_names)} names (showing):")
    for i, n in enumerate(target_names, 1):
        print(f"  {i}. {n}")
    print("=" * 100)

    for i, name in enumerate(target_names, 1):
        print(f"\n[{i}/{len(target_names)}] Processing: {name}\n" + "-"*100)
        subprocess.run(
            [
                "python",
                str(verify_script),
                "--person", name,
                "--topn", "10",
                "--max_scans", "10",
            ],
            capture_output=False,
            text=True,
            check=False,
        )
        print("-"*100 + f"\nFinished: {name}\n")

    print("\nAll done!\n")

if __name__ == "__main__":
    main()
