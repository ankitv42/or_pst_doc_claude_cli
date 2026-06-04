# ORCA — 16 Production & Reliability Interview Questions

> **Focus area.** Thread safety, error handling, deployment constraints, graceful
> degradation, and production-readiness decisions. These questions test engineering
> maturity — the ability to ship and maintain systems, not just build them.

---

## Q1 — How does the API handle multiple simultaneous pipeline runs without corrupting shared state?

### The Question to Ask
*"Two users click Analyse at the same time on different SKUs. Both pipelines write to `_pipeline_store`. What prevents corruption?"*

### Strong Answer
`_pipeline_store` is a plain Python dict — a **shared mutable data structure**.
Without protection, two threads could interleave reads and writes:

```
Thread 1 (SKU001): reads _pipeline_store    → gets {"SKU001": RUNNING}
Thread 2 (SKU002): reads _pipeline_store    → gets {"SKU001": RUNNING}
Thread 1: writes   _pipeline_store["SKU001"] = COMPLETED
Thread 2: writes   _pipeline_store["SKU002"] = COMPLETED
→ Race condition: both writes succeed, but Thread 1's write could be lost
  if the underlying dict resizes during Thread 2's write.
```

ORCA protects it with a `threading.Lock`:
```python
_pipeline_store: dict = {}
_store_lock = threading.Lock()

def _store_update(pipeline_id: str, **kwargs):
    with _store_lock:           # only one thread enters at a time
        if pipeline_id not in _pipeline_store:
            _pipeline_store[pipeline_id] = {}
        _pipeline_store[pipeline_id].update(kwargs)
        _pipeline_store[pipeline_id]["last_updated"] = _now()
```

The lock is held only during the dict update — a microsecond operation.
Pipeline execution (30–90 seconds) happens outside the lock, so pipelines
can run fully in parallel; only the state writes are serialised.

