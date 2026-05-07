'''
What queries.py is doing in one line:

It is your data access layer. Every time an agent needs to know something, it calls a function from queries.py. 
That function goes to the database, gets the answer, and returns it as a clean Python dictionary.
That's it. It's just a collection of "go fetch this information" functions.

'''

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from typing import Optional
from sqlalchemy import create_engine, text

DB_PATH = Path(__file__).parent / "orca.db"
engine = create_engine(f'sqlite:///{DB_PATH}')

# ── helpers ───────────────────────────────────────────────────────────────────

def _fetchone(sql: str, params: dict = {}) -> Optional[dict]:
    """Execute SQL and return first row as dict, or None."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        row = result.fetchone()
        if row is None:
            return None
        return dict(zip(result.keys(), row))

def _fetchall(sql: str, params: dict = {}) -> list[dict]:
    """Execute SQL and return all rows as list of dicts."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        keys = result.keys()
        return [dict(zip(keys, row)) for row in result.fetchall()]
    
# ══════════════════════════════════════════════════════════════════════════════
# AGENT 1 QUERIES — Demand Intelligence
# ══════════════════════════════════════════════════════════════════════════════

def get_critical_alerts() -> list[dict]:
    """
    Returns all inventory positions with stock_status Critical or At Risk.
    This is the Auto 1 trigger condition — the entry point of the agent chain.
    Grouped by sku_id to match RCC Auto 1 behaviour (one pipeline per SKU).
 
    Returns: list of dicts with sku_id, total critical stores,
             total at risk stores, min days_of_cover across all positions.
    """

    return _fetchall("""
        SELECT
            ci.sku_id,
            cs.sku_name,
            cs.category,
            cs.abc_class,
            COUNT(CASE WHEN ci.stock_status = 'Critical' THEN 1 END)  AS critical_stores,
            COUNT(CASE WHEN ci.stock_status = 'At Risk'  THEN 1 END)  AS at_risk_stores,
            SUM(ci.current_stock_units)                               AS total_current_stock,
            MIN(ci.days_of_cover)                                     AS min_days_of_cover,
            MAX(ci.risk_score)                                        AS max_risk_score
            from curated_inventory ci
            join curated_Skus cs on ci.sku_id = cs.sku_id
            WHERE  ci.stock_status IN ('Critical', 'At Risk')
            GROUP BY ci.sku_id, cs.sku_name, cs.category, cs.abc_class
            ORDER BY max_risk_score DESC
            """)

def get_inventory_position(store_id: str, sku_id: str) -> Optional[dict]:
    """
    Returns full inventory position for one Store × SKU combination.
    L1 + L2 combined: Position → Store + SKU.
 
    Maps to RCC: Agent 1 querying RCC Inventory Position object.
    """
    
    return _fetchone("""
        SELECT
            ci.record_id,
            ci.store_id,
            ci.sku_id,
            ci.current_stock_units,
            ci.warehouse_stock_units,
            ci.days_of_cover,
            ci.days_to_stockout,
            ci.stock_status,
            ci.coverage_gap_units,
            ci.risk_score,
            ci.reorder_triggered,
            ci.last_replenishment_date,
            ci.next_delivery_date,
            -- joined store fields (L1)
            cst.store_name,
            cst.region,
            cst.tier,
            cst.store_format,
            cst.store_priority_score,
            cst.annual_revenue_aed,
            -- joined sku fields (L2)
            csk.sku_name,
            csk.category,
            csk.abc_class,
            csk.effective_lead_time,
            csk.event_uplift_factor,
            csk.gross_margin_pct,
            csk.margin_priority_rank,
            csk.reorder_point,
            csk.min_order_qty,
            csk.unit_cost_aed,
            csk.selling_price_aed,
            csk.supplier_id
        FROM   curated_inventory  ci
        JOIN   curated_stores     cst ON ci.store_id = cst.store_id
        JOIN   curated_skus       csk ON ci.sku_id   = csk.sku_id
        WHERE  ci.store_id = :store_id
        AND    ci.sku_id   = :sku_id
    """, {"store_id": store_id, "sku_id": sku_id})
    


