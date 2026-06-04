# ADR-003: Native RAGAS-Style Metrics Over the RAGAS Library

**Status:** Accepted  
**Date:** 2026-05-28  
**Authors:** ORCA Engineering

---

## Context

ORCA needs to evaluate RAG quality across 4 dimensions — faithfulness, context recall, context precision, and answer relevance — to ensure agents are receiving policy knowledge that is accurate, complete, and relevant to their decisions.

The standard tool for this evaluation is the `ragas` Python library (`pip install ragas`), which implements these 4 metrics and is widely used in the LLM community. The initial plan was to use it directly.

**The RAGAS library could not be installed safely in this repository.**

The root cause is a hard import dependency conflict:

```
ragas → requires datasets → requires huggingface_hub >= 0.21
ragas → imports google.cloud.aiplatform (Vertex AI) at module load time
       ↓
       conflicts with langchain-core==1.4.0 which this repo requires
       ↓
       pip resolver: uninstalls langchain, pydantic, click to satisfy ragas
       ↓
       agents/graph.py: ImportError — LangGraph broken
```

In practice, every attempt to `pip install ragas` in the development environment caused the LangChain dependency tree to be partially uninstalled, breaking the 4-agent pipeline. The conflict is between ragas's pinned version of `langchain-community` and the `langchain-core` version required by LangGraph 1.1.10.

This was verified and documented in `learning/Evaluation/FINDINGS.md`. The `ragas` package remains half-installed in the virtual environment (visible in `pip list`) but is never imported — importing it at runtime crashes the process.

---

## Decision

Implement the **same 4 RAGAS metrics natively** using the Groq judge LLM (`llama-3.3-70b-versatile`) directly, without the RAGAS library. The metric definitions match the RAGAS paper exactly; only the execution engine differs.

```python
# evals/run_ragas_eval.py — native implementation

def metric_faithfulness(judge, answer, context, case_id=""):
    """
    Of the factual claims in the ANSWER, what fraction are directly
    supported by the CONTEXT? 1.0 = every claim supported; 0.0 = none.
    """
    return ask_judge_for_score(
        judge.with_config({"run_name": f"RAGAS-Judge-Faithfulness | {case_id}"}),
        f"Measure FAITHFULNESS...\nCONTEXT:\n{context}\nANSWER:\n{answer}"
    )

def metric_context_recall(judge, ground_truth, context, case_id=""):
    """Of the facts in GROUND TRUTH, what fraction are in the CONTEXT?"""
    ...

def metric_context_precision(judge, question, context, case_id=""):
    """How relevant is the CONTEXT to the QUESTION?"""
    ...

def metric_answer_relevance(judge, question, answer, case_id=""):
    """Does the ANSWER directly address the QUESTION?"""
    ...
```

Each metric is a single LLM call asking the judge for a score between 0.0 and 1.0. The judge is `llama-3.3-70b-versatile` — a stronger model than the agents (`llama-3.1-8b-instant`) — following the RAGAS principle that evaluation should use a more capable model than the one being evaluated.

A curated dataset of 5 `(question, ground_truth, retriever_agent)` pairs drives the evaluation. Each case specifies which retriever method (`query_for_agent1..4`) to use, ensuring the right policy context is retrieved for each question type.

```python
# evals/ragas_dataset.py
RAGAS_CASES = [
    {
        "id": "RG-CP003-LIMIT",
        "question": "What is the auto-approve limit for CP003?",
        "ground_truth": "The CP003 auto-approve limit is AED 20,000.",
        "retriever_agent": "agent3",   # capital pool question → agent3 retriever
        "approval_pool": "CP003",
    },
    ...
]
```

The composite score combines RAGAS metrics with the retrieval pass rate:

```python
WEIGHTS = {
    "retrieval_pass_rate": 0.40,
    "context_recall":      0.30,   # most critical — silent failure mode
    "faithfulness":        0.20,
    "answer_relevance":    0.10,
}
CI_FAIL_THRESHOLD = 0.75
```

---

## Consequences

**Positive:**

- **Pipeline is unbroken.** The 4-agent pipeline continues to work. The RAGAS library conflict does not exist in the execution path.
- **Full control over metric prompts.** The faithfulness prompt can be tuned to match ORCA's domain (UAE retail, AED amounts, ABC classification). The vanilla RAGAS library uses generic prompts.
- **No additional dependencies.** Uses `langchain_groq` which is already in requirements.txt. No new packages.
- **Metrics are fully traceable.** Each metric call is a named LangSmith span (`RAGAS-Judge-Faithfulness | RG-CP003-LIMIT`). The RAGAS library's internal LLM calls are opaque.
- **Same metric semantics.** The 4 metrics are defined identically to the RAGAS paper. Scores are comparable to published RAGAS benchmarks.

**Negative:**

- **Groq API cost.** Each RAGAS evaluation run makes 4 LLM calls per case × 5 cases = 20 Groq API calls. At scale this adds up. The RAGAS library has caching; our implementation does not.
- **Judge model dependency.** If `llama-3.3-70b-versatile` is deprecated by Groq, the eval suite breaks. The RAGAS library abstracts the judge model behind an interface.
- **Not a drop-in replacement.** Research that cites RAGAS library scores and our native scores cannot be directly compared without validation that the prompts produce equivalent results.
- **Maintenance burden.** If the RAGAS paper updates metric definitions, we must manually update our prompts. The RAGAS library would handle this automatically.

---

## Note on the Half-Installed `ragas` Package

The `ragas` package appears in `pip list` in the development environment because a partial install occurred before the conflict was discovered. It is never imported in any production code path. If rebuilding the venv from scratch, `ragas` should not be installed. See `learning/Evaluation/FINDINGS.md` for the full conflict trace.

**The guardrail:** Never run `pip install ragas` or `pip install ragas --upgrade` in this environment. It will uninstall `langchain-core` and break the agents.

---

## Alternatives Considered

| Option | Why Rejected |
|---|---|
| `ragas` library with isolated venv | Would require running evals in a separate process with a completely different Python environment. Complex, fragile. |
| DeepEval library | Similar Vertex AI import conflict. Different dependency tree but same class of problem. |
| Manual heuristic scoring (no LLM judge) | Keyword overlap is not a reliable proxy for faithfulness or answer relevance. Would produce misleading scores. |
| ROUGE/BLEU metrics | Text overlap metrics are wrong for RAG evaluation — a paraphrase of the ground truth scores zero but is semantically correct. |
