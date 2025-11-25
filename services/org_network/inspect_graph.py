import json
from pathlib import Path
from collections import Counter

def inspect_graph(graph_file: Path):
    with open(graph_file) as f:
        data = json.load(f)
    
    nodes = data['nodes']
    edges = data['edges']
    stats = data['stats']
    
    print("=" * 80)
    print("MASTER ORGANIZATION GRAPH")
    print("=" * 80)
    print(f"\nTotal Organizations: {stats['total_organizations']}")
    print(f"Total Units: {stats['total_units']}")
    print(f"Total Edges: {stats['total_edges']}")
    print(f"Sectors: {', '.join(stats['sectors'])}")
    
    print("\n" + "=" * 80)
    print("ORGANIZATIONS BY SECTOR")
    print("=" * 80)
    
    orgs = [n for n in nodes if n['type'] == 'employer']
    sector_counts = Counter(n['sector'] for n in orgs)
    
    for sector, count in sorted(sector_counts.items()):
        print(f"\n{sector.upper()} ({count} organizations):")
        sector_orgs = [n for n in orgs if n['sector'] == sector]
        sector_orgs.sort(key=lambda x: x['people_count'], reverse=True)
        
        for org in sector_orgs[:10]:
            print(f"  - {org['name']}")
            print(f"    People: {org['people_count']} ({', '.join(org['people'][:3])}{'...' if len(org['people']) > 3 else ''})")
            if org.get('country'):
                print(f"    Country: {org['country']}")
    
    print("\n" + "=" * 80)
    print("ORGANIZATIONS WITH MOST SUB-UNITS")
    print("=" * 80)
    
    org_unit_counts = Counter()
    for edge in edges:
        if edge['type'] == 'contains_unit':
            org_unit_counts[edge['source']] += 1
    
    for org_id, count in org_unit_counts.most_common(10):
        org = next(n for n in nodes if n['id'] == org_id)
        print(f"\n{org['name']}: {count} units")
        
        unit_edges = [e for e in edges if e['source'] == org_id and e['type'] == 'contains_unit']
        for edge in unit_edges[:5]:
            unit = next(n for n in nodes if n['id'] == edge['target'])
            print(f"  - {unit['name']} (level {unit.get('hierarchy_level', '?')})")
    
    print("\n" + "=" * 80)
    print("HIERARCHICAL STRUCTURES")
    print("=" * 80)
    
    parent_edges = [e for e in edges if e['type'] == 'parent_unit']
    print(f"Found {len(parent_edges)} parent-child relationships")
    
    for edge in parent_edges[:5]:
        parent = next(n for n in nodes if n['id'] == edge['source'])
        child = next(n for n in nodes if n['id'] == edge['target'])
        print(f"  {parent['name']} -> {child['name']}")

def main():
    graph_file = Path("master_graph.json")
    inspect_graph(graph_file)

if __name__ == "__main__":
    main()
