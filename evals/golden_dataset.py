"""
ORCA — evals/golden_dataset.py
================================
The golden dataset = hand-written answer key for retrieval evaluation.

Each case says: for THIS situation (agent + kwargs), the returned context
string MUST contain these facts (recall) and must NOT contain wrong ones
(precision).

GROUNDING RULE: every must_contain phrase should be copied from REAL retriever
output (seen via peek.py), never written from memory. The 3 cases marked
[VERIFIED] were confirmed against the live retriever (3/3 passing).

The cases marked [CALIBRATE] are reasonable first guesses — when you run the
eval, some may FAIL only because the exact wording differs in your docs. That
is normal: open peek.py for that situation, read the real text, and adjust the
must_contain words to match. Leave a one-line comment when you change one.
"""

GOLDEN_CASES = [

    # ════════ VERIFIED CASES (confirmed 3/3 against live retriever) ════════

    # [VERIFIED] Agent 2 — Hindustan FMCG cannot expedite -> must escalate
    {
        "id": "A2-HINDUSTAN-NOEXP",
        "agent": "agent2",
        "kwargs": {
            "category": "Personal Care",
            "supplier_name": "Hindustan FMCG",
            "lead_time_too_late": True,
        },
        "must_contain": ["No expedite", "escalate", "Hindustan FMCG"],
        # NOTE: we do NOT forbid other supplier names — the category->supplier->pool
        # reference table legitimately lists several suppliers (calibration).
        "must_not_contain": [],
    },

    # [VERIFIED] Agent 3 — CP003 pool limit + scoring formula
    {
        "id": "A3-CP003-SCORING",
        "agent": "agent3",
        "kwargs": {
            "category": "Grocery",
            "urgency": "CRITICAL",
            "abc_class": "A",
            "approval_pool": "CP003",
        },
        "must_contain": ["CP003", "20,000", "budget_score", "availability_score"],
        "must_not_contain": [],
    },

    # [VERIFIED] Agent 1 — Ramadan uplift + Class A "Option B NEVER" rule
    {
        "id": "A1-RAMADAN-CLASSA",
        "agent": "agent1",
        "kwargs": {
            "category": "Grocery",
            "abc_class": "A",
            "event_name": "Ramadan",
        },
        "must_contain": ["Ramadan", "180%", "NEVER"],
        "must_not_contain": [],
    },

    # ════════ CALIBRATE CASES (first guesses — tune wording after first run) ════════

    # [CALIBRATE] Agent 1 — Back to School / Electronics event planning
    {
        "id": "A1-BACK-TO-SCHOOL",
        "agent": "agent1",
        "kwargs": {
            "category": "Electronics",
            "abc_class": "B",
            "urgency": "HIGH",
            "event_name": "Back to School",
        },
        "must_contain": ["Back to School", "Electronics"],
        "must_not_contain": [],
    },

    # [CALIBRATE] Agent 1 — ABC class ordering rules surface for Class C
    {
        "id": "A1-CLASSC-RULES",
        "agent": "agent1",
        "kwargs": {
            "category": "Grocery",
            "abc_class": "C",
            "urgency": "MEDIUM",
        },
        "must_contain": ["C (Low Value)", "Ordering Rules"],
        "must_not_contain": [],
    },

    # [CALIBRATE] Agent 2 — Option building rules (A/B/C) present
    {
        "id": "A2-OPTION-RULES",
        "agent": "agent2",
        "kwargs": {
            "category": "Grocery",
            "supplier_name": "Al Rawdah Foods",
            "lead_time_too_late": False,
            "abc_class": "A",
            "urgency": "HIGH",
        },
        "must_contain": ["Option Building", "Standard Replenishment"],
        "must_not_contain": [],
    },

    # [CALIBRATE] Agent 2 — Class A means Option B not allowed (Agent 2 view)
    {
        "id": "A2-CLASSA-NO-OPTIONB",
        "agent": "agent2",
        "kwargs": {
            "category": "Grocery",
            "supplier_name": "Al Rawdah Foods",
            "lead_time_too_late": False,
            "abc_class": "A",
            "urgency": "HIGH",
        },
        "must_contain": ["Not for Class A"],
        "must_not_contain": [],
    },

    # [CALIBRATE] Agent 3 — approval routing rules (AUTO_EXECUTE/ESCALATE/SUSPEND)
    {
        "id": "A3-ROUTING-RULES",
        "agent": "agent3",
        "kwargs": {
            "category": "Grocery",
            "urgency": "HIGH",
            "abc_class": "B",
            "approval_pool": "CP001",
        },
        "must_contain": ["AUTO_EXECUTE", "ESCALATE", "SUSPEND"],
        "must_not_contain": [],
    },

    # [CALIBRATE] Agent 3 — CP001 pool details
    {
        "id": "A3-CP001-POOL",
        "agent": "agent3",
        "kwargs": {
            "category": "Grocery",
            "urgency": "HIGH",
            "abc_class": "B",
            "approval_pool": "CP001",
        },
        "must_contain": ["CP001", "50,000"],
        "must_not_contain": [],
    },

    # [CALIBRATE] Agent 3 — lead_time_penalty rule present
    {
        "id": "A3-PENALTY-RULE",
        "agent": "agent3",
        "kwargs": {
            "category": "Electronics",
            "urgency": "CRITICAL",
            "abc_class": "A",
            "approval_pool": "CP003",
        },
        "must_contain": ["Penalty", "CRITICAL"],
        "must_not_contain": [],
    },

    # [CALIBRATE] Agent 4 — ESCALATE briefing format / approval routing
    {
        "id": "A4-ESCALATE-BRIEF",
        "agent": "agent4",
        "kwargs": {
            "category": "Grocery",
            "supplier_name": "Al Rawdah Foods",
            "route": "ESCALATE",
        },
        "must_contain": ["ESCALATE"],
        "must_not_contain": [],
    },

    # [CALIBRATE] Agent 4 — contact resolution rule (use DB, never hardcode)
    {
        "id": "A4-CONTACT-RULE",
        "agent": "agent4",
        "kwargs": {
            "category": "Grocery",
            "supplier_name": "Al Rawdah Foods",
            "route": "ESCALATE",
        },
        "must_contain": ["contact"],
        "must_not_contain": [],
    },
]


if __name__ == "__main__":
    print(f"Golden dataset has {len(GOLDEN_CASES)} test cases:")
    by_agent = {}
    for c in GOLDEN_CASES:
        by_agent[c["agent"]] = by_agent.get(c["agent"], 0) + 1
    for a in sorted(by_agent):
        print(f"  {a}: {by_agent[a]} cases")
    print(f"  total: {len(GOLDEN_CASES)}")