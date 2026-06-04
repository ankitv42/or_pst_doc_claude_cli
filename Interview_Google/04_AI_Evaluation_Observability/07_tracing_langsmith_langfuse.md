# Tracing: LangSmith & Langfuse

## What Is It? (Plain English)

Tracing is observability for AI systems — it's the mechanism that records exactly what happened inside a pipeline run, including every LLM call made, every input and output, how long each step took, how many tokens were used, and what context was retrieved. Without tracing, debugging an AI pipeline is like debugging a program with no logs — you see the output but have no visibility into what happened in between.

In traditional software, you might add `print()` statements or use a debugger to understand what a function did. AI pipelines are far more complex: they might make 5 LLM API calls, retrieve documents from a vector database, call external tools, and make routing decisions — all before returning a final answer. A single "bad answer" could be caused by a retrieval failure (wrong documents), a prompt failure (wrong instructions), a model failure (LLM ignored the instructions), or a tool failure (external API returned an error). Tracing records the state at each step so you can pinpoint exactly where the pipeline went wrong.

LangSmith (by LangChain) and Langfuse (open-source) are the two most popular tracing platforms for LLM applications. They wrap your LLM calls with transparent instrumentation, send the traces to a centralized dashboard, and give you visual views of the call tree, token usage, latency, and inputs/outputs at every step. Think of them as Datadog or Sentry, but specialized for AI pipelines.

## How It Works

```
Tracing Architecture
──────────────────────────────────────────────────────────────────
Application Code                    Tracing Platform
──────────────────────────────────────────────────────────────────
                                        ┌─────────────────────┐
pipeline_run_id = "abc-123"            │   LangSmith / Langfuse│
                │                      │   ┌─────────────────┐ │
                ▼                      │   │ Run "abc-123"   │ │
 ┌─────────────────────────┐  trace ──►│   │                 │ │
 │ Agent 1: Demand Intel   │  ────────►│   │ Agent 1         │ │
 │  - LLM call (8B model)  │          │   │  input: "..."   │ │
 │  - retrieval: agent1    │          │   │  output: "..."  │ │
 │  - duration: 2.1s        │          │   │  tokens: 847    │ │
 └──────────┬──────────────┘          │   │  latency: 2.1s  │ │
            │                          │   │                 │ │
            ▼                          │   │ Agent 2         │ │
 ┌─────────────────────────┐  trace ──►│   │  input: "..."   │ │
 │ Agent 2: Supply Replen  │          │   │  ...            │ │
 │  - LLM call             │          │   └─────────────────┘ │
 │  - duration: 1.8s        │          │                       │
 └──────────┬──────────────┘          │   Dashboard:           │
            │                          │   Total tokens: 3,241  │
            ▼                          │   Total cost: $0.0023  │
 ┌─────────────────────────┐          │   Total latency: 8.4s  │
 │ Agent 3 + Agent 4       │          │   Status: ESCALATED     │
 └─────────────────────────┘          └─────────────────────────┘
──────────────────────────────────────────────────────────────────
```

**How instrumentation works in LangChain/LangGraph:**

```python
# ORCA-style instrumentation
llm = ChatGroq(model="llama-3.1-8b-instant")

# Attach a run name for every LLM call — shows in trace
response = llm.with_config(run_name="agent_1_demand_analysis").invoke(
    prompt,
    config={"run_id": run_id, "callbacks": [langsmith_tracer]}
)
```

Every `.invoke()` call creates a trace span with: input tokens, output tokens, latency, model name, and the full input/output text. Parent-child relationships between spans (Agent 1 calling retrieval, calling LLM) are automatically captured and visualized as a tree.

## Why Google Cares About This

Google's internal AI pipelines use distributed tracing for every production model serving system. For external-facing AI products built with LangChain or similar frameworks, LangSmith is the standard observability tool. Senior engineers are expected to explain not just "we have logging" but how they would debug a specific type of failure using a trace — for example, how to determine whether a bad answer was caused by retrieval failure versus LLM generation failure. Concrete, tool-specific knowledge signals production experience.

