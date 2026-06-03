"""
ORCA — evals/composite_score.py
=================================
Combines all eval layers into ONE composite score and a CI gate decision.

It reads the JSON result files written by the other runners:
    results/retrieval_latest.json   (Layer 1)
    results/ragas_latest.json       (RAGAS-style metrics)
    results/judge_latest.json       (Layer 2, optional — for display)

COMPOSITE WEIGHTS (the ones you specified):
    retrieval pass rate    : 40%   (the silent-failure zone)
    context_recall         : 30%   (most critical RAG metric)
    faithfulness           : 20%
    answer_relevance       : 10%

CI GATE: composite must be >= CI_FAIL_THRESHOLD (default 0.75) to pass.

RUN (from repo root, AFTER running the other evals):
    python evals/run_retrieval_eval.py
    python evals/run_ragas_eval.py
    python evals/composite_score.py
    python evals/composite_score.py --ci      # exit 1 if composite below threshold
"""

import sys
import json
import argparse
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"

WEIGHTS = {
    "retrieval_pass_rate": 0.40,
    "context_recall":      0.30,
    "faithfulness":        0.20,
    "answer_relevance":    0.10,
}
CI_FAIL_THRESHOLD = 0.75


def load(name):
    path = RESULTS_DIR / name
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="ORCA composite eval score")
    parser.add_argument("--ci", action="store_true", help="exit 1 if composite below threshold")
    args = parser.parse_args()

    retrieval = load("retrieval_latest.json")
    ragas = load("ragas_latest.json")
    judge = load("judge_latest.json")

    print("=" * 64)
    print("  ORCA COMPOSITE EVAL SCORE")
    print("=" * 64)

    if retrieval is None:
        print("\n  ERROR: retrieval_latest.json missing. Run first:")
        print("    python evals/run_retrieval_eval.py")
        sys.exit(2)

    ragas_available = ragas is not None

    if not ragas_available:
        print("\n  NOTE: ragas_latest.json not found — running in retrieval-only mode.")
        print("  Composite will be computed from retrieval pass rate only (weighted 100%).")
        print("  Run python evals/run_ragas_eval.py to include RAGAS metrics.")

    # gather the component values — RAGAS metrics default to None when unavailable
    retrieval_pass   = retrieval.get("pass_rate", 0.0)
    ragas_avgs       = ragas.get("averages", {}) if ragas_available else {}
    context_recall   = ragas_avgs.get("context_recall")
    faithfulness     = ragas_avgs.get("faithfulness")
    answer_relevance = ragas_avgs.get("answer_relevance")

    # compute composite — skip components with no data, re-normalise weights
    available = {"retrieval_pass_rate": retrieval_pass}
    if context_recall   is not None: available["context_recall"]   = context_recall
    if faithfulness     is not None: available["faithfulness"]     = faithfulness
    if answer_relevance is not None: available["answer_relevance"] = answer_relevance

    total_weight = sum(WEIGHTS[k] for k in available)
    composite = sum(available[k] * WEIGHTS[k] / total_weight for k in available)

    components = {
        "retrieval_pass_rate": retrieval_pass,
        "context_recall":      context_recall,
        "faithfulness":        faithfulness,
        "answer_relevance":    answer_relevance,
    }

    print("\n  Component scores (and weights):")
    for name, weight in WEIGHTS.items():
        val = components[name]
        if val is None:
            print(f"    {name:<22} N/A   (not run)")
        else:
            eff_weight = weight / total_weight
            contribution = val * eff_weight
            print(f"    {name:<22} {val:.3f}  x {eff_weight:.0%}  = {contribution:.3f}")

    print("\n  " + "-" * 40)
    print(f"  COMPOSITE SCORE: {composite:.3f}")

    # show RAGAS-style precision too (not weighted, but informative)
    cp = ragas_avgs.get("context_precision")
    if cp is not None:
        print(f"  (context_precision, unweighted: {cp:.3f})")

    # show judge criteria averages if available
    if judge and "criteria_avgs" in judge:
        print("\n  Judge criteria (1-5 scale, informative):")
        for crit, avg in judge["criteria_avgs"].items():
            print(f"    {crit:<18} {avg}/5")

    gate_pass = composite >= CI_FAIL_THRESHOLD
    print("\n" + "=" * 64)
    print(f"  CI GATE: {'PASS' if gate_pass else 'FAIL'}  "
          f"(composite {composite:.3f} vs threshold {CI_FAIL_THRESHOLD})")
    print("=" * 64)

    # save composite
    out = RESULTS_DIR / "composite_latest.json"
    with open(out, "w") as f:
        json.dump({
            "components": {k: v for k, v in components.items()},
            "weights": WEIGHTS,
            "ragas_available": ragas_available,
            "composite": round(composite, 3),
            "threshold": CI_FAIL_THRESHOLD,
            "gate_pass": gate_pass,
        }, f, indent=2)
    print(f"  Saved: {out}")

    if args.ci and not gate_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()