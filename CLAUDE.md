# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ORCA is an autonomous retail inventory management system. It monitors inventory across stores, detects stock risk, and triggers a **4-agent AI pipeline** (LangGraph + CrewAI + MCP tools + RAG) to recommend reorder decisions with human-in-the-loop (HITL) approval for expensive orders.

Stack: Python 3.11, FastAPI, Streamlit, LangGraph, CrewAI, ChromaDB, SQLite, Groq (free tier LLM), Docker.

## Environment Setup

Copy `.env` with:
```
GROQ_API_KEY=<your-key>
GROQ_MODEL=llama-3.1-8b-instant   # or llama-3.3-70b-versatile
LLM_PROVIDER=groq
```

Install dependencies:
```bash
pip install -r requirements.txt          # full local dev (includes torch, streamlit)
pip install -r requirements.api.txt      # API-only (slim, for Render deployment)
```

## Commands

**RAG setup (required before first run — downloads embedding models ~1-2 min):**
```bash
python docs/rag/ingest.py --reset
```

**Data generation (populates DB with 102 critical/at-risk SKU alerts):**
```bash
python data/scheduler.py --once
```

**Run API:**
```bash
uvicorn api.main:app --reload --port 8080
```

**Run Dashboard:**
```bash
streamlit run dashboard/app.py
```

**Docker (both services together):**
```bash
docker-compose up --build
```

**Evaluations:**
```bash
python evals/run_retrieval_eval.py          # Layer 1 retrieval eval — no API key needed
python evals/run_retrieval_eval.py --ci     # CI gate mode (fails if pass rate < 70%)
python evals/run_judge_eval.py              # Layer 2 LLM-as-judge (under development)
```

There are no pytest unit tests — evals are the primary correctness mechanism.

## Architecture

```
Streamlit Dashboard ──HTTP──► FastAPI Backend ──► LangGraph 4-Agent Pipeline ──► SQLite (orca.db)
  (dashboard/app.py)            (api/main.py)        (agents/graph.py)             (db/)
        ▲                           │
        └──── polls every 3s ◄──────┘         ┌── MCP tools (mcp_server/server.py)
                                               └── RAG retrieval (docs/rag/retriever.py)
```

**API Pattern:** FastAPI returns `202` immediately and runs the pipeline in a thread pool background task. Dashboard polls `/pipeline/{run_id}` every 3 seconds for progress updates.

**HITL Pause/Resume:** Uses LangGraph's `interrupt_before=["execute_node"]` + `MemorySaver` checkpointer. When Agent 4 routes to `ESCALATE`, the graph pauses and waits indefinitely for the human to approve/reject via the dashboard. Resume is triggered by `POST /approve/{run_id}` or `/reject/{run_id}`.

## The 4-Agent Pipeline (`agents/`)

| Agent | Role | Key Logic |
|---|---|---|
| Agent 1 — Demand Intelligence | Urgency, lead-time impact, demand trends | Calls CrewAI sub-crew (⚠ currently fails — see Known Issues) |
| Agent 2 — Supply Replenishment | Builds 3 options: standard / partial / expedite | Hard rule: Class A SKUs never get partial distribution |
| Agent 3 — Capital Allocation | Scores options, decides if approval is needed | Exact formula: `budget_score + availability_score + margin_score + lead_time_penalty` |
| Agent 4 / Route Node | Pure Python routing | `ESCALATE` (cost > limit) → `AUTO_EXECUTE` (cost < limit) → `SUSPEND` (pool HIGH) |

Key files: `agents/graph.py` (LangGraph state machine), `agents/prompts.py` (4 system prompts), `agents/crew.py` (CrewAI sub-crew), `agents/tools.py` (tool definitions), `agents/llm_factory.py`.

## RAG Pipeline (`docs/rag/`)

5 policy documents ingested into ChromaDB (71 chunks total). Retrieval uses hybrid search: BM25 + vector similarity fused with RRF (Reciprocal Rank Fusion), then cross-encoder reranking (BAAI/bge-reranker-v2-m3). Primary embeddings: `nomic-ai/nomic-embed-text-v1.5`; fallback: `all-MiniLM-L6-v2`.

Public API used by agents:
```python
from docs.rag.retriever import query_for_agent1, query_for_agent2, query_for_agent3, query_for_agent4
```

Agents receive a **pre-formatted context string**, not raw chunks.

## MCP Server (`mcp_server/server.py`)

Exposes 6 tools via MCP stdio protocol. The LangGraph graph connects to it via subprocess — tools are discovered dynamically at runtime, not hardcoded. Tool definitions live in `agents/tools.py`.

## Data Layer (`db/`)

SQLite database at `db/orca.db`. All reads/writes go through `db/queries.py` (clean Python functions, no raw SQL scattered elsewhere). Pipeline execution logs in `db/pipeline_log.py`.

## Evaluation Framework (`evals/`)

3 layers:
- **Layer 1** (`run_retrieval_eval.py`): 11 golden test cases checking `query_for_agent*()` returns correct keywords and doesn't leak wrong-doc content. Target ≥70% pass rate, zero leaks.
- **Layer 2** (`run_judge_eval.py`): LLM-as-judge for agent decisions — RAG grounding, HITL accuracy, formula correctness, Class-A safety. **Under development.**
- **Layer 3** (`.github/workflows/eval_gate.yaml`): CI gate runs Layer 1 on every push to main.

## Known Issues

1. **CrewAI + Groq `cache_breakpoint` error** (HIGH): CrewAI injects `cache_breakpoint` into the system message; Groq rejects it. Agent 1's CrewAI sub-crew fails every run and falls back to a raw-data demand summary.
2. **No pytest unit tests** (HIGH): `agents/tools.py`, API endpoints, and `db/queries.py` have no unit test coverage.
3. **Layer 2 LLM-as-judge not built** (HIGH): `evals/run_judge_eval.py` is a stub.
4. **Layer 1 keyword calibration** (MEDIUM): Golden dataset keywords were written from memory and may not match exact wording in policy docs.

## Deployment

Live on Render.com (free tier). The API image uses `requirements.api.txt` to stay under the 512 MB limit — do not add `torch`, `sentence-transformers`, or `streamlit` to that file.
