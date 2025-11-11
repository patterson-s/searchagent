#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/careerfinder/run_stage3.py

import os
import json
import re
from pathlib import Path
from typing import Dict, List
import cohere

def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def fill_template(template: str, variables: dict) -> str:
    text = template
    for k, v in variables.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text

def parse_stage3_output(text: str) -> List[Dict]:
    text = text.strip()
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    
    try:
        data = json.loads(text)
        return data.get("events", [])
    except json.JSONDecodeError:
        return []

def run_stage3_extraction_single_chunk(person_name: str, chunk: Dict, config_path: Path) -> List[Dict]:
    """Extract events from a single chunk."""
    config_path = Path(config_path)
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    api_key = os.getenv(cfg["api_key_env_var"])
    if not api_key:
        raise EnvironmentError(f"Missing environment variable {cfg['api_key_env_var']}")

    co = cohere.Client(api_key)
    system_prompt = load_text(config_path.parent / "system_stage3.txt")
    user_prompt_template = load_text(config_path.parent / "user_stage3.txt")
    
    temporal_context = "unknown"
    org_context = "unknown"
    
    chunks_text = f"CHUNK_ID: {chunk['chunk_id']}\nURL: {chunk.get('source_url', 'unknown')}\nTEXT:\n{chunk.get('text', '')}"
    
    user_prompt = fill_template(user_prompt_template, {
        "PERSON_NAME": person_name,
        "TEMPORAL_CONTEXT": temporal_context,
        "ORGANIZATION_CONTEXT": org_context,
        "CHUNKS_TEXT": chunks_text
    })

    response = co.chat(
        model=cfg["model"],
        temperature=cfg.get("temperature", 0.2),
        preamble=system_prompt,
        message=user_prompt,
        chat_history=[],
        max_tokens=1500,
    )
    
    events = parse_stage3_output(response.text.strip())
    
    for event in events:
        event["source_chunk_ids"] = [chunk["chunk_id"]]
        event["source_url"] = chunk.get("source_url", "unknown")
    
    return events

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Stage 3 event extraction on a single chunk.")
    parser.add_argument("--chunk", required=True, help="Path to chunk JSON file")
    parser.add_argument("--person", required=True)
    parser.add_argument("--config", default="config_01.json")
    args = parser.parse_args()

    with open(args.chunk, "r", encoding="utf-8") as f:
        chunk = json.load(f)
    
    events = run_stage3_extraction_single_chunk(args.person, chunk, Path(args.config))
    print(json.dumps(events, indent=2, ensure_ascii=False))