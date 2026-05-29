# 🔱 ORCA — Open Retail Command Agent

<div align="center">

![ORCA Banner](https://img.shields.io/badge/ORCA-Open%20Retail%20Command%20Agent-f59e0b?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTEyIDJMMiA3bDEwIDUgMTAtNS0xMC01ek0yIDE3bDEwIDUgMTAtNS0xMC01LTEwIDV6Ii8+PC9zdmc+)

[![Live Demo](https://img.shields.io/badge/Live%20Demo-orca--dashboard.onrender.com-10b981?style=for-the-badge&logo=render)](https://orca-dashboard.onrender.com)
[![API Docs](https://img.shields.io/badge/API%20Docs-Swagger%20UI-3b82f6?style=for-the-badge&logo=fastapi)](https://orca-retail.onrender.com/docs)
[![GitHub](https://img.shields.io/badge/GitHub-ankitv42-181717?style=for-the-badge&logo=github)](https://github.com/ankitv42/orca-retail)

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1.10-f59e0b?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Containerised-2496ED?style=flat-square&logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**A production-grade multi-agent AI system for retail inventory management.**  
Built with LangGraph · CrewAI · MCP · RAG · FastAPI · Streamlit · Docker

</div>

---

## 🎯 The Problem

During peak retail events — Ramadan, Dubai Shopping Festival, Eid — 200+ UAE retail stores face a critical operational bottleneck:

- **Demand surges** are unpredictable and event-driven
- **Supplier lead times** may not align with urgency
- **Capital approval** for large orders requires human sign-off
- **Manual decisions** are slow, inconsistent, and not auditable

Store managers spend hours on WhatsApp with suppliers, comparing spreadsheets, and escalating to finance — while stockouts happen and revenue is lost.

**ORCA replaces this entire workflow with a 4-agent AI pipeline + one human decision.**

---

## 🤖 How It Works

```
Alert Triggered (stock critical/at-risk)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Agent 1 — Demand Intelligence (CrewAI crew)            │
│  • Event uplift analysis (Ramadan 2.8×, DSF 1.9×)      │
│  • Supplier constraint discovery                        │
│  • Confidence scoring + demand forecasting              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Agent 2 — Replenishment Options                        │
│  • Option A: Standard Replenishment                     │
│  • Option B: Profit Maximisation (Tier-1 stores)       │
│  • Option C: Expedite Air Freight                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Agent 3 — Capital Allocation & Scoring                 │
│  budget_score      = (1 - cost/budget) × 40            │
│  availability_score = availability_pct × 0.40 × 100   │
│  margin_score      = (1/margin_rank) × 20              │
│  lead_time_penalty = -20 if CRITICAL & lead > 30d     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Route Decision Node                                    │
│  • AUTO_EXECUTE  → cost < pool auto-approve limit      │
│  • ESCALATE      → cost > limit → human required       │
│  • SUSPEND       → pool pressure HIGH                  │
└────────────────────┬────────────────────────────────────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
         Human HITL     Auto Execute
         (Approve /     (reorder_triggered
          Reject)        = Yes → DB)
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Dashboard                       │
│              (Command Centre / Pipeline Monitor / HITL)      │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP (httpx)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Layer                           │
│  POST /pipeline/run → 202 + background task                 │
│  GET  /pipeline/{id}/state → polling endpoint               │
│  POST /pipeline/{id}/approve → HITL resume                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  LangGraph Pipeline                          │
│  agent1_node → agent2_node → agent3_node → route_node      │
│       ↓              ↓            ↓              ↓          │
│  CrewAI crew    Options Gen   Scoring     ESCALATE/AUTO     │
│  (3 AI agents)  (3 options)  (formula)    EXECUTE/SUSPEND   │
└──────────┬──────────────────────────────────────────────────┘
           │                    │
           ▼                    ▼
┌─────────────────┐    ┌─────────────────────┐
│   MCP Server    │    │    RAG Pipeline      │
│  (tool discovery│    │  ChromaDB + BGE     │
│   via stdio)    │    │  Reranker           │
└─────────────────┘    └─────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│               SQLite Database                                │
│  skus · stores · stock_positions · capital_pools            │
│  pipeline_log · supplier_data · events                       │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🤖 **Multi-Agent Pipeline** | 4 specialised LangGraph agents, each with a single responsibility |
| 👥 **CrewAI Integration** | 3-agent crew (Market Analyst, Supply Chain Expert, Risk Assessor) |
| 🔌 **MCP Tool Discovery** | Dynamic tool registration via Model Context Protocol — no hardcoded calls |
| 📚 **RAG Policy Retrieval** | BGE reranker + ChromaDB for policy-grounded decisions |
| ✋ **HITL Approval Workflow** | LangGraph interrupt → human reviews briefing → approve/reject |
| ⚡ **Async FastAPI** | 202 pattern — pipeline runs as background task, client polls state |
| 🎨 **Industrial Dashboard** | Dark theme Streamlit UI — Command Centre / Pipeline Monitor / HITL tabs |
| 🐳 **Docker + Render** | Fully containerised, deployed on Render free tier |
| 📊 **Audit Trail** | Every decision logged with reviewer, timestamp, action taken |

---

## 🛠️ Tech Stack

```
Layer              Technology
─────────────────────────────────────────────────
Orchestration      LangGraph 1.1.10
Multi-Agent        CrewAI 1.14.4
Tool Protocol      MCP (Model Context Protocol)
LLM                Groq / llama-3.1-8b-instant
Embeddings         nomic-ai/nomic-embed-text-v1.5
Reranker           BAAI/bge-reranker-base
Vector Store       ChromaDB 1.1.1
API Framework      FastAPI 0.136 + Uvicorn
Dashboard          Streamlit 1.57
HTTP Client        httpx 0.28
Database           SQLite + SQLAlchemy
Containerisation   Docker + docker-compose
Deployment         Render.com (free tier)
Observability      LangSmith (hooks ready)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker Desktop
- Groq API key (free at [console.groq.com](https://console.groq.com))

### Option 1 — Docker (recommended)

```bash
# Clone
git clone https://github.com/ankitv42/orca-retail.git
cd orca-retail

# Create .env
cat > .env << EOF
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
LLM_PROVIDER=groq
LANGCHAIN_TRACING_V2=false
EOF

# Build and run
docker-compose up --build
```

Open:
- Dashboard: http://localhost:8501
- API Docs: http://localhost:8080/docs

### Option 2 — Local Development

```bash
# Clone and setup
git clone https://github.com/ankitv42/orca-retail.git
cd orca-retail
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Create .env (same as above)

# Terminal 1 — API
uvicorn api.main:app --port 8080 --reload

# Terminal 2 — Dashboard
streamlit run dashboard/app.py
```

---

## 📁 Project Structure

```
orca-retail/
├── agents/
│   ├── graph.py          # LangGraph pipeline — all 4 agents + route logic
│   ├── prompts.py        # Agent prompts + scoring formula
│   ├── crew.py           # CrewAI crew (3 agents)
│   ├── llm_factory.py    # LLM provider abstraction
│   └── tools.py          # MCP tool definitions
│
├── api/
│   ├── main.py           # FastAPI app — 7 endpoints
│   └── models.py         # Pydantic schemas
│
├── dashboard/
│   ├── app.py            # Streamlit UI — 3 tabs
│   └── api_client.py     # HTTP client wrapper
│
├── docs/rag/
│   ├── ingest.py         # PDF → chunks → ChromaDB
│   └── retriever.py      # BGE reranker retrieval
│
├── db/
│   ├── queries.py        # SQLite query layer
│   ├── pipeline_log.py   # Audit log
│   └── schema.sql        # Database schema
│
├── mcp_server/
│   └── server.py         # MCP stdio server
│
├── data/
│   └── scheduler.py      # Alert generation scheduler
│
├── Dockerfile.api         # API container
├── Dockerfile.dashboard   # Dashboard container
├── docker-compose.yml     # Orchestration
└── requirements.txt       # Dependencies
```

---

## 🔌 API Reference

Base URL: `https://orca-retail.onrender.com`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | System status — DB, RAG, LLM, MCP |
| GET | `/api/v1/alerts` | 102 critical/at-risk SKU alerts |
| POST | `/api/v1/pipeline/run` | Trigger pipeline → returns 202 + pipeline_id |
| GET | `/api/v1/pipeline/{id}/state` | Poll pipeline state (progressive) |
| GET | `/api/v1/pipeline/{id}/briefing` | HITL briefing text |
| POST | `/api/v1/pipeline/{id}/approve` | Approve or reject HITL decision |
| GET | `/api/v1/pipelines` | Session audit log |

Full interactive docs: [https://orca-retail.onrender.com/docs](https://orca-retail.onrender.com/docs)

---

## 🎬 Demo Flow

1. Open [https://orca-dashboard.onrender.com](https://orca-dashboard.onrender.com)
2. **Command Centre** tab → click **Analyse** on any SKU (try Ajwa Dates 1kg — Class A, Ramadan event)
3. **Pipeline Monitor** tab → watch 4 agents complete progressively (auto-refreshes every 3s)
4. If pipeline is **ESCALATED** → go to **HITL Approval** tab
5. Enter your email → read the briefing → click **APPROVE**
6. `reorder_triggered = Yes` is written to the database

> ⚠️ Free tier note: Render free instances spin down after inactivity. First load may take 30–60 seconds to wake up.

---

## 📐 Architecture Decision Records

| Decision | Choice | Rationale |
|---|---|---|
| Graph framework | LangGraph | Stateful, interruptible, production-grade checkpointing |
| Multi-agent | CrewAI | Role-based agents with built-in crew orchestration |
| Tool protocol | MCP | Dynamic discovery vs hardcoded tool calls |
| LLM provider | Groq | Free tier, fast inference, llama-3.1 quality |
| HITL pattern | LangGraph interrupt | Clean pause/resume without polling hacks |
| API pattern | FastAPI + 202 | Non-blocking — pipeline runs as background task |
| Vector store | ChromaDB | Local, no external service, Docker-friendly |
| Dashboard | Streamlit | Python-native, rapid UI, sufficient for ops tools |
| Deployment | Render free | Zero cost public URL for portfolio demo |

---

## 🗺️ Sprint Roadmap

| Sprint | Focus | Status |
|---|---|---|
| Sprint 1 | Data Foundation (SQLite, 100 SKUs, 200 stores, scheduler) | ✅ Complete |
| Sprint 2 | LangGraph Pipeline + MCP Integration | ✅ Complete |
| Sprint 3 | RAG (ChromaDB + BGE) + CrewAI | ✅ Complete |
| Sprint 4 | FastAPI + Streamlit HITL Dashboard | ✅ Complete |
| Sprint 5 | Docker + Render Deployment | ✅ Complete |
| Sprint 6 | LangSmith Tracing + Redis + ADRs | 🔜 Planned |

---

## 🤝 About

Built by **Ankit Kumar Verma**  
Data Science Manager @ Accenture | Palantir Foundry | GCP Professional Data Engineer

This project is an open-source rebuild of the **Retail Command Centre (RCC)** — a production HITL multi-agent inventory system deployed across 200+ UAE retail stores on Palantir Foundry.

ORCA is my bridge from proprietary enterprise AI to portable, open-source agentic systems.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=flat-square&logo=linkedin)](https://www.linkedin.com/in/ankitv42)
[![GitHub](https://img.shields.io/badge/GitHub-ankitv42-181717?style=flat-square&logo=github)](https://github.com/ankitv42)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>If this project helped you, give it a ⭐ — it helps others find it.</sub>
</div>
