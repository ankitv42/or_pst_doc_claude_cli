# ORCA — Knowledge Transfer Document

**Project:** ORCA (Open Retail Command Agent)
**Prepared for:** Incoming engineer (eval workstream)
**Prepared by:** Ankit (Data Science Manager) — handover before USA travel
**Status of project:** Sprints 1–5 complete and deployed live. Sprint 6 (evaluation) in progress.
**Your focus:** The **evaluation** workstream (Layer 1 retrieval eval is started; Layers 2 & 3 are yours to build).

> Read this document top to bottom **once** before touching the repo. Then keep it open beside your editor. It is long on purpose — by the end you should understand not just *what* ORCA is, but *why* every piece exists. Sections 12–14 are your actual task and the open issues; everything before that is context.

-----

## 0. How to read this document

|Section|What it covers                                 |Priority for you                  |
|-------|-----------------------------------------------|----------------------------------|
|1–2    |What ORCA is and why it exists                 |Read first                        |
|3      |The big-picture architecture                   |Read first                        |
|4      |The 4 agents and their business logic          |Important                         |
|5      |The data model (SQLite + RAG docs)             |Important                         |
|6      |The RAG pipeline (this is what you’ll evaluate)|**Critical**                      |
|7      |File-by-file walkthrough of the repo           |Reference                         |
|8      |Tech stack and glossary                        |Reference (fresher-friendly)      |
|9      |Environment setup — get it running locally     |**Do this Day 1**                 |
|10     |Deployment (Render)                            |Read                              |
|11     |The known landmines (C:/lit, CrewAI, etc.)     |**Read before debugging anything**|
|12     |Your task — the evaluation workstream          |**This is your job**              |
|13     |Issue tracker — everything still pending       |**Critical**                      |
|14     |Glossary                                       |Reference whenever stuck          |

-----

## 1. What is ORCA?

ORCA stands for **Open Retail Command Agent**. It is an **autonomous retail inventory management system** built with open-source AI tooling.

In plain terms: it watches inventory across many retail stores, and when a product is about to run out, an AI pipeline automatically figures out *how much to reorder, from which supplier, at what cost, and whether a human needs to approve it before the order is placed*.

It is a **multi-agent system** — four AI “agents” each handle one stage of the decision, passing their work down a chain like an assembly line.

The system is **HITL (Human-In-The-Loop)**: for expensive or risky orders, the pipeline **pauses** and waits for a human to click *Approve* or *Reject* before any money is committed. Cheap, routine orders execute automatically.

-----

## 2. Why does ORCA exist? (The backstory — important context)

Ankit spent ~10 years in data engineering: Informatica → Palantir Foundry → Palantir AIP Studio. On Palantir he built a real production system called **RCC (Retail Command Centre)** for a **UAE retail client, deployed across 200+ stores**. RCC did exactly what ORCA does — but it was built on **Palantir**, which is a *closed, proprietary platform*.

The problem: skills learned only on a closed platform don’t transfer well to open-source job interviews (Fortune 100 / FAANG AI Engineer roles). So ORCA is a deliberate **open-source rebuild of RCC** — same business problem, but using the open-source agentic AI stack that the industry actually interviews on (LangGraph, RAG, MCP, CrewAI, FastAPI, Docker, etc.).

**Why this matters to you:** Many design choices in ORCA are “how would the industry do what Palantir did for us automatically?” If something looks over-engineered, it’s usually because Palantir gave it for free and we had to rebuild it by hand. That rebuild *is* the learning.

**Key reference points you’ll see repeatedly:**

- **RCC** = the original Palantir system (the “source of truth” for business logic).
- **AIP Studio** = Palantir’s agent-building tool (where RCC’s agents lived).
- **Ontology** = Palantir’s data-object layer (ORCA replaces it with a SQLite database + Python query functions).

-----

## 3. Big-picture architecture

The full flow, end to end:

```
                       ┌─────────────────────────────────────────────┐
                       │  scheduler.py  (simulates real-time alerts)   │
                       │  marks SKUs as CRITICAL / AT_RISK in the DB   │
                       └───────────────────────┬─────────────────────┘
                                               │
                                               ▼
   Streamlit dashboard  ──HTTP──►  FastAPI (api/main.py)  ──►  LangGraph pipeline (agents/graph.py)
   (dashboard/app.py)                                              │
        ▲                                                          ▼
        │                                          ┌──────────────────────────────┐
        │   poll every 3s                          │  Agent 1 → Agent 2 → Agent 3  │
        └──────────────────────────────────────────│       → route → Agent 4       │
                                                    └───────────────┬──────────────┘
                                                                    │
                          each agent pulls two kinds of context:    │
                          1. structured data (MCP tools → SQLite)   │
                          2. policy knowledge (RAG → ChromaDB)       │
                                                                    ▼
                                          ┌──────────────────────────────────────┐
                                          │ route decision:                       │
                                          │   AUTO_EXECUTE → write order to DB     │
                                          │   ESCALATE     → PAUSE for human (HITL)│
                                          │   SUSPEND      → no order, log only    │
                                          └──────────────────────────────────────┘
```

