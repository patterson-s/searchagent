# src/services/prompt_builder.py
from __future__ import annotations
import pandas as pd
from typing import List, Dict, Tuple
from pathlib import Path

from models import Prompt, VerticalData, HorizontalData

# ───────────────────────────────────────────
# CSV → in-memory helpers
# ───────────────────────────────────────────

def load_verticals(csv_path: Path) -> VerticalData:
    """Return [(vertical_string, index_slug)]"""
    df = pd.read_csv(csv_path)
    rows: VerticalData = []

    for _, row in df.iterrows():
        vertical_value = " ".join(str(v) for v in row.values if pd.notnull(v))

        org_type = str(row.get("organization_type", "")).strip()
        org_name = str(row.get("organization_name", "")).strip()
        process  = str(row.get("organization_process", "")).strip()

        index_slug = f"{org_type}_{process or org_name}".replace(" ", "_")
        rows.append((vertical_value, index_slug))

    return rows


def load_horizontals(csv_path: Path) -> HorizontalData:
    df = pd.read_csv(csv_path)
    grouped: HorizontalData = {}
    for _, row in df.iterrows():
        grouped.setdefault(row["category"], []).append(row["term"])
    return grouped


# ───────────────────────────────────────────
# Core prompt-building routine
# ───────────────────────────────────────────

def build_prompts(
    template_txt: str,
    verticals: VerticalData,
    horizontals: HorizontalData,
) -> List[Prompt]:
    prompts: List[Prompt] = []

    for v_value, v_index in verticals:
        for category, terms in horizontals.items():
            bullet_block = "\n".join(f"- {category}, {t}" for t in terms)

            prompt_text = (
                template_txt
                .replace("{vertical}", v_value)
                .replace("{horizontal_category}", category)
                .replace("{horizontal_terms}", bullet_block)
            )

            cat_slug = category.replace(" ", "_").replace("&", "and")
            index    = f"{v_index}_{cat_slug}"

            prompts.append(
                Prompt(
                    vertical=v_value,
                    horizontal_category=category,
                    index=index,
                    prompt=prompt_text,
                )
            )
    return prompts
