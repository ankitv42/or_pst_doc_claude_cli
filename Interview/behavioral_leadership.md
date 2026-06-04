# ORCA — 15 Behavioral & Leadership Interview Questions

> **Focus area.** Google-style behavioral questions tied directly to ORCA.
> These questions test engineering judgment, technical decision-making, ownership,
> and communication. Every answer should reference specific design decisions from
> the codebase — vague answers fail at the Senior level.

---

## Q1 — Tell me about a time you had to choose between two competing technical approaches.

### The Prompt to Use
*"Walk me through a technical decision where you had to choose between two valid approaches and explain the reasoning behind your choice."*

### Strong Answer (ORCA framing — STAR format)

**Situation:** ORCA needed to handle the case where the AI pipeline (30–90 seconds)
would block the HTTP connection if run synchronously.

**Task:** Choose how to decouple the pipeline from the API response.

**Two valid approaches compared:**
```
Option 1 — WebSockets (server-push):
  Server pushes status updates as events occur
  Technically elegant, zero polling latency
  Requires persistent connection management
  Complex on Render free tier (connection pooling, reconnect logic)
  Harder to implement correctly with LangGraph's checkpoint model

Option 2 — 202 Accepted + polling:
  API returns immediately with pipeline_id
  Client polls /state every 3 seconds
  Simple to implement and debug
  Works perfectly on free-tier deployment
  Max 3s latency at completion (avg 1.5s) — acceptable for 30-90s process
```

**Action:** Chose polling because:
1. The pipeline takes 30–90 seconds — 3-second polling latency is imperceptible (1.5s avg)
2. Stateless GET requests work perfectly with Render's single worker and SQLite
3. The same pattern handles the HITL pause case naturally — human waits minutes, not milliseconds

**Result:** Implemented in under an hour, zero reconnection issues, and the dashboard
correctly shows live progress as each agent completes.

### Why This Question Works
It tests whether the candidate made a reasoned tradeoff (simpler IS better when
requirements allow it) vs. reaching for complexity.

### Red Flags in the Answer
- "WebSockets are always better" — shows no awareness of deployment constraints
- Can't quantify the latency tradeoff
- Didn't consider the HITL use case (human waiting minutes, not milliseconds)

---

## Q2 — Tell me about a time you caught a potential production issue before it happened.

### The Prompt to Use
*"Describe a situation where you proactively identified a risk or gap in a system you were building."*

### Strong Answer (ORCA framing)

**Situation:** Building Agent 4's HITL briefing, the LLM receives `capital_decision`
JSON with the winning option and is asked to write a human-readable briefing.

**Task:** Ensure the briefing correctly references the winner Agent 3 selected.

**Proactive identification:**
Realised that Agent 4's LLM prompt contained the full `capital_decision` JSON.
The LLM could re-read that JSON and independently decide a "better" option —
effectively overriding Agent 3's decision in the briefing text. A human planner
reading "I recommend Option A" when Agent 3 had scored Option C as the winner would
be approving the wrong option.

**Action:**
1. Pre-extracted the winner in Python before the LLM call:
   ```python
   winner_id = capital_decision.get("recommended", "A")
   winner_summary = f"WINNER — pre-extracted (DO NOT CHANGE): Option {winner_id}..."
   ```
2. Added a post-generation validation check:
   ```python
   if f"Option {winner_id}" not in briefing:
       logger.warning("HITL MISMATCH DETECTED")
   ```

**Result:** The briefing always references the correct winner. The validation check
catches any regression if the prompt changes.

### Why This Question Works
It tests proactive quality thinking — identifying failure modes before they happen.
Pre-extraction is a concrete, code-level answer.

### Red Flags
- Generic answer ("I reviewed the code carefully") without code-specific detail
- Thinks the LLM is always consistent — misses the fundamental non-determinism issue
- No mention of the validation check — one layer of protection is insufficient

---

## Q3 — Tell me about a technical debt decision you made consciously.

