# ORCA — 17 Agent Engineering Interview Questions

> **Focus area.** Deep questions on multi-agent orchestration: LangGraph state machines,
> CrewAI crew collaboration, MCP tool discovery, and the async/sync bridge. These
> are the questions a Google interviewer reaches for when evaluating senior AI engineers.

---

## Q1 — What is the difference between LangGraph and CrewAI, and why does ORCA use both?

### The Question to Ask
*"LangGraph and CrewAI are both multi-agent frameworks. Can't you pick one?"*

### Strong Answer
They solve different problems:

```
LangGraph = WORKFLOW ORCHESTRATOR
─────────────────────────────────────────────────────
You define the exact sequence: A → B → C → D
State is typed and explicit (AgentState TypedDict)
Supports interrupt/resume (HITL with checkpointing)
Perfect for: business pipelines where ORDER and AUDITABILITY matter

CrewAI = COLLABORATIVE REASONING ENGINE
─────────────────────────────────────────────────────
You define agent roles and goals
CrewAI decides how agents collaborate
No native interrupt/checkpoint support
Perfect for: open-ended analysis where multiple expert perspectives improve quality
```

ORCA's design exploits both:
```
LangGraph manages the 4-agent business pipeline (Agent 1 → 2 → 3 → Route → HITL/Execute)
         │
    Agent 1 needs deep demand analysis
         │
         ▼
    CrewAI crew runs INSIDE agent1_node:
       Data Analyst (tools: get_positions, get_velocity)
             +
       Market Analyst (tools: RAG query)
             ↘       ↙
         Forecast Strategist (synthesises → demand_summary JSON)
         │
    demand_summary returned to LangGraph state
         │
    Agent 2 receives it — completely unaware of CrewAI
```

LangGraph gives business guarantees. CrewAI gives analytical depth.

### Why It Matters
Using both frameworks and knowing when to apply each is a hallmark of a senior
engineer. Picking one for everything means compromising either reliability (CrewAI-only)
or analytical quality (LangGraph-only).

### Red Flags
- "I'd just pick one" — misses that they solve different problems
- Thinks LangGraph and CrewAI are competitors
- Unaware that CrewAI currently fails in ORCA due to the `cache_breakpoint` Groq error
  and falls back to a single LLM call (should know the known issues of their own system)

---

## Q2 — Walk through the `_run_async` bridge. Why does it exist?

### The Question to Ask
*"LangGraph node functions are synchronous `def` functions, but MCP tools are async-only. How do you bridge them?"*

### Strong Answer
LangGraph nodes are `def` (synchronous):
```python
def agent1_node(state: AgentState) -> dict:   # sync — LangGraph calls this
    tools = _run_async(_agent1_fetch(sku_id)) # bridge
```

MCP tools are async — they communicate with the MCP server subprocess over stdio I/O:
```python
async def _agent1_fetch(sku_id: str) -> tuple:
    tools            = await _get_mcp_tools()
    positions_result = await _call_mcp_tool(tools, "check_inventory_positions", ...)
    sku_result       = await _call_mcp_tool(tools, "get_sku_info", ...)
    return tools, positions_result, sku_result, ...
```

The bridge:
```python
def _run_async(coro):
    try:
        return asyncio.run(coro)      # creates a fresh event loop, runs coro, closes it
    except RuntimeError:
        # already inside a running loop (FastAPI, Jupyter)
        import nest_asyncio
        nest_asyncio.apply()           # patches event loop to allow nesting
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
```

Two scenarios:
1. **Called from `python agents/graph.py` directly:** No running event loop exists.
   `asyncio.run()` creates one fresh, runs the coroutine, closes it.
2. **Called from FastAPI (inside `background_tasks`):** FastAPI already has a running
   asyncio event loop. `asyncio.run()` raises `RuntimeError` → `nest_asyncio` patches
   the loop to allow nested `run_until_complete()`.

### Why It Matters
The sync/async boundary is one of the most common pain points in Python AI systems.
This exact pattern (sync orchestrator calling async tools) appears in nearly every
production LangGraph + MCP deployment.