### Why It Matters
Concurrency bugs are among the hardest to reproduce (they're timing-dependent).
Recognising where shared mutable state lives and protecting it is production-level thinking.

### Red Flags
- "Python's GIL prevents race conditions" — **incorrect**. The GIL prevents
  C-level bytecode interleaving but does NOT make compound operations (read-modify-write) atomic
- Suggests Redis as the answer without first showing the lock solution
- Uses a `threading.RLock` (re-entrant) without a reason — adds complexity for no gain here

---

## Q2 — The API uses FastAPI's `BackgroundTasks`. What's the difference between that and `asyncio` tasks?

### The Question to Ask
*"Pipelines run via `background_tasks.add_task(...)`. Could you use `asyncio.create_task()` instead?"*

### Strong Answer
```
FastAPI BackgroundTasks    vs    asyncio.create_task()
──────────────────────────────────────────────────────────
Runs in a thread pool            Runs in the event loop
(anyio thread pool)              (same thread as FastAPI)

Suitable for BLOCKING code       Suitable for ASYNC code
e.g. run_pipeline() blocks for   e.g. HTTP calls, DB queries
30-90s calling LLM, CrewAI, MCP  

Does NOT block event loop        Blocks event loop if awaited
FastAPI keeps serving requests   FastAPI freezes if task is CPU-bound
```

`run_pipeline()` calls LangGraph nodes which call MCP subprocess I/O and LLM HTTP
requests — these are blocking operations in a synchronous function.
`asyncio.create_task()` would block FastAPI's event loop for 30–90 seconds.

`BackgroundTasks.add_task()` moves the work to a thread pool — the event loop
remains free to serve hundreds of other requests while the pipeline runs.

```python
@app.post("/api/v1/pipeline/run")
async def run_pipeline_endpoint(body: RunPipelineRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_pipeline_task, pipeline_id, sku_id, store_id)
    return PipelineRunResponse(pipeline_id=pipeline_id, status="STARTED")
    # returns in ~1ms — pipeline runs asynchronously in thread pool
```

### Why It Matters
Misusing `asyncio.create_task()` for CPU-bound or blocking work is a common FastAPI
antipattern. The event loop starvation it causes is subtle and hard to diagnose under load.

### Red Flags
- Thinks `BackgroundTasks` uses the asyncio event loop (it uses a thread pool)
- Would use `asyncio.create_task()` without acknowledging the blocking code issue
- Can't explain what "event loop starvation" means

---

## Q3 — What happens if the pipeline background task raises an unhandled exception?

### The Question to Ask
*"Inside `_run_pipeline_task`, an LLM call raises a `ConnectionError`. What does the user see?"*

### Strong Answer
```python
def _run_pipeline_task(pipeline_id, sku_id, store_id):
    try:
        _store_update(pipeline_id, status=PipelineStatus.RUNNING)
        final_state = run_pipeline(sku_id=sku_id, store_id=store_id)
        # ... update store with final status
    except Exception as e:
        logger.error(f"Background task failed | {pipeline_id} | {e}", exc_info=True)
        _store_update(pipeline_id, status=PipelineStatus.FAILED, error=str(e))
```

Flow on exception:
```
LLM raises ConnectionError
    │
    └── propagates up through run_pipeline()
        └── propagates up through _run_pipeline_task()
            │
            ├── logger.error(..., exc_info=True) → full stack trace to server logs
            │                                      (visible to ops team, NEVER to client)
            │
            └── _store_update(pipeline_id, status=FAILED, error="Connection refused")
                    │
                    └── Next time Streamlit polls /state:
                        → status: "FAILED"
                        → error: "Connection refused"
                        → User sees: "Pipeline failed. Please retry."
```

Two properties:
1. **The API process never crashes** — exception is caught before it reaches FastAPI's
   thread pool management. Other pipelines continue unaffected.
2. **Full debug info is logged, minimal info shown to client** — security best practice.

### Why It Matters
Exception isolation in background tasks is crucial. Without `try/except`, a network
error in one pipeline could kill the worker thread — subsequent pipelines would
never start (thread pool exhaustion).

### Red Flags
- "The user gets a 500 error" — background task exceptions don't surface as HTTP errors
- Doesn't mention `exc_info=True` — the stack trace in server logs is critical for debugging
- Thinks `error=str(e)` should include the full traceback — information leakage risk

---

## Q4 — Why does the SqliteSaver use `check_same_thread=False`?

### The Question to Ask
*"In `build_graph()`, the SQLite checkpoint connection is opened with `check_same_thread=False`. Why? What risk does this create?"*

### Strong Answer
```python
_checkpoint_conn = sqlite3.connect(str(_CHECKPOINT_DB), check_same_thread=False)
checkpointer = SqliteSaver(_checkpoint_conn)
```

**Why it's needed:**
FastAPI serves requests from a thread pool. When two pipelines run concurrently:
- Pipeline A's background thread calls `SqliteSaver.put()` to save a checkpoint
- Pipeline B's background thread also calls `SqliteSaver.put()`

SQLite's Python driver, by default, checks that every DB call comes from the
thread that opened the connection (`check_same_thread=True`). Without `False`,
the second pipeline would raise: `ProgrammingError: SQLite objects created in a thread
can only be used in that same thread.`

**The risk:**
`check_same_thread=False` shifts the thread-safety responsibility to the application.
SQLite's write lock (WAL mode or exclusive lock) still prevents actual corruption —
only one writer at a time. The flag just allows multiple threads to **attempt** access.

**Production concern:**
If the Render deployment switches to multiple Uvicorn workers (not just threads),
SQLite file locking becomes a bottleneck — multiple processes contend for the same file.
This is one reason SQLite would need to be replaced with `PostgresSaver` at scale.

### Why It Matters
This is a subtle but real production issue. Knowing why the flag is needed AND its
limits shows architectural depth.

### Red Flags
- "It's fine, SQLite handles concurrency" — SQLite's locking is for single-writer safety,
  not multi-process production load
- Doesn't know what `check_same_thread` does — reveals shallow SQLite knowledge
- Can't connect this to the HITL resume path (resume comes from a different request thread)

---

## Q5 — How does the health endpoint detect partial system degradation vs total failure?

### The Question to Ask
*"A monitoring system calls `GET /health` every 30 seconds. What does it return when RAG is down but everything else is up?"*

### Strong Answer
```python
@app.get("/health", response_model=HealthResponse)
async def health():
    rag_ok = _retriever is not None and _retriever.is_available()

    try:
        alerts = get_critical_alerts()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return HealthResponse(
        status  = "ok" if db_status == "connected" else "degraded",
        db      = db_status,
        rag     = "available" if rag_ok else "unavailable (Windows path conflict — resolves on GCP)",
        llm     = f"{get_provider_name()}/{get_model_name()}",
        mcp     = "ready",
        version = "3.0.0-sprint3",
    )
```

Scenarios:
```
All up:          status="ok",       rag="available",    db="connected"
RAG down only:   status="ok",       rag="unavailable",  db="connected"
                 ↑ Not "degraded" — RAG is a fallback, not critical for the API
DB down:         status="degraded", rag=depends,        db="error: ..."
Both down:       status="degraded", rag="unavailable",  db="error: ..."
```

The status is `"ok"` even when RAG is unavailable because RAG has a fallback
(LLM knowledge). Only DB failure marks the system degraded — DB is required
for alerts and pipelines.

A load balancer would route to this endpoint and take the instance out of
rotation only if `status != "ok"`.

### Why It Matters
Health checks are the first signal operations teams act on. A health endpoint
that returns 200 for everything, or 500 for any minor degradation, is useless.
Understanding partial-failure semantics is ops-level thinking.

### Red Flags
- Returns 500 when RAG is unavailable (over-aggressive — disrupts the service unnecessarily)
- Returns 200 with no detail when DB is down (under-aggressive — ops can't diagnose)
- Doesn't know that `db_status = f"error: {e}"` would leak stack trace (it doesn't — only the string)

---

## Q6 — How does the API handle a request for a pipeline that doesn't exist?

### The Question to Ask
*"A user calls `GET /pipeline/FAKE_ID/state`. What does the API return?"*

### Strong Answer
Two-stage lookup:

```python
async def get_pipeline_state_endpoint(pipeline_id: str):
    # Stage 1: check in-memory store
    store_entry = _pipeline_store.get(pipeline_id)
    if not store_entry:
        # Stage 2: try loading from LangGraph checkpoint
        # (for pipelines that exist but whose API was restarted)
        try:
            raw_state = get_pipeline_state(pipeline_id)
            if raw_state:
                return _build_state_response(pipeline_id, raw_state)
        except Exception:
            pass
        # Neither store nor checkpoint — pipeline doesn't exist
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline {pipeline_id} not found."
        )
```

For `FAKE_ID`:
- Not in `_pipeline_store` (dict lookup: None)
- Not in LangGraph checkpoint store (thread_id not found)
- Returns: `HTTP 404` with `{"error": "Pipeline FAKE_ID not found.", "path": "/api/v1/pipeline/FAKE_ID/state"}`

The two-stage lookup is important for **server restart resilience** — a real pipeline
paused before the restart won't be in `_pipeline_store` but will be in the checkpoint.
FAKE_ID fails both stages → 404.

### Why It Matters
404 vs 200-with-empty-body is a correctness question. Streamlit uses the status code
to decide whether to show "loading" (polling 404) or an error state.

### Red Flags
- Returns 200 with empty body for missing pipelines (Streamlit would spin forever)
- Throws 500 (would suggest a server bug, not a client error)
- Doesn't mention the checkpoint fallback — would break HITL resume after restart

---

## Q7 — Why does the API validate the SKU exists in the database BEFORE launching the pipeline?

### The Question to Ask
*"In `run_pipeline_endpoint`, the first thing it does is `get_sku_details(body.sku_id)`. Why check before launching?"*

### Strong Answer
```python
@app.post("/api/v1/pipeline/run", status_code=202)
async def run_pipeline_endpoint(body: RunPipelineRequest, background_tasks: BackgroundTasks):
    # Validate SKU BEFORE launching expensive background task
    sku = get_sku_details(body.sku_id)
    if sku is None:
        raise HTTPException(
            status_code=422,
            detail=f"SKU '{body.sku_id}' not found in inventory database."
        )

    pipeline_id = f"PIPE_{body.sku_id}_{date.today()}"
    # ... launch background task
```

If the SKU validation was skipped:
1. Background task launches (returns 202 to client)
2. Agent 1 calls MCP: `check_inventory_positions(sku_id="NONEXISTENT")`
3. MCP returns empty result
4. Pipeline runs with empty data, produces garbage output or crashes
5. User polls `/state` for 90 seconds, sees `status: FAILED`
6. Error message is generic ("NoneType has no attribute...") — unhelpful

With pre-validation:
1. Returns `HTTP 422` immediately (~5ms)
2. Error message is specific: "SKU 'NONEXISTENT' not found"
3. No background thread wasted, no pipeline_store entry created

**Principle:** Validate at system boundaries, fail fast with actionable errors.

### Why It Matters
Early validation is a fundamental API design principle. Failing after 90 seconds
of background computation with a confusing error is a production anti-pattern.

### Red Flags
- "Validate inside the background task" — violates fail-fast principle
- Would return 404 instead of 422 (404 = resource not found, 422 = validation failed)
- No mention of the cost savings — validating early prevents expensive wasted computation

---

## Q8 — What does the CORS middleware do and what breaks without it?

### The Question to Ask
*"CORS middleware is configured with specific origins. What happens if Streamlit's origin isn't listed?"*

### Strong Answer
CORS (Cross-Origin Resource Sharing) is a browser security rule:
```
Origin A (localhost:8501 — Streamlit)  calls  Origin B (localhost:8080 — FastAPI)
Different port = different origin = blocked by browser by default
```

Without CORS configured:
1. Streamlit's browser sends a `POST /api/v1/pipeline/run` request to FastAPI
2. Browser first sends an OPTIONS "preflight" request: "Do you trust origin 8501?"
3. FastAPI responds with no CORS headers
4. Browser blocks the request → **Streamlit shows a network error**
5. The user never sees the API response — even if FastAPI processed the request correctly

ORCA's configuration:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", ...],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`localhost` and `127.0.0.1` are the same machine but different origins in the browser —
both must be explicitly listed.

### Why It Matters
CORS failures are silent from the server's perspective (the request reaches FastAPI,
FastAPI processes it, but the browser discards the response). Diagnosing them requires
opening the browser's network inspector — easy if you know CORS, mysterious if not.

