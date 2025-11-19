#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

# Import core logic from the existing single-person script
from generate_ontology import generate_ontology_by_sector, print_ontology_summary


def slugify(name: str) -> str:
    """Turn a person name into a safe filename slug."""
    slug = name.strip().lower()
    # Replace non-alphanumeric with underscores
    result_chars: List[str] = []
    for ch in slug:
        if ch.isalnum():
            result_chars.append(ch)
        else:
            result_chars.append("_")
    slug = "".join(result_chars)
    # Collapse multiple underscores
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "unknown"


def load_careerfinder_records(path: Path) -> List[Dict]:
    """Load all records from a careerfinder JSONL output file."""
    records: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"!! Skipping line due to JSON error: {e}", file=sys.stderr)
                continue
            records.append(data)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-generate organizational ontologies for multiple people."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to careerfinder JSONL output (one record per person).",
    )
    parser.add_argument(
        "--config",
        default="config_01.json",
        help="Path to org_ontology config JSON (default: config_01.json).",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory where per-person ontology JSON files will be written "
             "(default: outputs).",
    )
    parser.add_argument(
        "--max-people",
        type=int,
        help="Optional maximum number of people to process (for testing).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing per-person files if they already exist.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 100)
    print("BATCH ONTOLOGY GENERATION")
    print("=" * 100)
    print(f"Input file : {input_path}")
    print(f"Config file: {config_path}")
    print(f"Output dir : {output_dir}")
    if args.max_people:
        print(f"Max people : {args.max_people}")
    print()

    records = load_careerfinder_records(input_path)
    print(f"Loaded {len(records)} records from careerfinder output.\n")

    processed = 0
    skipped_no_events = 0
    skipped_existing = 0
    failures = 0
    success_people: List[str] = []

    for idx, record in enumerate(records, start=1):
        person_name = record.get("person_name")
        events = record.get("career_events") or []

        if not person_name:
            print(f"[{idx}] Skipping record with no person_name.")
            continue

        if not events:
            print(f"[{idx}] {person_name}: no career_events found, skipping.")
            skipped_no_events += 1
            continue

        slug = slugify(person_name)
        out_path = output_dir / f"{slug}.json"

        if out_path.exists() and not args.overwrite:
            print(f"[{idx}] {person_name}: output exists ({out_path}), skipping (use --overwrite to replace).")
            skipped_existing += 1
            continue

        print("\n" + "=" * 100)
        print(f"[{idx}] Generating ontology for: {person_name}")
        print("=" * 100)
        print(f"Events: {len(events)}")
        print(f"Output file: {out_path}")
        print()

        try:
            ontology = generate_ontology_by_sector(person_name, events, config_path)
        except Exception as e:
            print(f"!! ERROR while generating ontology for {person_name}: {e}", file=sys.stderr)
            failures += 1
            continue

        # Optional: brief console summary per person
        print_ontology_summary(ontology)

        # Write per-person JSON
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(ontology, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Saved ontology to: {out_path}\n")

        processed += 1
        success_people.append(person_name)

        if args.max_people is not None and processed >= args.max_people:
            print(f"Reached max-people limit ({args.max_people}). Stopping.")
            break

    print("\n" + "=" * 100)
    print("BATCH SUMMARY")
    print("=" * 100)
    print(f"Total records in input     : {len(records)}")
    print(f"Successfully processed     : {processed}")
    print(f"Skipped (no career_events) : {skipped_no_events}")
    print(f"Skipped (file exists)      : {skipped_existing} (use --overwrite to regenerate)")
    print(f"Failures (exceptions)      : {failures}")
    if success_people:
        print("\nPeople processed:")
        for name in success_people:
            print(f"  - {name}")
    print("=" * 100)


if __name__ == "__main__":
    main()
