# Services Architecture Memo

## Executive Summary

The SearchAgent system uses a **service-oriented architecture** where each service is a self-contained module that extracts specific types of information about individuals from text chunks using LLM-based extraction. Services operate independently and their outputs are consolidated by an aggregation layer.

---

## What is a Service?

A **service** is a specialized extraction module that:
- Takes text chunks about a person as input
- Uses semantic search to find relevant chunks
- Prompts an LLM to extract structured information
- Outputs JSONL files with extracted data and provenance
- Can be run independently or as part of a batch pipeline

---

## Core Components of a Service

Every service follows a standard directory structure with these components:

### 1. **Configuration File** (`config_01.json`)

Defines the service's runtime parameters:

```json
{
  "variant_name": "birthfinder_v1",
  "model": "command-a-03-2025",
  "temperature": 0.2,
  "api_key_env_var": "COHERE_API_KEY",
  "system_prompt_path": "system_01.txt",
  "user_prompt_path": "user_01.txt",
  "max_retries": 3,
  "timeout_seconds": 45
}
```

**Purpose:** Single source of truth for model selection, prompts, and runtime behavior.

### 2. **Prompt Files** (`system_*.txt`, `user_*.txt`)

**System Prompt:** Defines the LLM's role and instructions
- Sets expertise level and task objective
- Establishes output format requirements
- Provides extraction guidelines

**User Prompt Template:** Contains task-specific query with variable placeholders
- Uses `{{VARIABLE}}` syntax for dynamic values
- Common variables: `{{PERSON_NAME}}`, `{{CHUNK_TEXT}}`, `{{TEMPORAL_CONTEXT}}`

**Example:**
```
Find the birth year of {{PERSON_NAME}} in the following text:

{{CHUNK_TEXT}}

Output format:
birth_year: YYYY
confidence: high|medium|low
reasoning: <explanation>
```

### 3. **Chunk Selection Module** (`select_chunks_embeddings.py`)

**Purpose:** Semantic search to identify most relevant text chunks before extraction.

**Process:**
1. Load embedded chunks (Cohere Embed v4 vectors)
2. Compute cosine similarity between query and chunk embeddings
3. Apply greedy domain-diverse selection (top-k from different sources)
4. Return ranked chunks for processing

**Key Function:**
```python
def find_X_chunks(person_name: str, embedded_path: str, topk: int = 3) -> List[Dict]
```

### 4. **Execution Script** (`run_*.py`)

**Single-person execution:** Processes one individual through the extraction pipeline.

**Key Function:**
```python
def run_X_prompt_on_chunk(
    person_name: str,
    chunk_text: str,
    cfg_path: str
) -> str
```

**Responsibilities:**
- Load configuration
- Initialize LLM client (Cohere)
- Fill prompt templates
- Call LLM API with retry logic
- Parse and return response

### 5. **Batch Orchestrator** (`run_batch_*.py`, `batch_*.py`)

**Purpose:** Process multiple people through the service pipeline.

**Pattern:**
```python
1. Load chunks JSON/JSONL
2. Extract unique person names
3. For each person:
   - Call chunk selection module
   - Run extraction on selected chunks
   - Save results to outputs/
4. Optionally consolidate results
```

### 6. **Pipeline Script** (`run_pipeline_*.py`)

**For multi-stage services only** (e.g., careerfinder, educationfinder)

**Coordinates sequential stages:**
- Stage 1: Profiling/extraction
- Stage 2: Grouping/consolidation
- Stage 3: Structuring/enrichment
- Stage N: Validation/finalization

### 7. **Outputs Directory** (`outputs/`)

**Stores extraction results in JSONL format:**

```jsonl
{
  "person_name": "John Smith",
  "birth_year": 1965,
  "confidence": "high",
  "source_chunk_ids": ["chunk_123", "chunk_456"],
  "source_urls": ["https://example.com/bio"],
  "reasoning": "Text states 'born in 1965'"
}
```

**Key characteristics:**
- One JSON object per line (newline-delimited)
- Includes extracted data + provenance
- Read by aggregation service

---

## Service Patterns

### **Pattern A: Single-Stage Services**
**Examples:** birthfinder, deathfinder, nationalityfinder

**Flow:**
```
Input: Person name + text chunks
  ↓
Chunk Selection (semantic search)
  ↓
LLM Extraction (single prompt)
  ↓
Output: Structured data + sources
```

**Characteristics:**
- Simple extraction task
- One prompt call per person
- Direct output to JSONL

