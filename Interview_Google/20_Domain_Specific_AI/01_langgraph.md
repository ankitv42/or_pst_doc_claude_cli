# LangGraph: Building Stateful Multi-Agent Pipelines

## What Is It? (Plain English)

LangGraph is a framework for building AI pipelines where the flow of work is not a straight line but a graph — with branches, loops, and pauses. A simple LangChain chain is like a conveyor belt: input goes in, output comes out. LangGraph is like a flowchart: depending on what each step produces, the work can take different paths.

The central abstraction is a StateGraph. Your entire pipeline shares a typed state object — a Python dictionary — that gets updated as each node (processing step) runs. Nodes are just Python functions that take the current state and return updates to it. Edges define which node runs next, and conditional edges let you branch based on the state contents.

What makes LangGraph uniquely powerful for AI agents is its support for checkpointing and interrupts. Checkpointing means saving the state after every step, so the pipeline can be resumed if it crashes or paused if a human needs to review. The interrupt/resume pattern is how you implement Human-in-the-Loop (HITL): the pipeline literally pauses mid-execution and waits indefinitely for a human to make a decision before continuing.

## How It Works

```
ORCA's LangGraph State Machine
═══════════════════════════════════════════════════════════════════

                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Agent 1   │ Demand Intelligence
                    │ (urgency,   │ LLM call → updates state.demand_analysis
                    │  demand)    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Agent 2   │ Supply Replenishment
                    │ (3 reorder  │ LLM call → builds 3 options
                    │  options)   │ Hard rule: Class A ≠ partial
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Agent 3   │ Capital Allocation
                    │ (score &    │ LLM call → scores options
                    │  decide)    │ Sets state.route
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Route Node  │ Pure Python routing (no LLM)
                    └──────┬──────┘
                           │
              ┌────────────┼─────────────┐
              ▼            ▼             ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ ESCALATE │ │  AUTO    │ │ SUSPEND  │
        │ (HITL    │ │ EXECUTE  │ │ (pool    │
        │ pause)   │ │          │ │  HIGH)   │
        └──────────┘ └──────────┘ └──────────┘
              │
        interrupt_before=["execute_node"]
        → Pipeline pauses here
        → POST /approve/{run_id} resumes it
═══════════════════════════════════════════════════════════════════
```

Minimal code example:

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict

class AgentState(TypedDict):
    sku_id: str
    demand_analysis: dict
    replenishment_options: list
    capital_decision: dict
    route: str

def agent1_node(state: AgentState) -> dict:
    analysis = run_demand_intelligence(state["sku_id"])
    return {"demand_analysis": analysis}   # partial update

def route_node(state: AgentState) -> str:
    """Returns the name of the next node — this IS the conditional edge."""
    return state["route"]   # "ESCALATE", "AUTO_EXECUTE", or "SUSPEND"

# Build graph
builder = StateGraph(AgentState)
builder.add_node("agent1", agent1_node)
builder.add_node("agent2", agent2_node)
builder.add_node("agent3", agent3_node)
builder.add_node("execute_node", execute_node)

builder.set_entry_point("agent1")
builder.add_edge("agent1", "agent2")
builder.add_edge("agent2", "agent3")
builder.add_conditional_edges("agent3", route_node,
    {"ESCALATE": "execute_node", "AUTO_EXECUTE": "execute_node", "SUSPEND": END})

# HITL: pause BEFORE execute_node for human approval
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer,
                        interrupt_before=["execute_node"])
```

## Why Google Cares About This

Vertex AI's agent orchestration and Google DeepMind's research on multi-agent systems both require frameworks for coordinating multiple AI models in stateful workflows. LangGraph has become the standard framework for this in Python. Knowing it in depth — including checkpointing, HITL, and conditional routing — demonstrates that you can build production AI systems, not just prototype chains. Google interviewers will probe whether you understand why state management matters (debugging, auditability, resume-ability) not just how to call the APIs.

## Interview Questions & Answers

### Q1: What is the difference between LangGraph's StateGraph and a simple LangChain chain? When would you choose LangGraph?

**Answer:** A LangChain chain (or LCEL expression) is a linear composition: `prompt | llm | parser`. Each component receives the output of the previous one and passes its output to the next. The state is implicit — just the data flowing through the chain. There is no branching, no looping, no persistence between steps.

LangGraph's StateGraph introduces three capabilities that simple chains do not have:

**Explicit shared state.** Every node reads from and writes to a typed shared state object (`TypedDict`). Any node can access any previously computed value. In ORCA, Agent 3 can see Agent 1's demand analysis directly — they share the same `AgentState`. With a simple chain, you would have to carefully thread every earlier output through to later stages.

**Conditional routing.** After any node, you can route to different nodes based on the state. ORCA's route node returns "ESCALATE", "AUTO_EXECUTE", or "SUSPEND" and LangGraph dispatches to the corresponding next node. Simple chains cannot branch.

**Checkpointing and persistence.** LangGraph can save the full state after every node using a checkpointer (`MemorySaver` for in-memory, `SqliteSaver` for disk persistence). This means: if a node crashes, the graph can restart from the last checkpoint. More importantly for ORCA, the graph can pause (`interrupt_before`) and resume later — which is how HITL is implemented.

```
Choose LangGraph when:
  ✓ Multiple agents need to share intermediate results
  ✓ You need conditional routing (if X then A, else B)
  ✓ You need loops (retry until quality is sufficient)
  ✓ You need HITL (pause and wait for human input)
  ✓ You need auditability (checkpoint every step)

