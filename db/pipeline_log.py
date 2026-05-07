"""
ORCA — db/pipeline_log.py
==========================
Audit log for completed agent pipeline runs.
 
What this file is NOT:
    ❌ NOT a state management tool
    ❌ NOT a replacement for LangGraph state
    ❌ NOT mimicking Palantir's writeback object pattern
 
What this file IS:
    ✅ A simple SQLite audit log
    ✅ Written ONCE after LangGraph completes a full pipeline run
    ✅ Used by the Streamlit dashboard to show decision history
    ✅ Used by humans to audit what agents decided and why
 
In LangGraph (Sprint 2):
    State is managed by AgentState TypedDict — built into LangGraph.
    Each node reads from AgentState, writes to AgentState automatically.
    When the graph finishes, we call save_pipeline_run() here ONCE
    to persist the final result for the dashboard and audit trail.
 
    AgentState (in Sprint 2) will look like:
        class AgentState(TypedDict):
            sku_id:           str
            store_id:         str
            demand_summary:   Optional[dict]
            options_package:  Optional[dict]
            capital_decision: Optional[dict]
            hitl_briefing:    Optional[str]
            final_status:     str   # ESCALATED | AUTO_EXECUTED | SUSPENDED
 
Usage:
    from db.pipeline_log import save_pipeline_run, get_all_runs, get_pending_escalations
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))  # Add parent directory to path for imports

from sqlalchemy import create_engine, text

DB_PATH = Path(__file__).parent / 'orca.db'

engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)

# ══════════════════════════════════════════════════════════════════════════════
# TABLE SETUP
# ══════════════════════════════════════════════════════════════════════════════

def create_pipeline_table() -> None:
    """
    Creates the pipeline_log table if it does not exist.
    Called once when ORCA starts up.
 
    One row = one completed agent pipeline run.
    Written after LangGraph graph execution finishes.
    """
    with engine.connect() as conn:
        conn.execute(text("""
                          create table if not exists pipeline_log (
                          pipeline_id      TEXT PRIMARY KEY,
                sku_id           TEXT    NOT NULL,
                store_id         TEXT    NOT NULL,
                final_status     TEXT    NOT NULL,  -- ESCALATED | AUTO_EXECUTED | SUSPENDED
                demand_summary   TEXT,              -- JSON from Agent 1
                options_package  TEXT,              -- JSON from Agent 2
                capital_decision TEXT,              -- JSON from Agent 3
                hitl_briefing    TEXT,              -- text from Agent 4
                created_at       TEXT    NOT NULL,
                completed_at     TEXT    NOT NULL
            )
        """))
    print("✅  pipeline_log table ready")

# ══════════════════════════════════════════════════════════════════════════════
# WRITE — called once after LangGraph finishes
# ══════════════════════════════════════════════════════════════════════════════



def save_pipeline_run(
    pipeline_id:      str,
    sku_id:           str,
    store_id:         str,
    final_status:     str,
    demand_summary:   dict  = None,
    options_package:  dict  = None,
    capital_decision: dict  = None,
    hitl_briefing:    str   = None,
) -> None:
    """
    Saves a completed pipeline run to the audit log.
 
    Called by LangGraph ONCE when the graph reaches its end node.
    All state comes from AgentState which LangGraph managed internally.
 
    Args:
        pipeline_id:      unique ID for this run — PIPE_{sku_id}_{date}
        sku_id:           the SKU that triggered this pipeline
        store_id:         the store that raised the alert
        final_status:     ESCALATED | AUTO_EXECUTED | SUSPENDED
        demand_summary:   output dict from Agent 1 node
        options_package:  output dict from Agent 2 node
        capital_decision: output dict from Agent 3 node
        hitl_briefing:    output text from Agent 4 node
    """
    valid_statuses = {"ESCALATED", "AUTO_EXECUTED", "SUSPENDED"}
    if final_status not in valid_statuses:
        raise ValueError(f"final_status must be one of {valid_statuses}, got: {final_status}")
    
    now = str(datetime.now())

    with engine.begin() as conn:
        conn.execute(text("""
            insert into pipeline_log(
                pipeline_id, sku_id, store_id, final_status,
                demand_summary, options_package, capital_decision,
                hitl_briefing, created_at, completed_at)
            VALUES (
                :pipeline_id, :sku_id, :store_id, :final_status,
                :demand_summary, :options_package, :capital_decision,
                :hitl_briefing, :created_at, :completed_at
            )
            ON CONFLICT(pipeline_id) DO UPDATE SET
                final_status     = excluded.final_status,
                demand_summary   = excluded.demand_summary,
                options_package  = excluded.options_package,
                capital_decision = excluded.capital_decision,
                hitl_briefing    = excluded.hitl_briefing,
                completed_at     = excluded.completed_at
        """),
        {
            "pipeline_id":      pipeline_id,
            "sku_id":           sku_id,
            "store_id":         store_id,
            "final_status":     final_status,
            "demand_summary":   json.dumps(demand_summary)   if demand_summary   else None,
            "options_package":  json.dumps(options_package)  if options_package  else None,
            "capital_decision": json.dumps(capital_decision) if capital_decision else None,
            "hitl_briefing":    hitl_briefing,
            "created_at":       now,
            "completed_at":     now,
        })

        print(f"✅  Pipeline run saved: {pipeline_id} | {final_status}")


# ══════════════════════════════════════════════════════════════════════════════
# READ — used by dashboard and HITL approval panel
# ══════════════════════════════════════════════════════════════════════════════

def get_all_runs(limit: int = 50) -> list[dict]:
    """
    Returns recent pipeline runs for the dashboard decision log.
    Most recent first.
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                pipeline_id,
                sku_id,
                store_id,
                final_status,
                created_at,
                completed_at
            FROM   pipeline_log
            ORDER BY completed_at DESC
            LIMIT  :limit
        """), {"limit": limit})
        keys = result.keys()
        return [dict(zip(keys, row)) for row in result.fetchall()]
    

def get_pipeline_run(pipeline_id: str) -> dict | None:
    """
    Returns full detail of one pipeline run including all agent outputs.
    Used by the HITL approval panel to show the full briefing.
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM pipeline_log
            WHERE  pipeline_id = :pipeline_id
        """), {"pipeline_id": pipeline_id})
        row = result.fetchone()
        if row is None:
            return None
        data = dict(zip(result.keys(), row))
    
    # deserialise JSON fields back to dicts
    for field in ["demand_summary", "options_package", "capital_decision"]:
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                data[field] = None
 
    return data

def get_pending_escalations() -> list[dict]:
    """
    Returns all pipeline runs with final_status = ESCALATED.
    These are decisions waiting for human approval in the HITL panel.
    """

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                pipeline_id,
                sku_id,
                store_id,
                hitl_briefing,
                created_at
            FROM   pipeline_log
            WHERE  final_status = 'ESCALATED'
            ORDER BY created_at DESC
        """))
        keys = result.keys()
        return [dict(zip(keys, row)) for row in result.fetchall()]

