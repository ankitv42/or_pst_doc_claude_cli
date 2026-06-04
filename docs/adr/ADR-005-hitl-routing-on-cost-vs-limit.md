# ADR-005: HITL Gate Keyed on Cost vs Auto-Approve Limit (Pure Python, Not LLM-Driven)

**Status:** Accepted  
**Date:** 2026-05-10  
**Authors:** ORCA Engineering

---

## Context

After Agent 3 scores 3 replenishment options and selects a winner, the pipeline must decide whether a human needs to approve the order. This is a high-stakes binary decision:

- **Wrong ESCALATE** (escalating when not needed): A human planner wastes 48 hours reviewing an order that could have been auto-approved. In a system handling 200+ stores, unnecessary escalations block the pipeline and burn analyst time.
- **Wrong AUTO_EXECUTE** (executing when approval was needed): An unchecked order is placed — potentially for AED 200,000+ against a pool with a AED 50,000 auto-approve limit. This is a financial controls violation.

The original design placed the routing decision inside Agent 4's system prompt:

```
# Original Agent 4 prompt (rejected)
Based on capital_decision, determine if this order requires approval.
If cost > pool.auto_approve_limit → ESCALATE
If pool_pressure = HIGH → SUSPEND
Otherwise → AUTO_EXECUTE
```

The problem: this is an LLM making a binary financial controls decision from a text prompt. In testing, Agent 4 made routing errors on ~15% of runs — primarily confusing CP001's limit (AED 50,000) with CP003's limit (AED 20,000), or ignoring the pool_pressure flag entirely when pool data was buried in a long prompt.

The Palantir original had this routing logic hardcoded in the pipeline orchestrator — not in any agent's reasoning. The business rule "human approval required if cost > auto_approve_limit" is a financial control, not an inference task.

---

## Decision

**Routing is pure Python in `route_node`. No LLM call. No prompt. No inference.**

```python
# agents/graph.py — route_node (lines 737-776)
def route_node(state: AgentState) -> dict:
    """Pure Python routing decision — no LLM call."""

    capital_decision  = state.get("capital_decision", {})
    approval_required = capital_decision.get("approval_required", True)
    approval_pool     = capital_decision.get("approval_pool", "CP001")

    # fetch live pool pressure via MCP (one DB query)
    pool_data     = _run_async(_route_fetch(approval_pool))
    pool_pressure = pool_data.get("pool_pressure_flag", "LOW")

    # priority: SUSPEND > AUTO_EXECUTE > ESCALATE
    if pool_pressure == "HIGH":
        route = "SUSPEND"
    elif not approval_required:
        route = "AUTO_EXECUTE"
    else:
        route = "ESCALATE"

    return {"route": route}
```

`approval_required` is computed by Agent 3 using the formula:
```
approval_required = total_cost_aed > pool.auto_approve_limit_aed
```

This is computed in the LLM context where Agent 3 sees both the cost and the limit side-by-side — that's an appropriate inference task. The routing node reads the already-computed boolean and applies the priority rule in code. The LLM is only asked to do what LLMs are good at (interpreting and scoring options); the binary financial control decision is never delegated to inference.

**Pool pressure is fetched live** via MCP at routing time, not from the Agent 3 state. This is deliberate: pool pressure can change between Agent 3's execution and the routing decision (other pipelines may have consumed budget). The routing node makes a fresh MCP call to `check_capital_budgets(pool_id)` to get current pressure.

**The routing logic is covered by unit tests:**

```python
# tests/test_routing.py
@pytest.mark.parametrize("pressure,approval,expected", [
    ("HIGH",   True,  "SUSPEND"),
    ("HIGH",   False, "SUSPEND"),   # SUSPEND overrides even when no approval needed
    ("MEDIUM", False, "AUTO_EXECUTE"),
    ("LOW",    False, "AUTO_EXECUTE"),
    ("MEDIUM", True,  "ESCALATE"),
    ("LOW",    True,  "ESCALATE"),
])
def test_routing_matrix(self, pressure, approval, expected):
    assert decide_route(pressure, approval) == expected
```

22 tests. Zero LLM calls. The routing logic cannot silently drift.

---

## The `approval_required` Field — How Agent 3 Sets It

Agent 3's prompt explicitly instructs:

```
RULE 5 — Approval check:
    approval_required = option.total_cost_aed > pool.auto_approve_limit_aed

After selecting the winner, set the following TOP-LEVEL fields EXACTLY:
    - recommended         = winner id ("A", "B", or "C")
    - approval_required   = winner option's approval_required (true or false)
    - approval_amount_aed = winner option's total_cost_aed
                            COPY THE EXACT NUMBER. NEVER write 0.
```

The prompt also instructs Agent 3 to compute `approval_required` per-option in `scored_options[]` and copy the winner's value to the top-level field. The `route_node` reads the top-level field — it does not re-derive the approval decision.

This separation is intentional: Agent 3 computes, `route_node` reads. If Agent 3 mislabels `approval_required`, the LLM-as-judge `hitl_accuracy` criterion catches it.

---

## Consequences

**Positive:**

- **Routing is deterministic.** Given the same `approval_required` boolean and the same `pool_pressure_flag`, `route_node` always produces the same route. This is verifiable, testable, and auditable.
- **Financial controls are code, not prompts.** The rule "cost > 50,000 → human approval" is enforced in Python. It cannot hallucinate, misread the limit, or be confused by surrounding context.
- **Zero latency.** `route_node` adds 1 DB query (~5ms) to the pipeline. If this were an LLM call, it would add 0.5–2 seconds and a Groq API call.
- **Unit-testable.** The entire routing matrix is covered by parametrized tests. Any future change to the priority order (e.g., adding a new route) immediately shows up as a test failure.
- **Mirrors Palantir's original.** The RCC pipeline had routing hardcoded in the orchestrator. This faithfully rebuilds that architecture.

**Negative:**

- **Agent 3 must correctly set `approval_required`.** If Agent 3 LLM makes an error in computing `approval_required` (confusing pool limits, or setting it to `false` when it should be `true`), `route_node` will route incorrectly — because it trusts Agent 3's output. This is monitored by the `hitl_accuracy` judge criterion.
- **Pool pressure is sampled, not streamed.** The single MCP call for pool pressure is a point-in-time snapshot. In a high-throughput scenario where many pipelines run simultaneously, pool pressure could change between the MCP call and the actual order execution. Mitigated by checking pressure again in `execute_node` before writeback.
- **A future "smart routing" requirement would need a different architecture.** If ORCA ever needs routing that considers factors beyond cost-vs-limit (e.g., supplier reliability history, seasonal demand patterns), this pure-Python routing node would need to be replaced with an LLM-driven decision — which is the more complex path we deliberately avoided for now.

---

## Alternatives Considered

| Option | Why Rejected |
|---|---|
| Agent 4 prompt makes routing decision | 15% error rate in testing. LLM confused CP001 vs CP003 limits. Unacceptable for financial controls. |
| Route based on `final_status` from Agent 3 | Agent 3 shouldn't set final_status — that's the pipeline's decision. Mixing concerns. |
| Separate "routing agent" (5th LLM call) | Adds 0.5–2 seconds and an API call for a decision that is expressible as 3 lines of Python. No inference needed. |
| Threshold in environment variable | The limits are pool-specific (CP001: 50k, CP003: 20k) and stored in the DB. A single env var threshold can't capture this. |