def get_all_positions_for_sku(sku_id: str) -> list[dict]:
    """
    Returns all inventory positions for a given SKU across all stores.
    Used by Agent 1 to analyse the full picture for a triggered SKU.
    Only returns Critical and At Risk positions.
 
    Maps to RCC: Agent 1 step 1 — query positions where stock_status
    = Critical or At Risk, grouped by sku_id trigger.
    """
    return _fetchall("""
        SELECT
            ci.record_id,
            ci.store_id,
            ci.sku_id,
            ci.current_stock_units,
            ci.warehouse_stock_units,
            ci.days_of_cover,
            ci.days_to_stockout,
            ci.stock_status,
            ci.coverage_gap_units,
            ci.risk_score,
            cst.store_name,
            cst.tier,
            cst.region,
            cst.store_priority_score,
            cst.annual_revenue_aed
        FROM   curated_inventory ci
        JOIN   curated_stores    cst ON ci.store_id = cst.store_id
        WHERE  ci.sku_id = :sku_id
        AND    ci.stock_status IN ('Critical', 'At Risk')
        ORDER BY ci.risk_score DESC
    """, {"sku_id": sku_id})

def get_sales_velocity(sku_id: str, store_id: Optional[str] = None) -> dict:
    """
    Returns avg_daily_demand and demand_trend_7d for a SKU.
    If store_id given → single store velocity.
    If store_id None  → aggregated across all stores.
 
    Maps to RCC Agent 1 step 4:
    projected_demand = avg_daily_demand × event_uplift × duration
    """
    if store_id:
        row = _fetchone("""
            SELECT
                sku_id,
                store_id,
                avg_daily_demand,
                demand_trend_7d,
                event_baseline_uplift
            FROM  curated_sales
            WHERE sku_id   = :sku_id
            AND   store_id = :store_id
        """, {"sku_id": sku_id, "store_id": store_id})
        return row or {"avg_daily_demand": 0, "demand_trend_7d": 0, "event_baseline_uplift": 1.0}
    else:
        # aggregate across all stores
        row = _fetchone("""
            SELECT
                sku_id,
                SUM(avg_daily_demand)       AS avg_daily_demand,
                AVG(demand_trend_7d)        AS demand_trend_7d,
                AVG(event_baseline_uplift)  AS event_baseline_uplift
            FROM  curated_sales
            WHERE sku_id = :sku_id
            GROUP BY sku_id
        """, {"sku_id": sku_id})
        return row or {"avg_daily_demand": 0, "demand_trend_7d": 0, "event_baseline_uplift": 1.0}

def get_active_events_for_category(category: str) -> list[dict]:
    """
    Returns upcoming or active events that affect the given SKU category.
    Checks planning_lead_days window — same logic as curated_skus event_uplift_factor.
 
    Maps to RCC Agent 1 step 3:
    Query Event Calendar for active/upcoming events matching SKU category.
    """
    return _fetchall("""
        SELECT
            event_id,
            event_name,
            event_type,
            start_date,
            end_date,
            duration_days,
            demand_uplift_pct,
            affected_categories,
            affected_region,
            planning_lead_days
        FROM   staged_events
        WHERE  (
                    affected_categories LIKE '%' || :category || '%'
                OR  affected_region = 'All UAE'
               )
        ORDER BY start_date ASC
    """, {"category": category})


def get_sku_details(sku_id: str) -> Optional[dict]:
    """
    Returns full SKU details including all curated derived columns.
    L2 link: Inventory Position → SKU.
 
    Maps to RCC Agent 2: follow rccSku link to get effective_lead_time,
    abc_class, unit_cost, supplier_id for option building.
    """
    return _fetchone("""
        SELECT
            csk.sku_id,
            csk.sku_name,
            csk.category,
            csk.sub_category,
            csk.supplier_id,
            csk.unit_cost_aed,
            csk.selling_price_aed,
            csk.gross_margin_pct,
            csk.reorder_point,
            csk.min_order_qty,
            csk.lead_time_days,
            csk.effective_lead_time,
            csk.event_uplift_factor,
            csk.margin_priority_rank,
            csk.abc_class,
            csk.is_seasonal,
            csk.shelf_life_days,
            csk.weight_kg,
            csk.reliability_score
        FROM curated_skus csk
        WHERE csk.sku_id = :sku_id
    """, {"sku_id": sku_id})
 
 
