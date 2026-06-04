# Python Proficiency for Senior AI Engineers

## What Is It? (Plain English)

Python is the lingua franca of AI and machine learning, but most engineers who "know Python" are actually using only a fraction of its capabilities. There is a big difference between Python that works and Python that is readable, efficient, maintainable, and safe in production. Senior AI engineers are expected to know the difference.

The patterns covered here — generators, decorators, context managers, async/await, type hints — are the hallmarks that distinguish a Python practitioner from a Python beginner. They appear throughout production AI codebases because they solve real problems: generators handle large datasets without exhausting memory, decorators add cross-cutting behaviour cleanly, async/await handles the I/O-heavy reality of LLM API calls without blocking threads.

This section also covers the traps that trip up even experienced Python developers: mutable default arguments silently sharing state across function calls, the Global Interpreter Lock limiting parallelism, and late binding closures producing unexpected results in loops. Knowing these pitfalls is the mark of an engineer who has debugged production issues, not just written tutorials.

## How It Works

```
PYTHON FEATURE MAP
==========================================
Feature           | Use case
──────────────────|───────────────────────
List comprehension| Concise data transforms
Generator (yield) | Lazy evaluation, large data
Decorator (@)     | Cross-cutting concerns (logging, retry, auth)
Context manager   | Resource cleanup (files, DB connections)
async/await       | Non-blocking I/O (LLM calls, HTTP)
dataclass         | Typed data containers, less boilerplate
TypedDict         | Type-safe dictionaries (LangGraph AgentState)
Type hints        | IDE support, runtime validation via Pydantic
==========================================

List comprehension vs generator:
  [x*2 for x in range(1_000_000)]    → builds full list in memory (8 MB)
  (x*2 for x in range(1_000_000))    → lazy: one item at a time (56 bytes)
```

Key code patterns:

```python
# Generator — processes data lazily
def read_chunks(filepath: str, chunk_size: int = 1000):
    with open(filepath) as f:
        while chunk := f.read(chunk_size):
            yield chunk   # pauses here; resumes on next()

# Decorator — adds retry logic without changing function body
import functools, time
def retry(max_attempts: int = 3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(2 ** attempt)   # exponential backoff
        return wrapper
    return decorator

# TypedDict — how ORCA defines AgentState for LangGraph
from typing import TypedDict, Any
class AgentState(TypedDict):
    sku_id: str
    demand_analysis: dict[str, Any]
    replenishment_options: list[dict]
    capital_decision: dict[str, Any]
    route: str
    run_id: str
```

## Why Google Cares About This

Google's AI infrastructure is built in Python at the research and application layer. When a senior engineer joins a team, they are expected to write code that other engineers can read, maintain, and extend without hand-holding. Interviewers probe Python depth because superficial knowledge leads to subtle bugs at scale — a mutable default argument silently sharing state across requests, a blocking synchronous call in an async context grinding an entire API server to a halt, a shallow copy creating hard-to-reproduce data corruption bugs. Python proficiency signals that you will write production-quality code from day one.

## Interview Questions & Answers

### Q1: What is the difference between a generator and a list comprehension? When would you use a generator in an AI system?

**Answer:** A list comprehension evaluates the entire sequence immediately and stores all results in memory. A generator evaluates one item at a time, yielding each value lazily and keeping only the current item in memory.

```python
# List comprehension: loads all 1M embeddings into RAM at once
embeddings = [embed(doc) for doc in documents]   # could be gigabytes

# Generator: processes one at a time, then discards it
def embedding_stream(documents):
    for doc in documents:
        yield embed(doc)                           # 56 bytes overhead
```

In AI systems, generators are critical for two use cases. First, streaming LLM responses — OpenAI and Anthropic both provide streaming APIs that yield tokens as they are generated. A generator lets you process and forward each token to the UI without waiting for the full response. Second, batch processing large datasets — when ingesting 100,000 documents for a RAG pipeline, loading them all into memory before embedding would crash most machines. A generator-based pipeline processes one chunk at a time.

The `yield from` syntax delegates to a sub-generator, useful for composing streaming pipelines:

```python
def process_pipeline(docs):
    yield from (preprocess(d) for d in docs)   # chain generators lazily
```