### Red Flags
- Can't explain why `asyncio.run()` fails inside FastAPI (event loop already running)
- Suggests making all nodes `async def` — would require rewriting LangGraph internals
- Unaware of `nest_asyncio` and what "patching the event loop" means

---

## Q3 — Why is there one `async def _agentN_fetch()` helper per node instead of multiple `_run_async` calls?

### The Question to Ask
*"Agent 1 makes 4 MCP calls. Could you have called `_run_async` four times, once per tool call?"*

### Strong Answer
The broken approach:
```python
# WRONG — broken
def agent1_node(state):
    tools    = _run_async(_get_mcp_tools())           # creates+closes event loop
    pos      = _run_async(_call_mcp_tool(tools, ...)) # creates+closes ANOTHER loop
    sku      = _run_async(_call_mcp_tool(tools, ...)) # creates+closes ANOTHER loop
    # ERROR: each _run_async calls asyncio.run() which creates a NEW loop
    # On the 2nd call, the tools object from loop 1 may no longer be valid
    # because its async context (the subprocess connection) was closed.
```

The correct approach:
```python
async def _agent1_fetch(sku_id: str) -> tuple:
    """All async calls in ONE async context — same event loop, same subprocess connection."""
    tools            = await _get_mcp_tools()
    positions_result = await _call_mcp_tool(tools, "check_inventory_positions", ...)
    sku_result       = await _call_mcp_tool(tools, "get_sku_info", ...)
    velocity_result  = await _call_mcp_tool(tools, "get_demand_velocity", ...)
    events_result    = await _call_mcp_tool(tools, "check_active_events", ...)
    return tools, positions_result, sku_result, velocity_result, events_result

def agent1_node(state):
    # ONE _run_async call — all 4 MCP calls happen inside ONE event loop
    tools, positions, sku, velocity, events = _run_async(_agent1_fetch(sku_id))
```

Benefits:
1. The MCP subprocess connection stays open for all 4 calls (same async context)
2. Coroutines can run concurrently inside the async helper (natural async batching)
3. One bridge call per node — cleaner, easier to debug

### Why It Matters
This is a non-obvious async design pattern. Getting it wrong causes intermittent failures
that are hard to reproduce. The pattern shows deep understanding of Python's async model.

### Red Flags
- Suggests `asyncio.gather()` without understanding the subprocess lifetime constraint
- "Multiple `asyncio.run()` calls are fine" — demonstrates no experience debugging async bugs
- Can't explain why a tools object from one `asyncio.run()` can't be used in another

---

## Q4 — How does LangGraph know to route to `hitl_node` vs `execute_node` vs `suspend_node`?

### The Question to Ask
*"After `route_node` runs, LangGraph has to choose one of three next nodes. How does it make that decision?"*

### Strong Answer
LangGraph uses **conditional edges** — a function that reads state and returns
a string node name:

```python
def decide_route(state: AgentState) -> str:
    """Reads state.route and returns the next node name."""
    route = state.get("route", "ESCALATE")
    if route == "SUSPEND":
        return "suspend_node"
    elif route == "AUTO_EXECUTE":
        return "execute_node"
    else:
        return "hitl_node"

# Registered in build_graph():
builder.add_conditional_edges(
    "route_node",       # source node
    decide_route,       # function that returns which edge to take
    {
        "hitl_node":    "hitl_node",
        "execute_node": "execute_node",
        "suspend_node": "suspend_node",
    }
)
```

The dict maps string returns → node names. LangGraph calls `decide_route(state)`
after `route_node` completes, gets the string, and runs the corresponding node.

`route_node` itself writes `{"route": "ESCALATE"}` back to state — and `decide_route`
reads it. The state is the communication channel.

### Why It Matters
Conditional edges are the core LangGraph primitive for branching. Understanding
state-driven routing (vs function-call routing) shows the candidate knows
the framework's execution model.

