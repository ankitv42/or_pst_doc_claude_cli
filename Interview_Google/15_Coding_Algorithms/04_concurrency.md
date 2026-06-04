# Concurrency in Python

## What Is It? (Plain English)

Concurrency means making progress on multiple tasks at the same time, or at least giving that appearance. When your phone downloads a file while you type a text message, those two things happen "concurrently." In software, concurrency is how we make systems that are responsive and efficient rather than sitting idle waiting for one slow operation to finish before starting the next.

Python offers three mechanisms for concurrency: threads, processes, and async coroutines. Each solves a different problem. The confusion arises because they look similar but behave very differently — and Python has a peculiarity called the Global Interpreter Lock (GIL) that fundamentally changes the trade-offs compared to other languages like Java or Go.

In AI systems specifically, concurrency matters enormously because the dominant bottleneck is almost always I/O — waiting for LLM API responses that take 2-10 seconds, database queries, HTTP requests. The right concurrency model can turn a 30-second sequential pipeline into a 10-second concurrent one without any algorithmic changes.

## How It Works

```
THREE CONCURRENCY MODELS IN PYTHON
=========================================

threading.Thread     multiprocessing.Process     asyncio coroutine
─────────────────    ───────────────────────     ─────────────────
Shared memory        Separate memory             Shared memory
OS-managed           OS-managed                  Cooperative
GIL limited          No GIL (own interpreter)    Single thread
Good for I/O         Good for CPU work           Good for I/O
~1MB stack each      ~50MB overhead each         ~1KB each

THE GIL EXPLAINED:
─────────────────────────────────────────────────
Thread 1 wants to run Python code
Thread 2 wants to run Python code
GIL: "Only one of you can run at a time."
Thread 1 runs → Thread 2 waits
Thread 1 hits network I/O → GIL released
Thread 2 runs while Thread 1 waits for network
→ Threading works for I/O-bound (threads take turns)
→ Threading FAILS for CPU-bound (one thread at a time)

ASYNC EVENT LOOP:
─────────────────────────────────────────────────
Event loop runs in ONE thread
Coroutine A hits `await` → pauses, registers callback
Coroutine B starts running
Network data arrives → callback fires → A resumes
→ Zero thread-switching overhead
→ Can handle 10,000 concurrent I/O operations
```

## Why Google Cares About This

Google's products handle millions of concurrent requests. An AI engineer who does not understand concurrency will write code that either blocks under load (synchronous calls in async contexts) or creates race conditions that are nearly impossible to debug. LLM API calls are the slowest operations in any AI pipeline — 1-10 seconds each. Understanding when to parallelise them with `asyncio.gather`, when to use a thread pool via `run_in_executor`, and when a problem actually needs multiprocessing is the difference between a pipeline that handles 10 requests per second and one that handles 1. This knowledge also directly affects infrastructure cost on Google Cloud.

## Interview Questions & Answers

### Q1: Explain the Python GIL. Why does it exist, and what are its practical consequences for an AI engineer?

**Answer:** The Global Interpreter Lock is a mutex in CPython's interpreter that ensures only one thread executes Python bytecode at any moment. It exists because Python's memory management — specifically reference counting for garbage collection — is not thread-safe. Without the GIL, two threads could simultaneously modify an object's reference count, causing memory corruption and crashes.

The GIL's practical consequences depend on whether your work is CPU-bound or I/O-bound. For CPU-bound work — matrix multiplication, image processing, computing embeddings — the GIL means that adding more threads does not increase throughput. You still get only one CPU core worth of Python computation regardless of how many threads you create. This surprises engineers coming from Java or Go.

For I/O-bound work — HTTP requests, database queries, reading files, waiting for LLM API responses — the GIL is released during the blocking I/O operation. Thread 1 can hand off the GIL before calling `socket.recv()`, allowing Thread 2 to run Python code while Thread 1 waits for network data. This is why threading works fine for I/O-bound concurrency.

```
CPU-BOUND (image resizing):
Thread 1: [──Python────────────────────────────] uses GIL entire time
Thread 2: [─────────────────────────────waiting] blocked by GIL
→ Wall-clock time: same as single thread. Threads wasted.

I/O-BOUND (LLM API calls):
Thread 1: [──Python──][──waiting for API──][──Python──]
Thread 2: [────wait──][──Python──][──wait──][──Python──]
→ Wall-clock time: ~50% of sequential. Threads productive.
```

For CPU-bound parallelism in Python, use `multiprocessing` — each process gets its own Python interpreter and GIL. The cost is process startup time (~50ms) and inter-process communication overhead (data must be pickled). For CPU-heavy ML preprocessing, `concurrent.futures.ProcessPoolExecutor` is the standard idiom.

