"""
ORCA — agents/tools.py
======================
The 6 tools available to the LangGraph agent.

HOW THIS FILE RELATES TO queries.py:
--------------------------------------
queries.py  = raw data access functions (SQL → dict)
tools.py    = LangChain @tool wrappers around those functions

Each @tool function here either:
    A) Wraps a queries.py function directly (thin wrapper)
    B) Calls one or more queries.py functions and adds
       derived/summary fields on top (enriched wrapper)

Explicit mapping:

    TOOL FUNCTION               QUERIES.PY FUNCTION(S) CALLED
    ─────────────────────────────────────────────────────────────────
    check_inventory_positions   get_all_positions_for_sku()
                                + adds: critical_count, at_risk_count,
                                  total_current_stock as summary

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
"check_inventory_positions" is more natural for an agent reasoning
about inventory than "get_all_positions_for_sku".
The docstrings are also written for the LLM — they tell it WHEN
and HOW to call each tool, not just what the function does.

WHAT IS NOT IN tools.py:
--------------------------------------
writeback functions       → used directly in graph.py nodes only,
                            not exposed as free agent tools
get_critical_alerts()     → used by graph.py to find alerts to process
get_tier1_stores_for_sku  → used directly in graph.py Agent 2 node
dashboard query functions → used by dashboard/app.py only
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from langchain_core.tools import tool
from db.queries import (
    get_all_positions_for_sku,
    get_sku_details,
    get_supplier_for_sku,
    get_sales_velocity,
    get_active_events_for_category,
    get_all_capital_pools,
    get_capital_pool,
)


# ── Tool 1 ────────────────────────────────────────────────────────────────────
# Calls: get_all_positions_for_sku()
# Extra: adds critical_count, at_risk_count, total_current_stock summary

@tool
def check_inventory_positions(sku_id: str) -> dict:
    """
    Returns all Critical and At Risk inventory positions for a given SKU
    across all stores. Use this as your first call when analysing an alert.

    Returns a dict with:
        - sku_id: the SKU analysed
        - critical_count: number of stores in Critical status
        - at_risk_count: number of stores in At Risk status
        - total_current_stock: total units across all at-risk stores
        - positions: list of store positions with store_id, stock,
          days_of_cover, stock_status, tier, store_priority_score

    Use this to understand HOW MANY stores are affected and HOW SEVERE
    the situation is before making any recommendation.
    """
    positions = get_all_positions_for_sku(sku_id)

    if not positions:
        return {
            "sku_id":              sku_id,
            "critical_count":      0,
            "at_risk_count":       0,
            "total_current_stock": 0,
            "positions":           [],
            "message":             "No critical or at-risk positions found for this SKU."
        }

    critical    = [p for p in positions if p["stock_status"] == "Critical"]
    at_risk     = [p for p in positions if p["stock_status"] == "At Risk"]
    total_stock = sum(p["current_stock_units"] for p in positions)

    return {
        "sku_id":              sku_id,
        "critical_count":      len(critical),
        "at_risk_count":       len(at_risk),
        "total_current_stock": total_stock,
        "positions":           positions,
    }


# ── Tool 2 ────────────────────────────────────────────────────────────────────
# Calls: get_sku_details()
# Extra: none — thin wrapper

@tool
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

    Use this AFTER check_inventory_positions to understand the product's
    commercial importance (abc_class, margin) and supply constraints
    (effective_lead_time, min_order_qty) before building options.
    """
    sku = get_sku_details(sku_id)
    if not sku:
        return {"error": f"SKU {sku_id} not found in database."}
    return sku


# ── Tool 3 ────────────────────────────────────────────────────────────────────
# Calls: get_supplier_for_sku()
# Extra: none — thin wrapper

@tool
def get_supplier_info(sku_id: str) -> dict:
    """
    Resolves supplier contact and terms for a given SKU.
    Always call this before recommending any replenishment action —
    the supplier contact must never be hardcoded.

    Returns a dict with:
        - supplier_name, country, contact_name, contact_email
        - lead_time_days, allows_expedite (True/False)
        - expedite_premium_pct: extra cost % for expedited air freight
        - min_order_value_aed, reliability_score (1.0 to 5.0)

    Use allows_expedite to determine if Option C (expedite) is available.
    Use contact_name and contact_email in the HITL briefing so the human
    planner knows exactly who to call.
    """
    supplier = get_supplier_for_sku(sku_id)
    if not supplier:
        return {"error": f"No supplier found for SKU {sku_id}."}
    return supplier


# ── Tool 4 ────────────────────────────────────────────────────────────────────
# Calls: get_sales_velocity()
# Extra: none — thin wrapper

@tool
def get_demand_velocity(sku_id: str) -> dict:
    """
    Returns sales velocity metrics for a SKU aggregated across all stores.

    Returns a dict with:
        - avg_daily_demand: average units sold per day over last 28 days
        - demand_trend_7d: % change in demand last 7 days vs prior 7 days
          (positive = demand rising, negative = demand falling)
        - event_baseline_uplift: historical uplift ratio during event periods
          vs regular periods (e.g. 2.8 means 2.8x normal demand during events)

    Use avg_daily_demand to calculate:
        projected_demand = avg_daily_demand x event_uplift_factor x lead_time_days
        projected_shortfall = projected_demand - total_current_stock
    """
    velocity = get_sales_velocity(sku_id)
    return velocity


