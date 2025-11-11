#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/careerfinder/run_stage4.py

import os
import json
import re
from pathlib import Path
from typing import Dict
import cohere

def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def fill_template(template: str, variables: dict) -> str:
    text = template
    for k, v in variables.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text

def parse_stage4_output(text: str) -> Dict:
    text = text.strip()
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"metatype": "unknown", "type": "unknown", "tags": []}

def run_stage4_enrichment(event: Dict, source_text: str, config_path: Path) -> Dict:
    config_path = Path(config_path)
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    api_key = os.getenv(cfg["api_key_env_var"])
    if not api_key:
        raise EnvironmentError(f"Missing environment variable {cfg['api_key_env_var']}")

    co = cohere.Client(api_key)
    system_prompt = load_text(config_path.parent / "system_stage4.txt")
    user_prompt_template = load_text(config_path.parent / "user_stage4.txt")
    
    user_prompt = fill_template(user_prompt_template, {
        "ORGANIZATION": event.get("organization", ""),
        "ROLE": event.get("role", ""),
        "START_DATE": event.get("start_date", ""),
        "END_DATE": event.get("end_date", ""),
        "DESCRIPTION": event.get("description", ""),
        "SOURCE_TEXT": source_text[:2000]
    })

    response = co.chat(
        model=cfg["model"],
        temperature=cfg.get("temperature", 0.2),
        preamble=system_prompt,
        message=user_prompt,
        chat_history=[],
        max_tokens=400,
    )
    
    metadata = parse_stage4_output(response.text.strip())
    
    enriched = event.copy()
    enriched["metatype"] = metadata.get("metatype", "unknown")
    enriched["type"] = metadata.get("type", "unknown")
    enriched["tags"] = metadata.get("tags", [])
    
    return enriched

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Stage 4 metadata enrichment on an event.")
    parser.add_argument("--event", required=True, help="Path to event JSON file")
    parser.add_argument("--source", required=True, help="Source text")
    parser.add_argument("--config", default="config_01.json")
    args = parser.parse_args()

    with open(args.event, "r", encoding="utf-8") as f:
        event = json.load(f)
    
    enriched = run_stage4_enrichment(event, args.source, Path(args.config))
    print(json.dumps(enriched, indent=2, ensure_ascii=False))