**The two context sources are the heart of the system:**

1. **MCP tools** fetch *structured facts* from the SQLite database (current stock, supplier lead times, capital budgets).
1. **RAG** fetches *policy knowledge* from text documents (ordering rules, event playbooks, scoring formulas).

You will be **evaluating the RAG half** — measuring whether the right policy knowledge reaches each agent.

-----

## 4. The four agents (the business logic)

The pipeline is a fixed chain: **Agent 1 → Agent 2 → Agent 3 → routing → Agent 4**. Each agent is one “node” in LangGraph. Each calls the LLM once (Groq `llama-3.1-8b-instant`) with (a) structured data and (b) RAG policy context, and returns a JSON result that flows to the next agent via shared state (`AgentState`).

### Agent 1 — Demand Intelligence

**Question it answers:** *How urgent is this, and will a normal order arrive in time?*

- Classifies **urgency**: `CRITICAL` / `HIGH` / `MEDIUM` (driven mainly by how many stores are critical).
- Computes `lead_time_too_late` — `True` if the supplier’s lead time is longer than the time until an upcoming demand event.
- Estimates projected demand (uses event uplift factors, e.g. Ramadan multiplies demand).
- Also launches a **CrewAI forecasting crew** for a deeper demand read (⚠️ currently failing — see Issue #1).

### Agent 2 — Supply Replenishment

**Question it answers:** *What are our reorder options?*

- Builds exactly **three options**:
  - **Option A** — standard reorder (normal lead time).
  - **Option B** — profit-maximising / partial distribution (only top stores).
  - **Option C** — expedite (air freight, faster but expensive).
- **Hard rules** (these are common test targets):
  - **Class A SKUs NEVER get Option B** — they always require full store distribution.
  - **Suppliers with `allows_expedite = No` cannot do Option C** (e.g. Hindustan FMCG). If expedite is needed but not allowed → escalate to a human.

### Agent 3 — Capital Allocation

**Question it answers:** *Which option wins financially, and do we need approval?*

- Scores each option with an **exact formula** (memorise this — it’s a frequent eval target):

```
budget_score       = (1 - cost / available_budget) × 40
availability_score = availability_pct × 0.40 × 100
margin_score       = (1 / margin_priority_rank) × 20
lead_time_penalty  = -20   IF urgency = CRITICAL AND lead_time_days > 30   (else 0)

total_score = budget_score + availability_score + margin_score + lead_time_penalty
The option with the highest total_score wins.
```

- Determines approval:

```
approval_required = (cost > pool.auto_approve_limit_aed)
```

- A common mistake the agent must avoid (it’s in the RAG docs as a “known error”): applying the `lead_time_penalty` when urgency is `HIGH`. It applies **only** when urgency is `CRITICAL`.

### Agent 4 — Exception / HITL Briefing

**Question it answers:** *What happens next, and what does the human need to know?*

- First, a **pure-Python routing decision** (no LLM) picks the route:

```
IF   pool_pressure_flag == HIGH         → SUSPEND      (budget too tight, no order)
ELIF approval_required == False         → AUTO_EXECUTE (cheap enough, just do it)
ELSE                                    → ESCALATE     (needs a human to approve)
```

- For **ESCALATE**, Agent 4 writes a **briefing** (the text a human planner reads before approving) — including supplier contact, cost, which capital pool, and why approval is needed.
- For **AUTO_EXECUTE**, it writes the order to the DB and logs a confirmation.

**HITL mechanism:** the LangGraph is compiled with `interrupt_before=["execute_node"]`. This means the graph **physically pauses** before writing any order. A human approves via the dashboard → the API calls `resume_pipeline()` → the graph continues from its saved checkpoint. State is kept by a `MemorySaver` checkpointer keyed by `thread_id = pipeline_id`.

### The anchor scenario (memorise this — it’s the canonical demo)

- **ESCALATED example:** *Ajwa Dates* during the *Ramadan* surge. Air-freight (expedite) cost **AED 108,909** exceeds the CP003 pool’s auto-approve limit of **AED 20,000** → pipeline **ESCALATES** and waits for human approval.
- **AUTO_EXECUTED example:** *Dish Soap (SKU00097)* at **AED 817**, under the CP001 limit → executes automatically, no human needed.

-----

## 5. The data model

### 5.1 The SQLite database (`db/orca.db`)

Built in three layers (a Palantir habit carried over deliberately):

```
raw tables      →  staged tables    →  curated tables
(synthetic gen)    (cleaned)            (business-ready: alerts, positions, etc.)
```

Conceptually the curated layer holds these object-like tables (this is what the MCP tools query):

- **Inventory positions** — stock level per SKU per store, with a `stock_status` (CRITICAL / AT_RISK / OK) and `reorder_triggered` flag.
- **SKUs** — product master: `sku_id`, `category`, `abc_class` (A/B/C), margin info.
- **Suppliers** — lead times, reliability, `allows_expedite`, `expedite_premium_pct`, contacts.
- **Capital pools** — budgets (e.g. CP001, CP003), `auto_approve_limit_aed`, `pool_pressure_flag`.
- **Events** — the retail event calendar with demand uplift %.
- **alerts** — the working list of SKUs needing attention (the dashboard’s main feed).
- **pipeline_log** — audit trail of every completed pipeline run.

The data is **synthetic** (generated by the data scripts) but modelled on the real UAE retail dataset from RCC.

**Real reference data you’ll see in tests** (from the source Excel files):

|Supplier          |Category     |Lead time|Expedite?|Premium|
|------------------|-------------|---------|---------|-------|
|Al Rawdah Foods   |Grocery      |30 d     |Yes      |35%    |
|Emirates Dairy Co |Dairy        |5 d      |Yes      |20%    |
|Gulf Beverages LLC|Beverages    |7 d      |Yes      |25%    |
|Hindustan FMCG    |Personal Care|45 d     |**No**   |0%     |
|Dragon Imports    |Seasonal     |60 d     |Yes      |50%    |

|Event           |Uplift|Planning lead|Categories                      |
|----------------|------|-------------|--------------------------------|
|Ramadan 2025    |180%  |60 d         |Grocery, Dates, Beverages       |
|Eid Al Fitr 2025|220%  |45 d         |Seasonal, Personal Care, Grocery|
|Eid Al Adha 2025|150%  |45 d         |Grocery, Meat, Seasonal         |
|UAE National Day|80%   |30 d         |Seasonal, Beverages             |
|Back to School  |120%  |45 d         |Stationery, Bags, Electronics   |

### 5.2 The RAG documents (`docs/`)

Five hand-written `.txt` knowledge documents, ingested into ChromaDB as **71 chunks**. These hold the *policy knowledge* the database can’t express:

1. **`replenishment_policy.txt`** — ABC-class ordering rules, stock-status rules, capital-pool rules, lead-time rules, approval routing.
1. **`supplier_sla.txt`** — all 10 suppliers: lead times, reliability, expedite premiums, contacts.
1. **`event_playbook.txt`** — all 10 UAE retail events: uplift %, planning lead days, ordering rules.
1. **`entity_relationships.txt`** — GraphRAG-style: SKU→Supplier→Pool chains, risk chains, scoring-formula context.
1. **`agent_reasoning_patterns.txt`** — Corrective-RAG style: 4 golden worked examples, 6 common errors, self-correction triggers.

> **Rule baked into the system:** *the database always wins over RAG on any factual conflict.* If the DB says a supplier’s email is X and a document says Y, the DB is authoritative. The RAG context string literally starts with a “PRIORITY RULE: database wins” line.

-----

## 6. The RAG pipeline (what you will evaluate — read carefully)

This is the most important section for your work.

### 6.1 What RAG is doing here

When an agent needs policy knowledge, it does **not** dump all 5 documents into the prompt. Instead it asks the **retriever** for the most relevant chunks, formatted into a compact context string. That string is injected into the agent’s prompt.

### 6.2 The retrieval stack (in `docs/rag/retriever.py`)

- **Vector store:** ChromaDB, persisted at `db/chroma/`.
- **Embedding model:** `nomic-ai/nomic-embed-text-v1.5` (primary), falls back to `all-MiniLM-L6-v2`.
- **Reranker:** `BAAI/bge-reranker-v2-m3` (a cross-encoder that re-scores retrieved chunks for relevance).
- **Hybrid retrieval:** combines **BM25** (keyword search) + **vector** (semantic search), fused with **RRF** (Reciprocal Rank Fusion). This is why exact terms like “CP003” and semantic concepts both work.
- **Corrective RAG:** if the top chunk’s score is below a threshold (0.35), it automatically retries with an expanded query.
- **Metadata filtering:** each chunk has a `doc_type` (policy / supplier / event / graph / reasoning), so agents only search relevant document types.

### 6.3 The public API — the methods you will call in eval

Each agent calls one method. **Each returns a formatted context STRING** (not a list of chunks — remember this):

```python
retriever.query_for_agent1(category, abc_class, urgency, lead_time_too_late, event_name, demand_trend, supplier_name)
retriever.query_for_agent2(category, supplier_name, lead_time_too_late, abc_class, urgency)
retriever.query_for_agent3(category, urgency, abc_class, approval_pool)
retriever.query_for_agent4(category, supplier_name, route)
```

Because these return the exact string the agent sees, your retrieval eval checks: *did the right facts land in that string?* (recall) and *did wrong-document facts leak in?* (precision).

-----

## 7. File-by-file repo walkthrough

```
orca-retail/
├── data/
│   ├── (synthetic data generation scripts)     # builds the raw→staged→curated tables
│   └── scheduler.py                            # simulates real-time alerts; run with --once
├── db/
│   ├── orca.db                                 # SQLite database (auto-created on first run)
│   ├── chroma/                                 # ChromaDB vector store (created by ingest.py)
│   ├── queries.py                              # all DB read/write functions (the "ontology" replacement)
│   └── pipeline_log.py                         # saves completed pipeline runs to audit table
├── agents/
│   ├── graph.py                                # ⭐ THE CORE — LangGraph 4-agent pipeline + HITL
│   ├── crew.py                                 # CrewAI forecasting crew (⚠️ currently failing)
│   ├── llm_factory.py                          # get_llm() — returns Groq/OpenAI/Ollama based on .env
│   ├── prompts.py                              # the 4 system prompts as ChatPromptTemplate objects
│   └── tools.py                                # @tool functions (the 6 MCP tools' logic)
├── mcp_server/
│   └── server.py                               # MCP server exposing the 6 tools for dynamic discovery
├── docs/
│   ├── replenishment_policy.txt                # RAG doc 1
│   ├── supplier_sla.txt                        # RAG doc 2
│   ├── event_playbook.txt                      # RAG doc 3
│   ├── entity_relationships.txt                # RAG doc 4 (GraphRAG)
│   ├── agent_reasoning_patterns.txt            # RAG doc 5 (Corrective RAG)
│   └── rag/
│       ├── ingest.py                           # chunks + embeds docs into ChromaDB
│       └── retriever.py                        # ⭐ hybrid retrieval + rerank + the query_for_agentN API
├── api/
│   ├── main.py                                 # ⭐ FastAPI app — all endpoints
│   └── models.py                               # Pydantic request/response schemas
├── dashboard/
│   ├── app.py                                  # ⭐ Streamlit dashboard (3 tabs)
│   └── api_client.py                           # thin HTTP wrapper around the API (UI never calls HTTP directly)
├── evals/                                      # ⭐ YOUR WORKSPACE
│   ├── golden_dataset.py                       # 11 retrieval test cases (already written)
│   └── run_retrieval_eval.py                   # retrieval eval runner (already written)
├── Dockerfile.api
├── Dockerfile.dashboard
├── docker-compose.yml
├── requirements.txt                            # full deps (local)
├── requirements.api.txt                        # slim deps (Render API — no torch/chromadb)
└── .env                                        # secrets (GROQ_API_KEY etc.) — NEVER commit
```

### Key files explained simply

- **`agents/graph.py`** — the orchestrator. Defines `AgentState` (the shared notebook that flows through all agents), the 4 agent nodes, the routing logic, and the HITL interrupt. If you read one file, read this.
- **`agents/llm_factory.py`** — one function `get_llm()` that returns the right LLM object based on `LLM_PROVIDER` in `.env` (groq / openai / ollama). **You will reuse this in your judge eval.**
- **`agents/prompts.py`** — the 4 system prompts. Each is a `ChatPromptTemplate` with `{placeholders}` that `graph.py` fills with real data.
- **`docs/rag/retriever.py`** — the RAG brain. The `query_for_agentN` methods are your eval targets.
- **`api/main.py`** — exposes `/health`, `/api/v1/alerts`, `/api/v1/pipeline/run`, `/api/v1/pipeline/{id}/state`, `/api/v1/pipeline/{id}/approve`, etc.
- **`dashboard/app.py`** — 3 tabs: **Command Centre** (alert list + Analyse buttons), **Pipeline Monitor** (live pipeline progress), **HITL Approval** (Approve/Reject for escalated pipelines).

-----

## 8. Tech stack (with fresher-friendly one-liners)

|Tech                       |What it is                                                                          |Role in ORCA                                   |
|---------------------------|------------------------------------------------------------------------------------|-----------------------------------------------|
|**LangGraph**              |Framework for building stateful, multi-step AI agent workflows as a graph           |Runs the 4-agent pipeline + HITL pause/resume  |
|**LangChain**              |Toolkit for working with LLMs (prompts, chains)                                     |Prompt templates, LLM calls                    |
|**CrewAI**                 |Framework for multi-agent “crews” that collaborate                                  |Demand forecasting sub-crew inside Agent 1     |
|**RAG**                    |Retrieval-Augmented Generation — fetch relevant docs, feed to LLM                   |Supplies policy knowledge to agents            |
|**ChromaDB**               |A vector database                                                                   |Stores the 71 embedded document chunks         |
|**Embeddings**             |Turning text into number vectors for similarity search                              |nomic / all-MiniLM models                      |
|**BGE reranker**           |A model that re-scores search results for relevance                                 |Improves retrieval quality                     |
|**MCP**                    |Model Context Protocol — Anthropic’s standard for tools to be discovered dynamically|Exposes the 6 data tools                       |
|**FastAPI**                |Python web framework for building APIs                                              |The backend the dashboard talks to             |
|**Pydantic**               |Data validation library                                                             |Validates every API request/response           |
|**Streamlit**              |Python framework for quick web dashboards                                           |The UI                                         |
|**Docker / docker-compose**|Packages the app into portable containers                                           |Runs API + dashboard together                  |
|**Render**                 |Free cloud hosting platform                                                         |Where ORCA is deployed live                    |
|**Groq**                   |Fast LLM inference provider                                                         |Serves `llama-3.1-8b-instant` (the agent brain)|
|**SQLite**                 |A lightweight file-based database                                                   |`orca.db`                                      |
|**litellm**                |A library that gives one interface to many LLM providers                            |Used under the hood by CrewAI                  |

(Section 14 has a fuller glossary of eval-specific terms.)

-----

## 9. Environment setup — get ORCA running locally (DO THIS DAY 1)

> Goal: get the dashboard open in your browser with **API ONLINE** and **RAG: available**, and successfully run one pipeline.

### Step 0 — Prerequisites

- Python 3.11 (check: `python --version`)
- Git
- A free **Groq API key** (sign up at groq.com → API Keys). No money needed.

### Step 1 — Clone the repo

```bash
git clone https://github.com/ankitv42/orca-retail.git
cd orca-retail
```

### Step 2 — Create a virtual environment and install dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

> If `sentence-transformers` isn’t pulled in, install it explicitly: `pip install sentence-transformers`. The RAG retriever needs it.

### Step 3 — Create your `.env` file

In the repo root, create a file named `.env`:

```
LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-key-here
GROQ_MODEL=llama-3.1-8b-instant
```

> **Never commit `.env`.** It’s in `.gitignore` for a reason.

### Step 4 — Build the RAG knowledge base (REQUIRED — RAG won’t work without it)

```bash
python docs/rag/ingest.py --reset
```

This downloads the embedding model (first time only, ~1–2 min) and loads all 71 chunks into `db/chroma/`. Wait for “Ingestion complete”.

> **If you skip this, the dashboard will show `RAG: unavailable`** — that’s the #1 setup gotcha.

### Step 5 — Run the API (terminal 1)

```bash
uvicorn api.main:app --reload --port 8080
```

Check it: open `http://localhost:8080/health` — you want to see `"rag": "available"`.

### Step 6 — Run the dashboard (terminal 2)

```bash
streamlit run dashboard/app.py
```

The dashboard opens in your browser. Click a SKU’s **Analyse** button → watch the pipeline run in the **Pipeline Monitor** tab.

> `orca.db` is auto-created on the first pipeline run if it doesn’t exist. The `alerts` table is populated by `data/scheduler.py` (run `python data/scheduler.py --once` if the alert list is empty).

### Step 7 — Run the eval (terminal, no API key needed)

```bash
python evals/run_retrieval_eval.py
```

This is your starting point for the eval work (see Section 12).

-----

## 10. Deployment (Render) — for awareness

ORCA is deployed live on **Render** (free tier) as two web services:

- **API:** <https://orca-retail.onrender.com>  (`/health`, `/docs` for Swagger)
- **Dashboard:** <https://orca-dashboard.onrender.com>
- **GitHub:** <https://github.com/ankitv42/orca-retail>

**Important deployment fact:** On Render, **RAG is intentionally disabled**. The free tier has only 512 MB RAM, which can’t fit `torch` + `sentence-transformers` + ChromaDB. So the API there uses a slim `requirements.api.txt` that excludes those. The agents fall back to LLM knowledge only. This is a **deliberate trade-off, not a bug** — locally (with full requirements) RAG works fully. Do not “fix” RAG on Render; it’s by design.

-----

## 11. Known landmines (READ before debugging anything)

These cost real hours to discover. Don’t rediscover them.

### 11.1 The `C:/lit` / litellm path trap (Windows office laptop)

On the office laptop, `litellm` was installed separately with `pip install litellm --target C:/lit`. That folder *also* contains its own copies of `tokenizers` and `huggingface_hub`. The code used `sys.path.insert(0, "C:/lit")`, which put that folder **first** in Python’s search path — so the embedding model loaded the **wrong (incompatible) versions** from `C:/lit` and RAG died with `RuntimeError: No embedding model available`.

**Fix already applied:** change `insert(0, ...)` to `append(...)` in:

- `agents/graph.py` (around line 94)
- `api/main.py` (around line 75)

`append` puts `C:/lit` **last**, so the venv’s correct packages win. Recommended clean version for committing:

```python
import os
if os.path.exists(r"C:/lit"):
    sys.path.append(r"C:/lit")
```

This is harmless on machines without `C:/lit` (Render, personal laptop).

Also added: a **self-healing `is_available()`** in `retriever.py` that retries init if it failed during startup.

### 11.2 RAG shows “unavailable” locally

Almost always means **you didn’t run `python docs/rag/ingest.py --reset`** (empty ChromaDB), or `sentence-transformers` isn’t installed in the venv. See Section 9 Step 4.

### 11.3 The CrewAI / Groq `cache_breakpoint` error (active bug)

CrewAI’s internal LLM call adds a `cache_breakpoint` property to the system message. **Groq’s API rejects it** → the forecasting crew fails **every run** with a 400 error. The code catches this and falls back to a raw-data demand summary, so the pipeline still completes — but the CrewAI crew isn’t actually doing its job. See Issue #1.

### 11.4 Two laptops, two usernames

History spans an **office laptop** (`C:\Users\ankit.c.kumar.verma\...`) and a **personal laptop** (`C:\Users\anjal\...`). Paths in old logs differ for this reason. You’ll work on whichever machine you’re given — just know the repo is identical.

-----

## 12. YOUR TASK — the evaluation workstream

This is what you’ll actually build over the fortnight. ORCA evaluation has **three layers**. Layer 1 is started; Layers 2 and 3 are yours.

### The mental model (why eval exists)

ORCA makes autonomous money decisions. Without evaluation we’re flying blind — a prompt tweak or a doc change could silently break a decision and we’d never know until a wrong order goes out. Eval is **automated testing for AI behaviour**. On Palantir the platform watched quality for us; in open-source, *we* build that safety net. That net is your deliverable.

### Layer 1 — Retrieval eval ✅ (started — your first job is to calibrate it)

**Files:** `evals/golden_dataset.py`, `evals/run_retrieval_eval.py`
**What it does:** calls the real `query_for_agentN()` methods and checks whether the right keywords reached the context (**recall**) and whether wrong-document keywords leaked in (**precision**). Free to run, no API key.

**Your first task:**

```bash
python evals/run_retrieval_eval.py
```

Some cases may FAIL on the first run — **not** because retrieval is broken, but because the expected keywords in `golden_dataset.py` were written from memory and may not exactly match the wording in the real `.txt` docs (e.g. expected “approve” but the doc says “authorization”). **Open the 5 docs in `docs/`, read them, and adjust the `must_contain` keyword lists to match the real wording.** This calibration teaches you the whole knowledge base. Aim for ≥70% pass rate with zero keyword leaks.

> Pay special attention to the cases marked `"silent_failure": True`. These are traps where the agent could produce a plausible answer even if retrieval missed a key fact (like “Hindustan FMCG does NOT allow expedite”). Catching these is the whole point.

### Layer 2 — LLM-as-Judge eval 🔨 (YOUR MAIN BUILD)

**File to create:** `evals/run_judge_eval.py`
**Concept:** use a **stronger** LLM as a “judge” to score the agents’ decisions 1–5 on quality criteria. Our agents run on `llama-3.1-8b-instant`; the **judge runs on `llama-3.3-70b-versatile`** (stronger, same Groq key, free).

> Interview-grade nuance to understand and write in the README: the judge should ideally be from a *different model family* (e.g. GPT-4o or Claude) to avoid “family bias” — a model tends to rate its own family’s output favourably. We use llama-3.3-70b for cost reasons; note in the docs that the harness is model-agnostic and the judge is a one-line config swap.

**Criteria the judge should score (per agent decision):**

1. **RAG grounding** — did the agent reference the retrieved policy before deciding?
1. **HITL accuracy** — was human approval triggered exactly when cost exceeded the auto-approve limit?
1. **Scoring-formula correctness** — did Agent 3 apply the formula (Section 4) correctly?
1. **Class-A safety** — was Option B correctly never recommended for a Class A SKU?

**How to build it (suggested approach):**

- Reuse `agents.llm_factory.get_llm()` but point it at `llama-3.3-70b-versatile` (set `GROQ_MODEL` or add a judge-specific factory).
- Feed the judge: the input scenario + the agent’s output + the retrieved context.
- Ask it to return a JSON score (1–5) with a one-line reason per criterion.
- Parse the JSON, aggregate, and print a scorecard.
- Start with the **anchor scenario** (Ajwa Dates ESCALATE; Dish Soap AUTO_EXECUTE) as your first two judged cases.

You can study **DeepEval’s G-Eval** and **RAGAS** as references (these are the industry-standard libraries). You don’t have to use them — a clean hand-rolled judge with `get_llm()` is perfectly fine and arguably more educational — but read their docs so you understand faithfulness, context recall, context precision, and groundedness.

### Layer 3 — CI gate 🔨 (after Layers 1 & 2 are green)

**File to create:** `.github/workflows/eval_gate.yml`
**What it does:** runs the retrieval eval (and optionally the judge eval) automatically on every push to `main`. If scores drop below threshold, the build fails and the merge is blocked. This is **CI/CD** — automated quality gates.

- Start simple: a GitHub Action that checks out the code, installs deps, runs `python evals/run_retrieval_eval.py --ci`, and fails the job on a non-zero exit code.
- The retrieval eval already supports `--ci` (exits 1 if pass rate < 70% or any keyword leaks).

### Suggested fortnight plan

|Days  |Goal                                                                                            |
|------|------------------------------------------------------------------------------------------------|
|1–2   |Get ORCA running locally (Section 9). Read all 5 RAG docs.                                      |
|3–4   |Calibrate Layer 1 retrieval eval to ≥70% pass, 0 leaks.                                         |
|5–8   |Build Layer 2 LLM-as-judge (`run_judge_eval.py`). Judge the anchor scenarios first, then expand.|
|9–10  |Build Layer 3 CI gate (`eval_gate.yml`).                                                        |
|11–12 |Write findings into `docs/eval_findings.md`. Tidy, commit, document.                            |
|Buffer|Investigate any silent-failure traps that fail; tune docs/retriever if needed.                  |


> Commit often, with clear messages. Push to a **branch**, not directly to `main`, and open a PR so Ankit can review on return.

-----

## 13. ISSUE TRACKER (everything pending — READ THIS)

Ordered roughly by priority. Items marked **[eval]** are within your workstream; others are for awareness / if you have spare time.

|# |Issue                                                                                                                               |Severity|Status                |Notes                                                                                                                                                                                                      |
|--|------------------------------------------------------------------------------------------------------------------------------------|--------|----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|1 |**CrewAI `cache_breakpoint` Groq error** — forecasting crew fails every run, falls back to raw-data summary                         |HIGH    |Open                  |CrewAI adds `cache_breakpoint` to the system msg; Groq rejects it. Likely a litellm version pin or a CrewAI LLM config flag to disable prompt caching. Undercuts the “3-agent CrewAI crew” portfolio claim.|
|2 |**Layer 2 LLM-as-judge eval not built**                                                                                             |HIGH    |**[eval] — your task**|See Section 12.                                                                                                                                                                                            |
|3 |**Layer 3 CI/CD eval gate not built**                                                                                               |MEDIUM  |**[eval] — your task**|GitHub Actions. See Section 12.                                                                                                                                                                            |
|4 |**Unit tests (pytest) missing**                                                                                                     |HIGH    |Open                  |No `tests/` suite yet. `tools.py` and the API endpoints need unit tests with mocked LLM calls. Strong engineering signal if added.                                                                         |
|5 |**LangSmith tracing not added**                                                                                                     |MEDIUM  |Open                  |`LANGCHAIN_TRACING_V2=true` + API key would give per-node observability (latency, tokens, cost). Not started.                                                                                              |
|6 |**Layer 1 retrieval eval needs calibration**                                                                                        |MEDIUM  |**[eval] — your task**|Keyword lists written from memory; tune to real docs. See Section 12.                                                                                                                                      |
|7 |**Stale startup log line** in `api/main.py` (~line 156) prints `RAG: unavailable (Windows limitation)` even when RAG is available   |LOW     |Open                  |Cosmetic only — the `/health` endpoint reports correctly. Just an old log string.                                                                                                                          |
|8 |**`/api/v1/alerts` returns null fields** — `store_id`, `stock_status`, `current_stock`, `days_of_cover`, `risk_score` come back null|LOW     |Accepted              |Root cause: `get_critical_alerts()` joins at SKU level, not store level. Accepted because the pipeline fetches fresh store data when Analyse is clicked. Not a demo blocker.                               |
|9 |**Dashboard auto-refresh** was unreliable; reworked to always-on 3s polling                                                         |LOW     |Mostly resolved       |If it regresses, the polling lives in `dashboard/app.py`. Earlier attempts with `streamlit-autorefresh` and JS were flaky.                                                                                 |
|10|**First-SKU bug** — the very first SKU clicked sometimes errored while 2nd/3rd worked                                               |LOW     |Intermittent          |Seen during Docker testing. Re-verify locally; may already be resolved.                                                                                                                                    |
|11|**ADR documents not written**                                                                                                       |MEDIUM  |Open                  |`docs/adr/` with 5 Architecture Decision Records (LangGraph vs LangChain, ChromaDB vs Pinecone, embeddings choice, MCP vs hardcoded tools, Cloud Run vs K8s). For system-design interview prep.            |
|12|**`C:/lit` path lines** should be made conditional before committing                                                                |LOW     |Recommended           |Use the `if os.path.exists(r"C:/lit")` guard (Section 11.1) so the line is clean across all machines.                                                                                                      |
|13|**Render RAG disabled**                                                                                                             |N/A     |By design             |Not a bug — slim requirements for 512 MB free tier. Don’t “fix”.                                                                                                                                           |
|14|**LeetCode daily practice**                                                                                                         |N/A     |Ankit’s personal habit|Not part of the repo; ignore for eval work.                                                                                                                                                                |

-----

## 14. Glossary (whenever you’re stuck)

- **Agent** — an LLM given a specific role, prompt, and tools, that performs one reasoning step.
- **Multi-agent pipeline** — several agents chained so each one’s output feeds the next.
- **HITL (Human-In-The-Loop)** — the system pauses for a human decision before acting.
- **LangGraph node / edge** — a node is one step (an agent); edges connect steps. The graph defines the flow.
- **AgentState** — a shared dictionary (a “notebook”) that flows through every node carrying all results.
- **Checkpointer** — saves the graph’s state so it can pause and resume (how HITL works).
- **RAG (Retrieval-Augmented Generation)** — fetch relevant documents and put them in the prompt so the LLM answers from real knowledge, not just memory.
- **Chunk** — a small slice of a document stored in the vector DB.
- **Embedding** — a numeric vector representing text meaning; similar texts have similar vectors.
- **Vector search** — finding chunks whose embeddings are closest to the query embedding.
- **BM25** — a classic keyword-based search algorithm (good for exact terms like “CP003”).
- **Hybrid retrieval** — combining vector + BM25 search.
- **RRF (Reciprocal Rank Fusion)** — a formula to merge two ranked lists into one.
- **Reranker** — a model that re-scores retrieved chunks for relevance to the query.
- **Corrective RAG** — if retrieval looks weak, automatically retry with a better query.
- **MCP (Model Context Protocol)** — a standard that lets agents discover and call tools dynamically.
- **Tool** — a Python function the agent can call to fetch data or take an action.
- **Eval (evaluation)** — automated testing of AI behaviour quality.
- **Golden dataset** — a hand-written set of test cases with known-correct expectations.
- **LLM-as-judge** — using a (stronger) LLM to grade another LLM’s output.
- **G-Eval** — a specific LLM-as-judge technique (chain-of-thought scoring on custom criteria).
- **Faithfulness** — does the answer come only from the provided context (no hallucination)?
- **Groundedness** — sentence-level version of faithfulness (which exact sentence is supported?).
- **Context recall** — did retrieval fetch *all* the relevant info? (the “silent failure” metric)
- **Context precision** — was the retrieved info actually relevant (not noisy)?
- **Silent failure** — when the system looks healthy on one metric but is quietly broken on another (e.g. high faithfulness, low recall).
- **CI/CD** — Continuous Integration / Deployment; automated checks that run on every code push.
- **CI gate** — a check that blocks a merge if quality drops.
- **ABC class** — product importance tiers: A (most important, strict rules), B, C.
- **Capital pool** — a budget bucket (CP001, CP003…) with an auto-approve limit and a pressure flag.
- **Lead time** — days from placing an order to receiving stock.
- **Expedite** — faster (air freight) delivery at a premium cost = Option C.
- **AUTO_EXECUTE / ESCALATE / SUSPEND** — the three pipeline outcomes (Section 4).

-----

## 15. Where to find things / contacts

- **Repo:** <https://github.com/ankitv42/orca-retail>
- **Live API:** <https://orca-retail.onrender.com> (and `/docs` for the Swagger UI)
- **Live dashboard:** <https://orca-dashboard.onrender.com>
- **Your workspace in the repo:** the `evals/` folder.
- **Ankit:** travelling (USA) for ~2 weeks. Batch your questions; push work to a branch + PR for review on return. For anything that blocks you completely, note it in the issue tracker above and move to the next task.

-----

### Final note for you

You’ve joined at a genuinely good moment — the build is done, it’s deployed and working, and your job (evaluation) is the part that separates a “demo” from a “production-grade” system. Take your time with Section 9 (get it running) and Section 6 (understand RAG) before writing any eval code. Read the five `.txt` docs end to end — they *are* the business logic. Everything else will click from there.

Good luck. Commit often. Ask good questions.