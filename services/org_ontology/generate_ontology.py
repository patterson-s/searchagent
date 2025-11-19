#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/org_ontology/generate_ontology_v2.py

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
import cohere

def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def fill_template(template: str, variables: dict) -> str:
    text = template
    for k, v in variables.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text

def extract_json_from_response(text: str) -> Dict:
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
            return {}
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}

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

def get_cohere_client(config_path: Path):
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    api_key = os.getenv(cfg["api_key_env_var"])
    if not api_key:
        raise EnvironmentError(f"Missing environment variable {cfg['api_key_env_var']}")
    return cohere.ClientV2(api_key), cfg

def call_llm(co, cfg, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
    response = co.chat(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=cfg.get("temperature", 0.1),
        max_tokens=max_tokens,
    )
    
    for content in response.message.content:
        if hasattr(content, 'text'):
            return content.text
    return ""

def categorize_organizations(person_name: str, unique_orgs: List[str], config_path: Path) -> Dict:
    co, cfg = get_cohere_client(config_path)
    
    system_prompt = load_text(config_path.parent / "system_categorize.txt")
    user_prompt_template = load_text(config_path.parent / "user_categorize.txt")
    
    org_list_str = "\n".join([f"{i+1}. {org}" for i, org in enumerate(unique_orgs)])
    user_prompt = fill_template(user_prompt_template, {
        "PERSON_NAME": person_name,
        "ORGANIZATION_LIST": org_list_str
    })
    
    print("=" * 100)
    print("STAGE 1A: CATEGORIZING ORGANIZATIONS BY SECTOR")
    print("=" * 100)
    print(f"Total organizations: {len(unique_orgs)}\n")
    
    response_text = call_llm(co, cfg, system_prompt, user_prompt, max_tokens=2000)
    
    print("LLM Response:")
    print("-" * 100)
    print(response_text)
    print("-" * 100)
    print()
    
    parsed = extract_json_from_response(response_text)
    
    if not parsed:
        print("ERROR: Failed to parse categorization")
        return {"categorization": {}, "total_orgs": 0}
    
    categorization = parsed.get("categorization", {})
    
    print("CATEGORIZATION SUMMARY:")
    for sector, orgs in categorization.items():
        print(f"  {sector.upper()}: {len(orgs)} organizations")
    print()
    
    return parsed

def build_sector_ontology(person_name: str, sector: str, orgs: List[str], config_path: Path) -> Dict:
    co, cfg = get_cohere_client(config_path)
    
    system_prompt_template = load_text(config_path.parent / "system_sector.txt")
    system_prompt = fill_template(system_prompt_template, {"SECTOR": sector})
    
    user_prompt_template = load_text(config_path.parent / "user_sector.txt")
    
    org_list_str = "\n".join([f"{i+1}. {org}" for i, org in enumerate(orgs)])
    user_prompt = fill_template(user_prompt_template, {
        "PERSON_NAME": person_name,
        "SECTOR": sector,
        "ORGANIZATION_LIST": org_list_str
    })
    
    response_text = call_llm(co, cfg, system_prompt, user_prompt, max_tokens=6000)
    
    print("LLM Response:")
    print("-" * 100)
    print(response_text[:1000] + "..." if len(response_text) > 1000 else response_text)
    print("-" * 100)
    print()
    
    parsed = extract_json_from_response(response_text)
    
    if not parsed:
        print(f"  ERROR: Failed to parse {sector} ontology")
        return {
            "sector": sector,
            "employers": [],
            "completion_status": {
                "all_orgs_processed": False,
                "orgs_included": [],
                "orgs_skipped": orgs,
                "reason_for_skipping": "JSON parsing failed"
            }
        }
    
    return parsed

def merge_sector_results(main_result: Dict, retry_result: Dict):
    main_employers = main_result.get("employers", [])
    retry_employers = retry_result.get("employers", [])
    
    main_employers.extend(retry_employers)
    
    main_status = main_result.get("completion_status", {})
    retry_status = retry_result.get("completion_status", {})
    
    main_status["orgs_included"].extend(retry_status.get("orgs_included", []))
    main_status["orgs_skipped"] = retry_status.get("orgs_skipped", [])
    main_status["all_orgs_processed"] = retry_status.get("all_orgs_processed", False)

def combine_sector_ontologies(sector_results: List[Dict]) -> Dict:
    all_employers = []
    
    for result in sector_results:
        employers = result.get("employers", [])
        all_employers.extend(employers)
    
    return {
        "employers": all_employers
    }

def generate_ontology_by_sector(person_name: str, events: List[Dict], config_path: Path) -> Dict:
    unique_orgs = sorted(list(set([
        e.get("organization", "") 
        for e in events 
        if e.get("organization")
    ])))
    
    print("Building organization-to-event provenance map...")
    org_provenance = build_org_provenance(events)
    print(f"  Mapped {len(org_provenance)} organizations to {len(events)} events\n")
    
    categorization = categorize_organizations(person_name, unique_orgs, config_path)
    
    print("=" * 100)
    print("STAGE 1B: BUILDING SECTOR ONTOLOGIES")
    print("=" * 100)
    print()
    
    sector_ontologies = []
    warnings = []
    
    for sector, orgs in categorization.get("categorization", {}).items():
        if not orgs or sector == "other":
            if orgs and sector == "other":
                print(f"=== Skipping OTHER sector ({len(orgs)} orgs) ===")
                print(f"  Organizations: {', '.join(orgs[:5])}{'...' if len(orgs) > 5 else ''}\n")
            continue
        
        print(f"=== Processing {sector.upper()} sector ({len(orgs)} orgs) ===\n")
        
        sector_result = build_sector_ontology(
            person_name,
            sector,
            orgs,
            config_path
        )
        
        sector_ontologies.append(sector_result)
        
        status = sector_result.get("completion_status", {})
        all_processed = status.get("all_orgs_processed", True)
        skipped = status.get("orgs_skipped", [])
        
        if all_processed:
            print(f"  ✓ Complete - all {len(orgs)} organizations processed\n")
        else:
            reason = status.get("reason_for_skipping", "unknown")
            warning = f"{sector.upper()}: Skipped {len(skipped)} orgs - {reason}"
            warnings.append(warning)
            print(f"  ⚠️  WARNING: {warning}")
            
            if len(skipped) <= 10:
                print(f"  🔄 Retrying {len(skipped)} skipped orgs...")
                retry_result = build_sector_ontology(
                    person_name,
                    sector,
                    skipped,
                    config_path
                )
                merge_sector_results(sector_result, retry_result)
                
                retry_status = retry_result.get("completion_status", {})
                if retry_status.get("all_orgs_processed", True):
                    print(f"  ✓ Retry complete - all orgs now processed\n")
                    warnings.remove(warning)
                else:
                    print(f"  ⚠️  Retry partial - some orgs still skipped\n")
            else:
                print(f"  ⚠️  Too many skipped ({len(skipped)}) - not retrying\n")
    
    print("=" * 100)
    print("STAGE 1C: COMBINING RESULTS")
    print("=" * 100)
    
    combined = combine_sector_ontologies(sector_ontologies)
    combined["person_name"] = person_name
    
    combined["processing_report"] = {
        "total_orgs_input": len(unique_orgs),
        "orgs_categorized": categorization.get("total_orgs", 0),
        "sectors_processed": [r.get("sector") for r in sector_ontologies],
        "warnings": warnings,
        "sector_details": []
    }
    
    for result in sector_ontologies:
        sector = result.get("sector")
        status = result.get("completion_status", {})
        detail = {
            "sector": sector,
            "orgs_input": len(categorization.get("categorization", {}).get(sector, [])),
            "orgs_processed": len(status.get("orgs_included", [])),
            "orgs_skipped": len(status.get("orgs_skipped", [])),
            "complete": status.get("all_orgs_processed", True)
        }
        combined["processing_report"]["sector_details"].append(detail)
    
    return combined

def print_ontology_summary(ontology: Dict):
    print("\n" + "=" * 100)
    print("ONTOLOGY SUMMARY")
    print("=" * 100)
    
    employers = ontology.get("employers", [])
    print(f"\nTotal Employers: {len(employers)}")
    
    for employer in employers:
        print(f"\n📍 {employer.get('employer_name', 'Unknown')}")
        print(f"   Type: {employer.get('employer_type', 'unknown')}")
        print(f"   Sector: {employer.get('sector', 'unknown')}")
        
        units = employer.get("org_units", [])
        print(f"   Units: {len(units)}")
        
        unit_map = {u["unit_id"]: u for u in units}
        root_units = [u for u in units if not u.get("parent_unit_id")]
        
        def print_unit(unit, indent=0):
            prefix = "   " + "  " * indent + "├── "
            counterparty = unit.get("counterparty")
            cp_str = ""
            if counterparty:
                cp_str = f" → {counterparty.get('name', '')} ({counterparty.get('type', '')})"
            
            variants = len(unit.get("variant_names", []))
            var_str = f" [{variants} variants]" if variants > 1 else ""
            
            print(f"{prefix}{unit.get('unit_name', 'Unknown')}{cp_str}{var_str}")
            
            children = [u for u in units if u.get("parent_unit_id") == unit["unit_id"]]
            for child in children:
                print_unit(child, indent + 1)
        
        for root in root_units:
            print_unit(root, indent=1)
    
    report = ontology.get("processing_report", {})
    warnings = report.get("warnings", [])
    
    print("\n" + "=" * 100)
    print("PROCESSING REPORT")
    print("=" * 100)
    print(f"Total organizations input: {report.get('total_orgs_input', 0)}")
    print(f"Total employers identified: {len(employers)}")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("\n✓ No warnings - all organizations processed successfully")
    
    print("\nSector Details:")
    for detail in report.get("sector_details", []):
        status = "✓ Complete" if detail["complete"] else f"⚠️  Partial ({detail['orgs_skipped']} skipped)"
        print(f"  {detail['sector'].upper()}: {detail['orgs_processed']}/{detail['orgs_input']} orgs - {status}")
    
    print("=" * 100)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate organizational ontology by sector")
    parser.add_argument("--person", required=True, help="Person name")
    parser.add_argument("--input", required=True, help="Path to careerfinder JSONL output")
    parser.add_argument("--config", default="config_01.json", help="Config file")
    parser.add_argument("--output", help="Optional: Save ontology to JSON file")
    args = parser.parse_args()

    input_path = Path(args.input)
    
    events = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            if data.get("person_name") == args.person:
                events = data.get("career_events", [])
                break
    
    if not events:
        print(f"ERROR: No career events found for {args.person}")
        exit(1)
    
    print(f"\nLoaded {len(events)} career events for {args.person}\n")
    
    ontology = generate_ontology_by_sector(args.person, events, Path(args.config))
    
    print_ontology_summary(ontology)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ontology, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Ontology saved to: {output_path}")
