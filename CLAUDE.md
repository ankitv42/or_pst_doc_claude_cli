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

**Unit tests (no API key or LLM needed):**
```bash
python -m pytest tests/ -v    # scoring formula + routing logic
```

**Evaluations:**
```bash
python evals/run_retrieval_eval.py          # Layer 1 retrieval eval — no API key needed
python evals/run_retrieval_eval.py --ci     # CI gate mode (fails if pass rate < 70%)
python evals/eval_main.py --ci              # Full suite: retrieval + RAGAS + judge + composite (≥0.75)
python evals/run_judge_eval.py              # Layer 2 LLM-as-judge (under development)
```

**Quick smoke tests (each file has a `__main__` block):**
```bash
python agents/graph.py      # runs pipeline on top DB alert
python agents/tools.py      # tests all 6 MCP tools via LangChain @tool
python mcp_server/server.py # verifies MCP server starts and lists tools
```

## Architecture

```
Streamlit Dashboard ──HTTP──► FastAPI Backend ──► LangGraph 4-Agent Pipeline ──► SQLite (orca.db)
  (dashboard/app.py)            (api/main.py)        (agents/graph.py)             (db/)
        ▲                           │
        └──── polls every 3s ◄──────┘         ┌── MCP tools (mcp_server/server.py)
                                               └── RAG retrieval (docs/rag/retriever.py)
```

**API Pattern:** FastAPI returns `202` immediately and runs the pipeline in a thread pool background task. Dashboard polls `/pipeline/{run_id}/state` every 3 seconds for progress updates.

**HITL Pause/Resume:** Uses LangGraph's `interrupt_before=["execute_node"]` + `SqliteSaver` checkpointer (stored at `db/checkpoints.db`). When Agent 4 routes to `ESCALATE`, the graph pauses and waits indefinitely for the human to approve/reject via the dashboard. Resume is triggered by `POST /api/v1/pipeline/{pipeline_id}/approve`.

**Pipeline ID format:** `PIPE_{sku_id}_{YYYY-MM-DD}` — one pipeline per SKU per day. The API rejects duplicate runs with a 409.

## The 4-Agent Pipeline (`agents/`)

| Agent | Role | Key Logic |
|---|---|---|
| Agent 1 — Demand Intelligence | Urgency, lead-time impact, demand trends | Calls CrewAI sub-crew (⚠ currently fails — see Known Issues) |
| Agent 2 — Supply Replenishment | Builds 3 options: standard / partial / expedite | Hard rule: Class A SKUs never get partial distribution |
| Agent 3 — Capital Allocation | Scores options, decides if approval is needed | Exact formula: `budget_score + availability_score + margin_score + lead_time_penalty` |
| Agent 4 / Route Node | Pure Python routing | `ESCALATE` (cost > limit) → `AUTO_EXECUTE` (cost < limit) → `SUSPEND` (pool HIGH) |

Key files: `agents/graph.py` (LangGraph state machine), `agents/prompts.py` (4 system prompts), `agents/crew.py` (CrewAI sub-crew — uses `llama-3.3-70b-versatile`, not the default 8b model), `agents/tools.py` (tool definitions), `agents/llm_factory.py`, `api/models.py` (all Pydantic request/response models).

### `_run_async` bridge

LangGraph nodes are synchronous (`def agent1_node(state)`), but MCP tools are async-only (`ainvoke`). `_run_async(coro)` bridges them: it calls `asyncio.run()` first (Python 3.10+), and falls back to `nest_asyncio` when already inside a running event loop (FastAPI). Each node has one `async def _agentN_fetch()` helper that groups all its MCP calls; the node calls `_run_async(_agentN_fetch(...))` once.

### Tool duplication — `agents/tools.py` vs `mcp_server/server.py`

The same 6 tools are defined in **both** files:
- `agents/tools.py` — LangChain `@tool` wrappers, used only for standalone testing
- `mcp_server/server.py` — `@mcp.tool()` registrations, the actual runtime path

