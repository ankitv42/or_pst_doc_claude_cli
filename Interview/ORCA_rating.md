ORCA — 2026 AI System Rating

  ---
  1. Agentic Architecture — 8/10

  LangGraph is the dominant stateful agent framework in 2026. CrewAI sub-crew inside an outer LangGraph pipeline is a sophisticated pattern very few freshers attempt. MCP
  for dynamic tool discovery is genuinely forward-looking — it's an Anthropic open standard gaining rapid adoption in 2025-26.

  Deduction: Agent 1's CrewAI sub-crew fails on every run due to the cache_breakpoint bug. Known issue, not fixed.

  ---
  2. RAG Implementation — 6/10

  The architecture is production-quality: BM25 + vector + RRF fusion + BGE cross-encoder reranking + corrective retrieval. This is the same stack used at Cohere, Pinecone,
  and enterprise RAG products.

  Deduction: Your actual RAGAS scores tell the truth. Context precision 0.20 is the retriever returning noisy chunks. The architecture is right, the tuning is not done.
  Small corpus (71 chunks, 5 documents) also limits what you can demonstrate.

  ---
  3. Evaluation Framework — 7/10

  This is ORCA's most surprising strength. Most fresher projects have zero evaluation. You have:
  - pytest for deterministic logic (10 seconds, no LLM)
  - Layer 1 retrieval eval with golden dataset
  - RAGAS-style metrics with Groq judge
  - Composite gate in CI (≥0.75 to merge)

  Deduction: Layer 2 LLM-as-judge is a stub. Actual RAGAS scores are below threshold — the framework exists, the quality doesn't pass yet.

  ---
  4. HITL / AI Safety Design — 9/10

  This is ORCA's highest-rated area and the genuine differentiator. The design decisions are correct:
  - Financial routing in pure Python, not LLM inference
  - interrupt_before checkpoint survives server restarts
  - Class A SKU protection as a hard prompt rule, not an AI judgment
  - Approval threshold documented in ADR-005

  In 2026, "AI safety in production" means human oversight for high-stakes decisions. ORCA gets this right architecturally.

  Deduction: SqliteSaver on Render free tier means HITL doesn't actually persist across server restarts in the live deployment. The design is right; the deployment doesn't
  support it.

  ---
  5. Production Engineering — 4/10

  ┌─────────────────────────────────────────────────┬───────────────────────────────────────────┐
  │                      Issue                      │                  Impact                   │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ In-memory pipeline store (_pipeline_store dict) │ Wipes on restart                          │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ SqliteSaver → ephemeral Render disk             │ HITL state lost on restart                │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ ESCALATED in ACTIVE_STATUSES                    │ Polls for hours during HITL wait          │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ No LLM retry logic                              │ One Groq rate-limit = pipeline failure    │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ No authentication on API                        │ Any request can trigger a pipeline        │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ Two-file tool pattern                           │ Manual sync required on every tool change │
  └─────────────────────────────────────────────────┴───────────────────────────────────────────┘

  This is the honest gap between a demo and a production system. All fixable — Redis, PostgresSaver, retry decorator, API key middleware — but not done.

  ---
  6. Observability — 4/10

  LangSmith tracing exists in the eval layer. But for the live system:
  - No per-agent latency tracking
  - No token cost per pipeline run
  - No alert if pipeline failure rate spikes
  - No dashboard for AI behavior (separate from inventory dashboard)

  In 2026, production AI systems are expected to have LLM-specific observability: token spend, latency per LLM call, hallucination rate over time, retrieval quality
  trends. ORCA has none of this in the live path.

  ---
  7. Cost / Efficiency Design — 5/10

  Groq free tier is a smart choice for a demo (zero cost). The prompt design is efficient — each agent has a focused system prompt, not a giant context dump.
  Agent-specific RAG queries reduce irrelevant context tokens.

  Deduction: No semantic caching (same SKU queried twice = two full LLM calls). No token budget enforcement. No streaming (user waits 90 seconds for a full response with
  no incremental output).

  ---
  8. Model Provider Independence — 7/10

  llm_factory.py with LLM_PROVIDER=groq env var is the right pattern. Swapping to OpenAI or Anthropic is a config change, not a code change. LangChain abstraction means
  tools and memory patterns are provider-agnostic.

  Deduction: CrewAI's LLM wrapper is hardcoded to llama-3.3-70b-versatile. Agent 1's crew doesn't use the factory pattern.

  ---
  9. Code Quality and Patterns — 6/10

  Good patterns present:
  - _store_update() encapsulation (Redis swap touches one function)
  - db/queries.py clean data layer (Kafka swap touches one file)
  - _run_async() bridge with nest_asyncio fallback
  - 409 for duplicate pipeline runs
  - ADR documentation

  Issues present:
  - ESCALATED in ACTIVE_STATUSES (polling bug)
  - sys.path.append(r"C:/lit") hardcoded Windows path in 3 files
  - Tool logic duplicated across agents/tools.py and mcp_server/server.py with no enforcement

  ---
  10. Problem-Solution Fit — 8/10

  Retail inventory management is a real, billion-dollar problem. The days-of-cover formula is the same one Palantir uses in their Retail Command Center product. Capital
  pool management is realistic enterprise logic. The pipeline correctly identifies that only the expensive decision needs a human — the cheap one auto-executes.

  This is not a toy problem dressed up as AI. The domain is genuine.

  ---
  Final Scorecard

  ┌─────────────────────────────┬────────┬─────────────────────────────────────────┐
  │          Parameter          │ Score  │                 Verdict                 │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Agentic Architecture        │ 8/10   │ Current, sophisticated                  │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ RAG Implementation          │ 6/10   │ Architecture right, metrics not passing │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Evaluation Framework        │ 7/10   │ Strongest fresher differentiator        │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ HITL / AI Safety            │ 9/10   │ Best-designed area                      │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Production Engineering      │ 4/10   │ Demo-grade, documented gaps             │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Observability               │ 4/10   │ Weakest area                            │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Cost / Efficiency           │ 5/10   │ Groq free tier, no caching              │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Model Provider Independence │ 7/10   │ Good except CrewAI                      │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Code Quality                │ 6/10   │ Good patterns + known bugs              │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Problem-Solution Fit        │ 8/10   │ Real problem, right approach            │
  ├─────────────────────────────┼────────┼─────────────────────────────────────────┤
  │ Overall                     │ 6.4/10 │                                         │
  └─────────────────────────────┴────────┴─────────────────────────────────────────┘

  ---
  Two Different Questions

  As a fresher demo project: 8.5/10
  There is almost nothing comparable in a fresher portfolio. Most freshers show a chatbot or a fine-tuned sentiment classifier. You have a stateful multi-agent pipeline
  with HITL, hybrid RAG, and a CI eval gate. The evaluator who reviews your resume will notice.

  As a production-ready system: 4/10
  No retry logic, no auth, ephemeral state, failing eval metrics, polling bug. A senior engineer reviewing this for a production deploy would rewrite the infrastructure
  layer before trusting it with real inventory.

  The gap between 4 and 8.5 is not a problem — it's your interview story. You know exactly what's missing and why, and you have the documented upgrade path for every gap.
  That awareness is itself a senior signal.


