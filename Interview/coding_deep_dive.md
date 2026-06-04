# ORCA — 15 Coding & Implementation Deep-Dive Questions

> **Focus area.** Code-level questions about specific implementations in ORCA:
> Python async patterns, data structure choices, algorithmic decisions, and
> design patterns used. Google expects senior engineers to explain every line
> of code they've written.

---

## Q1 — Walk through exactly what `asyncio.run(coro)` does versus `loop.run_until_complete(coro)`.

### The Question to Ask
*"In `_run_async`, you call `asyncio.run()` and fall back to `loop.run_until_complete()`. What's the difference between these two functions?"*

### Strong Answer
```python
def _run_async(coro):
    try:
        return asyncio.run(coro)         # Path 1
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)  # Path 2
```

**`asyncio.run(coro)` (Python 3.7+, recommended):**
1. Creates a **new event loop** from scratch
2. Runs `coro` to completion on that loop
3. Closes the loop and cleans up (cancels pending tasks, closes connections)
4. Returns the result
- Fails with `RuntimeError: This event loop is already running` if called
  inside an already-running async context (FastAPI, Jupyter)

**`loop.run_until_complete(coro)` (older API):**
1. Gets the **current event loop** (already exists)
2. Runs `coro` to completion on that existing loop
3. Does NOT close the loop afterwards
- Would fail without `nest_asyncio` because nested event loop execution
  is not natively supported in CPython before nest_asyncio patches it

**Why `asyncio.run()` first:**
Python 3.10+ deprecated `asyncio.get_event_loop()` when no loop exists.
`asyncio.run()` is the clean modern API. The `except RuntimeError` path
handles the FastAPI/Jupyter case where a loop is already running.

### Why It Matters
This is the exact code path taken by every single MCP tool call in the pipeline.
Not being able to explain it means not understanding how the core infrastructure works.

### Red Flags
- Confuses `asyncio.run()` and `asyncio.create_task()` (very different operations)
- Thinks `asyncio.get_event_loop()` always returns a new loop (it returns existing or None)
- Unaware that Python 3.10 deprecated `get_event_loop()` in certain contexts

---

## Q2 — How does the `BM25Index` inverted index work? Explain the data structure.

### The Question to Ask
*"In `BM25Index.__init__`, you build `self.index: dict[str, dict[int, int]]`. What does that nested dict structure represent?"*

### Strong Answer
```python
self.index: dict[str, dict[int, int]] = {}

# After indexing 3 documents:
# doc 0: "Suppliers must submit invoices within 7 days"
# doc 1: "ABC supplier lead time is 14 days"
# doc 2: "Class A SKUs require emergency approval"

self.index = {
    "supplier": {0: 1, 1: 1},    # "supplier" in doc 0 (1 time), doc 1 (1 time)
    "days":     {0: 1, 1: 1},    # "days" in doc 0 and doc 1
    "class":    {2: 1},          # "class" only in doc 2
    "approval": {2: 1},          # "approval" only in doc 2
    "lead":     {1: 1},          # "lead" only in doc 1
    ...
}
```

This is an **inverted index** — the data structure used by every search engine.
Instead of document → words (forward index), it stores word → documents.

```
Forward index:   doc 0 → ["supplier", "must", "submit", ...]
Inverted index:  "supplier" → {doc 0: 1, doc 1: 1}
```

Why inverted? When you search for "supplier lead time", you:
1. Look up "supplier" in index → {0, 1}
2. Look up "lead" in index → {1}
3. Intersection/scoring: doc 1 has both terms → highest BM25 score

Without the inverted index, you'd scan ALL documents for each query word — O(n×m).
With the inverted index: lookup is O(k) where k = number of documents containing the word.

### Why It Matters
The inverted index is foundational to search (Lucene, Elasticsearch, Solr all use it).
Being able to explain it from the actual code in ORCA shows algorithmic depth.

### Red Flags
- Can't read the nested dict structure
- Doesn't know what an inverted index is (it's fundamental CS)
- Confuses the inverted index with a hash map (different structure and purpose)

---

## Q3 — Explain the `rrf_fuse` function line by line.

### The Question to Ask
*"Walk me through `rrf_fuse` in retriever.py. What does each line do and why?"*

