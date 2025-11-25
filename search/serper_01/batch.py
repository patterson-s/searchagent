import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from serper_client import search
from fetcher import fetch_url_text
from extractor import top_passages, score_passage

SEARCH_TEMPLATE = '{name} biography OR CV OR career OR education OR appointed OR minister OR ambassador OR director'
MAX_RESULTS = 20
OUTPUT_DIR = Path("outputs")

def read_names_from_json(filepath: str) -> List[str]:
    with open(filepath, 'r', encoding='utf-8') as f:
        names = json.load(f)
    if not isinstance(names, list):
        raise ValueError("JSON file must contain a list of names")
    return [str(name).strip() for name in names if str(name).strip()]

def build_search_query(name: str) -> str:
    return SEARCH_TEMPLATE.format(name=name)

def process_person(name: str, max_results: int) -> List[Dict[str, Any]]:
    query = build_search_query(name)
    print(f"  Searching: {query}")
    
    try:
        resp = search(query, num_results=max_results)
    except Exception as e:
        print(f"  Search failed: {e}")
        return []
    
    organic = resp.get("organic", []) or resp.get("results", []) or []
    print(f"  DEBUG: Requested {max_results}, Serper returned {len(organic)} results")
    results = organic[:max_results]
    
    all_results = []
    
    for i, r in enumerate(results):
        url = r.get("link") or r.get("url") or r.get("snippet")
        title = r.get("title") or ""
        snippet = r.get("snippet") or r.get("description") or ""
        
        result_entry = {
            "person": name,
            "search_query": query,
            "rank": i + 1,
            "url": url,
            "title": title,
            "snippet": snippet,
            "fetch_status": "pending",
            "fetch_error": None,
            "full_text": None,
            "passages": []
        }
        
        try:
            print(f"  Fetching [{i+1}/{len(results)}]: {url}")
            fetched_title, text = fetch_url_text(url)
            if fetched_title:
                result_entry["title"] = fetched_title
            
            result_entry["full_text"] = text
            
            passages = top_passages(text, query_name=name, top_k=10)
            result_entry["passages"] = [
                {"text": p, "score": score_passage(p, query_name=name)}
                for p in passages
            ]
            result_entry["fetch_status"] = "success"
            
        except Exception as e:
            print(f"  Fetch failed: {e}")
            result_entry["fetch_status"] = "failed"
            result_entry["fetch_error"] = str(e)
        
        all_results.append(result_entry)
    
    return all_results

def main():
    if len(sys.argv) < 2:
        print("Usage: python batch.py <input_json_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"results_{timestamp}.json"
    temp_file = OUTPUT_DIR / f"results_{timestamp}_temp.json"
    
    print(f"Reading names from: {input_file}")
    names = read_names_from_json(input_file)
    print(f"Found {len(names)} names to process\n")
    
    all_results = []
    
    for idx, name in enumerate(names, 1):
        print(f"[{idx}/{len(names)}] Processing: {name}")
        person_results = process_person(name, MAX_RESULTS)
        all_results.extend(person_results)
        print(f"  Collected {len(person_results)} results")
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"  Saved to temp file: {temp_file}\n")
    
    print(f"Writing final results to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    if temp_file.exists():
        temp_file.unlink()
    
    print(f"\nComplete! Processed {len(names)} people, collected {len(all_results)} total results")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    main()