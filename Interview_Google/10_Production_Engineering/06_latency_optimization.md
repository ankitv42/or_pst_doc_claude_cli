# Latency Optimization: Making Systems Fast

## What Is It? (Plain English)

Latency is the time between a user taking an action and seeing a result. It's the pause between clicking a button and the response appearing. Every millisecond of latency has a measurable impact on user satisfaction and business outcomes. Amazon's internal research (widely cited) found that every 100 ms of additional latency reduced sales by 1%. Google found that a 400 ms delay reduced search volume by 0.74%. These numbers are small percentages applied to enormous scales, which is why the world's largest technology companies invest heavily in latency optimization.

The tricky aspect of latency is that it's not uniform. Your average latency might be 50 ms, but some users experience 800 ms. This is why engineers measure "percentile latency" — P50, P95, P99. P99 latency (the latency that 99% of requests are faster than) is the most operationally relevant because it represents your worst common experience. P50 (the median) tells you what a typical user experiences; P99 tells you what your worst-served 1% experience — and at Google's scale, 1% is millions of users.

For AI systems, latency has two distinct components that require different optimization strategies. **Infrastructure latency** is what traditional software engineering addresses: database queries, network hops, serialization. **Inference latency** is unique to AI: the time the model takes to generate an answer. For LLMs specifically, inference latency has two sub-components: Time to First Token (TTFT — how quickly the first word appears) and total generation time (how long until the last word). Streaming responses improve perceived experience by optimizing TTFT even when total generation time is unchanged.

## How It Works

```
IDENTIFYING LATENCY SOURCES (Profiling):
─────────────────────────────────────────────────────────────
Incoming request for ORCA pipeline:
                                           Cumulative time
  [FastAPI receives request]    ──►  0 ms
  [Database: load SKU data]     ──►  5 ms   (+5ms)
  [ChromaDB: RAG retrieval]     ──►  50 ms  (+45ms)
  [Groq: Agent 1 call]          ──► 1800 ms (+1750ms) ← BOTTLENECK
  [Groq: Agent 2 call]          ──► 3200 ms (+1400ms) ← BOTTLENECK
  [Groq: Agent 3 call]          ──► 4500 ms (+1300ms) ← BOTTLENECK
  [Database: save results]      ──► 4508 ms (+8ms)
  [FastAPI: serialize response] ──► 4510 ms (+2ms)

Analysis: 99.8% of latency is Groq API calls.
Fix: parallelize where possible; cache where repeated;
     use faster model (8b vs 70b).
─────────────────────────────────────────────────────────────

ASYNC PATTERNS (Python asyncio):
─────────────────────────────────────────────────────────────
SEQUENTIAL (slow):
  result1 = await call_agent1()   ← wait 1800ms
  result2 = await call_agent2()   ← wait 1400ms (AFTER agent1)
  result3 = await call_agent3()   ← wait 1300ms (AFTER agent2)
  Total: ~4500ms

PARALLEL (where agents are independent):
  result1, result2 = await asyncio.gather(
      call_agent1(),  ← starts immediately
      call_agent2()   ← starts immediately, runs concurrently
  )                   ← both finish in max(1800, 1400) = 1800ms
  result3 = await call_agent3(result1, result2)  ← +1300ms
  Total: ~3100ms  (31% faster)

Note: ORCA's agents have dependencies, limiting parallelism.
─────────────────────────────────────────────────────────────

LLM LATENCY: TTFT vs TOTAL TIME with Streaming:
─────────────────────────────────────────────────────────────
Without streaming:
  User waits 3200ms → sees complete response

With streaming:
  User waits 150ms  → sees first word
  More words appear → feels fast even if total is 3200ms
  
  User perception: "instant response" despite same total time
─────────────────────────────────────────────────────────────
```

## Why Google Cares About This

