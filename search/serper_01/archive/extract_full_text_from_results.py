import json
import sys
import time
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from fetcher import fetch_url_text

OUTPUT_DIR = Path("output")

def load_results(filepath: str) -> List[Dict[str, Any]]:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_full_text_from_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    extracted_data = []
    total_urls = len(results)
    
    print(f"Processing {total_urls} URL entries...")
    
    for idx, result in enumerate(results, 1):
        person = result.get("person", "Unknown")
        search_query = result.get("search_query", "")
        url = result.get("url", "")
        title = result.get("title", "")
        fetch_status = result.get("fetch_status", "")
        
        entry = {
            "name": person,
            "search_query": search_query,
            "title": title,
            "url": url,
            "full_text": None,
            "extraction_status": "pending",
            "extraction_error": None
        }
        
        if fetch_status == "success" and url:
            try:
                print(f"[{idx}/{total_urls}] Fetching: {url}")
                fetched_title, full_text = fetch_url_text(url)
                
                if fetched_title:
                    entry["title"] = fetched_title
                
                entry["full_text"] = full_text
                entry["extraction_status"] = "success"
                
                print(f"  ✓ Success: {len(full_text)} characters extracted")
                
            except Exception as e:
                print(f"  ✗ Failed: {e}")
                entry["extraction_status"] = "failed"
                entry["extraction_error"] = str(e)
        
        elif fetch_status == "failed":
            print(f"[{idx}/{total_urls}] Skipping (originally failed): {url}")
            entry["extraction_status"] = "skipped_original_failure"
            entry["extraction_error"] = result.get("fetch_error", "Unknown error")
        
        else:
            print(f"[{idx}/{total_urls}] Skipping (no URL or unknown status): {url}")
            entry["extraction_status"] = "skipped_no_url"
        
        extracted_data.append(entry)
        
        if entry["extraction_status"] == "success":
            delay = random.uniform(0.1, 0.3)
            time.sleep(delay)
    
    return extracted_data

def save_results(data: List[Dict[str, Any]], output_path: Path):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")

def print_summary(data: List[Dict[str, Any]]):
    total = len(data)
    success = sum(1 for d in data if d["extraction_status"] == "success")
    failed = sum(1 for d in data if d["extraction_status"] == "failed")
    skipped = total - success - failed
    
    print(f"\n{'='*50}")
    print(f"EXTRACTION SUMMARY")
    print(f"{'='*50}")
    print(f"Total URLs processed: {total}")
    print(f"Successfully extracted: {success}")
    print(f"Failed extractions: {failed}")
    print(f"Skipped: {skipped}")
    print(f"{'='*50}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_full_text_from_results.py <input_json_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not Path(input_file).exists():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"full_text_extraction_{timestamp}.json"
    
    print(f"Loading results from: {input_file}")
    results = load_results(input_file)
    
    extracted_data = extract_full_text_from_results(results)
    
    save_results(extracted_data, output_file)
    
    print_summary(extracted_data)

if __name__ == "__main__":
    main()