### Strong Answer
```python
def rrf_fuse(
    vector_results: list[tuple[str, float]],   # [(chunk_id, score), ...]
    bm25_results:   list[tuple[str, float]],   # [(chunk_id, score), ...]
    k: int = 60,
) -> list[tuple[str, float]]:

    scores: dict[str, float] = {}

    # Process vector results:
    for rank, (doc_id, _) in enumerate(vector_results, 1):
        # rank starts at 1 (not 0) — the '_' discards the raw score
        # raw score is irrelevant — RRF uses only rank position
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
        # chunk at rank 1: 1/(60+1) = 0.01639
        # chunk at rank 2: 1/(60+2) = 0.01613
        # k=60 dampens the advantage of rank 1 vs rank 2

    # Process BM25 results (same formula):
    for rank, (doc_id, _) in enumerate(bm25_results, 1):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
        # If a chunk appeared in vector at rank 2 and BM25 at rank 1:
        # total = 1/(60+2) + 1/(60+1) = 0.01613 + 0.01639 = 0.03252

    # Sort by fused score descending:
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
    # Returns: [("chunk_B", 0.03252), ("chunk_A", 0.03202), ...]
```

**Why k=60?**
Mathematically: at k=60, rank 1 gets 1/61 ≈ 0.0164, rank 2 gets 1/62 ≈ 0.0161.
The gap is small — rank 1 is only 2% better than rank 2.
Lower k (e.g., k=10): 1/11 vs 1/12 = 8% gap — amplifies rank differences.
k=60 is the literature default for balanced merging across retrieval methods.

### Why It Matters
`rrf_fuse` is the heart of the hybrid retrieval system. Being able to explain it
proves code literacy, not just architectural knowledge.

### Red Flags
- Can't read the `enumerate(results, 1)` syntax (starts at 1)
- Doesn't know why the raw score is discarded with `_`
- Can't explain what k=60 achieves (dampens rank advantage)

---

## Q4 — How does Python's `TypedDict` work and why is it used for `AgentState`?

### The Question to Ask
*"Why is `AgentState` a `TypedDict` instead of a regular `dict` or a Pydantic model?"*

### Strong Answer
```python
from typing import TypedDict, Optional

class AgentState(TypedDict):
    sku_id:           str
    demand_summary:   Optional[dict]
    options_package:  Optional[dict]
    ...
```

**TypedDict vs alternatives:**

```
Regular dict:
  state = {}           # No type checking, any key is valid
  state["sku_id"] = 42 # No error — should be str
  mypy: no errors      # Defeats the purpose

TypedDict (ORCA's choice):
  state: AgentState = {"sku_id": "SKU001", ...}
  state["sku_id"] = 42  # mypy error: int, expected str
  Works like a dict at runtime (isinstance(state, dict) == True)
  LangGraph requires a dict-compatible type for AgentState

Pydantic model:
  class AgentState(BaseModel):
      sku_id: str
  state = AgentState(sku_id="SKU001")
  state.sku_id  # attribute access
  Not dict-compatible by default — LangGraph wouldn't accept it as AgentState
  Heavier: validation overhead on every assignment
```

**LangGraph requirement:** The graph is declared as `StateGraph(AgentState)`.
LangGraph internally treats the state as a dict, merging node return values into it.
TypedDict is dict at runtime but adds type-checking at static analysis time.

The `Optional[dict]` fields allow progressive filling — each field starts as `None`
and agents fill their own field.

### Why It Matters
TypedDict is the correct Python type for LangGraph state. Understanding why
(dict-compatible + type-safe) shows Python type system knowledge.

### Red Flags
- Thinks TypedDict validates at runtime (it doesn't — runtime validation is Pydantic's job)
- "Just use a dataclass" — not dict-compatible without extra code
- Doesn't know that `isinstance(AgentState_instance, dict)` returns True

---

## Q5 — Explain how the `_parse_json` function handles markdown code fences.

### The Question to Ask
*"Some LLMs wrap their JSON output in triple backticks. Show me how `_parse_json` handles this."*

### Strong Answer
LLMs frequently output:
```
```json
{
  "urgency": "HIGH",
  "critical_stores": 5
}
```
```

