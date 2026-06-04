# ADR-002: MCP Tools for Structured Data Over Direct Database Calls

**Status:** Accepted  
**Date:** 2026-05-15  
**Authors:** ORCA Engineering

---

## Context

Each of the 4 agents needs to read live inventory data from SQLite before making decisions:

- **Agent 1** needs: current stock positions, sales velocity, active events
- **Agent 2** needs: SKU details, supplier information, tier-1 store list
- **Agent 3** needs: capital pool budgets and pressure flags (CP001, CP003 separately)
- **Agent 4** needs: supplier contact details (for the HITL briefing)

The first prototype had each agent node directly import and call `db/queries.py` functions:

```python
# Original approach — direct imports inside graph.py
from db.queries import get_all_positions_for_sku, get_sku_details, get_supplier_for_sku

def agent1_node(state):
    positions = get_all_positions_for_sku(state["sku_id"])
    velocity  = get_sales_velocity(state["sku_id"])
    ...
```

This created a hard dependency between `graph.py` and `db/queries.py`. Every new piece of data an agent needed required modifying both files and redeploying the entire API. It also mixed concerns: orchestration logic (graph.py) was entangled with data access logic (queries.py).

At Palantir RCC (the system ORCA rebuilds), agents queried objects via Palantir's Application object model — a structured, discoverable interface. The closest open-source equivalent is the Model Context Protocol (MCP).

---

## Decision

Expose all data access as **MCP tools** via a standalone subprocess server (`mcp_server/server.py`). The LangGraph pipeline connects to this server at runtime using `MultiServerMCPClient` and discovers tools dynamically.

```python
# mcp_server/server.py — 6 tools registered via FastMCP
@mcp.tool()
def check_inventory_positions(sku_id: str) -> dict:
    """
    Returns inventory positions for a SKU across all stores.
    Includes critical_count, at_risk_count, total_current_stock,
    total_projected_shortfall, and a positions list sorted by risk_score.
    """
    return db_queries.get_all_positions_for_sku(sku_id)

@mcp.tool()
def check_capital_budgets(pool_id: str = None) -> dict:
    """
    Returns capital pool data. If pool_id provided, returns that pool only.
    Returns available_aed, utilization_pct, pool_pressure_flag (LOW/MEDIUM/HIGH),
    auto_approve_limit_aed, approval_threshold_aed.
    """
    ...

# 4 more tools: get_sku_info, get_supplier_info, get_demand_velocity, check_active_events
```

```python
# agents/graph.py — tool discovery at runtime
MCP_CLIENT_CONFIG = {
    "orca_db": {
        "command": "python",
        "args": [MCP_SERVER_PATH],
        "transport": "stdio",
    }
}

async def _get_mcp_tools() -> list:
    client = MultiServerMCPClient(MCP_CLIENT_CONFIG)
    tools = await client.get_tools()  # asks server: "what tools do you have?"
    return tools                      # returns LangChain-compatible tool objects
```

The MCP server runs as a **subprocess communicating over stdio**. No HTTP port, no network, no authentication needed for local development. The `transport: "stdio"` configuration means the client writes to the subprocess's stdin and reads from stdout using the MCP JSON-RPC protocol.

Tool docstrings become the LLM's tool descriptions. Type hints become the input schema. The LLM decides when and how to call each tool — it is not hardcoded in the agent node.

---

## Consequences

**Positive:**

- **Zero changes to graph.py when adding a new tool.** Adding `get_active_promotions(sku_id)` to `mcp_server/server.py` makes it immediately available to all 4 agents on the next pipeline run. The agents can start using it without any orchestration code change. This is the key decoupling benefit.
- **Tools are self-describing.** The LLM reads the docstring to understand what a tool does and when to call it. No hardcoded tool-calling logic in the agent prompts.
- **Clean separation of concerns.** `mcp_server/server.py` owns data access. `agents/graph.py` owns orchestration. Neither needs to know the internals of the other.
- **Testable in isolation.** The MCP server can be started independently and tested with any MCP client without the LangGraph pipeline running.
- **Aligns with Palantir pattern.** The original RCC used AIP Automate's object query system. MCP tools are the closest open-source equivalent, making the rebuild architecturally faithful.

**Negative:**

- **Subprocess overhead.** Every agent node that calls tools starts an MCP subprocess (`MultiServerMCPClient`) and communicates via stdio. For a single-server dev deployment this is acceptable (~50ms overhead). For high-throughput production, a persistent MCP server connection would be more efficient.
- **Debugging is harder.** When an agent calls a tool and gets wrong data, you must trace the call through: agent node → MCP client → stdio → MCP server → queries.py → SQLite. Direct DB calls would have a shorter stack.
- **AsyncIO complexity.** MCP tool calls are async (`await tool.ainvoke(args)`), which requires `_run_async()` helpers to bridge to the synchronous LangGraph node functions. This added boilerplate that a direct DB call would avoid.

---

## Alternatives Considered

| Option | Why Rejected |
|---|---|
| Direct `db/queries.py` imports in graph.py | Hard coupling between orchestration and data. Adding a field to an agent requires editing two unrelated files. |
| LangChain `@tool` decorator (agents/tools.py exists as a fallback) | Kept as fallback only. The `@tool` approach hardcodes tool definitions in graph.py — no dynamic discovery. If the tool list changes, graph.py must change. |
| REST API for data access | Adds HTTP round-trip latency, port management, and auth for what is fundamentally local IPC. MCP stdio is faster for same-machine communication. |
| Direct SQL in agent prompts | Anti-pattern. LLMs generating SQL against a production database is a security and reliability risk. |
