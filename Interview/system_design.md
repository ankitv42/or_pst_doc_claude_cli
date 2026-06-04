# ORCA — 20 System Design Interview Questions

> **Recruiter's guide.** Each question is followed by what a strong answer looks like,
> why it matters, and red flags to watch for. Diagrams use plain text so they render
> anywhere.

---

## Q1 — Why does the API return a response immediately instead of waiting for the AI to finish?

### The Question to Ask
*"When a user triggers the pipeline, the API responds in under a second. But the AI pipeline takes 30–90 seconds. How does that work?"*

### Strong Answer
The API uses an **async background task pattern** (202 Accepted). It hands the pipeline off to a background worker thread and returns a `pipeline_id` ticket immediately. The frontend then polls a `/state` endpoint every 3 seconds to check progress.

```
User clicks "Analyse"
        │
        ▼
  POST /pipeline/run
        │
        ├──► Returns {pipeline_id: "PIPE_SKU001_2026-06-04"}  ←── in ~1ms
        │
        └──► Background thread starts (runs 30-90s)
                   │
                   ▼
             Agent 1 → Agent 2 → Agent 3 → Route

Meanwhile, frontend polls every 3 seconds:
  GET /pipeline/PIPE_SKU001.../state
    → status: RUNNING  (after 5s)
    → status: RUNNING  (after 8s)
    → status: ESCALATED (after 45s) ← pipeline paused for human
```

### Why It Matters
If the API blocked for 90 seconds, the user's browser would freeze or time out. This pattern is standard for any operation that takes more than ~2 seconds.

### Red Flags
- Candidate says "just make it faster" without understanding the constraint
- No mention of polling or webhooks as the client-side complement
- Unaware that FastAPI's `BackgroundTasks` runs in a **thread pool**, not async event loop (important distinction for CPU-bound work)

---

## Q2 — How does the system "pause" and wait for a human to approve an order?

### The Question to Ask
*"When an expensive order needs approval, the system pauses. How does it hold that state while waiting — potentially for hours — for a human to click Approve?"*

### Strong Answer
The system uses LangGraph's **interrupt + checkpoint** mechanism:

```
                    PIPELINE RUNNING
                          │
          Agent 1 → Agent 2 → Agent 3
                          │
                    Route Node decides: ESCALATE
                          │
                    hitl_node writes briefing
                          │
                ┌─────────▼─────────┐
                │  SPEED BUMP fires │  ← interrupt_before=["execute_node"]
                │  Graph PAUSES     │
                │  State saved to   │
                │  db/checkpoints.db│
                └─────────┬─────────┘
                          │
                   ⏳ Waiting... (could be hours)
                          │
               Human clicks APPROVE on dashboard
                          │
                POST /pipeline/{id}/approve
                          │
                Graph RESUMES from checkpoint
                          │
                    execute_node runs
                          │
                 reorder_triggered = Yes → DB
```

The key is **SqliteSaver** — it serialises the entire pipeline state to disk. If the server restarts, the checkpoint survives and the pipeline can still be resumed.

### Why It Matters
This is the core differentiator of the system. Most AI pipelines are fire-and-forget. This one can be interrupted, reviewed, and either approved or rejected by a human. It's what makes it safe for high-value decisions.

### Red Flags
- Candidate describes polling loops or database flags instead of LangGraph's native interrupt
- No mention of checkpointing to disk — an in-memory pause breaks on server restart
- Can't explain what happens when the human clicks Reject (state is updated to SUSPEND before resume)

---

## Q3 — Why are there two separate requirements files?

### The Question to Ask
*"I noticed `requirements.txt` and `requirements.api.txt`. Why two? What's the risk of having just one?"*

### Strong Answer
The deployment platform (Render free tier) has a **512 MB memory limit**. The full `requirements.txt` includes:
- `torch` (~700 MB alone)
- `sentence-transformers`
- `streamlit`