### Red Flags
- "CORS is a server error" — CORS is a browser security policy, server enforcement is optional
- "Allow all origins (`*`) is fine" — `allow_credentials=True` + `allow_origins=["*"]` is actually
  rejected by browsers (security restriction)
- Can't explain the difference between preflight OPTIONS and the actual request

---

## Q9 — How does the pipeline deduplication prevent double-ordering the same SKU?

### The Question to Ask
*"Two supply planners try to run a pipeline for SKU00090 at the same time. How does the system prevent two orders being placed?"*

### Strong Answer
Two layers:

**Layer 1 — Deterministic pipeline ID:**
```python
pipeline_id = f"PIPE_{body.sku_id}_{date.today().strftime('%Y-%m-%d')}"
# Result: "PIPE_SKU00090_2026-06-04"
# Same SKU + same day = same ID — always
```

**Layer 2 — 409 check before launching:**
```python
existing = _pipeline_store.get(pipeline_id, {})
if existing.get("status") == PipelineStatus.RUNNING:
    raise HTTPException(
        status_code=409,
        detail=f"Pipeline {pipeline_id} is already running. Poll /state for updates."
    )
```

```
User A clicks Analyse (SKU00090)  → pipeline_id = "PIPE_SKU00090_2026-06-04"
                                  → not in store → 202 Accepted, pipeline starts

User B clicks Analyse (SKU00090)  → pipeline_id = "PIPE_SKU00090_2026-06-04"
                                  → IN store, status=RUNNING → 409 Conflict

User C clicks Analyse (SKU00091)  → pipeline_id = "PIPE_SKU00091_2026-06-04"
                                  → different SKU → 202 Accepted
```