---

### Q2: When would you use threading vs asyncio vs multiprocessing? Give a concrete example for each.

**Answer:** The decision tree is straightforward once you know what type of work you are doing:

**Threading** — Use for I/O-bound work where you have existing synchronous code you cannot easily convert to async, or when you need to interface with blocking libraries that don't support async.

```python
from concurrent.futures import ThreadPoolExecutor
import requests

def fetch_inventory(store_id: str) -> dict:
    return requests.get(f"https://api.inventory.com/store/{store_id}").json()

# Fetch 10 stores concurrently without rewriting as async
with ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(fetch_inventory, store_ids))
```

**asyncio** — Use for I/O-bound work when you control the code and can write it async from the start. This is the best approach for LLM API calls because the major LLM SDKs all provide async clients.

```python
import asyncio
from langchain_groq import ChatGroq

async def run_agents_concurrently(state: AgentState) -> dict:
    llm = ChatGroq(model="llama-3.1-8b-instant")
    # Run demand analysis and market check in parallel
    demand_task = asyncio.create_task(llm.ainvoke(demand_prompt))
    market_task = asyncio.create_task(llm.ainvoke(market_prompt))
    demand_result, market_result = await asyncio.gather(demand_task, market_task)
    return {"demand": demand_result, "market": market_result}
```

**multiprocessing** — Use for CPU-bound work: data preprocessing, feature engineering, running multiple model inference jobs in parallel.

```python
from concurrent.futures import ProcessPoolExecutor
import numpy as np

def compute_embeddings_batch(texts: list[str]) -> np.ndarray:
    # CPU-intensive: transformer model running locally
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model.encode(texts)

# Use all CPU cores for embedding computation
with ProcessPoolExecutor(max_workers=4) as executor:
    batches = [texts[i:i+100] for i in range(0, len(texts), 100)]
    all_embeddings = list(executor.map(compute_embeddings_batch, batches))
```

The summary: async for modern I/O code, threading for legacy I/O code, multiprocessing for CPU work.

---

### Q3: What is a race condition? Give an example and explain how threading.Lock prevents it.

**Answer:** A race condition occurs when the outcome of a program depends on the timing of thread execution — specifically, when two threads read and write shared state in an interleaved way that produces incorrect results.

The classic example is a counter increment. `counter += 1` in Python compiles to three bytecode instructions: LOAD the current value, ADD 1 to it, STORE the result. If two threads execute this simultaneously, they can both load the same value, both add 1, and both store the same result — incrementing by 1 when the intent was to increment by 2.

```
Thread 1: LOAD counter (value=5)
Thread 2: LOAD counter (value=5)   ← context switch happens here
Thread 1: ADD 1 → 6
Thread 2: ADD 1 → 6
Thread 1: STORE 6
Thread 2: STORE 6
Result: counter = 6, expected: counter = 7
```

`threading.Lock` is a mutual exclusion primitive. Only one thread can hold the lock at a time. Any thread that tries to acquire a held lock will block until the lock is released.

```python
import threading

class InvCounter:
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:           # acquires lock, releases on exit
            self._count += 1       # only one thread here at a time

    @property
    def count(self):
        with self._lock:
            return self._count

counter = InvCounter()
threads = [threading.Thread(target=counter.increment) for _ in range(1000)]
for t in threads: t.start()
for t in threads: t.join()
print(counter.count)   # always 1000, never less
```

A deadlock occurs when Thread A holds Lock 1 and waits for Lock 2, while Thread B holds Lock 2 and waits for Lock 1. Prevention: always acquire multiple locks in the same order, or use a single lock that protects all shared state.

---

### Q4: How does ORCA handle the sync/async boundary in its FastAPI + LangGraph architecture?

**Answer:** This is a genuine architectural challenge that appears in almost every real AI system. FastAPI is an async web framework — its request handlers are async functions running in an event loop. LangGraph's pipeline involves a mix of sync and async nodes. The MCP tools are async. The LLM calls via LangChain are async. But some utilities and the SQLite database queries are synchronous.

```
ORCA's Concurrency Architecture:
═══════════════════════════════════════════════════════════
FastAPI event loop (main thread)
  │
  ├─ POST /pipeline/run (async handler)
  │    └─ background_tasks.add_task(run_pipeline, ...)
  │         └─ asyncio.run() or loop.run_in_executor()
  │              └─ LangGraph pipeline
  │                   ├─ Agent 1 node: sync LLM call (via ChatGroq)
  │                   ├─ MCP tools: async (ainvoke)
  │                   ├─ Agent 2 node: sync computation
  │                   └─ DB writes: sync (sqlite3)
  │
  └─ GET /pipeline/{run_id} (async handler — non-blocking polling)
═══════════════════════════════════════════════════════════
```

