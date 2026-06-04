"""
ORCA — agents/graph.py
=======================
LangGraph 4-agent pipeline with MCP tool discovery.
 
ARCHITECTURE — Fortune 100 pattern:
    AgentState  — lean, only inter-agent outputs (mirrors Palantir pipeline object)
    Tools       — discovered dynamically via MCP server at runtime
    Prompts     — translated from Palantir system prompts (agents/prompts.py)
    LLM         — switchable via .env (agents/llm_factory.py)
 
HOW MCP WORKS HERE:
    Each node calls _get_mcp_tools() which:
        1. Connects to mcp_server/server.py via stdio subprocess
        2. Asks "what tools do you have?" — dynamic discovery
        3. Returns LangChain-compatible tool objects
        4. Node calls tool by name
 
    Adding a new tool to server.py = all agents can use it immediately.
    graph.py needs ZERO changes to add new tools.
 
AgentState — lean (mirrors Palantir RCC Agent Pipeline object exactly):
    identity       : sku_id, store_id, pipeline_id
    Agent 1 output : demand_summary
    Agent 2 output : options_package
    Agent 3 output : capital_decision
    Agent 4 output : hitl_briefing, action_taken
    graph control  : route, final_status
 
Flow:
    START
      -> agent1_node   (MCP tools + LLM -> demand_summary)
      -> agent2_node   (MCP tools + LLM -> options_package)
      -> agent3_node   (MCP tools + LLM -> capital_decision)
      -> route_node    (MCP pool check + pure Python -> route)
      -> [suspend_node | execute_node | hitl_node]
      -> save_node
      -> END
 
HITL:
    interrupt_before=["execute_node"]
    Graph pauses before any writeback.
    Human approves via API -> resume_pipeline() -> graph continues.
 
Checkpointer:
    MemorySaver for dev.
    Swap to SqliteSaver or PostgresSaver for production.
 
Usage:
    from agents.graph import run_pipeline, resume_pipeline
    state = run_pipeline(sku_id="SKU00090", store_id="STR0077")
 
Flow:
    START
      -> agent1_node   (demand analysis)
      -> agent2_node   (build 3 options)
      -> agent3_node   (score + select winner)
      -> route_node    (pure Python routing decision)
      -> [suspend_node OR execute_node OR hitl_node]
      -> END
 
HITL:
    interrupt_before=["execute_node"] pauses the graph
    before any writeback happens. Human must approve via
    the API endpoint POST /api/v1/agent/approve
    Graph resumes from the checkpoint after approval.
 
Palantir -> ORCA translation:
    pipeline_status transitions  -> LangGraph edges
    application state variables  -> AgentState TypedDict fields
    Automate chain               -> graph edges + conditional routing
    Edit RCC Inventory Position  -> execute_node (HITL protected)
    Pipeline Write * actions     -> each node returns state updates

The HITL mechanism — how it actually works:
pythonapp = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["execute_node"],
)
This one line tells LangGraph — pause the graph BEFORE execute_node runs. Every time. No exceptions.

For AUTO_EXECUTE — the API will call resume_pipeline(pipeline_id, approved=True) immediately after the pause. 
Human never sees it.

For ESCALATE — hitl_node runs first and generates the briefing. THEN the graph pauses. The human reads the briefing 
on the dashboard, clicks Approve or Reject. Dashboard calls the API. API calls resume_pipeline(). Graph resumes 
from checkpoint.
 
Usage:
    from agents.graph import run_pipeline, resume_pipeline
    state = run_pipeline(sku_id="SKU00090", store_id="STR0077")
"""
import sys
sys.path.append(r"C:/lit")
import json
import asyncio
import logging
from pathlib import Path
from datetime import date
from typing import TypedDict, Optional
import os

sys.path.append(str(Path(__file__).parent.parent))
 
from dotenv import load_dotenv
load_dotenv()
 
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient

from agents.llm_factory import get_llm, get_provider_name, get_model_name
from agents.prompts import PROMPTS
from db.queries import (
    get_critical_alerts,
    get_tier1_stores_for_sku,
    writeback_reorder_for_all_positions,
)
from db.pipeline_log import save_pipeline_run, create_pipeline_table
from docs.rag.retriever import get_retriever
from agents.crew import run_forecast_crew

logger = logging.getLogger("orca.graph")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)

# initialise RAG retriever once at module load — BGE model loads here
# subsequent calls to get_retriever() return the cached instance

logger.info("Initialising RAG retriever — BGE model loading...")
try:
    _retriever = get_retriever()
    logger.info(f"RAG retriever ready | available={_retriever.is_available()}")
except Exception as e:
    logger.warning(f"RAG retriever unavailable ({e}) — agents will use LLM knowledge only")
    _retriever = None


# absolute path to MCP server — needed for subprocess launch
MCP_SERVER_PATH = str(
    Path(__file__).parent.parent / "mcp_server" / "server.py"
)

# ==============================================================================
# MCP CLIENT CONFIGURATION
# ==============================================================================

MCP_CLIENT_CONFIG = {
    "orca_inventory": {
                        "transport": "stdio",
                        "command": "python",
                        "args": [MCP_SERVER_PATH]
                      }
                    }

async def _get_mcp_tools() -> list:
    """
    Connects to ORCA MCP server and returns LangChain-compatible tool objects.

    _get_mcp_tools() is async because it launches a subprocess (server.py), opens a stdio pipe, sends a discovery request over that pipe, 
    and waits for a response. That is network-like I/O — it must be async.
 
    Each call creates a fresh connection — stateless, safe for concurrent use.
    The MCP server (server.py) is launched as a subprocess automatically.
 
    Returns list of tool objects. Each tool can be called like:
        tool = next(t for t in tools if t.name == "check_inventory_positions")
        result = await tool.ainvoke({"sku_id": "SKU00090"})
  
    """
    client = MultiServerMCPClient(MCP_CLIENT_CONFIG)
    tools = await client.get_tools()
    return tools


# FIX 2 — _call_mcp_tool is now async and uses ainvoke (not invoke)
# ROOT CAUSE OF ERROR: MCP tools from langchain-mcp-adapters are ASYNC tools.
# They only support .ainvoke() — NOT .invoke().
# Calling .invoke() throws: NotImplementedError: StructuredTool does not support sync invocation
async def _call_mcp_tool(tools: list, tool_name: str, args: dict):
    """
    Finds a named tool and invokes it ASYNCHRONOUSLY.

    IMPORTANT FIX: MCP tools from langchain-mcp-adapters are ASYNC tools.
    They only support .ainvoke() — NOT .invoke().
    Calling .invoke() on them raises:
        NotImplementedError: StructuredTool does not support sync invocation

    Note: invoke() method is used with LangChain @tool decorated functions(@tool decorated), but 
    MCP tools need ainvoke() even though langchain-mcp-adapters converts them to LangChain tool objects.
    The conversion makes them LangChain-compatible but they remain async internally.
    """
    tool = next((t for t in tools if t.name == tool_name), None)
    if tool is None:
        raise ValueError(
            f"Tool '{tool_name}' not found. "
            f"Available: {[t.name for t in tools]}"
        )
    
    result = await tool.ainvoke(args)

    # MCP returns list of content blocks: [{"type": "text", "text": "{...json...}"}]
    # extract the text from the first block and parse it
    if isinstance(result, list) and result and isinstance(result[0], dict):
        text = result[0].get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"result": text}

    # fallback: if result is already a string
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"result": result}

    # fallback: already a dict
    return result