### Red Flags
- Thinks agents "call each other" directly (they don't — LangGraph orchestrates)
- Confused about the difference between `route_node` (sets route) and `decide_route` (reads route)
- Can't explain what happens if `state.route` is None (defaults to "ESCALATE" — safe)

---

## Q5 — Why does ORCA use `interrupt_before=["execute_node"]` and not `interrupt_after`?

### The Question to Ask
*"The HITL interrupt fires before `execute_node`. Why before, not after?"*

### Strong Answer
`execute_node` writes `reorder_triggered = Yes` to the database — a **write-back
to production data**. Once that write happens, it cannot be easily undone.

```
interrupt_before=["execute_node"]:
    hitl_node writes briefing
    graph PAUSES ← human reads, decides
    human APPROVES
    execute_node runs → writes DB

interrupt_after=["execute_node"]  ← WRONG approach:
    hitl_node writes briefing
    execute_node runs → writes DB   ← ORDER PLACED
    graph PAUSES
    human reads briefing
    human says "I don't approve" → TOO LATE
```

`interrupt_before` ensures the write-back only happens **after** human consent.
It is the correct pattern for any irreversible action requiring authorisation.

The checkpoint saved at the pause point contains the full state including
`hitl_briefing` and `capital_decision` — the human reads exactly what the
system plans to execute.

### Why It Matters
This is the core HITL pattern. Getting it wrong means either approvals happen too
late (after action) or not at all (wrong node interrupted). Knowing this shows
the candidate understands the semantics, not just the syntax.

### Red Flags
- Can't explain WHY before vs after matters
- Thinks `interrupt_before` interrupts EVERY node (it interrupts only the named ones)
- No awareness that `execute_node` also fires for AUTO_EXECUTE — the system
  immediately resumes it after the interrupt, no human involved

---

## Q6 — What happens in LangGraph when `resume_pipeline` is called with `approved=False`?

### The Question to Ask
*"A human clicks Reject on the dashboard. Walk through exactly what happens in LangGraph."*

### Strong Answer
```python
def resume_pipeline(pipeline_id: str, approved: bool) -> dict:
    config = {"configurable": {"thread_id": pipeline_id}, ...}

    if not approved:
        # Before resuming: patch the checkpoint state
        _app.update_state(config, {
            "route":        "SUSPEND",
            "final_status": "REJECTED",
            "action_taken": "REJECTED_BY_HUMAN",
        })
        # Now when graph resumes from checkpoint, route="SUSPEND"

    # Resume from checkpoint (None = "no new input, continue from pause")
    final_state = _app.invoke(None, config=config)
    return final_state
```

The flow:
```
Graph paused at: interrupt_before["execute_node"]
Last known state: route="ESCALATE"

Human rejects
    ↓
update_state() patches checkpoint: route="SUSPEND"
    ↓
_app.invoke(None, config) resumes graph
    ↓
LangGraph re-evaluates decide_route(state)
    → route = "SUSPEND" → routes to suspend_node
    ↓
suspend_node runs: writes SUSPENDED, no DB write
    ↓
save_node saves audit log
    ↓
END
```

The `update_state()` call is LangGraph's mechanism to modify a paused graph's
state before resumption — a powerful and non-obvious feature.

### Why It Matters
The rejection path is a production requirement. Many HITL demos only show
the approval path. Knowing `update_state()` exists and how it works shows
deep LangGraph knowledge.

### Red Flags
- "Just don't call resume" — leaves the pipeline in limbo, never completing
- Unaware of `update_state()` — the correct mechanism for patching paused state
- Can't trace why `decide_route` picks `suspend_node` after the state patch

---

## Q7 — How does MCP tool discovery work at runtime? What happens if the MCP server crashes?

### The Question to Ask
*"When agent1_node runs, it calls `_get_mcp_tools()`. Walk through exactly what happens at the OS level."*

### Strong Answer
```python
MCP_CLIENT_CONFIG = {
    "orca_inventory": {
        "transport": "stdio",
        "command":   "python",
        "args":      [MCP_SERVER_PATH]   # absolute path to mcp_server/server.py
    }
}

async def _get_mcp_tools():
    client = MultiServerMCPClient(MCP_CLIENT_CONFIG)
    tools  = await client.get_tools()
    return tools
```

At the OS level:
1. `MultiServerMCPClient` spawns a **new subprocess**: `python mcp_server/server.py`
2. A **stdio pipe** is opened between the agent process and this subprocess
3. The client sends a discovery request over stdin: "what tools do you have?"
4. `mcp_server/server.py` responds with tool definitions over stdout
5. Client converts them to LangChain-compatible `StructuredTool` objects
6. The subprocess is **closed after each call** — stateless, fresh each time

If the server crashes mid-call, `_call_mcp_tool` raises an exception, which
propagates up to the node. Since each node is wrapped in `_run_pipeline_task`'s
`try/except`, the pipeline gracefully marks the run as `FAILED`.

If the server binary doesn't exist, the subprocess fails to spawn and raises
`FileNotFoundError` immediately — caught by the same error boundary.

### Why It Matters
Understanding MCP at the subprocess level (not just the API level) is what
separates someone who used it from someone who understands it. The stdio protocol
means no ports, no network, no service discovery — pure OS primitives.

### Red Flags
- Thinks MCP uses HTTP (it uses stdio)
- "Tools are hardcoded at import time" — tools are discovered dynamically each call
- Unaware that a fresh subprocess is spawned per call (stateless by design)

---

## Q8 — What is the `thread_id` in LangGraph's config and why does it equal `pipeline_id`?

### The Question to Ask
*"When you call `_app.invoke(initial_state, config)`, the config contains `thread_id: pipeline_id`. What is a thread ID and what does it do?"*

### Strong Answer
In LangGraph, `thread_id` is the **checkpoint namespace** — it identifies which
sequence of checkpoints belongs to a particular execution:

```python
config = {
    "configurable": {"thread_id": "PIPE_SKU00090_2026-06-04"},
    ...
}
```

Every time a node completes, LangGraph saves a checkpoint under this thread ID.
When `resume_pipeline` is called:
```python
_app.invoke(None, config={"configurable": {"thread_id": "PIPE_SKU00090_2026-06-04"}})
```
LangGraph loads the checkpoint for that thread ID and continues from where
it paused — it knows exactly what state was saved.

Setting `thread_id = pipeline_id` is intentional:
- `PIPE_SKU001_2026-06-04` is unique (one pipeline per SKU per day)
- The same ID used for the 409 deduplication check maps to the checkpoint
- Human approval endpoint passes the same `pipeline_id` → checkpoint retrieved

If you used a random UUID, resuming after a server restart would require
passing that UUID through — much harder to track.

### Why It Matters
The thread ID is the key that unlocks checkpoint resumption. A candidate who
doesn't know this concept can't explain how HITL survives server restarts.

### Red Flags
- Confuses `thread_id` with Python's `threading.Thread` — completely unrelated
- Thinks each node run creates a separate thread ID (one ID per full pipeline run)
- Can't connect `thread_id` to the HITL resumption mechanism

---

## Q9 — What does `_app.invoke(None, config)` mean — what does passing `None` do?

### The Question to Ask
*"In `resume_pipeline`, the call is `_app.invoke(None, config)`. What does `None` mean here?"*

### Strong Answer
```python
# Starting a fresh pipeline run:
_app.invoke(initial_state, config)
# ^ Pass the initial state — LangGraph starts from the entry point
#   with this as the starting state

# Resuming a paused pipeline:
_app.invoke(None, config)
# ^ None = "do NOT start fresh"
#   Load the checkpoint from config["thread_id"]
#   Continue from exactly where the graph paused
```

When `None` is passed, LangGraph:
1. Looks up `config["configurable"]["thread_id"]` in the checkpoint store
2. Finds the saved state at the pause point (before `execute_node`)
3. Restores that state
4. Continues running from the paused node forward

This is equivalent to loading a save game — the entire pipeline state
(demand_summary, options_package, capital_decision, hitl_briefing) is
reconstructed from the checkpoint.

### Why It Matters
This is the mechanism that makes HITL possible. Without it, you'd have to
re-run all 4 agents just to execute the write-back — defeating the purpose
of a human review step.

### Red Flags
- Thinks `None` means "run with empty state" — it means "load from checkpoint"
- Can't explain what the checkpoint contains (full AgentState at pause point)
- Doesn't know that `invoke(None)` will fail if no checkpoint exists for that thread_id

---

## Q10 — How does CrewAI's sequential process differ from the LangGraph pipeline?

### The Question to Ask
*"CrewAI uses `Process.sequential`. How is that different from LangGraph's agent chain?"*

### Strong Answer
Both are sequential — but the execution model differs:

```
LangGraph sequential:
    You define EDGES: agent1 → agent2 → agent3
    LangGraph enforces the order at the graph level
    State flows between nodes via TypedDict
    Interrupts are supported between any two nodes

CrewAI sequential process:
    You define TASKS with context=[task_data, task_market]
    CrewAI passes the output of previous tasks to the next agent's context
    Each agent decides HOW to achieve its task (can use tools, retry, ask for clarification)
    No native interrupt support
```

In ORCA's CrewAI crew:
```python
crew = Crew(
    agents  = [data_analyst, market_analyst, forecast_strategist],
    tasks   = [task_data, task_market, task_forecast],
    process = Process.sequential,
)
# Forecast Strategist automatically receives outputs of task_data and task_market
# because: task_forecast = Task(..., context=[task_data, task_market])
```

LangGraph can't be used for this because the three forecasting agents are
collaborating (sharing intermediate outputs freely) — LangGraph nodes
communicate only via the typed AgentState, not free-form text.

### Why It Matters
Understanding how context flows in CrewAI (task outputs passed as context)
vs LangGraph (typed state dict) shows the candidate has actually used both.

### Red Flags
- Thinks `context=[task_data, task_market]` in CrewAI means the same as
  reading from LangGraph's AgentState
- "Process.sequential is the same as LangGraph edges" — misses that
  CrewAI agents can iterate internally (max_iter=5) whereas LangGraph nodes run once
- Unaware that `allow_delegation=False` prevents agents from redirecting work to each other

---

## Q11 — How does Agent 3's scoring formula get enforced precisely if it's in a prompt?

### The Question to Ask
*"The capital allocation formula (`budget_score + availability_score + margin_score`) is in the Agent 3 prompt. What prevents the LLM from computing it wrong?"*

### Strong Answer
Three layers of enforcement:

**Layer 1 — Formula locked in system prompt, step-by-step:**
```
RULE 4a — Score each FEASIBLE option (max 100 points):
    budget_score       = (1 - total_cost_aed / pool.available_aed) x 40
    availability_score = option.availability_pct x 0.40
    margin_score       = (1 / margin_priority_rank) x 20
    total_score        = budget_score + availability_score + margin_score
```
The exact formula with exact multipliers is given, not a description.

**Layer 2 — Structured JSON output with all intermediate scores:**
The LLM must output `budget_score`, `availability_score`, `margin_score`, and
`total_score` separately in the response. This forces the LLM to show its work
— intermediate steps are verifiable.

**Layer 3 — RAG retrieves the scoring formula TABLE specifically:**
```python
q3 = "scoring formula table Agent 3 capital allocation 0 100 points"
# element_type=table filter targets the structural scoring table from the policy doc
```
This gives the LLM a second grounding source — the formula from the policy document
reinforces the formula in the system prompt.

**What's still probabilistic:**
The LLM can still compute `(1 - 45000/250000) x 40` wrong if it's doing arithmetic
in its head. This is caught by `_parse_json`'s self-correction: `json.loads` validates
that numbers are numbers, not formulas.

### Why It Matters
The scoring formula is the most auditable part of the system — a regulator
could check it. Multi-layer enforcement (prompt + structured output + RAG)
is the correct defensive pattern.

### Red Flags
- "Just trust the LLM" — LLMs make arithmetic errors
- No mention of the intermediate scores in the JSON output (they enable verification)
- Unaware that the formula table is specifically retrieved from RAG to reinforce the prompt

---

## Q12 — Why does `hitl_node` pre-extract the winner before calling the LLM?

### The Question to Ask
*"In `hitl_node`, the winning option, cost, and pool are extracted in Python before the LLM prompt is built. Why not let the LLM re-derive the winner from `capital_decision`?"*

### Strong Answer
Agent 3 already decided the winner. Letting the LLM re-derive it would risk **decision drift**:

```python
# In hitl_node — Python pre-extraction:
winner_id       = capital_decision.get("recommended", "A")
winner_cost_aed = capital_decision.get("approval_amount_aed", 0)
winner_pool     = capital_decision.get("approval_pool", "CP001")

winner_summary = (
    f"WINNER — pre-extracted by system (DO NOT CHANGE):\n"
    f"  Option {winner_id} | AED {winner_cost_aed:,.0f} | Pool {winner_pool}\n"
    f"  Approval required: {capital_decision.get('approval_required', True)}"
)
```

If the LLM re-reads `capital_decision` and re-selects the winner, it might:
- Choose based on a different heuristic (cost vs score)
- "Round" the cost slightly and create a mismatch with Agent 3's decision
- Pick a different option if the briefing format confused it

The human reads the briefing expecting to approve exactly what Agent 3 scored.
If the briefing says Option C but Agent 3 scored Option A, the audit trail
breaks — the human approved something the system didn't recommend.

After the LLM writes the briefing, there's also a validation check:
```python
if f"Option {winner_id}" not in briefing:
    logger.warning("HITL MISMATCH DETECTED — briefing does not reference winner")
```

### Why It Matters
Decision consistency across agent outputs is a production correctness requirement.
Pre-extraction + validation is the defensive pattern. "Trust the LLM to be consistent"
is not acceptable for financial decisions.

### Red Flags
- "The LLM is consistent enough" — LLMs are non-deterministic at temperature > 0
- No awareness of the `logger.warning` mismatch check
- Can't explain what "decision drift" means in a multi-agent pipeline

---

## Q13 — What does `allow_delegation=False` do in CrewAI agents, and why is it important?

### The Question to Ask
*"All three CrewAI agents have `allow_delegation=False`. What does delegation mean in CrewAI and why is it disabled?"*

### Strong Answer
CrewAI's delegation feature allows an agent to **ask another agent to do work for it**:
```
Without restriction:
  Forecast Strategist is writing the demand_summary
  It thinks: "I need more data — I'll ask the Data Analyst to run another query"
  → CrewAI routes a sub-task back to the Data Analyst
  → Data Analyst runs another tool call
  → Result comes back to the Forecast Strategist
```

This is disabled (`allow_delegation=False`) because:
1. **Predictability:** In ORCA, each agent has a clear, bounded role. Delegation
   creates unbounded execution chains — the Strategist might repeatedly ask for
   more data, exploding latency and token usage.
2. **Tool boundaries:** Only the Data Analyst has tools. Delegation would allow
   the Strategist to use them indirectly, breaking the role separation.
3. **Auditability:** If the Forecast Strategist delegates, the final demand_summary
   is harder to explain — which agent's judgment prevailed?

`max_iter=5` (Data Analyst) and `max_iter=3` (others) are set for similar
reasons — bound the maximum number of tool calls per agent.

### Why It Matters
Unbounded delegation is a common cause of runaway CrewAI executions in production
(infinite loops, token exhaustion). Knowing to disable it shows production awareness.

### Red Flags
- Doesn't know CrewAI has delegation (it's non-obvious from the docs)
- Thinks `allow_delegation=True` is safer — it's the opposite
- Can't explain how `max_iter` interacts with delegation (both bound execution depth)