Google Search has a latency SLA that has historically been under 200 ms for the entire round trip. Achieving this for a system that ranks billions of web pages in real time requires every subsystem — query parsing, index lookup, ranking model, ad selection, response formatting — to complete within its allocated latency budget. Google pioneered "tail latency" thinking (P99/P999) because at their request volume, even a 0.01% failure rate represents millions of users. In a senior AI interview, demonstrating latency optimization knowledge proves you think about user experience engineering, not just algorithmic correctness.

## Interview Questions & Answers

### Q1: What is P50/P95/P99 latency and why do we care about percentiles rather than averages?

**Answer:** Latency percentiles describe the distribution of response times across all requests, not just the central tendency. P50 (the 50th percentile, also the median) means 50% of requests complete faster than this value. P95 means 95% complete faster. P99 means 99% complete faster. The remaining 1% of requests — the "tail" — take longer than the P99 value.

The average (mean) latency is misleading because it's sensitive to outliers in the wrong direction. Imagine 100 requests: 99 complete in 50 ms and 1 completes in 10,000 ms. The average is (99×50 + 1×10,000) / 100 = 149.5 ms. But 99% of users experienced 50 ms — the "bad" 10-second experience is completely invisible in the average. P99 = 10,000 ms would immediately flag this outlier. The average flatters the system; percentiles expose the extremes.

