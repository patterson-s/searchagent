#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict


def load_events(events_path: Path, person_name: str) -> List[Dict]:
    events = []
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            if data.get("person_name") == person_name:
                events = data.get("career_events", [])
                break
    return events


def load_ontology(ontology_path: Path) -> Dict:
    with open(ontology_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_raw_org_names(events: List[Dict]) -> Set[str]:
    org_names = set()
    for event in events:
        org = event.get("organization", "")
        if org:
            org_names.add(org)
    return org_names


def extract_canonical_units(ontology: Dict) -> List[Dict]:
    units = []
    for employer in ontology.get("employers", []):
        for unit in employer.get("org_units", []):
            units.append({
                "employer_name": employer.get("employer_name"),
                "unit_name": unit.get("unit_name"),
                "unit": unit
            })
    return units


def analyze_consolidation(raw_orgs: Set[str], canonical_units: List[Dict]) -> Dict:
    total_raw = len(raw_orgs)
    total_canonical = len(canonical_units)
    
    ratio = total_raw / total_canonical if total_canonical > 0 else 0
    
    variant_mapping = {}
    for unit_info in canonical_units:
        unit = unit_info["unit"]
        canonical_name = unit.get("unit_name")
        variants = unit.get("variant_names", [])
        
        for variant in variants:
            if variant in raw_orgs:
                variant_mapping[variant] = canonical_name
        
        if canonical_name in raw_orgs:
            variant_mapping[canonical_name] = canonical_name
    
    return {
        "total_raw_orgs": total_raw,
        "total_canonical_units": total_canonical,
        "consolidation_ratio": ratio,
        "unmapped_count": len(raw_orgs - set(variant_mapping.keys()))
    }


def analyze_coverage(events: List[Dict], canonical_units: List[Dict]) -> Dict:
    total_events = len(events)
    
    event_to_unit = defaultdict(list)
    
    for unit_info in canonical_units:
        unit = unit_info["unit"]
        provenance = unit.get("provenance", {})
        contributing_events = provenance.get("contributing_events", [])
        
        for event_idx in contributing_events:
            event_to_unit[event_idx].append({
                "employer": unit_info["employer_name"],
                "unit": unit_info["unit_name"]
            })
    
    mapped_event_indices = set(event_to_unit.keys())
    orphaned_count = len(set(range(total_events)) - mapped_event_indices)
    
    employer_coverage = defaultdict(int)
    for unit_info in canonical_units:
        employer = unit_info["employer_name"]
        unit = unit_info["unit"]
        event_count = unit.get("provenance", {}).get("event_count", 0)
        employer_coverage[employer] += event_count
    
    return {
        "total_events": total_events,
        "mapped_events": len(mapped_event_indices),
        "orphaned_events": orphaned_count,
        "coverage_percentage": (len(mapped_event_indices) / total_events * 100) if total_events > 0 else 0,
        "employer_coverage": dict(employer_coverage)
    }


def evaluate_single_ontology(ontology_path: Path, events_path: Path) -> Dict:
    ontology = load_ontology(ontology_path)
    person_name = ontology.get("person_name", "")
    
    if not person_name:
        return None
    
    events = load_events(events_path, person_name)
    if not events:
        return None
    
    raw_orgs = extract_raw_org_names(events)
    canonical_units = extract_canonical_units(ontology)
    
    consolidation = analyze_consolidation(raw_orgs, canonical_units)
    coverage = analyze_coverage(events, canonical_units)
    
    return {
        "person_name": person_name,
        "file_name": ontology_path.name,
        "consolidation": consolidation,
        "coverage": coverage
    }


def print_summary_table(results: List[Dict]):
    print("\n" + "=" * 140)
    print("BATCH EVALUATION SUMMARY")
    print("=" * 140)
    print(f"{'Person':<30} {'Raw Orgs':<10} {'Canon':<10} {'Ratio':<8} {'Events':<10} {'Mapped':<10} {'Coverage':<10}")
    print("-" * 140)
    
    total_raw = 0
    total_canonical = 0
    total_events = 0
    total_mapped = 0
    
    for result in results:
        person = result["person_name"][:28]
        cons = result["consolidation"]
        cov = result["coverage"]
        
        ratio = f"{cons['consolidation_ratio']:.1f}:1"
        coverage_pct = f"{cov['coverage_percentage']:.1f}%"
        
        print(f"{person:<30} {cons['total_raw_orgs']:<10} {cons['total_canonical_units']:<10} {ratio:<8} {cov['total_events']:<10} {cov['mapped_events']:<10} {coverage_pct:<10}")
        
        total_raw += cons['total_raw_orgs']
        total_canonical += cons['total_canonical_units']
        total_events += cov['total_events']
        total_mapped += cov['mapped_events']
    
    print("-" * 140)
    avg_ratio = total_raw / total_canonical if total_canonical > 0 else 0
    overall_coverage = (total_mapped / total_events * 100) if total_events > 0 else 0
    
    print(f"{'TOTALS':<30} {total_raw:<10} {total_canonical:<10} {avg_ratio:.1f}:1  {total_events:<10} {total_mapped:<10} {overall_coverage:.1f}%")
    print("=" * 140)


def main():
    base_dir = Path(__file__).parent
    outputs_dir = base_dir / "outputs"
    events_file = Path(r"..\..\data\careerfinder_results.jsonl")
    
    ontology_files = [f for f in outputs_dir.glob("*_enriched.json")]
    
    if not ontology_files:
        print("ERROR: No enriched ontology files found in outputs/")
        return
    
    print(f"Found {len(ontology_files)} enriched ontology files")
    print(f"Events file: {events_file}")
    print()
    
    results = []
    errors = []
    
    for i, ontology_file in enumerate(ontology_files, 1):
        try:
            result = evaluate_single_ontology(ontology_file, events_file)
            if result:
                results.append(result)
            else:
                errors.append(f"{ontology_file.name}: No person name or events found")
        except Exception as e:
            errors.append(f"{ontology_file.name}: {str(e)}")
    
    if results:
        results.sort(key=lambda x: x["person_name"])
        print_summary_table(results)
    
    if errors:
        print("\n" + "=" * 140)
        print("ERRORS")
        print("=" * 140)
        for error in errors:
            print(f"  {error}")
    
    print()


if __name__ == "__main__":
    main()