### Solution
where ever score is lagging do give inputs how to get 10. In detail.                                                                                                     

● Going through each lagging area one by one. Only covering the ones below 8.

  ---
  RAG Implementation: 6 → 10

  Root problem: Context precision 0.20 means 80% of retrieved chunks are noise. Faithfulness 0.667 means the LLM is making claims not supported by what was retrieved.

  Fix 1 — Context Precision (biggest lever)

  Your retriever returns too many irrelevant chunks. Two causes:

  1. Chunk size too large. Large chunks pull in neighbouring text that's off-topic. Experiment with 256-token chunks instead of your current size. Smaller = higher
  precision.
  2. No query rewriting. Agent 3 asks about capital pool limits. The raw query hits BM25 and vector both — but the vector query might drift semantically. Add a query
  rewriting step:
  # Before retrieval: ask LLM to rewrite query for better retrieval
  rewritten = llm.invoke(f"Rewrite this for document retrieval: {raw_query}")
  context = retriever.query_for_agent3(rewritten)

  3. HyDE (Hypothetical Document Embedding). Instead of embedding the question, generate a hypothetical answer and embed THAT. "What does a document about CP003 limits
  look like?" → embed that → retrieve. The hypothesis vector sits closer to the actual document vectors than the question does.

  Fix 2 — Faithfulness (0.667 → target 0.90)

  The LLM is hallucinating claims not in the retrieved context. Fix: add a citation constraint to every agent prompt.

  # Add to every agent system prompt:
  "Answer ONLY using the provided context.
  For every factual claim, end with [SOURCE: chunk X].
  If the answer is not in the context, say: 'Policy document does not address this.'"

  This forces the model to stay grounded. Faithfulness will jump immediately.

  Fix 3 — Expand the corpus

  71 chunks from 5 documents is thin. In production, you'd have supplier contracts, historical order logs, seasonal calendars per region, store-specific policy overrides.
  Even adding 3-4 more realistic policy documents would improve retrieval diversity and give the eval more surface area.

  ---
  Production Engineering: 4 → 10

  Five concrete changes, in priority order:

  1. Fix the ESCALATED polling bug (30 minutes)

  # dashboard/app.py line 161 — change this:
  ACTIVE_STATUSES = {"STARTED", "RUNNING", "ESCALATED"}

  # To this:
  ACTIVE_STATUSES = {"STARTED", "RUNNING"}
  PAUSED_STATUSES = {"ESCALATED"}  # stop polling, show Approve/Reject buttons

  2. Add LLM retry with exponential backoff (1 hour)

  Every Groq rate-limit currently kills the pipeline. One decorator fixes this:

  from tenacity import retry, stop_after_attempt, wait_exponential

  @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
  def call_llm(prompt):
      return llm.invoke(prompt)

  3. Swap SqliteSaver → PostgresSaver (2 hours)

  # One import change
  from langgraph.checkpoint.postgres import PostgresSaver
  checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))

  Render provides a free Postgres instance. Add DATABASE_URL to env. HITL now survives server restarts in production.

  4. Add API key authentication (1 hour)

  Currently anyone who knows your Render URL can trigger a pipeline.

  # FastAPI dependency
  from fastapi.security.api_key import APIKeyHeader

  API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

  async def verify_api_key(key: str = Depends(API_KEY_HEADER)):
      if key != os.getenv("API_KEY"):
          raise HTTPException(status_code=403)

  Add to every route: Depends(verify_api_key).

  5. Fix the hardcoded Windows path (15 minutes)

  # Replace in agents/graph.py, api/main.py, evals/run_retrieval_eval.py:
  import sys, os
  if os.path.exists(r"C:/lit"):          # was always-on
      sys.path.append(r"C:/lit")         # now conditional — safe on Linux/Mac/CI

  ---
  Observability: 4 → 10

  What 10/10 looks like in 2026: Every LLM call traced, every pipeline run costed, failure rate visible on a dashboard, alert fires before the user notices.

  Fix 1 — LangSmith for the live pipeline (not just evals)

  # api/main.py — add to env setup
  os.environ["LANGCHAIN_TRACING_V2"] = "true"
  os.environ["LANGCHAIN_PROJECT"] = "orca-production"

  Every LangGraph node call, every LLM invoke, every tool call now appears in LangSmith with latency and token counts. Free tier is enough for a demo.

  Fix 2 — Per-agent timing in the state

  # Add to AgentState TypedDict:
  agent_timings: dict  # {"agent1": 12.3s, "agent2": 8.1s, ...}

  # In each node:
  import time
  start = time.time()
  # ... agent logic ...
  state["agent_timings"]["agent1"] = round(time.time() - start, 2)

  Now the dashboard can show: "Agent 1: 12s | Agent 2: 8s | Agent 3: 15s". You can see which agent is the bottleneck.

  Fix 3 — Token cost tracking

  # After every LLM call:
  response = llm.invoke_with_usage(prompt)
  cost_usd = (response.usage.input_tokens * 0.00003) + (response.usage.output_tokens * 0.00006)
  state["total_cost_usd"] = state.get("total_cost_usd", 0) + cost_usd

  Show cost on the dashboard per pipeline run. A supply planner seeing "this analysis cost $0.04" builds trust.

  Fix 4 — Structured pipeline logs to the database

  You already have db/pipeline_log.py. Add fields: agent1_latency_ms, agent2_latency_ms, total_tokens, estimated_cost_usd, retrieval_chunks_returned. Now you can run:

  SELECT avg(total_tokens), avg(estimated_cost_usd)
  FROM pipeline_log
  WHERE created_at > date('now', '-7 days')

  Weekly cost and performance trends from one query.

  ---
  Cost / Efficiency: 5 → 10

  Fix 1 — Cache retrieval results

  Same SKU gets analysed multiple times? The RAG retrieval returns the same chunks. Cache it:

  import functools

  @functools.lru_cache(maxsize=256)
  def cached_query_for_agent1(category, abc_class, urgency, event_name):
      return retriever.query_for_agent1(category, abc_class, urgency, event_name)

  lru_cache is in Python's standard library. Zero new dependencies. Retrieval goes from 2-3 seconds to microseconds on cache hit.

  Fix 2 — Streaming responses

  Instead of the dashboard waiting 90 seconds for a complete response:

  # FastAPI endpoint
  @app.get("/pipeline/{run_id}/stream")
  async def stream_pipeline(run_id: str):
      async def event_generator():
          for chunk in graph.stream(state, config):
              yield f"data: {json.dumps(chunk)}\n\n"
      return StreamingResponse(event_generator(), media_type="text/event-stream")

  User sees "Agent 1 complete..." then "Agent 2 complete..." progressively. Same total time, completely different perceived experience.

  Fix 3 — Token budget per agent

  # Limit context sent to each agent
  MAX_CONTEXT_TOKENS = 800  # enough for policy retrieval, not wasteful

  def trim_context(context: str, max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
      # rough token estimate: 1 token ≈ 4 chars
      return context[:max_tokens * 4]

  Prevents one over-loaded retrieval from blowing up cost.

  ---
  Model Provider Independence: 7 → 10

  Fix 1 — Bring CrewAI into the factory pattern

  # agents/llm_factory.py — add:
  def get_crew_llm():
      provider = os.getenv("LLM_PROVIDER", "groq")
      if provider == "groq":
          from langchain_groq import ChatGroq
          return ChatGroq(model=os.getenv("GROQ_CREW_MODEL", "llama-3.3-70b-versatile"))
      elif provider == "openai":
          from langchain_openai import ChatOpenAI
          return ChatOpenAI(model="gpt-4o-mini")

  # agents/crew.py — replace hardcoded model:
  from agents.llm_factory import get_crew_llm
  llm = get_crew_llm()  # was: ChatGroq(model="llama-3.3-70b-versatile") hardcoded

  Fix 2 — Provider health check with fallback

  def get_llm_with_fallback():
      try:
          llm = get_llm()  # primary: Groq
          llm.invoke("ping")  # test call
          return llm
      except Exception:
          # fallback: OpenAI
          from langchain_openai import ChatOpenAI
          return ChatOpenAI(model="gpt-4o-mini")

  Pipeline never fails just because Groq is having an outage.

  ---
  Code Quality: 6 → 10

  Fix 1 — Single source of truth for tools

  The two-file tool problem (tools.py + server.py both define the same 6 tools) will cause drift bugs. Fix: generate one from the other.

  # mcp_server/server.py — the ONLY place tool logic lives
  # agents/tools.py — thin wrappers that import from mcp_server

  # Instead of duplicating logic:
  from mcp_server.server import get_inventory_status as _get_inventory_status

  @tool
  def get_inventory_status(sku_id: str) -> dict:
      """LangChain wrapper for testing."""
      return asyncio.run(_get_inventory_status(sku_id))

  One change in server.py propagates to both paths.

  Fix 2 — Integration tests for API endpoints

  # tests/test_api.py
  from fastapi.testclient import TestClient
  from api.main import app

  client = TestClient(app)

  def test_duplicate_pipeline_returns_409():
      client.post("/api/v1/pipeline/run", json={"sku_id": "SKU-001"})
      resp = client.post("/api/v1/pipeline/run", json={"sku_id": "SKU-001"})
      assert resp.status_code == 409

  def test_escalated_not_in_active_statuses():
      # regression test for the polling bug
      from api.main import ACTIVE_STATUSES
      assert "ESCALATED" not in ACTIVE_STATUSES

  The second test would have caught the polling bug before it reached production.

  ---
  Evaluation Framework: 7 → 10

  Fix 1 — Build Layer 2 LLM-as-judge (the stub)

  The judge needs to verify three things:

  # evals/run_judge_eval.py — replace stub with:
  def judge_formula_correctness(judge, scored_output):
      """Did Agent 3 apply the formula correctly?"""
      prompt = f"""
      Formula: budget_score + availability_score + margin_score - lead_time_penalty
      Agent 3 output: {scored_output}
   
      Verify: does the total score equal the sum of components?
      Does CRITICAL urgency + lead_time > 30 days trigger -20 penalty?
      Score 0.0-1.0.
      """
      return ask_judge_for_score(judge, prompt)

  def judge_class_a_safety(judge, replenishment_options, abc_class):
      """Was Class A partial option correctly excluded?"""
      if abc_class != "A":
          return 1.0  # rule only applies to Class A
      prompt = f"""
      Options offered: {replenishment_options}
      Rule: Class A SKUs must NEVER receive Option B (partial distribution).
      Was this rule respected? 1.0 = yes, 0.0 = no.
      """
      return ask_judge_for_score(judge, prompt)

  Fix 2 — Regression baseline

  # After every eval run, compare against the last known good run:
  if current_composite < baseline_composite - 0.05:
      print(f"REGRESSION: composite dropped from {baseline_composite} to {current_composite}")
      sys.exit(1)

  Catches silent regressions when a prompt change degrades quality.

  ---
  Priority Order If You Have Limited Time

  1 hour   Fix ESCALATED polling bug — highest visible impact, embarrassing in demo
  2 hours  Add LLM retry with tenacity — stops pipeline crashes from rate limits
  2 hours  Fix faithfulness: add citation constraint to all agent prompts
  3 hours  Build Layer 2 judge stubs into real tests
  4 hours  Add LangSmith to live pipeline — immediately shows latency + cost per run
  1 day    PostgresSaver swap — makes HITL actually work on Render
  1 day    Streaming responses — biggest UX improvement
