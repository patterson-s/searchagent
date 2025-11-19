#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/org_ontology/enrich_ontology_with_provenance.py

import json
from pathlib import Path
from typing import Dict, List

def build_org_provenance(events: List[Dict]) -> Dict:
    """Map each organization to the events that mentioned it"""
    org_to_events = {}
    
    for idx, event in enumerate(events):
        org = event.get("organization", "")
        if not org:
            continue
            
        if org not in org_to_events:
            org_to_events[org] = {
                "event_indices": [],
                "source_chunks": [],
                "source_urls": []
            }
        
        org_to_events[org]["event_indices"].append(idx)
        
        chunks = event.get("source_chunk_ids", [])
        if isinstance(chunks, list):
            org_to_events[org]["source_chunks"].extend(chunks)
        elif chunks:
            org_to_events[org]["source_chunks"].append(chunks)
        
        urls = event.get("source_urls", []) or event.get("source_url", [])
        if isinstance(urls, str):
            urls = [urls]
        if isinstance(urls, list):
            org_to_events[org]["source_urls"].extend(urls)
    
    for org in org_to_events:
        org_to_events[org]["source_chunks"] = list(set(org_to_events[org]["source_chunks"]))
        org_to_events[org]["source_urls"] = list(set(org_to_events[org]["source_urls"]))
    
    return org_to_events

def attach_provenance_to_units(ontology: Dict, org_provenance: Dict, events: List[Dict]) -> Dict:
    """Add provenance info to each org_unit in the ontology"""
    
    for employer in ontology.get("employers", []):
        for unit in employer.get("org_units", []):
            all_event_indices = []
            all_chunks = []
            all_urls = []
            
            for variant in unit.get("variant_names", []):
                if variant in org_provenance:
                    prov = org_provenance[variant]
                    all_event_indices.extend(prov["event_indices"])
                    all_chunks.extend(prov["source_chunks"])
                    all_urls.extend(prov["source_urls"])
            
            unit_name = unit.get("unit_name", "")
            if unit_name in org_provenance:
                prov = org_provenance[unit_name]
                all_event_indices.extend(prov["event_indices"])
                all_chunks.extend(prov["source_chunks"])
                all_urls.extend(prov["source_urls"])
            
            all_event_indices = sorted(list(set(all_event_indices)))
            all_chunks = list(set(all_chunks))
            all_urls = list(set(all_urls))
            
            dates = []
            for idx in all_event_indices:
                if idx < len(events):
                    event = events[idx]
                    start = event.get("start_date", "")
                    end = event.get("end_date", "")
                    if start:
                        dates.append(start)
                    if end:
                        dates.append(end)
            
            unit["provenance"] = {
                "contributing_events": all_event_indices,
                "event_count": len(all_event_indices),
                "source_chunks": all_chunks,
                "source_urls": all_urls,
                "date_range_from_events": {
                    "earliest": min(dates) if dates else None,
                    "latest": max(dates) if dates else None
                }
            }
    
    return ontology

def print_provenance_summary(ontology: Dict):
    print("\n" + "=" * 100)
    print("PROVENANCE ENRICHMENT SUMMARY")
    print("=" * 100)
    
    total_units = 0
    units_with_provenance = 0
    total_events_referenced = set()
    
    for employer in ontology.get("employers", []):
        employer_name = employer.get("employer_name", "Unknown")
        print(f"\n📍 {employer_name}")
        
        for unit in employer.get("org_units", []):
            total_units += 1
            unit_name = unit.get("unit_name", "Unknown")
            prov = unit.get("provenance", {})
            
            event_count = prov.get("event_count", 0)
            if event_count > 0:
                units_with_provenance += 1
                
            event_indices = prov.get("contributing_events", [])
            total_events_referenced.update(event_indices)
            
            chunk_count = len(prov.get("source_chunks", []))
            url_count = len(prov.get("source_urls", []))
            date_range = prov.get("date_range_from_events", {})
            
            earliest = date_range.get("earliest", "?")
            latest = date_range.get("latest", "?")
            date_str = f"{earliest}-{latest}" if earliest and latest else "no dates"
            
            print(f"  ├── {unit_name}")
            print(f"      Events: {event_count}, Chunks: {chunk_count}, URLs: {url_count}, Dates: {date_str}")
    
    print("\n" + "=" * 100)
    print(f"Total units: {total_units}")
    print(f"Units with provenance: {units_with_provenance}")
    print(f"Unique events referenced: {len(total_events_referenced)}")
    print("=" * 100)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enrich existing ontology with provenance from raw events")
    parser.add_argument("--ontology", required=True, help="Path to existing ontology JSON file")
    parser.add_argument("--events", required=True, help="Path to careerfinder JSONL output")
    parser.add_argument("--person", required=True, help="Person name")
    parser.add_argument("--output", required=True, help="Path for enriched ontology output")
    args = parser.parse_args()

    print("=" * 100)
    print("ENRICHING ONTOLOGY WITH PROVENANCE")
    print("=" * 100)
    print()
    
    print(f"Loading ontology from: {args.ontology}")
    with open(args.ontology, "r", encoding="utf-8") as f:
        ontology = json.load(f)
    
    employers_count = len(ontology.get("employers", []))
    units_count = sum(len(e.get("org_units", [])) for e in ontology.get("employers", []))
    print(f"  Loaded: {employers_count} employers, {units_count} units")
    print()
    
    print(f"Loading events from: {args.events}")
    events = []
    with open(args.events, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            if data.get("person_name") == args.person:
                events = data.get("career_events", [])
                break
    
    if not events:
        print(f"ERROR: No career events found for {args.person}")
        exit(1)
    
    print(f"  Loaded: {len(events)} career events")
    print()
    
    print("Building organization-to-event provenance map...")
    org_provenance = build_org_provenance(events)
    print(f"  Mapped {len(org_provenance)} organizations to events")
    print()
    
    print("Attaching provenance to ontology units...")
    enriched_ontology = attach_provenance_to_units(ontology, org_provenance, events)
    print("  ✓ Provenance attached")
    print()
    
    print_provenance_summary(enriched_ontology)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched_ontology, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Enriched ontology saved to: {output_path}")
