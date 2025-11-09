#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path
import cohere

def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def fill_template(template: str, variables: dict) -> str:
    text = template
    for k, v in variables.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text

def run_stage1_extraction(person_name: str, chunk_text: str, cfg_path: Path) -> str:
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    api_key = os.getenv(cfg["api_key_env_var"])
    if not api_key:
        raise EnvironmentError(f"Missing environment variable {cfg['api_key_env_var']}")

    co = cohere.Client(api_key)
    system_prompt = load_text(cfg_path.parent / cfg["system_prompt_path"])
    user_prompt_template = load_text(cfg_path.parent / cfg["user_prompt_path"])
    user_prompt = fill_template(user_prompt_template, {
        "PERSON_NAME": person_name,
        "CHUNK_TEXT": chunk_text
    })

    response = co.chat(
        model=cfg["model"],
        temperature=cfg.get("temperature", 0.3),
        preamble=system_prompt,
        message=user_prompt,
        chat_history=[],
        max_tokens=500,
    )
    return response.text.strip()

def run_stage2_structuring(person_name: str, all_mentions: list, cfg_path: Path) -> str:
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    api_key = os.getenv(cfg["api_key_env_var"])
    if not api_key:
        raise EnvironmentError(f"Missing environment variable {cfg['api_key_env_var']}")

    co = cohere.Client(api_key)
    system_prompt = load_text(cfg_path.parent / "system_stage2.txt")
    user_prompt_template = load_text(cfg_path.parent / "user_stage2.txt")
    
    mentions_formatted = "\n".join(f"- {m}" for m in all_mentions)
    user_prompt = fill_template(user_prompt_template, {
        "PERSON_NAME": person_name,
        "EDUCATION_MENTIONS": mentions_formatted
    })

    response = co.chat(
        model=cfg["model"],
        temperature=cfg.get("temperature", 0.3),
        preamble=system_prompt,
        message=user_prompt,
        chat_history=[],
        max_tokens=1000,
    )
    return response.text.strip()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run educationfinder prompts manually.")
    parser.add_argument("--person", required=True)
    parser.add_argument("--chunk", required=True)
    parser.add_argument("--config", default="config_01.json")
    args = parser.parse_args()

    out = run_stage1_extraction(args.person, args.chunk, Path(args.config))
    print(out)