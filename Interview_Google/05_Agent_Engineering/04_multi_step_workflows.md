# Multi-Step Agent Workflows

## What Is It? (Plain English)

Some tasks cannot be completed in one shot — they require many sequential steps, branching decisions, loops, and the ability to recover when something goes wrong partway through. Imagine an agent that processes insurance claims: it must first validate the claim form, then pull the customer's policy, then assess coverage, then calculate the payout, then route for human review if the amount exceeds a threshold, then trigger payment. Each step depends on the previous one, errors at step 3 shouldn't mean restarting from step 1, and the whole workflow might take days while waiting for human approval.

Multi-step workflows in AI agents are governed by the same concepts used in software engineering for decades: state machines (a system with defined states and transitions between them), directed acyclic graphs (DAGs, where tasks are nodes and dependencies are edges), and loops (repeat until condition met). The innovation in modern agent frameworks is that these classical workflow constructs are now combined with LLM decision-making — instead of hardcoded transitions, the LLM decides at runtime which branch to take.

The challenge is reliability. A single-step LLM call that fails can simply be retried. A workflow that fails at step 7 of 12 is a much harder problem: do you restart from the beginning? Resume from step 7? Roll back steps 5-6 that had side effects? Understanding idempotency (making operations safe to retry), error recovery, and state persistence is what separates enterprise-grade agent systems from research demos.

## How It Works

LangGraph is the primary framework for multi-step agent workflows. It models the agent as a graph where nodes are processing steps and edges are transitions:

```
LangGraph State Machine for an Inventory Reorder Agent:

                    ┌─────────────────┐
                    │   START NODE    │
                    │  (receive alert)│
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  AGENT 1 NODE   │
                    │ Demand Analysis │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  AGENT 2 NODE   │
                    │ Supply Options  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  AGENT 3 NODE   │
                    │Capital Scoring  │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │  ROUTE NODE     │ ◄── LLM/rule decides branch
                    │ (conditional)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────┐
     │  AUTO EXECUTE│ │   ESCALATE   │ │ SUSPEND  │
     │  (cost<$500) │ │ (need human  │ │(pool HIGH│
     │              │ │  approval)   │ │ risk)    │
     └──────┬───────┘ └──────┬───────┘ └──────────┘
            │                │
            ▼                ▼ (wait for human)
     ┌──────────────┐ ┌──────────────┐
     │   EXECUTE    │ │   APPROVE /  │
     │   ORDER      │ │   REJECT     │
     └──────┬───────┘ └──────┬───────┘
            │                │
            └────────┬───────┘
                     ▼
                ┌─────────────────┐
                │    END NODE     │
                └─────────────────┘

State object carried between all nodes:
{
  "sku_id": "SKU-1042",
  "alert_type": "critical",
  "demand_analysis": {...},  ← populated by Agent 1
  "supply_options": {...},   ← populated by Agent 2
  "capital_score": {...},    ← populated by Agent 3
  "routing_decision": "ESCALATE",
  "human_decision": null     ← filled in after HITL
}
```

## Why Google Cares About This

Google's AI infrastructure handles workflows that span minutes to days — training pipelines, data processing jobs, multi-agent customer resolution flows. At scale, any workflow step can fail, any external dependency can be unavailable, and any business policy can require a human in the loop. Candidates who understand state machines, DAGs, idempotency, and graceful partial-failure recovery are demonstrating production engineering maturity. This is the line between "I can demo this" and "I can run this at Google scale."

## Interview Questions & Answers

### Q1: What is idempotency, and why is it critical in multi-step agent workflows?

**Answer:** Idempotency means that performing an operation multiple times produces the same result as performing it once. A light switch is idempotent when you press it twice to turn it on — nothing changes on the second press because the light is already on. In agent workflows, idempotency means it is safe to retry any step that fails without worrying about creating duplicate side effects: ordering twice, sending two emails, deducting payment twice.

Idempotency matters in multi-step workflows because failures are inevitable and retry is your primary recovery mechanism. If your agent fails at step 7 of 12 due to a network timeout, you need to resume from step 7. But if step 7 already partially executed before failing — for example, it called an external API that sent an email before timing out — retrying step 7 might send the email twice. Non-idempotent steps in a retryable workflow are a correctness landmine.

