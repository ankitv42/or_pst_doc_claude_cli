"""
ORCA — evals/eval_main.py
===========================
ONE command to run the whole eval suite in order:

    1. Layer 1   — retrieval eval        (run_retrieval_eval.py)
    2. RAGAS     — RAGAS-style metrics   (run_ragas_eval.py)
    3. Layer 2   — LLM-as-judge          (run_judge_eval.py)
    4. Composite — weighted score + gate (composite_score.py)

Each step writes its own JSON to evals/results/; the composite reads them.

RUN (from repo root):
    python evals/eval_main.py                 # full suite, sensible default limits
    python evals/eval_main.py --ragas-limit 3 --judge-limit 5
    python evals/eval_main.py --skip-ragas    # skip the slow Groq RAGAS step
    python evals/eval_main.py --skip-judge    # skip the judge step
    python evals/eval_main.py --ci            # exit 1 if the composite gate fails

NOTE: steps 2 and 3 call the Groq judge (many calls) and are the slow part.
Use --ragas-limit / --judge-limit to keep them small while iterating.
"""

import sys
import subprocess
import argparse
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable          # use the same interpreter that launched this


def run_step(title, args):
    """Run one eval script as a subprocess and report whether it succeeded."""
    print("\n" + "#" * 70)
    print(f"#  {title}")
    print("#" * 70)
    result = subprocess.run([PYTHON] + args)
    ok = result.returncode == 0
    print(f"\n--> {title}: {'OK' if ok else 'returned exit code ' + str(result.returncode)}")
    return ok


def main():
    parser = argparse.ArgumentParser(description="Run the full ORCA eval suite")
    parser.add_argument("--ragas-limit", type=int, default=3,
                        help="how many RAGAS cases to run (default 3)")
    parser.add_argument("--judge-limit", type=int, default=5,
                        help="how many saved runs the judge grades (default 5)")
    parser.add_argument("--skip-ragas", action="store_true", help="skip the RAGAS-style step")
    parser.add_argument("--skip-judge", action="store_true", help="skip the LLM-judge step")
    parser.add_argument("--ci", action="store_true",
                        help="exit 1 if the composite gate fails")
    args = parser.parse_args()

    print("=" * 70)
    print("  ORCA EVAL SUITE — full run")
    print("=" * 70)

    statuses = {}

    # 1. retrieval (free, fast) — always runs
    statuses["retrieval"] = run_step(
        "STEP 1/4 — retrieval eval",
        [str(EVALS_DIR / "run_retrieval_eval.py")],
    )

    # 2. RAGAS-style (Groq, slow) — optional
    if args.skip_ragas:
        print("\n(skipping RAGAS-style step)")
    else:
        statuses["ragas"] = run_step(
            "STEP 2/4 — RAGAS-style eval",
            [str(EVALS_DIR / "run_ragas_eval.py"), "--limit", str(args.ragas_limit)],
        )

    # 3. LLM-judge (Groq, slow) — optional
    if args.skip_judge:
        print("\n(skipping LLM-judge step)")
    else:
        statuses["judge"] = run_step(
            "STEP 3/4 — LLM-as-judge",
            [str(EVALS_DIR / "run_judge_eval.py"), "--limit", str(args.judge_limit)],
        )

    # 4. composite (reads the JSON the others wrote)
    composite_args = [str(EVALS_DIR / "composite_score.py")]
    if args.ci:
        composite_args.append("--ci")
    statuses["composite"] = run_step("STEP 4/4 — composite score + gate", composite_args)

    # ── final recap ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  SUITE COMPLETE — step status")
    print("=" * 70)
    for step, ok in statuses.items():
        print(f"  {step:<12} {'OK' if ok else 'FAILED / gate not met'}")
    print("\n  Detailed JSON results are in evals/results/")

    # in CI mode, fail the whole run if the composite gate failed
    if args.ci and not statuses.get("composite", False):
        sys.exit(1)


if __name__ == "__main__":
    main()