"""
ORCA — api/main.py
===================
FastAPI application — single entry point for all ORCA operations.
 
ARCHITECTURE:
    Streamlit dashboard → HTTP → FastAPI → graph.py → MCP → SQLite
                                         ↑
                                   This file
 
WHY FASTAPI:
    FastAPI is the standard Python API framework for production AI systems.
    Used by Hugging Face, Palantir (internally), and most Fortune 100 ML platforms.
    Auto-generates OpenAPI docs at /docs — important for FAANG interviews.
    Pydantic integration means every request/response is validated at the boundary.
    BackgroundTasks lets us return 202 immediately and run pipelines async.
 
BACKGROUND TASK PATTERN:
    Pipeline runs take 30-90 seconds (LLM calls + MCP + CrewAI).
    A synchronous endpoint would block the HTTP connection for 90 seconds — bad.
    Instead:
        POST /pipeline/run → launches background task → returns {pipeline_id} immediately
        GET  /pipeline/{id}/state → client polls this every 3 seconds
        POST /pipeline/{id}/approve → resumes paused pipeline
 
    In-memory store (_pipeline_store) holds running state between requests.
    In Sprint 5 this upgrades to Redis or PostgreSQL for multi-instance support.
 
PIPELINE STORE:
    Simple dict: pipeline_id → PipelineStateResponse
    Thread-safe for single-worker dev. Production uses Redis.
    Store is populated at task launch and updated after each phase.
 
LIFESPAN:
    FastAPI lifespan context manager runs startup/shutdown logic.
    Startup: verifies DB connection, logs all system status.
    Shutdown: clean log.
 
CORS:
    Configured for localhost:8501 (Streamlit default port).
    In production, restrict to your domain.
 
OPENAPI:
    Auto-generated at http://localhost:8080/docs (Swagger UI)
    and http://localhost:8080/redoc (ReDoc).
    These are your FAANG demo URLs — always keep them working.
 
Usage:
    uvicorn api.main:app --reload --port 8080
    OR
    python api/main.py


    Client (Streamlit)
    │
    │ HTTP request
    ▼
FastAPI Event Loop (asyncio)          ← handles 1000s of concurrent requests
    │
    ├── GET /health          → responds in 1ms, fully async
    ├── GET /alerts          → responds in 5ms, fully async
    ├── GET /state           → responds in 2ms, fully async (reads from store)
    ├── POST /approve        → responds in 3s, sync but short
    │
    └── POST /run            → adds to thread pool, responds in 1ms
              │
              ▼
         Thread Pool (anyio)
              │
              └── _run_pipeline_task()   ← blocking, runs here, 30-90 seconds
                      │
                      └── run_pipeline() → CrewAI → MCP → LLM → DB
"""
import sys
sys.path.append(r"C:/lit")   # litellm short-path — Windows workaround