## Interview Questions & Answers

### Q1: Why are print statements insufficient for debugging AI pipelines, and what does a proper trace provide?

**Answer:** Print statements capture information at the time of writing — you print what you think you'll need. For AI pipelines, you don't know in advance what's going to go wrong. The space of failure modes is enormous: a changed document in the vector database affects retrieval; a small prompt change causes the LLM to format its response differently, breaking a downstream parser; a new type of query triggers a code path nobody tested; the external MCP tool returns an unexpected response shape.

With print statements, you'd need to print every LLM input and output, every retrieval result, every tool call and response, every routing decision — which is effectively reinventing tracing from scratch, badly. You'd end up with unstructured log lines that don't capture the hierarchical nature of the pipeline (which agent called which tool), don't record token counts or latency per step, and can't be queried across runs to find patterns.

A proper trace captures the complete execution graph: which node ran when, its full input and output, its latency, any errors it raised, and its relationship to parent and child nodes. In LangSmith's visualization, you see the LangGraph state machine as an interactive tree where you can click on any node and see exactly what context it received, what the LLM was asked, and what it replied. This makes debugging from "the final answer was wrong" to "the LLM generated a wrong answer because it received this specific incorrect context chunk at Agent 2" a matter of minutes rather than hours.

For ORCA specifically, `.with_config(run_name=...)` on every LLM call is CLAUDE.md's documented pattern. This surfaces in LangSmith as named spans — you see "agent_1_demand_analysis", "agent_2_supply_replenishment", "agent_3_capital_allocation" as distinct colored spans with their individual token counts. Without these names, all spans would appear as generic "ChatGroq" calls and it would be impossible to tell which agent made which call.

### Q2: Walk me through how you would debug a specific ORCA failure using a LangSmith trace.

**Answer:** Let's say ORCA is recommending auto-execute for a $52,000 order when it should be escalating for human approval (the threshold is $47,500). The final dashboard shows the recommendation as AUTO_EXECUTE, which is wrong.

Step 1: Open the LangSmith trace for that pipeline run. ORCA logs `run_id` in the pipeline log table, so you look up the run_id from `orca.db` and paste it into LangSmith's search.

Step 2: Examine the Agent 4 routing span. Agent 4 is the pure Python routing node — it reads the `total_cost` from Agent 3's output and routes based on the threshold. Click on the Agent 4 span. What was its input? You see `{"total_cost": 44800, "route": "AUTO_EXECUTE"}`. The routing logic says AUTO_EXECUTE because $44,800 < $47,500 — technically correct!

Step 3: Trace back to Agent 3. If Agent 4 computed correctly, the problem is in the `total_cost` calculation. Open Agent 3's span. You see the LLM's output included: "The capital allocation score leads to a recommended order at the standard tier, total estimated cost: $44,800." But the actual order is for $52,000 worth of items.

Step 4: Look at Agent 3's input (the LangGraph state it received). The state shows `proposed_order_cost: $52,000` in the input from Agent 2. But Agent 3's LLM somehow computed $44,800. This is an LLM computation error — possibly a hallucinated discount calculation.

Step 5: Look at what context Agent 3 retrieved. The retriever span under Agent 3 shows which policy chunks were returned. If the context included a document about "bulk discount tiers" and the LLM applied an incorrect discount, you've found your bug: Agent 3 retrieved a discount policy and incorrectly applied it to reduce the apparent cost below the threshold.

Fix: Add explicit instruction to Agent 3's system prompt: "Use the `proposed_order_cost` exactly as provided in the state. Do not apply any discount calculations — cost adjustments are handled by Agent 2." Verify the fix by checking the next run's trace to confirm Agent 3 now uses the exact cost from state.

This entire debugging process takes under 10 minutes with a proper trace. Without tracing, you'd add print statements, redeploy, reproduce the issue, and manually parse unstructured logs — taking hours.