In ORCA's RAG ingest pipeline, generators would be the right pattern for reading documents in chunks rather than loading all policy documents at once, though the current implementation works fine since there are only 5 policy documents. The principle becomes critical when ingesting enterprise knowledge bases with thousands of documents.

---

### Q2: Explain Python decorators. Write a decorator that adds timing and logging to any function.

**Answer:** A decorator is a function that takes another function as input and returns a modified function. It is Python's mechanism for adding cross-cutting concerns — behaviour that applies across many functions — without repeating code in each function body. Common uses: logging, timing, authentication checks, rate limiting, retry logic, caching.

The `@functools.wraps(func)` line is critical — without it, the wrapper function replaces the original function's `__name__` and `__doc__` attributes, breaking debugging tools, logging, and docstring inspection.

```python
import functools
import logging
import time

logger = logging.getLogger(__name__)

def timed_and_logged(func):
    @functools.wraps(func)   # preserves __name__, __doc__, __module__
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        logger.info(f"Calling {func.__name__} with args={args!r}")
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.info(f"{func.__name__} completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"{func.__name__} failed after {elapsed:.3f}s: {e}")
            raise
    return wrapper

@timed_and_logged
def call_llm(prompt: str) -> str:
    # ... actual LLM call
    return "response"
```

In the ORCA codebase, a decorator like this would be valuable on every LangGraph node function — you would get automatic timing and logging for the demand intelligence, replenishment, and capital allocation agents without instrumenting each one individually.

Decorators can also take arguments (parameterised decorators), which requires an extra layer of nesting: the outer function accepts the parameters and returns the actual decorator.

---

### Q3: What are Python's most dangerous pitfalls? Explain mutable default arguments, the GIL, and late binding closures.

**Answer:** These three pitfalls are responsible for a disproportionate share of Python production bugs.

**Mutable default arguments** — Python evaluates default argument values once, at function definition time, not at each call. When the default is a mutable object like a list or dict, all calls that use the default share the same object.

```python
# BROKEN: all calls share the same list
def add_item(item, store=[]):
    store.append(item)
    return store

add_item("a")   # returns ["a"]
add_item("b")   # returns ["a", "b"]  ← WRONG, expected ["b"]

# CORRECT: use None as sentinel, create new list each call
def add_item(item, store=None):
    if store is None:
        store = []
    store.append(item)
    return store
```

**The Global Interpreter Lock (GIL)** — Python's memory management is not thread-safe, so CPython uses a mutex (the GIL) that allows only one thread to execute Python bytecode at a time. This means CPU-bound threads do not truly run in parallel, even on multi-core machines. However, the GIL is released during I/O operations — network calls, file reads — so threading works fine for I/O-bound work like concurrent LLM API calls.

```
threading.Thread   → I/O-bound: OK (GIL released during I/O)
                   → CPU-bound: NO benefit (GIL prevents true parallelism)
multiprocessing    → CPU-bound: OK (separate process, no shared GIL)
asyncio            → I/O-bound: best (single thread, no GIL issue, very low overhead)
```

**Late binding closures** — Python looks up closure variable values at call time, not at definition time. In a loop, all closures see the final value of the loop variable.

```python
# BROKEN: all functions print 4 (the final value of i)
funcs = [lambda: i for i in range(5)]
funcs[0]()   # prints 4, not 0

# CORRECT: bind the current value with a default argument
funcs = [lambda i=i: i for i in range(5)]
funcs[0]()   # prints 0 correctly
```

---

### Q4: Explain async/await in Python. How does ORCA handle the sync/async boundary?

**Answer:** Python's `asyncio` event loop runs in a single thread and multiplexes I/O operations. When an async function hits an `await`, it pauses and hands control back to the event loop, which can then run another coroutine. This is cooperative multitasking — no OS-level thread switching, extremely low overhead.

```python
import asyncio
import httpx

async def call_llm(prompt: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"messages": [{"role": "user", "content": prompt}]}
        )
        return response.json()["choices"][0]["message"]["content"]

async def run_parallel_agents(prompts: list[str]) -> list[str]:
    tasks = [call_llm(p) for p in prompts]
    return await asyncio.gather(*tasks)   # runs all concurrently
```

