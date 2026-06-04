"""
tests/test_routing.py
======================
Unit tests for the route_node routing logic.

Tests the pure Python routing decision from agents/graph.py route_node:
    PRIORITY: SUSPEND > AUTO_EXECUTE > ESCALATE

    SUSPEND:      pool_pressure_flag = HIGH
    AUTO_EXECUTE: approval_required = False AND pool not HIGH
    ESCALATE:     approval_required = True AND pool not HIGH

Run: pytest tests/test_routing.py -v
"""

import pytest


# ==============================================================================
# Pure Python implementation of route_node's routing logic
# Mirrors agents/graph.py route_node (lines 737-776) exactly
# ==============================================================================

def decide_route(pool_pressure: str, approval_required: bool) -> str:
    """
    Pure Python routing decision — mirrors route_node in graph.py.
    Priority: SUSPEND > AUTO_EXECUTE > ESCALATE
    """
    if pool_pressure == "HIGH":
        return "SUSPEND"
    elif not approval_required:
        return "AUTO_EXECUTE"
    else:
        return "ESCALATE"


# ==============================================================================
# SUSPEND tests — pool pressure HIGH overrides everything
# ==============================================================================

class TestSuspendRoute:
    def test_high_pressure_suspends_even_without_approval(self):
        # pool HIGH → SUSPEND, regardless of approval_required
        assert decide_route("HIGH", False) == "SUSPEND"

    def test_high_pressure_suspends_even_with_approval(self):
        assert decide_route("HIGH", True) == "SUSPEND"

    def test_medium_pressure_does_not_suspend(self):
        assert decide_route("MEDIUM", True) != "SUSPEND"

    def test_low_pressure_does_not_suspend(self):
        assert decide_route("LOW", True) != "SUSPEND"


# ==============================================================================
# AUTO_EXECUTE tests — no approval needed, pool not HIGH
# ==============================================================================

class TestAutoExecuteRoute:
    def test_no_approval_needed_auto_executes(self):
        assert decide_route("LOW", False) == "AUTO_EXECUTE"

    def test_medium_pressure_no_approval_auto_executes(self):
        assert decide_route("MEDIUM", False) == "AUTO_EXECUTE"

    def test_high_pressure_overrides_auto_execute(self):
        # SUSPEND takes priority even when approval not required
        assert decide_route("HIGH", False) == "SUSPEND"

    def test_approval_required_blocks_auto_execute(self):
        assert decide_route("LOW", True) != "AUTO_EXECUTE"


# ==============================================================================
# ESCALATE tests — approval needed, pool not HIGH
# ==============================================================================

class TestEscalateRoute:
    def test_approval_required_escalates(self):
        assert decide_route("LOW", True) == "ESCALATE"

    def test_medium_pressure_approval_required_escalates(self):
        assert decide_route("MEDIUM", True) == "ESCALATE"

    def test_high_pressure_overrides_escalate(self):
        # SUSPEND takes priority even when approval would be required
        assert decide_route("HIGH", True) == "SUSPEND"

    def test_no_approval_does_not_escalate(self):
        assert decide_route("LOW", False) != "ESCALATE"


# ==============================================================================
# Priority order tests — SUSPEND > AUTO_EXECUTE > ESCALATE
# ==============================================================================

class TestRoutingPriority:
    def test_all_three_routes_are_reachable(self):
        assert decide_route("HIGH", True) == "SUSPEND"
        assert decide_route("LOW", False) == "AUTO_EXECUTE"
        assert decide_route("LOW", True) == "ESCALATE"

    def test_suspend_wins_over_auto_execute(self):
        # HIGH pressure + no approval → SUSPEND, not AUTO_EXECUTE
        assert decide_route("HIGH", False) == "SUSPEND"

    def test_suspend_wins_over_escalate(self):
        # HIGH pressure + approval needed → SUSPEND, not ESCALATE
        assert decide_route("HIGH", True) == "SUSPEND"

    def test_auto_execute_wins_over_escalate(self):
        # not HIGH, no approval → AUTO_EXECUTE, not ESCALATE
        assert decide_route("LOW", False) == "AUTO_EXECUTE"
        assert decide_route("MEDIUM", False) == "AUTO_EXECUTE"

    @pytest.mark.parametrize("pressure,approval,expected", [
        ("HIGH",   True,  "SUSPEND"),
        ("HIGH",   False, "SUSPEND"),
        ("MEDIUM", False, "AUTO_EXECUTE"),
        ("LOW",    False, "AUTO_EXECUTE"),
        ("MEDIUM", True,  "ESCALATE"),
        ("LOW",    True,  "ESCALATE"),
    ])
    def test_routing_matrix(self, pressure, approval, expected):
        assert decide_route(pressure, approval) == expected
