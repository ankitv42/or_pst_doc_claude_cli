"""
ORCA — evals/ragas_dataset.py
===============================
Curated (question, ground_truth) pairs for the RAGAS-style eval.

Each case is a question an agent might need answered from policy, plus the
KNOWN-CORRECT answer (ground_truth). The eval retrieves real context, has the
agent model answer, then the judge scores faithfulness / recall / precision /
relevance against these.

The ground_truth values come from the verified ORCA policy (the same facts you
saw in peek.py output and in the KT doc). Keep this set SMALL (5-8) — each case
makes several judge calls, and Groq's free tier rate-limits.

The optional category/abc_class/urgency/event_name fields steer which context
the retriever pulls for that question.
"""

RAGAS_CASES = [
    {
        "id": "RG-CP003-LIMIT",
        "question": "What is the auto-approve limit for the CP003 Expedite and Air Freight pool?",
        "ground_truth": "The CP003 auto-approve limit is AED 20,000. Orders above it require approval.",
        "category": "Grocery",
        "abc_class": "A",
        "urgency": "CRITICAL",
    },
    {
        "id": "RG-CLASSA-OPTIONB",
        "question": "For a Class A SKU, is Option B (partial distribution) ever allowed?",
        "ground_truth": "No. Option B is NEVER permitted for Class A SKUs; Class A requires full distribution to all affected stores.",
        "category": "Grocery",
        "abc_class": "A",
        "urgency": "HIGH",
    },
    {
        "id": "RG-RAMADAN-UPLIFT",
        "question": "What is the demand uplift and planning lead time for Ramadan 2025?",
        "ground_truth": "Ramadan 2025 has a 180% uplift (2.8x factor) and a 60-day planning lead, affecting Grocery, Dates, and Beverages.",
        "category": "Grocery",
        "abc_class": "B",
        "urgency": "HIGH",
        "event_name": "Ramadan",
    },
    {
        "id": "RG-PENALTY-RULE",
        "question": "When is the lead_time_penalty of -20 applied in Agent 3 scoring?",
        "ground_truth": "The -20 lead_time_penalty applies only when urgency is CRITICAL AND the option's lead_time_days exceeds 30. It does not apply for HIGH urgency.",
        "category": "Electronics",
        "abc_class": "A",
        "urgency": "CRITICAL",
    },
    {
        "id": "RG-SUSPEND-RULE",
        "question": "Under what condition is an order SUSPENDED instead of executed or escalated?",
        "ground_truth": "An order is SUSPENDED when the capital pool pressure flag is HIGH (or budget is below the minimum viable order). Check CP007 before suspending.",
        "category": "Grocery",
        "abc_class": "B",
        "urgency": "HIGH",
    },
]