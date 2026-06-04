# ADR-001: LangGraph StateGraph Over Plain LangChain for the Agent Pipeline

**Status:** Accepted  
**Date:** 2026-05-01  
**Authors:** ORCA Engineering

---

## Context

ORCA needs to run a fixed 4-agent chain (Demand → Supply → Capital → HITL) where:

1. **Each agent produces structured output** that the next agent reads from a shared state object — not just passing a string through.
2. **A human must be able to approve or reject an order** that costs more than the auto-approve limit. The pipeline must pause indefinitely and resume from the exact point it stopped.
3. **The routing decision** (ESCALATE vs AUTO_EXECUTE vs SUSPEND) happens after Agent 3's output and must never misfire — a wrong ESCALATE costs a human 48 hours of review time; a wrong AUTO_EXECUTE places an unchecked order.
4. **The pipeline runs inside a FastAPI background thread** that returns 202 immediately. The paused state must survive across HTTP requests (the approval comes in a completely different request, potentially minutes or hours later).

The initial prototype used plain LangChain — a single `RunnableSequence` of LLM calls piped together. This failed for three reasons:

- **No shared mutable state.** Each agent's output was passed as text into the next prompt. Agent 3 couldn't reliably read Agent 2's numeric option costs from a free-text summary — it hallucinated values.
- **No pause/resume.** LangChain chains run to completion or fail. There is no concept of "stop here, save everything, let a human in, then continue." Implementing this manually would require writing our own checkpoint/resume system from scratch.
- **No conditional branching on state.** Route decisions (SUSPEND vs AUTO_EXECUTE vs ESCALATE) had to be checked outside the chain, which broke the execution model entirely.

---

## Decision

Use **LangGraph `StateGraph`** with a `TypedDict`-based `AgentState`, compiled with `SqliteSaver` checkpointer and `interrupt_before=["execute_node"]`.

```python
# agents/graph.py — the compiled graph
class AgentState(TypedDict):
    sku_id:           str
    store_id:         str
    pipeline_id:      str
    demand_summary:   Optional[dict]   # Agent 1 output
    options_package:  Optional[dict]   # Agent 2 output
    capital_decision: Optional[dict]   # Agent 3 output
    hitl_briefing:    Optional[str]    # Agent 4 output
    action_taken:     Optional[str]
    route:            Optional[str]
    final_status:     Optional[str]

app = builder.compile(
    checkpointer = SqliteSaver(conn),
    interrupt_before = ["execute_node"],
)
```

The `interrupt_before` directive is the technical foundation of HITL. When the graph reaches `execute_node`, it:
1. Saves the complete `AgentState` (all 4 agent outputs) to `db/checkpoints.db` via SqliteSaver.
2. Returns the current state to the caller with the graph frozen.
3. Waits indefinitely.

`resume_pipeline(pipeline_id, approved=True)` calls `_app.invoke(None, config=config)`. The `None` input tells LangGraph: "don't start fresh — load the checkpoint for this `thread_id` and continue from where you stopped." The entire agent state (demand_summary, options_package, capital_decision, hitl_briefing) is restored exactly as it was when the graph paused.

---

## Consequences

**Positive:**

- **HITL is deterministic.** The graph always pauses at exactly `execute_node`. It cannot accidentally write an order before human approval. This is guaranteed by the framework, not by application logic.
- **State is typed and explicit.** Every field in `AgentState` is typed. Agent 2 reads `state["demand_summary"]["urgency"]` — a structured dict, not parsed text. Eliminates cross-agent hallucination from free-text hand-offs.
- **Conditional routing is state-driven.** `decide_route()` reads `state["route"]` and returns a node name. LangGraph calls the right node. Adding a new route (e.g., PARTIAL_EXECUTE) means adding one node and one edge — graph.py has no if/else explosion.
- **Persistence across restarts.** SqliteSaver writes to `db/checkpoints.db`. If the API server restarts while an order is awaiting approval, the human clicks Approve and `resume_pipeline()` loads the checkpoint — the order proceeds exactly as intended.
- **Observability.** LangGraph propagates tracing config through all nodes automatically. LangSmith receives named spans for every agent without any agent-level code change.

**Negative:**

- **LangGraph is opinionated.** Developers must understand the state-graph abstraction. A new engineer sees `builder.add_conditional_edges(...)` and needs to read LangGraph docs before they can contribute.
- **SqliteSaver is single-instance.** Works for one Render deployment. A multi-worker deployment needs `PostgresSaver` and a shared database. This is a known limitation noted in the code.
- **MemorySaver was the original choice** (and still appears in git history). The migration to SqliteSaver was done mid-project after discovering that restarting the dev server lost all paused pipelines.

---

## Alternatives Considered

| Option | Why Rejected |
|---|---|
| Plain LangChain `RunnableSequence` | No shared state, no pause/resume, no conditional routing |
| Custom orchestration (hand-written) | Would require building checkpoint, resume, and state management from scratch — equivalent to reimplementing LangGraph |
| CrewAI for the full pipeline | CrewAI manages collaboration between agents, not a fixed ordered pipeline with HITL gates. It was used for the Agent 1 sub-crew (open-ended demand analysis) but is wrong for the deterministic 4-step pipeline. |
| Prefect / Airflow | Heavy infrastructure for task orchestration, not LLM agent pipelines. No native LLM state management. |