---

## Q14 — How does the pipeline log save_node fit into the LangGraph graph structure?

### The Question to Ask
*"There's a `save_node` at the end of every path. How is it connected to the graph?"*

### Strong Answer
```python
# In build_graph():
# All three terminal nodes (hitl, execute, suspend) converge to save_node:
builder.add_edge("hitl_node",    "save_node")
builder.add_edge("execute_node", "save_node")
builder.add_edge("suspend_node", "save_node")
builder.add_edge("save_node",    END)
```

Visual flow:
```
agent1 → agent2 → agent3 → route_node
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
     hitl_node          execute_node         suspend_node
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                          save_node
                              │
                             END
```

`save_node` calls `save_pipeline_run()` which writes the full pipeline state
to the `pipeline_log` SQLite table:
```python
save_pipeline_run(
    pipeline_id      = state["pipeline_id"],
    final_status     = state.get("final_status"),
    demand_summary   = state.get("demand_summary"),
    options_package  = state.get("options_package"),
    capital_decision = state.get("capital_decision"),
    hitl_briefing    = state.get("hitl_briefing"),
)
```

This is the **audit log** — immutable record of every pipeline run.

### Why It Matters
The fan-in pattern (multiple nodes converging to one node) is a common LangGraph
structure. Understanding it shows the candidate has designed multi-path graphs, not
just linear pipelines.

