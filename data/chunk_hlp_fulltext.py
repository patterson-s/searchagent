#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

def find_whitespace_tokens_with_spans(text: str) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text, flags=re.UNICODE)]

def chunk_by_size(spans: List[Tuple[int, int]], size: int) -> List[Tuple[int, int]]:
    chunks = []
    n = len(spans)
    for start in range(0, n, size):
        end = min(start + size, n)
        chunks.append((start, end))
    return chunks

def safe_get(d: Dict[str, Any], key: str, default=None):
    v = d.get(key, default)
    return v if v is not None else default

def maybe_tiktoken_count(text: str) -> int:
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return -1

def process_document(doc: Dict[str, Any],
                     source_index: int,
                     chunk_size: int,
                     use_tiktoken: bool,
                     text_mode: str,
                     preview_len: int) -> List[Dict[str, Any]]:
    name = safe_get(doc, "name", "")
    title = safe_get(doc, "title", "")
    url = safe_get(doc, "url", "")
    full_text = safe_get(doc, "full_text", "")

    if not isinstance(full_text, str) or not full_text.strip():
        return []

    token_spans = find_whitespace_tokens_with_spans(full_text)
    if not token_spans:
        return []

    token_chunks = chunk_by_size(token_spans, chunk_size)

    out_chunks = []
    for ci, (t_start, t_end) in enumerate(token_chunks):
        char_start = token_spans[t_start][0]
        char_end = token_spans[t_end - 1][1]  # exclusive
        chunk_text = full_text[char_start:char_end]

        token_count_gpt = maybe_tiktoken_count(chunk_text) if use_tiktoken else -1

        obj = {
            "person_name": name,
            "source_title": title,
            "source_url": url,
            "source_index": source_index,
            "chunk_index": ci,
            "chunk_id": f"src{source_index}_ch{ci}",
            "start_token": t_start,
            "end_token": t_end,  # exclusive
            "char_start": char_start,
            "char_end": char_end,  # exclusive
            "token_count_regex": t_end - t_start,
            "token_count_gpt": token_count_gpt if token_count_gpt >= 0 else None,
        }

        if text_mode == "full":
            obj["text"] = chunk_text
        elif text_mode == "preview":
            # Keep a short preview to make files scannable
            preview = chunk_text[:preview_len]
            obj["preview"] = preview
            obj["text_len"] = len(chunk_text)
        else:  # none
            obj["text_len"] = len(chunk_text)

        out_chunks.append(obj)

    return out_chunks

def main():
    parser = argparse.ArgumentParser(description="Chunk hlp_fulltext JSON into segments with readable output options.")
    default_input = Path(__file__).parent / "hlp_fulltext_01.json"
    default_output = Path(__file__).parent / "hlp_fulltext_chunks_01.json"

    parser.add_argument("--input", type=Path, default=default_input, help="Path to input JSON (list of docs).")
    parser.add_argument("--output", type=Path, default=default_output, help="Path to output file (.json or .jsonl).")
    parser.add_argument("--chunk-size", type=int, default=400, help="Regex-token count per chunk (no overlap).")
    parser.add_argument("--use-tiktoken", action="store_true", help="Also compute GPT token count (info only).")

    parser.add_argument("--output-format", choices=["json", "jsonl"], default="json",
                        help="Pretty JSON (default) or JSON Lines (one chunk per line).")
    parser.add_argument("--text-mode", choices=["full", "preview", "none"], default="full",
                        help="Include full text, short preview, or omit text (keep lengths).")
    parser.add_argument("--preview-len", type=int, default=280, help="Preview length when --text-mode preview.")

    args = parser.parse_args()

    # Load input docs
    with args.input.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of documents.")

    all_chunks: List[Dict[str, Any]] = []
    total_docs = 0
    for idx, doc in enumerate(data):
        if not isinstance(doc, dict):
            continue
        chunks = process_document(
            doc,
            source_index=idx,
            chunk_size=args.chunk_size,
            use_tiktoken=args.use_tiktoken,
            text_mode=args.text_mode,
            preview_len=args.preview_len,
        )
        all_chunks.extend(chunks)
        total_docs += 1

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output_format == "jsonl":
        with args.output.open("w", encoding="utf-8") as f:
            for row in all_chunks:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    else:
        with args.output.open("w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"Processed documents: {total_docs}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Wrote: {args.output.resolve()} (format={args.output_format}, text_mode={args.text_mode})")

if __name__ == "__main__":
    main()
