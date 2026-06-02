"""
ORCA — evals/run_retrieval_eval.py
====================================
LAYER 1 — Retrieval evaluation (free, no API key).

For each golden case it calls the REAL retriever method the agents use and
checks the returned context string:
  recall    : did the expected facts appear?   (must_contain)
  precision : did forbidden facts leak in?      (must_not_contain)

Writes a JSON result file to evals/results/ so the composite scorer can read it.

RUN (from repo root):
    python evals/run_retrieval_eval.py
    python evals/run_retrieval_eval.py --ci      # exit 1 if below threshold
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if os.path.exists(r"C:/lit"):
    sys.path.append(r"C:/lit")

from docs.rag.retriever import get_retriever
from evals.golden_dataset import GOLDEN_CASES

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CI_MIN_PASS_RATE = 0.70          # at least 70% of cases must pass for CI


def call_retriever(retriever, case):
    methods = {
        "agent1": retriever.query_for_agent1,
        "agent2": retriever.query_for_agent2,
        "agent3": retriever.query_for_agent3,
        "agent4": retriever.query_for_agent4,
    }
    agent = case["agent"]
    if agent not in methods:
        raise ValueError(f"Unknown agent: {agent}")
    return methods[agent](**case["kwargs"])


def score_one_case(context, case):
    ctx = (context or "").lower()
    found = [w for w in case["must_contain"] if w.lower() in ctx]
    missing = [w for w in case["must_contain"] if w.lower() not in ctx]
    leaked = [w for w in case["must_not_contain"] if w.lower() in ctx]
    passed = (len(missing) == 0) and (len(leaked) == 0)
    coverage = len(found) / max(len(case["must_contain"]), 1)
    return passed, found, missing, leaked, coverage


def main():
    parser = argparse.ArgumentParser(description="ORCA Layer 1 retrieval eval")
    parser.add_argument("--ci", action="store_true", help="exit 1 if below threshold")
    args = parser.parse_args()

    retriever = get_retriever()
    if not retriever.is_available():
        print("RAG not available — run: python docs/rag/ingest.py --reset")
        sys.exit(2)

    print("=" * 64)
    print("  ORCA RETRIEVAL EVAL  (Layer 1)")
    print("=" * 64)

    results = []
    pass_count = 0
    total_leaks = 0

    for case in GOLDEN_CASES:
        try:
            context = call_retriever(retriever, case)
        except Exception as e:
            print(f"\n[{case['id']}]  ERROR: {e}")
            results.append({"id": case["id"], "passed": False, "error": str(e)})
            continue

        passed, found, missing, leaked, coverage = score_one_case(context, case)
        if passed:
            pass_count += 1
        total_leaks += len(leaked)

        status = "PASS" if passed else "FAIL"
        print(f"\n[{case['id']}]  {status}   coverage={coverage:.0%}")
        print(f"   found   : {found}")
        if missing:
            print(f"   MISSING : {missing}")
        if leaked:
            print(f"   LEAKED  : {leaked}")

        results.append({
            "id": case["id"],
            "agent": case["agent"],
            "passed": passed,
            "coverage": round(coverage, 3),
            "found": found,
            "missing": missing,
            "leaked": leaked,
        })

    scored = [r for r in results if "error" not in r]
    total = len(GOLDEN_CASES)
    pass_rate = pass_count / max(total, 1)
    avg_cov = sum(r["coverage"] for r in scored) / max(len(scored), 1)

    print("\n" + "=" * 64)
    print(f"  RESULT: {pass_count}/{total} passed  (pass rate {pass_rate:.0%})")
    print(f"  Avg keyword coverage: {avg_cov:.0%}   |   keyword leaks: {total_leaks}")
    print("=" * 64)

    # write JSON for the composite scorer
    summary = {
        "layer": "retrieval",
        "timestamp": datetime.now().isoformat(),
        "pass_rate": round(pass_rate, 3),
        "avg_coverage": round(avg_cov, 3),
        "keyword_leaks": total_leaks,
        "total_cases": total,
        "passed": pass_count,
        "cases": results,
    }
    out = RESULTS_DIR / "retrieval_latest.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Saved: {out}")

    if args.ci:
        gate_ok = (pass_rate >= CI_MIN_PASS_RATE) and (total_leaks == 0)
        if not gate_ok:
            print(f"\n  CI GATE FAILED (pass {pass_rate:.0%} < {CI_MIN_PASS_RATE:.0%} or leaks {total_leaks})")
            sys.exit(1)
        print("\n  CI GATE PASSED")


if __name__ == "__main__":
    main()