### Q3: How does LangSmith differ from Langfuse, and when would you choose each?

**Answer:** LangSmith and Langfuse occupy similar spaces (LLM observability platforms) but have different ownership models, integration depth, and feature priorities.

LangSmith is developed by LangChain and has the deepest native integration with the LangChain ecosystem (LangGraph, LangChain expression language, LangServe). If your application is built on LangChain/LangGraph — like ORCA — LangSmith is the natural choice because: automatic tracing works with zero code changes when you set `LANGSMITH_API_KEY` in environment variables, trace metadata (chain names, agent names, tool names) aligns exactly with LangChain's internal concepts, and LangSmith's dataset and evaluation features are tightly integrated with LangChain's eval utilities. The limitation: LangSmith is a proprietary, commercial product. The free tier has usage limits; at scale, it costs money. Data is stored on LangChain's servers, which may be a concern for regulated industries with data residency requirements.

Langfuse is open-source (MIT license) and self-hostable. You can run Langfuse on your own infrastructure, keeping all trace data within your environment. This is critical for healthcare, finance, or government applications where data cannot leave a private network. Langfuse has SDKs for Python, JavaScript, and other languages, and integrates with LangChain, OpenAI, Anthropic, and raw API calls — it's framework-agnostic. The trade-off: more setup complexity (you manage the Langfuse server), less automatic instrumentation depth compared to LangSmith for LangGraph specifically.

The practical decision tree: if you're building on LangChain/LangGraph and don't have data sovereignty requirements, use LangSmith (zero friction, best depth). If you have data residency requirements, are not using LangChain, or need to self-host, use Langfuse. Both support the core use cases: viewing traces, debugging failures, monitoring token usage and costs, and running eval datasets.

For ORCA, LangSmith is the documented choice (CLAUDE.md mentions `.with_config(run_name=...)` patterns consistent with LangSmith). The free tier is sufficient for ORCA's low-volume production use.

### Q4: What metrics should you monitor in a LangSmith trace dashboard for a production RAG system?

**Answer:** A production RAG system monitored via LangSmith should track metrics across three layers: operational metrics, quality metrics, and cost metrics.

**Operational metrics**: Total pipeline latency (end-to-end from trigger to final recommendation) with P50, P95, P99 percentiles. Breaking down by component: retrieval latency, LLM call latency per agent, tool call latency (MCP server). Pipeline success rate: what fraction complete without an exception? For ORCA, tracking the fallback rate (how often does Agent 1 fall back to the raw-data summary due to the CrewAI error) is an important operational signal.

**Quality signals from traces**: LLM call retry rates (if the LLM is returning malformed JSON or errors, the pipeline retries — high retry rates indicate prompt brittleness). HITL routing distribution: what fraction of runs end in ESCALATE vs AUTO_EXECUTE vs SUSPEND? A sudden shift in this distribution (e.g., ESCALATE rate drops from 40% to 5%) may indicate a bug in Agent 3's cost scoring. Token usage per agent: if Agent 1's token count suddenly spikes, it may have received an unexpectedly large context, or a prompt change introduced token inefficiency.

**Cost metrics**: Total tokens per run, broken down by model and agent. If you're on a paid LLM provider, daily cost trends. Token efficiency: are agents using their context wisely, or are prompts filled with boilerplate that wastes tokens? In ORCA's case, Groq is free-tier, so cost monitoring is less critical — but token count monitoring matters because Groq has rate limits.

**Alerting thresholds**: Pipeline success rate drops below 95% → page on-call. P95 latency exceeds 60 seconds → alert. HITL escalation rate drops below 10% for more than 24 hours → alert (suggests routing logic is broken). These thresholds should be set empirically from baseline measurements during normal operation, not guessed.

### Q5: How would you set up end-to-end tracing for ORCA and what gaps exist in the current implementation?