The challenge in production systems is that sync and async code must interoperate. FastAPI is async-native. LangGraph nodes can be sync or async. When sync code needs to call an async function, you cannot simply `await` it — there is no running event loop. When async code needs to call a blocking sync function, it should not call it directly — it would block the entire event loop.

ORCA handles this with an `_run_async` bridge pattern:

```python
import asyncio

def _run_async(coro):
    """Run an async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an existing event loop (e.g., FastAPI)
            # Use a thread pool to avoid blocking
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
```

For CPU-bound tasks, use `loop.run_in_executor(None, sync_function, args)` to run them in a thread pool without blocking the event loop.

---

### Q5: How do TypedDict, dataclasses, and Pydantic models differ? When would you use each in an AI system?

**Answer:** All three provide structured data containers with type annotations, but they have fundamentally different trade-offs.

**TypedDict** is a plain dictionary at runtime — no validation, no overhead. Type checkers (mypy, pyright) can check types statically, but at runtime you can put anything in a TypedDict and it won't complain. This makes it ideal for LangGraph's AgentState because LangGraph needs to serialise/deserialise the state object through checkpoints, and a plain dict serialises perfectly without any custom logic.

```python
from typing import TypedDict, Any

class AgentState(TypedDict):
    sku_id: str
    demand_analysis: dict[str, Any]
    route: str      # "ESCALATE" | "AUTO_EXECUTE" | "SUSPEND"
```

**dataclass** adds real Python object semantics — methods, `__repr__`, `__eq__`, optional `__hash__`, default values. It is validated at definition time (not instantiation time). Use it for internal domain objects where you want methods and equality comparison.

```python
from dataclasses import dataclass, field

@dataclass
class ReplenishmentOption:
    option_type: str
    quantity: int
    total_cost: float
    lead_days: int
    score: float = field(default=0.0)

    def is_affordable(self, budget: float) -> bool:
        return self.total_cost <= budget
```

**Pydantic** provides runtime validation — it will raise a `ValidationError` at instantiation if a value doesn't match the declared type. Use it at API boundaries (FastAPI request/response models) where you cannot trust the input.

```python
from pydantic import BaseModel, Field

class ApprovalRequest(BaseModel):
    run_id: str
    approved: bool
    approver_email: str = Field(pattern=r".*@.*\..*")
    comments: str | None = None
```

The rule of thumb: TypedDict for LangGraph state (serialisation-first), Pydantic for API models (validation-first), dataclass for internal business objects (methods-first).

## Key Points to Say in the Interview

- "Generators are lazy sequences — they compute one item at a time, avoiding memory exhaustion on large datasets."
- "The GIL means Python threads share one CPU core for CPU-bound work; use multiprocessing for parallelism there."
- "Decorators add cross-cutting behaviour without modifying function bodies — I use them for retry, timing, and authentication."
- "`asyncio` gives high concurrency for I/O-bound work like LLM calls at almost zero overhead compared to threads."
- "TypedDict is a runtime dict with static type hints — perfect for LangGraph AgentState because it serialises cleanly."
- "Mutable default arguments is the most common Python footgun — always use None as sentinel for mutable defaults."
- "Pydantic validates at runtime at API boundaries; TypedDict validates statically via mypy at development time."
- "Late binding closures are fixed by capturing the variable as a default argument: `lambda x=x: x`."

## Common Mistakes to Avoid

- Using mutable objects (list, dict) as default function arguments — always use `None` and create inside the function.
- Calling a blocking sync function directly inside an async function — it will block the entire event loop.
- Forgetting `@functools.wraps(func)` in decorators — breaks `__name__`, `__doc__`, and introspection tools.
- Using `threading.Thread` for CPU-bound parallelism — the GIL prevents true parallel execution; use `multiprocessing` instead.
- Confusing shallow copy (`copy.copy`) with deep copy (`copy.deepcopy`) — shallow copy of nested objects shares inner references.

## Further Reading

- [Python Data Model (official docs)](https://docs.python.org/3/reference/datamodel.html) — explains decorators, context managers, and dunder methods from first principles
- [asyncio documentation](https://docs.python.org/3/library/asyncio.html) — official event loop, coroutines, and tasks reference
- [Pydantic v2 docs](https://docs.pydantic.dev/latest/) — runtime validation library used by FastAPI and LangChain
