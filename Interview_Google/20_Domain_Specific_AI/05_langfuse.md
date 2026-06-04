# Langfuse: Open-Source LLM Observability

## What Is It? (Plain English)

Langfuse is an open-source alternative to LangSmith for observing, evaluating, and managing LLM applications. While LangSmith is tightly integrated with the LangChain ecosystem, Langfuse is provider-agnostic — it works with any LLM API (OpenAI, Anthropic, Groq, self-hosted models) and any orchestration framework, not just LangChain. You can instrument a plain Python script that calls OpenAI directly, a Haystack pipeline, a CrewAI crew, or a LangGraph graph.

Langfuse offers the same core capabilities as LangSmith — traces, evaluations, prompt management — but adds fine-grained cost tracking, a self-hosted deployment option (via Docker), and an open-source codebase you can inspect, extend, and contribute to. The self-hosted option is particularly important for organisations with data residency requirements: all trace data stays in your own infrastructure.

The trade-off: Langfuse requires slightly more explicit instrumentation. LangSmith's automatic capture via environment variables works because LangChain's callback system handles it transparently. Langfuse uses an SDK that you wrap around your LLM calls. For applications already in LangChain, both are easy. For non-LangChain applications, Langfuse is simpler.

## How It Works

```
LANGFUSE TRACE HIERARCHY
═══════════════════════════════════════════════════════════════════
A trace represents one complete interaction (e.g., one ORCA pipeline run)

Trace: orca_pipeline_run_abc123
  │
  ├── Span: agent1_node (start, end, metadata)
  │     └── Generation: llm_call (model, input, output, tokens, cost)
  │
  ├── Span: agent2_node
  │     └── Generation: llm_call
  │
  ├── Span: agent3_node
  │     └── Generation: llm_call
  │
  └── Span: route_node
        └── Event: route_decision (route=ESCALATE)

LANGFUSE SDK INSTRUMENTATION:
──────────────────────────────────────────────────────────────────
from langfuse import Langfuse
langfuse = Langfuse()          # reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
                               # from environment

trace = langfuse.trace(        # one per pipeline run
    name="orca_pipeline",
    user_id=user_id,
    metadata={"sku_id": sku_id, "run_id": run_id}
)

with trace.span("agent1_node") as span:
    generation = span.generation(
        name="demand_llm_call",
        model="llama-3.1-8b-instant",
        input=formatted_prompt,
    )
    response = llm.invoke(formatted_prompt)
    generation.end(output=response.content, usage={
        "input": response.usage_metadata["input_tokens"],
        "output": response.usage_metadata["output_tokens"]
    })
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Langfuse is widely adopted in enterprise AI deployments, particularly where data privacy or self-hosting is required. Google Cloud customers building AI on Vertex AI often use Langfuse for observability because it can be self-hosted on GKE with all trace data staying within the customer's GCP project. Senior AI engineers are expected to know both LangSmith and Langfuse, understand the trade-offs, and be able to justify the choice for a given deployment context. Demonstrating Langfuse knowledge also signals awareness of the broader AI infrastructure ecosystem beyond Anthropic/LangChain-specific tooling.

## Interview Questions & Answers

### Q1: What are the key differences between LangSmith and Langfuse? When would you choose one over the other?

**Answer:** Both tools provide LLM observability — traces, evaluations, prompt management, cost tracking. The meaningful differences are in architecture, ecosystem integration, and data control.

**LangSmith:**
- Tightly integrated with LangChain/LangGraph — automatic instrumentation via environment variables
- Cloud-only (Langchain Inc. processes your trace data)
- Evaluation framework built around LangChain's `evaluate()` function
- Prompt Hub versioning
- Better UI for debugging LangGraph-specific traces (shows graph state transitions)

**Langfuse:**
- Framework-agnostic — works with any Python LLM code, not just LangChain
- Cloud OR self-hosted (Docker compose, Helm chart for Kubernetes)
- Explicit SDK instrumentation (slightly more code, but more control)
- Open source (MIT license — you can inspect, fork, and extend)
- Scores/feedback API for custom evaluation workflows
- Better cost tracking UI (attribution by model, project, user)

```
DECISION MATRIX:
═══════════════════════════════════════════════════════════════════
Choose LangSmith if:
  ✓ Your application is built on LangChain/LangGraph
  ✓ You want zero-instrumentation automatic tracing
  ✓ Data residency is not a constraint
  ✓ You want the best LangGraph debugging experience