Use simple chain/LCEL when:
  ✓ Single LLM call with structured output
  ✓ Retrieval + generation without branching
  ✓ Prototype that will be refactored later
```

The complexity cost of LangGraph is real — it requires understanding state management, the graph compilation model, and the checkpointer. For a simple RAG query, LCEL is the right tool.

---

### Q2: Explain LangGraph's HITL interrupt/resume mechanism. How does ORCA use it?

**Answer:** Human-in-the-Loop (HITL) in LangGraph works via `interrupt_before` — a list of node names where the graph should pause before executing that node. When the graph reaches the node before which an interrupt is registered, it saves the current state to the checkpointer and raises an `Interrupt` exception that the calling code can catch.

```python
# Compiling with interrupts
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["execute_node"]
)

# Invoking the graph
config = {"configurable": {"thread_id": run_id}}
try:
    result = graph.invoke(initial_state, config=config)
except Interrupt:
    # Graph paused before execute_node
    # State is saved in checkpointer under thread_id=run_id
    print(f"Pipeline {run_id} is awaiting human approval")
```

The graph state is persisted by the checkpointer. Any time later, the graph can be resumed by invoking it again with the same `thread_id` and an explicit instruction to continue:

```python
# Human calls POST /approve/{run_id}
# Backend resumes the graph:
def resume_pipeline(run_id: str, approved: bool):
    config = {"configurable": {"thread_id": run_id}}
    if approved:
        # Resume from interrupt — execute_node will now run
        result = graph.invoke(None, config=config)
    else:
        # Update state to mark rejected, then resume (which routes to END)
        graph.update_state(config, {"route": "REJECTED"})
        result = graph.invoke(None, config=config)
```

ORCA's specific use: Agent 4 / the route node sets `state.route = "ESCALATE"` when the total order cost exceeds the approval threshold. Because `interrupt_before=["execute_node"]` is set, the graph pauses. The FastAPI backend catches this, sets the pipeline run status to "awaiting_approval" in the database, and returns. The Streamlit dashboard polls `GET /pipeline/{run_id}` every 3 seconds. When it sees "awaiting_approval", it shows an approval UI with the 3 options and their scores. The human clicks Approve or Reject. FastAPI calls the resume function. The graph continues from where it paused.

This is exactly the HITL pattern regulators require for high-stakes automated decisions.

---

### Q3: What is the difference between MemorySaver and SqliteSaver checkpointers? When would you use each?

**Answer:** Both checkpointers implement the same LangGraph `BaseCheckpointSaver` interface — they both save and restore graph state at each node. The difference is where and how long the state is stored.

**MemorySaver** stores checkpoints in a Python dictionary in memory. It is fast, requires no setup, and works well for development and testing. But the state is lost when the process terminates. For ORCA running in a single uvicorn process that restarts when Render's free tier spins down after inactivity, MemorySaver means any in-progress pipeline paused for HITL approval would be lost on restart.

**SqliteSaver** persists checkpoints to a SQLite database on disk. State survives process restarts. It is appropriate for any production deployment where pipelines may be long-running or interrupted.

```python
# Development / testing
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()

# Production (state survives server restarts)
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("db/checkpoints.db")

graph = builder.compile(checkpointer=checkpointer, interrupt_before=["execute_node"])
```

For ORCA running on Render free tier: SqliteSaver is the better choice for production because the server can spin down and come back up without losing pending HITL approvals. The SQLite file can live alongside `db/orca.db`.

For Google Cloud production deployments: neither MemorySaver (in-memory, not distributed) nor SqliteSaver (single file, not horizontally scalable) would be appropriate if you need multiple API instances. LangGraph also provides `PostgresSaver` and Redis-based checkpointers for distributed deployments.

---

### Q4: How does LangGraph handle errors and retries? What happens when an LLM call fails in one of ORCA's nodes?

**Answer:** LangGraph does not have built-in retry logic — that is the responsibility of the node implementation. When a node raises an unhandled exception, LangGraph propagates it to the caller. The state is saved up to the last successfully completed node (assuming a checkpointer is configured), so a retry can resume from there rather than from the beginning.

Best practices for error handling in LangGraph nodes:

```python
import tenacity
from langchain_groq import ChatGroq