def get_supplier_for_sku(sku_id: str) -> Optional[dict]:
    """
    Resolves supplier contact dynamically: SKU → Supplier.
    L3 link: RCC SKU → RCC Supplier.
 
    Maps to RCC Agent 2 supplier resolution:
    pipeline → sku_id → RCC SKU → rccSupplier link → RCC Supplier.
    Contact name and email NEVER hardcoded — always resolved here.
    """
    return _fetchone("""
        SELECT
            ss.supplier_id,
            ss.supplier_name,
            ss.country,
            ss.lead_time_days,
            ss.min_order_value_aed,
            ss.reliability_score,
            ss.allows_expedite,
            ss.expedite_premium_pct,
            ss.payment_terms_days,
            ss.contact_name,
            ss.contact_email,
            ss.annual_contract_value_aed
        FROM   curated_skus       csk
        JOIN   staged_suppliers   ss  ON csk.supplier_id = ss.supplier_id
        WHERE  csk.sku_id = :sku_id
    """, {"sku_id": sku_id})
 
 
def get_tier1_stores_for_sku(sku_id: str) -> list[dict]:
    """
    Returns Tier-1 stores that have at-risk positions for this SKU.
    Used by Agent 2 for Option B (profit-max — Tier-1 stores only).
 
    Maps to RCC Agent 2 Option B:
    Only Tier-1 stores by store_priority_score.
    """
    return _fetchall("""
        SELECT
            ci.store_id,
            ci.sku_id,
            ci.current_stock_units,
            ci.coverage_gap_units,
            ci.stock_status,
            cst.store_name,
            cst.tier,
            cst.store_priority_score,
            cst.annual_revenue_aed
        FROM   curated_inventory ci
        JOIN   curated_stores    cst ON ci.store_id = cst.store_id
        WHERE  ci.sku_id = :sku_id
        AND    cst.tier  = 'Tier-1'
        AND    ci.stock_status IN ('Critical', 'At Risk')
        ORDER BY cst.store_priority_score DESC
    """, {"sku_id": sku_id})
 
 
# ══════════════════════════════════════════════════════════════════════════════
# AGENT 3 QUERIES — Capital Allocation
# ══════════════════════════════════════════════════════════════════════════════
 
def get_capital_pool(pool_id: str) -> Optional[dict]:
    """
    Returns live capital pool budget for a specific pool.
    Used by Agent 3 to check available_aed before approving any option.
 
    Maps to RCC Agent 3: fetch live capital pool budgets.
    """
    return _fetchone("""
        SELECT
            cc.pool_id,
            cc.pool_name,
            cc.pool_type,
            cc.total_budget_aed,
            cc.allocated_aed,
            cc.available_aed,
            cc.utilization_pct,
            cc.pool_pressure_flag,
            cc.priority_rank,
            cc.owner_dept,
            cc.approval_threshold_aed,
            cc.auto_approve_limit_aed
        FROM curated_capital cc
        WHERE cc.pool_id = :pool_id
    """, {"pool_id": pool_id})
 
 
def get_all_capital_pools() -> list[dict]:
    """
    Returns all capital pools with pressure flags.
    Agent 3 Rule 1: pool_pressure_flag = HIGH → eliminate ALL options
    using that pool.
    """
    return _fetchall("""
        SELECT
            pool_id,
            pool_name,
            pool_type,
            total_budget_aed,
            available_aed,
            utilization_pct,
            pool_pressure_flag,
            priority_rank,
            approval_threshold_aed,
            auto_approve_limit_aed,
            owner_dept
        FROM curated_capital
        ORDER BY priority_rank ASC
    """)
 
 
# ══════════════════════════════════════════════════════════════════════════════
# AGENT 4 QUERIES — Exception + Writeback
# ══════════════════════════════════════════════════════════════════════════════
 
def get_store_details(store_id: str) -> Optional[dict]:
    """
    Returns full store details including curated priority score.
    L1 link: Inventory Position → Store.
    """
    return _fetchone("""
        SELECT
            store_id,
            store_name,
            region,
            city,
            tier,
            store_format,
            floor_area_sqm,
            monthly_footfall,
            annual_revenue_aed,
            manager_name,
            store_priority_score
        FROM curated_stores
        WHERE store_id = :store_id
    """, {"store_id": store_id})
 
 
