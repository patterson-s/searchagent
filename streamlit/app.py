# streamlit/app.py

import sys
from pathlib import Path
import json
import io

import pandas as pd
import streamlit as st

# ────── Add src/ to sys.path ──────
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

# ────── Imports from your own code ──────
from models import Prompt
from services.prompt_builder import (
    load_verticals,
    load_horizontals,
    build_prompts,
)

# ────── Streamlit UI ──────
st.set_page_config(page_title="Prompt Builder", layout="wide")
st.title("Prompt Builder")

tmpl_file  = st.file_uploader("Upload prompt template (.txt)", type=["txt"])
vert_file  = st.file_uploader("Upload verticals CSV", type=["csv"])
horiz_file = st.file_uploader("Upload horizontals CSV", type=["csv"])

if st.button(
    "Generate prompts",
    type="primary",
    disabled=not (tmpl_file and vert_file and horiz_file),
):
    with st.spinner("Building prompts…"):
        template_str   = tmpl_file.read().decode("utf-8")
        # Save uploaded bytes to temporary buffer and load
        verticals_data = load_verticals(io.StringIO(vert_file.getvalue().decode("utf-8")))
        horizontals    = load_horizontals(io.StringIO(horiz_file.getvalue().decode("utf-8")))
        prompts        = build_prompts(template_str, verticals_data, horizontals)

    st.success(f"Created {len(prompts):,} prompts")

    # Preview the first 100 prompts
    df_prev = pd.DataFrame([p.model_dump() for p in prompts[:100]])
    st.dataframe(df_prev, use_container_width=True)

    # JSON download
    json_bytes = json.dumps([p.model_dump() for p in prompts], indent=2).encode("utf-8")
    st.download_button(
        "Download full set (JSON)",
        json_bytes,
        file_name="prompts.json",
        mime="application/json",
    )

    st.caption(
        "Note: Preview is limited to 100 prompts. JSON download includes the full set."
    )