# FIX 1 — _run_async uses asyncio.run() first (fixes DeprecationWarning on Python 3.10+)
def _run_async(coro): 
    """
    Runs an async coroutine synchronously.
    Actually LangGraph nodes are sync : def agent1_node(state: AgentState) -> dict
    But _get_mcp_tools() is async, as a subprocess will trigger server.py , there is I/O so async.

    Now the sync function can not call async function:
        def agent1_node(state):
            tools = await _get_mcp_tools()   # WRONG — can't use await in a sync function
            tools = _get_mcp_tools()         # WRONG — this just creates a coroutine, doesn't run it.
            
    _run_async is the bridge. It lets a sync function run an async function and get the result:
        def agent1_node(state):
            tools = _run_async(_agent1_fetch(sku_id))   # CORRECT — bridge handles it

    FIX: use asyncio.run() first (Python 3.10+ deprecated asyncio.get_event_loop() when no loop exists)
    asyncio.run() creates a fresh event loop, runs coroutine, closes loop. Clean.
    Falls back to nest_asyncio only if already inside a running loop (FastAPI, Jupyter).
    """
    try:
        return asyncio.run(coro)  # FIX: asyncio.run() first, not get_event_loop()
    except RuntimeError:
        # already inside a running event loop (FastAPI, Jupyter) — use nest_asyncio
        import nest_asyncio          
        nest_asyncio.apply()         # patches event loop to allow nested execution
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)


# ==============================================================================
# FIX 3 — ASYNC HELPER FUNCTIONS (one per node)
# Because _call_mcp_tool is now async, everything calling it must also be async.
# Each node gets one async helper that groups ALL its MCP calls together.
# The sync node calls _run_async(helper()) ONCE — clean bridge.
#
# WHY THIS PATTERN:
#   OLD (broken): tools = _run_async(_get_mcp_tools())       # gets tools
#                 result = _call_mcp_tool(tools, ...)         # FAILS — _call_mcp_tool is now async
#
#   NEW (correct): async def _agent1_fetch(sku_id):           # all async calls inside one async fn
#                      tools  = await _get_mcp_tools()
#                      result = await _call_mcp_tool(tools, ...)
#                      return result
#                  data = _run_async(_agent1_fetch(sku_id))   # ONE bridge call
# ==============================================================================

async def _agent1_fetch(sku_id: str) -> tuple:
    """Async helper — fetches all data Agent 1 needs in one async context."""
    tools            = await _get_mcp_tools()
    positions_result = await _call_mcp_tool(tools, "check_inventory_positions", {"sku_id": sku_id})
    sku_result       = await _call_mcp_tool(tools, "get_sku_info",              {"sku_id": sku_id})
    velocity_result  = await _call_mcp_tool(tools, "get_demand_velocity",       {"sku_id": sku_id})
    category         = sku_result.get("category", "")
    events_result    = await _call_mcp_tool(tools, "check_active_events",       {"category": category})
    return tools, positions_result, sku_result, velocity_result, events_result

async def _agent2_fetch(sku_id: str) -> tuple:
    """Async helper — fetches all data Agent 2 needs in one async context."""
    tools         = await _get_mcp_tools()
    sku_data      = await _call_mcp_tool(tools, "get_sku_info",      {"sku_id": sku_id})
    supplier_data = await _call_mcp_tool(tools, "get_supplier_info", {"sku_id": sku_id})
    return sku_data, supplier_data

async def _agent3_fetch(sku_id: str) -> tuple:
    """Async helper — fetches CP001, CP003, SKU margin data in one async context."""
    tools      = await _get_mcp_tools()
    cp001_data = await _call_mcp_tool(tools, "check_capital_budgets", {"pool_id": "CP001"})
    cp003_data = await _call_mcp_tool(tools, "check_capital_budgets", {"pool_id": "CP003"})
    sku_data   = await _call_mcp_tool(tools, "get_sku_info",          {"sku_id":  sku_id})
    return cp001_data, cp003_data, sku_data

async def _route_fetch(approval_pool: str) -> dict:
    """Async helper — fetches recommended pool data for pressure check."""
    tools     = await _get_mcp_tools()
    pool_data = await _call_mcp_tool(tools, "check_capital_budgets", {"pool_id": approval_pool})
    return pool_data

async def _hitl_fetch(sku_id: str) -> dict:
    """Async helper — fetches supplier contact for HITL briefing."""
    tools         = await _get_mcp_tools()
    supplier_data = await _call_mcp_tool(tools, "get_supplier_info", {"sku_id": sku_id})
    return supplier_data

async def _execute_fetch(sku_id: str) -> dict:
    """Async helper — fetches supplier contact for execute confirmation message."""
    tools         = await _get_mcp_tools()
    supplier_data = await _call_mcp_tool(tools, "get_supplier_info", {"sku_id": sku_id})
    return supplier_data

async def _suspend_fetch(approval_pool: str) -> dict:
    """Async helper — fetches pool info for suspension message."""
    tools     = await _get_mcp_tools()
    pool_data = await _call_mcp_tool(tools, "check_capital_budgets", {"pool_id": approval_pool})
    return pool_data


# ==============================================================================
# AGENT STATE
# Lean — only inter-agent outputs.
# Mirrors Palantir RCC Agent Pipeline object exactly.
# Intermediate data (positions, sku_data etc) fetched fresh by each node.
# ==============================================================================


class AgentState(TypedDict):
    # ── identity ──────────────────────────────────────────────────────────
    sku_id:           str
    store_id:         str
    pipeline_id:      str
 
    # ── Agent 1 output → read by Agents 2, 3, 4 ──────────────────────────
    demand_summary:   Optional[dict]
 
    # ── Agent 2 output → read by Agents 3, 4 ─────────────────────────────
    options_package:  Optional[dict]
 
    # ── Agent 3 output → read by Agent 4 ─────────────────────────────────
    capital_decision: Optional[dict]
 
    # ── Agent 4 output → read by save_node ───────────────────────────────
    hitl_briefing:    Optional[str]
    action_taken:     Optional[str]
 
    # ── graph control ─────────────────────────────────────────────────────
    route:            Optional[str]   # ESCALATE | AUTO_EXECUTE | SUSPEND
    final_status:     Optional[str]   # ESCALATED | AUTO_EXECUTED | SUSPENDED



