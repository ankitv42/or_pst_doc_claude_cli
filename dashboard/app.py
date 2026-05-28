"""
ORCA — dashboard/app.py
========================
Streamlit HITL Command Centre dashboard.

ARCHITECTURE:
    This file is pure UI. Zero business logic. Zero HTTP knowledge.
    All data comes from dashboard/api_client.py.
    All pipeline logic lives in api/main.py → agents/graph.py.

THREE TABS:
    Tab 1 — Command Centre
        Live alert table (102 critical/at-risk SKUs).
        One-click pipeline trigger per alert.
        Auto-refreshes every 30 seconds.

    Tab 2 — Pipeline Monitor
        Real-time pipeline state polling (every 3 seconds).
        Progressive reveal: cards appear as agents complete.
        Status badge updates live.

    Tab 3 — HITL Approval
        Briefing text display for ESCALATED pipelines.
        Approve / Reject buttons.
        Audit log of all decisions in this session.

POLLING PATTERN:
    Streamlit re-runs the entire script on every interaction.
    For live polling: st.rerun() + time.sleep() inside a loop.
    For pipeline monitor: auto-refresh every 3s while RUNNING/ESCALATED.

STATE MANAGEMENT:
    st.session_state stores:
        active_pipeline_id  — pipeline being monitored
        pipeline_history    — list of completed pipeline IDs
        reviewer_name       — cached reviewer name for HITL

DESIGN:
    Dark theme. Amber accents. Monospace data font.
    Industrial command centre aesthetic — serious, not toy.

Usage:
    streamlit run dashboard/app.py
    (API must be running: uvicorn api.main:app --port 8080)
"""

import time
import streamlit as st
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import dashboard.api_client as api

# ==============================================================================
# PAGE CONFIG — must be first Streamlit call
# ==============================================================================

st.set_page_config(
    page_title    = "ORCA Command Centre",
    page_icon     = "🔱",
    layout        = "wide",
    initial_sidebar_state = "collapsed",
)

# ==============================================================================
# CUSTOM CSS — Industrial dark theme, amber accents
# ==============================================================================