The raw string is: `"```json\n{\n  \"urgency\": \"HIGH\"...}\n```"`

The stripping logic:
```python
clean = text.strip()
if clean.startswith("```"):
    lines = clean.split("\n")
    clean = "\n".join(
        lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
    ).strip()
```

Step by step for input ` ```json\n{"urgency": "HIGH"}\n``` `:
```
lines = ["```json", '{"urgency": "HIGH"}', "```"]

lines[-1].strip() == "```"  → True
→ take lines[1:-1] = ['{"urgency": "HIGH"}']
→ "\n".join([...]) = '{"urgency": "HIGH"}'
→ .strip() = '{"urgency": "HIGH"}'
```

Edge case — no closing fence:
```
lines = ["```json", '{"urgency": "HIGH"}']
lines[-1].strip() == "```"  → False (last line is the JSON itself)
→ take lines[1:] = ['{"urgency": "HIGH"}']
→ same result
```

**Why this matters:** Without stripping, `json.loads('```json\n...\n```')` raises
`JSONDecodeError` — the pipeline would immediately go to the self-correction path,
wasting a second LLM call.

### Why It Matters
String parsing edge cases are a common interview topic. The two-branch logic
(with and without closing fence) handles both common LLM behaviours.

### Red Flags
- Would use a regex (more fragile and harder to read for this case)
- Doesn't account for the no-closing-fence case
- Can't trace the `split` → `join` transformation for a concrete example

---

## Q6 — What design pattern does `get_retriever()` implement and what problem does it solve?

### The Question to Ask
*"The `get_retriever()` function at the bottom of retriever.py uses a global variable. What pattern is this?"*

### Strong Answer
```python
_instance: Optional[ORCARetriever] = None

def get_retriever() -> ORCARetriever:
    global _instance
    if _instance is None:
        _instance = ORCARetriever()
    return _instance
```

This is the **Singleton pattern** — guarantees exactly one instance of `ORCARetriever`
exists in the entire Python process.

**Problem it solves:**
`ORCARetriever.__init__` loads:
- Embedding model: ~270 MB, ~10s load time
- BGE reranker: ~1.1 GB, ~20s load time
- ChromaDB connection
- BM25 cache (empty initially)

If `ORCARetriever()` were called per-request:
```
Request 1 → ORCARetriever() → 30s + 1.5 GB
Request 2 → ORCARetriever() → 30s + 1.5 GB (duplicate!)
Request 3 → ORCARetriever() → 30s + 1.5 GB (duplicate!)
# = OOM or 90s overhead per pipeline
```

With singleton:
```
Request 1 → _instance = ORCARetriever() → 30s, 1.5 GB (first call only)
Request 2 → returns _instance → 0ms, 0 MB
Request 3 → returns _instance → 0ms, 0 MB
```

**Thread safety caveat:** If two requests arrive simultaneously and `_instance is None`
for both, two instances could be created (double initialisation). For ORCA's
single-worker deployment, this is acceptable. A thread-safe version would use
a `threading.Lock` around the check-and-create.

### Why It Matters
Singleton is a Gang of Four pattern — fundamental CS knowledge. More importantly,
knowing the SPECIFIC problem it solves (model loading cost) shows applied reasoning.

### Red Flags
- "It's just a global variable" — misses the pattern name and intent
- Unaware of the thread-safety caveat
- Can't explain WHY model loading makes the singleton critical (not optional)

---

## Q7 — How does LangGraph merge a node's return dict into the AgentState?

### The Question to Ask
*"Agent 1 returns `{"demand_summary": {...}}`. The AgentState has 9 fields. How does LangGraph handle the fact that Agent 1 only returns one field?"*

### Strong Answer
LangGraph performs **selective state merging** — a node's return value is
`dict.update()`-merged into the current state:

```python
def agent1_node(state: AgentState) -> dict:
    ...
    return {"demand_summary": demand_summary}  # only one key

# LangGraph internally:
state.update({"demand_summary": demand_summary})
# Result: state["demand_summary"] = {urgency: HIGH, ...}
# All other fields (sku_id, store_id, options_package, ...) are UNCHANGED
```

This means:
- Agents only need to return the fields they changed
- An agent that forgets to return a field leaves it at its current value (None initially)
- An agent can't accidentally overwrite another agent's output if they only return their own field

**What happens if a node returns an empty dict `{}`?**
Nothing changes. `save_node` returns `{}` — it has no state to write,
it just performs a side effect (DB write) and exits.

**What happens if a node returns a key that doesn't exist in AgentState?**
LangGraph would raise a `KeyError` — TypedDict validation catches this at static analysis.

### Why It Matters
Understanding this merge behaviour is essential for anyone building LangGraph pipelines.
The "return only what you change" pattern is why nodes are composable.

### Red Flags
- Thinks agents need to return the FULL state
- Unaware that returning `{}` is valid (used by save_node)
- Doesn't know that unknown keys would cause errors

---

## Q8 — What does `json.loads` raise if the input has Python-style formulas instead of numbers?

### The Question to Ask
*"An LLM outputs `'{"cost": 993 * 43.74}'`. What exactly does `json.loads()` raise and why?"*

### Strong Answer
```python
import json
json.loads('{"cost": 993 * 43.74}')
# Raises: json.JSONDecodeError: Expecting value: line 1 column 9 (char 8)
```

JSON is a strict subset of JavaScript. JSON does not support:
- Arithmetic expressions: `993 * 43.74`
- Comments: `// this is the cost`
- Trailing commas: `{"a": 1,}`
- Single quotes: `{'a': 1}`
- Undefined/NaN/Infinity

Python's `json.loads()` implements strict JSON parsing. Any non-compliant token
raises `json.JSONDecodeError` with:
- `msg`: description of what was unexpected
- `doc`: the original string
- `pos`: character position of the error

The error position `char 8` points to `*` — the operator that JSON doesn't understand.

**ORCA's self-correction prompt is specifically designed for this:**
```python
fix_prompt = (
    "Fix this JSON — compute all formulas and replacing with actual numbers.\n"
    "Return ONLY valid JSON, no explanation.\n\n"
    f"{clean}"
)
```
"Compute all formulas" directly addresses the `993 * 43.74` pattern.

### Why It Matters
Knowing the specific exception type (`json.JSONDecodeError`, not `ValueError`)
and what triggers it shows deep Python library knowledge.

### Red Flags
- "It raises a `ValueError`" — `JSONDecodeError` is a subclass of `ValueError` but
  being specific matters in a Google interview
- Doesn't know that JSON doesn't support arithmetic (might say "just eval it" — security risk!)
- Unaware that `json.JSONDecodeError` has `pos` and `doc` attributes for debugging

---

## Q9 — Explain the `_build_state_response` function and why it converts to Pydantic models.

### The Question to Ask
*"Why does `api/main.py` have `_parse_demand_summary`, `_parse_options_package`, `_parse_capital_decision`? Why not just return the raw dict?"*

### Strong Answer
The pipeline produces raw Python dicts (from LLM JSON parsing).
FastAPI needs Pydantic models to:
1. **Validate output** — catch missing or wrong-type fields before sending to Streamlit
2. **Serialise consistently** — `model.model_dump()` produces predictable JSON
3. **Document the API** — Pydantic models auto-generate OpenAPI schema at `/docs`

Without conversion:
```python
return raw_state  # a raw Python dict
# Streamlit receives: unpredictable JSON shape
# Missing fields = KeyError in Streamlit
# Wrong types = silent bugs in dashboard
```

With conversion:
```python
def _parse_demand_summary(ds: Optional[dict]) -> Optional[DemandSummary]:
    if not ds:
        return None       # guard clause — None state is valid (pipeline still running)
    return DemandSummary(
        sku_id   = ds.get("sku_id", ""),   # explicit default for required field
        urgency  = ds.get("urgency"),       # Optional — can be None
        ...
    )
```

The three separate functions exist because each nested section (`demand_summary`,
`options_package`, `capital_decision`) has a different shape and different required
fields. Splitting them follows single-responsibility: one function per section.

**Why `ds.get("sku_id", "")` and not `ds["sku_id"]`?**
The raw dict comes from an LLM response. If the LLM forgot to include `sku_id`,
`ds["sku_id"]` would raise `KeyError` and return a 500. `ds.get("sku_id", "")` returns
an empty string — Streamlit gets a valid response, just with an empty field.

### Why It Matters
The raw-to-Pydantic conversion layer is a standard API pattern (hexagonal architecture
— domain objects at the boundary). Knowing WHY it exists (validation, documentation,
type safety) shows API design maturity.

### Red Flags
- "FastAPI serialises dicts automatically" — it does, but with no validation or schema
- Doesn't know `response_model=` in FastAPI triggers Pydantic validation on output
- Unaware that `model_dump()` is the Pydantic v2 equivalent of `.dict()`

---

## Q10 — What is the `with_config()` call on the LLM and what does it do?

### The Question to Ask
*"In Agent 2's code, the LLM call uses `.with_config(run_name=..., tags=..., metadata=...)`. What does this do?"*

### Strong Answer
```python
response = llm.with_config({
    "run_name": f"Agent2-Supply | {sku_id} | {_urgency}",
    "tags":     ["agent2", "supply-replenishment", f"urgency:{_urgency}", f"class:{_abc_class}"],
    "metadata": {
        "agent":     "supply_replenishment",
        "sku_id":    sku_id,
        "urgency":   _urgency,
        "abc_class": _abc_class,
    },
}).invoke(messages)
```

`with_config()` is a LangChain method that attaches **observability metadata** to an LLM call.
It doesn't change the model's behaviour — it adds tracing annotations.

This data is sent to **LangSmith** (if `LANGCHAIN_TRACING_V2=true` is set):
- `run_name`: identifies this call in LangSmith's run tree
- `tags`: filterable labels — you can filter "all urgency:CRITICAL runs" in LangSmith
- `metadata`: structured key-value data — piped to dashboards

**Why it matters in production:**
```
Without: LangSmith shows "LLM call" × 200 — no way to identify which agent ran when
With:    "Agent2-Supply | SKU00090 | HIGH" — immediately know what failed
         Filter by tag "urgency:CRITICAL" → compare critical vs non-critical pipeline times
```

The retrieval eval also logs to LangSmith via `_log_retrieval_to_langsmith()`.

### Why It Matters
LangSmith observability is a production LangChain pattern. Knowing `.with_config()`
shows the candidate thinks about observability, not just correctness.

### Red Flags
- "It changes how the LLM responds" — it doesn't; it's metadata only
- Unaware of LangSmith (the primary LangChain observability tool)
- Can't explain why `tags` vs `metadata` — tags are for filtering, metadata for rich data

---

## Q11 — How is the `PipelineStatus` enum used and why an enum instead of string constants?

### The Question to Ask
*"The API uses `PipelineStatus.RUNNING`, `PipelineStatus.FAILED`, etc. Why use an Enum instead of string constants like `STATUS_RUNNING = 'RUNNING'`?"*

### Strong Answer
```python
class PipelineStatus(str, Enum):
    STARTED              = "STARTED"
    RUNNING              = "RUNNING"
    ESCALATED            = "ESCALATED"
    AUTO_EXECUTED        = "AUTO_EXECUTED"
    EXECUTED_AFTER_APPROVAL = "EXECUTED_AFTER_APPROVAL"
    SUSPENDED            = "SUSPENDED"
    REJECTED             = "REJECTED"
    FAILED               = "FAILED"
```

**`str, Enum` (inherits from both):**
- `PipelineStatus.RUNNING == "RUNNING"` → True (string comparison works)
- FastAPI can serialize it to `"RUNNING"` in JSON automatically
- Pydantic accepts it as a string field value

**Why Enum vs string constants:**
```python
# String constants (fragile):
STATUS_RUNNING = "RUNNING"
STATUS_FAILED  = "FAILED"
if status == "RUNNNIG":  # typo — no error, silent bug!
    ...

# Enum (safe):
if status == PipelineStatus.RUNNNIG:  # AttributeError at IMPORT TIME
    ...
```

**Autocomplete and exhaustiveness:**
With Enum, IDE autocomplete shows all valid values. If you add a new status and
forget to handle it in a `match` statement, mypy warns you (with `match`/`case`).

**`_value2member_map_` for safe conversion:**
```python
status = PipelineStatus(fs) if fs in PipelineStatus._value2member_map_ else PipelineStatus.FAILED
```
Converting unknown strings to Enum raises `ValueError` — `_value2member_map_` check
prevents this crash.

### Why It Matters
Enum vs constants is a fundamental Python design question. The `str, Enum` pattern
for FastAPI-compatible enums is idiomatic modern Python.

### Red Flags
- "Strings are fine" — no IDE support, typo-vulnerable
- Doesn't know `str, Enum` inherits both (thinks enums can't be compared to strings)
- Can't explain `_value2member_map_` — shows no real Enum usage experience