The date scoping (`_2026-06-04`) also means the same SKU can be run the next day —
one pipeline per SKU per day is the intended operation.

### Why It Matters
Duplicate orders for a high-value SKU are a financial error, not just a UX annoyance.
Date-scoped IDs as deduplication keys are an elegant pattern.

### Red Flags
- Relies only on frontend disabling the button — backend must enforce it too
- Uses a database unique constraint instead of the ID-based check — adds a DB write per request
- Doesn't understand why the date is part of the ID (same SKU legitimately re-runs next day)

---

## Q10 — How does ORCA handle the case where the Groq API is rate-limited?

### The Question to Ask
*"Groq has a rate limit on the free tier. What happens when the LLM call is rejected with a 429?"*

### Strong Answer
**Current state:** ORCA has no automatic retry on LLM calls. A 429 from Groq
propagates as an exception through the agent node, up to `_run_pipeline_task`'s
`except Exception` handler, and the pipeline status is marked `FAILED`.

This is a **known gap** (no retry logic — known issue from CLAUDE.md):
```
No retry on LLM failure (pipeline fails, user must retry manually)
```

**What a production system would add:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def _call_llm_with_retry(llm, messages):
    return llm.invoke(messages)
```

**Why Groq specifically:**
Free tier: ~6000 tokens/minute per model. ORCA's average pipeline consumes ~4000 tokens
(4 LLM calls × ~1000 tokens each). Burst usage (multiple concurrent pipelines) easily
hits the limit.

**Mitigation at Groq level:**
`llama-3.1-8b-instant` has a higher rate limit than `llama-3.3-70b-versatile`.
The `.env` allows switching: `GROQ_MODEL=llama-3.1-8b-instant`.

### Why It Matters
Rate limiting is a reality of every LLM-backed system. A candidate who knows the gap
AND the fix (tenacity with exponential backoff) demonstrates production experience.

### Red Flags
- "The system retries automatically" — it doesn't (this is a known gap)
- "Just increase the limit" — free tier doesn't allow this; need a design solution
- Unaware of `tenacity` — the Python library that handles this pattern

---

## Q11 — What is the difference between the in-memory pipeline store and the checkpoint store?

### The Question to Ask
*"There are two places state is persisted: `_pipeline_store` (in-memory) and `checkpoints.db` (SQLite). What does each hold and when is each used?"*

### Strong Answer
```
_pipeline_store (Python dict in memory)
───────────────────────────────────────
Contains: pipeline metadata (started_at, status, sku_id, raw_state, reviewer)
Scope:    API process lifetime only — LOST on server restart
Thread safety: protected by threading.Lock
Purpose: fast state access for the /state polling endpoint
Access: direct dict lookup, ~1μs