import json
import logging
import asyncio
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.append(str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.models import (
    RunPipelineRequest, PipelineRunResponse, PipelineStateResponse,
    ApproveRequest, ApproveResponse, AlertsResponse, HealthResponse,
    ErrorResponse, PipelineStatus, Alert,
    DemandSummary, OptionsPackage, ReplenishmentOption,
    CapitalDecision, ScoredOption,
)

from agents.graph import run_pipeline, resume_pipeline, get_pipeline_state
from agents.graph import _retriever
from agents.llm_factory import get_provider_name, get_model_name
from db.queries import get_critical_alerts, get_sku_details
from db.pipeline_log import create_pipeline_table

logger = logging.getLogger("orca.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ==============================================================================
# IN-MEMORY PIPELINE STORE
# pipeline_id → dict of pipeline metadata + latest state snapshot
# Upgraded to Redis in Sprint 5
# ==============================================================================

_pipeline_store: dict[str, dict] = {}
_store_lock = threading.Lock()   # guards _pipeline_store against concurrent updates


def _now() -> str:
    """Returns current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _store_update(pipeline_id: str, **kwargs):
    """Thread-safe update of pipeline store entry."""
    with _store_lock:
        if pipeline_id not in _pipeline_store:
            _pipeline_store[pipeline_id] = {}
        _pipeline_store[pipeline_id].update(kwargs)
        _pipeline_store[pipeline_id]["last_updated"] = _now()


# ==============================================================================
# LIFESPAN — startup / shutdown
# ==============================================================================

@asynccontextmanager                    # A async context manager(decorator) is anything that has a "before" and "after" step. lets you write your own context manager using yield:
async def lifespan(app: FastAPI):       #  Takes app as a parameter — FastAPI passes itself in
    """
    Runs at application startup and shutdown.                   # Everything BEFORE yield  →  runs at startup
    Startup: verify DB, log system status.                      #         yield            →  app runs here (paused)
    Shutdown: clean log.                                        # Everything AFTER yield   →  runs at shutdown
    """
    # STARTUP
    logger.info("ORCA API starting up...")
    try:
        create_pipeline_table()
        logger.info("DB: pipeline_log table ready")
    except Exception as e:
        logger.error(f"DB startup error: {e}")
    
    rag_status = "available" if (_retriever and _retriever.is_available()) else "unavailable (Windows limitation)"
    logger.info(f"RAG: {rag_status}")                                   # Is RAG (vector search) available? Log it.
    logger.info(f"LLM: {get_provider_name()} / {get_model_name()}")     # Which LLM provider/model are we using? Log it.
    logger.info("ORCA API ready — listening on http://localhost:8000")
    logger.info("OpenAPI docs: http://localhost:8000/docs")


    yield  # app runs here                                              # yield  # app runs here ← THE PAUSE POINT
                                                                        # This single line is the entire lifetime of your running server — 
                                                                        # every request, every response, all 30-90 second pipelines. Everything happens 
                                                                        # while the code is "frozen" at yield.
    # SHUTDOWN
    logger.info("ORCA API shutting down...")                            #Teardown block — runs when you press Ctrl+C or the server stops. Currently just logs — in production this is where you'd flush queues, close DB connections, etc.

# ==============================================================================
# FASTAPI APP
# ==============================================================================

app = FastAPI(
    title="ORCA — Open Retail Command Agent",
    description=(
        "Multi-agent inventory management API. "
        "LangGraph pipeline with CrewAI forecasting, MCP tool discovery, "
        "RAG policy retrieval, and Human-in-the-Loop approval workflow."
    ),
    version="3.0.0-sprint3",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    )


# CORS - allow Streamlit (8501) and local dev
# You're attaching a middleware — a layer that wraps every single request before it reaches your route handlers.
# Think of it like a security checkpoint at the entrance of your API. Every request passes through it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[                                            # The whitelist — only these addresses are trusted. localhost and 127.0.0.1 
                                                               # are the same machine but browsers treat them as different origins, so both are listed explicitly. 
                                                               # Miss one and Streamlit breaks silently.              
        "http://localhost:8501",  # Streamlit default           
        "http://localhost:3000",    # React dev server (future)
        "http://127.0.0.1:8501",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,     # Allows cookies and Authorization headers to be sent cross-origin. Allows cookies and Authorization headers to be sent cross-origin.
    allow_methods=["*"],        # ["*"] means any HTTP method (GET, POST, DELETE, PATCH...) and any header is allowed.
    allow_headers=["*"],        # any header "Content-Type", "Authorization" etc allowed, In prod we tighten this by specifically naming
)
'''
CORS Middleware -- what is it ??
--------------------------------
Step 1: Intuition — Why does CORS exist?,Imagine two neighbors:

        House A = your Streamlit frontend at localhost:8501
        House B = your FastAPI backend at localhost:8000

Your browser has a security guard (called the Same-Origin Policy). Its rule:
                            "You can only fetch data from the same house you came from."
                            So when Streamlit (8501) tries to call FastAPI (8000) — different port = different origin — the browser's guard blocks it.

CORS is how House B (FastAPI) tells the guard: "It's okay, I trust House A. Let them in."

Step 2: What is an "Origin"?
An origin = protocol + domain + port. All three must match.


http://localhost:8501   ← origin 1  (Streamlit)
http://localhost:8000   ← origin 2  (FastAPI)
                  ^^^^
                  different port = different origin = BLOCKED by default
Same domain, different port → still blocked. That's why CORS is needed.

CORS is not a FastAPI feature — it's a browser security rule. Your backend adds CORS headers to opt-in to trusting specific origins. 
FastAPI's CORSMiddleware handles all the boilerplate so you just provide the whitelist.
'''

# ==============================================================================
# EXCEPTION HANDLERS
# consistent error shape for all errors
# ==============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            path=str(request.url.path),
            timestamp=_now(),
        ).model_dump(),
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            path=str(request.url.path),
            timestamp=_now(),
        ).model_dump(),
    )

'''
Exception for Two Types of Errors — The Key Distinction

All errors
    │
    ├── HTTPException     ← YOU raised it intentionally
    │       e.g. raise HTTPException(404, "not found")
    │
    └── Exception         ← something CRASHED unexpectedly
            e.g. KeyError, AttributeError, DB connection lost
One handler for each. This is the architecture.

The flow:


Route code HTTPException:
    raise HTTPException(404, "Pipeline not found")
                │
                ▼
FastAPI catches it → calls http_exception_handler()
                │
                ▼
Client receives:
{
  "error": "Pipeline not found",
  "path": "/pipeline/abc123/state",
  "timestamp": "2026-05-27T10:45:00Z"
}
You control the status code. You control the message. Nothing leaks.

Route code Exception:
This catches everything else — bugs you didn't anticipate.


    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
exc_info=True — this is important. It tells the logger to print the full stack trace to your server logs, so you can debug it. 
But the client never sees the stack trace.


Notice the deliberate difference:

HTTPException handler → returns exc.detail       (your message, safe to expose)
Exception handler     → returns "Internal server error"  (vague, hides internals)
                        + detail=str(exc)         (dev info, but not the traceback)
The full stack trace only goes to your server logs — never to the client. This prevents attackers from learning your file 
paths, DB schema, or internal logic from error messages.
'''



# ==============================================================================
# HELPERS — state conversion
# Converts raw graph.py state dict → Pydantic response models
# ==============================================================================



'''
What problem are all three solving?
Your AI pipeline(graph.py) returns one big raw python dict. Think of it like a shipping container — everything dumped in together, unorganized, unverified.

raw_state = {
    "demand_summary":   { "urgency": "HIGH", "confidence_score": 0.91, ... },
    "options_package":  { "options": [ {...}, {...}, {...} ], ... },
    "capital_decision": { "scored_options": [ {...}, {...} ], ... },
    "hitl_briefing":    {...........}
}

Your pipeline (the AI agent graph) works internally with raw Python dicts — loose, untyped, flexible. Like a chef's rough notes scribbled on a napkin.
Your API must send Streamlit a clean, typed, validated JSON — a proper printed menu with guaranteed fields.

Each of the three nested dicts has its own shape and rules. You need three specialized workers — one per section — to unpack each box and hand back a clean, 
typed Pydantic object.

You can't send a raw dict directly as a typed API response. Problems:

No validation — a missing field won't be caught
No type guarantees — confidence_score could be a string or None
No consistent shape — Streamlit can't rely on it
Pydantic models fix all three.

HELPERS are the translator between those two worlds. from python raw dict to pydantic validated, typed, serializable.

raw_state
    ├── demand_summary   ──► _parse_demand_summary()  ──► DemandSummary
    ├── options_package  ──► _parse_options_package() ──► OptionsPackage
    └── capital_decision ──► _parse_capital_decision()──► CapitalDecision

'''


# Every _parse_* function follows the exact same skeleton:
'''
Part 1: Guard clause   — handle None/empty input
Part 2: Loop (maybe)   — build list of nested sub-objects (if needed)
Part 3: Return         — construct and return the Pydantic model

'''

# This one is flat — no nested lists. Just extract each key and hand it to Pydantic.

def _parse_demand_summary(ds: Optional[dict]) -> Optional[DemandSummary]:  # Input: ds is either a dict or None, Output: DemandSummary (Pydantic) or None
    if not ds:                                              # Part 1: Guard
        return None                                         # If demand analysis hasn't run yet, ds is None. Return None early — no crash.
    return DemandSummary(
        sku_id              = ds.get("sku_id", ""),         # Notice ds.get("sku_id", "") — sku_id gets an empty string default instead of None because Pydantic's DemandSummary model requires it to be a string, not optional.
        urgency             = ds.get("urgency"),
        critical_stores     = ds.get("critical_stores"),
        at_risk_stores      = ds.get("at_risk_stores"),
        projected_shortfall = ds.get("projected_shortfall"),
        lead_time_too_late  = ds.get("lead_time_too_late"),
        event_name          = ds.get("event_name"),
        demand_trend        = ds.get("demand_trend"),
        confidence_score    = ds.get("confidence_score"),
        briefing            = ds.get("briefing"),
        crew_insights       = ds.get("crew_insights"),

    )

def _parse_options_package(op: Optional[dict]) -> Optional[OptionsPackage]:
    if not op:                                              # Part 1: Guard
        return None
    options = []                                            # Part 2: Build sub-list
    for o in op.get("options", []):                         # ← "options" is a list of dicts
        options.append(ReplenishmentOption(
            id                = str(o.get("id", "")),       # str(o.get("id", "")) — notice the forced string cast. The raw dict may have integer IDs from the DB. Pydantic's model expects a string. Cast it explicitly.
            name              = o.get("name"),
            order_qty         = o.get("order_qty"),
            lead_time_days    = o.get("lead_time_days"),
            total_cost_aed    = o.get("total_cost_aed"),
            pool_id           = o.get("pool_id"),
            availability_pct  = o.get("availability_pct"),
            feasible          = o.get("feasible"),
            not_recommended   = o.get("not_recommended"),
            elimination_reason = o.get("elimination_reason"),
        ))
    return OptionsPackage(
        recommended           = op.get("recommended"),
        recommendation_reason = op.get("recommendation_reason"),
        options               = options,                  #  ← the list we just built
    )

def _parse_capital_decision(cd: Optional[dict]) -> Optional[CapitalDecision]:
    if not cd:
        return None
    scored = []
    for o in cd.get("scored_options", []):
        scored.append(ScoredOption(
            id                 = str(o.get("id", "")),
            total_score        = o.get("total_score"),
            budget_score       = o.get("budget_score"),
            availability_score = o.get("availability_score"),
            margin_score       = o.get("margin_score"),
            lead_time_penalty  = o.get("lead_time_penalty"),
            feasible           = o.get("feasible"),
            elimination_reason = o.get("elimination_reason"),
            not_recommended    = o.get("not_recommended"),
        ))
    return CapitalDecision(
        recommended            = cd.get("recommended"),
        approval_required      = cd.get("approval_required"),
        approval_amount_aed    = cd.get("approval_amount_aed"),
        approval_pool          = cd.get("approval_pool"),
        recommendation_summary = cd.get("recommendation_summary"),
        scored_options         = scored,
    )


# All three results flow into _build_state_response() → PipelineStateResponse → JSON

def _build_state_response(pipeline_id: str, raw_state: dict) -> PipelineStateResponse:
    """Converts raw graph.py state dict → PipelineStateResponse."""
    return PipelineStateResponse(
        pipeline_id      = pipeline_id,
        sku_id           = raw_state.get("sku_id"),
        store_id         = raw_state.get("store_id"),
        status           = raw_state.get("final_status"),
        route            = raw_state.get("route"),
        action_taken     = raw_state.get("action_taken"),
        demand_summary   = _parse_demand_summary(raw_state.get("demand_summary")),
        options_package  = _parse_options_package(raw_state.get("options_package")),
        capital_decision = _parse_capital_decision(raw_state.get("capital_decision")),
        hitl_briefing    = raw_state.get("hitl_briefing"),
        last_updated     = _now(),
    )

# ==============================================================================
# BACKGROUND TASK — pipeline runner
# Runs in a background thread so POST /pipeline/run returns immediately
# ==============================================================================
'''
_run_pipeline_task - Why does this function exist?

Your AI pipeline takes 30–90 seconds (LLM calls, CrewAI agents, DB reads).
If you ran it directly inside a route handler, the HTTP connection would stay open for 90 seconds. Streamlit would freeze. Users would think the app crashed.
The fix:  Give Streamlit a ticket number immediately. Cook in the background.

The Dhabba Analogy
-----------------

You walk into a dhabba.
    You order food.  ← this is POST /run (Streamlit asking "start the pipeline")
Waiter says:
    "Order number 42. Sit down, we'll cook."  ← API returns pipeline_id immediately
You sit. Every 2 minutes you ask the waiter:
    "Bhai, order 42 ready hua?"  ← this is GET /state (Streamlit checking)
Waiter checks kitchen:
    "Abhi ban raha hai..."  ← status = RUNNING
    "Abhi ban raha hai..."  ← status = RUNNING
    "Ready hai!"  ← status = APPROVED / DONE

POST /pipeline/run
      │
      ├── launches _run_pipeline_task() in background thread ─────────────────►
      │                                                          (runs 30-90s)
      └── returns {pipeline_id} to Streamlit in ~1ms ◄──────────── immediately

Streamlit polls GET /state every 3s to check progress


That's the entire system. _run_pipeline_task is the kitchen.

The board = _pipeline_store (just a Python dictionary in memory)
Streamlit reading the board = GET /state endpoint

_run_pipeline_task is the worker that runs in that background thread while Streamlit is already back on screen showing a spinner.


: Can the SAME user do anything while pipeline runs?
Yes. Streamlit is NOT frozen.

Why? Because Streamlit already got the reply:


Streamlit → POST /run → got back {pipeline_id: "abc123"} in 1ms
Streamlit is done waiting. It's now showing a spinner on screen. The user can click buttons, navigate pages — Streamlit is alive.

Every 3 seconds Streamlit quietly asks FastAPI in the background: "Hey, order abc123 done yet?" — that's a tiny instant call, not a freeze.
----------------

When WOULD Streamlit freeze?
Only if you had written it the wrong way — without BackgroundTasks:


# WRONG WAY (no background task)
@app.post("/run")
def run(req):
    result = run_pipeline()   # Agent 1 gets stuck here 60 seconds
    return result             # Streamlit frozen until this line
Here Agent 1 is stuck. Streamlit sent the request TO Agent 1 and is waiting for Agent 1 to reply. Agent 1 can't reply until pipeline finishes. That would freeze Streamlit.

Your code avoids this completely by handing the work to Agent 4 first, then Agent 1 replies immediately.

'''
def _run_pipeline_task(pipeline_id: str, sku_id: str, store_id: str):       #This is the kitchen worker. Gets told: which order (pipeline_id), which product (sku_id), which store (store_id).
    """
    Background task — runs the full LangGraph pipeline.
 
    Called by FastAPI BackgroundTasks after POST /pipeline/run returns.
    Updates _pipeline_store throughout so GET /state polls pick up progress.
 
    Error handling:
        Any unhandled exception → store status=FAILED, log full traceback.
        Pipeline never crashes the API process — it fails gracefully.
    """
    try:
        logger.info(f"Background task starting | {pipeline_id}")
        _store_update(pipeline_id, status=PipelineStatus.RUNNING)          # Kitchen puts a sticky note on the board: Order 42 → RUNNING
                                                                           # Now if Streamlit asks "what's the status of order 42?" — it sees RUNNING. Not blank. Not crashed.
                                                                           # First thing: write RUNNING into _pipeline_store. Now if Streamlit polls /state at this exact moment, it sees "status": "RUNNING" — not a 404, not stale data.

        # run the pipeline — this blocks until HITL pause or completion, This single line calls graph.py which runs the entire AI pipeline:
        # This blocks the thread for 30–90 seconds. That's okay — it's in a background thread, not the main event loop. The API keeps serving other requests normally.
        final_state = run_pipeline(sku_id=sku_id, store_id=store_id)       # This is the actual cooking. Calls the AI agents. Takes 30–90 seconds. Blocks here until done.
                                                                           # final_state = the finished dish — everything the AI figured out (demand, options, decision).
        # determine status
        fs = final_state.get("final_status", "") or ""
        route = final_state.get("route", "") or ""
        # if AUTO_EXECUTE — pipeline resumes immediately in background task
        if route == "AUTO_EXECUTE" and fs in ("", None, "ESCALATED"):
            final_state = resume_pipeline(pipeline_id=pipeline_id, approved=True)
            fs = final_state.get("final_status", "") or "AUTO_EXECUTED"
        status = PipelineStatus(fs) if fs in PipelineStatus._value2member_map_ else PipelineStatus.AUTO_EXECUTED
        
        '''
                                                                         This is a safe enum conversion. The pipeline returns a string like "APPROVED" or "HITL_REQUIRED". 
                                                                        You need to turn it into the PipelineStatus enum.
                                                Two cases:
                                                            "APPROVED"       → PipelineStatus("APPROVED") → PipelineStatus.APPROVED  ✓
                                                            "some_garbage"   → not in _value2member_map_  → PipelineStatus.FAILED    ✓ (safe default)
                                                            ""               → not in _value2member_map_  → PipelineStatus.FAILED    ✓ (safe default)
                                                _value2member_map_ is a built-in Python dict that every Enum has — it maps string values to their enum members. Checking it before converting prevents a ValueError crash.                
                                                        '''
 
        _store_update(                                  # Kitchen updates the board:Order 42 → APPROVED  ✓  (full result stored here)
            pipeline_id,
            status       = status,
            raw_state    = final_state,
            final_status = fs,
        )
        logger.info(f"Background task complete | {pipeline_id} | {status}")
 
    except Exception as e:
        logger.error(f"Background task failed | {pipeline_id} | {e}", exc_info=True)
        _store_update(pipeline_id, status=PipelineStatus.FAILED, error=str(e))
                                            # If the kitchen catches fire (any crash, LLM timeout, DB down) — don't let the whole dhabba burn down.
                                            # Just update the board:
                                            # Order 42 → FAILED  (reason: "LLM timeout")
                                            # Streamlit sees FAILED and shows the user an error. The rest of the app keeps running normally.


# ==============================================================================
# ROUTES
# ==============================================================================
 
# ── Health ───────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Liveness and readiness check",
)

async def health():
    """
    Returns system status for all ORCA components.
    Used by load balancers and monitoring dashboards.
    Status is 'ok' if all critical components are up, 'degraded' if RAG is unavailable.
    """
    rag_ok = _retriever is not None and _retriever.is_available()

    # quick DB check
    try:
        alerts = get_critical_alerts()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    
    return HealthResponse(
        status    = "ok" if db_status == "connected" else "degraded",
        db        = db_status,
        rag       = "available" if rag_ok else "unavailable (Windows path conflict — resolves on GCP)",
        llm       = f"{get_provider_name()}/{get_model_name()}",
        mcp       = "ready",
        version   = "3.0.0-sprint3",
        timestamp = _now(),
    )


# ── Alerts ───────────────────────────────────────────────────────────────────

@app.get(
    "/api/v1/alerts",
    response_model=AlertsResponse,
    tags=["Alerts"],
    summary="Get current critical and at-risk alerts",
)
async def get_alerts():
    """
    Returns all SKUs currently in Critical or At Risk stock status.
    Streamlit Command Centre panel polls this every 30 seconds.
    Each alert contains enough context to trigger a pipeline run.
    """
    try:
        raw_alerts = get_critical_alerts()
        alerts = []
        for a in raw_alerts:
            alerts.append(Alert(
                sku_id        = a.get("sku_id", ""),
                sku_name      = a.get("sku_name"),
                category      = a.get("category"),
                abc_class     = a.get("abc_class"),
                store_id      = a.get("store_id"),
                stock_status  = a.get("stock_status"),
                current_stock = a.get("current_stock_units"),
                days_of_cover = a.get("days_of_cover"),
                risk_score    = a.get("risk_score"),
            ))
        return AlertsResponse(total=len(alerts), alerts=alerts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ── Pipeline — Run ────────────────────────────────────────────────────────────

@app.post(
    "/api/v1/pipeline/run",
    response_model=PipelineRunResponse,
    status_code=202,
    tags=["Pipeline"],
    summary="Trigger a new pipeline run",
)
async def run_pipeline_endpoint(
    body: RunPipelineRequest,
    background_tasks: BackgroundTasks,
):
    """
    Launches the ORCA 4-agent pipeline as a background task.
 
    Returns 202 Accepted immediately with pipeline_id.
    Client must poll(matlab bar bar ping karna) GET /api/v1/pipeline/{pipeline_id}/state every 3 seconds.
 
    Pipeline flow:
        Agent 1 (CrewAI forecasting crew) →
        Agent 2 (Supply replenishment options) →
        Agent 3 (Capital allocation + scoring) →
        Route node (ESCALATE / AUTO_EXECUTE / SUSPEND) →
        [HITL pause OR execute OR suspend]
 
    If pipeline is AUTO_EXECUTE:
        The background task resumes the pipeline immediately after HITL pause.
        No human action required.
 
    If pipeline is ESCALATE:
        Pauses and waits for POST /approve or /reject.
    """
    from datetime import date

    # validate SKU exists in DB before launching expensive background task
    sku = get_sku_details(body.sku_id)
    if sku is None:
        raise HTTPException(
            status_code=422,
            detail=f"SKU '{body.sku_id}' not found in inventory database.",
        )

    pipeline_id = f"PIPE_{body.sku_id}_{date.today().strftime('%Y-%m-%d')}"

    # check if already running
    existing = _pipeline_store.get(pipeline_id, {})
    if existing.get("status") == PipelineStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline {pipeline_id} is already running. Poll /state for updates."
        )
    
    # initialise store entry
    started_at = _now()
    _store_update(
        pipeline_id,
        sku_id      = body.sku_id,
        store_id    = body.store_id,
        status      = PipelineStatus.STARTED,
        started_at  = started_at,
    )


    # launch background task — returns immediately
    background_tasks.add_task(
        _run_pipeline_task,
        pipeline_id = pipeline_id,
        sku_id      = body.sku_id,
        store_id    = body.store_id,
    )
    

    logger.info(f"Pipeline launched | {pipeline_id} | sku={body.sku_id} store={body.store_id}")
 
    return PipelineRunResponse(
        pipeline_id = pipeline_id,
        status      = PipelineStatus.STARTED,
        message     = "Pipeline launched. Poll /state for updates.",
        started_at  = started_at,
    )

# ── Pipeline — State ──────────────────────────────────────────────────────────

'''
get_pipeline_state_endpoint is Streamlit's "are we there yet?" checker. Every 3 seconds, it looks up the pipeline in two places — 
RAM (fast) and LangGraph checkpoint (accurate). 

Combines both, returns the freshest state possible. If pipeline is still running, shows partial results. If done, shows everything
'''


@app.get(
    "/api/v1/pipeline/{pipeline_id}/state",
    response_model=PipelineStateResponse,
    tags=["Pipeline"],
    summary="Poll pipeline state",
)
async def get_pipeline_state_endpoint(pipeline_id: str):
    """
    Returns current state of a pipeline run.
    Streamlit polls this every 3 seconds to show live progress.
 
    Response fields become non-null progressively:
        After Agent 1: demand_summary populated
        After Agent 2: options_package populated
        After Agent 3: capital_decision populated
        After HITL:    hitl_briefing populated, status=ESCALATED
 
    When status=ESCALATED, the Approve/Reject buttons become active in Streamlit.
    """
    store_entry = _pipeline_store.get(pipeline_id)
    if not store_entry:
        # try loading from graph checkpoint (for pipelines started before API restart)
        try:
            raw_state = get_pipeline_state(pipeline_id)
            if raw_state:
                return _build_state_response(pipeline_id, raw_state)
        except Exception:
            pass
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline {pipeline_id} not found."
        )
    

    raw_state = store_entry.get("raw_state", {})
 
    # if still running — pull live state from graph checkpoint
    if store_entry.get("status") in (PipelineStatus.STARTED, PipelineStatus.RUNNING):
        try:
            live_state = get_pipeline_state(pipeline_id)
            if live_state:
                raw_state = live_state
        except Exception:
            pass   # use last known store state
 
    response = _build_state_response(pipeline_id, raw_state)
 
    # override status from store (more up to date than graph state)
    store_status = store_entry.get("status")
    if store_status:
        response.status = store_status if isinstance(store_status, str) else store_status.value
 
    return response


# ── Pipeline — Approve ────────────────────────────────────────────────────────

@app.post(
    "/api/v1/pipeline/{pipeline_id}/approve",
    response_model=ApproveResponse,
    tags=["Pipeline"],
    summary="Approve a paused HITL pipeline",
)
async def approve_pipeline(pipeline_id: str, body: ApproveRequest):
    """
    Resumes a pipeline paused at the HITL checkpoint.
    approved=True → execute_node runs, reorder_triggered=Yes written to DB.
    approved=False → suspend_node runs, no order placed.
 
    Only valid when pipeline status=ESCALATED.
    Returns final state after resumption.
    """

    store_entry = _pipeline_store.get(pipeline_id, {})
    current_status = store_entry.get("status")

    if not store_entry:
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found.")
 
    if current_status not in (PipelineStatus.ESCALATED, "ESCALATED"):
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline {pipeline_id} is not awaiting approval. Current status: {current_status}"
        )
    
    try:
        reviewed_at = _now()
        logger.info(
            f"HITL decision | {pipeline_id} | "
            f"approved={body.approved} | reviewer={body.reviewer}"
        )
 
        # resume pipeline — this is synchronous (short, just runs execute/suspend node)
        final_state = resume_pipeline(pipeline_id=pipeline_id, approved=body.approved)
 
        # fs = final_state.get("final_status", "")
        # status = PipelineStatus(fs) if fs in PipelineStatus._value2member_map_ else PipelineStatus.FAILED

        # # determine final status from approved decision
        # if body.approved:
        #     fs     = final_state.get("final_status", "EXECUTED_AFTER_APPROVAL")
        #     status = PipelineStatus.EXECUTED_AFTER_APPROVAL if "EXECUTED" in (fs or "").upper() else PipelineStatus.EXECUTED_AFTER_APPROVAL
        # else:
        #     status = PipelineStatus.REJECTED

        status = PipelineStatus.EXECUTED_AFTER_APPROVAL if body.approved else PipelineStatus.REJECTED
 
        _store_update(
            pipeline_id,
            status       = status,
            raw_state    = final_state,
            reviewed_by  = body.reviewer,
            reviewed_at  = reviewed_at,
        )
 
        action = final_state.get("action_taken", "")
        return ApproveResponse(
            pipeline_id  = pipeline_id,
            status       = status,
            action_taken = action,
            message      = f"Pipeline {'approved' if body.approved else 'rejected'} and completed.",
            reviewed_by  = body.reviewer,
            reviewed_at  = reviewed_at,
        )
 
    except Exception as e:
        logger.error(f"Approve failed | {pipeline_id} | {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Pipeline — Briefing ───────────────────────────────────────────────────────
 
@app.get(
    "/api/v1/pipeline/{pipeline_id}/briefing",
    tags=["Pipeline"],
    summary="Get HITL briefing text",
)
async def get_briefing(pipeline_id: str):
    """
    Returns the HITL briefing text for a paused pipeline.
    Used by Streamlit HITL panel to display the planner briefing.
    """
    store_entry = _pipeline_store.get(pipeline_id, {})
    raw_state   = store_entry.get("raw_state", {})
    briefing    = raw_state.get("hitl_briefing")
 
    if not briefing:
        # try checkpoint
        try:
            state    = get_pipeline_state(pipeline_id)
            briefing = state.get("hitl_briefing") if state else None
        except Exception:
            pass
 
    if not briefing:
        raise HTTPException(
            status_code=404,
            detail=f"No briefing found for pipeline {pipeline_id}. "
                   f"Pipeline may not be at HITL stage yet."
        )
 
    return {"pipeline_id": pipeline_id, "briefing": briefing, "timestamp": _now()}
 
 
# ── Pipeline — List ───────────────────────────────────────────────────────────
 
@app.get(
    "/api/v1/pipelines",
    tags=["Pipeline"],
    summary="List all pipeline runs in this session",
)
async def list_pipelines():
    """
    Returns all pipeline runs tracked in the current session.
    Used by Streamlit audit log panel.
    Resets on API restart (use pipeline_log DB table for persistent history).
    """
    pipelines = []
    for pid, entry in _pipeline_store.items():
        pipelines.append({
            "pipeline_id": pid,
            "sku_id":      entry.get("sku_id"),
            "store_id":    entry.get("store_id"),
            "status":      entry.get("status").value if hasattr(entry.get("status"), "value") else entry.get("status"),
            "started_at":  entry.get("started_at"),
            "last_updated": entry.get("last_updated"),
        })
    # sort by started_at descending
    pipelines.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return {"total": len(pipelines), "pipelines": pipelines}
 
 
# ==============================================================================
# DEV RUNNER
# ==============================================================================
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,          # auto-reload on code changes
        log_level="info",
    )