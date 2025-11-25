# extractor.py
import re
from collections import Counter

# keywords for prosopography extraction (expandable)
KEYWORDS = [
    "born", "b\.", "birth", "educated", "graduat", "PhD", "doctor", "scopus",
    "BA", "B.S.", "MSc", "M.A.", "appointed", "served as", "minister",
    "ambassador", "professor", "head", "chair", "deputy", "senator", "mp",
    "member of", "president", "governor", "mayor", "counselor", "degree",
    "studied", "received", "award", "honor"
]

SENTENCE_RE = re.compile(r'(?<=[\.\?\!])\s+')

def split_into_passages(text, max_chars=800):
    """Split by paragraphs then into passages not longer than max_chars."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    passages = []
    for p in paragraphs:
        if len(p) <= max_chars:
            passages.append(p)
        else:
            # split into approximate sentences
            parts = SENTENCE_RE.split(p)
            cur = ""
            for s in parts:
                if len(cur) + len(s) + 1 <= max_chars:
                    cur = (cur + " " + s).strip()
                else:
                    if cur:
                        passages.append(cur.strip())
                    cur = s
            if cur:
                passages.append(cur.strip())
    return passages

def score_passage(passage, query_name=None):
    """
    Return a score based on keyword hits and presence of name.
    Simple heuristic: keyword counts + bonus for name presence.
    """
    text = passage.lower()
    cnt = 0
    for kw in KEYWORDS:
        if kw.lower() in text:
            cnt += 1
    # add frequency weight
    freq = sum(text.count(kw.lower()) for kw in KEYWORDS)
    score = cnt + 0.2 * freq
    # name bonus
    if query_name and query_name.lower() in text:
        score += 2.0
    return score

def top_passages(text, query_name=None, top_k=5):
    passages = split_into_passages(text)
    scored = [(score_passage(p, query_name), p) for p in passages]
    scored.sort(reverse=True, key=lambda x: x[0])
    return [p for s,p in scored[:top_k] if s > 0]
