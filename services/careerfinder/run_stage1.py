#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/careerfinder/run_stage1.py

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

def parse_stage1_output(text: str) -> Dict:
    contains = False
    temporal = []
    orgs = []
    roles = []
    domains = []

    m = re.search(r"contains_career_info:\s*(true|false)", text, flags=re.IGNORECASE)
    if m and m.group(1).lower() == "true":
        contains = True

    m2 = re.search(r"temporal_markers:\s*\[(.*?)\]", text, flags=re.IGNORECASE | re.DOTALL)
    if m2:
        temporal = re.findall(r'"([^"]+)"', m2.group(1))

    m3 = re.search(r"organizations:\s*\[(.*?)\]", text, flags=re.IGNORECASE | re.DOTALL)
    if m3:
        orgs = re.findall(r'"([^"]+)"', m3.group(1))

    m4 = re.search(r"roles:\s*\[(.*?)\]", text, flags=re.IGNORECASE | re.DOTALL)
    if m4:
        roles = re.findall(r'"([^"]+)"', m4.group(1))

    m5 = re.search(r"career_domains:\s*\[(.*?)\]", text, flags=re.IGNORECASE | re.DOTALL)
    if m5:
        domains = re.findall(r'"([^"]+)"', m5.group(1))

    return {
        "contains_career_info": contains,
        "temporal_markers": temporal,
        "organizations": orgs,
        "roles": roles,
        "career_domains": domains
    }

def run_stage1_profiling(person_name: str, chunk_text: str, chunk_id: str, 
                         source_url: str, config_path: Path) -> Dict:
    config_path = Path(config_path)
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    api_key = os.getenv(cfg["api_key_env_var"])
    if not api_key:
        raise EnvironmentError(f"Missing environment variable {cfg['api_key_env_var']}")

    co = cohere.Client(api_key)
    system_prompt = load_text(config_path.parent / "system_stage1.txt")
    user_prompt_template = load_text(config_path.parent / "user_stage1.txt")
    user_prompt = fill_template(user_prompt_template, {
        "PERSON_NAME": person_name,
        "CHUNK_TEXT": chunk_text
    })

    response = co.chat(
        model=cfg["model"],
        temperature=cfg.get("temperature", 0.2),
        preamble=system_prompt,
        message=user_prompt,
        chat_history=[],
        max_tokens=600,
    )
    
    parsed = parse_stage1_output(response.text.strip())
    parsed["chunk_id"] = chunk_id
    parsed["source_url"] = source_url
    parsed["chunk_text"] = chunk_text
    
    return parsed

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Stage 1 profiling on a chunk.")
    parser.add_argument("--person", required=True)
    parser.add_argument("--chunk", required=True)
    parser.add_argument("--chunk_id", default="test_chunk")
    parser.add_argument("--url", default="http://test.com")
    parser.add_argument("--config", default="config_01.json")
    args = parser.parse_args()

    result = run_stage1_profiling(args.person, args.chunk, args.chunk_id, 
                                   args.url, Path(args.config))
    print(json.dumps(result, indent=2))