None of these are needed by the API server — only by the dashboard and the RAG pipeline locally. So `requirements.api.txt` is a slim install that keeps the deployed API image under 512 MB.

```
requirements.txt          requirements.api.txt
─────────────────         ──────────────────────
torch (700MB)             fastapi
sentence-transformers     uvicorn
streamlit                 langraph
chromadb                  crewai
...everything...          groq
                          sqlalchemy
                          ...just what API needs...

Full local dev            Render deployment
~3 GB                     ~300 MB
```

### Why It Matters
A common mistake is to ship the full dev environment to production. This costs money, slows deployments, and can breach platform limits. The candidate understands the separation of concerns between dev and prod.

### Red Flags
- "I'd just use one file, it's simpler" — misses the deployment constraint
- Unaware that adding torch to requirements.api.txt would break the Render deployment
- No mention of Docker layer caching benefits from a leaner image

---

## Q4 — How do the AI agents share information with each other?

### The Question to Ask
*"There are 4 agents in the pipeline. Agent 3 needs to know what Agent 1 concluded. How does that information travel between them?"*

### Strong Answer
All agents share a single **AgentState object** — a typed Python dictionary that flows through the entire pipeline. Each agent reads from it and writes only its own output back.

```
                    AgentState (shared memory)
                    ──────────────────────────
                    sku_id:           "SKU00090"
                    store_id:         "STR0077"
                    pipeline_id:      "PIPE_SKU..."
                    demand_summary:   None  ──────────── Agent 1 fills this
                    options_package:  None  ──────────── Agent 2 fills this
                    capital_decision: None  ──────────── Agent 3 fills this
                    hitl_briefing:    None  ──────────── Agent 4 fills this
                    route:            None  ──────────── Route Node fills this
                    final_status:     None

Agent 1 runs → writes demand_summary
                     ↓
Agent 2 runs → reads demand_summary, writes options_package
                     ↓
Agent 3 runs → reads demand_summary + options_package, writes capital_decision
                     ↓
Route node → reads capital_decision, writes route
```

The state is **append-only** — each agent only fills its own field, never overwrites another agent's output.

### Why It Matters
This is the LangGraph pattern. Understanding it shows the candidate knows how multi-agent state machines work vs. simple function chaining.

