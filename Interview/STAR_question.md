###  Q1 What is the most challenging technical problem you've solved in a product?

The best answer here is the async/sync bridge.

Situation

  When I connected the LangGraph agents to the MCP tools, the pipeline crashed immediately.

   This was confusing because langchain-mcp-adapters converts MCP tools into LangChain StructuredTool objects — they look exactly like regular LangChain tools. I was calling .invoke() on them, which is the standard LangChain API. It should have worked.

Why It Was Hard

  When I dug into it, I realised I had two completely incompatible execution contexts that all needed to talk to each other:

  LangGraph nodes (synchronous)
      LangGraph calls agent nodes as plain def functions.
      They run in a background thread via BackgroundTasks.
      That thread has NO running event loop.

   MCP tools (async-only)
      MCP communicates via subprocess stdio.
      The adapter wraps them as async coroutines.
      They ONLY support .ainvoke(), never .invoke()

The LangGraph node is synchronous, but it needs to call an async tool. 

The Solution

  I wrote a single bridge function _run_async()

   ▎ "LangGraph nodes are synchronous functions, but MCP tools are async-only — they communicate over a subprocess and only support async calls. The problem is you can't call async code from a 
  ▎ synchronous function directly. 
  
  I wrote one bridge function that handles its:  it creates a  event loop and runs the async call inside it.  
  Every agent batches all its tool calls into one async helper function, then calls 
  the bridge once. One bridge, one entry point, both execution environments covered."


### Q2 Tell me about a production incident or outage you were involved in.

After deploying ORCA, every pipeline run was failing at Agent 1. The dashboard showed the pipeline stuck at RUNNING, never progressing past the demand analysis step. The logs showed a 422
  Unprocessable Entity error coming back from Groq on every CrewAI call. 422 means the request was malformed — Groq was rejecting the request before even attempting to run the model.

The confusing part was that direct LLM calls from other agents were working fine. Only CrewAI calls were failing. Same API key, same model, same endpoint — but different result.

Diagnosis

  My first instinct was to check the API key and model name. Both were correct. I then enabled verbose logging inside CrewAI by passing verbose=True to the Crew constructor. This printed the full
  outgoing message payload to the terminal before it hit the Groq API.

  That's when I saw it. The system message had an extra field injected into it — cache_breakpoint — that I had never written. It wasn't in any of my prompts. CrewAI was adding it automatically.

   It was in CrewAI's LLM wrapper — a block of code that checks if the provider is Anthropic, and if so, injects
  cache_breakpoint into the system message to enable Anthropic's prompt caching feature. The problem was that CrewAI was treating Groq's endpoint as an Anthropic endpoint — because the model name
  format triggered that check — and injecting a field that only Anthropic's API understands. Groq had no idea what cache_breakpoint was and rejected the entire request with a 422.

Fix

  The LLM wrapper had a parameter called is_anthropic. Setting it to False explicitly told CrewAI not to inject the Anthropic-specific fields, regardless of what the model name looked like. One
  parameter, one line. Every CrewAI call started working immediately.