### The Prompt to Use
*"Have you ever made a deliberate choice to accrue technical debt? What was the tradeoff?"*

### Strong Answer (ORCA framing)

**Situation:** ORCA's in-memory pipeline store (`_pipeline_store`) was designed
as a Python dictionary with a threading lock.

**The debt:** Everyone knows a Python dict in RAM is not production-grade:
- Lost on server restart
- Can't scale to multiple Render workers
- No TTL (entries accumulate indefinitely in memory)

**Conscious decision:** Used the dict anyway, documented the upgrade path.
```python
# api/main.py comment:
# Upgraded to Redis in Sprint 5
```

**Reasoning:**
1. For the current single-worker Render deployment, the dict works perfectly
2. The checkpoint store (SqliteSaver) handles the persistence requirement — the dict
   is just a fast cache for polling
3. Building Redis integration takes ~3 hours; the dict takes 10 minutes and works now
4. YAGNI — "You Aren't Gonna Need It" until multiple workers are actually needed

**Result:** Working system in the current deployment. The comment serves as a reminder
that this is a known gap, not an oversight.

### Why This Question Works
Senior engineers understand that perfect is the enemy of good. Deliberate tech debt
with a documented upgrade path is fundamentally different from accidental complexity.

### Red Flags
- "I would never take on technical debt" — unrealistic, shows inexperience
- The debt is not documented — accidental, not deliberate
- No upgrade path in mind — "maybe we'll fix it someday"

---

## Q4 — Describe a time you had to simplify a complex technical problem for a non-technical stakeholder.

### The Prompt to Use
*"Give an example of explaining a complex system concept to someone who isn't technical."*

### Strong Answer (ORCA framing)

**Situation:** A supply planning manager asks: "Why does the system take 60 seconds
before I see the approval request? My old system was instant."

**Task:** Explain the AI pipeline without losing the manager or oversimplifying.

**The explanation used:**

"Think of it like ordering a meal at a restaurant. You press 'Analyse' — that's
like handing your order to the waiter. The waiter immediately gives you a receipt
(your pipeline ID) and goes to the kitchen. You don't wait at the counter — you
sit down and the app checks in with the kitchen every 3 seconds.

In the kitchen, 4 specialists are working: the demand analyst looks at how much
stock is left and how fast it's selling. The replenishment specialist builds 3
options for restocking. The financial analyst scores each option against your
budget rules. Then the system decides if it needs your sign-off.

When it needs your approval, it's because the cost is above your auto-approve
limit — that's the policy you set. The 60 seconds is actually 4 AI agents
thinking through your inventory problem — much faster and more thorough than
any human could do manually."

**Result:** Manager understood why the delay has value, and started asking
"what are the 4 agents checking?" — turned into a productive conversation about
improving the urgency rules.

### Why This Question Works
Communication ability is explicitly evaluated at Google Senior level. Candidates
who can only talk to engineers are limited in impact.

### Red Flags
- Overly technical (talks about LangGraph, MCP) — loses the audience
- Too simple ("AI is just doing math") — undersells the value
- No analogy — analogies are the most effective communication tool for abstraction

---

## Q5 — Tell me about a time a system you built failed in a way you didn't anticipate.

### The Prompt to Use
*"Describe a time a bug or failure surprised you. How did you diagnose and fix it?"*

### Strong Answer (ORCA framing)

**Situation:** During Agent 1's development, the pipeline crashed with:
```
NotImplementedError: StructuredTool does not support sync invocation
```

**Unexpected aspect:** The MCP tools were converted to LangChain `StructuredTool` objects
by `langchain-mcp-adapters`. These look like regular LangChain tools. The code called
`.invoke()` on them — standard LangChain API. It shouldn't fail.

**Diagnosis:**
MCP tools, even after conversion, retain their async-only nature internally.
`langchain-mcp-adapters` wraps them but doesn't implement sync `.invoke()`.
The adapter documents this — `ainvoke()` only.

The deeper problem: LangGraph nodes are synchronous `def` functions. Calling async
tools inside them required the `_run_async` bridge.

