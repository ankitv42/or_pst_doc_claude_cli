"""
ORCA — dashboard/api_client.py
================================
Thin HTTP client wrapping all FastAPI calls from Streamlit.

WHY A SEPARATE CLIENT MODULE:
    Streamlit app.py should contain ONLY UI logic.
    All HTTP calls, error handling, and response parsing live here.
    This is the standard pattern — UI layer never knows about HTTP.
    In production this gets replaced with a proper SDK.

    Testing: mock this module to test UI without a running API.
    Switching API URL: change BASE_URL in one place.

ALL methods:
    - Return Python dicts/lists — never raw httpx objects
    - Return None on any error — caller decides how to handle
    - Log errors to console — never crash the Streamlit app
    - Timeout after 120s — pipelines can run for 90s
"""
import os
import httpx
import logging
import streamlit as st

logger = logging.getLogger("orca.dashboard")

# API base URL — matches uvicorn port
# BASE_URL = "http://localhost:8080"
BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")
TIMEOUT  = 120.0   # seconds — must be > max pipeline runtime


def _get(path: str) -> dict | None:
    """GET request with error handling."""
    try:
        r = httpx.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("Cannot connect to ORCA API. Is it running on port 8080?")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"GET {path} failed: {e.response.status_code} {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"GET {path} error: {e}")
        return None


def _post(path: str, body: dict) -> dict | None:
    """POST request with error handling."""
    try:
        r = httpx.post(
            f"{BASE_URL}{path}",
            json=body,
            timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("Cannot connect to ORCA API. Is it running on port 8080?")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"POST {path} failed: {e.response.status_code} {e.response.text}")
        try:
            return e.response.json()
        except Exception:
            return {"error": e.response.text}
    except Exception as e:
        logger.error(f"POST {path} error: {e}")
        return None


# ==============================================================================
# PUBLIC API
# ==============================================================================

def get_health() -> dict | None:
    return _get("/health")


def get_alerts() -> list[dict]:
    result = _get("/api/v1/alerts")
    return result.get("alerts", []) if result else []


def run_pipeline(sku_id: str, store_id: str) -> dict | None:
    return _post("/api/v1/pipeline/run", {"sku_id": sku_id, "store_id": store_id})


def get_pipeline_state(pipeline_id: str) -> dict | None:
    return _get(f"/api/v1/pipeline/{pipeline_id}/state")


def approve_pipeline(pipeline_id: str, reviewer: str) -> dict | None:
    return _post(
        f"/api/v1/pipeline/{pipeline_id}/approve",
        {"approved": True, "reviewer": reviewer},
    )


def reject_pipeline(pipeline_id: str, reviewer: str) -> dict | None:
    return _post(
        f"/api/v1/pipeline/{pipeline_id}/approve",
        {"approved": False, "reviewer": reviewer},
    )


def get_briefing(pipeline_id: str) -> str | None:
    result = _get(f"/api/v1/pipeline/{pipeline_id}/briefing")
    return result.get("briefing") if result else None


def list_pipelines() -> list[dict]:
    result = _get("/api/v1/pipelines")
    return result.get("pipelines", []) if result else []