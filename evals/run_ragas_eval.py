"""
ORCA — evals/run_ragas_eval.py
================================
RAGAS-STYLE metrics, computed with your Groq judge (NO ragas library).

WHY NOT THE RAGAS LIBRARY:
    The `ragas` package hard-imports a Vertex AI class that clashes with the
    LangChain version this repo's agents need. It could not be installed
    without risking the agent pipeline. So we compute the SAME four metrics,
    with the SAME definitions, using the Groq judge directly. The metric is
    what matters, not the library.

THE FOUR METRICS (standard RAG-eval definitions):
    faithfulness      : of the claims in the answer, what fraction are supported
                        by the retrieved context? (catches hallucination)
    context_recall    : of the facts in the ground-truth answer, what fraction
                        are present in the retrieved context? (the silent-failure metric)
    context_precision : of the retrieved context, how relevant is it to the question?
    answer_relevance  : does the answer actually address the question asked?

Each is scored 0.0-1.0 by the judge (llama-3.3-70b), then compared to a threshold.

DATA SOURCE:
    A small curated set of (question, ground_truth) pairs in ragas_dataset.py.
    For each, we retrieve real context from the live retriever, generate a real
    answer with the AGENT model (llama-3.1-8b via your get_llm), then judge it.

RUN (from repo root):
    python evals/run_ragas_eval.py
    python evals/run_ragas_eval.py --limit 3     # fewer cases (avoid rate limits)
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if os.path.exists(r"C:/lit"):
    sys.path.append(r"C:/lit")

from langchain_groq import ChatGroq
from docs.rag.retriever import get_retriever
from evals.ragas_dataset import RAGAS_CASES

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

JUDGE_MODEL = "llama-3.3-70b-versatile"   # strong judge
AGENT_MODEL = "llama-3.1-8b-instant"      # same model the agents use

# RAGAS-style thresholds (the ones you wanted)
THRESHOLDS = {
    "faithfulness":      0.80,
    "context_recall":    0.75,
    "context_precision": 0.70,
    "answer_relevance":  0.75,
}


def get_judge():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY not set in .env")
    return ChatGroq(model=JUDGE_MODEL, api_key=key, temperature=0)


def get_agent_model():
    key = os.getenv("GROQ_API_KEY")
    return ChatGroq(model=AGENT_MODEL, api_key=key, temperature=0)


def ask_judge_for_score(judge, instruction):
    """Ask the judge for a single 0.0-1.0 number. Returns float or None."""
    prompt = (
        instruction
        + "\n\nRespond with ONLY a single number between 0.0 and 1.0, nothing else."
    )
    try:
        resp = judge.invoke(prompt)
        text = resp.content.strip()
        # grab the first number-looking token
        for token in text.replace("\n", " ").split():
            try:
                val = float(token)
                if 0.0 <= val <= 1.0:
                    return val
            except ValueError:
                continue
        return None
    except Exception:
        return None


def metric_faithfulness(judge, answer, context):
    return ask_judge_for_score(judge,
        f"""Measure FAITHFULNESS. Of the factual claims in the ANSWER, what fraction
are directly supported by the CONTEXT? 1.0 = every claim supported; 0.0 = none.

CONTEXT:
{context}

ANSWER:
{answer}""")


def metric_context_recall(judge, ground_truth, context):
    return ask_judge_for_score(judge,
        f"""Measure CONTEXT RECALL. Of the facts stated in the GROUND TRUTH answer,
what fraction are present in the CONTEXT? 1.0 = all facts present; 0.0 = none.

GROUND TRUTH:
{ground_truth}

CONTEXT:
{context}""")


def metric_context_precision(judge, question, context):
    return ask_judge_for_score(judge,
        f"""Measure CONTEXT PRECISION. How relevant is the CONTEXT to the QUESTION?
1.0 = all of it is relevant; 0.0 = it is mostly irrelevant noise.

QUESTION:
{question}

CONTEXT:
{context}""")


def metric_answer_relevance(judge, question, answer):
    return ask_judge_for_score(judge,
        f"""Measure ANSWER RELEVANCE. Does the ANSWER directly address the QUESTION?
1.0 = fully on-point; 0.0 = does not answer it.

QUESTION:
{question}

ANSWER:
{answer}""")


def generate_answer(agent_model, retriever, case):
    """Retrieve real context and have the AGENT model answer the question."""
    # use a broad retrieval for the question (agent1 path is a reasonable default)
    context = retriever.query_for_agent1(
        category=case.get("category", "Grocery"),
        abc_class=case.get("abc_class", "B"),
        urgency=case.get("urgency", "HIGH"),
        event_name=case.get("event_name"),
    )
    prompt = (
        "You are an inventory planning assistant. Using ONLY the policy context "
        "below, answer the question concisely.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {case['question']}\n\nANSWER:"
    )
    resp = agent_model.invoke(prompt)
    return resp.content, context


def main():
    parser = argparse.ArgumentParser(description="ORCA RAGAS-style eval (Groq-native)")
    parser.add_argument("--limit", type=int, default=len(RAGAS_CASES),
                        help="how many cases to run")
    args = parser.parse_args()

    retriever = get_retriever()
    if not retriever.is_available():
        print("RAG not available — run: python docs/rag/ingest.py --reset")
        sys.exit(2)

    judge = get_judge()
    agent_model = get_agent_model()
    cases = RAGAS_CASES[: args.limit]

    print("=" * 70)
    print(f"  ORCA RAGAS-STYLE EVAL (Groq-native) — {len(cases)} cases")
    print(f"  judge={JUDGE_MODEL}  agent={AGENT_MODEL}")
    print("=" * 70)

    totals = {m: [] for m in THRESHOLDS}
    case_records = []

    for case in cases:
        print(f"\n[{case['id']}] {case['question'][:60]}...")
        answer, context = generate_answer(agent_model, retriever, case)

        scores = {
            "faithfulness":      metric_faithfulness(judge, answer, context),
            "context_recall":    metric_context_recall(judge, case["ground_truth"], context),
            "context_precision": metric_context_precision(judge, case["question"], context),
            "answer_relevance":  metric_answer_relevance(judge, case["question"], answer),
        }
        for m, v in scores.items():
            if v is not None:
                totals[m].append(v)
            mark = "" if v is None else ("OK " if v >= THRESHOLDS[m] else "LOW")
            print(f"    {m:<20} {v}   {mark}")
        case_records.append({"id": case["id"], "scores": scores})
        time.sleep(0.5)

    # ── averages vs thresholds ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  AVERAGES vs THRESHOLDS")
    print("=" * 70)
    averages = {}
    for m in THRESHOLDS:
        vals = totals[m]
        avg = sum(vals) / len(vals) if vals else 0.0
        averages[m] = round(avg, 3)
        status = "PASS" if avg >= THRESHOLDS[m] else "FAIL"
        print(f"  {m:<20} {avg:.3f}   threshold {THRESHOLDS[m]}   {status}")

    summary = {
        "layer": "ragas_style",
        "judge_model": JUDGE_MODEL,
        "agent_model": AGENT_MODEL,
        "thresholds": THRESHOLDS,
        "averages": averages,
        "cases": case_records,
    }
    out = RESULTS_DIR / "ragas_latest.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Saved: {out}")


if __name__ == "__main__":
    main()