db/checkpoints.db (SqliteSaver)
──────────────────────────────────────
Contains: full LangGraph graph state (AgentState fields) after each node
Scope:    persists across server restarts
Thread safety: SQLite file locking + check_same_thread=False
Purpose: HITL resume — allow paused pipeline to survive restart
Access: SqliteSaver query on thread_id, ~1ms

HOW THEY WORK TOGETHER:
────────────────────────
GET /state (during run):
  1. Check _pipeline_store → if RUNNING, pull live state from checkpoint
  2. If not in store (post-restart), load from checkpoint directly

POST /approve:
  1. resume_pipeline() loads from checkpoint via _app.invoke(None, config)
  2. After completion, updates _pipeline_store

Server restarts:
  _pipeline_store: wiped → empty
  checkpoints.db:  survives → paused pipelines can resume
```

### Why It Matters
Two-layer state management is a pattern that appears in many production systems.
Understanding the scope and purpose of each layer prevents debugging confusion
when one layer has stale data.

### Red Flags
- Thinks they're redundant — they serve different purposes (speed vs persistence)
- Doesn't know _pipeline_store is lost on restart (missed the HITL restart scenario)
- Confuses checkpoint store (per-node state during execution) with pipeline_log (audit trail)

---

## Q12 — How does the dashboard's 3-second polling interact with the pipeline running in a background thread?

### The Question to Ask
*"The dashboard sends GET /state every 3 seconds. The pipeline runs for 60 seconds in a background thread. What does the dashboard show during those 60 seconds?"*

### Strong Answer
```
t=0s:  POST /run → pipeline starts → {status: STARTED} returned
t=3s:  GET /state → _pipeline_store[id].status = RUNNING → demand_summary: None
t=6s:  GET /state → still RUNNING → demand_summary: None
t=15s: Agent 1 completes → _store_update(pipeline_id, raw_state=state)
t=18s: GET /state → live_state = get_pipeline_state(id) → demand_summary: {...}
       Streamlit shows: "Agent 1 complete — HIGH urgency"
t=30s: Agent 2 completes → _store_update(...)
t=33s: GET /state → options_package: {...}
       Streamlit shows: "Agent 2 — 3 options built"
t=45s: Agent 3 completes → route = ESCALATE
t=48s: GET /state → capital_decision: {...}, status: ESCALATED
       Streamlit shows: "Approval Required" → Approve/Reject buttons appear
