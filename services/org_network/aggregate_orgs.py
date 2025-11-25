import json
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

def load_enriched_files(input_dir: Path) -> List[Dict]:
    files = list(input_dir.glob("*_enriched.json"))
    data = []
    for file in files:
        with open(file, encoding='utf-8') as f:
            content = json.load(f)
            content['source_file'] = file.stem.replace('_enriched', '')
            data.append(content)
    return data

def create_org_key(name: str, sector: str, country: str = None) -> str:
    parts = [name.lower().strip(), sector]
    if country:
        parts.append(country.lower().strip())
    return "::".join(parts)

def aggregate_organizations(data: List[Dict]) -> Dict:
    org_map = {}
    unit_map = {}
    edges = []
    
    for person_data in data:
        person_name = person_data['source_file']
        
        for employer in person_data.get('employers', []):
            org_key = create_org_key(
                employer['employer_name'],
                employer['sector'],
                employer.get('country')
            )
            
            if org_key not in org_map:
                org_map[org_key] = {
                    'id': org_key,
                    'name': employer['employer_name'],
                    'type': 'employer',
                    'sector': employer['sector'],
                    'employer_type': employer['employer_type'],
                    'country': employer.get('country'),
                    'people': set(),
                    'people_count': 0
                }
            
            org_map[org_key]['people'].add(person_name)
            
            for unit in employer.get('org_units', []):
                unit_key = create_org_key(
                    f"{employer['employer_name']}::{unit['unit_name']}",
                    employer['sector'],
                    employer.get('country')
                )
                
                if unit_key not in unit_map:
                    unit_map[unit_key] = {
                        'id': unit_key,
                        'name': unit['unit_name'],
                        'full_name': f"{employer['employer_name']} - {unit['unit_name']}",
                        'type': 'unit',
                        'unit_type': unit['unit_type'],
                        'sector': employer['sector'],
                        'country': employer.get('country'),
                        'hierarchy_level': unit['hierarchy_level'],
                        'parent_org': org_key,
                        'people': set(),
                        'people_count': 0
                    }
                
                unit_map[unit_key]['people'].add(person_name)
                
                edges.append({
                    'source': org_key,
                    'target': unit_key,
                    'type': 'contains_unit'
                })
                
                if unit.get('parent_unit_id'):
                    parent_key = None
                    for other_unit in employer.get('org_units', []):
                        if other_unit['unit_id'] == unit['parent_unit_id']:
                            parent_key = create_org_key(
                                f"{employer['employer_name']}::{other_unit['unit_name']}",
                                employer['sector'],
                                employer.get('country')
                            )
                            break
                    
                    if parent_key:
                        edges.append({
                            'source': parent_key,
                            'target': unit_key,
                            'type': 'parent_unit'
                        })
    
    for org in org_map.values():
        org['people_count'] = len(org['people'])
        org['people'] = sorted(list(org['people']))
    
    for unit in unit_map.values():
        unit['people_count'] = len(unit['people'])
        unit['people'] = sorted(list(unit['people']))
    
    nodes = list(org_map.values()) + list(unit_map.values())
    
    return {
        'nodes': nodes,
        'edges': edges,
        'stats': {
            'total_organizations': len(org_map),
            'total_units': len(unit_map),
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'sectors': list(set(n['sector'] for n in nodes))
        }
    }

def main():
    import sys
    
    if len(sys.argv) > 1:
        input_dir = Path(sys.argv[1])
    else:
        input_dir = Path("../org_ontology/outputs")
    
    output_dir = Path(".")
    
    print("Loading enriched files...")
    data = load_enriched_files(input_dir)
    print(f"Loaded {len(data)} files")
    
    print("Aggregating organizations...")
    graph = aggregate_organizations(data)
    
    print(f"\nStats:")
    print(f"  Organizations: {graph['stats']['total_organizations']}")
    print(f"  Units: {graph['stats']['total_units']}")
    print(f"  Total nodes: {graph['stats']['total_nodes']}")
    print(f"  Total edges: {graph['stats']['total_edges']}")
    print(f"  Sectors: {', '.join(graph['stats']['sectors'])}")
    
    output_file = output_dir / "master_graph.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to {output_file}")

if __name__ == "__main__":
    main()