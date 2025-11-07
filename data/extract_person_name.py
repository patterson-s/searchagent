import json
from pathlib import Path

def extract_person_names(input_path: str, output_path: str) -> None:
    """Extracts all person names from nested career_trajectories JSON."""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    names = []

    # Handle nested list structure
    for group in data:
        for record in group:
            try:
                name = record["person"]["name"]
                if name and name not in names:
                    names.append(name)
            except KeyError:
                continue

    # Write one name per line in a JSON array
    with open(output_path, 'w', encoding='utf-8') as out:
        json.dump(names, out, ensure_ascii=False, indent=2)

    print(f"Extracted {len(names)} names to {output_path}")

if __name__ == "__main__":
    base_dir = Path(__file__).parent
    input_file = Path(r"C:\Users\spatt\Desktop\consultocracy_dashboard\data\career_trajectories_03_dates_normalized_with_hlp.json")
    output_file = base_dir / "person_names.json"

    extract_person_names(str(input_file), str(output_file))
