#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/org_ontology/batch_enrich_ontologies.py

import json
import subprocess
from pathlib import Path

def get_person_name_from_ontology(ontology_path: Path) -> str:
    """Extract person name from ontology file"""
    with open(ontology_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("person_name", "")

def main():
    base_dir = Path(__file__).parent
    ontology_dir = base_dir / "outputs"
    events_file = Path(r"..\..\data\careerfinder_results.jsonl")
    enrichment_script = base_dir / "enrich_ontology_with_provenance.py"
    
    ontology_files = list(ontology_dir.glob("*.json"))
    
    if not ontology_files:
        print("ERROR: No JSON files found in outputs directory")
        return
    
    print("=" * 100)
    print(f"BATCH ENRICHMENT: Found {len(ontology_files)} ontology files")
    print("=" * 100)
    print()
    
    success_count = 0
    error_count = 0
    
    for i, ontology_file in enumerate(ontology_files, 1):
        if ontology_file.stem.endswith("_enriched"):
            print(f"[{i}/{len(ontology_files)}] Skipping {ontology_file.name} (already enriched)")
            continue
        
        print(f"[{i}/{len(ontology_files)}] Processing {ontology_file.name}")
        
        try:
            person_name = get_person_name_from_ontology(ontology_file)
            
            if not person_name:
                print(f"  ERROR: Could not extract person name from {ontology_file.name}")
                error_count += 1
                continue
            
            print(f"  Person: {person_name}")
            
            output_file = ontology_dir / f"{ontology_file.stem}_enriched.json"
            
            result = subprocess.run(
                [
                    "python",
                    str(enrichment_script),
                    "--ontology", str(ontology_file),
                    "--events", str(events_file),
                    "--person", person_name,
                    "--output", str(output_file)
                ],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"  [OK] Success: {output_file.name}")
                success_count += 1
            else:
                print(f"  [ERROR] {result.stderr[:200]}")
                error_count += 1
        
        except Exception as e:
            print(f"  [ERROR] Exception: {e}")
            error_count += 1
        
        print()
    
    print("=" * 100)
    print("BATCH ENRICHMENT COMPLETE")
    print("=" * 100)
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Total: {len(ontology_files)}")
    print("=" * 100)

if __name__ == "__main__":
    main()