### Q3 Tell me about a time when your solution did not work as expected.

  The original design of ORCA had Agent 4 make the routing decision using an LLM. The logic seemed sound — Agent 4 had read all the output from Agents 1, 2, and 3, it knew the capital pool limits, it
  knew the urgency. I wrote a prompt that said: based on the cost, the pool pressure, and whether approval is required, decide whether to ESCALATE, AUTO_EXECUTE, or SUSPEND.

  It worked in testing. The model understood the three routes and picked correctly on most cases.

  ---
  What Went Wrong

  When I ran it across a wider set of test scenarios — different capital pools, different cost thresholds, different urgency combinations — I noticed the routing was wrong roughly 15 percent of the
  time. Not randomly wrong. Specifically wrong in one pattern: the model was confusing the auto-approval limits across capital pools.

  ORCA has three capital pools. CP001 has a fifty thousand AED auto-approve limit. CP003 has a twenty thousand AED limit. When an order from CP003 came in at thirty thousand AED — which requires
  approval — the model would sometimes route it to AUTO_EXECUTE because thirty thousand is below CP001's limit. It was applying the wrong pool's threshold.

  The model wasn't hallucinating. It was retrieving a real number from its context. It was just retrieving the wrong pool's number. And because the output looked confident and structured, this failure
  was completely silent — no error, no warning, just a wrong routing decision.

  In a financial system, a 15 percent error rate on the approval gate is not a calibration problem. It's a fundamental disqualification. An order that needed human approval was going straight to
  execution one in every seven times.

  ---
  How I Recovered

  I removed the LLM from the routing decision entirely. The route node became twelve lines of pure Python. It reads two values from state — approval_required, which Agent 3 sets as a boolean, and
  pool_pressure, which comes from a direct database lookup. Three if/else branches. No prompt. No inference.

  pool pressure HIGH       → SUSPEND
  approval_required false  → AUTO_EXECUTE
  approval_required true   → ESCALATE

  Then I wrote 22 unit tests covering the full routing matrix — every combination of pool pressure and approval flag. The test suite runs in under 10 seconds with zero LLM calls. If anyone changes the
  routing logic, the tests catch it immediately.

  I documented the decision in ADR-005: routing logic was moved from LLM inference to deterministic Python after observing a 15 percent error rate on capital pool limit confusion.

  ---
  What I Learned

  The LLM was doing exactly what I asked it to do — reasoning from context. The problem was that reasoning from context is the wrong tool for a binary financial gate. The correct tool is a lookup and
  a comparison. There is no ambiguity in "does this number exceed this threshold" — it's a deterministic question with a deterministic answer. Giving it to an LLM introduced variance where variance
  must not exist.

   30-Second Version

  ▎ "I originally had an LLM decide whether to escalate, auto-execute, or suspend each order. It worked in basic testing but had a 15 percent error rate across broader scenarios — specifically it was
  ▎ confusing auto-approval limits across capital pools, routing orders that needed human approval straight to execution. I removed the LLM from that decision entirely and replaced it with twelve
  ▎ lines of pure Python and 22 unit tests. The learning: deterministic financial gates must be deterministic code. An LLM introduces variance exactly where variance cannot exist."

### Q4 What is a technical decision you strongly disagreed with?

Story 1 — Committing the ChromaDB Index to the Repo (ADR-004)

  The conventional wisdom being disagreed with:
  Every engineer knows you don't commit generated or binary files to git. The ChromaDB vector index is a generated artifact — it's built by running ingest.py over 5 policy documents. Standard
  practice: add it to .gitignore, regenerate it in CI as part of the build.

  Why I disagreed:

  The ChromaDB index uses nomic-embed-text-v1.5 for embeddings. That model downloads from HuggingFace at runtime. Two problems with regenerating in CI: first, HuggingFace downloads are flaky — a
  transient network failure fails the entire eval gate for a reason unrelated to code quality. Second, nomic-embed-text updates its model weights periodically. If the model version on CI drifts from
  the version used locally, the same query returns different chunks, the same golden test cases fail, and you spend hours debugging what looks like a retrieval regression but is actually an embedding
  model version mismatch. I had this happen — a golden case that passed locally failed on CI because CI downloaded a newer model version that shifted vector rankings slightly.

  The committed index guarantees that every CI run evaluates against identical embeddings, identical chunks, identical rankings. The eval gate measures whether my code changed the retrieval quality,
  not whether HuggingFace changed their model.

   ▎ "The conventional rule is never commit generated files. I disagreed with that for the ChromaDB vector index specifically. The index is built from embeddings — and embedding models update their
  ▎ weights. When CI regenerates the index it can download a different model version than what I used locally, and suddenly the same retrieval test fails not because my code changed but because the
  ▎ model changed. I committed the index so every CI run evaluates against identical embeddings. The tradeoff is 15MB in the repo, which is acceptable for 71 chunks. I documented it as ADR-004 with
  ▎ the condition under which it should be revisited: when the document corpus grows past a few hundred chunks, the index moves to object storage and CI pulls it as an artifact."


### Q5 Describe the most scalable system you've built.

Situation

  ORCA is the most architecturally complex system I've built. It's a multi-agent AI pipeline with a FastAPI backend, LangGraph orchestration, MCP tool discovery, a RAG retrieval layer, and a
  human-in-the-loop approval workflow — all running concurrently and writing to shared state. I designed it for single-instance deployment, but I made deliberate decisions about which parts can scale
  independently and documented exactly where the current architecture breaks under load.


 What the Scaled Architecture Looks Like

  Current                         At Scale
  ───────────────────────         ──────────────────────────────
  Single Render worker            Multiple workers behind
                                  a load balancer

  In-memory dict (_pipeline_store) → Redis with TTL

  SQLite (orca.db + checkpoints)  → PostgreSQL
                                    (LangGraph PostgresSaver)

  MCP subprocess per pipeline     → Persistent MCP server
                                    with connection pool

  No LLM retry                    → Tenacity exponential backoff

  Single ChromaDB instance        → Pinecone or Weaviate
                                    for distributed vector search

  The API layer, the pipeline logic, the RAG layer, and the data layer are each independently replaceable. That separation was deliberate — I didn't want the scaling upgrade of one component to
  require touching the others.


