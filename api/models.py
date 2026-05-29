"""
ORCA — api/models.py
=====================
Pydantic request/response schemas for the ORCA FastAPI layer.

WHY PYDANTIC SCHEMAS:
    Every API request and response is strictly typed.
    FastAPI validates incoming JSON automatically against these models.
    If a client sends wrong types or missing fields — 422 error before
    any business logic runs. No defensive coding needed inside routes.

    This is the standard pattern at FAANG:
        Request  schema → validates input
        Response schema → guarantees output shape
        Error    schema → consistent error format across all endpoints

DESIGN DECISIONS:
    - All pipeline IDs are strings (format: PIPE_SKU00090_2026-05-27)
    - Monetary amounts in AED as floats
    - Timestamps as ISO strings — frontend handles timezone display
    - Optional fields use Optional[T] = None — never omit fields from response
    - Enums for all fixed-value fields — prevents typos across codebase
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ==============================================================================
# ENUMS
# ==============================================================================

class PipelineStatus(str, Enum):
    """All possible pipeline lifecycle states."""
    STARTED    = "STARTED"      # background task launched, agents not yet run
    RUNNING    = "RUNNING"      # agents actively processing
    ESCALATED  = "ESCALATED"    # HITL pause — waiting for human decision
    APPROVED   = "APPROVED"     # human approved — execute_node running
    REJECTED   = "REJECTED"     # human rejected — suspend_node running
    AUTO_EXECUTED = "AUTO_EXECUTED"  # below auto-approve limit, executed automatically
    EXECUTED_AFTER_APPROVAL = "EXECUTED_AFTER_APPROVAL"  # human approved, executed
    SUSPENDED  = "SUSPENDED"    # pool pressure HIGH — no order placed
    FAILED     = "FAILED"       # unhandled exception in graph


class RouteDecision(str, Enum):
    """Agent 3 routing outcomes."""
    ESCALATE     = "ESCALATE"
    AUTO_EXECUTE = "AUTO_EXECUTE"
    SUSPEND      = "SUSPEND"


class Urgency(str, Enum):
    """Demand urgency levels from Agent 1."""
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"


# ==============================================================================
# REQUEST SCHEMAS
# ==============================================================================

class RunPipelineRequest(BaseModel):
    """
    POST /api/v1/pipeline/run

    Triggers a new pipeline run for a SKU + store combination.
    sku_id and store_id come from the alert table — Streamlit
    passes them from the GET /api/v1/alerts response.
    """
    sku_id:   str = Field(..., example="SKU00090", description="SKU identifier")
    store_id: str = Field(..., example="STR0077",  description="Store identifier")


class ApproveRequest(BaseModel):
    """
    POST /api/v1/pipeline/{pipeline_id}/approve
    POST /api/v1/pipeline/{pipeline_id}/reject

    Human HITL decision. approved=True → execute_node runs.
    approved=False → suspend_node runs (order not placed).
    reviewer is optional — logged to audit trail.
    """
    approved: bool = Field(..., description="True to approve, False to reject")
    reviewer: Optional[str] = Field(
        None,
        example="ankit.kumar@retailcorp.ae",
        description="Email or name of the human reviewer — for audit trail"
    )


# ==============================================================================
# NESTED RESPONSE SCHEMAS
# (used as fields inside larger response models)
# ==============================================================================

class DemandSummary(BaseModel):
    """Agent 1 output — demand intelligence."""
    sku_id:               str
    urgency:              Optional[str]   = None
    critical_stores:      Optional[int]   = None
    at_risk_stores:       Optional[int]   = None
    projected_shortfall:  Optional[int]   = None
    lead_time_too_late:   Optional[bool]  = None
    event_name:           Optional[str]   = None
    demand_trend:         Optional[str]   = None
    confidence_score:     Optional[float] = None
    briefing:             Optional[str]   = None
    crew_insights:        Optional[str]   = None


class ReplenishmentOption(BaseModel):
    """Single option (A, B, or C) inside options_package."""
    id:                str
    name:              Optional[str]   = None
    order_qty:         Optional[float]   = None
    lead_time_days:    Optional[float] = None
    total_cost_aed:    Optional[float] = None
    pool_id:           Optional[str]   = None
    availability_pct:  Optional[float] = None
    feasible:          Optional[bool]  = None
    not_recommended:   Optional[bool]  = None
    elimination_reason: Optional[str]  = None


class OptionsPackage(BaseModel):
    """Agent 2 output — 3 replenishment options."""
    recommended:            Optional[str]  = None
    recommendation_reason:  Optional[str]  = None
    options:                list[ReplenishmentOption] = []


class ScoredOption(BaseModel):
    """Agent 3 scored option with formula breakdown."""
    id:                 str
    total_score:        Optional[float] = None
    budget_score:       Optional[float] = None
    availability_score: Optional[float] = None
    margin_score:       Optional[float] = None
    lead_time_penalty:  Optional[float] = None
    feasible:           Optional[bool]  = None
    elimination_reason: Optional[str]   = None
    not_recommended:    Optional[bool]  = None


class CapitalDecision(BaseModel):
    """Agent 3 output — capital allocation decision."""
    recommended:              Optional[str]   = None
    approval_required:        Optional[bool]  = None
    approval_amount_aed:      Optional[float] = None
    approval_pool:            Optional[str]   = None
    recommendation_summary:   Optional[str]   = None
    scored_options:           list[ScoredOption] = []


# ==============================================================================
# ALERT SCHEMA
# ==============================================================================

class Alert(BaseModel):
    """Single critical/at-risk alert from the DB."""
    sku_id:          str
    sku_name:        Optional[str]  = None
    category:        Optional[str]  = None
    abc_class:       Optional[str]  = None
    store_id:        Optional[str]  = None
    stock_status:    Optional[str]  = None
    current_stock:   Optional[int]  = None
    days_of_cover:   Optional[float] = None
    risk_score:      Optional[float] = None


# ==============================================================================
# PRIMARY RESPONSE SCHEMAS
# ==============================================================================

class PipelineRunResponse(BaseModel):
    """
    POST /api/v1/pipeline/run → immediate response.

    Returns pipeline_id and STARTED status immediately.
    Client must poll GET /api/v1/pipeline/{id}/state for updates.
    Pipeline runs as a FastAPI background task.
    """
    pipeline_id: str
    status:      PipelineStatus
    message:     str
    started_at:  str   # ISO timestamp


class PipelineStateResponse(BaseModel):
    """
    GET /api/v1/pipeline/{pipeline_id}/state

    Full pipeline state snapshot — polled by Streamlit every 3 seconds.
    All agent outputs included when available.
    frontend renders progressively as fields become non-null.
    """
    pipeline_id:      str
    sku_id:           Optional[str]            = None
    store_id:         Optional[str]            = None
    status:           Optional[str]            = None
    route:            Optional[str]            = None
    action_taken:     Optional[str]            = None
    demand_summary:   Optional[DemandSummary]  = None
    options_package:  Optional[OptionsPackage] = None
    capital_decision: Optional[CapitalDecision] = None
    hitl_briefing:    Optional[str]            = None
    last_updated:     Optional[str]            = None


class ApproveResponse(BaseModel):
    """
    POST /api/v1/pipeline/{pipeline_id}/approve or /reject

    Returned after resume_pipeline() completes.
    """
    pipeline_id:  str
    status:       PipelineStatus
    action_taken: Optional[str] = None
    message:      str
    reviewed_by:  Optional[str] = None
    reviewed_at:  str


class AlertsResponse(BaseModel):
    """GET /api/v1/alerts — list of current critical/at-risk SKUs."""
    total:  int
    alerts: list[Alert]


class HealthResponse(BaseModel):
    """GET /health — liveness + readiness check."""
    status:      str   # "ok" or "degraded"
    db:          str   # "connected" or "error"
    rag:         str   # "available" or "unavailable" (Windows limitation)
    llm:         str   # provider/model string
    mcp:         str   # "ready"
    version:     str   # sprint version
    timestamp:   str   # ISO timestamp


class ErrorResponse(BaseModel):
    """
    Consistent error shape for all 4xx and 5xx responses.
    FastAPI returns this via exception handlers.
    """
    error:   str
    detail:  Optional[str] = None
    path:    Optional[str] = None
    timestamp: str

'''
This file defines the contract of your API.

Think of it as the official data blueprint between:

Frontend (Streamlit/UI)
Backend (FastAPI routes)
AI agents / pipeline
Database
External clients

In a production system, this file is extremely important because it guarantees:

what data comes IN
what data goes OUT
what values are allowed
what structure every endpoint follows

This is very FAANG-style backend engineering.

Big Picture

This file is doing 3 major things:

    Defines allowed constant values → using Enum
    Defines request body schemas → what client sends
    Defines response schemas → what API returns

Everything is strongly typed.

1. ENUMS — Controlled Values
    class PipelineStatus(str, Enum):
    
    This creates a fixed set of allowed values.
    Instead of random strings like:

    status = "done"
    status = "completed"
    status = "finished"

    you enforce:
    
    STARTED
    RUNNING
    FAILED
    ESCALATED

    This prevents:

    typos
    inconsistent states
    frontend/backend mismatch



'''