At Google's scale (100,000+ requests per second), 1% slow means 1,000 users/second experiencing bad latency. P99 is not an edge case — it's a real, large population. Furthermore, Jeff Dean (one of Google's most renowned engineers) documented the "tail-at-scale" problem: in a system where a client makes 100 parallel requests (e.g., fetching 100 search result components), the total latency is determined by the *slowest* component. If each component has P99 = 1s, a fan-out request that waits for all 100 has a near-100% probability of hitting at least one slow component. The P99 of the aggregate is much worse than the P99 of any individual component.

For ORCA's 4-agent sequential pipeline, the total latency is the sum of agent latencies. If each Groq call has P99 latency of 5 seconds, the 4-agent pipeline's P99 is approximately 20 seconds. The sequential pipeline is latency-additive. This is why even small improvements in per-call P99 latency compound across a multi-agent pipeline.

### Q2: How do you identify and fix latency bottlenecks in a system?

**Answer:** Identifying bottlenecks follows the scientific method: instrument, measure, analyze, optimize. "Optimizing blindly" — tuning database queries when the actual bottleneck is network I/O — wastes time and can actually introduce regressions in the things you're not measuring.

The first step is distributed tracing: adding trace context to every request that flows through the system, so you can see a waterfall diagram of where time was spent. Tools like Jaeger, Zipkin, or Google Cloud Trace produce timeline charts showing every service call, its duration, and its children. For ORCA, adding OpenTelemetry spans around each agent call, each database query, and each RAG retrieval call would immediately reveal where the 4-5 second pipeline time is spent. The waterfall diagram in the observation section above (FastAPI→DB→ChromaDB→Agent1→Agent2→Agent3) comes from this kind of instrumentation.

The second step is finding the "critical path" — the sequence of operations that determines total latency. Operations on the critical path cannot be made faster by parallelizing; they must be optimized individually. Operations off the critical path can be parallelized with critical-path operations. In ORCA's sequential 4-agent pipeline, every step is on the critical path (each agent depends on the previous). To reduce total latency, you must reduce individual agent latency.

The options for reducing LLM inference latency: (1) Use a smaller, faster model — Groq's llama-3.1-8b-instant is ~3x faster than llama-3.3-70b-versatile with acceptable quality for structured reasoning tasks. (2) Reduce token count — the output length directly determines generation time. Strict output format instructions ("respond in exactly this JSON schema, no prose") can cut agent output tokens by 50-70%. (3) Prompt caching — Anthropic and some providers offer prompt caching where the static system prompt is cached server-side, eliminating re-processing on every call. (4) Streaming — return tokens as generated rather than waiting for completion; for ORCA's pipeline, streaming Agent 2's output to Agent 3 would reduce the inter-agent waiting time.

### Q3: What are async patterns and how do they improve latency?

**Answer:** Asynchronous (async) programming allows a program to start an operation (like an I/O call) and move on to other work while waiting for the result, instead of blocking until the operation completes. It's the difference between placing a coffee order and standing at the counter frozen until it's ready (synchronous) versus placing the order, doing other work, and returning when called (asynchronous).

In Python, async/await syntax (using asyncio) implements this pattern. An `await` statement suspends the current task, gives control back to the event loop, and the event loop can start other tasks while the awaited operation completes. This is why FastAPI uses async handlers: while waiting for a Groq API response (I/O-bound, no CPU work needed during the wait), the event loop can handle other incoming HTTP requests. One Python thread can serve hundreds of concurrent HTTP requests this way.

The latency benefit of async is greatest when multiple independent I/O operations can be parallelized with `asyncio.gather()`. If ORCA's Agent 1 and Agent 2 were truly independent (no dependency), running them concurrently would cut their combined latency from `agent1_time + agent2_time` to `max(agent1_time, agent2_time)`. For two 1.5-second calls, this saves 1.5 seconds — a 33% reduction in total pipeline time.

However, async does not make CPU-bound work faster. If Agent 1's logic requires heavy Python computation, asyncio doesn't help — it only helps with I/O wait. For CPU-bound ML inference (running a local model, not an API call), true parallelism requires multiple Python processes (via `concurrent.futures.ProcessPoolExecutor`), not multiple async tasks. The distinction: async is for I/O concurrency; multiprocessing is for CPU parallelism. ORCA is almost entirely I/O-bound (waiting for Groq API and database calls), so async is the right tool.

### Q4: What is connection pooling and why does it reduce latency?

**Answer:** Every time an application opens a new database connection, there is overhead: the TCP handshake, the database authentication handshake, and the initialization of the connection state. This overhead can take 5–50 ms depending on the database and network. For a service that makes 1,000 queries/second, opening a fresh connection for each query is 1,000 × 50 ms = 50 seconds of pure overhead per second — clearly impossible.

Connection pooling maintains a pool of pre-opened, authenticated database connections that queries can reuse. When a query arrives, it borrows a connection from the pool (near-instant), executes the query, and returns the connection. The overhead of opening the connection is paid once at startup, not per-query. A pool of 20 connections can service thousands of queries per second, limited only by the database's query execution speed.

The pool size choice is a tuning decision. Too small: queries queue waiting for a free connection (latency increases). Too large: the database is overwhelmed by the number of active connections (databases have per-connection overhead; PostgreSQL allocates ~10 MB per connection). The empirically common starting point is: pool size = number of CPU cores × 2 + effective spindle count. For most web services, 10–20 connections is reasonable.

For AI systems specifically, connection pooling is important because LLM API clients (the HTTP connections to Groq, OpenAI) also benefit from connection reuse. HTTP/2 keeps connections open for multiple requests; HTTP/1.1 connection keep-alive achieves similar effect. The Groq Python client uses `httpx` under the hood, which implements connection pooling automatically. For high-throughput LLM serving, configuring the `httpx.AsyncClient` with an explicit `limits` parameter (`max_connections=100, max_keepalive_connections=20`) prevents a new TCP connection from being opened for every API call.

### Q5: What is LLM-specific latency optimization — TTFT, speculative decoding, and continuous batching?

**Answer:** LLM inference has a unique latency profile because generation is autoregressive: each token depends on all previous tokens, making generation fundamentally sequential. You cannot parallelize the generation of a single sequence — token N+1 requires token N's key-value (KV) cache. The strategies for reducing perceived and actual latency are therefore different from traditional systems optimization.

Time to First Token (TTFT) is the latency from receiving the request to generating the first output token. It's dominated by the prefill phase — processing the full input prompt through the model. TTFT matters for user experience: a system that starts streaming output in 100 ms feels responsive even if total generation takes 5 seconds. Strategies to reduce TTFT: shorter prompts (fewer tokens to prefill), prompt caching (server-side cache of the KV states for a commonly-used system prompt, so prefill is skipped), and hardware — Groq's LPU (Language Processing Unit) hardware achieves ~50x faster prefill than GPU for their supported models.

Speculative decoding is a clever algorithm for reducing total generation time. A small "draft" model generates several candidate tokens very quickly. A larger "oracle" model then verifies these candidates in parallel — checking whether it would have generated the same tokens. If it agrees with the draft, those tokens are accepted and the large model effectively skips N generation steps. If it disagrees, it regenerates from the disagreement point. Because verification is parallel (unlike generation), the oracle model can accept batches of speculative tokens for a 2–4x speedup with no quality reduction.

Continuous batching (also called iteration-level scheduling) is the key innovation in serving frameworks like vLLM that makes GPU utilization efficient. Traditional batching holds a fixed batch of requests and processes them together until all finish — wasteful because short requests finish early while the GPU waits for long ones. Continuous batching adds new requests to the batch as old ones complete, maximizing GPU utilization. This doesn't reduce per-request latency but dramatically increases throughput — serving more users per GPU hour. Groq's architecture (LPU chips plus custom serving software) achieves high efficiency through similar principles, which is why it delivers notably low latency at low cost.

For ORCA, the practical latency levers are: (1) use `llama-3.1-8b-instant` instead of `llama-3.3-70b-versatile` — the 8b model is ~3x faster; (2) implement streaming for agent outputs displayed in the dashboard (TTFT improvement); (3) cache the static parts of system prompts using Groq's or Anthropic's prompt caching feature; (4) instrument each agent call with timing spans and alert when any single call exceeds 5 seconds (an outlier that should trigger retry or fallback).

## Key Points to Say in the Interview

- Always cite P99 latency, not average — P99 represents the worst experience that a significant population of users encounters
- Identify bottlenecks before optimizing — distributed tracing reveals the critical path, then optimize only what's on the critical path
- Async/await improves I/O-bound latency by allowing concurrency; multiprocessing improves CPU-bound throughput
- For LLMs, distinguish TTFT (time to first token — user experience) from total generation time (compute cost)
- Streaming responses improve perceived TTFT dramatically with no change to backend latency
- Connection pooling is a mandatory production configuration — pay connection setup cost once, not per request
- Speculative decoding and continuous batching are key LLM serving optimizations worth knowing at a conceptual level for a Google interview

## Common Mistakes to Avoid

- Do NOT optimize for mean/average latency — it hides tail latency; optimize for P99 or P95
- Do NOT assume parallelism always helps — only independent operations benefit; operations on the critical path must be optimized in place
- Do NOT conflate async and multiprocessing — async handles I/O concurrency in one thread; multiprocessing achieves CPU parallelism across multiple processes
- Do NOT ignore TTFT for interactive applications — a 5-second streaming response feels very different from a 5-second blank-then-dump
- Do NOT over-pool connections — too many database connections degrades database performance; tune the pool size to the database's concurrency capacity

## Further Reading

- [Jeff Dean: The Tail at Scale (Google Research Paper)](https://research.google/pubs/the-tail-at-scale/) — The canonical paper on why P99 latency matters at scale and techniques for hedging against tail latency
- [ByteByteGo: Latency Numbers Every Programmer Should Know](https://blog.bytebytego.com/p/ep22-latency-numbers-every-programmer) — Visual reference for latency of every common operation from L1 cache to cross-datacenter network round trip
- [vLLM Documentation: Continuous Batching](https://docs.vllm.ai/en/latest/serving/distributed_serving.html) — Technical explanation of continuous batching and how it improves LLM throughput
- [Google Cloud: Optimize AI Platform Prediction Latency](https://cloud.google.com/ai-platform/prediction/docs/online-predict#latency) — Google's official guidance on reducing prediction latency in production serving
- [Martin Fowler: Async Await Patterns](https://martinfowler.com/articles/async-await.html) — Clear explanation of async programming patterns and their latency implications