---

## Q12 — Explain the `asynccontextmanager` decorator on the `lifespan` function.

### The Question to Ask
*"How does `@asynccontextmanager` turn `lifespan` into something FastAPI can use for startup/shutdown?"*

### Strong Answer
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    create_pipeline_table()
    logger.info("ORCA API ready")

    yield  # ← the app runs here

    # SHUTDOWN
    logger.info("ORCA API shutting down...")
```

`@asynccontextmanager` is a decorator that turns a generator function into an
async context manager. It works like `@contextmanager` but for async generators.

**The `yield` mechanics:**
```
asynccontextmanager wraps the function so:
  __aenter__:  runs everything BEFORE yield, returns the yielded value (app runs here)
  __aexit__:   runs everything AFTER yield (shutdown)

FastAPI uses it as:
  async with lifespan(app):
      # serve all requests here
```

**Why a single yield and not two separate functions:**
The startup and shutdown code are co-located — you can see the full lifecycle
in one function. Before yield = on/after yield = off, like a switch.
Compare to the older pattern which required two separate decorated functions:
```python
@app.on_event("startup")     # deprecated
async def startup_event():
    create_pipeline_table()

@app.on_event("shutdown")    # deprecated
async def shutdown_event():
    logger.info("shutting down")
```

### Why It Matters
Context managers are a core Python pattern (used everywhere: `with open()`, `with lock:`).
The `@asynccontextmanager` variant shows advanced Python knowledge.

### Red Flags
- Confuses `asynccontextmanager` with `contextmanager` (the sync version)
- Can't explain what happens between `yield` and shutdown (the app runs there)
- "This is FastAPI-specific magic" — it's standard Python stdlib pattern

---

## Q13 — How does `_store_update` achieve thread safety and what's the scope of the lock?

### The Question to Ask
*"The lock is held only during `_store_update`. What does this mean for the pipeline code that runs for 30 seconds?"*

### Strong Answer
```python
_store_lock = threading.Lock()