### Red Flags
- Thinks agents call each other directly (they don't — LangGraph orchestrates)
- Can't name what each agent reads vs. writes
- Confuses AgentState with a database — it's in-memory, not persisted (the pipeline log is separate)

---

## Q5 — What is MCP and why use it instead of just importing functions directly?

### The Question to Ask
*"The system uses something called MCP to call database tools. Why not just call the database directly from inside the agent code?"*

### Strong Answer
MCP (Model Context Protocol) is a protocol that lets agents **discover tools at runtime** instead of having them hardcoded. The MCP server runs as a separate subprocess, and agents ask it "what tools do you have?" each time they need to act.

```
WITHOUT MCP (hardcoded):                WITH MCP (dynamic):
─────────────────────────               ──────────────────────────────
# graph.py                              # graph.py
from db.queries import (                tools = await _get_mcp_tools()
    get_sku_details,                    # Returns: [check_inventory,
    get_supplier_info,                  #           get_sku_info,
    get_sales_velocity,                 #           get_supplier_info,
    ...                                 #           ...]
)
                                        # Adding new tool = add to server.py
# Adding new tool = edit graph.py       # graph.py needs ZERO changes
```

The benefit: **adding a new tool to `mcp_server/server.py` makes it instantly available to all agents** without touching the pipeline code.

### Why It Matters
This shows awareness of decoupling and extensibility — a Fortune 100 production pattern. The candidate isn't just writing code that works; they're writing code that's maintainable.

### Red Flags
- "It's overengineering for a small project" — misses the architectural point
- Can't explain that MCP runs as a **stdio subprocess** (not HTTP), so no port needed
- Unaware that tools are async-only via MCP adapters (requires `ainvoke`, not `invoke`)

---

## Q6 — How does the system handle an AI agent returning broken or invalid JSON?

### The Question to Ask
*"The agents output structured JSON. What happens if the LLM returns malformed JSON — say it includes a formula like '100*2' instead of the number 200?"*

### Strong Answer
The system has a two-stage recovery in `_parse_json()`:

```
LLM returns response text
         │
         ▼
Step 1: Strip markdown fences
  (LLM sometimes wraps output in ```json ... ```)
         │
         ▼
Step 2: Try json.loads()
         │
    ┌────┴────┐
   OK        FAIL
    │         │
    ▼         ▼
  Return   Send broken JSON BACK to LLM:
  parsed   "Fix this JSON — compute all formulas,
  dict     return only valid JSON"
                │
                ▼
           Try json.loads() again
                │
           ┌────┴────┐
          OK        FAIL
           │         │
           ▼         ▼
         Return    Raise ValueError
         result    (pipeline fails gracefully)
```

This is called **LLM self-correction** — using the model's own capabilities to fix its own mistakes before failing.

### Why It Matters
In production AI systems, you cannot assume the LLM always returns perfectly formatted output. Graceful degradation prevents one bad response from crashing the entire pipeline.

### Red Flags
- No mention of stripping markdown code fences (a very common LLM quirk)
- Would just `try/except` and return None — loses information
- No awareness of the retry / self-correction pattern

---

## Q7 — The routing decision is "pure Python, no LLM". Why?

### The Question to Ask
*"The Route Node — which decides whether to auto-approve, escalate, or suspend — doesn't use AI at all. Why not let the LLM make that decision?"*

### Strong Answer
The routing rules are **deterministic business logic**:

```
if pool_pressure == "HIGH":
    route = "SUSPEND"
elif cost < auto_approve_limit:
    route = "AUTO_EXECUTE"
else:
    route = "ESCALATE"
```

These rules must be 100% predictable and auditable. An LLM might:
- "Round" a cost slightly and make the wrong call
- Interpret "HIGH pressure" differently based on context
- Hallucinate a justification for an incorrect route

For financial decisions, **correctness > flexibility**. Pure Python guarantees the same input always produces the same output.

### Why It Matters
This shows the candidate understands *when to use AI and when not to*. Overusing LLMs for tasks that should be deterministic is a common mistake.

### Red Flags
- "The LLM is smarter so it should decide" — misses auditability requirement
- Can't articulate the 3 routes and the condition for each
- Unaware that the pool pressure check requires an MCP call (live data, not static)

---

## Q8 — How does the system prevent two pipelines from running for the same SKU at the same time?

### The Question to Ask
*"What stops a user from clicking 'Analyse' on the same SKU twice and creating duplicate orders?"*

### Strong Answer
Two layers of protection:

**Layer 1 — Pipeline ID collision:**
```
pipeline_id = f"PIPE_{sku_id}_{today's date}"
# e.g. "PIPE_SKU00090_2026-06-04"
```
Same SKU, same day = same ID. The system only creates one pipeline per SKU per day.

**Layer 2 — API 409 check:**
```
if existing pipeline status == RUNNING:
    return HTTP 409 Conflict
    "Pipeline already running. Poll /state for updates."
```

```
User 1 clicks Analyse (SKU001)  →  Pipeline created: PIPE_SKU001_2026-06-04
User 2 clicks Analyse (SKU001)  →  409 Conflict: already running
User 3 clicks Analyse (SKU001)  →  409 Conflict: already running

User 1 clicks Analyse (SKU002)  →  Pipeline created: PIPE_SKU002_2026-06-04  ✓
```

### Why It Matters
Duplicate pipeline runs could result in double orders being placed. This is a data integrity concern, not just a UX one.

### Red Flags
- Relies only on frontend disabling the button — backend must enforce it too
- No awareness of the date-scoped ID as the primary deduplication key
- Would use a database lock without explaining the 409 response code

---

## Q9 — How does the RAG system retrieve the right policy documents for each agent?

### The Question to Ask
*"There are 5 policy documents in the system. How does Agent 3 — the Capital Allocation agent — know which parts of which document to read?"*

### Strong Answer
Each agent has its own **targeted query function** (`query_for_agent3`). Rather than a generic search, it fires 3 specific queries based on the actual state data:

```
Agent 3 calls query_for_agent3(
    category="Dates",
    urgency="HIGH",
    abc_class="A",
    approval_pool="CP001"
)

This fires 3 targeted queries:
  Q1: "pool CP001 rules and approval thresholds for Dates category"
  Q2: "scoring formula elimination rules urgency HIGH class A"
  Q3: [table search] "budget score availability score margin score"
              │
              ▼
    Hybrid retrieval:
    ┌─────────────────────────────┐
    │  BM25 (keyword match)       │──┐
    │  Vector search (meaning)    │──┤ RRF Fusion → Top chunks
    │  Metadata filter (doc_type) │──┘
    └─────────────────────────────┘
              │
              ▼
    BGE Reranker re-scores top chunks
              │
              ▼
    Formatted context string injected into Agent 3's prompt
```

### Why It Matters
Generic RAG (one query per agent) retrieves noise. Query construction from structured state data — called **metadata-aware targeted retrieval** — is a production RAG technique.

### Red Flags
- Thinks all agents use the same query function
- Unaware of hybrid search (BM25 + vector) — just "ChromaDB does similarity search"
- Can't explain what RRF fusion is (Reciprocal Rank Fusion — merges ranked lists from two retrieval methods)

---

## Q10 — Why does CrewAI run *inside* Agent 1 instead of replacing LangGraph?

### The Question to Ask
*"The system uses both LangGraph and CrewAI. These are both multi-agent frameworks. Isn't that redundant?"*

### Strong Answer
They solve different problems:

```
LangGraph = WORKFLOW ORCHESTRATOR
─────────────────────────────────
You define the exact sequence.
State is explicit and typed.
Supports interrupt/resume (HITL).
Perfect for: business pipelines where order,
             auditability, and HITL matter.

CrewAI = COLLABORATIVE REASONING
──────────────────────────────────
You define agent roles + goals.
Agents decide how to collaborate.
No explicit interrupt support.
Perfect for: open-ended analysis where
             multiple perspectives improve quality.

ORCA's design:
─────────────────────────────────────────────────
LangGraph manages the 4-agent business pipeline
                   │
          Agent 1 needs deep demand analysis
                   │
                   ▼
         CrewAI crew runs INSIDE agent1_node:
           Data Analyst → Market Analyst
                    ↘        ↙
               Forecast Strategist
                   │
                   ▼
         demand_summary returned to LangGraph
```

LangGraph gets the business guarantees. CrewAI gets the analytical depth.

### Why It Matters
The candidate demonstrates awareness of multiple AI frameworks and, more importantly, *when to use each one*. Using only one for everything would mean compromising either reliability or analytical quality.

### Red Flags
- "I would just pick one" — misses that they serve different purposes
- Unaware that CrewAI currently fails due to the `cache_breakpoint` Groq error and the system falls back to a single LLM call
- Thinks LangGraph and CrewAI are competitors (they're complementary)

---

## Q11 — How is thread safety handled in the in-memory pipeline store?

### The Question to Ask
*"Multiple pipeline runs can happen at the same time. The system stores pipeline state in a Python dictionary in memory. What prevents two background threads from corrupting each other's data?"*

### Strong Answer
The pipeline store uses a **threading.Lock**:

```python
_pipeline_store: dict = {}
_store_lock = threading.Lock()

def _store_update(pipeline_id, **kwargs):
    with _store_lock:          # ← Only one thread can enter at a time
        _pipeline_store[pipeline_id].update(kwargs)
```

```
Thread 1 (Pipeline A)      Thread 2 (Pipeline B)
──────────────────────     ──────────────────────
_store_update(A, ...)  →   BLOCKED (lock held by Thread 1)
  updates store A
  releases lock        ←   Thread 2 now acquires lock
                           _store_update(B, ...)
                           updates store B
                           releases lock
```

Without the lock, two threads could read, modify, and write the same dict entry simultaneously — a **race condition** — corrupting the data silently.

### Why It Matters
Concurrency bugs are among the hardest to reproduce and debug. Recognising where shared mutable state exists and protecting it is a sign of production-level thinking.

### Red Flags
- "Python's GIL prevents race conditions" — **incorrect**. The GIL doesn't make dict operations atomic at the application level
- No mention of the lock at all — relies on luck
- Suggests Redis as the fix (correct for scale-out, but misses the immediate answer)

---

## Q12 — What happens to a paused pipeline if the API server restarts?

### The Question to Ask
*"An order is waiting for human approval. The server crashes and restarts. What happens to the paused pipeline?"*

### Strong Answer
The pipeline **survives** because the checkpoint is stored on disk, not in memory:

```
Before crash:
  Pipeline "PIPE_SKU001_2026-06-04" paused at execute_node
  State serialised → db/checkpoints.db (SqliteSaver)
  in-memory _pipeline_store also has the entry

Server crashes
  _pipeline_store → LOST (in-memory)
  db/checkpoints.db → SURVIVES (disk)

Server restarts
  _pipeline_store is empty

Human clicks Approve
  POST /pipeline/PIPE_SKU001.../approve
       │
       ├── _pipeline_store.get(id) → None  ← not in memory
       └── But: resume_pipeline() loads checkpoint from checkpoints.db
                     │
                     ▼
               Graph resumes from exact pause point
               execute_node runs
               Order placed ✓
```

The GET `/state` endpoint also falls back to the graph checkpoint if the pipeline isn't in the in-memory store.

### Why It Matters
Any production system must handle restarts gracefully. An AI pipeline that loses state on restart is not production-grade.

### Red Flags
- Thinks MemorySaver is used (it was in an early version, now replaced by SqliteSaver)
- No awareness of the fallback in the `/state` endpoint that reads from the checkpoint
- "The human would just click Analyse again" — this would start a **new** pipeline, not resume the paused one

---

## Q13 — Why does the dashboard poll every 3 seconds instead of using WebSockets?

### The Question to Ask
*"The dashboard checks the pipeline status every 3 seconds. Why not use WebSockets, which would push updates to the dashboard the moment something changes?"*

### Strong Answer
Polling is a **deliberate tradeoff**:

```
WebSockets:                          Polling every 3s:
────────────────────────────         ──────────────────────────────
Server pushes instantly              Client asks "done yet?" every 3s
Lower latency                        ~1.5s average latency
Complex server infrastructure        Simple GET endpoint
Requires persistent connection       Stateless — works with load balancers
Connection management overhead       Reconnects automatically on failure
Hard to deploy on free tier          Works on Render free tier today
```

For a pipeline that takes 30–90 seconds, a 3-second polling interval gives sufficient UX (average 1.5s delay at completion) with much simpler infrastructure. WebSockets would add complexity for marginal benefit at this scale.

### Why It Matters
Good engineers choose the simplest solution that meets requirements, not the most technically impressive one. The candidate understands the deployment context (Render free tier, single instance).

### Red Flags
- "WebSockets are always better" — ignores deployment constraints
- Can't quantify the latency tradeoff (3s polling = max 3s, avg 1.5s delay)
- Doesn't mention that free-tier Render can't easily maintain persistent WebSocket connections

---

## Q14 — How does the system ensure Class A SKUs never get a partial distribution option?

### The Question to Ask
*"For Class A products (the most valuable SKUs), there's a rule: they can never be given the 'partial order' option. How is that enforced?"*

### Strong Answer
This rule is a **hard constraint** — enforced in the Agent 2 system prompt, not left to the LLM's judgement:

```
In agents/prompts.py (Agent 2 prompt):

"HARD RULE — Class A SKUs:
 Option B (partial distribution) is NEVER available for Class A SKUs.
 If abc_class = 'A', mark Option B as:
   feasible: false
   elimination_reason: 'Class A SKU — partial distribution not permitted'
 Do not offer it regardless of budget."
```

The scoring in Agent 3 then eliminates any option marked `feasible: false`.

```
SKU abc_class = "A"
        │
        ▼
Agent 2 builds options:
  Option A: Standard    → feasible: true
  Option B: Partial     → feasible: false  ← HARD RULE applied
  Option C: Expedite    → feasible: true

        │
        ▼
Agent 3 scoring:
  Option A: scored normally
  Option B: ELIMINATED (not scored — feasible=false)
  Option C: scored normally

Winner must be A or C — never B.
```

### Why It Matters
Business rules that must never be violated should be enforced in the prompt **and** in downstream code, not left to probabilistic AI reasoning. The candidate shows they understand the limits of LLM reliability for hard constraints.

### Red Flags
- "The LLM is smart enough to figure it out" — LLMs can and do ignore rules
- No defence-in-depth (what if Agent 2 ignores the rule? Agent 3 should catch it)
- Unaware of the `feasible` flag as the enforcement mechanism

---

## Q15 — How does the evaluation framework test an AI system without running the AI?

### The Question to Ask
*"Testing an AI pipeline is hard because the LLM is non-deterministic. How does ORCA's eval framework verify correctness without needing to run the LLM?"*

### Strong Answer
Layer 1 evals test the **retrieval layer**, not the LLM, making them deterministic and free:

```
What Layer 1 tests:
─────────────────────────────────────────────────────
Input:  query_for_agent3(category="Dates", urgency="HIGH", ...)
Output: a text string (the retrieved policy context)

Checks:
  must_contain:     ["auto_approve_limit", "CP001", "budget_score"]
                    → Did the right facts come back?
  must_not_contain: ["supplier contact", "event planning"]
                    → Did wrong document content leak in?

11 golden test cases × 2 checks each = 22 assertions
Target: ≥70% pass rate, ZERO leaks

No LLM called.
No API key needed.
Runs in CI on every push in ~30 seconds.
```

```
CI gate (GitHub Actions):
─────────────────────────────────
git push
    │
    ▼
.github/workflows/eval_gate.yaml
    │
    ▼
python evals/run_retrieval_eval.py --ci
    │
    ├── PASS (≥70%) → merge allowed
    └── FAIL (<70%) → merge blocked
```

### Why It Matters
The candidate has thought about testability from the ground up. Separating retrieval quality from LLM quality makes meaningful CI possible without an API key or LLM costs.

### Red Flags
- No awareness that the eval runs without an API key
- Thinks "you can't test AI" — misses the retrieval/decision separation
- Can't explain what a "leak" means (a document from the wrong policy appearing in the wrong agent's context)

---

## Q16 — How does the system handle the case where the LLM provider (Groq) is down?

### The Question to Ask
*"What happens to the pipeline if Groq — the external AI service — is unavailable or returns an error?"*

### Strong Answer
There are two layers of resilience:

**Layer 1 — CrewAI fallback in Agent 1:**
```
Agent 1 tries CrewAI crew (3 agents)
        │
    ┌───┴───┐
  Success  Exception (Groq error, timeout, etc.)
    │         │
    ▼         ▼
 demand_   Fallback: single LLM call
 summary   with simpler prompt
 from         │
 crew         ▼
           demand_summary from single LLM
```

**Layer 2 — Background task error handling:**
```
_run_pipeline_task() wraps the entire pipeline in try/except:

try:
    run the pipeline
except Exception as e:
    _store_update(pipeline_id,
        status = FAILED,
        error  = str(e)
    )
```

The API never crashes. The dashboard shows `status: FAILED` with an error message. The user can retry.

### Why It Matters
External dependencies fail. Any system calling a third-party API must handle failures gracefully. The pipeline failing should never bring down the API server.

### Red Flags
- No awareness of the CrewAI → single LLM fallback
- "It would just crash" — missing the background task error boundary
- No mention of retry logic (the system currently has no automatic retry — a valid follow-up gap to explore)

---

## Q17 — How does the system prevent the AI from fabricating supplier contact details?

### The Question to Ask
*"The HITL briefing tells the human planner which supplier to call — name, email. How does the system ensure this information is real and not made up by the AI?"*

### Strong Answer
Supplier contact details are **never given to the LLM as something to generate**. They are fetched from the database via MCP and injected into the prompt as facts:

```
WRONG approach (hallucination risk):
─────────────────────────────────────
Prompt: "Write a briefing for SKU00090.
         Include the supplier contact."
LLM: "Contact: Ahmed Al-Rashid, ahmed@fakecompany.com"
           ↑ HALLUCINATED

ORCA's approach (data-grounded):
─────────────────────────────────────────────
Step 1: MCP tool call → get_supplier_info(sku_id)
  Returns from database:
  {
    "supplier_name": "Gulf Foods LLC",
    "contact_name": "Khalid Hassan",
    "contact_email": "k.hassan@gulfoods.ae"
  }

Step 2: Inject into prompt as a FACT:
  "Supplier data (DO NOT CHANGE):
   Name: Gulf Foods LLC
   Contact: Khalid Hassan — k.hassan@gulfoods.ae"

Step 3: Prompt instructs LLM to USE this data, not generate it.
```

The same pattern applies to the recommended option's cost and pool — pre-extracted in Python and injected as `winner_summary` with "DO NOT CHANGE" labels.

### Why It Matters
Hallucinated contact details could cause the human planner to reach out to the wrong person — or no one at all. For any data that matters, ground the LLM in the source of truth.

### Red Flags
- Thinks the LLM "looks up" the supplier — it can't, it has no internet access
- No awareness of the prompt injection pattern for facts vs. generation
- Can't explain the `winner_summary` pre-extraction in `hitl_node`

---

## Q18 — The system uses SQLite. What are its limitations and when would you need to replace it?

### The Question to Ask
*"The database is SQLite — a file-based database. That seems simple for a production system. What are the trade-offs, and when would you need to upgrade?"*

### Strong Answer
SQLite is the right choice *now* given the deployment constraints:

```
SQLite is fine when:                 SQLite breaks when:
────────────────────────────────     ──────────────────────────────────
Single server (Render free tier)     Multiple API instances (scale-out)
Low concurrent writes                Many simultaneous pipeline runs
Simple deployment (just a file)      High write throughput needed
Free tier — no managed DB cost       Need full ACID across services
Team of 1 developer                  Team of 5+ writing concurrently

ORCA's current bottleneck: check_same_thread=False on the checkpoint
connection. It's safe for single-worker but would need revisiting with
multiple Uvicorn workers.
```

The upgrade path would be:
1. **PostgreSQL** for the main `orca.db` data (SKUs, stores, capital pools)
2. **Redis** for the in-memory `_pipeline_store` (already planned as Sprint 6)
3. **LangGraph's PostgresSaver** for the checkpoint store

### Why It Matters
Understanding the limits of a technology and the upgrade path shows engineering maturity. The candidate isn't gold-plating (using Postgres from day one) but also isn't naive about the constraints.

### Red Flags
- "SQLite is never production-grade" — oversimplified; it's appropriate here
- No awareness of the `check_same_thread=False` detail on the checkpoint connection
- Can't name the specific things that would break first (checkpoint store under concurrent load)

---

## Q19 — How is the AI pipeline's full execution history preserved for auditing?

### The Question to Ask
*"A supply planner approved a $50,000 order last Tuesday. Finance wants a complete audit trail — which agent recommended it, why, and who approved it. How does the system provide that?"*

### Strong Answer
Every completed pipeline run is persisted to the `pipeline_log` table in SQLite:

```
pipeline_log table
──────────────────────────────────────────────────────
pipeline_id         "PIPE_SKU00090_2026-06-04"
sku_id              "SKU00090"
store_id            "STR0077"
final_status        "EXECUTED_AFTER_APPROVAL"
demand_summary      { urgency: HIGH, shortfall: 2400, ... }  ← Agent 1 full output
options_package     { options: [A, B, C], recommended: C }    ← Agent 2 full output
capital_decision    { winner: C, score: 87.3, approval: true } ← Agent 3 full output
hitl_briefing       "APPROVED BY HUMAN: Option C ... "
reviewed_by         "priya.sharma@retailco.ae"
reviewed_at         "2026-06-04T14:32:11Z"
created_at          "2026-06-04T14:02:45Z"
```

The full reasoning of all three agents is stored as JSON blobs — not just the final decision. This means you can reconstruct exactly how the system arrived at its recommendation.

### Why It Matters
In regulated industries or high-stakes decisions, auditability is a legal requirement. Storing only the outcome ("order placed") is not enough — you need the full reasoning chain.

### Red Flags
- Thinks the checkpoint store is the audit log (it isn't — checkpoints expire and are implementation detail)
- Only stores final status, not agent reasoning
- No awareness of `reviewed_by` and `reviewed_at` fields (the human's identity is captured)

---

## Q20 — What would you change if this system had to scale from 1 store to 10,000 stores?

### The Question to Ask
*"Right now this system handles one store at a time. If a retailer with 10,000 stores wanted to deploy it, what would break and what would you redesign?"*

### Strong Answer
Several things would need to change:

```
Current Architecture          10,000 Store Architecture
─────────────────────         ──────────────────────────────────────
Single Uvicorn worker     →   Multiple workers + load balancer (Nginx/ECS)
In-memory pipeline store  →   Redis (shared across all workers)
SQLite checkpoint store   →   PostgresSaver (LangGraph checkpoint to Postgres)
SQLite main database      →   PostgreSQL with read replicas
One pipeline at a time    →   Message queue (SQS/RabbitMQ) for 1000s of alerts
Groq free tier LLM        →   Dedicated LLM endpoint with rate limit management
RAG on local disk         →   Hosted vector DB (Pinecone / Weaviate)
No retry on LLM failure   →   Tenacity retry with exponential backoff
```

The biggest architectural change:
```
Current:  Alert → API → Background thread → Pipeline
                  (synchronous, one server)

At scale: Alert → API → Message Queue → Worker pool
                        (async, distributed)
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                Worker 1  Worker 2  Worker N
                Pipeline  Pipeline  Pipeline
```

### Why It Matters
This is the classic "design for scale" question. The candidate should know both what they built and what they would need to change — and more importantly, *why* those things are bottlenecks.

### Red Flags
- "Just add more servers" — without addressing shared state (in-memory store) and SQLite concurrency
- Doesn't identify the message queue as the key architectural change for burst alert handling
- Can't explain why SQLite is a bottleneck under concurrent writes (file locking)
- Adds complexity that isn't needed ("we need Kubernetes") without justifying the threshold

---

## Scoring Guide for Recruiters

| Score | What It Means |
|---|---|
| Answers all 3 parts (what, why, tradeoffs) | Strong hire — production mindset |
| Answers what + why, misses tradeoffs | Solid hire — grows with experience |
| Answers what but not why | Proceed with caution — may be pattern-matching |
| Can't explain the system they built | Red flag — may not have written the code |

**Questions that most separate senior from junior candidates:**
- Q2 (HITL checkpoint mechanics)
- Q7 (why routing is pure Python)
- Q11 (thread safety)
- Q17 (preventing hallucination of facts)
- Q20 (scale tradeoffs)