def agent1_node(state: AgentState) -> dict:
    """Demand intelligence with retry and fallback."""
    llm = ChatGroq(model="llama-3.1-8b-instant")

    # Retry with exponential backoff for transient API errors
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(Exception),
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def call_llm_with_retry(prompt: str) -> str:
        return llm.invoke(prompt).content

    try:
        analysis = call_llm_with_retry(build_demand_prompt(state))
        return {"demand_analysis": parse_demand_response(analysis)}
    except Exception as e:
        # Graceful fallback — don't fail the entire pipeline
        logger.warning(f"Agent 1 LLM call failed after 3 retries: {e}")
        return {
            "demand_analysis": {
                "urgency": "UNKNOWN",
                "narrative": f"Analysis unavailable: {str(e)}. Using raw data.",
                "fallback": True
            }
        }
```

ORCA's known issue with the CrewAI sub-crew failing is an example of this pattern in action — the sub-crew failure is caught and falls back to a raw-data demand summary. The pipeline continues rather than failing completely.

For the resume-after-failure case: if Agent 2 fails after Agent 1 completed, and a SqliteSaver checkpointer is configured, you can invoke the graph again with the same `thread_id` and it will restart from the Agent 2 node rather than re-running Agent 1.

---

### Q5: How does ORCA's pipeline state flow through the four agents? Walk me through what the AgentState dictionary looks like at each stage.

**Answer:** This question tests whether you understand LangGraph state management conceptually, not just syntactically. Here is the state progression through ORCA's pipeline:

```python
# Initial state (from FastAPI POST /pipeline/run)
state_at_start = {
    "sku_id": "SKU-0042",
    "demand_analysis": {},
    "replenishment_options": [],
    "capital_decision": {},
    "route": "",
    "run_id": "run-abc123"
}

# After Agent 1 (demand intelligence):
state_after_agent1 = {
    **state_at_start,
    "demand_analysis": {
        "urgency": "CRITICAL",
        "days_of_stock": 3,
        "demand_trend": "UP",
        "lead_time_impact": "HIGH",
        "narrative": "SKU-0042 is critically low with 3 days of stock..."
    }
}

# After Agent 2 (supply replenishment — builds 3 options):
state_after_agent2 = {
    **state_after_agent1,
    "replenishment_options": [
        {"type": "standard",  "quantity": 500, "cost": 12500, "lead_days": 7, "score": 0},
        {"type": "expedite",  "quantity": 300, "cost": 18000, "lead_days": 2, "score": 0},
        # Note: partial NOT included if sku_class == "A" (hard rule)
    ]
}

# After Agent 3 (capital allocation — scores options, sets route):
state_after_agent3 = {
    **state_after_agent2,
    "capital_decision": {
        "recommended_option": "expedite",
        "total_cost": 18000,
        "budget_score": 0.6,
        "availability_score": 0.9,
        "margin_score": 0.7,
        "lead_time_penalty": -0.1,
        "final_score": 2.1,
        "reasoning": "Expedite selected due to critical stock level..."
    },
    "route": "ESCALATE"   # because total_cost > HITL_APPROVAL_THRESHOLD
}

# Route node reads state.route → dispatches to ESCALATE branch
# interrupt_before=["execute_node"] fires → pipeline pauses
```

The key design principle: each node returns only the fields it modified — LangGraph merges the return dict with the existing state. This is why nodes return partial dicts, not the complete state. This also enables parallel nodes (future extension) where two nodes update different fields simultaneously.

## Key Points to Say in the Interview

- "LangGraph's StateGraph is a directed graph where nodes update shared typed state — unlike simple chains where state is implicit."
- "Checkpointing persists state after every node — enables resume-after-crash and HITL pause/resume."
- "interrupt_before is how ORCA implements HITL — the graph saves state and stops before the execute node, waiting for a human API call."
- "MemorySaver for development, SqliteSaver for single-server production, PostgresSaver for distributed production."
- "Nodes return partial state updates — LangGraph merges them — so each node only specifies the fields it changed."
- "The route node is pure Python, not an LLM call — it reads state.route and dispatches. This is intentional: routing logic should be deterministic."
- "LangGraph vs simple chains: use LangGraph when you need branching, loops, shared state across agents, or HITL."

## Common Mistakes to Avoid

- Modifying the state object in-place inside a node — nodes should return a dict of updates, not mutate state directly.
- Forgetting to configure a checkpointer when using `interrupt_before` — without a checkpointer, interrupted states cannot be resumed.
- Using thread_id carelessly — each pipeline run needs a unique thread_id, and a thread_id used by a completed run should not be reused.
- Making the route node an LLM call — routing should be deterministic based on the state, not a probabilistic LLM output.
- Over-designing the state TypedDict — keep only the fields that need to flow between agents; don't use it as a general data dumping ground.

## Further Reading

- [LangGraph documentation](https://langchain-ai.github.io/langgraph/) — official documentation including how-to guides for HITL, checkpointing, and multi-agent patterns
- [LangGraph conceptual guide](https://langchain-ai.github.io/langgraph/concepts/) — explains StateGraph, nodes, edges, and checkpointing from first principles
- [LangGraph examples (GitHub)](https://github.com/langchain-ai/langgraph/tree/main/examples) — production-ready example implementations including HITL and multi-agent coordination