The standard solution is idempotency keys: before executing any external action, check a persistent log for a key like `(run_id, step_name)`. If an entry exists with status "completed," skip the execution and return the cached result. If no entry exists, execute, then write the result. If an entry exists with status "in_progress" (crashed mid-execution), clean up and retry. This three-state check-before-execute pattern makes any operation safe to retry.

For agent workflows specifically, the state object persisted in LangGraph's MemorySaver or a database is the key tool. Every node should write its output to state before returning. If a node crashes after writing output but before the orchestrator marks it complete, the orchestrator can detect the written output and treat the node as complete on retry. If a node crashes before writing output, the orchestrator retries the node from scratch. This is why "write to state atomically, at the end of the node" is a critical implementation pattern.

### Q2: How do you handle partial failures in a multi-step workflow? Walk me through a specific example.

**Answer:** Partial failure means some steps of a workflow completed successfully but others did not. The naive response is to restart the entire workflow, but this is expensive and wrong — successful steps might have had side effects (sent a notification, reserved a slot, deducted budget) that cannot or should not be repeated. The correct approach depends on whether the failed step is recoverable, whether it had side effects, and where in the workflow it occurred.

Consider the ORCA inventory workflow: Step 1 (demand analysis) succeeded and took 30 seconds to run. Step 2 (supply option generation) crashed at the external supplier API call. Restarting from the beginning means re-running the 30-second demand analysis for no reason. The right recovery is to checkpoint step 1's output, mark step 2 as failed, and retry only step 2 with exponential backoff.

The implementation pattern for this is: every node writes its output to the shared state object (persisted in a database) before signaling completion to the orchestrator. The orchestrator marks each node's completion status in a persistent log. On restart (whether from crash or scheduled retry), the orchestrator checks which nodes are already marked complete and skips them, resuming from the first incomplete node. LangGraph's MemorySaver does exactly this for short-lived workflows; for workflows that must survive server restarts, you need a proper database-backed checkpointer.

For nodes that have irreversible side effects (sent an email, charged a card, booked a flight), you have two options: either make the node idempotent (check before acting), or accept that retrying it might double-execute and handle that at the business level (detect duplicate orders and cancel one). The cleanest architecture keeps "read/compute" operations (which are always safely retryable) separate from "write/act" operations (which need idempotency protection), with only the final "execute" step having irreversible side effects.

### Q3: When should you model a workflow as a state machine vs a DAG?

**Answer:** The distinction comes down to whether the workflow has cycles. A DAG (Directed Acyclic Graph) has no loops — each step runs once, in dependency order, and the workflow terminates when all steps complete. This is the right model for data processing pipelines, ETL jobs, and linear multi-stage tasks. If you are processing an insurance claim where each step always happens exactly once in a fixed order, a DAG is perfect.

A state machine allows cycles — you can revisit states, loop until a condition is met, and have transitions that depend on the current state plus the outcome of actions. This is the right model when an agent might need to retry, ask clarifying questions, or loop through a process multiple times. A customer service agent that keeps asking the user for more information until it has enough to resolve the ticket is a state machine, not a DAG.

LangGraph is explicitly designed as a state machine (graph with potential cycles), not a DAG. This is what makes it suitable for agents that need to re-try steps, loop on reasoning, or wait for external events (like human approval). A DAG framework like Apache Airflow or Prefect is better for data pipelines where each step runs once and the dependency structure is known in advance.

The practical rule: if your workflow can loop, branch based on LLM outputs, or pause for external input, use a state machine framework. If your workflow is a fixed sequence of data transformation steps, use a DAG framework. Many production systems use both: Airflow orchestrates the outer data pipeline (DAG), within which individual steps may launch short-lived agent state machines for tasks requiring LLM reasoning.

### Q4: What is the difference between an error and a failure in workflow design, and how do you handle each?

**Answer:** An error is a known, expected condition that the workflow should handle gracefully — a tool returns "not found," an API call times out, a document is malformed. An error is anticipated in the workflow design, has a defined handler, and should not terminate the workflow. A failure is an unexpected condition that the workflow cannot recover from automatically — the database is corrupt, the LLM provider is down, a critical business rule was violated. A failure should trigger escalation, human intervention, or a clean shutdown rather than silent retry loops.

