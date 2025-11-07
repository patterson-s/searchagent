#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

BIRTH_KEYWORDS = [
    r"\bborn\b",
    r"\bbirth\b",
    r"\bdate of birth\b",
    r"\bb\.\b",
    r"\bnée\b",
    r"\bné\b",
    r"出生", r"生于",
    r"\bgeboren\b",
    r"\bnacido\b|\bnació\b",
    r"\bnaissance\b"
]

MONTHS = (
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

PATTERN_DAY_MONTH_YEAR = re.compile(rf"\b\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}\b", re.IGNORECASE)
PATTERN_ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
PATTERN_MONTH_YEAR = re.compile(rf"\b(?:{MONTHS})\s+\d{{4}}\b", re.IGNORECASE)
PATTERN_YEAR = re.compile(r"\b(1[6-9]\d{2}|20\d{2})\b")
KEYWORD_REGEXES = [re.compile(pat, re.IGNORECASE) for pat in BIRTH_KEYWORDS]
BORN_NEAR_DATE_WINDOW = 80

W_KEYWORD = 2.0
W_DMY = 3.0
W_ISO = 3.0
W_MY = 2.0
W_YEAR = 1.0
W_PROXIMITY = 3.0
W_NAME_PRESENT = 1.5

def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""

def has_any(regexes, text: str) -> bool:
    return any(r.search(text) for r in regexes)

def indexes(regex, text: str):
    return [m.span() for m in regex.finditer(text)]

def name_tokens(name: str):
    toks = [t for t in re.split(r"\s+", name.strip()) if len(t) > 1]
    return toks

def contains_name(text: str, name: str) -> bool:
    toks = name_tokens(name)
    if not toks:
        return True
    for t in toks[::-1]:
        if re.search(rf"\b{re.escape(t)}\b", text, flags=re.IGNORECASE):
            return True
    return False

def score_chunk(text: str, person_name: str) -> float:
    score = 0.0
    kw_hits = sum(1 for r in KEYWORD_REGEXES if r.search(text))
    score += kw_hits * W_KEYWORD

    dmy_spans = indexes(PATTERN_DAY_MONTH_YEAR, text)
    iso_spans = indexes(PATTERN_ISO, text)
    my_spans = indexes(PATTERN_MONTH_YEAR, text)
    year_spans = indexes(PATTERN_YEAR, text)

    score += len(dmy_spans) * W_DMY
    score += len(iso_spans) * W_ISO
    score += len(my_spans) * W_MY
    score += len(year_spans) * W_YEAR

    born_spans = []
    for r in KEYWORD_REGEXES:
        if r.pattern == r"\bborn\b":
            born_spans = indexes(r, text)
            break
    if born_spans:
        for b_start, b_end in born_spans:
            for s, e in dmy_spans + iso_spans + my_spans + year_spans:
                if abs(b_start - s) <= BORN_NEAR_DATE_WINDOW:
                    score += W_PROXIMITY
                    break

    if contains_name(text, person_name):
        score += W_NAME_PRESENT

    return score

def greedy_diverse_topk(candidates, k=3):
    picked = []
    seen_domains = set()
    for c in candidates:
        if len(picked) >= k:
            break
        if c["domain"] not in seen_domains:
            picked.append(c)
            seen_domains.add(c["domain"])
    if len(picked) < k:
        for c in candidates:
            if len(picked) >= k:
                break
            if c in picked:
                continue
            picked.append(c)
    return picked[:k]

def main():
    parser = argparse.ArgumentParser(description="Select top birth-likely chunks (test-only).")
    default_input = Path(__file__).parents[2] / "data" / "hlp_fulltext_chunks_01.json"
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--min_score", type=float, default=0.0)
    parser.add_argument("--preview-len", type=int, default=900, help="How many characters of text to preview.")
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8") as f:
        chunks = json.load(f)
    if not isinstance(chunks, list) or not chunks:
        print("No chunks found.")
        return

    first_person = chunks[0].get("person_name", "").strip()
    if not first_person:
        print("No person_name in first chunk.")
        return

    person_chunks = [c for c in chunks if c.get("person_name", "").strip() == first_person]

    scored = []
    for c in person_chunks:
        text = c.get("text") or c.get("preview") or ""
        if not text:
            continue
        s = score_chunk(text, first_person)
        if s >= args.min_score:
            scored.append({
                "score": round(s, 3),
                "domain": domain_of(c.get("source_url", "")),
                "person_name": c.get("person_name"),
                "source_title": c.get("source_title"),
                "source_url": c.get("source_url"),
                "chunk_id": c.get("chunk_id"),
                "chunk_index": c.get("chunk_index"),
                "char_start": c.get("char_start"),
                "char_end": c.get("char_end"),
                "text": text
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    if not scored:
        print(f"No candidates for {first_person}")
        return

    picked = greedy_diverse_topk(scored, k=args.topk)

    print("=" * 100)
    print(f"Person: {first_person}")
    print(f"Input:  {args.input}")
    print(f"Top {len(picked)} birth-likely chunks (diversity-first, preview={args.preview_len} chars):")
    print("=" * 100)

    for i, c in enumerate(picked, 1):
        preview = c["text"][:args.preview_len].replace("\n", " ")
        print(f"\n[{i}] score={c['score']}  domain={c['domain']}")
        print(f"    source_title : {c['source_title']}")
        print(f"    source_url   : {c['source_url']}")
        print(f"    chunk_id     : {c['chunk_id']} (index {c['chunk_index']})")
        print(f"    char_span    : {c['char_start']}–{c['char_end']}")
        print(f"    preview:\n{preview}")
        print("-" * 100)

if __name__ == "__main__":
    main()