**Fix:** Two changes:
1. Made `_call_mcp_tool` async and changed all calls to `.ainvoke()`
2. Created per-node `async def _agentN_fetch()` helpers to group all async calls
   in one coroutine, called once via `_run_async()`

**Result:** Stable pipeline. The pattern was documented explicitly:
```python
# FIX 1, FIX 2, FIX 3 comments in graph.py
```

**What I learned:** Don't assume library wrappers faithfully implement the full
interface. Test async/sync boundaries explicitly, especially with adapter layers.

### Why This Question Works
The bug is specific, the diagnosis is systematic, and the learning is generalizable.
Vague "I fixed a bug" answers fail at Google.

### Red Flags
- No specific bug — generic "things always go as planned"
- Can't explain WHY the fix worked (not just what was changed)
- No documented learning — suggests the lesson wasn't internalised

---

## Q6 — Tell me about a time you had to make a design decision without complete information.

### The Prompt to Use
*"Sometimes you have to ship without knowing if a decision is optimal. Give an example."*

### Strong Answer (ORCA framing)

**Situation:** Designing the RAG pipeline's `RETRIEVE_TOP_K=10` and `FINAL_TOP_K=3`
constants. These numbers significantly affect retrieval quality.

**Unknown information:** ORCA had 71 chunks at the time. The "right" values depend
on chunk size distribution, query diversity, and reranker quality — none of which
were measured yet.

**Decision with incomplete info:**
Used literature defaults: `top_k=10` for candidate retrieval, `top_k=3` for final
context. These are widely cited in RAG papers as starting points.

Reasoning:
- 10 candidates: large enough buffer that the correct chunk is almost always included
- 3 final chunks: small enough that the context doesn't overwhelm the 8K token window
- Can always tune later if eval results show recall < 70%

**What I built to validate it:**
Layer 1 evals with `must_contain` assertions — if the correct chunk isn't reaching
the agent, the eval fails and the constants need adjustment.

**Result:** 11 golden cases pass at ≥70% — indicating the defaults are reasonable.
The constants are named (not magic numbers) so adjusting them is a one-line change.

### Why This Question Works
Senior engineers ship with appropriate defaults and build the measurement infrastructure
to validate them later. They don't over-optimise prematurely.

### Red Flags
- "I always research the optimal value first" — unrealistic for all decisions
- Used magic numbers without naming the constants (makes tuning harder)
- Built no validation mechanism — can't tell if the defaults are wrong

---

## Q7 — How do you approach testing in an AI system where outputs are non-deterministic?

### The Prompt to Use
*"Traditional software has deterministic tests. AI systems don't. How do you test them?"*

### Strong Answer (ORCA framing)

**The core insight:** Test the deterministic parts in CI; test the non-deterministic
parts with statistical assertions and human review.

**ORCA's three-layer strategy:**

**Layer 1 — Test what's deterministic:**
```python
# Retrieval is deterministic (same query → same embedding → same vector search result)
context = retriever.query_for_agent3(category="Electronics", ...)
assert "auto_approve_limit" in context  # always either in or not — no randomness
```
→ Runs in CI on every push, no API key, ~30 seconds.

**Layer 2 — Test with assertions that tolerate variance (planned):**
```python
# LLM-as-judge: does the output meet semantic criteria?
# "Does the HITL briefing contain an approval deadline?" (yes/no, not exact text)
# This is threshold-based, not exact-match
```
→ Runs offline, costs ~$0.01 per check on free Groq tier.

**Layer 3 — Human evaluation (planned):**
```
Monthly: operations team reviews 10 random pipeline completions
Did the system recommend the right option?
Were the capital scores plausible?
Was the HITL briefing clear and accurate?
```
→ Ground truth from domain experts.

**The principle:** You can test AI systems; you just test differently.
Retrieve → score → decide → generate: each step can be tested with appropriate
assertions for its determinism level.

