#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/careerfinder/run_stage2.py

import re
from typing import Dict, List, Set
from collections import defaultdict

def extract_years(temporal_markers: List[str]) -> Set[int]:
    years = set()
    for marker in temporal_markers:
        year_matches = re.findall(r'\b(1[6-9]\d{2}|20\d{2})\b', marker)
        for y in year_matches:
            years.add(int(y))
    return years

def normalize_org(org: str) -> str:
    org = org.lower().strip()
    org = re.sub(r'\s+', ' ', org)
    return org

def temporal_overlap(years1: Set[int], years2: Set[int], threshold: int = 5) -> bool:
    if not years1 or not years2:
        return False
    min1, max1 = min(years1), max(years1)
    min2, max2 = min(years2), max(years2)
    return not (max1 + threshold < min2 or max2 + threshold < min1)

def org_overlap(orgs1: List[str], orgs2: List[str]) -> bool:
    normed1 = {normalize_org(o) for o in orgs1}
    normed2 = {normalize_org(o) for o in orgs2}
    return len(normed1 & normed2) > 0

def cluster_profiles(profiles: List[Dict]) -> List[Dict]:
    career_profiles = [p for p in profiles if p.get("contains_career_info")]
    
    if not career_profiles:
        return []
    
    clusters = []
    assigned = set()
    
    for i, profile in enumerate(career_profiles):
        if i in assigned:
            continue
            
        cluster = {
            "cluster_id": f"c{len(clusters):03d}",
            "chunk_ids": [profile["chunk_id"]],
            "profiles": [profile],
            "temporal_range": extract_years(profile.get("temporal_markers", [])),
            "organizations": set(profile.get("organizations", [])),
            "career_domains": set(profile.get("career_domains", []))
        }
        assigned.add(i)
        
        for j, other in enumerate(career_profiles[i+1:], start=i+1):
            if j in assigned:
                continue
                
            other_years = extract_years(other.get("temporal_markers", []))
            
            temp_match = temporal_overlap(cluster["temporal_range"], other_years)
            org_match = org_overlap(
                list(cluster["organizations"]), 
                other.get("organizations", [])
            )
            
            if temp_match or org_match:
                cluster["chunk_ids"].append(other["chunk_id"])
                cluster["profiles"].append(other)
                cluster["temporal_range"].update(other_years)
                cluster["organizations"].update(other.get("organizations", []))
                cluster["career_domains"].update(other.get("career_domains", []))
                assigned.add(j)
        
        cluster["temporal_range"] = sorted(list(cluster["temporal_range"]))
        cluster["organizations"] = list(cluster["organizations"])
        cluster["career_domains"] = list(cluster["career_domains"])
        
        clusters.append(cluster)
    
    return clusters

if __name__ == "__main__":
    import json
    import sys
    
    profiles_path = sys.argv[1] if len(sys.argv) > 1 else "stage1_profiles.json"
    
    with open(profiles_path, "r", encoding="utf-8") as f:
        profiles = json.load(f)
    
    clusters = cluster_profiles(profiles)
    
    print(json.dumps(clusters, indent=2, ensure_ascii=False))