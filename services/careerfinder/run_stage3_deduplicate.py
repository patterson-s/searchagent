#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/careerfinder/run_stage3_deduplicate.py

import re
from typing import List, Dict, Set
from difflib import SequenceMatcher

def normalize_org(org: str) -> str:
    org = org.lower().strip()
    org = re.sub(r'\s+', ' ', org)
    org = re.sub(r'\b(the|of)\b', '', org)
    return org.strip()

def normalize_role(role: str) -> str:
    role = role.lower().strip()
    role = re.sub(r'\s+', ' ', role)
    return role

def string_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def year_overlap(start1: str, end1: str, start2: str, end2: str, threshold: int = 5) -> bool:
    """Check if two date ranges overlap within threshold years."""
    def to_year(s: str) -> int:
        if not s:
            return None
        try:
            return int(s)
        except:
            return None
    
    y1_start = to_year(start1)
    y1_end = to_year(end1)
    y2_start = to_year(start2)
    y2_end = to_year(end2)
    
    if y1_start is None and y1_end is None:
        return True
    if y2_start is None and y2_end is None:
        return True
    
    y1 = y1_end if y1_end else y1_start
    y2 = y2_end if y2_end else y2_start
    
    if y1 and y2:
        return abs(y1 - y2) <= threshold
    
    return True

def events_match(e1: Dict, e2: Dict) -> bool:
    """Determine if two events are the same position."""
    org1 = normalize_org(e1.get("organization", ""))
    org2 = normalize_org(e2.get("organization", ""))
    role1 = normalize_role(e1.get("role", ""))
    role2 = normalize_role(e2.get("role", ""))
    
    org_sim = string_similarity(org1, org2)
    role_sim = string_similarity(role1, role2)
    
    if org_sim < 0.7:
        return False
    
    if role_sim < 0.6:
        return False
    
    date_match = year_overlap(
        e1.get("start_date", ""),
        e1.get("end_date", ""),
        e2.get("start_date", ""),
        e2.get("end_date", "")
    )
    
    return date_match

def merge_events(e1: Dict, e2: Dict) -> Dict:
    """Merge two matching events, preferring more specific information."""
    merged = e1.copy()
    
    if not merged.get("organization") and e2.get("organization"):
        merged["organization"] = e2["organization"]
    elif e2.get("organization") and len(e2["organization"]) > len(merged.get("organization", "")):
        merged["organization"] = e2["organization"]
    
    if not merged.get("role") and e2.get("role"):
        merged["role"] = e2["role"]
    elif e2.get("role") and len(e2["role"]) > len(merged.get("role", "")):
        merged["role"] = e2["role"]
    
    if not merged.get("start_date") and e2.get("start_date"):
        merged["start_date"] = e2["start_date"]
    
    if not merged.get("end_date") and e2.get("end_date"):
        merged["end_date"] = e2["end_date"]
    
    if not merged.get("description") and e2.get("description"):
        merged["description"] = e2["description"]
    elif e2.get("description") and len(e2.get("description", "")) > len(merged.get("description", "")):
        merged["description"] = e2["description"]
    
    merged_chunks = list(set(merged.get("source_chunk_ids", []) + e2.get("source_chunk_ids", [])))
    merged["source_chunk_ids"] = merged_chunks
    
    merged_urls = []
    if isinstance(merged.get("source_url"), str):
        merged_urls.append(merged["source_url"])
    elif isinstance(merged.get("source_url"), list):
        merged_urls.extend(merged["source_url"])
    
    if isinstance(e2.get("source_url"), str):
        merged_urls.append(e2["source_url"])
    elif isinstance(e2.get("source_url"), list):
        merged_urls.extend(e2["source_url"])
    
    merged["source_url"] = list(set(merged_urls))
    
    return merged

def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """Deduplicate and merge overlapping events."""
    if not events:
        return []
    
    deduplicated = []
    
    for event in events:
        matched = False
        for i, existing in enumerate(deduplicated):
            if events_match(event, existing):
                deduplicated[i] = merge_events(existing, event)
                matched = True
                break
        
        if not matched:
            deduplicated.append(event)
    
    return deduplicated

if __name__ == "__main__":
    import json
    import sys
    
    events_path = sys.argv[1] if len(sys.argv) > 1 else "raw_events.json"
    
    with open(events_path, "r", encoding="utf-8") as f:
        events = json.load(f)
    
    deduped = deduplicate_events(events)
    
    print(json.dumps(deduped, indent=2, ensure_ascii=False))
    print(f"\nOriginal: {len(events)} events -> Deduplicated: {len(deduped)} events")