### Why This Question Works
This is a high-signal question at Google. Most junior candidates say
"you can't really test AI" — which is wrong. Senior candidates have a strategy.

### Red Flags
- "You can't test AI" — immediately signals junior thinking
- "Just use unit tests on the prompts" — doesn't account for non-determinism
- No distinction between retrieval (deterministic) and LLM output (non-deterministic)

---

## Q8 — Describe a time you had to balance feature completeness against shipping deadlines.

### The Prompt to Use
*"What did you cut from ORCA and why, and how did you decide it was okay to cut it?"*

### Strong Answer (ORCA framing)

**Cut 1 — Layer 2 LLM-as-judge eval (HIGH priority gap, accepted):**
Building the judge eval would take ~2 days. The retrieval eval (Layer 1) already
provides meaningful CI signal. The risk of shipping without Layer 2 is that
LLM reasoning errors slip through — accepted because:
- A human (supply planner) is in the loop for all expensive orders
- The retrieval eval catches the most common failure (wrong context → wrong decision)
- The gap is documented as a Known Issue

**Cut 2 — Redis for pipeline store (accepted for now):**
SQLite + in-memory dict works fine for single-worker Render deployment.
Redis integration would take ~3 hours and adds a Redis Cloud dependency.
Accepted because the current deployment is single-worker by design.

**Cut 3 — Automatic retry on LLM failure (known gap):**
Tenacity integration takes ~1 hour but every other change was happening simultaneously.
The fallback (mark as FAILED, user retries manually) is functionally correct.
Accepted because Groq's free tier has a higher reliability than expected.

**Framework used:**
For each cut: (a) what is the probability and impact of the missing feature failing?
(b) is there a human backstop? (c) is it documented?
If probability × impact is low and it's documented → cut is acceptable.

### Why This Question Works
Senior engineers own the whole system — they make conscious cuts, not silent omissions.
Every cut in ORCA is documented in CLAUDE.md Known Issues.

### Red Flags
- "I didn't cut anything" — they clearly didn't ship
- Cuts are not documented — leads to future engineers stepping on the same traps
- No framework for the cut decision — sounds random rather than principled

---

## Q9 — Tell me about the most complex system interaction you designed.

### The Prompt to Use
*"What's the most technically complex interaction in ORCA and how did you design it?"*

### Strong Answer (ORCA framing)

**The most complex:** The async/sync bridge between LangGraph nodes and MCP tools.

**Why it's complex:**
```
FastAPI event loop (async) ──► BackgroundTasks thread pool (sync)
                                         │
                                   LangGraph node (sync def)
                                         │
                                   MCP tool call (async — subprocess I/O)
                                         │
                               asyncio.run() vs nest_asyncio
                               (two different environments)
```

Three incompatible execution contexts need to interact:
1. FastAPI's async event loop
2. A synchronous background thread (LangGraph)
3. An async subprocess I/O call (MCP)

**Design decisions:**
1. One `async def _agentN_fetch()` per node — all async calls in ONE coroutine
2. `_run_async(coro)` bridge: `asyncio.run()` first (for direct calls),
   `nest_asyncio` fallback (for FastAPI context where a loop already exists)
3. Each MCP call returns content blocks — parsed in `_call_mcp_tool` before returning

**How I validated it works:**
```python
python agents/graph.py    # direct execution — uses asyncio.run()
uvicorn api.main:app      # FastAPI context — uses nest_asyncio
```
Both paths tested explicitly.

### Why This Question Works
This is the hardest technical problem in ORCA. A candidate who can explain the
three-context interaction has truly understood the system.

### Red Flags
- Picks something simpler (HITL mechanism, routing logic) — shows they avoid complexity
- Can't explain WHY two different async paths are needed
- "I found code online that worked" — no understanding of WHY it works

---

## Q10 — How do you approach designing a system to be auditable for financial decisions?

### The Prompt to Use
*"ORCA makes financial recommendations. How did you ensure the system is auditable?"*

### Strong Answer (ORCA framing)

**Three properties of a financially auditable AI system:**

