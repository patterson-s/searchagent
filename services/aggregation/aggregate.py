import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

def normalize_person_id(name: str) -> str:
    return name.lower().replace(" ", "_")

def load_jsonl(file_path: Path) -> List[Dict]:
    records = []
    if not file_path.exists():
        return records
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def aggregate_person_data(
    person_name: str,
    birth_data: Optional[Dict],
    death_data: Optional[Dict],
    nationality_data: Optional[Dict],
    education_data: Optional[Dict],
    career_data: Optional[Dict],
    hlp_data: Optional[Dict]
) -> tuple[Dict, Dict]:
    
    person_id = normalize_person_id(person_name)
    
    data_record = {
        "person_id": person_id,
        "person_name": person_name,
        "biographical": {
            "birth_year": birth_data.get("birth_year") if birth_data else None,
            "death_year": death_data.get("death_year") if death_data else None,
            "status": death_data.get("status", "unknown") if death_data else "unknown",
            "nationalities": nationality_data.get("nationalities", []) if nationality_data else [],
            "hlp": hlp_data.get("hlp") if hlp_data else None,
            "hlp_year": hlp_data.get("hlp_year") if hlp_data else None
        },
        "education": education_data.get("education_events", []) if education_data else [],
        "career": career_data.get("career_events", []) if career_data else []
    }
    
    sources_record = {
        "person_id": person_id,
        "biographical_sources": {},
        "education_sources": [],
        "career_sources": []
    }
    
    if birth_data:
        sources_record["biographical_sources"]["birth_year"] = {
            "verified": birth_data.get("verified"),
            "corroboration_outcome": birth_data.get("corroboration_outcome"),
            "winner_sources": birth_data.get("winner_sources", [])
        }
    
    if death_data:
        sources_record["biographical_sources"]["death_year"] = {
            "status": death_data.get("status"),
            "verified": death_data.get("verified"),
            "corroboration_outcome": death_data.get("corroboration_outcome"),
            "alive_signals": death_data.get("alive_signals", []),
            "death_year_sources": death_data.get("death_year_sources", [])
        }
    
    if nationality_data:
        sources_record["biographical_sources"]["nationalities"] = {
            "verified": nationality_data.get("verified"),
            "corroboration_outcome": nationality_data.get("corroboration_outcome"),
            "nationality_details": nationality_data.get("nationality_details", {})
        }
    
    if education_data and education_data.get("education_events"):
        for idx, event in enumerate(education_data["education_events"]):
            sources_record["education_sources"].append({
                "event_index": idx,
                "sources": education_data.get("sources", [])
            })
    
    if career_data and career_data.get("career_events"):
        for idx, event in enumerate(career_data["career_events"]):
            sources_record["career_sources"].append({
                "event_index": idx,
                "source_chunk_ids": event.get("source_chunk_ids", []),
                "source_urls": event.get("source_urls", [])
            })
    
    for event in data_record["education"]:
        event.pop("raw_mentions", None)
        event.pop("sources", None)
    
    for event in data_record["career"]:
        event.pop("source_chunk_ids", None)
        event.pop("source_url", None)
        event.pop("source_urls", None)
    
    return data_record, sources_record

def run_aggregation(config_path: Path):
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    base_dir = config_path.parent
    output_dir = Path(base_dir / config["output_dir"])
    output_dir.mkdir(exist_ok=True)
    
    birth_records = load_jsonl(base_dir / config["input_files"]["birthfinder"])
    death_records = load_jsonl(base_dir / config["input_files"]["deathfinder"])
    nationality_records = load_jsonl(base_dir / config["input_files"]["nationalityfinder"])
    education_records = load_jsonl(base_dir / config["input_files"]["educationfinder"])
    career_records = load_jsonl(base_dir / config["input_files"]["careerfinder"])
    
    hlp_path = base_dir / config["input_files"]["hlp"]
    hlp_map = {}
    if hlp_path.exists():
        with open(hlp_path, 'r', encoding='utf-8') as f:
            hlp_data = json.load(f)
            for item in hlp_data:
                if isinstance(item, list) and len(item) > 0:
                    person_obj = item[0].get("person", {})
                    name = person_obj.get("name")
                    metadata = person_obj.get("metadata", {})
                    if name:
                        hlp_map[name] = {
                            "hlp": metadata.get("hlp"),
                            "hlp_year": metadata.get("hlp_year")
                        }
    
    birth_map = {r["person_name"]: r for r in birth_records}
    death_map = {r["person_name"]: r for r in death_records}
    nationality_map = {r["person_name"]: r for r in nationality_records}
    education_map = {r["person_name"]: r for r in education_records}
    career_map = {r["person_name"]: r for r in career_records}
    
    all_names = set()
    all_names.update(birth_map.keys())
    all_names.update(death_map.keys())
    all_names.update(nationality_map.keys())
    all_names.update(education_map.keys())
    all_names.update(career_map.keys())
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_output = output_dir / f"{config['output_prefix']}_data_{timestamp}.jsonl"
    sources_output = output_dir / f"{config['output_prefix']}_sources_{timestamp}.jsonl"
    log_output = output_dir / f"{config['output_prefix']}_log_{timestamp}.txt"
    
    with open(data_output, 'w', encoding='utf-8') as data_file, \
         open(sources_output, 'w', encoding='utf-8') as sources_file:
        
        for person_name in sorted(all_names):
            data_record, sources_record = aggregate_person_data(
                person_name,
                birth_map.get(person_name),
                death_map.get(person_name),
                nationality_map.get(person_name),
                education_map.get(person_name),
                career_map.get(person_name),
                hlp_map.get(person_name)
            )
            
            data_file.write(json.dumps(data_record) + "\n")
            sources_file.write(json.dumps(sources_record) + "\n")
    
    with open(log_output, 'w', encoding='utf-8') as log_file:
        log_file.write(f"Aggregation Run Log\n")
        log_file.write(f"{'='*80}\n\n")
        log_file.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
        log_file.write(f"Config:\n")
        log_file.write(json.dumps(config, indent=2))
        log_file.write(f"\n\nResults:\n")
        log_file.write(f"Total persons processed: {len(all_names)}\n")
        log_file.write(f"Output files:\n")
        log_file.write(f"  - Data: {data_output.name}\n")
        log_file.write(f"  - Sources: {sources_output.name}\n")
    
    print(f"Aggregation complete!")
    print(f"Processed {len(all_names)} persons")
    print(f"Data output: {data_output}")
    print(f"Sources output: {sources_output}")
    print(f"Log output: {log_output}")

if __name__ == "__main__":
    config_path = Path(__file__).parent / "config.json"
    run_aggregation(config_path)