This distinction matters for design because treating all errors as failures makes the system too brittle — any transient network issue kills the workflow. Treating all failures as errors makes the system keep retrying indefinitely, potentially amplifying a bad situation (if the database is corrupt, retrying will corrupt more data).

For errors: implement retry with exponential backoff and jitter (add randomness to prevent thundering herd), define per-node timeout budgets, and have fallback logic for each tool. An agent that can't reach the primary supplier API should automatically try the backup supplier API before declaring the step failed.

For failures: implement a dead-letter queue or failure state. When a step exceeds its retry budget, move the workflow to a "failed" state, log all context (the run ID, the step that failed, the error message, the state at time of failure), and alert a human operator. Never silently discard a failed workflow — silent failures are invisible production incidents. The audit trail from the failure state is also essential for post-mortem debugging.

### Q5: How do loops work in LangGraph, and how do you prevent infinite loops?

**Answer:** In LangGraph, a loop is created by having a conditional edge that can route back to an earlier node rather than always progressing forward. For example, an agent might route back to "gather more information" if it doesn't have enough context to make a decision, creating a loop: gather → assess → (if insufficient) → gather → assess → (if sufficient) → decide. The loop is driven by the conditional routing function's return value.

Preventing infinite loops requires both a step counter and a circuit breaker. The step counter is simple: add a `step_count` field to the state object, increment it at each node, and add a condition to every routing function that returns "terminate" if `step_count > MAX_STEPS` (typically 10-25). This is the hard limit.

The circuit breaker is more subtle: track whether the state is actually changing between iterations. If the agent loops 3 times through "gather information" but the new information gathered in each loop is identical to the previous loop (same tool called, same result returned), force a different path or terminate. This prevents the infinite loop pattern where the agent keeps trying the same thing expecting different results.

LangGraph specifically supports this through its interrupt mechanism: you can configure a node to be interrupt-able after a certain number of visits, pausing for human review. This is different from an infinite loop prevention — it's a "checkpointing for complex workflows" pattern where a human can inspect the state and either confirm the loop is making progress or kill it.

```
Loop with safety guards:

              ┌─────────────────────┐
              │  GATHER INFORMATION │ ◄──────────────┐
              │  step_count += 1    │                │
              └──────────┬──────────┘                │
                         │                           │
                         ▼                           │
              ┌─────────────────────┐                │
              │  ASSESS SUFFICIENCY │                │
              └──────────┬──────────┘                │
                         │                           │
              ┌──────────┼───────────┐               │
              │          │           │               │
              ▼          ▼           ▼               │
        step_count   state has   sufficient          │
          > 20?      not changed?  context?          │
              │          │           │               │
              ▼          ▼           │               │
           ABORT      ABORT          └── No ─────────┘
                                         Yes ──► DECIDE
```

## Key Points to Say in the Interview

- State machines allow cycles and LLM-driven conditional routing; DAGs are for fixed-order pipelines — choose the right model for the task
- Idempotency means safe to retry; implement it with a `(run_id, step_name)` log checked before every external action
- Checkpoint state after every step; on retry, skip already-completed steps and resume from the first incomplete one
- Distinguish errors (expected, handled gracefully) from failures (unexpected, escalate to human or dead-letter queue)
- Infinite loops need two guards: a hard step count limit AND a state-change detector
- LangGraph's MemorySaver is for in-memory workflows; production workflows spanning server restarts need a DB-backed checkpointer

## Common Mistakes to Avoid

- Don't design workflows without checkpointing — saying "just restart from the beginning" on failure shows lack of production experience
- Don't conflate a DAG with a state machine — they solve different problems; confusing them in an interview is a red flag
- Don't forget idempotency for any node with external side effects (API calls, DB writes, emails)
- Don't rely solely on step count for infinite loop prevention — also check for state stagnation
- Don't silently discard failed workflows — always log failure context for debugging and alerting

## Further Reading

- [LangGraph Documentation: State Machines and Cycles](https://langchain-ai.github.io/langgraph/) — Official docs for the most widely used agent workflow framework
- [Temporal.io: Durable Execution for Workflows](https://docs.temporal.io/concepts/what-is-a-workflow) — Industry-leading approach to fault-tolerant multi-step workflows with automatic state persistence
- [Building Reliable Agent Pipelines (LangChain Blog)](https://blog.langchain.dev/langgraph-v0-2/) — Practical patterns for error recovery and checkpointing in production agents