**1. Every decision is traceable to its inputs:**
```python
save_pipeline_run(
    pipeline_id      = ...,
    demand_summary   = state.get("demand_summary"),   # Agent 1's full reasoning
    options_package  = state.get("options_package"),  # Agent 2's full 3 options
    capital_decision = state.get("capital_decision"), # Agent 3's scores + winner
    hitl_briefing    = state.get("hitl_briefing"),    # what the human read
    reviewed_by      = body.reviewer,                 # WHO approved
    reviewed_at      = reviewed_at,                   # WHEN they approved
)
```
Not just "order placed" — the entire reasoning chain is stored.

**2. Hard constraints are enforced in code, not just in prompts:**
```python
# In agents/prompts.py — Agent 2:
"HARD RULE — Class A SKUs: Option B is NEVER available"
# In agents/graph.py — route_node:
if pool_pressure == "HIGH":
    route = "SUSPEND"
elif not approval_required:
    route = "AUTO_EXECUTE"
else:
    route = "ESCALATE"
```
Routing logic is pure Python — deterministic and verifiable.

**3. Approval is immutable and attributed:**
```python
reviewed_by = body.reviewer   # "priya.sharma@retailco.ae"
reviewed_at = "2026-06-04T14:32:11Z"
```
A specific person approved a specific amount at a specific time. This is audit evidence.

**Finance could reconstruct any decision:** Query `pipeline_log` for `pipeline_id`,
read the demand_summary → options_package → capital_decision → hitl_briefing.
See exactly which agent recommended what, and who approved it.

### Why This Question Works
Auditability is a real enterprise requirement, especially in finance and supply chain.
Most junior candidates don't think about it until asked.

### Red Flags
- "We log everything" — logging != auditability; the audit trail must be queryable
- Doesn't mention the `reviewed_by` / `reviewed_at` fields
- No mention of storing the full reasoning chain (most systems only store the outcome)

---

## Q11 — Tell me about a time you identified a gap in a third-party library and worked around it.

### The Prompt to Use
*"Have you ever been blocked by a bug or limitation in a library you were using? How did you handle it?"*

### Strong Answer (ORCA framing)

**Library:** CrewAI's LLM message builder.

**Gap:** CrewAI injects `cache_breakpoint` into the system message before sending
to the LLM API. This is an undocumented internal field used for Anthropic's
prompt caching feature. Groq's API doesn't recognise it and returns 422.

**Diagnosis process:**
1. Saw error: `422 Unprocessable Entity` on every CrewAI call
2. Enabled verbose logging in CrewAI: `crew = Crew(..., verbose=True)`
3. Saw the outgoing message included `cache_breakpoint: ...` in the system field
4. Cross-referenced CrewAI source code: `crewai/llm.py` injects it for Anthropic
5. Found that `is_anthropic=False` on the `LLM` wrapper prevents injection

**Workaround:**
```python
# agents/crew.py
def _get_crew_llm() -> LLM:
    return LLM(
        model        = "groq/llama-3.3-70b-versatile",
        api_key      = os.getenv("GROQ_API_KEY"),
        temperature  = 0,
        is_anthropic = False,  # ← prevents cache_breakpoint injection
    )
```

**Result:** The workaround is the current recommended fix. The issue is
documented in CLAUDE.md as a Known Issue with the fix approach noted.

**Alternative if the workaround failed:** Patch CrewAI's message builder directly
via monkey-patching or fork the repo.

### Why This Question Works
Library bugs are common at the frontier of AI tooling (2024–2025 stack).
Senior engineers diagnose them systematically and either fix or work around.

### Red Flags
- "I reported the bug and waited" — unacceptable for a production blocker
- Can't explain what `cache_breakpoint` is or WHY it causes the failure
- Went straight to "replace the library" without trying to fix the issue

---

## Q12 — How do you communicate technical risk to stakeholders?

### The Prompt to Use
*"ORCA has several Known Issues documented. How would you communicate these to a business stakeholder considering deploying it?"*