Choose Langfuse if:
  ✓ Your application uses non-LangChain frameworks (Haystack, CrewAI direct, custom)
  ✓ Data residency requirements (self-host in your own infrastructure)
  ✓ Open source requirement (compliance, auditability, or preference)
  ✓ Cost tracking is a priority feature
  ✓ You want to avoid per-seat SaaS pricing at scale
═══════════════════════════════════════════════════════════════════
```

For ORCA running on Render: LangSmith is the pragmatic choice because ORCA uses LangChain/LangGraph throughout. For a financial services company deploying AI on GKE with strict data residency: Langfuse self-hosted is the better choice.

---

### Q2: How do you instrument a Python AI application with the Langfuse SDK? Show a complete working example.

**Answer:** Langfuse's SDK uses a decorator-based or context manager-based approach. The most ergonomic pattern for an existing codebase is the context manager approach, which wraps existing code without requiring architectural changes.

```python
import os
from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe

# Initialize once (reads env vars: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST)
langfuse = Langfuse()

# Decorator approach — minimal code change, auto-traces the function
@observe(name="demand_intelligence_agent")
def run_agent1(state: dict) -> dict:
    """Agent 1 runs inside this automatically traced function."""
    # All LLM calls inside here are automatically captured if using LangChain
    # with LANGCHAIN_CALLBACKS environment variable
    analysis = call_llm_for_demand(state)
    
    # Add custom metadata to the current trace
    langfuse_context.update_current_observation(
        metadata={
            "sku_id": state["sku_id"],
            "urgency": analysis.get("urgency"),
        },
        tags=["agent1", "demand"]
    )
    return {"demand_analysis": analysis}

# Manual SDK approach — more control, for non-LangChain code
def run_pipeline_with_tracing(sku_id: str, run_id: str) -> dict:
    # Create a trace (one per pipeline run)
    trace = langfuse.trace(
        name="orca_pipeline",
        id=run_id,                     # use run_id as trace ID for correlation
        user_id="system",
        session_id=f"daily_run_{date.today().isoformat()}",
        metadata={"sku_id": sku_id, "version": "1.0.0"}
    )

    # Create spans for each major phase
    agent1_span = trace.span(name="agent1_demand_intelligence", input={"sku_id": sku_id})

    # Create a generation for the LLM call
    generation = agent1_span.generation(
        name="groq_demand_call",
        model="llama-3.1-8b-instant",
        model_parameters={"temperature": 0.1, "max_tokens": 512},
        input=[{"role": "system", "content": AGENT1_SYSTEM_PROMPT},
               {"role": "user", "content": build_demand_user_prompt(sku_id)}],
    )

    # Make the actual LLM call
    response = llm.invoke(formatted_prompt)

    # End the generation with output and token usage
    generation.end(
        output=response.content,
        usage={"input": response.usage_metadata["input_tokens"],
               "output": response.usage_metadata["output_tokens"],
               "unit": "TOKENS"}
    )

    agent1_span.end(output=parse_demand(response.content))
    # ... repeat for agent2, agent3 spans
    
    trace.update(output={"route": final_route, "run_id": run_id})
    langfuse.flush()   # ensure all events are sent before process exits
    return result
```

The `id=run_id` pattern is important — it ties the Langfuse trace to ORCA's own run_id, allowing correlation between the Langfuse trace and the pipeline log in the SQLite database.

---

### Q3: How do scores work in Langfuse? How would you use them to build an online evaluation system?

**Answer:** Scores in Langfuse are numeric or categorical ratings attached to a trace or a specific generation. They represent quality assessments — either from humans (the HITL approver rated the recommendation) or from automated evaluators (an LLM-as-judge assessed the reasoning quality).

```python
# Human score — from the HITL approval decision
def record_hitl_decision(run_id: str, approved: bool, rejector_reason: str | None):
    # Langfuse trace ID = run_id (we set this at trace creation)
    langfuse.score(
        trace_id=run_id,
        name="human_approval",
        value=1 if approved else 0,
        comment=rejector_reason or "Approved without comment",
        data_type="BOOLEAN"
    )