### Q6 Tell me about a time you improved performance, cost, or reliability significantly. 

The strongest story here is the LLM routing → pure Python change. It has real numbers, a clear before/after, and a financial risk angle that lands hard. Here's the full answer.

  ---
  The Answer

  Situation
  
  ORCA's route node decides whether an order gets auto-executed, escalated for human approval, or suspended. This decision is a financial control — it determines whether money gets spent without a
  human seeing it. I originally implemented it as an LLM call inside Agent 4. The model read the full pipeline state and decided the route.

  ---
  The Problem — Quantified

  When I ran a systematic test across 30 scenarios covering all three capital pools at different cost thresholds and urgency levels, I found the LLM was routing incorrectly in roughly 15 percent of
  cases.

  The failure pattern was specific: the model was confusing auto-approval limits across capital pools. CP001 has a 50,000 AED auto-approve limit. CP003 has a 20,000 AED limit. Orders from CP003
  between 20,000 and 50,000 AED — which require approval — were being routed to AUTO_EXECUTE because the model retrieved CP001's limit instead of CP003's.

  Translating that to business impact: at the order volumes this system is designed for — roughly 100 pipeline runs per day across a retail operation — a 15 percent error rate means 15 orders per day
  bypassing the approval gate. If the average escalated order is 35,000 AED, that's 525,000 AED per day being auto-executed without human sign-off. That's not a performance problem. That's a
  compliance failure.

  The LLM call itself also cost roughly 3 seconds per routing decision — token generation on a model reading a large state object just to produce a three-word answer.

  ---
  The Change

  I replaced the entire LLM call with 12 lines of pure Python. The route node reads two values from state — approval_required, a boolean set by Agent 3, and pool_pressure, fetched from the database —
  and branches deterministically:

  pool pressure HIGH       → SUSPEND
  approval_required false  → AUTO_EXECUTE
  approval_required true   → ESCALATE

  No prompt. No inference. No token generation.

  Then I wrote a test matrix: 22 unit tests covering every combination of pool pressure and approval flag across all three capital pools. The full suite runs in under 10 seconds with zero API calls.

  ---
  The Impact — Quantified

  Metric                   Before              After
  ──────────────────────── ──────────────────  ──────────────────
  Routing error rate        15%                 0%
  Routing latency           ~3 seconds          < 1 millisecond
  Cost per routing call     ~$0.001 (Groq)      $0
  Test coverage             0 tests             22 tests
  Financial exposure        525,000 AED/day     0
    (at target volume)      bypassing approval

  The latency improvement is also compounding — this node runs on every single pipeline. At 100 pipelines per day, removing a 3-second LLM call saves 300 seconds of processing time daily. More
  importantly it removes 100 Groq API calls from the rate limit budget, which frees capacity for the agents that genuinely need inference.

  ---
  What Made This an Architectural Decision, Not Just a Bug Fix

  The key insight is that the original design was wrong at the concept level, not the implementation level. Routing on a financial threshold is a deterministic question — does this number exceed this
  other number? There is no ambiguity, no nuance, no context that changes the answer. Giving a deterministic question to a probabilistic system introduces variance exactly where variance must not
  exist.

  I documented this in ADR-005: financial controls must be deterministic code, not inference. That principle now governs every future design decision in ORCA about what goes to an LLM and what stays
  in Python.

  ---
  30-Second Version

  ▎ "The route node originally used an LLM to decide whether to escalate or auto-execute. I measured a 15 percent error rate — the model was confusing auto-approval limits across capital pools,
  ▎ routing orders that needed human sign-off straight to execution. At target volume that's roughly 525,000 AED per day bypassing the approval gate. I replaced the entire LLM call with 12 lines of
  ▎ Python and 22 unit tests. Routing latency dropped from 3 seconds to under a millisecond. Error rate dropped to zero. The principle I extracted: a deterministic question should never be answered by
  ▎ a probabilistic system."


### Q7 Describe the most difficult bug you've ever debugged.