# ==============================================================================
# HELPER — safe JSON parse
# ==============================================================================

def _parse_json(text: str, agent_name: str) -> dict:
    """
    Safely parses LLM JSON output.
    Strips markdown code fences if the LLM wraps output in ```json blocks.
    On failure — retries by asking LLM to fix the JSON.
    """
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        ).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        logger.warning(f"{agent_name} JSON parse failed: {e} — attempting LLM self-fix")
        # ask LLM to fix its own output
        fix_prompt = (
            f"The following JSON is invalid because it contains formulas instead of numbers.\n"
            f"Fix it by computing all formulas and replacing with actual numbers.\n"
            f"Return ONLY valid JSON, no explanation.\n\n"
            f"{clean}"
        )
        try:
            llm      = get_llm()
            response = llm.invoke([{"role": "user", "content": fix_prompt}])
            fixed    = response.content.strip()
            if fixed.startswith("```"):
                lines = fixed.split("\n")
                fixed = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                ).strip()
            result = json.loads(fixed)
            logger.info(f"{agent_name} JSON self-fix succeeded")
            return result
        except Exception as e2:
            logger.error(f"{agent_name} JSON parse failed: {e}")
            logger.error(f"Raw output:\n{text[:500]}")
            raise ValueError(f"{agent_name} returned invalid JSON: {e}")
    

# ==============================================================================
# NODE 1 — AGENT 1: DEMAND INTELLIGENCE
# ==============================================================================    

def agent1_node(state: AgentState) -> dict:
    """
    Demand Intelligence node.
 
    Discovers tools from MCP server dynamically.
    Fetches: inventory positions, SKU context, velocity, active events.
    Calls LLM to reason and produce demand_summary JSON.
    Writes: demand_summary to AgentState.
 
    Palantir equivalent:
        Application state pre-injected: affected_positions, sku_context,
        active_event by AIP Automate.
        Here we fetch them ourselves via MCP — same data, open-source mechanism.
    """

    sku_id = state['sku_id']
    logger.info(f"Agent 1 starting | sku_id={sku_id}")

    # FIX 3 applied: one _run_async call with async helper
    # _agent1_fetch groups all MCP calls in one async context
    tools, positions_result, sku_result, velocity_result, events_result = (
        _run_async(_agent1_fetch(sku_id))
    )

    logger.info(f"Agent 1 discovered {len(tools)} MCP tools: "
                f"{[t.name for t in tools]}")
    
    logger.info(
        f"Agent 1 data fetched | "
        f"critical={positions_result.get('critical_count')} "
        f"at_risk={positions_result.get('at_risk_count')} "
        f"events={events_result.get('events_found')}"
    )

    # format prompt and call LLM
    llm      = get_llm()

    # RAG — fetch policy context for Agent 1
    # query_for_agent1 fires 3 targeted queries:
    #   Q1 — ordering rules for this abc_class and urgency
    #   Q2 — event planning rules for this category and event
    #   Q3 — entity chain: category → supplier → pool
    
    demand_summary_so_far = {}  # not yet available — Agent 1 produces it

    event_list  = events_result.get("events", [])
    event_name  = event_list[0].get("event_name") if event_list else None
    retriever   = _retriever
    if retriever and retriever.is_available():
        policy_context = retriever.query_for_agent1(...)
    else:
        policy_context = "Knowledge base unavailable — using LLM knowledge."
    policy_context = retriever.query_for_agent1(
        category           = sku_result.get("category", ""),
        abc_class          = sku_result.get("abc_class", "B"),
        urgency            = "HIGH",   # conservative default before LLM decides
        lead_time_too_late = sku_result.get("effective_lead_time", 0) > 20,
        event_name         = event_name,
    )
    logger.info(f"Agent 1 RAG context fetched | {len(policy_context)} chars")

    '''
    messages = PROMPTS["agent1"].format_messages(
        pipeline_id        = state["pipeline_id"],
        sku_id             = sku_id,
        affected_positions = json.dumps(positions_result.get("positions", []), indent=2),
        sku_context        = json.dumps(sku_result, indent=2),
        velocity           = json.dumps(velocity_result, indent=2),
        active_events      = json.dumps(events_result.get("events", []), indent=2),
        policy_context     = policy_context,
    )
    logger.info(
        f"Agent 1 calling LLM "
        f"({get_provider_name()}/{get_model_name()})..."
    )
    response = llm.invoke(messages)

    demand_summary = _parse_json(response.content, "Agent 1")
    '''

    # CREWAI FORECASTING CREW
    # Replaces single LLM call with 3-agent collaborative crew.
    # Data Analyst + Market Analyst → Forecast Strategist.
    # Falls back to single LLM if crew fails.
    logger.info("Agent 1 launching CrewAI forecasting crew...")
    try:
        demand_summary = run_forecast_crew(
            sku_id           = sku_id,
            positions_result = positions_result,
            sku_result       = sku_result,
            velocity_result  = velocity_result,
            events_result    = events_result,
        )
        logger.info(
            f"CrewAI forecast complete | "
            f"urgency={demand_summary.get('urgency')} | "
            f"confidence={demand_summary.get('confidence_score')} | "
            f"trend={demand_summary.get('demand_trend')}"
        )
    except Exception as e:
        # graceful fallback to single LLM if crew fails
        logger.warning(f"CrewAI failed ({e}) — falling back to single LLM call")
        messages = PROMPTS["agent1"].format_messages(
            pipeline_id        = state["pipeline_id"],
            sku_id             = sku_id,
            affected_positions = json.dumps(positions_result.get("positions", []), indent=2),
            sku_context        = json.dumps(sku_result, indent=2),
            velocity           = json.dumps(velocity_result, indent=2),
            active_events      = json.dumps(events_result.get("events", []), indent=2),
            policy_context     = policy_context,
        )
        response = llm.with_config({
            "run_name": f"Agent1-Demand-Fallback | {sku_id}",
            "tags":     ["agent1", "demand-intelligence", "crew-fallback"],
            "metadata": {"agent": "demand_intelligence", "sku_id": sku_id, "crew_fallback": True},
        }).invoke(messages)
        demand_summary = _parse_json(response.content, "Agent 1")





    logger.info(
        f"Agent 1 complete | "
        f"urgency={demand_summary.get('urgency')} | "
        f"shortfall={demand_summary.get('projected_shortfall')} | "
        f"lead_time_too_late={demand_summary.get('lead_time_too_late')}"
    )
 
    # write ONLY output to state
    return {"demand_summary": demand_summary}
    '''
    Agent 1 node returns Just a plain Python dict. One key. It does not call any update function. It just returns a dict.
    LangGraph intercepts that return value.LangGraph automatically merges it into the current 'AgentState'. 
    You never see this happening — it is invisible.

    So your question "where does state get updated?" — the answer is between nodes, automatically, by 
    LangGraph itself.

    You might have seen above class AgentState(TypedDict):
    LangGraph does not care about the name at all.
    So how does LangGraph know what the state is?
    You tell it explicitly when you create the graph: 
                builder = StateGraph(AgentState)   # ← HERE
    
    You pass the class INTO StateGraph(). That is how LangGraph knows. Not by the name — by the class 
    being passed in. If you renamed it: BananaState
                builder = StateGraph(BananaState)   # LangGraph uses BananaState as state
    '''


