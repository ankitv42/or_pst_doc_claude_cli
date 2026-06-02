"""
ORCA — evals/run_judge_eval.py
================================
LAYER 2 — LLM-as-judge over real saved decisions.

Reads saved pipeline decisions from db/orca.db and asks a STRONGER model
(llama-3.3-70b) to grade each one 1-5 on FOUR criteria:

  1. consistency      : do scored decision, chosen option, cost, and briefing agree?
  2. hitl_accuracy     : was human approval triggered exactly when cost > auto-approve limit?
  3. scoring_accuracy  : did Agent 3 apply the scoring formula correctly?
  4. classa_safety     : was Option B correctly NEVER used for a Class A SKU?

WHY A STRONGER JUDGE: agents run on llama-3.1-8b; a judge should be smarter,
so it runs on llama-3.3-70b. temperature=0 => deterministic scoring.

NOTE: a judge score is EVIDENCE, not absolute truth. Spot-check low scores by
hand (peek_db.py) before acting on them.

RUN (from repo root):
    python evals/run_judge_eval.py            # 10 most recent runs, all 4 criteria
    python evals/run_judge_eval.py --limit 5
    python evals/run_judge_eval.py --criterion consistency   # just one criterion
"""

import os
import sqlite3
import argparse
import time
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "db" / "orca.db"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

JUDGE_MODEL = "llama-3.3-70b-versatile"

# ── the scoring formula, restated so the judge can check Agent 3's math ─────
FORMULA_TEXT = """
budget_score       = (1 - cost / available_budget) * 40
availability_score = availability_pct * 0.40 * 100
margin_score       = (1 / margin_priority_rank) * 20
lead_time_penalty  = -20 ONLY IF urgency = CRITICAL AND lead_time_days > 30 (else 0)
total_score        = budget_score + availability_score + margin_score + lead_time_penalty
approval_required  = (cost > pool auto_approve_limit)
""".strip()

# ── the four criteria: each has a name + the rubric text given to the judge ─
CRITERIA = {
    "consistency": (
        "INTERNAL CONSISTENCY: do the scored decision, the chosen winning option, "
        "the cost, and the human briefing all agree with each other?\n"
        "5 = all fully consistent; 3 = one noticeable mismatch; "
        "1 = briefing names a different option or cost than the scored decision."
    ),
    "hitl_accuracy": (
        "HITL ACCURACY: was human approval triggered exactly when it should be? "
        "approval_required must be TRUE when cost exceeds the pool auto-approve limit, "
        "and the final status must reflect that (ESCALATED if approval needed, "
        "AUTO_EXECUTED only if below the limit).\n"
        "5 = routing perfectly matches the cost-vs-limit rule; "
        "1 = approved automatically despite exceeding the limit, or escalated needlessly."
    ),
    "scoring_accuracy": (
        "SCORING ACCURACY: did Agent 3 apply the scoring formula correctly?\n"
        f"The correct formula is:\n{FORMULA_TEXT}\n"
        "Check the scored_options numbers against this formula.\n"
        "5 = all components correct; 3 = one component off; 1 = formula clearly misapplied."
    ),
    "classa_safety": (
        "CLASS A SAFETY: for a Class A SKU, Option B (partial / profit-maximisation) "
        "must NEVER be the recommended/winning option — Class A requires full distribution.\n"
        "5 = Class A correctly never uses Option B (or SKU is not Class A, so N/A -> 5); "
        "1 = Option B was chosen for a Class A SKU."
    ),
}


def get_judge_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set in .env")
    return ChatGroq(model=JUDGE_MODEL, api_key=api_key, temperature=0)


def load_recent_runs(limit):
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM pipeline_log ORDER BY rowid DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def build_prompt(run, criterion_name, rubric):
    return f"""You are a senior QA reviewer for an autonomous retail inventory system.
Grade ONE decision on this single criterion:

{rubric}

DECISION TO GRADE:
SKU: {run['sku_id']}
FINAL STATUS: {run['final_status']}
DEMAND SUMMARY (Agent 1): {run['demand_summary']}
OPTIONS PACKAGE (Agent 2): {run['options_package']}
CAPITAL DECISION (Agent 3): {run['capital_decision']}
HUMAN BRIEFING (Agent 4): {run['hitl_briefing']}

Respond in EXACTLY this format, nothing else:
SCORE: <number 1-5>
REASON: <one sentence>
"""


def parse_score(text):
    for line in text.splitlines():
        if line.strip().upper().startswith("SCORE:"):
            try:
                return int(line.split(":", 1)[1].strip()[0])
            except (ValueError, IndexError):
                return None
    return None


def parse_reason(text):
    for line in text.splitlines():
        if line.strip().upper().startswith("REASON:"):
            return line.split(":", 1)[1].strip()
    return ""


def main():
    parser = argparse.ArgumentParser(description="ORCA Layer 2 LLM-as-judge")
    parser.add_argument("--limit", type=int, default=10, help="how many recent runs (default 10)")
    parser.add_argument("--criterion", choices=list(CRITERIA.keys()),
                        help="grade only ONE criterion (default: all four)")
    args = parser.parse_args()

    runs = load_recent_runs(args.limit)
    if not runs:
        print("No saved runs. Click Analyse on a few SKUs in the dashboard first.")
        return

    judge = get_judge_llm()
    criteria_to_run = [args.criterion] if args.criterion else list(CRITERIA.keys())

    print(f"Grading {len(runs)} runs on {len(criteria_to_run)} criteria "
          f"(judge = {JUDGE_MODEL})")
    print("=" * 78)

    # per-criterion score lists, and a per-run record
    by_criterion = {c: [] for c in criteria_to_run}
    run_records = []

    for run in runs:
        record = {"sku_id": run["sku_id"], "final_status": run["final_status"], "scores": {}}
        line_parts = [f"{run['sku_id']:<10}"]

        for crit in criteria_to_run:
            prompt = build_prompt(run, crit, CRITERIA[crit])
            try:
                resp = judge.invoke(prompt)
                score = parse_score(resp.content)
                reason = parse_reason(resp.content)
            except Exception as e:
                score, reason = None, f"ERROR: {e}"

            by_criterion[crit].append(score)
            record["scores"][crit] = {"score": score, "reason": reason}
            line_parts.append(f"{crit[:9]}={score}")
            time.sleep(0.4)   # gentle on the Groq rate limit

        run_records.append(record)
        print("  " + "  ".join(line_parts))

    # ── summary per criterion ────────────────────────────────────────────────
    print("=" * 78)
    print("SUMMARY (average score per criterion, 1-5):")
    criterion_avgs = {}
    for crit in criteria_to_run:
        valid = [s for s in by_criterion[crit] if s is not None]
        avg = sum(valid) / len(valid) if valid else 0
        low = sum(1 for s in valid if s <= 2)
        criterion_avgs[crit] = round(avg, 2)
        print(f"  {crit:<18} avg={avg:.1f}/5   low(<=2)={low}/{len(valid)}")

    # write JSON for the composite scorer
    summary = {
        "layer": "judge",
        "judge_model": JUDGE_MODEL,
        "runs_graded": len(runs),
        "criteria_avgs": criterion_avgs,
        "runs": run_records,
    }
    out = RESULTS_DIR / "judge_latest.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()