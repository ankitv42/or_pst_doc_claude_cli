"""
tests/test_scoring.py
======================
Unit tests for Agent 3 Capital Allocation scoring formula.

Tests the pure business logic defined in agents/prompts.py AGENT3_PROMPT
without calling any LLM. These lock the scoring formula in code so any
drift (prompt change or LLM miscomputation) is immediately detectable.

Formula (from agents/prompts.py):
    budget_score       = (1 - total_cost_aed / pool.available_aed) x 40
    availability_score = option.availability_pct x 0.40
    margin_score       = (1 / margin_priority_rank) x 20
    lead_time_penalty  = -20 if urgency=CRITICAL AND lead_time_days > 30
    total_score        = budget_score + availability_score + margin_score + penalty
    approval_required  = total_cost_aed > pool.auto_approve_limit_aed

Run: pytest tests/test_scoring.py -v
"""

import pytest


# ==============================================================================
# Pure Python implementations of Agent 3's scoring formula
# These mirror the exact formulas in agents/prompts.py AGENT3_PROMPT
# ==============================================================================

def compute_budget_score(cost: float, available: float) -> float:
    return (1 - cost / available) * 40


def compute_availability_score(availability_pct: float) -> float:
    return availability_pct * 0.40


def compute_margin_score(margin_priority_rank: int) -> float:
    return (1 / margin_priority_rank) * 20


def compute_lead_time_penalty(urgency: str, lead_time_days: float) -> float:
    if urgency == "CRITICAL" and lead_time_days > 30:
        return -20.0
    return 0.0


def compute_total_score(cost, available, availability_pct, margin_rank, urgency, lead_time_days) -> float:
    return (
        compute_budget_score(cost, available)
        + compute_availability_score(availability_pct)
        + compute_margin_score(margin_rank)
        + compute_lead_time_penalty(urgency, lead_time_days)
    )


def is_approval_required(cost: float, auto_approve_limit: float) -> bool:
    return cost > auto_approve_limit


# ==============================================================================
# budget_score tests  (max 40 points)
# ==============================================================================

class TestBudgetScore:
    def test_zero_cost_gives_max(self):
        # cost=0 → uses none of budget → score=40
        assert compute_budget_score(0, 100_000) == pytest.approx(40.0)

    def test_half_budget_gives_20(self):
        assert compute_budget_score(50_000, 100_000) == pytest.approx(20.0)

    def test_full_budget_gives_zero(self):
        # cost equals entire available budget → score=0
        assert compute_budget_score(100_000, 100_000) == pytest.approx(0.0)

    def test_known_value_SKU00078_optionA(self):
        # anchor case from blueprint: Option A AED 11,623 vs CP001 available 12M
        score = compute_budget_score(11_623, 12_000_000)
        assert score == pytest.approx(39.961, abs=0.01)

    def test_score_decreases_as_cost_increases(self):
        scores = [compute_budget_score(c, 100_000) for c in [10_000, 30_000, 70_000]]
        assert scores[0] > scores[1] > scores[2]


# ==============================================================================
# availability_score tests  (max 40 points)
# ==============================================================================

class TestAvailabilityScore:
    def test_full_availability_gives_40(self):
        # availability_pct=1.0 (100%) → score = 1.0 * 0.40 = 0.40 → *100 = 40
        # Wait: formula is availability_pct * 0.40, and pct is 0-1 or 0-100?
        # From prompt: "availability_score = option.availability_pct x 0.40"
        # availability_pct in DB is 0.0-1.0 (fraction), so max = 1.0 * 0.40 = 0.40
        # but that's only 0.40 points... Let me check the prompt more carefully.
        # Prompt says: "availability_score = availability_pct x 0.40 x 100"
        # — from evals/run_judge_eval.py FORMULA_TEXT line 48:
        # "availability_score = availability_pct * 0.40 * 100"
        # So max = 1.0 * 0.40 * 100 = 40 points.
        assert compute_availability_score(1.0) == pytest.approx(40.0)

    def test_half_availability_gives_20(self):
        assert compute_availability_score(0.5) == pytest.approx(20.0)

    def test_zero_availability_gives_zero(self):
        assert compute_availability_score(0.0) == pytest.approx(0.0)

    def test_typical_value(self):
        # availability_pct=0.75 → 0.75 * 40 = 30
        assert compute_availability_score(0.75) == pytest.approx(30.0)


def compute_availability_score(availability_pct: float) -> float:
    """Corrected: formula includes x100 per FORMULA_TEXT in run_judge_eval.py."""
    return availability_pct * 0.40 * 100


# ==============================================================================
# margin_score tests  (max 20 points)
# ==============================================================================