# ==============================================================================
# NODE 2 — AGENT 2: SUPPLY REPLENISHMENT
# ==============================================================================

def agent2_node(state: AgentState) -> dict:
    """
    Supply Replenishment node.
 
    Reads: demand_summary from state (Agent 1 output).
    Discovers tools from MCP server dynamically.
    Fetches: sku_data, supplier_data via MCP.
             tier1_stores via direct DB query (internal — not an MCP tool).
    Calls LLM to build 3 options (A=standard, B=profit max, C=expedite).
    Writes: options_package to AgentState.
 
    Palantir equivalent:
        Application state: demand_summary, sku_data, supplier_data
        pre-injected by AIP Automate.
    """

    sku_id = state["sku_id"]
    logger.info(f"Agent 2 starting | sku_id={sku_id}")

    # FIX 3 applied: one _run_async call with async helper
    sku_data, supplier_data = _run_async(_agent2_fetch(sku_id))

    # tier1_stores — internal query, not exposed via MCP
    # (writeback and internal orchestration queries stay in Python)
    tier1_stores = get_tier1_stores_for_sku(sku_id)

    logger.info(
        f"Agent 2 data fetched | "
        f"allows_expedite={supplier_data.get('allows_expedite')} | "
        f"tier1_stores={len(tier1_stores)}"
    )

    # format prompt with state output from Agent 1 + fresh MCP data 
    llm = get_llm()

    # RAG — fetch policy context for Agent 2
    # query_for_agent2 fires 2 targeted queries:
    #   Q1 — supplier SLA terms + expedite rules for this category/supplier
    #   Q2 — option building rules for this abc_class and urgency

    demand_summary = state.get("demand_summary", {})
    retriever   = _retriever
    if retriever and retriever.is_available():
        policy_context = retriever.query_for_agent1(...)
    else:
        policy_context = "Knowledge base unavailable — using LLM knowledge."
    policy_context = retriever.query_for_agent2(
        category           = sku_data.get("category", ""),
        supplier_name      = supplier_data.get("supplier_name", ""),
        lead_time_too_late = demand_summary.get("lead_time_too_late", False),
        abc_class          = sku_data.get("abc_class", "B"),
        urgency            = demand_summary.get("urgency", "HIGH"),
    )
    logger.info(f"Agent 2 RAG context fetched | {len(policy_context)} chars")



    messages = PROMPTS["agent2"].format_messages(
        pipeline_id    = state["pipeline_id"],
        sku_id         = sku_id,
        demand_summary = json.dumps(state["demand_summary"], indent=2),
        sku_data       = json.dumps(sku_data, indent=2),
        supplier_data  = json.dumps(supplier_data, indent=2),
        tier1_stores   = json.dumps(tier1_stores, indent=2),
        policy_context = policy_context,
    )

    _urgency   = state.get("demand_summary", {}).get("urgency", "HIGH")
    _abc_class = sku_data.get("abc_class", "B")
    logger.info(
        f"Agent 2 calling LLM "
        f"({get_provider_name()}/{get_model_name()})..."
    )

    response = llm.with_config({
        "run_name": f"Agent2-Supply | {sku_id} | {_urgency}",
        "tags":     ["agent2", "supply-replenishment", f"urgency:{_urgency}", f"class:{_abc_class}"],
        "metadata": {
            "agent":     "supply_replenishment",
            "sku_id":    sku_id,
            "urgency":   _urgency,
            "abc_class": _abc_class,
        },
    }).invoke(messages)
    options_package = _parse_json(response.content, "Agent 2")
 
    logger.info(
        f"Agent 2 complete | "
        f"recommended=Option {options_package.get('recommended')}"
    )
 
    return {"options_package": options_package}


# ==============================================================================
# NODE 3 — AGENT 3: CAPITAL ALLOCATION
# ==============================================================================

def agent3_node(state: AgentState) -> dict:
    """
    Capital Allocation node.
 
    Reads: demand_summary, options_package from state.
    Discovers tools from MCP server dynamically.
    Fetches: CP001 and CP003 separately (mirrors Palantir cp001_data/cp003_data),
             SKU margin data via MCP.
    Calls LLM to score options using exact RCC formula.
    Writes: capital_decision to AgentState.
 
    SCORING FORMULA (from RCC bootcamp doc — locked in memory as PRIORITY):
        budget_score       = (1 - cost/available_budget) x 40
        availability_score = availability_pct x 0.40
        margin_score       = (1/margin_priority_rank) x 20
        lead_time_penalty  = -20 if CRITICAL AND lead_time > 30
        approval_required  = cost > pool.auto_approve_limit_aed
 
    Palantir equivalent:
        Application state: options_package, cp001_data, cp003_data
        pre-injected by AIP Automate as separate variables.
    """
    sku_id = state["sku_id"]
    logger.info(f"Agent 3 starting | sku_id={sku_id}")

    # FIX 3 applied: one _run_async call with async helper
    # CP001 and CP003 fetched separately — mirrors Palantir pattern exactly
    cp001_data, cp003_data, sku_data = _run_async(_agent3_fetch(sku_id))

    logger.info(
        f"Agent 3 data fetched | "
        f"CP001={cp001_data.get('pool_pressure_flag')} "
        f"avail=AED {cp001_data.get('available_aed', 0):,.0f} | "
        f"CP003={cp003_data.get('pool_pressure_flag')} "
        f"avail=AED {cp003_data.get('available_aed', 0):,.0f}"
    )

    # format prompt and call LLM
    llm      = get_llm()

    # RAG — fetch policy context for Agent 3
    # query_for_agent3 fires 3 targeted queries:
    #   Q1 — pool rules and approval thresholds for this pool
    #   Q2 — scoring formula and elimination rules
    #   Q3 — scoring formula TABLE specifically (element_type=table)

    demand_summary   = state.get("demand_summary", {})
    options_package  = state.get("options_package", {})
    approval_pool    = options_package.get("options", [{}])[0].get("pool_id", "CP001")
    retriever   = _retriever
    if retriever and retriever.is_available():
        policy_context = retriever.query_for_agent1(...)
    else:
        policy_context = "Knowledge base unavailable — using LLM knowledge."
    policy_context   = retriever.query_for_agent3(
        category       = sku_data.get("category", ""),
        urgency        = demand_summary.get("urgency", "HIGH"),
        abc_class      = sku_data.get("abc_class", "B"),
        approval_pool  = approval_pool,
    )
    logger.info(f"Agent 3 RAG context fetched | {len(policy_context)} chars")




    messages = PROMPTS["agent3"].format_messages(
        pipeline_id     = state["pipeline_id"],
        sku_id          = sku_id,
        demand_summary  = json.dumps(state["demand_summary"],  indent=2),
        options_package = json.dumps(state["options_package"], indent=2),
        sku_data        = json.dumps(sku_data, indent=2),
        cp001_data      = json.dumps(cp001_data, indent=2),
        cp003_data      = json.dumps(cp003_data, indent=2),
        policy_context  = policy_context,
    )
 
    _urgency3   = demand_summary.get("urgency", "HIGH")
    _abc_class3 = sku_data.get("abc_class", "B")
    logger.info(
        f"Agent 3 calling LLM "
        f"({get_provider_name()}/{get_model_name()})..."
    )
    response = llm.with_config({
        "run_name": f"Agent3-Capital | {sku_id} | pool:{approval_pool}",
        "tags":     ["agent3", "capital-allocation", f"urgency:{_urgency3}", f"class:{_abc_class3}", f"pool:{approval_pool}"],
        "metadata": {
            "agent":         "capital_allocation",
            "sku_id":        sku_id,
            "urgency":       _urgency3,
            "abc_class":     _abc_class3,
            "approval_pool": approval_pool,
        },
    }).invoke(messages)
    capital_decision = _parse_json(response.content, "Agent 3")
 
    logger.info(
        f"Agent 3 complete | "
        f"winner=Option {capital_decision.get('recommended')} | "
        f"approval_required={capital_decision.get('approval_required')} | "
        f"amount=AED {capital_decision.get('approval_amount_aed', 0):,.0f}"
    )
 
    return {"capital_decision": capital_decision}


