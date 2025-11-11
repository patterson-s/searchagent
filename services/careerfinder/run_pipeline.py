#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/careerfinder/run_pipeline.py

import json
from pathlib import Path
from typing import Any, Dict, List
import argparse
import time

from select_chunks_embeddings import find_career_chunks
from run_stage1 import run_stage1_profiling
from run_stage3 import run_stage3_extraction_single_chunk
from run_stage3_deduplicate import deduplicate_events
from run_stage4 import run_stage4_enrichment

def load_chunks_map(chunks_path: Path) -> Dict[str, Dict[str, Any]]:
    with open(chunks_path, "r", encoding="utf-8") as f:
        arr = json.load(f)
    return {row["chunk_id"]: row for row in arr}

def main():
    base_dir = Path(__file__).parent
    chunks_path = Path(r"C:\Users\spatt\Desktop\searchagent\data\hlp_fulltext_chunks_01.json")
    config_path = base_dir / "config_01.json"
    out_path = base_dir / "outputs" / "careerfinder_results.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Careerfinder: comprehensive career extraction pipeline.")
    parser.add_argument("--person", type=str, help="Target person name.")
    args = parser.parse_args()

    print("=" * 100)
    print("Careerfinder: comprehensive career extraction (all chunks)")
    print("=" * 100)

    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)
    if not all_chunks:
        raise ValueError("No chunks found.")

    if args.person and args.person.strip():
        person_name = args.person.strip()
    else:
        person_name = all_chunks[0]["person_name"]

    chunk_map = load_chunks_map(chunks_path)

    try:
        print(f"\n=== STAGE 1: Profiling ALL chunks for {person_name} ===\n")
        person_chunks = find_career_chunks(person_name, chunks_path)
        
        profiles = []
        for i, chunk_data in enumerate(person_chunks, 1):
            chunk_id = chunk_data["chunk_id"]
            
            print(f"[{i}/{len(person_chunks)}] Profiling {chunk_id}...")
            try:
                profile = run_stage1_profiling(
                    person_name, 
                    chunk_data["text"], 
                    chunk_id, 
                    chunk_data.get("source_url", "unknown"),
                    config_path
                )
                profiles.append(profile)
            except Exception as e:
                print(f"  ERROR profiling {chunk_id}: {e}")
                time.sleep(2)
                continue
        
        print(f"\n=== STAGE 2: SKIPPED (processing all chunks individually) ===\n")
        
        print(f"\n=== STAGE 3: Extracting events from {len(person_chunks)} chunks ===\n")
        all_events = []
        for i, chunk_data in enumerate(person_chunks, 1):
            print(f"[{i}/{len(person_chunks)}] Processing {chunk_data['chunk_id']}...")
            try:
                events = run_stage3_extraction_single_chunk(person_name, chunk_data, config_path)
                if events:
                    print(f"  Extracted {len(events)} event(s)")
                    all_events.extend(events)
                else:
                    print(f"  No events found")
            except Exception as e:
                print(f"  ERROR processing {chunk_data['chunk_id']}: {e}")
                time.sleep(2)
                continue
        
        print(f"\n=== STAGE 3b: Deduplicating {len(all_events)} raw events ===\n")
        deduplicated_events = deduplicate_events(all_events)
        print(f"After deduplication: {len(deduplicated_events)} unique events")
        
        print(f"\n=== STAGE 4: Enriching {len(deduplicated_events)} events with metadata ===\n")
        enriched_events = []
        for i, event in enumerate(deduplicated_events, 1):
            print(f"[{i}/{len(deduplicated_events)}] Enriching: {event.get('organization', 'Unknown')} - {event.get('role', 'Unknown')}")
            
            try:
                source_texts = []
                for chunk_id in event.get("source_chunk_ids", []):
                    chunk_data = chunk_map.get(chunk_id)
                    if chunk_data:
                        source_texts.append(chunk_data.get("text", ""))
                
                combined_source = "\n\n".join(source_texts)
                enriched = run_stage4_enrichment(event, combined_source, config_path)
                
                source_urls = event.get("source_url", [])
                if isinstance(source_urls, str):
                    source_urls = [source_urls]
                enriched["source_urls"] = list(set(source_urls))
                
                enriched_events.append(enriched)
            except Exception as e:
                print(f"  ERROR enriching event: {e}")
                enriched_events.append(event)
                time.sleep(2)
                continue
        
        enriched_events.sort(key=lambda e: (e.get("start_date") or e.get("end_date") or "9999", e.get("end_date") or "9999"))
        
        result = {
            "person_name": person_name,
            "career_events": enriched_events,
            "total_events": len(enriched_events),
            "chunks_analyzed": len(person_chunks),
            "raw_events_extracted": len(all_events)
        }

        print("\n=== SUMMARY ===")
        print(f"Total career events extracted: {len(enriched_events)}")
        print(f"Raw events before deduplication: {len(all_events)}")
        print(f"Chunks analyzed: {len(person_chunks)}")
        
        with open(out_path, "a", encoding="utf-8") as f_out:
            f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
            f_out.flush()
        
        print(f"\nSaved -> {out_path.resolve()}\n")
        
    except Exception as e:
        print(f"\n!!! CRITICAL ERROR for {person_name}: {e}")
        print("Saving partial results if available...")
        
        result = {
            "person_name": person_name,
            "career_events": [],
            "total_events": 0,
            "chunks_analyzed": 0,
            "raw_events_extracted": 0,
            "error": str(e)
        }
        
        with open(out_path, "a", encoding="utf-8") as f_out:
            f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
            f_out.flush()

if __name__ == "__main__":
    main()