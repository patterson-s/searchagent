import json
from pathlib import Path

file_paths = [
    r"C:\Users\spatt\Desktop\searchagent\data\birthfinder_verified_v2.jsonl",
    r"C:\Users\spatt\Desktop\searchagent\data\careerfinder_results.jsonl",
    r"C:\Users\spatt\Desktop\searchagent\data\deathfinder_verified.jsonl",
    r"C:\Users\spatt\Desktop\searchagent\data\educationfinder_results.jsonl",
    r"C:\Users\spatt\Desktop\searchagent\data\nationalityfinder_verified.jsonl",
]

for file_path in file_paths:
    print(f"\n{'='*80}")
    print(f"FILE: {Path(file_path).name}")
    print(f"{'='*80}\n")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 2:
                    break
                record = json.loads(line)
                print(f"Record {i+1}:")
                print(json.dumps(record, indent=2))
                print()
    except FileNotFoundError:
        print(f"ERROR: File not found\n")
    except Exception as e:
        print(f"ERROR: {e}\n")
