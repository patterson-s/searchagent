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
from services.cohere_client import CohereClient

# ────── Streamlit UI ──────
st.set_page_config(page_title="Web Search Agent", layout="wide")
st.title("Web Search Agent")

# ────── Tabs ──────
tab1, tab2 = st.tabs(["Prompt Builder", "Prompt Executor"])

with tab1:
    st.header("Prompt Builder")
    
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
            verticals_data = load_verticals(io.StringIO(vert_file.getvalue().decode("utf-8")))
            horizontals    = load_horizontals(io.StringIO(horiz_file.getvalue().decode("utf-8")))
            prompts        = build_prompts(template_str, verticals_data, horizontals)

        st.success(f"Created {len(prompts):,} prompts")

        df_prev = pd.DataFrame([p.model_dump() for p in prompts[:100]])
        st.dataframe(df_prev, use_container_width=True)

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

with tab2:
    st.header("Prompt Executor")
    
    # API Key Input
    api_key = st.text_input("Cohere API Key", type="password")
    
    if api_key:
        try:
            # Initialize client
            client = CohereClient(api_key)
            
            # Test connection
            if client.test_connection():
                st.success("✅ Connected to Cohere!")
                
                # Chat interface
                prompt_text = st.text_area("Enter your prompt:", height=200)
                
                if st.button("Execute Prompt", type="primary", disabled=not prompt_text.strip()):
                    with st.spinner("Getting response..."):
                        try:
                            response = client.chat(prompt_text.strip())
                            st.text_area("Response:", value=response, height=400)
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            else:
                st.error("❌ Connection failed. Check your API key.")
                
        except Exception as e:
            st.error(f"❌ Initialization failed: {str(e)}")
    else:
        st.info("Enter your Cohere API key above")