def _store_update(pipeline_id: str, **kwargs):
    with _store_lock:               # LOCK ACQUIRED
        if pipeline_id not in _pipeline_store:
            _pipeline_store[pipeline_id] = {}
        _pipeline_store[pipeline_id].update(kwargs)
        _pipeline_store[pipeline_id]["last_updated"] = _now()
    # LOCK RELEASED  ← exits `with` block
```

**Lock scope:** The lock is held only for the duration of the dict update — ~1 microsecond.

**What's NOT inside the lock:** The actual pipeline execution (30–90 seconds):
```python
def _run_pipeline_task(pipeline_id, sku_id, store_id):
    _store_update(pipeline_id, status=RUNNING)      # lock for 1μs
    # ... 90 seconds of LLM calls, MCP, DB ... NOT under lock
    _store_update(pipeline_id, status=COMPLETED, raw_state=final_state)  # lock for 1μs
```

**Why this design is correct:**
- Multiple pipelines can run fully in parallel — they never block each other
- The dict update is atomic (one thread updates, then the next)
- Reading `_pipeline_store[pipeline_id]` in the `/state` endpoint is not locked
  — a read-only operation with potential stale data is acceptable (polling endpoint,
  not financial transaction)

**Alternative (worse): Lock the entire pipeline execution:**
```python
with _store_lock:
    run_pipeline()  # 90s under lock — serialises ALL pipelines
