"""
ORCA — agents/crew.py
======================
CrewAI Demand Forecasting Crew — Sprint 3 Week 6.

WHY CREWAI ON TOP OF LANGGRAPH:
    LangGraph = you design the exact workflow. Sequential, stateful, deterministic.
                Perfect for the 4-agent pipeline where order and HITL matter.

    CrewAI    = you define agents with roles and goals. CrewAI manages collaboration.
                Perfect for open-ended analysis tasks where agents need to reason
                independently and then synthesise.

    Together  = LangGraph orchestrates the business pipeline (Agents 1-4).
                CrewAI handles the deep demand analysis INSIDE Agent 1.
                One project. Both paradigms. Full coverage for interviews.

THE CREW:
    Agent A — Data Analyst
        Role: crunch the quantitative data
        Tools: get_velocity_tool, get_positions_tool (read from orca.db via queries.py)
        Output: demand rising/stable/falling, critical store breakdown, coverage gaps

    Agent B — Market Analyst
        Role: interpret business context and policy
        Tools: query_rag_tool (queries ChromaDB via retriever.py)
        Output: event context, ordering rules, lead time constraints

    Agent C — Forecast Strategist
        Role: synthesise A and B into final structured forecast
        Tools: none — reads Agent A and B outputs
        Output: structured demand_summary JSON with confidence_score and crew_insights

HOW IT INTEGRATES WITH GRAPH.PY:
    In agent1_node, CrewAI replaces the single LLM call.
    crew_forecast = run_forecast_crew(sku_id, positions_result, sku_result,
                                      velocity_result, events_result)
    The rest of graph.py (Agents 2, 3, 4) is COMPLETELY UNCHANGED.

LLM:
    groq/llama-3.3-70b-versatile
    Specifically fine-tuned for tool calling — uses correct JSON format.
    llama-3.1-8b-instant uses wrong XML tool format and fails with CrewAI.
    litellm installed at C:/lit (short path workaround for Windows long path limit).

Usage:
    python agents/crew.py          # standalone test
    from agents.crew import run_forecast_crew
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Optional

# litellm short-path install — workaround for Windows long path limit
# litellm installed via: pip install litellm --target C:\lit
sys.path.insert(0, r"C:/lit")

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

from db.queries import get_all_positions_for_sku, get_sales_velocity
from docs.rag.retriever import get_retriever

logger = logging.getLogger("orca.crew")


# ==============================================================================
# LLM — Groq via litellm (fast, free, correct tool-use format)
# ==============================================================================

def _get_crew_llm() -> str:
    """
    Returns Groq model string for CrewAI via litellm.
    
    llama-3.3-70b-versatile — current Groq recommended model for tool use.
    Replaces deprecated llama3-groq-8b-8192-tool-use-preview.
    70B model — much better reasoning than 8B for tool orchestration.
    Free on Groq. ~14,400 requests/day.
    """
    return "groq/llama-3.3-70b-versatile"


# ==============================================================================
# CREWAI TOOLS
# Direct DB calls — no MCP needed (CrewAI runs synchronously).
# Tool docstrings guide the LLM on how to call them correctly.
# Output kept compact — avoid hitting Groq token limits.
# ==============================================================================

@tool("get_position_data")
def get_positions_tool(sku_id: str) -> str:
    """
    Fetches current inventory positions for a SKU across all stores.
    Returns counts of critical and at-risk stores, total stock, top 3 critical stores.

    Input: sku_id as a plain string. Example: SKU00090
    """
    try:
        positions = get_all_positions_for_sku(sku_id)
        critical  = [p for p in positions if p["stock_status"] == "Critical"]
        at_risk   = [p for p in positions if p["stock_status"] == "At Risk"]

        summary = {
            "total_stores":            len(positions),
            "critical_count":          len(critical),
            "at_risk_count":           len(at_risk),
            "total_stock_units":       sum(p["current_stock_units"] for p in positions),
            "min_days_cover_critical": min(
                (p["days_of_cover"] for p in critical), default=0
            ),
            "top_3_critical_stores": [
                {
                    "store_id":      p["store_id"],
                    "stock_units":   p["current_stock_units"],
                    "days_of_cover": p["days_of_cover"],
                    "coverage_gap":  p.get("coverage_gap_units", 0),
                    "risk_score":    p.get("risk_score", 0),
                }
                for p in critical[:3]
            ],
        }
        return json.dumps(summary, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "sku_id": sku_id})


@tool("get_velocity_data")
def get_velocity_tool(sku_id: str) -> str:
    """
    Fetches sales velocity data for a SKU — demand rate and recent trend.
    Returns avg_daily_demand, demand_trend_7d, event_baseline_uplift, trend_direction.

    Input: sku_id as a plain string. Example: SKU00090
    """
    try:
        velocity = get_sales_velocity(sku_id)
        compact = {
            "avg_daily_demand":      velocity.get("avg_daily_demand", 0),
            "demand_trend_7d":       velocity.get("demand_trend_7d", 0),
            "event_baseline_uplift": velocity.get("event_baseline_uplift", 1.0),
            "trend_direction": (
                "rising"  if (velocity.get("demand_trend_7d") or 0) > 0.02
                else "falling" if (velocity.get("demand_trend_7d") or 0) < -0.02
                else "stable"
            ),
        }
        return json.dumps(compact, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "sku_id": sku_id})


@tool("query_policy_knowledge")
def query_rag_tool(query: str) -> str:
    """
    Searches the ORCA knowledge base for business rules, event planning guidelines,
    supplier SLA terms, ordering policies, and capital pool rules.

    Input: plain English query string.
    Example: ordering rules Class B Electronics CRITICAL urgency DSF event
    Example: TechLine Asia lead time expedite premium Electronics
    """
    try:
        retriever = get_retriever()
        if not retriever.is_available():
            return "Knowledge base unavailable. Proceed with general knowledge."

        doc_types = ["policy", "event", "supplier", "graph"]
        chunks    = retriever._hybrid_retrieve(query, doc_types, top_k=5)
        chunks    = retriever._rerank(query, chunks)

        if not chunks:
            return "No relevant policy found."

        parts = []
        for c in chunks[:2]:
            meta    = c.get("metadata", {})
            dtype   = meta.get("doc_type", "").capitalize()
            section = meta.get("section_name", "")[:50]
            text    = c["text"].strip()[:400]
            parts.append(f"[{dtype}] {section}\n{text}")

        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"RAG query error: {str(e)}"


# ==============================================================================
# AGENTS
# ==============================================================================

def _build_agents(llm: str):
    """
    Builds 3 CrewAI agents.

    llm is a string like 'groq/llama-3.3-70b-versatile'.
    CrewAI passes this to litellm which handles the API call.

    max_iter=5 — enough iterations for tool-use trained model.
    allow_delegation=False — keeps each agent focused on its task.
    """

    data_analyst = Agent(
        role="Senior Data Analyst — UAE Retail Inventory",
        goal=(
            "Analyse quantitative inventory and sales data for the given SKU. "
            "Use tools to get actual numbers. Report exactly what the data shows."
        ),
        backstory=(
            "You are a precise data analyst specialising in UAE retail inventory. "
            "You only report numbers from actual tool calls, never guess. "
            "When demand data is zero, you note that as a data limitation."
        ),
        tools=[get_positions_tool, get_velocity_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
    )

    market_analyst = Agent(
        role="Market Analyst — UAE Retail Planning",
        goal=(
            "Research business context for the given SKU — upcoming events, "
            "ordering policy rules, and supplier constraints. "
            "Use the knowledge base tool to find verified rules."
        ),
        backstory=(
            "You are a UAE retail planning specialist who understands event-driven "
            "demand and supplier lead time constraints. "
            "You use the ORCA knowledge base to retrieve verified business rules."
        ),
        tools=[query_rag_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
    )

    forecast_strategist = Agent(
        role="Demand Forecast Strategist",
        goal=(
            "Synthesise the Data Analyst and Market Analyst findings into a "
            "structured JSON demand forecast. Output valid JSON only — no other text."
        ),
        backstory=(
            "You synthesise quantitative data and market context into actionable "
            "forecasts. You are concise and always output valid JSON with no extra text."
        ),
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

    return data_analyst, market_analyst, forecast_strategist


# ==============================================================================
# TASKS
# ==============================================================================

def _build_tasks(
    data_analyst,
    market_analyst,
    forecast_strategist,
    sku_id:          str,
    category:        str,
    abc_class:       str,
    effective_lead:  float,
    event_name:      Optional[str],
    critical_stores: int,
    at_risk_stores:  int,
):
    """Builds 3 sequential tasks for the forecasting crew."""

    task_data = Task(
        description=(
            f"Analyse SKU {sku_id} ({category}, Class {abc_class}).\n"
            f"Known: {critical_stores} critical stores, {at_risk_stores} at-risk, "
            f"lead time {effective_lead} days, event: {event_name or 'none'}.\n\n"
            f"Steps:\n"
            f"1. Call get_position_data with sku_id='{sku_id}' to get store breakdown.\n"
            f"2. Call get_velocity_data with sku_id='{sku_id}' to get demand rate.\n"
            f"3. Report: demand trend direction, minimum days cover in critical stores, "
            f"total units at risk, data quality (was avg_daily_demand zero?)."
        ),
        expected_output=(
            "Quantitative summary with: avg_daily_demand, trend_direction "
            "(rising/stable/falling), min_days_cover_critical, total_units_at_risk, "
            "data_quality_note (mention if demand data is zero)."
        ),
        agent=data_analyst,
    )

    task_market = Task(
        description=(
            f"Research business context for {sku_id} ({category}, Class {abc_class}).\n"
            f"Event: {event_name or 'none'}. Lead time: {effective_lead} days.\n\n"
            f"Use query_policy_knowledge to find:\n"
            f"1. Ordering rules for Class {abc_class} with CRITICAL urgency.\n"
            f"2. Event planning rules for {event_name or category} category.\n"
            f"3. Whether {effective_lead} day lead time is adequate.\n"
            f"Report: event_uplift_factor, lead_time_adequate (yes/no + reason), "
            f"key policy rules (2-3 bullet points)."
        ),
        expected_output=(
            "Market context with: event_uplift_factor, lead_time_adequate, "
            "lead_time_too_late (true/false), key_policy_rules (2-3 points), "
            "market_summary (1-2 sentences)."
        ),
        agent=market_analyst,
    )

    task_forecast = Task(
        description=(
            f"Synthesise findings for SKU {sku_id} into a demand_summary JSON.\n\n"
            f"Use ONLY the Data Analyst and Market Analyst outputs provided to you.\n"
            f"Output ONLY this JSON — no other text before or after:\n\n"
            f"{{\n"
            f'  "sku_id": "{sku_id}",\n'
            f'  "urgency": "CRITICAL or HIGH or MEDIUM",\n'
            f'  "critical_stores": {critical_stores},\n'
            f'  "at_risk_stores": {at_risk_stores},\n'
            f'  "projected_shortfall": 0,\n'
            f'  "lead_time_too_late": false,\n'
            f'  "event_name": "{event_name or ""}",\n'
            f'  "demand_trend": "rising or stable or falling",\n'
            f'  "confidence_score": 0.7,\n'
            f'  "briefing": "2-3 sentence summary",\n'
            f'  "crew_insights": "1-2 sentences on what crew discovered"\n'
            f"}}\n\n"
            f"Urgency rule: CRITICAL if critical_stores > 5 OR lead_time_too_late=true. "
            f"HIGH if critical_stores > 0. MEDIUM otherwise."
        ),
        expected_output=(
            "Valid JSON with all fields: sku_id, urgency, critical_stores, "
            "at_risk_stores, projected_shortfall, lead_time_too_late, event_name, "
            "demand_trend, confidence_score, briefing, crew_insights."
        ),
        agent=forecast_strategist,
        context=[task_data, task_market],
    )

    return task_data, task_market, task_forecast


# ==============================================================================
# PUBLIC API — called by graph.py agent1_node
# ==============================================================================

def run_forecast_crew(
    sku_id:           str,
    positions_result: dict,
    sku_result:       dict,
    velocity_result:  dict,
    events_result:    dict,
) -> dict:
    """
    Runs 3-agent CrewAI demand forecasting crew.
    Returns demand_summary dict — same structure as single LLM but richer.

    New fields vs single LLM:
        demand_trend     — rising / stable / falling
        confidence_score — 0.0-1.0 (lower when data is missing)
        crew_insights    — what the crew discovered beyond raw data

    Falls back to raw data summary if crew fails — resilience pattern.
    """
    logger.info(f"CrewAI forecast crew starting | sku_id={sku_id}")

    category        = sku_result.get("category", "")
    abc_class       = sku_result.get("abc_class", "B")
    effective_lead  = sku_result.get("effective_lead_time", 0)
    critical_stores = positions_result.get("critical_count", 0)
    at_risk_stores  = positions_result.get("at_risk_count", 0)
    event_list      = events_result.get("events", [])
    event_name      = event_list[0].get("event_name") if event_list else None

    llm = _get_crew_llm()
    data_analyst, market_analyst, forecast_strategist = _build_agents(llm)

    task_data, task_market, task_forecast = _build_tasks(
        data_analyst        = data_analyst,
        market_analyst      = market_analyst,
        forecast_strategist = forecast_strategist,
        sku_id              = sku_id,
        category            = category,
        abc_class           = abc_class,
        effective_lead      = effective_lead,
        event_name          = event_name,
        critical_stores     = critical_stores,
        at_risk_stores      = at_risk_stores,
    )

    crew = Crew(
        agents  = [data_analyst, market_analyst, forecast_strategist],
        tasks   = [task_data, task_market, task_forecast],
        process = Process.sequential,
        verbose = True,
    )

    logger.info("CrewAI crew kickoff starting...")

    try:
        result     = crew.kickoff()
        raw_output = result.raw if hasattr(result, "raw") else str(result)

        logger.info(f"CrewAI crew complete | output length: {len(raw_output)}")

        # parse JSON — strip markdown fences if present
        clean = raw_output.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            ).strip()

        # find first { to last } in case model added preamble
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start >= 0 and end > start:
            clean = clean[start:end]

        demand_summary = json.loads(clean)
        logger.info(
            f"CrewAI forecast complete | "
            f"urgency={demand_summary.get('urgency')} | "
            f"confidence={demand_summary.get('confidence_score')} | "
            f"trend={demand_summary.get('demand_trend')}"
        )
        return demand_summary

    except json.JSONDecodeError as e:
        logger.error(f"CrewAI JSON parse failed: {e}")
        return _fallback(sku_id, critical_stores, at_risk_stores,
                         effective_lead, event_name, velocity_result)
    except Exception as e:
        logger.error(f"CrewAI crew error: {e}")
        return _fallback(sku_id, critical_stores, at_risk_stores,
                         effective_lead, event_name, velocity_result)


def _fallback(
    sku_id, critical_stores, at_risk_stores,
    effective_lead, event_name, velocity_result
) -> dict:
    """
    Fallback demand_summary if CrewAI fails.
    Ensures graph.py never crashes — graceful degradation pattern.
    """
    logger.warning("CrewAI failed — using fallback demand summary from raw data")
    urgency = (
        "CRITICAL" if critical_stores > 5
        else "HIGH" if critical_stores > 0
        else "MEDIUM"
    )
    return {
        "sku_id":              sku_id,
        "urgency":             urgency,
        "critical_stores":     critical_stores,
        "at_risk_stores":      at_risk_stores,
        "projected_shortfall": 0,
        "lead_time_too_late":  False,
        "event_name":          event_name,
        "demand_trend":        "stable",
        "confidence_score":    0.5,
        "briefing": (
            f"{critical_stores} critical stores detected for {sku_id}. "
            f"CrewAI forecast unavailable — raw data fallback used."
        ),
        "crew_insights": "CrewAI unavailable — fallback used.",
    }


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    print("\nORCA CrewAI Demand Forecasting Crew — standalone test")
    print("LLM: groq/llama-3.3-70b-versatile (tool-use optimised)\n")

    test_positions = {
        "critical_count":      5,
        "at_risk_count":       4,
        "total_current_stock": 2546,
        "positions":           [],
    }
    test_sku = {
        "sku_id":               "SKU00090",
        "sku_name":             "Screen Protector v1",
        "category":             "Electronics",
        "abc_class":            "B",
        "effective_lead_time":  54.5,
        "margin_priority_rank": 3,
    }
    test_velocity = {
        "avg_daily_demand":      4.2,
        "demand_trend_7d":       0.08,
        "event_baseline_uplift": 1.0,
    }
    test_events = {
        "events_found": 1,
        "events": [{
            "event_name":        "Dubai Shopping Festival",
            "demand_uplift_pct": 90,
            "duration_days":     32,
        }],
    }

    result = run_forecast_crew(
        sku_id           = "SKU00090",
        positions_result = test_positions,
        sku_result       = test_sku,
        velocity_result  = test_velocity,
        events_result    = test_events,
    )

    print("\n" + "=" * 60)
    print("CREW FORECAST RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))