### **Pattern B: Multi-Stage Services**
**Examples:** educationfinder (2 stages), careerfinder (4 stages)

**Flow:**
```
Stage 1: Profiling/Mention Extraction
  ↓
Stage 2: Consolidation
  ↓
Stage 3: Structuring/Event Extraction
  ↓
Stage 4: Enrichment/Classification
  ↓
Output: Complex structured data
```

**Characteristics:**
- Progressive refinement
- Each stage reads previous stage output
- Includes deduplication logic
- Richer output schema

### **Pattern C: Ontology Services**
**Examples:** org_ontology

**Flow:**
```
Input: Entity lists (e.g., organizations)
  ↓
LLM builds hierarchical relationships
  ↓
Enrich with provenance from source events
  ↓
Output: Graph/tree structure
```

**Characteristics:**
- Operates on aggregated entities
- Builds relationships, not individual facts
- Enrichment phase adds traceability

---

## Data Flow Architecture

```
┌─────────────────────┐
│  Text Chunks        │
│  (JSON/JSONL)       │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  Embedding Layer    │
│  (Cohere Embed v4)  │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────────────────────────┐
│         Services Layer                  │
├─────────────────────────────────────────┤
│  birthfinder     → birth_year           │
│  deathfinder     → death_year, status   │
│  nationalityfinder → nationalities      │
│  educationfinder → education_events[]   │
│  careerfinder    → career_events[]      │
│  org_ontology    → ontology tree        │
└──────────┬──────────────────────────────┘
           │
           ↓
┌─────────────────────┐
│  Aggregation        │
│  Service            │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  Unified Person     │
│  Profiles           │
│  (data + sources)   │
└─────────────────────┘
```

---

## Service Independence Principles

### **Stateless Execution**
- Services do not maintain state between runs
- All context passed via input files
- Idempotent operations (same input → same output)

### **Loose Coupling**
- Services read from standardized chunk files
- No direct service-to-service communication
- Aggregation layer handles cross-service dependencies

### **Provenance Tracking**
- Every extracted fact links back to source chunks
- Maintains `source_chunk_ids` and `source_urls`
- Enables verification and auditability

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **LLM-based extraction** | Handles unstructured text, nuanced interpretation |
| **Semantic chunk selection** | Reduces tokens processed, improves relevance |
| **JSONL output format** | Streamable, append-only, easy to process |
| **Configuration-driven prompts** | Enables A/B testing without code changes |
| **Multi-stage pipelines** | Balances accuracy vs. cost (progressive refinement) |
| **Service independence** | Parallel execution, easier debugging, modular development |

---

## Extension Guidelines

### To Add a New Service:

1. **Create service directory:** `services/newservice/`
2. **Define config:** `config_01.json` with model, prompts, parameters
3. **Write prompts:** `system_01.txt` and `user_01.txt` with clear extraction instructions
4. **Implement chunk selection:** `select_chunks_embeddings.py` with query strategy
5. **Write execution script:** `run_prompt.py` with LLM calling logic
6. **Add batch orchestrator:** `run_batch_verify.py` for multi-person processing
7. **Update aggregation:** Modify `services/aggregation/aggregate.py` to include new service output

### To Modify an Existing Service:

1. **Prompt iteration:** Create `system_02.txt`, `user_02.txt`, `config_02.json`
2. **Test variant:** Run with `--config config_02.json`
3. **Compare outputs:** Use inspection tools to evaluate quality
4. **Deploy:** Update batch scripts to use new config version

---

## Current Services Inventory

| Service | Type | Stages | Output |
|---------|------|--------|--------|
| birthfinder | Single | 1 | birth_year, confidence |
| deathfinder | Single | 1 | death_year, status, alive_signals |
| nationalityfinder | Single | 1 | nationalities[] |
| educationfinder | Multi | 2 | education_events[] |
| careerfinder | Multi | 4 | career_events[] with enrichment |
| org_ontology | Ontology | 2 | hierarchical ontology |
| aggregation | Meta | 1 | unified person profiles |

---

## Technical Stack

- **LLM Provider:** Cohere (Command A 03 2025)
- **Embedding Model:** Cohere Embed v4
- **Language:** Python 3.x
- **Key Libraries:** `cohere`, `numpy`, `json`, `pathlib`, `subprocess`
- **Data Formats:** JSON, JSONL
- **Orchestration:** Subprocess-based batch execution

---

**Document Version:** 1.0
**Last Updated:** 2025-11-25
**Maintained By:** SearchAgent Development Team