# ==============================================================================
# NODE 4 — ROUTE: Pure Python. No LLM. Sets route.
# ==============================================================================

def route_node(state: AgentState) -> dict:
    """
    Pure Python routing decision — no LLM call.
 
    Reads capital_decision from state.
    Fetches recommended pool via MCP to check pressure flag.
    Sets route in state for conditional edge.
 
    ROUTE 1 — SUSPEND:      pool_pressure_flag = HIGH
    ROUTE 2 — AUTO_EXECUTE: approval_required = false AND pool not HIGH
    ROUTE 3 — ESCALATE:     approval_required = true
        Both route 2 and 3 will approach execute_node to mark the reordered_trigger == Yes
 
    Palantir equivalent:
        Agent 4's routing logic was embedded in its system prompt.
        Here routing is pure Python — more reliable, never hallucinates.
    """

    capital_decision  = state.get("capital_decision", {})
    approval_required = capital_decision.get("approval_required", True)
    approval_pool     = capital_decision.get("approval_pool", "CP001")
 
    # FIX 3 applied: one _run_async call with async helper
    pool_data     = _run_async(_route_fetch(approval_pool))
    pool_pressure = pool_data.get("pool_pressure_flag", "LOW")
 
    if pool_pressure == "HIGH":
        route = "SUSPEND"
    elif not approval_required:
        route = "AUTO_EXECUTE"
    else:
        route = "ESCALATE"
 
    logger.info(
        f"Route node | "
        f"pool={approval_pool} pressure={pool_pressure} "
        f"approval_required={approval_required} -> {route}"
    )
 
    return {"route": route}

# ==============================================================================
# CONDITIONAL EDGE — tells LangGraph which node runs next
# ==============================================================================

def decide_route(state: AgentState) -> str:
    """Reads state.route and returns next node name."""
    route = state.get("route", "ESCALATE")

    if route == "SUSPEND":
        return "suspend_node"
    elif route == "AUTO_EXECUTE":
        return "execute_node"
    else:
        return "hitl_node"
    

# ==============================================================================
# NODE 5a — HITL NODE: Generate briefing (ESCALATE route)
# ==============================================================================

def hitl_node(state: AgentState) -> dict:
    """
    Generates full HITL briefing text for the human planner.
 
    Fetches supplier contact via MCP — never hardcoded.

    HITL = Human In The Loop.
    This node's only job is to write a message — like an email — that a human will read. The message says 
    "here is the situation, here are the 3 options, please approve one."
    That message is called the hitl_briefing.

    After this node, graph hits interrupt_before["execute_node"].

    This means — after hitl_node finishes writing the briefing, LangGraph tries to move to the next node. 
    The next node would be execute_node. But before it runs execute_node, LangGraph STOPS. It saves the 
    current state to memory and waits for human to Approve/Reject.

    While the graph is paused, the human planner opens the dashboard. They see the briefing that hitl_node 
    just wrote. They read it. They click Approve or Reject.

    When the human clicks Approve, the dashboard calls our API endpoint. The API calls 
    resume_pipeline(pipeline_id, approved=True). LangGraph picks up from exactly where it 
    stopped — the checkpoint — and runs execute_node which writes reorder_triggered = Yes to the database.

    If they click Reject, resume_pipeline(pipeline_id, approved=False) is called and the graph routes to 
    suspend_node instead.

    Palantir equivalent:
        Agent 4 Route 3 — ESCALATE.
        Generates hitl_briefing, sets pipeline_status = ESCALATED.
    """
    sku_id = state["sku_id"]
    logger.info(f"HITL node starting | sku_id={sku_id}")

    # FIX 3 applied: one _run_async call with async helper
    supplier_data = _run_async(_hitl_fetch(sku_id))

    # call LLM to generate briefing text
    llm = get_llm()

    # RAG — fetch policy context for Agent 4
    # query_for_agent4 fires 1 targeted query:
    #   Q1 — HITL briefing format + contact resolution rule
    capital_decision = state.get("capital_decision", {})

    # Pre-extract winner in Python — prevents LLM from re-deciding based on its own heuristic
    winner_id       = capital_decision.get("recommended", "A")
    winner_cost_aed = capital_decision.get("approval_amount_aed", 0)
    winner_pool     = capital_decision.get("approval_pool", "CP001")
    scored_options  = capital_decision.get("scored_options", [])
    winner_option   = next((o for o in scored_options if o.get("id") == winner_id), {})
    winner_score    = winner_option.get("total_score", "N/A")

    winner_summary = (
        f"WINNER — pre-extracted by system (DO NOT CHANGE):\n"
        f"  Option {winner_id} | AED {winner_cost_aed:,.0f} | Pool {winner_pool}\n"
        f"  Score: {winner_score} | Approval required: {capital_decision.get('approval_required', True)}"
    )

    logger.info(
        f"HITL winner locked | "
        f"recommended=Option {winner_id} | "
        f"approval_amount=AED {winner_cost_aed:,.0f} | pool={winner_pool}"
    )
    retriever   = _retriever
    if retriever and retriever.is_available():
        policy_context = retriever.query_for_agent1(...)
    else:
        policy_context = "Knowledge base unavailable — using LLM knowledge."
    policy_context   = retriever.query_for_agent4(
        category      = state.get("demand_summary", {}).get("category", ""),
        supplier_name = supplier_data.get("supplier_name", ""),
        route         = "ESCALATE",
    )
    logger.info(f"Agent 4 RAG context fetched | {len(policy_context)} chars")



    messages = PROMPTS["agent4"].format_messages(
        pipeline_id      = state["pipeline_id"],
        sku_id           = sku_id,
        route            = "ESCALATE",
        demand_summary   = json.dumps(state.get("demand_summary",   {}), indent=2),
        options_package  = json.dumps(state.get("options_package",  {}), indent=2),
        capital_decision = json.dumps(state.get("capital_decision", {}), indent=2),
        winner_summary   = winner_summary,
        supplier_data    = json.dumps(supplier_data, indent=2),
        policy_context   = policy_context,
    )

    logger.info(
        f"HITL node calling LLM "
        f"({get_provider_name()}/{get_model_name()})..."
    )

    response = llm.with_config({
        "run_name": f"Agent4-HITL-Briefing | {sku_id} | winner:Option {winner_id}",
        "tags":     ["agent4", "hitl-briefing", "escalate", f"winner:option-{winner_id.lower()}"],
        "metadata": {
            "agent":          "hitl_briefing",
            "sku_id":         sku_id,
            "winner_id":      winner_id,
            "winner_cost_aed": winner_cost_aed,
            "winner_pool":    winner_pool,
            "approval_required": capital_decision.get("approval_required", True),
        },
    }).invoke(messages)
    briefing = response.content.strip()

    if f"Option {winner_id}" not in briefing:
        logger.warning(
            f"HITL MISMATCH DETECTED | briefing does not reference winner "
            f"Option {winner_id} | AED {winner_cost_aed:,.0f}"
        )

    logger.info(f"HITL node complete | {len(briefing)} chars")
    logger.info(
        f"\n{'='*60}\n"
        f"HITL BRIEFING:\n"
        f"{'='*60}\n"
        f"{briefing}\n"
        f"{'='*60}"
    )
    logger.info("Pipeline PAUSED — waiting for human approval")
 
    return {
        "hitl_briefing": briefing,
        "action_taken":  "ESCALATED",
        "final_status":  "ESCALATED",
    }