st.markdown("""
<style>
    /* ── Import fonts ───────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

    /* ── Root variables ─────────────────────────────── */
    :root {
        --bg-primary:   #0d0e11;
        --bg-surface:   #13151a;
        --bg-card:      #1a1d24;
        --bg-elevated:  #21252e;
        --border:       #2a2f3a;
        --amber:        #f59e0b;
        --amber-dim:    #92400e;
        --amber-glow:   rgba(245,158,11,0.08);
        --green:        #10b981;
        --red:          #ef4444;
        --blue:         #3b82f6;
        --text-primary: #e8eaf0;
        --text-muted:   #6b7280;
        --text-dim:     #374151;
        --mono:         'IBM Plex Mono', monospace;
        --sans:         'IBM Plex Sans', sans-serif;
    }

    /* ── Global reset ───────────────────────────────── */
    .stApp {
        background-color: var(--bg-primary) !important;
        font-family: var(--sans);
        color: var(--text-primary);
    }
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* ── Header bar ─────────────────────────────────── */
    .orca-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.5rem;
        background: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: 6px;
        margin-bottom: 1.5rem;
    }
    .orca-logo {
        font-family: var(--mono);
        font-size: 1.4rem;
        font-weight: 600;
        color: var(--amber);
        letter-spacing: 0.15em;
    }
    .orca-tagline {
        font-size: 0.75rem;
        color: var(--text-muted);
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .orca-status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--green);
        margin-right: 6px;
        box-shadow: 0 0 6px var(--green);
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* ── Stat cards ─────────────────────────────────── */
    .stat-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .stat-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 1rem 1.25rem;
        position: relative;
        overflow: hidden;
    }
    .stat-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: var(--amber);
    }
    .stat-label {
        font-size: 0.65rem;
        color: var(--text-muted);
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.4rem;
    }
    .stat-value {
        font-family: var(--mono);
        font-size: 1.8rem;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1;
    }
    .stat-value.amber { color: var(--amber); }
    .stat-value.red   { color: var(--red); }
    .stat-value.green { color: var(--green); }

    /* ── Status badges ──────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 3px;
        font-family: var(--mono);
        font-size: 0.7rem;
        font-weight: 500;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .badge-critical  { background: rgba(239,68,68,0.15);  color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
    .badge-high      { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
    .badge-medium    { background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }
    .badge-escalated { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
    .badge-running   { background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }
    .badge-executed  { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
    .badge-suspended { background: rgba(107,114,128,0.15);color: #6b7280; border: 1px solid rgba(107,114,128,0.3); }
    .badge-started   { background: rgba(59,130,246,0.1);  color: #60a5fa; border: 1px solid rgba(59,130,246,0.2); }
    .badge-failed    { background: rgba(239,68,68,0.15);  color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }

    /* ── Section headers ────────────────────────────── */
    .section-header {
        font-family: var(--mono);
        font-size: 0.7rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: var(--text-muted);
        border-bottom: 1px solid var(--border);
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }

    /* ── Pipeline cards ─────────────────────────────── */
    .pipeline-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    .pipeline-card.active {
        border-color: var(--amber);
        box-shadow: 0 0 20px var(--amber-glow);
    }
    .pipeline-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.75rem;
    }
    .pipeline-id {
        font-family: var(--mono);
        font-size: 0.8rem;
        color: var(--amber);
    }

    /* ── Agent progress steps ───────────────────────── */
    .agent-steps {
        display: flex;
        gap: 0.5rem;
        margin: 1rem 0;
        align-items: center;
    }
    .agent-step {
        flex: 1;
        padding: 0.5rem;
        border-radius: 4px;
        text-align: center;
        font-family: var(--mono);
        font-size: 0.65rem;
        letter-spacing: 0.05em;
    }
    .agent-step.done    { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
    .agent-step.running { background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }
    .agent-step.pending { background: var(--bg-elevated);    color: var(--text-dim);  border: 1px solid var(--border); }
    .agent-step.paused  { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
    .step-arrow { color: var(--text-dim); font-size: 0.8rem; }

    /* ── Data rows ──────────────────────────────────── */
    .data-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.4rem 0;
        border-bottom: 1px solid var(--bg-elevated);
        font-size: 0.82rem;
    }
    .data-key   { color: var(--text-muted); font-family: var(--mono); font-size: 0.72rem; }
    .data-value { color: var(--text-primary); font-weight: 500; }
    .data-value.amber { color: var(--amber); font-family: var(--mono); }
    .data-value.green { color: var(--green); }
    .data-value.red   { color: var(--red); }

    /* ── HITL briefing box ──────────────────────────── */
    .briefing-box {
        background: var(--bg-elevated);
        border: 1px solid var(--amber-dim);
        border-left: 3px solid var(--amber);
        border-radius: 4px;
        padding: 1.25rem;
        font-family: var(--mono);
        font-size: 0.78rem;
        line-height: 1.7;
        color: var(--text-primary);
        white-space: pre-wrap;
        margin-bottom: 1.25rem;
    }

    /* ── Options table ──────────────────────────────── */
    .options-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.75rem;
        margin: 0.75rem 0;
    }
    .option-card {
        background: var(--bg-elevated);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 0.9rem;
    }
    .option-card.winner {
        border-color: var(--amber);
        background: var(--amber-glow);
    }
    .option-title {
        font-family: var(--mono);
        font-size: 0.72rem;
        color: var(--amber);
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    .option-cost {
        font-family: var(--mono);
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.25rem;
    }
    .option-detail {
        font-size: 0.7rem;
        color: var(--text-muted);
    }
    .option-status {
        margin-top: 0.5rem;
        font-size: 0.68rem;
        font-family: var(--mono);
    }

    /* ── Alert table rows ───────────────────────────── */
    .alert-row {
        display: grid;
        grid-template-columns: 1fr 1.5fr 0.7fr 0.7fr 0.8fr 0.8fr 0.8fr;
        gap: 0.5rem;
        align-items: center;
        padding: 0.6rem 0.75rem;
        border-bottom: 1px solid var(--border);
        font-size: 0.78rem;
        transition: background 0.15s;
    }
    .alert-row:hover { background: var(--bg-elevated); }
    .alert-header {
        font-family: var(--mono);
        font-size: 0.65rem;
        color: var(--text-muted);
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .sku-id   { font-family: var(--mono); color: var(--amber); font-weight: 500; }
    .sku-name { color: var(--text-primary); }

    /* ── Audit log ──────────────────────────────────── */
    .audit-row {
        display: grid;
        grid-template-columns: 1.5fr 1fr 1fr 1fr 1.5fr;
        gap: 0.5rem;
        align-items: center;
        padding: 0.5rem 0.75rem;
        border-bottom: 1px solid var(--border);
        font-size: 0.75rem;
        font-family: var(--mono);
    }
    .audit-header { color: var(--text-muted); font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.08em; }

    /* ── Hide streamlit chrome ──────────────────────── */
    #MainMenu, footer, header { visibility: hidden; }
    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg-surface);
        border-radius: 6px;
        padding: 4px;
        gap: 4px;
        border: 1px solid var(--border);
    }
    .stTabs [data-baseweb="tab"] {
        font-family: var(--mono);
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
        background: transparent;
        border-radius: 4px;
        padding: 0.4rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        background: var(--amber-glow) !important;
        color: var(--amber) !important;
        border-bottom: none !important;
    }
    /* Force button styling — override Streamlit defaults */
    .stButton > button {
        font-family: var(--mono) !important;
        font-size: 0.72rem !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        border-radius: 4px !important;
        background-color: var(--bg-elevated) !important;
        color: var(--amber) !important;
        border: 1px solid var(--amber-dim) !important;
        font-weight: 500 !important;
    }
    .stButton > button:hover {
        background-color: var(--amber-glow) !important;
        border-color: var(--amber) !important;
        color: var(--amber) !important;
    }
    .stButton > button[kind="primary"] {
        background-color: rgba(16,185,129,0.15) !important;
        color: #10b981 !important;
        border-color: rgba(16,185,129,0.5) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: rgba(239,68,68,0.10) !important;
        color: #ef4444 !important;
        border-color: rgba(239,68,68,0.4) !important;
    }
    div[data-testid="stMetricValue"] { font-family: var(--mono); }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# SESSION STATE INIT
# ==============================================================================

if "active_pipeline_id" not in st.session_state:
    st.session_state.active_pipeline_id = None
if "pipeline_history" not in st.session_state:
    st.session_state.pipeline_history = []
if "reviewer_name" not in st.session_state:
    st.session_state.reviewer_name = ""
if "last_alerts_refresh" not in st.session_state:
    st.session_state.last_alerts_refresh = 0
if "alerts_cache" not in st.session_state:
    st.session_state.alerts_cache = []
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0


# ==============================================================================
# HELPERS
# ==============================================================================

def _badge(status: str) -> str:
    """Returns HTML badge for a pipeline/alert status."""
    s = (status or "").upper()
    css = {
        "CRITICAL":                "badge-critical",
        "HIGH":                    "badge-high",
        "MEDIUM":                  "badge-medium",
        "ESCALATED":               "badge-escalated",
        "RUNNING":                 "badge-running",
        "STARTED":                 "badge-started",
        "AUTO_EXECUTED":           "badge-executed",
        "EXECUTED_AFTER_APPROVAL": "badge-executed",
        "SUSPENDED":               "badge-suspended",
        "REJECTED":                "badge-suspended",
        "FAILED":                  "badge-failed",
    }.get(s, "badge-started")
    return f'<span class="badge {css}">{s}</span>'


def _fmt_aed(amount) -> str:
    if amount is None:
        return "—"
    return f"AED {float(amount):,.0f}"


def _fmt_bool(val) -> str:
    if val is True:
        return '<span style="color:#ef4444">YES</span>'
    if val is False:
        return '<span style="color:#10b981">NO</span>'
    return "—"


def _agent_steps(state: dict) -> str:
    """Returns HTML agent progress steps based on what is populated in state."""
    ds  = state.get("demand_summary")
    op  = state.get("options_package")
    cd  = state.get("capital_decision")
    hb  = state.get("hitl_briefing")
    sts = (state.get("status") or "").upper()

    def step(label, done, is_paused=False):
        if is_paused:
            cls = "paused"
        elif done:
            cls = "done"
        else:
            cls = "pending"
        return f'<div class="agent-step {cls}">{label}</div>'

    a1 = step("Agent 1<br/>Demand", ds is not None)
    a2 = step("Agent 2<br/>Options", op is not None)
    a3 = step("Agent 3<br/>Capital", cd is not None)
    a4 = step("Agent 4<br/>HITL", hb is not None, is_paused=(sts == "ESCALATED"))
    ar = '<span class="step-arrow">›</span>'

    return f'<div class="agent-steps">{a1}{ar}{a2}{ar}{a3}{ar}{a4}</div>'


# ==============================================================================
# HEADER
# ==============================================================================

health = api.get_health()
api_ok = health is not None and health.get("status") == "ok"

st.markdown(f"""
<div class="orca-header">
    <div>
        <div class="orca-logo">🔱 ORCA</div>
        <div class="orca-tagline">Open Retail Command Agent — Inventory Intelligence</div>
    </div>
    <div style="text-align:right">
        <div style="font-family:var(--mono);font-size:0.72rem;color:{'#10b981' if api_ok else '#ef4444'}">
            <span class="orca-status-dot" style="background:{'#10b981' if api_ok else '#ef4444'}"></span>
            API {'ONLINE' if api_ok else 'OFFLINE'}
        </div>
        <div style="font-size:0.68rem;color:var(--text-muted);margin-top:2px">
            {health.get('llm','—') if health else 'N/A'} &nbsp;·&nbsp;
            RAG: {health.get('rag','—').split('(')[0].strip() if health else 'N/A'}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# STAT BAR
# ==============================================================================

alerts = api.get_alerts()
pipelines = api.list_pipelines()

critical_count  = sum(1 for a in alerts if (a.get("abc_class") or "") == "A")
escalated_count = sum(1 for p in pipelines if (p.get("status") or "") == "ESCALATED")
executed_count  = sum(1 for p in pipelines if "EXECUTED" in (p.get("status") or ""))
total_alerts    = len(alerts)

st.markdown(f"""
<div class="stat-grid">
    <div class="stat-card">
        <div class="stat-label">Active Alerts</div>
        <div class="stat-value amber">{total_alerts}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Class A SKUs</div>
        <div class="stat-value red">{critical_count}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Awaiting Approval</div>
        <div class="stat-value amber">{escalated_count}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Executed Today</div>
        <div class="stat-value green">{executed_count}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# TABS
# ==============================================================================

tab1, tab2, tab3 = st.tabs([
    "⚡  Command Centre",
    "📡  Pipeline Monitor",
    "✅  HITL Approval",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — COMMAND CENTRE
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    col_left, col_right = st.columns([3, 1])

    with col_left:
        st.markdown('<div class="section-header">Critical & At-Risk Alerts</div>', unsafe_allow_html=True)

    with col_right:
        if st.button("↻  Refresh Alerts", use_container_width=True):
            st.session_state.alerts_cache = api.get_alerts()
            st.rerun()

    if not alerts:
        st.info("No alerts found. Run the scheduler to generate alerts.")
    else:
        # Table header
        # Header row using same column ratios as data rows
        h1, h2, h3, h4, h5, h6 = st.columns([1.2, 2, 1.2, 0.6, 1, 1])
        headers = ["SKU ID", "SKU Name", "Category", "Class", "Status", "Action"]
        for col, label in zip([h1,h2,h3,h4,h5,h6], headers):
            col.markdown(f'<div style="font-family:var(--mono);font-size:0.65rem;color:#6b7280;letter-spacing:0.1em;text-transform:uppercase;padding-bottom:0.4rem;border-bottom:1px solid #2a2f3a">{label}</div>', unsafe_allow_html=True)

        # Show top 25 alerts — pure st.columns for alignment consistency
        for i, alert in enumerate(alerts[:25]):
            sku_id   = alert.get("sku_id", "—")
            sku_name = alert.get("sku_name", "—")
            category = alert.get("category", "—")
            abc      = alert.get("abc_class", "—")
            # stock_status is per-store — show category-level indicator instead
            stock_status = alert.get("stock_status") or "Critical"

            c1, c2, c3, c4, c5, c6 = st.columns([1.2, 2, 1.2, 0.6, 1, 1])
            with c1:
                st.markdown(f'<div style="font-family:var(--mono);color:#f59e0b;font-size:0.78rem;padding:0.4rem 0">{sku_id}</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div style="font-size:0.78rem;padding:0.4rem 0;color:#e8eaf0">{sku_name}</div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div style="font-size:0.78rem;padding:0.4rem 0;color:#6b7280">{category}</div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div style="padding:0.4rem 0">{_badge(abc)}</div>', unsafe_allow_html=True)
            with c5:
                st.markdown(f'<div style="padding:0.3rem 0">{_badge(stock_status)}</div>', unsafe_allow_html=True)
            with c6:
                if st.button("Analyse", key=f"analyse_{i}_{sku_id}", use_container_width=True):
                    store_id = alert.get("store_id") or "STR0001"
                    result = api.run_pipeline(sku_id=sku_id, store_id=store_id)
                    if result and result.get("pipeline_id"):
                        st.session_state.active_pipeline_id = result["pipeline_id"]
                        if result["pipeline_id"] not in st.session_state.pipeline_history:
                            st.session_state.pipeline_history.append(result["pipeline_id"])
                        st.success(f"Pipeline launched: {result['pipeline_id']}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to launch pipeline.")
            st.markdown('<hr style="margin:0;border-color:#2a2f3a;border-width:1px 0 0 0">', unsafe_allow_html=True)

        if len(alerts) > 25:
            st.markdown(
                f'<div style="text-align:center;color:var(--text-muted);font-size:0.75rem;padding:0.75rem">'
                f'Showing 25 of {len(alerts)} alerts</div>',
                unsafe_allow_html=True
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PIPELINE MONITOR
# ══════════════════════════════════════════════════════════════════════════════

with tab2:

    col_id, col_refresh = st.columns([3, 1])

    with col_id:
        pipeline_id_input = st.text_input(
            "Pipeline ID",
            value=st.session_state.active_pipeline_id or "",
            placeholder="PIPE_SKU00090_2026-05-27",
            label_visibility="collapsed",
        )
        if pipeline_id_input:
            st.session_state.active_pipeline_id = pipeline_id_input

    with col_refresh:
        auto_refresh = st.toggle("Auto-refresh (3s)", value=st.session_state.get("auto_refresh", False))
        st.session_state.auto_refresh = auto_refresh

    pid = st.session_state.active_pipeline_id

    if not pid:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:var(--text-muted)">
            <div style="font-size:2rem;margin-bottom:0.5rem">📡</div>
            <div style="font-family:var(--mono);font-size:0.8rem">
                No pipeline selected.<br/>Trigger one from Command Centre or enter a Pipeline ID above.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        state = api.get_pipeline_state(pid)

        if not state:
            st.error(f"Pipeline {pid} not found.")
        else:
            status = state.get("status") or "UNKNOWN"
            ds     = state.get("demand_summary") or {}
            op     = state.get("options_package") or {}
            cd     = state.get("capital_decision") or {}
            hb     = state.get("hitl_briefing")

            # ── Pipeline header
            st.markdown(f"""
            <div class="pipeline-card {'active' if status in ('RUNNING','STARTED','ESCALATED') else ''}">
                <div class="pipeline-card-header">
                    <span class="pipeline-id">{pid}</span>
                    {_badge(status)}
                </div>
                <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.5rem">
                    SKU: <span style="color:var(--amber);font-family:var(--mono)">{state.get('sku_id','—')}</span>
                    &nbsp;·&nbsp;
                    Store: <span style="font-family:var(--mono)">{state.get('store_id','—')}</span>
                    &nbsp;·&nbsp;
                    Route: <span style="font-family:var(--mono)">{state.get('route') or '—'}</span>
                </div>
                {_agent_steps(state)}
            </div>
            """, unsafe_allow_html=True)

            # ── Agent outputs side by side
            if ds or op or cd:
                c1, c2, c3 = st.columns(3)

                # Agent 1
                with c1:
                    st.markdown('<div class="section-header">Agent 1 — Demand</div>', unsafe_allow_html=True)
                    if ds:
                        urgency = ds.get("urgency") or "—"
                        st.markdown(f"""
                        <div class="pipeline-card">
                            <div style="margin-bottom:0.5rem">{_badge(urgency)}</div>
                            <div class="data-row"><span class="data-key">Critical Stores</span>
                                <span class="data-value amber">{ds.get('critical_stores','—')}</span></div>
                            <div class="data-row"><span class="data-key">At Risk</span>
                                <span class="data-value">{ds.get('at_risk_stores','—')}</span></div>
                            <div class="data-row"><span class="data-key">Shortfall</span>
                                <span class="data-value">{ds.get('projected_shortfall','—')} units</span></div>
                            <div class="data-row"><span class="data-key">Lead Time Late</span>
                                <span class="data-value">{_fmt_bool(ds.get('lead_time_too_late'))}</span></div>
                            <div class="data-row"><span class="data-key">Event</span>
                                <span class="data-value" style="font-size:0.7rem">{ds.get('event_name') or '—'}</span></div>
                            <div class="data-row"><span class="data-key">Trend</span>
                                <span class="data-value">{ds.get('demand_trend') or '—'}</span></div>
                            <div class="data-row"><span class="data-key">Confidence</span>
                                <span class="data-value">{ds.get('confidence_score') or '—'}</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="color:var(--text-dim);font-size:0.75rem;padding:1rem">Waiting...</div>', unsafe_allow_html=True)

                # Agent 2
                with c2:
                    st.markdown('<div class="section-header">Agent 2 — Options</div>', unsafe_allow_html=True)
                    if op:
                        options = op.get("options", [])
                        winner  = op.get("recommended", "")
                        st.markdown(f"""
                        <div class="pipeline-card">
                            <div style="margin-bottom:0.75rem;font-size:0.72rem;color:var(--text-muted)">
                                Recommended: <span style="color:var(--amber);font-family:var(--mono)">Option {winner}</span>
                            </div>
                        """, unsafe_allow_html=True)
                        for opt in options:
                            is_winner = str(opt.get("id")) == str(winner)
                            eliminated = opt.get("elimination_reason")
                            st.markdown(f"""
                            <div class="option-card {'winner' if is_winner else ''}">
                                <div class="option-title">Option {opt.get('id')} — {opt.get('name','')}</div>
                                <div class="option-cost">{_fmt_aed(opt.get('total_cost_aed'))}</div>
                                <div class="option-detail">
                                    Lead: {opt.get('lead_time_days','—')}d &nbsp;·&nbsp;
                                    Pool: {opt.get('pool_id','—')} &nbsp;·&nbsp;
                                    Avail: {opt.get('availability_pct','—')}%
                                </div>
                                <div class="option-status">
                                    {'⛔ ELIMINATED' if eliminated else ('✅ RECOMMENDED' if is_winner else '○ feasible')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="color:var(--text-dim);font-size:0.75rem;padding:1rem">Waiting...</div>', unsafe_allow_html=True)

                # Agent 3
                with c3:
                    st.markdown('<div class="section-header">Agent 3 — Capital</div>', unsafe_allow_html=True)
                    if cd:
                        winner = cd.get("recommended", "")
                        st.markdown(f"""
                        <div class="pipeline-card">
                            <div class="data-row"><span class="data-key">Winner</span>
                                <span class="data-value amber">Option {winner}</span></div>
                            <div class="data-row"><span class="data-key">Amount</span>
                                <span class="data-value amber">{_fmt_aed(cd.get('approval_amount_aed'))}</span></div>
                            <div class="data-row"><span class="data-key">Pool</span>
                                <span class="data-value">{cd.get('approval_pool') or '—'}</span></div>
                            <div class="data-row"><span class="data-key">Approval Req.</span>
                                <span class="data-value">{_fmt_bool(cd.get('approval_required'))}</span></div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Scores
                        st.markdown('<div style="margin-top:0.75rem">', unsafe_allow_html=True)
                        for so in cd.get("scored_options", []):
                            score = so.get("total_score", 0) or 0
                            is_w  = str(so.get("id")) == str(winner)
                            bar_w = min(int(score), 100)
                            st.markdown(f"""
                            <div style="margin-bottom:0.4rem">
                                <div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:0.68rem;margin-bottom:2px">
                                    <span style="color:{'#f59e0b' if is_w else 'var(--text-muted)'}">Option {so.get('id')}</span>
                                    <span style="color:var(--text-primary)">{score:.1f}</span>
                                </div>
                                <div style="background:var(--bg-elevated);border-radius:2px;height:4px">
                                    <div style="width:{bar_w}%;height:4px;border-radius:2px;background:{'#f59e0b' if is_w else '#3b82f6'}"></div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.markdown('<div style="color:var(--text-dim);font-size:0.75rem;padding:1rem">Waiting...</div>', unsafe_allow_html=True)

            # ── HITL briefing preview (if available)
            if hb:
                st.markdown('<div class="section-header" style="margin-top:1rem">Agent 4 — HITL Briefing</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="briefing-box">{hb}</div>', unsafe_allow_html=True)

                if status == "ESCALATED":
                    st.info("⏸ Pipeline paused — go to **HITL Approval** tab to approve or reject.", icon="⏸")

            # ── Auto-refresh handled at tab level below


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — HITL APPROVAL
# ══════════════════════════════════════════════════════════════════════════════

with tab3:

    col_form, col_audit = st.columns([2, 1])

    with col_form:
        st.markdown('<div class="section-header">Human-in-the-Loop Approval</div>', unsafe_allow_html=True)

        # reviewer name
        reviewer = st.text_input(
            "Reviewer",
            value=st.session_state.reviewer_name,
            placeholder="your.email@company.ae",
        )
        if reviewer:
            st.session_state.reviewer_name = reviewer

        # pipeline selector
        escalated = [
            p for p in api.list_pipelines()
            if (p.get("status") or "") == "ESCALATED"
        ]

        if not escalated:
            st.markdown("""
            <div style="text-align:center;padding:2rem;color:var(--text-muted)">
                <div style="font-size:1.5rem;margin-bottom:0.5rem">✅</div>
                <div style="font-family:var(--mono);font-size:0.8rem">No pipelines awaiting approval.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            selected_pid = st.selectbox(
                "Select Pipeline",
                options=[p["pipeline_id"] for p in escalated],
                format_func=lambda x: f"{x} — {next((p['sku_id'] for p in escalated if p['pipeline_id']==x), '')}",
            )

            if selected_pid:
                state = api.get_pipeline_state(selected_pid)
                hb    = state.get("hitl_briefing") if state else None
                cd    = state.get("capital_decision") or {}
                ds    = state.get("demand_summary") or {}

                if hb:
                    st.markdown(f'<div class="briefing-box">{hb}</div>', unsafe_allow_html=True)

                    # Key decision info
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Winner", f"Option {cd.get('recommended','—')}")
                    with c2:
                        st.metric("Amount", _fmt_aed(cd.get("approval_amount_aed")))
                    with c3:
                        st.metric("Pool", cd.get("approval_pool") or "—")

                    st.markdown("---")

                    col_approve, col_reject = st.columns(2)

                    with col_approve:
                        if st.button(
                            "✅  APPROVE — Execute Order",
                            type="primary",
                            use_container_width=True,
                            disabled=not reviewer,
                        ):
                            result = api.approve_pipeline(selected_pid, reviewer)
                            if result:
                                st.success(f"Order approved by {reviewer}. reorder_triggered = Yes.")
                                st.balloons()
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Approval failed. Check API logs.")

                    with col_reject:
                        if st.button(
                            "❌  REJECT — Suspend Order",
                            type="secondary",
                            use_container_width=True,
                            disabled=not reviewer,
                        ):
                            result = api.reject_pipeline(selected_pid, reviewer)
                            if result:
                                st.warning(f"Order rejected by {reviewer}. No action taken.")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Rejection failed. Check API logs.")

                    if not reviewer:
                        st.caption("⚠ Enter your name/email above to enable Approve/Reject buttons.")

    with col_audit:
        st.markdown('<div class="section-header">Session Audit Log</div>', unsafe_allow_html=True)

        all_pipelines = api.list_pipelines()

        if not all_pipelines:
            st.markdown('<div style="color:var(--text-muted);font-size:0.75rem">No pipelines in this session.</div>', unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="audit-row audit-header">
                <span>Pipeline</span>
                <span>SKU</span>
                <span>Status</span>
                <span>Started</span>
                <span>Updated</span>
            </div>
            """, unsafe_allow_html=True)

            for p in all_pipelines[:15]:
                pid_short = (p.get("pipeline_id") or "")[-15:]
                started   = (p.get("started_at") or "")[:16].replace("T", " ")
                updated   = (p.get("last_updated") or "")[:16].replace("T", " ")
                st.markdown(f"""
                <div class="audit-row">
                    <span style="color:var(--amber)">...{pid_short}</span>
                    <span>{p.get('sku_id','—')}</span>
                    <span>{_badge(p.get('status',''))}</span>
                    <span style="color:var(--text-muted)">{started[11:]}</span>
                    <span style="color:var(--text-muted)">{updated[11:]}</span>
                </div>
                """, unsafe_allow_html=True)

# ==============================================================================
# AUTO-REFRESH — at script level, outside all tabs
# Fires every 3 seconds when toggle is on and pipeline is active
# Must be at the END of the script so all UI renders first
# ==============================================================================

# Auto-refresh reads from session_state — accessible at script level
_auto_refresh = st.session_state.get("auto_refresh", False)
_pid_check    = st.session_state.get("active_pipeline_id")
if _auto_refresh and _pid_check:
    _live        = api.get_pipeline_state(_pid_check)
    _live_status = (_live or {}).get("status", "")
    if _live_status in ("STARTED", "RUNNING"):
        time.sleep(3)
        st.rerun()