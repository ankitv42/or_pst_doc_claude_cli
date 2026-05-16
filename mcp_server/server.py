"""
ORCA — mcp_server/server.py
============================
MCP server that exposes all ORCA inventory tools via Model Context Protocol.
 
WHY MCP:
    Without MCP: graph.py imports tools directly — hardcoded, coupled.
    With MCP:    graph.py asks "what tools exist?" at runtime — dynamic, decoupled.
 
    Adding a new tool = add it here. graph.py needs zero changes.
    This is the Fortune 100 production pattern.
 
WHAT IS FastMCP:
    FastMCP is the Python SDK for building MCP servers.
    @mcp.tool() decorator registers a function as an MCP tool.
    The docstring becomes the tool description the LLM reads.
    The type hints become the tool's input schema.
 
HOW IT RUNS:
    stdio transport — server runs as a subprocess.
    graph.py launches it via MultiServerMCPClient and communicates
    via standard input/output. No HTTP port needed for local dev.
 
TOOLS EXPOSED (6 total):
    check_inventory_positions   — all Critical/At Risk stores for a SKU
    get_sku_info                — full SKU details + derived columns
    get_supplier_info           — supplier contact resolved dynamically
    get_demand_velocity         — avg_daily_demand + trend
    check_active_events         — upcoming events for a category
    check_capital_budgets       — capital pool budgets and pressure flags
 
Run standalone to verify:
    python mcp_server/server.py

HOW THIS FILE RELATES TO queries.py:
--------------------------------------
queries.py  = raw data access functions (SQL -> dict)
tools.py    = LangChain @tool wrappers around those functions

Each @tool function here either:
    A) Wraps a queries.py function directly (thin wrapper)
    B) Calls one or more queries.py functions and adds
       derived/summary fields on top (enriched wrapper)

Explicit mapping:

    TOOL FUNCTION               QUERIES.PY FUNCTION(S) CALLED
    -----------------------------------------------------------------
    check_inventory_positions   get_all_positions_for_sku()
                                + adds: critical_count, at_risk_count,
                                  total_current_stock, total_projected_shortfall

    get_sku_info                get_sku_details()
                                thin wrapper, same return value

    get_supplier_info           get_supplier_for_sku()
                                thin wrapper, same return value

    get_demand_velocity         get_sales_velocity()
                                thin wrapper, same return value

    check_active_events         get_active_events_for_category()
                                + adds: events_found count as summary

    check_capital_budgets       get_capital_pool()  (if pool_id given)
                                get_all_capital_pools() (if no pool_id)
                                conditional — one function or the other

WHY DIFFERENT NAMES FROM queries.py:
--------------------------------------
Tool names are written for the LLM to read, not for developers.
The docstrings tell the LLM WHEN and HOW to call each tool.

WHAT IS NOT IN tools.py:
--------------------------------------
writeback functions       -> used directly in graph.py nodes only
get_critical_alerts()     -> used by graph.py to find alerts to process
get_tier1_stores_for_sku  -> used directly in graph.py Agent 2 node
dashboard query functions -> used by dashboard/app.py only
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.queries import (
    get_all_positions_for_sku,
    get_sku_details,
    get_supplier_for_sku,
    get_sales_velocity,
    get_active_events_for_category,
    get_all_capital_pools,
    get_capital_pool,
)
from mcp.server.fastmcp import FastMCP

# create the MCP server instance
mcp = FastMCP("ORCA Inventory Tools")

# ==============================================================================
# TOOL 1 — check_inventory_positions
# ==============================================================================
# ── Tool 1 ────────────────────────────────────────────────────────────────────
# Calls: get_all_positions_for_sku()
# FIX 3: now also sums projected_shortfall across all positions
# and surfaces it as total_projected_shortfall in the summary dict.
# This gives Agent 1 the total shortfall number it needs for demand_summary
# without having to loop through positions itself.

@mcp.tool()
def check_inventory_positions(sku_id: str) -> dict:
    """
    Returns all Critical and At Risk inventory positions for a given SKU
    across all stores. Use this as your first call when analysing an alert.

    Returns a dict with:
        - sku_id: the SKU analysed
        - critical_count: number of stores in Critical status
        - at_risk_count: number of stores in At Risk status
        - total_current_stock: total units currently in stock across all
          at-risk stores
        - total_projected_shortfall: total units shortfall across all
          at-risk stores — use this as the shortfall value in demand_summary
        - positions: full list of store positions including store_id, stock,
          days_of_cover, stock_status, tier, store_priority_score,
          projected_demand, projected_shortfall per store

    Use this to understand HOW MANY stores are affected, HOW SEVERE the
    situation is, and WHAT THE TOTAL SHORTFALL IS before making any
    recommendation.
    """
    positions = get_all_positions_for_sku(sku_id)

    if not positions:
        return {
            "sku_id":                    sku_id,
            "critical_count":            0,
            "at_risk_count":             0,
            "total_current_stock":       0,
            "total_projected_shortfall": 0,
            "positions":                 [],
            "message": "No critical or at-risk positions found for this SKU."
        }

    critical    = [p for p in positions if p["stock_status"] == "Critical"]
    at_risk     = [p for p in positions if p["stock_status"] == "At Risk"]
    total_stock = sum(p["current_stock_units"] for p in positions)

    # FIX 3: sum projected_shortfall across all positions
    # projected_shortfall is now in curated_inventory (added in transforms.py Fix 2)
    # each position has its own shortfall — we sum them for the SKU total
    total_shortfall = sum(
        p.get("projected_shortfall", 0) or 0
        for p in positions
    )

    return {
        "sku_id":                    sku_id,
        "critical_count":            len(critical),
        "at_risk_count":             len(at_risk),
        "total_current_stock":       total_stock,
        "total_projected_shortfall": total_shortfall,
        "positions":                 positions,
    }



# ==============================================================================
# TOOL 2 — get_sku_info
# ==============================================================================
# ── Tool 2 ────────────────────────────────────────────────────────────────────
# Calls: get_sku_details()
# Extra: none — thin wrapper

@mcp.tool()
def get_sku_info(sku_id: str) -> dict:
    """
    Returns full product details for a SKU including commercial and
    supply chain information needed for replenishment decisions.

    Returns a dict with:
        - sku_name, category, abc_class, gross_margin_pct
        - lead_time_days: raw supplier lead time
        - effective_lead_time: lead time adjusted for supplier reliability
        - event_uplift_factor: demand multiplier from any active upcoming event
        - reorder_point, min_order_qty, unit_cost_aed, supplier_id
        - margin_priority_rank: rank within category by gross margin (1 = best)

    Use this AFTER check_inventory_positions to understand the product's
    commercial importance (abc_class, margin) and supply constraints
    (effective_lead_time, min_order_qty) before building options.
    """
    sku = get_sku_details(sku_id)
    if not sku:
        return {"error": f"SKU {sku_id} not found in database."}
    return sku



# ==============================================================================
# TOOL 3 — get_supplier_info
# ==============================================================================
# ── Tool 3 ────────────────────────────────────────────────────────────────────
# Calls: get_supplier_for_sku()
# Extra: none — thin wrapper

@mcp.tool()
def get_supplier_info(sku_id: str) -> dict:
    """
    Resolves supplier contact and terms for a given SKU.
    Always call this before recommending any replenishment action.
    The supplier contact must never be hardcoded — always resolved here.

    Returns a dict with:
        - supplier_name, country, contact_name, contact_email
        - lead_time_days, allows_expedite (True/False)
        - expedite_premium_pct: extra cost % for expedited air freight
        - min_order_value_aed, reliability_score (1.0 to 5.0)

    Use allows_expedite to determine if Option C (expedite) is available.
    If allows_expedite is False, Option C must be eliminated immediately.
    Use contact_name and contact_email in the HITL briefing so the human
    planner knows exactly who to call.
    """
    supplier = get_supplier_for_sku(sku_id)
    if not supplier:
        return {"error": f"No supplier found for SKU {sku_id}."}
    return supplier



# ==============================================================================
# TOOL 4 — get_demand_velocity
# ==============================================================================
# ── Tool 4 ────────────────────────────────────────────────────────────────────
# Calls: get_sales_velocity()
# Extra: none — thin wrapper

@mcp.tool()
def get_demand_velocity(sku_id: str) -> dict:
    """
    Returns sales velocity metrics for a SKU aggregated across all stores.

    Returns a dict with:
        - avg_daily_demand: average units sold per day over last 28 days
        - demand_trend_7d: % change in demand last 7 days vs prior 7 days
          (positive = demand rising, negative = demand falling)
        - event_baseline_uplift: historical uplift ratio during event periods
          vs regular periods (e.g. 2.8 means 2.8x normal demand during events)

    Use avg_daily_demand to verify projected_demand calculations.
    projected_demand is already pre-computed in the database but this
    gives you the raw velocity for your own reasoning.
    """
    velocity = get_sales_velocity(sku_id)
    return velocity



# ==============================================================================
# TOOL 5 — check_active_events
# ==============================================================================
# ── Tool 5 ────────────────────────────────────────────────────────────────────
# Calls: get_active_events_for_category()
# Extra: adds events_found count as summary field

@mcp.tool()
def check_active_events(category: str) -> dict:
    """
    Returns upcoming or active retail events that affect demand for
    a given product category (e.g. 'Dates', 'Beverages', 'Snacks').

    Returns a dict with:
        - events_found: number of relevant events
        - events: list of events, each with event_name, demand_uplift_pct,
          start_date, end_date, duration_days, planning_lead_days,
          affected_region

    Use demand_uplift_pct to verify the event_uplift_factor:
        event_uplift_factor = 1 + (demand_uplift_pct / 100)

    If events_found = 0, set event_uplift_factor = 1.0 and event_name = None.

    To determine lead_time_too_late:
        days_until_event = (start_date - today).days
        lead_time_too_late = effective_lead_time > days_until_event
    """
    events = get_active_events_for_category(category)
    return {
        "events_found": len(events),
        "events":       events,
    }

# ==============================================================================
# TOOL 6 — check_capital_budgets
# ==============================================================================
# ── Tool 6 ────────────────────────────────────────────────────────────────────
# Calls: get_capital_pool()      — if pool_id is provided
#        get_all_capital_pools() — if no pool_id (returns all pools)
# Extra: conditional logic — one query or the other depending on input

@mcp.tool()
def check_capital_budgets(pool_id: str = None) -> dict:
    """
    Returns capital pool budget information for evaluating replenishment options.

    If pool_id is provided: returns details for that specific pool.
    If pool_id is None or empty: returns all pools with pressure flags.

    Each pool includes:
        - pool_id, pool_name, available_aed, utilization_pct
        - pool_pressure_flag: LOW, MEDIUM, or HIGH
          HIGH means the pool is constrained — eliminate ALL options using it
        - auto_approve_limit_aed: orders below this need no human approval
        - approval_threshold_aed: orders above this go to owner_dept

    Standard pool assignments:
        Option A (standard order) -> CP001
        Option B (profit max)     -> CP001
        Option C (expedite)       -> CP003

    Call with no pool_id first to check all pool pressure flags.
    Then call with specific pool_id to get exact available_aed and limits.
    """
    if pool_id:
        pool = get_capital_pool(pool_id)
        if not pool:
            return {"error": f"Pool {pool_id} not found."}
        return pool

    pools = get_all_capital_pools()
    return {
        "total_pools": len(pools),
        "pools":       pools,
    }


# ==============================================================================
# ENTRY POINT
# ==============================================================================
 
if __name__ == "__main__":
    print("ORCA MCP Server starting (stdio transport)...")
    print("Tools registered:")
    print("  1. check_inventory_positions")
    print("  2. get_sku_info")
    print("  3. get_supplier_info")
    print("  4. get_demand_velocity")
    print("  5. check_active_events")
    print("  6. check_capital_budgets")
    mcp.run(transport="stdio")