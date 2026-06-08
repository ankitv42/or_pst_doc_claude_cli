# ORCA — Deep-Dive System Narrative (~1000 words)

> Deliver this as a spoken narrative. Pause after each section.
> When the interviewer interrupts, that section is what they want to dig into — stop and answer.

---

## The Full Narrative

The problem I set out to solve is one that every large retailer faces:
you have hundreds of SKUs going critical across dozens of stores simultaneously,
and the people responsible for reordering can't analyse them fast enough.
By the time a supply planner manually reviews sales velocity, checks capital pool
availability, reads the supplier SLA, and writes an approval request — the shelf
is already empty. 

Note: A Vendor SLA (Service Level Agreement) is a formal contract between an organization and an external supplier. It defines the specific services to be provided, the performance standards the vendor must meet, and the penalties or remedies if those standards are not achieved.

ORCA automates that entire analysis loop, end to end, and only
surfaces the decision that genuinely needs a human: whether to approve an expensive
reorder that exceeds the auto-approval threshold.

The data foundation is a continuously updated inventory database. An APScheduler
job depletes stock levels every 60 seconds on demand curves derived from historical
sales velocity, and a risk engine recalculates every 5 minutes using the same
days-of-cover formula that Palantir uses in their Retail Command Center product —
Critical when days_of_cover falls below 50 percent of effective lead time, At Risk
between 50 and 100 percent. 

When a SKU crosses a threshold, it surfaces as an alert
in the dashboard. In a live deployment this scheduler is replaced by a Kafka consumer
pulling from the warehouse management system — the schema contract is identical.

When a supply planner clicks Analyse on an alert, the API returns 202 Accepted immediately with a pipeline ID. 
(An HTTP status code 202 Accepted means the server received and validated your API request, but the actual processing is happening asynchronously in the background)

The actual work runs in a background thread so
the dashboard never freezes. 

The pipeline ID follows the format PIPE_{sku_id}_{date},
one per SKU per day, and the API rejects duplicate runs with a 409 so you can't
accidentally queue the same analysis twice. 
(An HTTP status code 409 Conflict means your request could not be completed because it conflicts with the current state of the server.)

The dashboard polls the state endpoint (we created a STATE end point using FASTAPI)
every 3 seconds while the pipeline is active and stops the moment it completes.

I chose polling over WebSockets deliberately — the pipeline takes 30 to 90 seconds
and the HITL step can wait hours for human approval, so a 3-second polling interval
is too small to get noticed to the user and far simpler operationally than managing persistent
connections on a single-worker deployment. 

I documented this decision as an ADR
along with the upgrade path, which is a FastAPI WebSocket endpoint and a JavaScript
client replacing the autorefresh component.

The pipeline itself is a 4-node LangGraph StateGraph. I chose LangGraph over plain
LangChain for two reasons that I couldn't engineer around: shared mutable state and
interruptible execution. 

In plain LangChain, each agent gets its own context and
you have no reliable way for Agent 3 to read a cost figure that Agent 2 computed.
LangGraph's TypedDict state solves that — every agent reads from and writes back to
the same typed state object. The second reason is the HITL mechanism. LangGraph has
an interrupt_before parameter that tells the graph to pause before a specified node
and persist the entire state to a SQLite checkpoint database. When the human approves
hours later, the graph resumes from the exact checkpoint — same state, same position
in the graph, nothing recomputed. That's one line of configuration to get pause and
resume that survives server restarts.

Agent 1 handles demand intelligence.
---------------------------------------- 
But rather than a single LLM call, it runs
a CrewAI sub-crew — three collaborative agents inside the outer LangGraph pipeline.
A Data Analyst with database tool access pulls position and velocity data. 
A Market Analyst adds business context — upcoming events, category trends. 
A Forecast Strategist synthesises both into a structured demand summary with urgency rating,
projected shortfall, and confidence score. 