```
This would allow only one pipeline at a time — catastrophic for throughput.

### Why It Matters
Lock granularity is a key concurrency concept. Coarse-grained locks cause
serialisation (poor throughput); fine-grained locks cause complexity and
potential deadlocks. ORCA's design is appropriately fine-grained.

### Red Flags
- "The entire pipeline should be under the lock" — catastrophic performance
- "GIL handles this" — GIL doesn't make compound dict operations atomic
- No mention that read operations on the store aren't locked (acceptable stale read)

---

## Q14 — How does `sorted(scores.items(), key=lambda x: x[1], reverse=True)` work?

### The Question to Ask
*"In `rrf_fuse` and `BM25Index.search`, you sort with `key=lambda x: x[1], reverse=True`. Walk me through this."*

### Strong Answer
```python
scores = {
    "chunk_B": 0.03252,
    "chunk_A": 0.03202,
    "chunk_D": 0.01613,
    "chunk_C": 0.01587,
}

result = sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

Step by step:
1. `scores.items()` → view of `(key, value)` tuples:
   `[("chunk_B", 0.03252), ("chunk_A", 0.03202), ("chunk_D", 0.01613), ("chunk_C", 0.01587)]`

2. `key=lambda x: x[1]` → sort by the second element (the score):
   `x` = `("chunk_B", 0.03252)`, `x[1]` = `0.03252`
   Python's Timsort uses this key function to compare elements.