def get_run_counts_by_status() -> dict:
    """
    Returns count of pipeline runs grouped by final_status.
    Used by dashboard KPI cards.
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                final_status,
                COUNT(*) as count
            FROM   pipeline_log
            GROUP BY final_status
        """))
        return {row[0]: row[1] for row in result.fetchall()}
    
# ══════════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════════
 
if __name__ == "__main__":
    print("\n🔍  Testing db/pipeline_log.py\n")
 
    create_pipeline_table()
 
    # simulate what LangGraph will do in Sprint 2:
    # graph runs through all 4 agent nodes,
    # builds up AgentState internally,
    # then calls save_pipeline_run() ONCE at the end
 
    print("── Simulating LangGraph completing a pipeline run ──────────────")
 
    save_pipeline_run(
        pipeline_id      = "PIPE_SKU00090_20260505",
        sku_id           = "SKU00090",
        store_id         = "STR0077",
        final_status     = "AUTO_EXECUTED",
        demand_summary   = {
            "sku_name":            "Screen Protector v1",
            "critical_stores":     4,
            "at_risk_stores":      1,
            "projected_shortfall": 9,
            "urgency":             "HIGH",
            "lead_time_too_late":  False,
        },
        options_package  = {
            "option_a": {"cost_aed": 3850,  "lead_days": 15.3, "feasible": True},
            "option_b": {"cost_aed": 3850,  "lead_days": 15.3, "feasible": True},
            "option_c": {"cost_aed": 5582,  "lead_days": 5.4,  "feasible": True, "recommended": True},
            "supplier_contact": {"name": "Li Ming", "email": "li@techline.cn"},
        },
        capital_decision = {
            "winner":            "option_c",
            "scores":            {"option_a": 72.4, "option_b": 58.1, "option_c": 81.2},
            "approval_required": False,
            "reason":            "Cost AED 5,582 below auto_approve_limit AED 50,000",
        },
        hitl_briefing    = "AUTO-EXECUTED: Option C approved. Order placed with TechLine Asia (Li Ming). AED 5,582. Delivery in 5.4 days.",
    )
 
    save_pipeline_run(
        pipeline_id      = "PIPE_SKU00001_20260505",
        sku_id           = "SKU00001",
        store_id         = "STR0042",
        final_status     = "ESCALATED",
        demand_summary   = {
            "sku_name":            "Ajwa Dates 1kg v1",
            "critical_stores":     9,
            "at_risk_stores":      11,
            "projected_shortfall": 5143,
            "urgency":             "CRITICAL",
            "lead_time_too_late":  True,
        },
        options_package  = {
            "option_a": {"cost_aed": 72606,  "lead_days": 51.7, "feasible": True},
            "option_b": {"cost_aed": 43566,  "lead_days": 51.7, "feasible": False, "reason": "abc_class A"},
            "option_c": {"cost_aed": 108909, "lead_days": 18.1, "feasible": True, "recommended": True},
            "supplier_contact": {"name": "Wei Zhang", "email": "wei@dragon.cn"},
        },
        capital_decision = {
            "winner":            "option_c",
            "scores":            {"option_a": 60.62, "option_b": 45.26, "option_c": 78.68},
            "approval_required": True,
            "reason":            "Cost AED 108,909 exceeds auto_approve_limit AED 20,000",
        },
        hitl_briefing    = (
            "🚨 URGENT — Ajwa Dates 1kg v1 | CRITICAL\n\n"
            "9 stores critical, 11 at risk. Ramadan 2025 starts in 18 days. "
            "Shortfall: 5,143 units. Standard lead time too late.\n\n"
            "RECOMMENDED: Option C — Expedite AED 108,909 | 18 days\n"
            "Supplier: Wei Zhang | wei@dragon.cn\n\n"
            "ACTION REQUIRED within 48 hours."
        ),
    )
 
    print("\n── get_all_runs() ──────────────────────────────────────────────")
    runs = get_all_runs()
    for r in runs:
        print(f"  {r['pipeline_id']:<30} | {r['final_status']}")
 
    print("\n── get_pending_escalations() ───────────────────────────────────")
    pending = get_pending_escalations()
    print(f"  Pending escalations: {len(pending)}")
    for p in pending:
        print(f"  {p['pipeline_id']} | {p['sku_id']}")
        print(f"\n  HITL Briefing:\n{p['hitl_briefing']}")
 
    print("\n── get_run_counts_by_status() ──────────────────────────────────")
    counts = get_run_counts_by_status()
    for status, count in counts.items():
        print(f"  {status:<20} : {count}")
 
    print("\n── get_pipeline_run() — full detail ────────────────────────────")
    full = get_pipeline_run("PIPE_SKU00090_20260505")
    print(f"  pipeline_id  : {full['pipeline_id']}")
    print(f"  final_status : {full['final_status']}")
    print(f"  urgency      : {full['demand_summary']['urgency']}")
    print(f"  winner       : {full['capital_decision']['winner']}")
    print(f"  supplier     : {full['options_package']['supplier_contact']['name']}")
 
    print("\n✅  pipeline_log.py working correctly.\n")