There's a known issue here worth mentioning:
CrewAI injects a cache_breakpoint field into the system message for Anthropic's
prompt caching feature, and Groq rejects it with a 422. I diagnosed it by enabling
verbose logging in CrewAI, traced the outgoing message structure, cross-referenced
the CrewAI source code, and patched it by setting is_anthropic=False on the LLM
wrapper, which prevents the injection. When the crew still fails, Agent 1 falls back
to a single LLM call with the same structured output schema so the rest of the
pipeline is unaffected.

Agent 2 builds exactly three replenishment options: 
--------------------------------------------------
standard reorder, 
partial distribution from an existing pool, 
and expedite with a shorter lead time and a higher cost. 

One hard rule is enforced in the prompt: Class A SKUs — the top revenue tier — can never receive the partial distribution option. 

This is a business control,not an AI judgment, and it's expressed explicitly in the system prompt rather than left to the model to infer.

Agent 3 scores all three options
--------------------------------- 
using a formula that is locked into the prompt:
budget score plus availability score plus margin score minus lead time penalty.
Every component is visible in the scored_options output, so a supply planner can
see exactly why Option C ranked higher than Option A — it's not a black box.
Agent 3 also sets an approval_required boolean based on whether the recommended
option's cost exceeds the capital pool's auto-approval limit.