# Automated score — LLM-as-judge for reasoning quality
def evaluate_agent3_reasoning(run_id: str, capital_decision: dict) -> float:
    judge_prompt = f"""
    Rate the quality of this capital allocation decision on a scale of 0-1.
    Decision: {capital_decision}
    Criteria: Is the reasoning sound? Are the scores plausible?
    Return only a float between 0 and 1.
    """
    score_str = judge_llm.invoke(judge_prompt).content.strip()
    score = float(score_str)
    
    langfuse.score(
        trace_id=run_id,
        name="capital_decision_quality",
        value=score,
        data_type="NUMERIC"
    )
    return score
```

In Langfuse's UI, scores become queryable dimensions — you can see all traces where `human_approval = 0` and `capital_decision_quality > 0.8` (rejected by human but agent thought the decision was good — a signal of misalignment). This is powerful for discovering systematic failure modes.

Online evaluation workflow:
1. Every pipeline run creates a Langfuse trace (with `id=run_id`)
2. When the HITL decision is made, record it as a score on the trace
3. Periodically run the LLM-as-judge evaluator over recent traces
4. Langfuse dashboard shows quality trends over time
5. When a quality dip is detected, drill into the low-scoring traces to find the root cause

---

### Q4: How do you interpret a Langfuse trace for a RAG pipeline? What are the most useful things to look at?

**Answer:** A RAG pipeline trace in Langfuse has three critical sections: the retrieval span, the generation, and the output. Debugging RAG failures requires understanding which section went wrong.

```
LANGFUSE TRACE FOR RAG PIPELINE
══════════════════════════════════════════════════════════════
Trace: rag_query_run_xyz789                     Total: 2.8s
  │
  ├── Span: retrieval                           0.4s
  │     Input: "What is the reorder policy for Class A?"
  │     Output: [
  │       {score: 0.89, doc: "Class A items require dual approval..."},
  │       {score: 0.71, doc: "Emergency procurement procedures..."},
  │       {score: 0.68, doc: "Standard reorder triggers at..."}
  │     ]
  │     ← KEY: are the retrieved docs actually relevant to the query?
  │
  ├── Generation: llm_context_window            2.4s
  │     Model: llama-3.1-8b-instant
  │     Input tokens: 3847
  │     Output tokens: 412
  │     Input messages:
  │       [system prompt] + [retrieved docs injected] + [user query]
  │       ← KEY: is the relevant content actually present in the context?
  │     Output: "For Class A SKUs, the policy requires..."
  │     ← KEY: does the output faithfully reflect the retrieved content?
  │
  └── Score: faithfulness = 0.94  (LLM-as-judge)
      Score: answer_relevancy = 0.87