def writeback_reorder_triggered(
    store_id: str,
    sku_id:   str,
    value:    str = "Yes"
) -> bool:
    """
    Writes reorder_triggered back to curated_inventory.
    This is the ONLY writeback operation in the entire system.
 
    Maps to RCC Action Type: 'Edit RCC Inventory Position'
    Approval: ON (HITL required before this runs)
    Properties exposed: reorder_triggered ONLY
 
    Returns True if update succeeded.
    """
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE curated_inventory
                SET    reorder_triggered = :value
                WHERE  store_id = :store_id
                AND    sku_id   = :sku_id
            """), {"value": value, "store_id": store_id, "sku_id": sku_id})
        return True
    except Exception as e:
        print(f"  ❌  writeback failed: {e}")
        return False
 
 
def writeback_reorder_for_all_positions(sku_id: str) -> int:
    """
    Writes reorder_triggered=Yes for ALL Critical and At Risk positions
    for a given SKU. Used by Agent 4 AUTO_EXECUTE route.
 
    Maps to RCC: Agent 4 AUTO_EXECUTE → reorder_triggered=Yes on ALL
    Critical and At Risk positions for the SKU.
 
    Returns count of rows updated.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE curated_inventory
                SET    reorder_triggered = 'Yes'
                WHERE  sku_id      = :sku_id
                AND    stock_status IN ('Critical', 'At Risk')
            """), {"sku_id": sku_id})
        return result.rowcount
    except Exception as e:
        print(f"  ❌  bulk writeback failed: {e}")
        return 0
 
 
# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD QUERIES — KPIs and Widgets
# ══════════════════════════════════════════════════════════════════════════════

def get_store_kpis() -> dict:
    """
    Returns system-wide KPI summary for the dashboard header.
    Maps to RCC Workshop KPI Command Centre — Widget row 1.
    """
    row = _fetchone("""
        SELECT
            COUNT(*)                                                    AS total_positions,
            COUNT(CASE WHEN stock_status = 'Critical'  THEN 1 END)     AS critical_count,
            COUNT(CASE WHEN stock_status = 'At Risk'   THEN 1 END)     AS at_risk_count,
            COUNT(CASE WHEN stock_status = 'Healthy'   THEN 1 END)     AS healthy_count,
            COUNT(CASE WHEN stock_status = 'Overstock' THEN 1 END)     AS overstock_count,
            COUNT(CASE WHEN reorder_triggered = 'Yes'  THEN 1 END)     AS reorder_triggered_count,
            ROUND(
                COUNT(CASE WHEN stock_status = 'Healthy' THEN 1 END)
                * 100.0 / COUNT(*), 1
            )                                                           AS fill_rate_pct,
            ROUND(AVG(risk_score), 4)                                   AS avg_risk_score
        FROM curated_inventory
    """)
    return row or {}


def get_top_risk_skus(limit: int = 10) -> list[dict]:
    """
    Returns top N SKUs by aggregate risk score across all stores.
    Maps to RCC Workshop Widget 6 — Top At-Risk SKUs.
    L5 inverse link: RCC SKU → RCC Inventory Positions.
    """
    return _fetchall("""
        SELECT
            ci.sku_id,
            csk.sku_name,
            csk.category,
            csk.abc_class,
            COUNT(CASE WHEN ci.stock_status = 'Critical' THEN 1 END)  AS critical_stores,
            COUNT(CASE WHEN ci.stock_status = 'At Risk'  THEN 1 END)  AS at_risk_stores,
            SUM(ci.current_stock_units)                                AS total_stock,
            ROUND(MAX(ci.risk_score), 4)                               AS max_risk_score,
            ROUND(MIN(ci.days_of_cover), 1)                            AS min_days_of_cover
        FROM   curated_inventory ci
        JOIN   curated_skus      csk ON ci.sku_id = csk.sku_id
        WHERE  ci.stock_status IN ('Critical', 'At Risk')
        GROUP BY ci.sku_id, csk.sku_name, csk.category, csk.abc_class
        ORDER BY max_risk_score DESC
        LIMIT :limit
    """, {"limit": limit})


def get_store_positions(store_id: str) -> list[dict]:
    """
    Returns all inventory positions for a specific store.
    Maps to RCC Workshop Widget 3 — store drill-down.
    L4 inverse link: RCC Store → RCC Inventory Positions.
    """
    return _fetchall("""
        SELECT
            ci.record_id,
            ci.sku_id,
            csk.sku_name,
            csk.category,
            csk.abc_class,
            ci.current_stock_units,
            ci.days_of_cover,
            ci.days_to_stockout,
            ci.stock_status,
            ci.risk_score,
            ci.reorder_triggered
        FROM   curated_inventory ci
        JOIN   curated_skus      csk ON ci.sku_id = csk.sku_id
        WHERE  ci.store_id = :store_id
        ORDER BY ci.risk_score DESC
    """, {"store_id": store_id})


def get_dashboard_inventory_heatmap() -> list[dict]:
    """
    Returns store × SKU risk data for the Streamlit heatmap widget.
    Top 20 SKUs by risk × all stores — manageable for plotly px.imshow().
    """
    return _fetchall("""
        SELECT
            ci.store_id,
            ci.sku_id,
            ci.stock_status,
            ci.risk_score,
            ci.days_of_cover,
            ci.current_stock_units
        FROM curated_inventory ci
        WHERE ci.sku_id IN (
            SELECT sku_id
            FROM   curated_inventory
            WHERE  stock_status IN ('Critical','At Risk')
            GROUP BY sku_id
            ORDER BY MAX(risk_score) DESC
            LIMIT 20
        )
        ORDER BY ci.sku_id, ci.store_id
    """)



# ══════════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════════
 
if __name__ == "__main__":
    print("\n🔍  Testing db/queries.py against orca.db\n")
 
    print("── get_critical_alerts() — top 5 ──────────────────────────────")
    alerts = get_critical_alerts()
    print(f"  Total SKUs with alerts: {len(alerts)}")
    for a in alerts[:5]:
        print(f"  {a['sku_id']} | {a['sku_name']:<30} | critical={a['critical_stores']} "
              f"at_risk={a['at_risk_stores']} | risk={a['max_risk_score']}")
 
    if alerts:
        top_sku = alerts[0]["sku_id"]
 
        print(f"\n── get_all_positions_for_sku('{top_sku}') — first 3 ───────────")
        positions = get_all_positions_for_sku(top_sku)
        print(f"  Total positions: {len(positions)}")
        for p in positions[:3]:
            print(f"  {p['store_id']} | stock={p['current_stock_units']} "
                  f"| doc={p['days_of_cover']} | {p['stock_status']} | tier={p['tier']}")
 
        print(f"\n── get_sku_details('{top_sku}') ───────────────────────────────")
        sku = get_sku_details(top_sku)
        if sku:
            print(f"  {sku['sku_name']} | category={sku['category']} "
                  f"| abc={sku['abc_class']} | margin={sku['gross_margin_pct']}%")
            print(f"  lead_time={sku['lead_time_days']}d → effective={sku['effective_lead_time']}d")
            print(f"  event_uplift_factor={sku['event_uplift_factor']}")
 
        print(f"\n── get_supplier_for_sku('{top_sku}') — L3 link ───────────────")
        supplier = get_supplier_for_sku(top_sku)
        if supplier:
            print(f"  {supplier['supplier_name']} ({supplier['country']})")
            print(f"  Contact: {supplier['contact_name']} | {supplier['contact_email']}")
            print(f"  expedite={supplier['allows_expedite']} | premium={supplier['expedite_premium_pct']}%")
 
        print(f"\n── get_sales_velocity('{top_sku}') — aggregated ───────────────")
        vel = get_sales_velocity(top_sku)
        print(f"  avg_daily_demand={vel['avg_daily_demand']} | trend_7d={vel['demand_trend_7d']}")
 
        print(f"\n── get_active_events_for_category() ───────────────────────────")
        if sku:
            events = get_active_events_for_category(sku["category"])
            print(f"  Events found: {len(events)}")
            for e in events:
                print(f"  {e['event_name']} | uplift={e['demand_uplift_pct']}% "
                      f"| lead={e['planning_lead_days']}d")
 
    print(f"\n── get_all_capital_pools() ─────────────────────────────────────")
    pools = get_all_capital_pools()
    for p in pools:
        print(f"  {p['pool_id']} | {p['pool_name']:<35} "
              f"| avail=AED {p['available_aed']:>10,.0f} | {p['pool_pressure_flag']}")
 
    print(f"\n── get_store_kpis() ────────────────────────────────────────────")
    kpis = get_store_kpis()
    print(f"  Fill rate    : {kpis.get('fill_rate_pct')}%")
    print(f"  Critical     : {kpis.get('critical_count')}")
    print(f"  At Risk      : {kpis.get('at_risk_count')}")
    print(f"  Avg risk score: {kpis.get('avg_risk_score')}")
 
    print(f"\n── get_top_risk_skus() — top 5 ────────────────────────────────")
    top_skus = get_top_risk_skus(5)
    for s in top_skus:
        print(f"  {s['sku_id']} | {s['sku_name']:<30} | "
              f"critical={s['critical_stores']} | risk={s['max_risk_score']}")
 
    print("\n✅  All queries working.\n")