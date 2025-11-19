#!/usr/bin/env python
# -*- coding: utf-8 -*-
# services/aggregation/inspect_aggregated.py

import json
import streamlit as st
from pathlib import Path
from typing import List, Dict, Optional

st.set_page_config(page_title="Aggregated Data Inspector", layout="wide")

DEFAULT_DATA_PATH = r"C:\Users\spatt\Desktop\searchagent\data"

def load_latest_aggregated_files(data_dir: str) -> tuple:
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return None, None
    
    data_files = sorted(data_dir.glob("aggregated_data_*.jsonl"), reverse=True)
    sources_files = sorted(data_dir.glob("aggregated_sources_*.jsonl"), reverse=True)
    
    if not data_files or not sources_files:
        return None, None
    
    return data_files[0], sources_files[0]

def load_jsonl(path: Path) -> List[Dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except:
                    continue
    return records

def parse_year(year_str: str) -> Optional[int]:
    if not year_str:
        return None
    try:
        return int(year_str)
    except:
        return None

def get_year_range(event: Dict) -> tuple:
    start = parse_year(event.get("start_date", ""))
    end = parse_year(event.get("end_date", ""))
    has_date = start is not None or end is not None
    return (not has_date, start or 9999, end or 9999)

def format_date_range(event: Dict) -> str:
    start = event.get("start_date", "")
    end = event.get("end_date", "")
    if start and end:
        return f"{start}-{end}"
    elif start:
        return f"{start}-"
    elif end:
        return f"-{end}"
    else:
        return "Unknown"

st.title("Aggregated Data Inspector")

with st.sidebar:
    st.header("Settings")
    data_dir = st.text_input("Data directory", value=DEFAULT_DATA_PATH)

data_file, sources_file = load_latest_aggregated_files(data_dir)

if not data_file or not sources_file:
    st.warning("No aggregated files found. Run the aggregator first.")
    st.stop()

st.sidebar.success(f"Loaded: {data_file.name}")

data_records = load_jsonl(data_file)
sources_records = load_jsonl(sources_file)

sources_map = {r["person_id"]: r for r in sources_records}

if not data_records:
    st.error("No data records found")
    st.stop()

person_names = [r["person_name"] for r in data_records]
selected_person = st.sidebar.selectbox("Select person", person_names)

person_data = next((r for r in data_records if r["person_name"] == selected_person), None)
person_sources = sources_map.get(person_data["person_id"]) if person_data else None

if not person_data:
    st.error("Person data not found")
    st.stop()

st.header(person_data["person_name"])

col1, col2, col3, col4 = st.columns(4)

bio = person_data["biographical"]

with col1:
    birth_year = bio.get("birth_year")
    st.metric("Birth Year", birth_year if birth_year else "Unknown")

with col2:
    death_year = bio.get("death_year")
    st.metric("Death Year", death_year if death_year else bio.get("status", "unknown").title())

with col3:
    nationalities = ", ".join(bio.get("nationalities", []))
    st.metric("Nationality", nationalities if nationalities else "Unknown")

with col4:
    career_events = len(person_data.get("career", []))
    st.metric("Career Events", career_events)

tab1, tab2, tab3, tab4 = st.tabs(["Biographical", "Education", "Career Timeline", "Sources"])

with tab1:
    st.subheader("Biographical Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Birth Year**")
        st.write(bio.get("birth_year") or "Unknown")
        
        st.markdown("**Death Year**")
        st.write(bio.get("death_year") or "N/A")
        
        st.markdown("**Status**")
        st.write(bio.get("status", "unknown").title())
    
    with col2:
        st.markdown("**Nationalities**")
        nats = bio.get("nationalities", [])
        if nats:
            for nat in nats:
                st.write(f"- {nat}")
        else:
            st.write("Unknown")

with tab2:
    st.subheader("Education")
    
    education = person_data.get("education", [])
    
    if not education:
        st.info("No education data available")
    else:
        for i, edu in enumerate(education):
            with st.expander(f"{edu.get('university_name', 'Unknown University')}", expanded=i==0):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**University**")
                    st.write(edu.get("university_name", "Unknown"))
                    
                    st.markdown("**Degree Level**")
                    st.write(edu.get("degree_level", "Unknown"))
                
                with col2:
                    st.markdown("**Field**")
                    st.write(edu.get("degree_field", "Unknown"))
                    
                    st.markdown("**Years**")
                    start = edu.get("year_start", "")
                    finish = edu.get("year_finish", "")
                    if start and finish:
                        st.write(f"{start}-{finish}")
                    elif start:
                        st.write(f"{start}-")
                    elif finish:
                        st.write(f"-{finish}")
                    else:
                        st.write("Unknown")
                
                if edu.get("note"):
                    st.markdown("**Note**")
                    st.write(edu["note"])

with tab3:
    st.subheader("Career Timeline")
    
    career = person_data.get("career", [])
    
    if not career:
        st.info("No career data available")
    else:
        with st.sidebar:
            st.divider()
            st.header("Filters")
            
            all_metatypes = sorted(list(set(e.get("metatype", "unknown") for e in career)))
            selected_metatypes = st.multiselect("Metatype", all_metatypes, default=all_metatypes)
            
            all_types = sorted(list(set(e.get("type", "unknown") for e in career)))
            selected_types = st.multiselect("Type", all_types, default=all_types)
            
            show_undated = st.checkbox("Show undated events", value=True)
        
        filtered_events = [
            e for e in career 
            if e.get("metatype") in selected_metatypes 
            and e.get("type") in selected_types
            and (show_undated or e.get("start_date") or e.get("end_date"))
        ]
        
        sorted_events = sorted(filtered_events, key=get_year_range)
        
        view_mode = st.radio("View", ["Timeline", "Table"], horizontal=True)
        
        if view_mode == "Timeline":
            dated_events = [e for e in sorted_events if e.get("start_date") or e.get("end_date")]
            undated_events = [e for e in sorted_events if not e.get("start_date") and not e.get("end_date")]
            
            if dated_events:
                st.markdown("#### Dated Events")
                for i, event in enumerate(dated_events):
                    col1, col2 = st.columns([1, 4])
                    
                    with col1:
                        st.markdown(f"**{format_date_range(event)}**")
                    
                    with col2:
                        metatype_color = {
                            "govt": "🔵",
                            "private": "🟢",
                            "io": "🟣",
                            "academic": "🟡",
                            "think_tank": "🟠",
                            "ngo": "🔴"
                        }.get(event.get("metatype"), "⚪")
                        
                        st.markdown(f"{metatype_color} **{event.get('role', 'Unknown role')}** at *{event.get('organization', 'Unknown org')}*")
                        
                        if event.get("description"):
                            st.caption(event["description"])
                        
                        tags = event.get("tags", [])
                        if tags:
                            st.caption(" • ".join(tags))
                    
                    if i < len(dated_events) - 1:
                        st.divider()
            
            if undated_events:
                st.markdown("#### Undated Events")
                st.caption(f"{len(undated_events)} events without date information")
                
                for i, event in enumerate(undated_events):
                    metatype_color = {
                        "govt": "🔵",
                        "private": "🟢",
                        "io": "🟣",
                        "academic": "🟡",
                        "think_tank": "🟠",
                        "ngo": "🔴"
                    }.get(event.get("metatype"), "⚪")
                    
                    st.markdown(f"{metatype_color} **{event.get('role', 'Unknown role')}** at *{event.get('organization', 'Unknown org')}*")
                    
                    if event.get("description"):
                        st.caption(event["description"])
                    
                    tags = event.get("tags", [])
                    if tags:
                        st.caption(" • ".join(tags))
                    
                    if i < len(undated_events) - 1:
                        st.divider()
        else:
            table_data = []
            for event in sorted_events:
                table_data.append({
                    "Dates": format_date_range(event),
                    "Organization": event.get("organization", ""),
                    "Role": event.get("role", ""),
                    "Metatype": event.get("metatype", ""),
                    "Type": event.get("type", "")
                })
            
            st.dataframe(table_data, use_container_width=True, height=600)

with tab4:
    st.subheader("Source Information")
    
    if not person_sources:
        st.warning("No source information available")
    else:
        st.markdown("### Biographical Sources")
        
        bio_sources = person_sources.get("biographical_sources", {})
        
        if bio_sources.get("birth_year"):
            with st.expander("Birth Year Sources"):
                birth_src = bio_sources["birth_year"]
                st.write(f"Verified: {birth_src.get('verified')}")
                st.write(f"Outcome: {birth_src.get('corroboration_outcome')}")
                st.json(birth_src.get("winner_sources", []))
        
        if bio_sources.get("death_year"):
            with st.expander("Death Year Sources"):
                death_src = bio_sources["death_year"]
                st.write(f"Status: {death_src.get('status')}")
                st.write(f"Verified: {death_src.get('verified')}")
                st.json(death_src.get("alive_signals", []))
        
        if bio_sources.get("nationalities"):
            with st.expander("Nationality Sources"):
                nat_src = bio_sources["nationalities"]
                st.write(f"Verified: {nat_src.get('verified')}")
                st.json(nat_src.get("nationality_details", {}))
        
        st.markdown("### Education Sources")
        edu_sources = person_sources.get("education_sources", [])
        if edu_sources:
            for src in edu_sources:
                idx = src.get("event_index")
                edu_event = person_data["education"][idx] if idx < len(person_data["education"]) else {}
                with st.expander(f"Event {idx}: {edu_event.get('university_name', 'Unknown')}"):
                    st.json(src.get("sources", []))
        else:
            st.info("No education sources available")
        
        st.markdown("### Career Sources")
        career_sources = person_sources.get("career_sources", [])
        if career_sources:
            for src in career_sources:
                idx = src.get("event_index")
                career_event = person_data["career"][idx] if idx < len(person_data["career"]) else {}
                with st.expander(f"Event {idx}: {career_event.get('organization', 'Unknown')} - {career_event.get('role', 'Unknown')}"):
                    st.markdown("**Source URLs**")
                    for url in src.get("source_urls", []):
                        st.markdown(f"- {url}")
                    st.markdown("**Source Chunks**")
                    st.code(", ".join(src.get("source_chunk_ids", [])))
        else:
            st.info("No career sources available")

with st.sidebar:
    st.divider()
    st.caption("Data Summary")
    st.write(f"Education events: {len(person_data.get('education', []))}")
    st.write(f"Career events: {len(person_data.get('career', []))}")
    
    career = person_data.get("career", [])
    dated_events = [e for e in career if parse_year(e.get("start_date", "")) or parse_year(e.get("end_date", ""))]
    
    if dated_events:
        years = []
        for e in dated_events:
            start = parse_year(e.get("start_date", ""))
            end = parse_year(e.get("end_date", ""))
            if start:
                years.append(start)
            if end:
                years.append(end)
        
        if years:
            min_year = min(years)
            max_year = max(years)
            st.write(f"Career span: {min_year}-{max_year}")