══════════════════════════════════════════════════════════════
```

**Step 1 — Check retrieval quality.** Look at the retrieved documents. Are they relevant to the query? If the top-scored document is irrelevant, the retriever is the problem (wrong embedding model, BM25 keywords don't match, or the document is not in the knowledge base).

**Step 2 — Check context window content.** Expand the LLM call's input. Is the retrieved content actually present? If the retrieved content was truncated (too many tokens) or not injected into the right position in the prompt, the LLM cannot answer correctly even if retrieval was perfect.

**Step 3 — Check output faithfulness.** Does the response reflect what's in the retrieved documents? If the LLM confidently states something not in the retrieved content, that's hallucination. If scores are attached (from RAGAS evaluators), look at the faithfulness score.

**Step 4 — Check latency breakdown.** Is the bottleneck retrieval (slow embedding, slow vector search) or generation (slow LLM, long prompt)? For ORCA's hybrid search with cross-encoder reranking, the reranking step can be slow — visible in the retrieval span latency.

Common RAG failure patterns visible in traces:
- Retrieval returns wrong documents (embedding quality issue)
- Right documents retrieved but truncated from context (token limit exceeded)
- LLM ignores retrieved content (prompt structure issue — context not prominent enough)
- High latency in reranking (cross-encoder is slow for large retrieved sets)

---

### Q5: Compare Langfuse and LangSmith in a table. What are the specific situations where Langfuse is clearly the better choice?

**Answer:**

```
LANGFUSE VS LANGSMITH COMPARISON
════════════════════════════════════════════════════════════════════════
Feature                    LangSmith              Langfuse
──────────────────────────────────────────────────────────────────────
Open source                No                     Yes (MIT)
Self-hosted                No (cloud only)        Yes (Docker/Helm)
Auto-instrumentation       Yes (LangChain env)    Partial (LangChain)
Non-LangChain support      Limited                Full SDK support
LangGraph trace view       Excellent              Good (via callback)
Cost tracking              Basic                  Excellent (per model)
Prompt management          Prompt Hub             Prompts feature
Score/feedback API         Yes                    Yes (more flexible)
Evaluation datasets        Yes                    Yes
Online evaluation          Yes                    Yes
Data residency             Customer data in cloud Customer infrastructure
Pricing                    SaaS per-seat          Free self-hosted
Community                  LangChain ecosystem    Independent
────────────────────────────────────────────────────────────────────────
```

**Situations where Langfuse is clearly the better choice:**

1. **Financial services, healthcare, government.** These sectors have data residency regulations that prohibit sending trace data (which contains LLM inputs and outputs, potentially including customer data) to third-party cloud services. Langfuse self-hosted on GKE or EKS means all trace data stays within the customer's own infrastructure, never leaving their security perimeter.

2. **Non-LangChain applications.** If your team built the pipeline using raw API calls, CrewAI directly, Haystack, or any other framework, Langfuse's explicit SDK is the only option that doesn't require adopting LangChain just for observability.

3. **Cost analysis at scale.** Langfuse's cost tracking is genuinely more detailed than LangSmith's — it attributes costs by user, project, model, and time period with dedicated dashboard views. At scale (millions of LLM calls per month), understanding cost distribution is operationally critical.

4. **Large open-source project.** If you are building an open-source AI application and want to include observability as a built-in feature, recommending Langfuse (MIT, self-hostable) is more appropriate than recommending LangSmith (proprietary, cloud-only).

## Key Points to Say in the Interview

- "Langfuse is the open-source, framework-agnostic alternative to LangSmith — self-hostable for data residency requirements."
- "Both provide traces, evaluations, prompt management, and scoring — the key differentiator is self-hosting and framework independence."
- "Langfuse scores allow human feedback (HITL approval decisions) and automated evaluation results to be attached to the same trace."
- "Interpreting a RAG trace: check retrieval quality (correct docs?), context window (relevant content present?), then output faithfulness."
- "Setting `trace id = run_id` correlates the Langfuse trace with your application's own run identifier — essential for debugging."
- "For LangChain/LangGraph apps without data residency constraints: LangSmith. For non-LangChain or self-hosted requirement: Langfuse."
- "`langfuse.flush()` before process exit is critical — Langfuse batches events asynchronously, flush ensures they are sent."

## Common Mistakes to Avoid

- Forgetting `langfuse.flush()` at the end of batch jobs or short-lived processes — events in the queue are lost on process exit.
- Not setting `trace_id` to your own run identifier — makes correlation between Langfuse and your application logs impossible.
- Using Langfuse cloud when self-hosted is required by data policy — check data residency requirements before choosing the deployment model.
- Creating a new `Langfuse()` client on every function call — it should be a singleton, initialised once at application startup.
- Not recording human feedback (HITL decisions) as scores — this is the most valuable signal for improving the pipeline over time.

## Further Reading

- [Langfuse documentation](https://langfuse.com/docs) — comprehensive official guide to SDK, self-hosting, evaluations, and prompt management
- [Langfuse GitHub](https://github.com/langfuse/langfuse) — open source repository, issues, and community discussions
- [Langfuse vs LangSmith comparison (Langfuse blog)](https://langfuse.com/blog/2024-09-langsmith-alternative) — detailed side-by-side comparison from the Langfuse team