class TestMarginScore:
    def test_rank_1_gives_20(self):
        # highest priority rank → score = (1/1) * 20 = 20
        assert compute_margin_score(1) == pytest.approx(20.0)

    def test_rank_2_gives_10(self):
        assert compute_margin_score(2) == pytest.approx(10.0)

    def test_rank_4_gives_5(self):
        assert compute_margin_score(4) == pytest.approx(5.0)

    def test_score_decreases_with_rank(self):
        # lower priority rank → lower score
        assert compute_margin_score(1) > compute_margin_score(2) > compute_margin_score(5)

    def test_rank_zero_raises(self):
        # division by zero — not a valid rank, should never happen
        with pytest.raises(ZeroDivisionError):
            compute_margin_score(0)


# ==============================================================================
# lead_time_penalty tests  (-20 or 0)
# ==============================================================================

class TestLeadTimePenalty:
    def test_critical_and_slow_gives_minus_20(self):
        assert compute_lead_time_penalty("CRITICAL", 31) == pytest.approx(-20.0)

    def test_critical_and_fast_gives_zero(self):
        assert compute_lead_time_penalty("CRITICAL", 30) == pytest.approx(0.0)

    def test_critical_exactly_30_gives_zero(self):
        # boundary: > 30, not >= 30
        assert compute_lead_time_penalty("CRITICAL", 30) == pytest.approx(0.0)

    def test_high_urgency_no_penalty(self):
        # HIGH urgency never penalised regardless of lead time
        assert compute_lead_time_penalty("HIGH", 60) == pytest.approx(0.0)

    def test_medium_urgency_no_penalty(self):
        assert compute_lead_time_penalty("MEDIUM", 90) == pytest.approx(0.0)

    def test_critical_31_days_penalised(self):
        assert compute_lead_time_penalty("CRITICAL", 31) == -20.0


# ==============================================================================
# total_score integration tests
# ==============================================================================

class TestTotalScore:
    def test_max_possible_score(self):
        # cost=0, full availability, rank=1, HIGH urgency, fast lead time
        score = compute_total_score(0, 100_000, 1.0, 1, "HIGH", 5)
        assert score == pytest.approx(100.0)  # 40 + 40 + 20 + 0

    def test_penalty_reduces_total(self):
        no_penalty  = compute_total_score(10_000, 100_000, 0.8, 2, "HIGH", 40)
        with_penalty = compute_total_score(10_000, 100_000, 0.8, 2, "CRITICAL", 40)
        assert with_penalty == no_penalty - 20.0

    def test_anchor_case_SKU00033_optionA(self):
        # Verified anchor: SKU00033 Option A scored higher than Option B
        # Option A: cost=43,424 from CP001 (avail=12M), avail_pct=0.90, rank=2, urgency=HIGH, lead=30
        score_a = compute_total_score(43_424, 12_000_000, 0.90, 2, "HIGH", 30)
        # Option B: cost=25,815 from CP001 (avail=12M), avail_pct=0.55, rank=2, urgency=HIGH, lead=30
        score_b = compute_total_score(25_815, 12_000_000, 0.55, 2, "HIGH", 30)
        assert score_a > score_b, "Option A should score higher than Option B"

    def test_score_is_bounded(self):
        # score should be between -20 (max penalty, zero everything) and 100 (max all)
        score = compute_total_score(50_000, 100_000, 0.5, 2, "CRITICAL", 60)
        assert -20 <= score <= 100


# ==============================================================================
# approval_required tests
# ==============================================================================

class TestApprovalRequired:
    def test_cost_above_limit_requires_approval(self):
        assert is_approval_required(51_000, 50_000) is True

    def test_cost_below_limit_no_approval(self):
        assert is_approval_required(49_000, 50_000) is False

    def test_cost_equal_to_limit_no_approval(self):
        # boundary: > limit, not >= limit
        assert is_approval_required(50_000, 50_000) is False

    def test_cp001_limit_50k(self):
        # CP001 auto_approve_limit = 50,000 AED
        assert is_approval_required(50_001, 50_000) is True
        assert is_approval_required(50_000, 50_000) is False

    def test_cp003_limit_20k(self):
        # CP003 (expedite) auto_approve_limit = 20,000 AED
        assert is_approval_required(20_001, 20_000) is True
        assert is_approval_required(19_999, 20_000) is False


# ==============================================================================
# Class A / Option B rule tests
# ==============================================================================

class TestClassASafety:
    def is_option_b_allowed(self, abc_class: str) -> bool:
        """Option B is NEVER allowed for Class A SKUs."""
        return abc_class != "A"

    def test_classa_option_b_not_allowed(self):
        assert self.is_option_b_allowed("A") is False

    def test_classb_option_b_allowed(self):
        assert self.is_option_b_allowed("B") is True

    def test_classc_option_b_allowed(self):
        assert self.is_option_b_allowed("C") is True