**Answer:** ORCA's current LangSmith integration (as documented in CLAUDE.md) uses `.with_config(run_name=...)` on LLM calls to label each agent's LLM invocation in the trace. This provides basic span-level visibility into LLM call timing and token usage. Setting up the complete integration requires: `LANGSMITH_API_KEY` in `.env`, `LANGSMITH_PROJECT=orca-prod` for project organization, and ensuring the `run_id` from the FastAPI endpoint is threaded through to the LangGraph run configuration as a `thread_id` — so each pipeline run produces a single root-level trace in LangSmith.

Current gaps in the implementation:

Gap 1: Retrieval is not traced. The calls to `query_for_agent1()` etc. inside the LangGraph nodes don't create trace spans. Adding `langsmith.traceable` decorator to each `query_for_agent*()` function would make retrieval latency, retrieval results, and reranker scores visible in the trace. This is essential for debugging retrieval failures.

Gap 2: MCP tool calls are not attributed. When agents call MCP tools (via `mcp_server/server.py`), these show up as subprocess calls in Python — not as properly labeled LangSmith spans. Wrapping MCP calls with `langsmith.traceable` or adding explicit span creation would surface them in the trace tree.

Gap 3: No custom metadata on traces. ORCA doesn't add business-level context to traces: which SKU triggered the run, what the run's routing decision was, whether it required HITL approval, what the final recommendation was. Adding `langsmith.metadata` to each run with these fields enables filtering in the LangSmith dashboard: "show me all traces where routing_decision=ESCALATE and HITL was rejected by the human."

Gap 4: No automated quality scoring pipeline attached to traces. LangSmith supports "feedback" — attaching evaluation scores to individual traces. Running Layer 1 retrieval eval results, faithfulness scores, and HITL approval/rejection outcomes as feedback events on each trace would create a rich quality dataset. Over time, you'd be able to query "show me traces with low faithfulness scores" to find systematic failure patterns.

Addressing these four gaps would transform ORCA's observability from "basic LLM call logging" to "full pipeline observability with quality monitoring" — the standard expected in a production-grade AI system.

## Key Points to Say in the Interview
- Tracing creates a hierarchical record of every step in a pipeline run — inputs, outputs, latency, tokens — enabling root cause analysis
- `.with_config(run_name=...)` on LLM calls names spans in LangSmith, making traces readable instead of a sequence of "ChatGroq" calls
- Debugging with traces: start from the wrong output, trace backwards through the agent tree to find which component produced bad data
- LangSmith for LangChain-native applications; Langfuse for self-hosting or framework-agnostic needs
- Monitor: pipeline success rate, P95 latency, token usage per agent, routing distribution, HITL approval rate
- Retrieval steps should also be traced — retrieval failures are the most common source of bad RAG answers

## Common Mistakes to Avoid
- Not threading run_id through the pipeline (traces become disconnected spans, not linked to a single run)
- Only tracing LLM calls and ignoring retrieval, tool calls, and routing decisions — these are equally important failure points
- Not adding business metadata to traces (SKU ID, routing outcome) — makes it impossible to filter traces by business event
- Using LangSmith only for debugging, not for continuous monitoring — proactive alerting prevents user-facing degradation
- Storing trace data with PII (user names, sensitive business data) in LangSmith without reviewing data retention policies

## Further Reading
- [LangSmith Documentation](https://docs.smith.langchain.com/) — Official docs covering tracing, evaluation, and monitoring for LangChain/LangGraph applications
- [Langfuse Documentation](https://langfuse.com/docs) — Open-source alternative with self-hosting instructions and Python SDK
- [Observability for LLM Applications (Arize blog)](https://arize.com/blog-course/llm-observability/) — Conceptual overview of what observability means for LLM systems vs traditional software
- [LangGraph with LangSmith Tracing](https://langchain-ai.github.io/langgraph/how-tos/langsmith/) — Official guide for integrating LangSmith tracing with LangGraph state machines
- [OpenTelemetry for LLM Applications](https://opentelemetry.io/blog/2024/llm-observability/) — How the open-source OpenTelemetry standard is extending to support LLM trace semantics