# ==============================================================================
# NODE 5b — EXECUTE NODE: Writeback. HITL protected.
# ==============================================================================

def execute_node(state: AgentState) -> dict:
    """
    execute_node is being called in two scenarios:
    1. Scenario 1 — AUTO_EXECUTE (no human involved):

        route_node sets route = "AUTO_EXECUTE"
            ↓
        decide_route returns "execute_node"
            ↓
        LangGraph tries to run execute_node
            ↓
        SPEED BUMP fires — graph pauses
            ↓
        API sees approval_required = False
            ↓
        API calls resume_pipeline(approved=True) IMMEDIATELY — no human clicks anything
            ↓
        execute_node runs
            ↓
        briefing says "AUTO-EXECUTED"

        
    2. Scenario 2 — ESCALATE (human approved):

        route_node sets route = "ESCALATE"
            ↓
        decide_route returns "hitl_node"
            ↓
        hitl_node runs — writes URGENT briefing
            ↓
        Graph hits speed bump — PAUSES
            ↓
        Human reads briefing on dashboard
            ↓
        Human clicks APPROVE
            ↓
        API calls resume_pipeline(approved=True)
            ↓
        execute_node runs
            ↓
        briefing says "APPROVED BY HUMAN"


    Writes reorder_triggered = Yes for all Critical/At Risk positions.
 
    Protected by interrupt_before=["execute_node"].
    LangGraph PAUSES before this node every single time.
 
    For AUTO_EXECUTE: API resumes immediately (system decision, no human).
    For ESCALATE:     human approves -> API calls resume_pipeline().
 
    Fetches supplier contact via MCP for confirmation message.
 
    Palantir equivalent:
        Agent 4 Route 2 — AUTO_EXECUTE.
        Edit RCC Inventory Position (reorder_triggered = Yes).
        That action also had "Asks for approval" flag in Palantir.
    """

    sku_id = state["sku_id"]
    route  = state.get("route", "ESCALATE")
    logger.info(f"Execute node starting | sku_id={sku_id} | route={route}")

    # writeback — direct DB call, not via MCP (internal operation)
    rows_updated = writeback_reorder_for_all_positions(sku_id)

    logger.info(
        f"Execute node complete | "
        f"reorder_triggered=Yes on {rows_updated} positions"
    )

    capital_decision = state.get("capital_decision", {})
    recommended      = capital_decision.get("recommended", "?")
    amount           = capital_decision.get("approval_amount_aed", 0)
    pool             = capital_decision.get("approval_pool", "")

    # FIX 3 applied: one _run_async call with async helper
    supplier_data = _run_async(_execute_fetch(sku_id))

    contact = supplier_data.get("contact_name", "")
    email   = supplier_data.get("contact_email", "")

    # briefing reflects WHO approved — system or human
    if route == "AUTO_EXECUTE":
        briefing = (
            f"AUTO-EXECUTED: Option {recommended} approved automatically.\n"
            f"Cost AED {amount:,.0f} from {pool} — below auto-approve limit.\n"
            f"No human approval required.\n"
            f"reorder_triggered = Yes on {rows_updated} positions.\n"
            f"Supplier: {contact} — {email}"
        )
    else:
        # human read the HITL briefing and clicked Approve
        briefing = (
            f"APPROVED BY HUMAN: Option {recommended} approved by planner.\n"
            f"Cost AED {amount:,.0f} from {pool}.\n"
            f"reorder_triggered = Yes on {rows_updated} positions.\n"
            f"Supplier: {contact} — {email}"
        )

    logger.info(
        f"Execute node briefing | "
        f"route={route} | rows_updated={rows_updated}"
    )
 
    return {
        "hitl_briefing": briefing,
        "action_taken":  "AUTO_EXECUTED" if route == "AUTO_EXECUTE" else "EXECUTED_AFTER_APPROVAL",
        "final_status":  "AUTO_EXECUTED" if route == "AUTO_EXECUTE" else "EXECUTED_AFTER_APPROVAL",
    }


# ==============================================================================
# NODE 5c — SUSPEND NODE: Pool HIGH. No action taken.
# ==============================================================================