The Answer

  Situation

  After building the Layer 1 retrieval eval, I ran it locally — 11 golden test cases, all passing. I pushed to GitHub. CI failed. Same code, same data, same test cases. Different results.

  This is the worst category of bug. When something crashes with a traceback, you have a starting point. When something produces different results silently in a different environment, you have nothing
  obvious to follow.

  ---
  Investigation Process

  Step 1 — Rule out the obvious things. (20 minutes)

  First hypothesis: the ChromaDB index wasn't present on CI. I checked the workflow file — the index was committed to the repo and present in the CI checkout. Not that.

  Second hypothesis: missing environment variable or API key. The retrieval eval doesn't use an LLM or API key. Not that.

  Third hypothesis: a path issue. I checked sys.path and the ROOT resolution in the eval script. Both environments resolved to the same directory structure. Not that.

  All three obvious hypotheses eliminated. The eval was running, reaching the retriever, and getting a response. The response was just different.

  Step 2 — Add visibility into what was actually being returned. (30 minutes)

  I added temporary print statements to the eval to show the raw context string for each failing case, not just the pass/fail result. I ran it locally, captured the output. Then I pushed a branch that
  printed the same output on CI and looked at the CI logs.

  The same query was returning different chunks. Locally, the top-ranked chunk for an Agent 1 Grocery Class C query contained "Options A & B available" and "Ordering Rules". On CI, those chunks
  weren't in the top 3 at all — different chunks were ranking higher.

  Same query. Same ChromaDB index. Different rankings.

  Step 3 — Isolate what could cause ranking differences. (45 minutes)

  Ranking in hybrid retrieval comes from two sources: BM25 scores and vector similarity scores. BM25 is deterministic — same index, same query, same scores every time. So if rankings differ, it has to
  be the vector similarity scores changing.

  Vector similarity depends on the query embedding. If the embedding of the query string is different, the cosine distances are different, the rankings change.

  That led to the question: could the query embedding be different between environments?

  Step 4 — Find the embedding model version difference. (20 minutes)

  The embedding model is nomic-embed-text-v1.5, downloaded from HuggingFace. Locally I had run ingest.py weeks earlier — at that point, a specific version of the model weights was cached. CI downloads
  the model fresh on every run, pulling the latest available version from HuggingFace.

  nomic-embed-text had released a minor update between when I cached it locally and when CI was pulling it. The model weights changed. The embeddings of the same query string changed slightly. The
  cosine distances changed slightly. Chunks that were ranking 2nd locally were ranking 4th on CI, falling outside the top 3 that get returned.

  The eval was not broken. The retriever was not broken. The test cases were written against embeddings that no longer existed on CI.

  Step 5 — Fix the test cases pragmatically. (30 minutes)

  Two options: pin the model version everywhere, or change the test cases to use keywords stable across both embedding versions.

  Pinning the model version adds a maintenance burden — you have to manually update the pin when the model improves. Worse, it means CI is testing against a stale embedding model, which defeats the
  purpose of the eval.

  The pragmatic fix: change must_contain keywords to phrases that appear in chunks which rank highly under both embedding versions — terms with strong BM25 signal, like exact supplier names and exact
  pool IDs, rather than phrases from chunks whose ranking is sensitive to vector similarity.

  For example: "Options A & B" depends on a specific chunk ranking in the top 3. "CP001" and "Grocery" appear in multiple chunks across multiple document types, so they surface regardless of which
  chunks win the vector ranking.

  I updated the failing cases, added comments explaining exactly why each keyword was chosen and what was removed, and pushed.

  ---
  How Long It Took

  About 2.5 hours total. The first hour was elimination — ruling out the obvious causes. The second half hour was adding visibility. The final hour was tracing from "different chunks" to "different
  embeddings" to "different model version." The fix itself took 30 minutes.

  The part that took longest was step 3 — realising the rankings could only differ if the embeddings differed, and that the embeddings could differ even with the same model name if the weights had
  been updated upstream.

  ---
  What I Learned

  Two things. First: when debugging environment-specific failures, the fastest path is making the outputs visible before making hypotheses. I wasted 20 minutes on hypotheses before I just printed what
  was actually being returned. The print statements told me in 5 minutes what the hypotheses couldn't.

  Second: external dependencies with implicit versioning are a hidden source of non-determinism. nomic-embed-text has a version in its name but HuggingFace serves updated weights under the same name.
  That's a mutable reference disguised as a fixed one. Now when I write eval test cases, I choose keywords with strong lexical signal — exact names, exact IDs — rather than phrases whose retrieval
  depends on vector ranking alone.

  ---
  30-Second Version

  ▎ "My retrieval eval passed locally and failed on CI with no error — just different chunks returned for the same query. I added logging to see the raw context on both sides, confirmed the chunks
  ▎ were different, traced it to different cosine similarity scores, traced that to different query embeddings, traced that to HuggingFace serving updated nomic-embed-text weights to CI while my local
  ▎ cache had an older version. Same model name, different weights. The fix was changing must_contain keywords from phrases sensitive to vector ranking to exact IDs and names with strong BM25 signal
  ▎ that appear reliably under both versions. Took 2.5 hours. The lesson: version names on external models aren't always version pins."

  ---
  The Line That Shows Deep Understanding

  ▎ "The hardest part wasn't finding the root cause — it was knowing that BM25 is deterministic so if rankings differed it had to be the vector side, and if the vector side differed with the same
  ▎ model name it had to be the weights. That chain of elimination is the only way to debug a system where everything looks correct but outputs differ."