The routing node is pure Python. 
--------------------------------
pure Python, no LLM, no AI. It just reads two values from state and picks a path:
  - Pool pressure HIGH → SUSPEND (stop, don't order, pool is out of budget)
  - approval_required = false → AUTO_EXECUTE (cheap order, just do it)
  - approval_required = true → ESCALATE (expensive, need a human) 
Financial controls cannot be delegated to inference. I documented this in ADR-005.

Agent 4 (hitl_node)
--------------------
Only runs on the ESCALATE path. Its one job is to write a human-readable briefing message — like a well-structured email — that a supply planner will read before clicking
Approve or Reject. It uses an LLM to compose that briefing from all the data Agents 1–3 produced.

Each agent also receives RAG context specific to its role. 
---------------------------------------------------------
The retrieval layer uses hybrid search — BM25 keyword retrieval and vector cosine similarity over 71 policy
chunks, fused with Reciprocal Rank Fusion, then cross-encoder reranked using the
BGE reranker model. 

I also added corrective retrieval: if the top-ranked chunk
scores below a confidence threshold, the retriever automatically retries with a
domain-enriched query. 

Each agent has its own query function with metadata filters so Agent 1 cannot accidentally pull capital pool rules that are only relevant for Agent 3.

The final piece is the evaluation framework.Deep Dive — Evaluation Framewor
----------------------------------------------------------------------------
The core challenge with testing an AI system is that the outputs are                                                                                                   non-deterministic.

I split the testing into two completely separate concerns: 
the parts of the system that ARE deterministic get traditional unit tests via pytest, 
and the parts that are non-deterministic get a statistical eval framework with threshold-based gates. 

+**pytest — the deterministic layer**                                                                                                                                                  
------------------------------
pytest is Python's standard unit testing framework. You write functions starting with `test_`, make assertions, and pytest reports pass or fail.The key insight is identifying what in an AI pipeline is actually deterministic.                                                                                                      
In ORCA, two things never involve an LLM: 
    the Agent 3 scoring formula and the                                                                                                         
    routing logic. Both are pure Python. So I unit-tested both exhaustively.

The scoring tests in `tests/test_scoring.py` implement the exact same formula as the Agent 3 prompt — 
budget_score, availability_score, margin_score, lead_time_penalty — and verify every edge case in isolation. 

There's a test that verifies a CRITICAL urgency SKU with a 31-day lead time gets exactly minus 20 points penalty. There's a boundary test that verifies a lead time of exactly 30 days gets zero penalty — because the rule is greater than 30, notgreater than or equal to. 

There's an anchor case using a real SKU from the database to verify Option A scores higher than Option B under known inputs.                                                                                                           

There's even a test that checks margin_rank=0 raises ZeroDivisionError, 
becausethat's data integrity guarantee the query layer must never violate. 

The routing tests cover the full decision matrix — 22 combinations of  pool_pressure and approval_required — and verify the correct route every time with zero LLM calls. 
Total CI time for the pytest suite: under 10 seconds. 

**The 3-layer eval framework**
-------------------------------
Layer 1 is the retrieval eval. Tests retriever in isolation  — no LLM involved
------------------------------------------------------------
It tests whether the RAG pipeline is surfacing the right policy chunks to the right agents. I wrote 11 golden test cases —  
each one specifies an agent, the query parameters, 
keywords that MUST appear in the returned context (to check context recall), and 
keywords that must NOT appear(to check context precesion). to check context leaking from wrong document type.

This eval runs in CI on every push with no API key and no LLM — the retriever is deterministic given the same query. Gate: 70 percent pass rate AND zero keyword leaks.

Retriever + LLM + quality of generation
---------------------------------------
"Given what the retriever returned, did the LLM produce a faithful,relevant, complete answer?"
A set of 4 standard metrics that the research community uses to evaluate RAG pipelines. 
— faithfulness,
- context recall, 
- context precision, and 
- answer relevance are the standard metrics for RAG systems.

RAGAS the library — a Python package that computes those metrics automatically.

  ▎ "I evaluated RAGAS as the evaluation library. RAGAS works by decomposing each metric into multiple LLM calls — for faithfulness it first extracts atomic claims from the answer, then verifies each
  ▎ claim against the context individually. For context recall it breaks the ground truth into sentences and checks each one


  ▎ "RAGAS's answer relevance metric is the most interesting one architecturally — it doesn't ask the judge 'is this answer relevant?' directly, because LLMs are bad at that self-referential question.
  ▎ Instead it reverse-engineers questions from the answer and measures embedding similarity to the original.


  The 4 RAGAS Metrics in Plain English

  1. Faithfulness (threshold: 0.80)

  ▎ "Did the LLM make up anything, or did it stick to what the retrieved context actually said?"

  The judge reads the retrieved context and the agent's answer. For every claim in the answer, it checks: is this claim supported by the context? If the agent said "Ramadan has 200% uplift" but the
  context says "180% uplift" — faithfulness drops. This catches hallucination.

  Current score: 0.667 — below threshold. One case (CP003 limit) scored 0.0, meaning the agent answer made a claim the retrieved context didn't support.

  2. Context Recall (threshold: 0.75)

  ▎ "Did the retrieved chunks actually contain all the facts needed to answer correctly?"

  The judge compares the retrieved context against the hand-written ground truth answer. If the ground truth says "CP003 limit is AED 20,000 and orders above require approval" — did both those facts
  appear in the retrieved context? This is the silent failure metric. If context recall is low, it means the retriever missed important chunks.

  Current score: 0.667 — below threshold.

  3. Context Precision (threshold: 0.70)

  ▎ "Was the retrieved context relevant, or was it full of noise?"

  The judge reads the question and the context and asks: how much of this context is actually useful for answering the question? If the retriever pulled in a supplier SLA when the question was about a
  capital pool limit — precision drops.

  Current score: 0.200 — significantly below threshold. This is the lowest score in the system. It tells you the retriever is returning relevant content but mixed with a lot of noise.

  4. Answer Relevance (threshold: 0.75)

  ▎ "Did the agent's answer actually address the question that was asked?"

  The judge reads the question and the answer independently. Did the answer stay on topic or did it wander? This catches cases where the agent technically used the context but answered a different
  question.

  Current score: 0.933 — passing. The agent answers are on-point.

 

Layer 2 is LLM-as-judge. 
------------------------ 
An independent LLM(more powerful) evaluates
whether Agent 3's scored output actually follows the formula, 
whether the HITL briefing accurately describes the winner Agent 3 selected, and 
whether Class A safety rules were respected. 

Layer 1 only tests retrieval. It can't tell you whether the LLM used the retrieved context correctly.


Layer 3 is the composite gate that runs on every push to main. 
-------------------------------------------------------------
It reads the JSON output files from Layers 1 and 2 and computes a weighted composite:                                                                                                              

retrieval pass rate at 40 percent, context recall at 30, faithfulness at 20, answer relevance at 10. The composite must reach 0.75 to merge. 
                                                                                                                                                    
The reason I weight retrieval highest is that it's the silent failure zone. If the retriever returns the wrong chunk, every downstream agent is working from wrong information, but none of them will surface an error — they'll just produce a confident-sounding wrong answer. Catching retrieval failures early is the highest-leverage place to spend eval budget.                                                                                                                                          

**How to say it to the interviewer in 30 seconds**                                                                                                                                    

"I split testing into two tracks. Deterministic logic — scoring formula,                                                                                                            
routing matrix — gets pytest with exact assertions and runs in 10 seconds.                                                                                                          
Non-deterministic outputs get a 3-layer eval framework: retrieval correctness                                                                                                       
gated on keyword recall and precision, LLM-as-judge for semantic quality, and                                                                                                       
a composite score above 0.75 to merge. Retrieval is weighted heaviest because                                                                                                       
a bad chunk means confident wrong answers downstream — and no agent will                                                                                                            
tell you the context was wrong."


  The Two-Track Mental Model

  DETERMINISTIC parts          NON-DETERMINISTIC parts
  (same input = same output)   (LLM = different output every run)
           │                              │
           ▼                              ▼
        pytest                    3-layer eval framework
     exact assertions             statistical thresholds
     runs in 10 seconds           runs with API key in CI
           │                              │
     scoring formula               Layer 1: did retriever
     routing matrix                return the RIGHT chunks?
     Class A safety rule           Layer 2: did LLM USE
     boundary conditions           the context correctly?
                                   Layer 3: composite ≥ 0.75
                                   to merge to main
==========================================
Kafka/ pubsub

How to Answer the Interviewer

  ▎ "Currently ORCA uses an APScheduler job that simulates stock depletion every 60 seconds — that's the demo layer. In a production deployment, the WMS publishes stock change events to a Kafka topic
  ▎ or a Pub/Sub topic every time a transaction happens. ORCA runs a consumer that subscribes to that topic and calls the same database update functions the scheduler calls today. The schema contract
  ▎ is identical — the consumer receives a JSON payload with sku_id, store_id, and current_stock, and passes those directly into db/queries.py. I'd choose Kafka if ORCA is deployed on any general
  ▎ cloud or on-premise, because Kafka's offset model means no events are lost even if ORCA restarts mid-processing. I'd choose Pub/Sub if ORCA is on GCP, because it's fully managed — no brokers to
  ▎ configure, no partitions to tune, and it integrates natively with Cloud Run where the API is deployed."

  ---
  The One Line That Shows You've Thought About It

  ▎ "The reason the Kafka/Pub/Sub boundary is clean in ORCA is that I never let raw SQL leak out of db/queries.py. The consumer only calls the same named functions the scheduler calls —
  ▎ update_stock_level, recalculate_risk_score. Swapping the data source is a new file, not a refactor."











---

## One-line version (for when they ask "summarise it in 30 seconds")

> "ORCA is a 4-agent LangGraph pipeline that monitors retail inventory risk,
> runs a CrewAI demand crew inside Agent 1, builds and scores replenishment options
> with a locked formula, routes to human approval or auto-execute via pure Python,
> and retrieves policy context through hybrid BM25 plus vector RAG with BGE reranking —
> all gated by a 3-layer eval framework on every CI push."

---

## Likely follow-up questions after this narrative

| What they ask | Where to go |
|---|---|
| "Tell me more about the async bridge" | `_run_async()` + nest_asyncio — this is Q9 in behavioral doc |
| "How does the HITL checkpoint actually work?" | SqliteSaver + interrupt_before — one line, survives restarts |
| "Why CrewAI inside LangGraph?" | Collaborative inner loop inside deterministic outer pipeline |
| "What happens if the LLM returns bad JSON?" | JSON self-healing: strip markdown fences, ask LLM to fix formula |
| "How do you test something non-deterministic?" | 3-layer eval strategy — retrieval is deterministic, LLM output is not |
| "What would you change at 10x scale?" | PostgresSaver, Redis pipeline store, persistent MCP server, Kafka ingest |