```

The key mechanism: for RUNNING pipelines, `/state` also calls
`get_pipeline_state(id)` which reads the **live checkpoint** — more up-to-date
than the snapshot in `_pipeline_store`.

### Why It Matters
Progressive state delivery (None → partial → complete) is what enables the
live progress UI. Understanding the interplay between polling and background
state updates shows full-stack AI systems thinking.

### Red Flags
- Thinks the dashboard only gets the final state (misses progressive rendering)
- Doesn't know the /state endpoint reads from both store and checkpoint
- Can't explain the 1.5-second average latency (3-second poll interval ÷ 2)

---

## Q13 — What is the lifespan context manager in FastAPI and what does it run at startup?

### The Question to Ask
*"ORCA uses `@asynccontextmanager async def lifespan(app)`. What runs at startup vs shutdown, and why use a context manager instead of a startup event?"*

### Strong Answer
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP block (runs before first request):
    create_pipeline_table()         # ensures pipeline_log table exists
    logger.info(f"RAG: {rag_status}")
    logger.info(f"LLM: {get_provider_name()}/{get_model_name()}")

    yield  # APP RUNS HERE (all requests served)

    # SHUTDOWN block (runs after last request, before process exits):
    logger.info("ORCA API shutting down...")
```

Why context manager vs `@app.on_event("startup")`:
- Context manager (`lifespan`) is the **modern FastAPI approach** (v0.95+). The older
  `@app.on_event` is deprecated.
- `yield` makes startup/shutdown symmetrical and co-located — easier to read.
- The context manager pattern is familiar to Python developers (like `with` statements).
- `yield` allows clean pairing: resource acquired before `yield`, released after.

What `create_pipeline_table()` does:
```sql
CREATE TABLE IF NOT EXISTS pipeline_log (
    pipeline_id TEXT PRIMARY KEY,
    sku_id TEXT, store_id TEXT,
    final_status TEXT, demand_summary TEXT,
    ...
)
```
Running this on startup (not on first write) ensures the table always exists —
even on a fresh deployment with an empty database.

### Why It Matters
FastAPI lifespan is the standard pattern for initialising resources (DB connections,
model loads, caches) that outlive individual requests. Knowing it's replaced `on_event`
shows current FastAPI knowledge.

### Red Flags
- Describes `@app.on_event("startup")` — correct conceptually, but deprecated in FastAPI 0.95+
- "Just put startup code at module level" — runs at import time, hard to test and debug
- Can't explain what happens between `yield` and the shutdown block

---

## Q14 — How does Pydantic validation at the API boundary protect the pipeline from bad inputs?

### The Question to Ask
*"If the Streamlit dashboard sends a malformed JSON body to `POST /pipeline/run`, what happens before any pipeline code runs?"*

### Strong Answer
FastAPI + Pydantic validates every request body against the declared model:

```python
class RunPipelineRequest(BaseModel):
    sku_id:   str = Field(..., description="SKU identifier", min_length=1)
    store_id: str = Field(..., description="Store identifier", min_length=1)
```

If the request body is missing `sku_id`:
```
POST /api/v1/pipeline/run
{"store_id": "STR0077"}  ← missing sku_id

→ FastAPI parses body with Pydantic
→ Pydantic raises ValidationError: "sku_id is required"
→ FastAPI auto-converts to HTTP 422 Unprocessable Entity:
{
    "detail": [
        {
            "loc": ["body", "sku_id"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
```

The pipeline code (`_run_pipeline_task`) is **never called**.
The validation happens at the framework level before your code runs.

This is the "validate at system boundaries" principle. The internal pipeline
code (agents, MCP calls, DB queries) can trust its inputs — it never needs to
check if `sku_id` is None because Pydantic guaranteed it isn't.

### Why It Matters
Boundary validation is one of the most important API design principles. It prevents
defensive code from proliferating inside business logic — which would obscure the
actual logic and make testing harder.

### Red Flags
- Would put `if not sku_id: return error` inside the pipeline code (missing the boundary principle)
- Unaware that FastAPI auto-converts `ValidationError` to 422
- Thinks Pydantic only validates output (response_model), not input

---

## Q15 — What is the deployment strategy for ORCA and what are the limits of Render free tier?