### Red Flags
- Thinks `save_node` runs after every node (it only runs at terminal nodes)
- Confuses `save_node` (audit log) with the checkpoint store (SqliteSaver)
- Can't explain why all three terminal nodes connect to the same save_node
  (DRY principle — audit write happens once, consistently)

---

## Q15 — What are the known limitations of CrewAI in ORCA and what is the fallback?

### The Question to Ask
*"You said CrewAI is used for Agent 1's demand analysis. Does it always work?"*

### Strong Answer
**Known Issue (HIGH priority):** CrewAI fails on every run in ORCA's current deployment.

Root cause: CrewAI injects `cache_breakpoint` into the system message before
sending to the LLM. Groq's API rejects this field — it's not a standard
OpenAI API field:

```
CrewAI builds:
  system_message = "You are a data analyst..." + "\ncache_breakpoint: ..."
                                                          ↑
                                              Groq API: 422 Unprocessable Entity
```

**The fallback in agent1_node:**
```python
try:
    demand_summary = run_forecast_crew(sku_id, ...)
except Exception as e:
    logger.warning(f"CrewAI failed ({e}) — falling back to single LLM call")
    messages = PROMPTS["agent1"].format_messages(...)
    response = llm.invoke(messages)
    demand_summary = _parse_json(response.content, "Agent 1")
```