3. `reverse=True` → descending order (highest score first).

Result: `[("chunk_B", 0.03252), ("chunk_A", 0.03202), ("chunk_D", 0.01613), ("chunk_C", 0.01587)]`

**Time complexity:** O(n log n) for Timsort, where n = number of unique chunks across both result lists.
For ORCA's 71-chunk collection: at most 71 items to sort — negligible cost.

**Why not `sorted(scores, key=scores.get, reverse=True)`?**
That also works but returns keys only (not key-value tuples). The current form
returns tuples that can be directly iterated as `(doc_id, score)` pairs.

### Why It Matters
Sorting with lambda key functions is idiomatic Python. Understanding what `items()`
returns and why `x[1]` extracts the score is basic Python literacy for data-heavy code.

### Red Flags
- Thinks `scores.items()` returns keys only (it returns `(key, value)` tuples)
- Doesn't know that `reverse=True` means highest first (might confuse with ascending)
- Can't explain the time complexity of sort (should be reflexive knowledge)

---

## Q15 — What does `Optional[dict]` mean in Python's type system, and what does `state.get("demand_summary", {})` protect against?

### The Question to Ask
*"Many places in graph.py use `state.get('demand_summary', {})` instead of `state['demand_summary']`. Why the `.get()` with default `{}`?"*

### Strong Answer
`Optional[dict]` in Python's type system means `Union[dict, None]` — the field
can be either a `dict` or `None`.

```python
# TypedDict declaration:
demand_summary: Optional[dict]  # can be None initially

# Early in pipeline execution:
state = {
    "sku_id":         "SKU00090",
    "demand_summary": None,   # ← not yet filled
    ...
}
```

**`state['demand_summary']`** when the value is `None`:
- Returns `None` — no error, but `demand_summary.get("urgency")` would then crash:
  `AttributeError: 'NoneType' object has no attribute 'get'`

**`state.get('demand_summary', {})`**:
- If key exists and is not None: returns the dict
- If key doesn't exist: returns `{}`
- If key exists but is None: returns `None` (NOT the default `{}` — common mistake!)

**The actual safe pattern in graph.py:**
```python
demand_summary  = state.get("demand_summary") or {}
# or {}  handles both missing AND None: None or {} = {}
```

This is a Python idiom: `x or {}` returns `{}` if `x` is falsy (None, empty dict, 0).
Different from `.get(key, {})` which only handles missing keys, not None values.

**Why agents do this:**
```python
approval_pool = options_package.get("options", [{}])[0].get("pool_id", "CP001")
# What if options_package is None (Agent 2 hasn't run yet)?
# None.get(...) → AttributeError — need the `or {}` guard
```

### Why It Matters
`None` vs "missing key" is a common Python pitfall. The `or {}` pattern is
the correct way to handle both. The difference between `.get(key, {})` and `x or {}`
reveals Python fluency.

### Red Flags
- Thinks `.get(key, {})` handles None values (it doesn't — only missing keys)
- Doesn't know `Optional[dict]` means `Union[dict, None]`
- "Just use `if demand_summary is not None`" — works but verbose for every access

---

## Scoring Guide for Recruiters

| Score | What It Means |
|---|---|
| Can trace execution at the byte level | Strong hire — reads and writes code confidently |
| Correct on patterns, fuzzy on syntax | Solid hire — good reasoning, review some Python |
| Knows design patterns without code execution model | Caution — may be more architect than engineer |
| Can't read `enumerate(results, 1)` | Red flag — insufficient Python proficiency for senior |

**Questions that most separate senior from mid-level coders:**
- Q1 (asyncio.run vs run_until_complete — exact semantics matter)
- Q5 (markdown fence stripping — defensive edge-case thinking)
- Q8 (json.JSONDecodeError — specific exception, not generic ValueError)
- Q13 (lock granularity — 1μs vs 90s inside the lock)
- Q15 (`or {}` vs `.get(key, {})` — subtle Python distinction)