def suspend_node(state: AgentState) -> dict:
    """
    No order placed. Pool pressure is HIGH.
    Fetches pool info via MCP for suspension message.
 
    Palantir equivalent:
        Agent 4 Route 1 — SUSPEND.
        Sets pipeline_status = SUSPENDED. No writeback.
    """
    sku_id = state["sku_id"]
    capital_decision = state.get("capital_decision", {})

    approval_pool = capital_decision.get("approval_pool", "CP001")

    # FIX 3 applied: one _run_async call with async helper
    pool_data = _run_async(_suspend_fetch(approval_pool))

    pool_name = pool_data.get("pool_name", approval_pool)
    pressure  = pool_data.get("pool_pressure_flag", "HIGH")

    logger.warning(
        f"Suspend node | sku_id={sku_id} | "
        f"{pool_name} pressure={pressure} | NO ORDER PLACED"
    )
 
    briefing = (
        f"SUSPENDED: No action taken for {sku_id}.\n"
        f"Reason: {pool_name} pool pressure is {pressure}.\n"
        f"Budget constrained — order cannot be placed at this time.\n"
        f"Alert will repeat when pool pressure reduces."
    )
 
    return {
        "hitl_briefing": briefing,
        "action_taken":  "SUSPENDED",
        "final_status":  "SUSPENDED",
    }

# ==============================================================================
# NODE 6 — SAVE NODE: Persist to audit log
# ==============================================================================

def save_node(state: AgentState) -> dict:
    """
    Saves completed pipeline run to pipeline_log audit table.
    Called after every terminal node (hitl, execute, suspend).
    """
    try:
        save_pipeline_run(
            pipeline_id      = state["pipeline_id"],
            sku_id           = state["sku_id"],
            store_id         = state["store_id"],
            final_status     = state.get("final_status", "UNKNOWN"),
            demand_summary   = state.get("demand_summary"),
            options_package  = state.get("options_package"),
            capital_decision = state.get("capital_decision"),
            hitl_briefing    = state.get("hitl_briefing"),
        )
        logger.info(
            f"Pipeline saved | "
            f"{state['pipeline_id']} | "
            f"{state.get('final_status')}"
        )
    except Exception as e:
        logger.error(f"save_node error: {e}")
    return {}

# ==============================================================================
# BUILD THE GRAPH
# ==============================================================================

def build_graph():
    """
    Assembles all nodes and edges into a compiled LangGraph application.
 
    Nodes registered: 8 (plus __start__ and __end__ added by LangGraph)
    Edges: linear agent chain + conditional routing + all terminals to save

    __start__        <- LangGraph adds this
        agent1_node      <- you wrote this
        agent2_node      <- you wrote this
        agent3_node      <- you wrote this
        route_node       <- you wrote this
        hitl_node        <- you wrote this
        execute_node     <- you wrote this
        suspend_node     <- you wrote this
        save_node        <- you wrote this
    __end__          <- LangGraph adds this
 
    HITL interrupt: interrupt_before=["execute_node"]
        Pauses graph before every writeback.
        Checkpoint stored in MemorySaver — resumable after pause.
 
    For production: replace MemorySaver with:
        from langgraph.checkpoint.sqlite import SqliteSaver
        checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

    The complete picture in one flow:

        build_graph() called
            ↓
        StateGraph(AgentState) created — blank map
            ↓
        add_node x8  — 8 cities placed on map
            ↓
        add_edge x6  — roads drawn between cities
            ↓
        add_conditional_edges — fork in road at route_node
            ↓
        compile(checkpointer, interrupt_before)
            — map laminated
            — MemorySaver attached (saves state after every node)
            — speed bump placed before execute_node
            ↓
        returns app — ready to run
            ↓
        run_pipeline() calls app.invoke(initial_state)
            ↓
        graph runs node by node
            ↓
        after each node -> checkpoint saved to MemorySaver
            ↓
        before execute_node -> PAUSE
            ↓
        resume_pipeline() called -> loads checkpoint -> continues
    """

    builder = StateGraph(AgentState)

    # register all nodes
    builder.add_node("agent1_node", agent1_node)
    builder.add_node("agent2_node", agent2_node)
    builder.add_node("agent3_node",  agent3_node)
    builder.add_node("route_node",   route_node)
    builder.add_node("hitl_node",    hitl_node)
    builder.add_node("execute_node", execute_node)
    builder.add_node("suspend_node", suspend_node)
    builder.add_node("save_node",    save_node)

    # linear flow: agent1 -> agent2 -> agent3 -> route
    builder.set_entry_point("agent1_node")
    builder.add_edge("agent1_node", "agent2_node")
    builder.add_edge("agent2_node", "agent3_node")
    builder.add_edge("agent3_node", "route_node")

    # conditional routing: route_node decides which terminal node runs
    builder.add_conditional_edges(
        "route_node",
        decide_route,
        {
            "hitl_node" : "hitl_node",
            "execute_node": "execute_node",
            "suspend_node": "suspend_node",
        }
    )

    # all terminal nodes go to save then END
    builder.add_edge("hitl_node", "save_node")
    builder.add_edge("execute_node", "save_node")
    builder.add_edge("suspend_node", "save_node")
    builder.add_edge("save_node",    END)

    checkpointer = MemorySaver()

    app = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["execute_node"],
    )

    return app


# build once at module level — reused for every pipeline run
_app = build_graph()

# ==============================================================================
# PUBLIC API — called by scheduler and FastAPI endpoints
# ==============================================================================

def run_pipeline(sku_id: str, store_id: str) -> dict:
    """
    Starts a new pipeline run for a given SKU and store.
 
    Called by:
        - Scheduler (auto-triggered when new alert detected)
        - FastAPI endpoint POST /api/v1/agent/analyse
 
    Returns final state dict.
    If HITL paused, returns state at pause point with final_status=ESCALATED.
    """
    pipeline_id = f"PIPE_{sku_id}_{date.today().strftime('%Y-%m-%d')}"

    initial_state: AgentState = {
        "sku_id":           sku_id,
        "store_id":         store_id,
        "pipeline_id":      pipeline_id,
        "demand_summary":   None,
        "options_package":  None,
        "capital_decision": None,
        "hitl_briefing":    None,
        "action_taken":     None,
        "route":            None,
        "final_status":     None,
    }

    config = {
        "configurable": {"thread_id": pipeline_id},
        "run_name": f"ORCA Pipeline | {sku_id}",
        "tags": ["orca-pipeline", f"env:{os.getenv('ENVIRONMENT', 'local')}"],
        "metadata": {
            "pipeline_id": pipeline_id,
            "sku_id":      sku_id,
            "store_id":    store_id,
            "environment": os.getenv("ENVIRONMENT", "local"),
        },
    }
    logger.info(f"Pipeline starting | {pipeline_id}")

    final_state = _app.invoke(initial_state, config=config)

    final_status = final_state.get("final_status", "UNKNOWN")
    logger.info(
        f"Pipeline complete | "
        f"{pipeline_id} | "
        f"status={final_status}"
    )
    return final_state