The single LLM fallback produces a valid `demand_summary` — same structure,
just without the richer `demand_trend`, `confidence_score`, and `crew_insights` fields
that the 3-agent crew would add.

**Fix options:** Use CrewAI's `LLM` wrapper with `is_anthropic=False` to prevent
`cache_breakpoint` injection, or patch CrewAI's message builder.

### Why It Matters
Knowing the known issues of your own system is a must for a senior engineer.
The `cache_breakpoint` error is subtle (it's injected invisibly) and the graceful
fallback is correct. Pretending everything works is a red flag.

### Red Flags
- Claims CrewAI works fine — hasn't run the system
- Can't explain what `cache_breakpoint` is or why it causes the failure
- "Just remove the try/except" — would crash the entire pipeline on every run

---

## Q16 — What is the `AgentState` TypedDict and why are all fields `Optional`?

### The Question to Ask
*"The `AgentState` has fields like `demand_summary: Optional[dict]`. Why Optional, and what happens if an agent writes None to one of them?"*

### Strong Answer
```python
class AgentState(TypedDict):
    sku_id:           str            # required from the start
    store_id:         str            # required from the start
    pipeline_id:      str            # required from the start
    demand_summary:   Optional[dict] # None until Agent 1 writes it
    options_package:  Optional[dict] # None until Agent 2 writes it
    capital_decision: Optional[dict] # None until Agent 3 writes it
    hitl_briefing:    Optional[str]  # None until hitl_node/execute_node writes it
    route:            Optional[str]  # None until route_node writes it
    final_status:     Optional[str]  # None until terminal node writes it
```

`Optional` fields represent **data that doesn't exist yet at graph start**.
The pipeline is a pipeline — Agent 2 can't read `demand_summary` before
Agent 1 has run.

The GET `/state` endpoint polls this progressively:
```
t=0:   demand_summary=None, options_package=None, capital_decision=None
t=15s: demand_summary={...}, options_package=None, capital_decision=None  ← Agent 1 done
t=30s: demand_summary={...}, options_package={...}, capital_decision=None ← Agent 2 done
t=45s: demand_summary={...}, options_package={...}, capital_decision={...} ← Agent 3 done
```

If an agent writes `None` to a field, downstream agents use `state.get("x", {})` as
a safe default — they won't crash, but they'll produce degraded output.

### Why It Matters
TypedDict state design is a core LangGraph skill. The progressive None → value
pattern maps directly to the frontend's incremental rendering.

### Red Flags
- "All fields should be required" — would prevent incremental state builds
- Can't explain the connection between Optional fields and the polling endpoint
- Thinks `Optional` means "sometimes the agent skips writing it" — agents always
  write their field; Optional means it starts as None

---

## Q17 — If you had to add a 5th agent to the pipeline, what would you change?

### The Question to Ask
*"You want Agent 5 to send a WhatsApp message to the supplier after `execute_node`. What code changes are needed?"*

### Strong Answer
Four changes required:

**1. Add Agent 5 output field to AgentState:**
```python
class AgentState(TypedDict):
    ...
    notification_status: Optional[str]  # ← new field
```

**2. Write the new node:**
```python
def agent5_node(state: AgentState) -> dict:
    # reads: state["hitl_briefing"], state["capital_decision"]
    # sends WhatsApp via Twilio or similar
    # returns the notification status
    return {"notification_status": "sent"}
```

**3. Register the node and add an edge:**
```python
builder.add_node("agent5_node", agent5_node)
builder.add_edge("execute_node", "agent5_node")  # instead of "save_node"
builder.add_edge("agent5_node", "save_node")
```

**4. Add an MCP tool if the WhatsApp call should be discoverable:**
```python
# In mcp_server/server.py:
@mcp.tool()
def send_whatsapp_notification(phone: str, message: str) -> dict:
    ...
```

Because MCP tools are discovered dynamically, the new tool is immediately
available to Agent 5 without changing any agent code.

The rest of the pipeline — Agents 1-4, the HITL mechanism, and save_node —
is **completely unchanged**.

### Why It Matters
This question tests whether the candidate understands extensibility. A correct
answer shows: (a) TypedDict extension, (b) edge rewiring, (c) the MCP tool
discovery benefit (no change to existing agents).

### Red Flags
- "I'd put it inside execute_node" — violates single-responsibility
- Thinks all agents need to be rewritten to accommodate the new field
- Unaware that LangGraph nodes returning a partial dict only update that field
  (other fields in AgentState are unchanged)

---

## Scoring Guide for Recruiters

| Score | What It Means |
|---|---|
| Explains LangGraph + CrewAI + async bridge precisely | Strong hire — has built production agents |
| Knows frameworks conceptually, misses async details | Solid hire — needs one production cycle |
| "I've used LangChain agents" without LangGraph specifics | Caution — may be framework-surfacer |
| Can't distinguish LangGraph graph from a function chain | Red flag — tutorial-level knowledge only |

**Questions that most separate senior from junior agent engineers:**
- Q2 (the sync/async bridge — the hardest question in this set)
- Q5 (interrupt_before vs interrupt_after — must understand WHY)
- Q6 (resume with approved=False — tests `update_state` knowledge)
- Q12 (pre-extraction to prevent decision drift — defensive engineering)
- Q15 (known issues — intellectual honesty about your own system)