### The Question to Ask
*"ORCA is deployed on Render free tier. What are the constraints and what would need to change to support 10x more users?"*

### Strong Answer
Current Render free tier constraints:
```
Memory limit:   512 MB → requires requirements.api.txt (no torch, no sentence-transformers)
CPU:            Shared, throttled → cold starts take 30-60s after inactivity
Single worker:  1 Uvicorn worker → SQLite + in-memory store work fine
Sleep after 15 min inactivity → first request after sleep hits cold start
Storage:        Ephemeral disk → ChromaDB doesn't persist (RAG unavailable on Render)
```

What's missing for production scale:
```
Current                    10x Users
──────────────             ────────────────────────────
Single worker          →   Multiple workers + load balancer
_pipeline_store (RAM)  →   Redis (shared across workers)
SQLite checkpoints     →   PostgresSaver
SQLite main DB         →   PostgreSQL
Groq free tier         →   Dedicated LLM endpoint / paid plan
Render free tier       →   Render paid or GCP Cloud Run
No retry logic         →   Tenacity + exponential backoff
```

The RAG unavailability on Render is a separate issue:
ChromaDB + BGE reranker need ~1.5 GB and `C:/lit` path fix — these can't run
on a 512 MB container. The CLAUDE.md notes `"resolves on GCP"`.

### Why It Matters
Understanding deployment constraints shows real-world experience. "Just deploy to
production" is not an answer — every deployment decision has a resource constraint behind it.

### Red Flags
- "Add more Render workers" — multiple workers on free tier share the same 512 MB, doesn't help
- Doesn't mention the `requirements.api.txt` split as the key to staying under 512 MB
- Unaware that SQLite breaks under concurrent writes from multiple workers

---

## Q16 — How does ORCA log observable information without exposing it to the client?

### The Question to Ask
*"The pipeline produces detailed logs. How does the system ensure detailed debugging information reaches the ops team but NOT the API client?"*

### Strong Answer
Three-layer logging / error exposure model:

**Layer 1 — Structured server logs (ops team sees everything):**
```python
logger.info(f"Agent 1 data fetched | critical={n} at_risk={n} events={n}")
logger.error(f"Background task failed | {pipeline_id} | {e}", exc_info=True)
# exc_info=True includes full stack trace — visible in server logs
```

**Layer 2 — Client gets minimal context (safe to expose):**
```python
# HTTPException: controlled message, no stack trace
raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found.")

# Generic exception handler: vague message, only exc string (no trace)
return JSONResponse(status_code=500, content=ErrorResponse(
    error="Internal server error",
    detail=str(exc),      # "Connection refused" — not a stack trace
    path=str(request.url.path),
))
```

**Layer 3 — Audit log (immutable record, readable by finance/compliance):**
```python
save_pipeline_run(
    pipeline_id  = state["pipeline_id"],
    final_status = state.get("final_status"),
    reviewed_by  = body.reviewer,  # who approved
    reviewed_at  = reviewed_at,    # when they approved
)
```

Each layer has a different audience: developers (server logs), users (HTTP response),
auditors (pipeline_log). These should never be mixed.

### Why It Matters
Information leakage through error messages is a real security vulnerability
(OWASP A05 — Security Misconfiguration). Stack traces in HTTP responses reveal
file paths, library versions, and DB schemas.

### Red Flags
- Would include the full exception trace in the API response "for debugging"
- Uses `exc_info=True` in the HTTP response handler (should only go to server logs)
- No audit log — compliance requirement for financial decisions

---

## Scoring Guide for Recruiters

| Score | What It Means |
|---|---|
| Knows threading model, exception isolation, deployment constraints | Strong hire — production engineering mindset |
| Correct on concurrency but shallow on deployment | Solid hire — needs production exposure |
| Talks about Docker/Kubernetes without specifics | Caution — may be DevOps-adjacent but not an engineer |
| "Just test it locally" | Red flag — no production awareness |

**Questions that most separate senior from mid-level engineers:**
- Q1 (threading.Lock — knows WHY GIL doesn't help)
- Q4 (SqliteSaver check_same_thread — nuanced concurrency)
- Q7 (fail-fast validation — API design principle)
- Q10 (rate limiting gap and tenacity — knows current state and the fix)
- Q16 (logging layers — security awareness)