#############################

 Questions You Should Still Practice

  ---
  1. "How do you test a system whose outputs are non-deterministic?"

  Why it matters: Google asks this directly for ML/AI roles. Most junior candidates say "you can't really test AI." That's wrong and they know it.

  Your ORCA angle: The 3-layer strategy — pytest for deterministic parts, retrieval eval for deterministic retrieval, RAGAS for statistical LLM quality. The key line: "retrieval is deterministic, LLM
  output is not, and you test them differently."

  ---
  2. "Tell me about a time you over-engineered something."

  Why it matters: Self-awareness question. They want to see intellectual honesty.

  Your ORCA angle: Building BM25 from scratch instead of using rank_bm25. You needed a custom tokenizer and per-agent indexes — valid reasons. But the honest admission is that if you added a second
  corpus, maintaining a custom BM25 implementation costs more than the library would.

  ---
  3. "Tell me about a time you had to make a decision and ship without complete information."

  Why it matters: Tests whether you can operate under uncertainty without paralysis.

  Your ORCA angle: Setting RETRIEVE_TOP_K=10 and FINAL_TOP_K=3 for the RAG pipeline. You had 71 chunks, no measured chunk distribution, no query diversity data. Used literature defaults and built the
  eval framework to validate them after.

  ---
  4. "What would you do differently if you started this project over?"

  Why it matters: Retrospective thinking is explicitly a Google signal. Defending every past decision signals inexperience.

  Your ORCA angle: Three honest changes — Layer 2 eval built first not last, LangGraph Studio used from the start, the two-file tool pattern enforced with a lint rule from day one. Plus what you would
  NOT change and why.

  ---
  5. "Tell me about a time you had to explain a technical decision to a non-technical stakeholder."

  Why it matters: Communication ability is evaluated explicitly at senior level.

  Your ORCA angle: Explaining to a supply planning manager why the pipeline takes 60 seconds. The restaurant analogy — receipt given immediately, 4 specialists cooking in the kitchen, app checks in
  every 3 seconds. The 60 seconds IS the value, not a delay.

  ---
  6. "Tell me about a time you had to balance shipping speed against quality."

  Why it matters: Every team faces this. They want a framework, not "I always prioritise quality."

  Your ORCA angle: Three conscious cuts — Layer 2 judge eval, Redis for pipeline store, automatic LLM retry. Each cut has a documented reason, a human backstop, and a timeline to fix. The framework:
  probability × impact, is there a human backstop, is it documented.

  ---
  Which to Practice Next?

  ┌──────────────────────────────┬────────────────────────────────────────────┐
  │ If your interviews are at... │                 Prioritise                 │
  ├──────────────────────────────┼────────────────────────────────────────────┤
  │ Google (ML/AI team)          │ Q1 — testing non-deterministic systems     │
  ├──────────────────────────────┼────────────────────────────────────────────┤
  │ Google (SWE generalist)      │ Q4 — what would you do differently         │
  ├──────────────────────────────┼────────────────────────────────────────────┤
  │ Any senior role              │ Q6 — shipping speed vs quality             │
  ├──────────────────────────────┼────────────────────────────────────────────┤
  │ Any AI product role          │ Q3 — decision without complete information │
  └──────────────────────────────┴────────────────────────────────────────────┘

  Want me to write out the full answer for any of these?