When tool logic changes, **both files must be updated**. The agents use the MCP server tools at runtime via `_get_mcp_tools()`; `agents/tools.py` is never imported by the live pipeline.

## RAG Pipeline (`docs/rag/`)

5 policy documents ingested into ChromaDB (71 chunks total). Retrieval uses hybrid search: BM25 + vector similarity fused with RRF (Reciprocal Rank Fusion), then cross-encoder reranking (BAAI/bge-reranker-v2-m3). Primary embeddings: `nomic-ai/nomic-embed-text-v1.5`; fallback: `all-MiniLM-L6-v2`.

**RAG is unavailable on Windows** due to a path conflict — the API health endpoint will report `"rag": "unavailable (Windows path conflict — resolves on GCP)"`. Agents fall back to LLM knowledge only.

Public API used by agents:
```python
from docs.rag.retriever import query_for_agent1, query_for_agent2, query_for_agent3, query_for_agent4
```

Agents receive a **pre-formatted context string**, not raw chunks.

## MCP Server (`mcp_server/server.py`)

Exposes 6 tools via MCP stdio protocol. The LangGraph graph connects to it via subprocess — tools are discovered dynamically at runtime, not hardcoded. Tool definitions live in `agents/tools.py` (test path) and `mcp_server/server.py` (runtime path).

## Data Layer (`db/`)

SQLite database at `db/orca.db`. All reads/writes go through `db/queries.py` (clean Python functions, no raw SQL scattered elsewhere). Pipeline execution logs in `db/pipeline_log.py`. HITL checkpoint state persisted in `db/checkpoints.db` (SqliteSaver).

## Evaluation Framework (`evals/`)

3 layers:
- **Layer 1** (`run_retrieval_eval.py`): 11 golden test cases in `evals/golden_dataset.py` checking `query_for_agent*()` returns correct keywords and doesn't leak wrong-doc content. Target ≥70% pass rate, zero leaks.
- **Layer 2** (`run_judge_eval.py`): LLM-as-judge for agent decisions — RAG grounding, HITL accuracy, formula correctness, Class-A safety. **Under development.**
- **Layer 3** (`.github/workflows/eval_gate.yaml`): CI gate on every push to main — runs `pytest tests/` first (scoring + routing, no LLM), then `evals/eval_main.py` (full suite via `composite_score.py`, target composite ≥0.75).

## Known Issues

1. **CrewAI + Groq `cache_breakpoint` error** (HIGH): CrewAI injects `cache_breakpoint` into the system message; Groq rejects it. Agent 1's CrewAI sub-crew fails every run and falls back to a raw-data demand summary.
2. **Partial pytest coverage** (HIGH): `agents/tools.py`, API endpoints, and `db/queries.py` have no unit test coverage. `tests/test_scoring.py` and `tests/test_routing.py` cover the scoring formula and routing logic only.
3. **Layer 2 LLM-as-judge not built** (HIGH): `evals/run_judge_eval.py` is a stub.
4. **Layer 1 keyword calibration** (MEDIUM): Golden dataset keywords were written from memory and may not match exact wording in policy docs.
5. **Hardcoded Windows path** (LOW): `sys.path.append(r"C:/lit")` appears in `agents/graph.py`, `api/main.py`, and `evals/run_retrieval_eval.py` as a litellm workaround. This path does not exist on non-Windows machines and should be made conditional.

## Architecture Decision Records (`docs/adr/`)

5 ADRs document key design choices: LangGraph for stateful interruptible workflows (ADR-001), MCP for dynamic tool discovery (ADR-002), native RAGAS metrics implementation (ADR-003), ChromaDB index committed to repo for reproducible CI (ADR-004), and pure-Python HITL routing by cost threshold (ADR-005).

## Deployment

Live on Render.com (free tier). The API image uses `requirements.api.txt` to stay under the 512 MB limit — do not add `torch`, `sentence-transformers`, or `streamlit` to that file.