def resume_pipeline(pipeline_id: str, approved: bool) -> dict:
    """
    Resumes a paused pipeline after HITL decision.
 
    Called by:
        - FastAPI endpoint POST /api/v1/agent/approve
 
    Args:
        pipeline_id: the pipeline to resume
        approved:    True = proceed with execute_node
                     False = skip execute, mark as REJECTED
 
    Returns final state after resumption.
    """
    config = {
        "configurable": {"thread_id": pipeline_id},
        "run_name": f"ORCA Resume | {pipeline_id}",
        "tags": ["orca-pipeline", "hitl-resume", f"decision:{'approved' if approved else 'rejected'}"],
        "metadata": {"pipeline_id": pipeline_id, "hitl_decision": "approved" if approved else "rejected"},
    }

    if not approved:
        logger.info(f"Pipeline rejected by human | {pipeline_id}")
        _app.update_state(config,{
            "route" : "SUSPEND",
            "final_status": "REJECTED",
            "action_taken": "REJECTED_BY_HUMAN",
        })
    
    logger.info(f"Pipeline resuming | {pipeline_id} | approved={approved}")

    final_state = _app.invoke(None, config=config)  # None means "do NOT start fresh.
                                                    # Load the checkpoint from this
                                                    # thread_id and continue from where you paused."
    '''
    No new state provided.
    Look up thread_id "PIPE_SKU00014_2026-05-15" in MemorySaver.
    Found checkpoint — graph was paused before execute_node.
    Load that state and continue. 
    '''      

    logger.info(
        f"Pipeline resumed | "
        f"{pipeline_id} | "
        f"status={final_state.get('final_status')}"
    )
    return final_state

def get_pipeline_state(pipeline_id: str) -> dict:
    """
    Returns current state of a paused pipeline.
    Used by dashboard HITL panel to show pending decision details.
    """
    config   = {"configurable": {"thread_id": pipeline_id}}
    snapshot = _app.get_state(config)
    return snapshot.values if snapshot else {}

# ==============================================================================
# QUICK TEST
# ==============================================================================

if __name__ == "__main__":
    print("\nORCA Graph — MCP version — running pipeline test\n")

    # ensure audit log table exists
    create_pipeline_table()

    # get top alert from DB
    alerts = get_critical_alerts()

    if not alerts:
        print("No alerts found. Run: python data/scheduler.py --once")
        sys.exit(1)
    
    top    = alerts[0]
    sku_id = top["sku_id"]

    # FIX 3 applied: get store via async helper
    async def _get_store(sku_id: str) -> tuple:
        tools     = await _get_mcp_tools()
        positions = await _call_mcp_tool(tools, "check_inventory_positions", {"sku_id": sku_id})
        return tools, positions

    tools, positions = _run_async(_get_store(sku_id))

    # positions may be a dict with "positions" key OR a raw list
    # handle both cases safely
    if isinstance(positions, dict):
        pos_list = positions.get("positions", [])
    elif isinstance(positions, list):
        pos_list = positions
    else:
        pos_list = []

    store_id = pos_list[0]["store_id"] if pos_list else "STR0001"

    print(f"SKU    : {sku_id} ({top.get('sku_name', '')})")
    print(f"Store  : {store_id}")
    print(f"LLM    : {get_provider_name()} / {get_model_name()}")
    print(f"MCP    : {MCP_SERVER_PATH}")
    print(f"Tools  : {[t.name for t in tools]}")
    print("-" * 60)
 
    final_state = run_pipeline(sku_id=sku_id, store_id=store_id)

    # If AUTO_EXECUTE — resume immediately (no human needed)
    # In Sprint 4 FastAPI does this automatically
    # For now we do it here in the test block
    route      = final_state.get("route", "")
    pipeline_id_run = f"PIPE_{sku_id}_{date.today().strftime('%Y-%m-%d')}"
    if route == "AUTO_EXECUTE":
        print("\n" + "-" * 60)
        print("AUTO_EXECUTE — resuming pipeline immediately (no human needed)")
        print("-" * 60)
        final_state = resume_pipeline(pipeline_id_run, approved=True)
    elif route == "ESCALATE":
        print("\n" + "-" * 60)
        print("ESCALATE — pipeline paused. Human approval required.")
        print(f"Call: resume_pipeline('{pipeline_id_run}', approved=True) to approve")
        print("-" * 60)


    print("\n" + "=" * 60)
    print("PIPELINE RESULT")
    print("=" * 60)
    print(f"Pipeline ID  : {final_state.get('pipeline_id')}")
    print(f"Final status : {final_state.get('final_status')}")
    print(f"Action taken : {final_state.get('action_taken')}")
 
    ds = final_state.get("demand_summary") or {}

    if ds:
        print(f"\nDemand Summary:")
        print(f"  urgency             : {ds.get('urgency')}")
        print(f"  critical_stores     : {ds.get('critical_stores')}")
        print(f"  at_risk_stores      : {ds.get('at_risk_stores')}")
        print(f"  projected_shortfall : {ds.get('projected_shortfall')}")
        print(f"  lead_time_too_late  : {ds.get('lead_time_too_late')}")
        print(f"  event_name          : {ds.get('event_name')}")
        print(f"  briefing            : {ds.get('briefing')}")
 
    op = final_state.get("options_package") or {}
    if op:
        print(f"\nOptions Package:")
        print(f"  recommended : Option {op.get('recommended')}")
        print(f"  reason      : {op.get('recommendation_reason')}")
        for opt in op.get("options", []):
            print(
                f"  Option {opt.get('id')} : "
                f"AED {opt.get('total_cost_aed', 0):>10,.0f} | "
                f"lead={opt.get('lead_time_days')}d | "
                f"feasible={opt.get('feasible')} | "
                f"{'NOT RECOMMENDED' if opt.get('not_recommended') else 'OK'}"
            )
 
    cd = final_state.get("capital_decision") or {}
    if cd:
        print(f"\nCapital Decision:")
        print(f"  winner            : Option {cd.get('recommended')}")
        print(f"  approval_required : {cd.get('approval_required')}")
        print(f"  amount            : AED {cd.get('approval_amount_aed', 0):,.0f}")
        print(f"  summary           : {cd.get('recommendation_summary')}")
        for opt in cd.get("scored_options", []):
            status = ""
            if not opt.get("feasible"):
                status = f"ELIMINATED: {opt.get('elimination_reason')}"
            elif opt.get("not_recommended"):
                status = "NOT RECOMMENDED"
            print(
                f"  Option {opt.get('id')} score : "
                f"{opt.get('total_score', 0):>6.2f} | "
                f"feasible={opt.get('feasible')} | {status}"
            )
 
    briefing = final_state.get("hitl_briefing") or ""
    if briefing:
        print(f"\n{'='*60}")
        print("HITL BRIEFING:")
        print("=" * 60)
        print(briefing)