# ── Tool 5 ────────────────────────────────────────────────────────────────────
# Calls: get_active_events_for_category()
# Extra: adds events_found count as summary field

@tool
def check_active_events(category: str) -> dict:
    """
    Returns upcoming or active retail events that affect demand for
    a given product category (e.g. 'Dates', 'Beverages', 'Snacks').

    Returns a dict with:
        - events_found: number of relevant events
        - events: list of events, each with event_name, demand_uplift_pct,
          start_date, end_date, planning_lead_days, affected_region

    Use demand_uplift_pct to adjust projected_demand:
        uplift_factor = 1 + (demand_uplift_pct / 100)
        projected_demand = avg_daily_demand x uplift_factor x duration_days

    If events_found = 0, use event_uplift_factor = 1.0 (no adjustment).
    If lead_time_days > days_until_event_start, set lead_time_too_late = True.
    """
    events = get_active_events_for_category(category)
    return {
        "events_found": len(events),
        "events":       events,
    }


# ── Tool 6 ────────────────────────────────────────────────────────────────────
# Calls: get_capital_pool()      — if pool_id is provided
#        get_all_capital_pools() — if no pool_id (returns all pools)
# Extra: conditional logic — one query or the other depending on input

@tool
def check_capital_budgets(pool_id: str = None) -> dict:
    """
    Returns capital pool budget information for evaluating replenishment options.

    If pool_id is provided: returns details for that specific pool.
    If pool_id is None or empty: returns all pools with pressure flags.

    Each pool includes:
        - pool_id, pool_name, available_aed, utilization_pct
        - pool_pressure_flag: LOW, MEDIUM, or HIGH
          HIGH means the pool is constrained — eliminate options using this pool
        - auto_approve_limit_aed: orders below this need no human approval
        - approval_threshold_aed: orders above this go to owner_dept for sign-off

    Use this to:
        1. Check if a pool is HIGH pressure before assigning an option to it
        2. Determine if approval_required = True (cost > auto_approve_limit_aed)

    Call with no pool_id first to see all pools and their pressure flags.
    Then call with a specific pool_id to get exact budget numbers.
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


# ── quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nTesting agents/tools.py\n")

    from db.queries import get_critical_alerts
    alerts = get_critical_alerts()

    if not alerts:
        print("No alerts found — run scheduler first")
    else:
        top     = alerts[0]
        sku_id  = top["sku_id"]
        print(f"Testing with top alert SKU: {sku_id}\n")

        print("-- Tool 1: check_inventory_positions --")
        result = check_inventory_positions.invoke({"sku_id": sku_id})
        print(f"  critical={result['critical_count']} "
              f"at_risk={result['at_risk_count']} "
              f"total_stock={result['total_current_stock']}")

        print("\n-- Tool 2: get_sku_info --")
        result = get_sku_info.invoke({"sku_id": sku_id})
        print(f"  {result.get('sku_name')} | abc={result.get('abc_class')} "
              f"| margin={result.get('gross_margin_pct')}% "
              f"| effective_lead={result.get('effective_lead_time')}d")

        print("\n-- Tool 3: get_supplier_info --")
        result = get_supplier_info.invoke({"sku_id": sku_id})
        print(f"  {result.get('supplier_name')} | "
              f"contact={result.get('contact_name')} | "
              f"email={result.get('contact_email')} | "
              f"expedite={result.get('allows_expedite')}")

        print("\n-- Tool 4: get_demand_velocity --")
        result = get_demand_velocity.invoke({"sku_id": sku_id})
        print(f"  avg_daily_demand={result.get('avg_daily_demand')} | "
              f"trend_7d={result.get('demand_trend_7d')}")

        print("\n-- Tool 5: check_active_events --")
        sku    = get_sku_info.invoke({"sku_id": sku_id})
        result = check_active_events.invoke(
            {"category": sku.get("category", "Dates")}
        )
        print(f"  events_found={result['events_found']}")
        for e in result["events"]:
            print(f"  {e['event_name']} | uplift={e['demand_uplift_pct']}%")

        print("\n-- Tool 6: check_capital_budgets (all pools) --")
        result = check_capital_budgets.invoke({})
        print(f"  total_pools={result['total_pools']}")
        for p in result["pools"][:3]:
            print(f"  {p['pool_id']} | {p['pool_name'][:30]:<30} "
                  f"| avail=AED {p['available_aed']:>10,.0f} "
                  f"| {p['pool_pressure_flag']}")

        print("\n-- Tool 6: check_capital_budgets (specific pool) --")
        result = check_capital_budgets.invoke({"pool_id": "CP001"})
        print(f"  {result.get('pool_name')} | "
              f"available=AED {result.get('available_aed'):,.0f} | "
              f"auto_approve_limit=AED {result.get('auto_approve_limit_aed'):,.0f}")

    print("\nAll tools working.\n")