### Strong Answer (ORCA framing)

**ORCA's Known Issues ranked by business impact:**

```
High business impact — must discuss upfront:
1. CrewAI fallback always runs (Agent 1 uses single LLM instead of 3-agent crew)
   Business impact: Demand forecasts are less sophisticated
   Mitigation: System still works; crew_insights field is empty but other fields are complete
   Timeline to fix: 1 sprint — already have the is_anthropic=False workaround identified

2. No automatic retry on LLM failure
   Business impact: Pipeline fails if Groq is briefly unavailable; user must retry
   Mitigation: Alert is not lost — just needs manual re-trigger
   Timeline to fix: 2 hours — tenacity integration is straightforward

Lower business impact — mention but don't alarm:
3. No pytest unit tests on agents/tools
   Impact: Changes could introduce subtle bugs without immediate detection
   Mitigation: Layer 1 eval catches retrieval regressions; manual testing covers major flows

4. Hardcoded Windows path (C:/lit)
   Impact: Breaks on non-Windows deployment
   Mitigation: Only affects developers, not users; trivial to fix
```

**Communication format:**
Each issue has: (a) what is affected, (b) what works despite the issue, (c) the fix.
Business stakeholders need to know "will it break my operation?" — not the technical cause.

### Why This Question Works
Risk communication distinguishes senior engineers from individual contributors.
Being specific about impact and mitigation is far more useful than "it has some bugs."

### Red Flags
- "It's basically production-ready" — overstatement without acknowledging gaps
- "It has a lot of issues" — understates working functionality without quantifying risk
- Can't prioritise the issues by business impact

---

## Q13 — Tell me about a time you over-engineered something and what you learned.

### The Prompt to Use
*"Engineers sometimes build more complexity than needed. Give an example from your own work."*

### Strong Answer (ORCA framing)

**What might have been over-engineered:**
The BM25 index in ORCA is implemented from scratch — custom `BM25Index` class with
IDF computation, inverted index, and TF-BM25 scoring.

Python has `rank_bm25` library that implements this in 3 lines:
```python
from rank_bm25 import BM25Okapi
bm25 = BM25Okapi([doc.split() for doc in corpus])
scores = bm25.get_scores(query.split())
```

**Why it was built from scratch:**
1. Learning: Understanding BM25 mechanics deeply matters for debugging retrieval
2. Control: Custom tokeniser (regex-based, no stopword list) vs rank_bm25's default
3. Cache key: The custom implementation integrates cleanly with ChromaDB's doc_types
   for per-agent BM25 indexes

**What was learned:**
The custom implementation is correct and performs identically to rank_bm25 on our
test cases. But if the project needed to add BM25 for a second corpus (e.g., product
reviews), maintaining the custom class would cost developer time.

**The lesson:** Build from scratch when (a) understanding the algorithm is important for
your system or (b) the library doesn't support your exact interface. Otherwise, use
the library and write tests.

### Why This Question Works
Self-awareness about complexity decisions is a senior-level skill. This answer
is honest without being self-deprecating.

### Red Flags
- "I never over-engineer" — dishonest
- Can't identify a specific example in their own work
- Defends the complexity without acknowledging the tradeoff

---

## Q14 — How do you ensure that AI system decisions are explainable to end users?

### The Prompt to Use
*"A supply planner asks: 'Why did the system recommend Option C instead of Option A?' How does ORCA answer that question?"*

### Strong Answer (ORCA framing)

ORCA has three layers of explainability:

**Layer 1 — Scored options table (structured):**
```
Agent 3 output — pipeline_log.capital_decision:
Option A: budget_score=22.1, availability_score=38.4, margin_score=6.7, total=67.2
Option B: ELIMINATED (Pool CP001 pressure HIGH)
Option C: budget_score=14.1, availability_score=40.0, margin_score=6.7, total=60.8
            + lead_time_penalty=0 (CRITICAL but lead_time=7d < 30d)
Recommended: Option A (score 67.2)
```
Every number is traceable to its formula component.