The key pattern is FastAPI's `BackgroundTasks`: the API returns a `202 Accepted` immediately, then runs the pipeline in a background task. This means the slow LangGraph pipeline does not block the HTTP response. The dashboard polls the status endpoint every 3 seconds.

For truly blocking calls inside an async context, the correct pattern is `loop.run_in_executor(None, sync_function)`, which runs the sync function in a thread pool without blocking the event loop:

```python
import asyncio

async def async_node(state: AgentState) -> AgentState:
    loop = asyncio.get_event_loop()
    # Run blocking SQLite query in thread pool, don't block event loop
    result = await loop.run_in_executor(None, db_query_sync, state["sku_id"])
    return {**state, "db_result": result}
```

The `interrupt_before=["execute_node"]` HITL pattern works because LangGraph's MemorySaver checkpointer persists the graph state to memory between the pause and resume. The graph can be reconstructed and continued from any checkpoint, which is why `POST /approve/{run_id}` can resume a pipeline that paused hours earlier.

---

### Q5: What are common concurrency bugs, and how do you detect and prevent them?

**Answer:** The four most common concurrency bugs are race conditions, deadlocks, livelocks, and starvation.

**Race condition** (covered above) — two threads modifying shared state without synchronisation. Detection: use threading sanitisers (Python's `-X dev` mode), write tests that run operations from multiple threads, look for non-deterministic test failures. Prevention: use locks, use thread-safe data structures (`queue.Queue`, `collections.deque`), prefer immutable data.

**Deadlock** — Thread A holds Lock 1, waits for Lock 2. Thread B holds Lock 2, waits for Lock 1. Both wait forever. Detection: stack traces show threads all waiting on locks. Prevention: always acquire locks in the same global order; use `threading.RLock` (re-entrant lock) if a thread needs to acquire the same lock twice; use `asyncio.wait_for` with a timeout to surface deadlocks.

**Async-specific: blocking call in event loop** — The most common async bug. Calling a blocking function (database query, file read, `time.sleep`) directly in an async function blocks the entire event loop, preventing all other coroutines from running.

```python
# BUG: blocks event loop for the duration of the DB query
async def handle_request():
    result = sqlite3.connect("db.sqlite").execute("SELECT ...").fetchall()  # WRONG

# CORRECT: run blocking call in thread pool
async def handle_request():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, db_query_sync)   # RIGHT
```

**Task exception swallowed silently** — When you use `asyncio.create_task()`, exceptions in the task are not propagated unless you explicitly await the task or add a `.add_done_callback`. Always store task references and check for exceptions.

```python
# Swallowed exception (common bug)
asyncio.create_task(risky_coroutine())   # if this raises, you'll never know

# Safe pattern
task = asyncio.create_task(risky_coroutine())
task.add_done_callback(lambda t: t.exception() and logger.error(t.exception()))
```

## Key Points to Say in the Interview

- "The GIL means Python threads can't achieve CPU parallelism — for that, use multiprocessing."
- "asyncio is the right choice for LLM API calls — I/O-bound, thousands of concurrent requests, near-zero overhead."
- "A race condition is non-deterministic by nature — it may not appear in testing but will appear in production under load."
- "threading.Lock prevents races; always use context manager (`with lock:`) to ensure release on exception."
- "Blocking calls inside async functions are the #1 async bug — use `run_in_executor` to offload to a thread pool."
- "ORCA's 202 pattern — return immediately, process in background — is the right model for slow AI pipelines."
- "Deadlock prevention: always acquire multiple locks in the same order across all code paths."

## Common Mistakes to Avoid

- Using `threading.Thread` for CPU-bound parallelism expecting speedup — the GIL prevents it.
- Calling `time.sleep()` instead of `await asyncio.sleep()` in an async function — blocks the entire event loop.
- Creating `asyncio.Task` objects without storing references — Python's garbage collector may cancel them silently.
- Using a single global lock for all shared state — serialises everything and eliminates concurrency benefit.
- Forgetting to call `thread.join()` before program exit — the main thread exits, killing background threads mid-operation.

## Further Reading

- [asyncio documentation](https://docs.python.org/3/library/asyncio.html) — comprehensive official reference for Python async programming
- [threading documentation](https://docs.python.org/3/library/threading.html) — Lock, RLock, Semaphore, Event, Condition primitives explained
- [Python Concurrency with asyncio (Manning)](https://www.manning.com/books/python-concurrency-with-asyncio) — the most thorough treatment of Python async patterns for production systems