**Layer 2 — HITL briefing (human-readable):**
```
HITL briefing says:
"Option A RECOMMENDED (score 67.2). Option B ELIMINATED — Pool CP001 at HIGH pressure.
Option C viable but lower score (60.8) due to higher expedite cost reducing budget_score."
```
Plain English explanation of the same decision.

**Layer 3 — Full reasoning chain (audit):**
```
pipeline_log stores:
  demand_summary   — WHY the urgency was HIGH (9 critical stores, event approaching)
  options_package  — HOW the options were built (order quantities, lead times)
  capital_decision — HOW options were scored (each component shown)
  hitl_briefing    — WHAT the human was told
```

**What ORCA can't yet explain:**
- Why Agent 1 rated urgency as HIGH vs CRITICAL (the LLM's internal reasoning)
- Why the LLM chose specific wording in the briefing

These are the limits of current LLM explainability — a known gap.

### Why This Question Works
Explainability is a business requirement in regulated industries. A candidate
who has thought through multiple layers (structured data, plain text, audit log)
vs just "the LLM explains itself" is production-ready.

### Red Flags
- "The LLM explains its reasoning in the response" — LLM self-explanations are not reliable
- Only mentions the HITL briefing, not the scored options table
- No acknowledgment of the limits (Agent 1's reasoning is still a black box)

---

## Q15 — What would you do differently if you were starting ORCA from scratch today?

### The Prompt to Use
*"With the benefit of hindsight, what architectural or implementation decisions would you change?"*

### Strong Answer (ORCA framing)

**Change 1 — Layer 2 eval first, not last:**
The LLM-as-judge eval should have been built early — alongside the prompts — not
left as a stub. Without it, prompt changes in sprint 3 could introduce regressions
that only appear in production, not in CI. Evaluation infrastructure is load-bearing
infrastructure, not a nice-to-have.

**Change 2 — Use LangGraph Studio from the start:**
LangGraph has a visual debugger (Studio) that shows graph state at each node.
Running `python agents/graph.py` and reading logs is slower for debugging
than seeing the state machine visually. Not using Studio added 30–40% to debug time.

**Change 3 — Separate tool definitions from test mocks earlier:**
The two-file tool pattern (`agents/tools.py` for testing, `mcp_server/server.py` for runtime)
emerged organically. Enforcing this boundary from day 1 — with a lint rule preventing
`agents/tools.py` from being imported in non-test code — would have prevented confusion.

**What I would NOT change:**
- The polling + 202 Accepted pattern — still the right tradeoff
- SQLite for current scale — premature optimisation to PostgreSQL from the start
- The `_run_async` bridge approach — the alternative (all-async LangGraph nodes)
  would require rewriting the graph framework

**The meta-lesson:** Build the observable infrastructure (evals, logging) before the
agent logic, not after. You can't improve what you can't measure.

### Why This Question Works
Retrospective thinking shows a growth mindset and honest self-assessment. Google
explicitly values engineers who learn from experience rather than defending
every past decision.

### Red Flags
- "I wouldn't change anything" — no growth mindset
- Changes every architectural decision (shows no confidence in original reasoning)
- No mention of the eval gap — the most significant learning for AI systems

---

## Scoring Guide for Interviewers

| Score | What It Means |
|---|---|
| STAR answers with specific code/system references | Strong hire — owns what they built |
| Good narrative, weak on technical specifics | Solid hire — may have been more user than author |
| Generic answers ("I learned to communicate better") | Caution — surface-level behavioral prep |
| No specific examples from ORCA | Red flag — may not have built the system they're describing |

**Questions that most differentiate senior candidates:**
- Q2 (proactive issue identification — pre-extraction pattern)
- Q7 (testing strategy — deterministic vs non-deterministic distinction)
- Q10 (auditability — financial system requirements)
- Q11 (library bug diagnosis — systematic vs guessing)
- Q15 (retrospective — honest self-assessment with specific changes)
