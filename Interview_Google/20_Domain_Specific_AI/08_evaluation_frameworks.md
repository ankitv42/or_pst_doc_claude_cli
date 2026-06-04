# Evaluation Frameworks for AI Systems

## What Is It? (Plain English)

Evaluating an AI system is fundamentally harder than evaluating traditional software. You cannot just check if the output equals the expected output — LLM outputs are probabilistic, open-ended, and correct in more than one form. How do you know if your RAG pipeline is good? How do you know if your agent is making sound decisions? How do you detect when a prompt change degrades performance?

Evaluation frameworks are tools and methodologies that answer these questions. They provide metrics, harnesses, and infrastructure for systematically measuring AI system quality. The field splits into two broad categories: offline evaluation (running your system against a fixed dataset before deployment) and online monitoring (tracking quality on real traffic after deployment).

The most important insight about AI evaluation: there is no single "accuracy" number. A RAG system can retrieve the right documents (high retrieval recall) but have the LLM ignore them and hallucinate (low faithfulness). An agent can make correct decisions on your evaluation set but fail on real user inputs that look nothing like your evaluation cases (distribution shift). Good evaluation requires multiple complementary metrics, not one number.

## How It Works

```
EVALUATION FRAMEWORK TAXONOMY
═══════════════════════════════════════════════════════════════════
LAYER 1: RETRIEVAL EVALUATION (no LLM needed)
  Tool: custom scripts, RAGAS retrieval metrics
  Metrics: Context Precision, Context Recall, Hit Rate
  Cost: cheapest — compare retrieved chunks to gold standard
  ORCA: run_retrieval_eval.py — 11 golden test cases, keyword checks

LAYER 2: LLM-AS-JUDGE (LLM needed)
  Tool: RAGAS, DeepEval, TruLens, custom judges
  Metrics: Faithfulness, Answer Relevancy, Reasoning Quality
  Cost: ~$0.01-0.10 per test case (LLM API calls)
  ORCA: run_judge_eval.py (stub — not yet implemented)

LAYER 3: ONLINE MONITORING (production traffic)
  Tool: Langfuse scores, LangSmith feedback, Arize AI
  Metrics: User feedback, human corrections, downstream outcomes
  Cost: continuous, proportional to traffic
  ORCA: HITL approval rate, rejection reason analysis

EVALUATION METRIC RELATIONSHIPS:
──────────────────────────────────────────────────────────────────
         Retrieved Context
         │
         ▼
Context Precision: what % of retrieved chunks are relevant?
Context Recall:    what % of relevant chunks were retrieved?
         │
         ▼
         LLM Response
         │
Faithfulness:      does the response reflect the retrieved context?
Answer Relevancy:  does the response answer the user's question?
─────────────────────────────────────────────────────────────────
A system can have high Context Recall but low Faithfulness:
retrieved the right docs, but the LLM ignored them and hallucinated.
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google deploys AI features to billions of users. A change to a Search AI Overview prompt that degrades faithfulness by 10% affects hundreds of millions of queries per day. The only way to catch this before deployment is a rigorous evaluation pipeline that runs automatically on every change. Senior AI engineers at Google are expected to build and maintain evaluation frameworks as a core part of their systems, not as a nice-to-have. Demonstrating that you have built ORCA's Layer 1 eval (11 golden cases, CI gate on every push) and understand why Layer 2 LLM-as-judge is harder — and what it would take to build it — shows evaluation engineering maturity.

## Interview Questions & Answers

### Q1: Explain the RAGAS framework. What are its core metrics, and what does each measure?

**Answer:** RAGAS (Retrieval Augmented Generation Assessment) is a Python library designed to evaluate RAG pipelines without requiring ground-truth answers for every test case — a significant practical advantage. It measures four core metrics.

**Context Precision** measures what fraction of the retrieved context is relevant to answering the question. High context precision means the retriever is not returning noise. Low context precision means irrelevant chunks are polluting the LLM's context window.

**Context Recall** measures what fraction of the information needed to answer the question is present in the retrieved context. High context recall means the retriever found everything it needed. Low context recall means the LLM cannot answer correctly even if it is perfect, because the relevant information is not in its context.

**Faithfulness** measures whether the response's claims are supported by the retrieved context. An unfaithful response makes claims not found in or contradicted by the context — hallucination. This is the most critical metric for production RAG systems.

**Answer Relevancy** measures whether the response actually answers the user's question. A response can be faithful to the context but still not answer what was asked (e.g., providing correct but tangential information).

```python
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy
)
from datasets import Dataset

# Evaluation dataset format
eval_data = {
    "question": ["What is the reorder policy for Class A SKUs?"],
    "answer": ["Class A SKUs require dual approval for any order exceeding $10,000..."],
    "contexts": [["Class A items require dual approval...", "Emergency procurement..."]],
    "ground_truth": ["Class A SKUs require management approval for large orders..."]
}

dataset = Dataset.from_dict(eval_data)
result = evaluate(dataset, metrics=[
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy
])
print(result)
# {'context_precision': 0.83, 'context_recall': 0.76,
#  'faithfulness': 0.91, 'answer_relevancy': 0.88}
```

RAGAS uses an LLM internally to compute these metrics — it asks the LLM to judge whether each claim in the response is supported by the context (for faithfulness), or whether the question is answered (for answer relevancy). This means RAGAS requires an LLM API, which is why ORCA's Layer 1 eval was designed to not need one.

---

### Q2: Explain DeepEval. How does its "unit test" style differ from RAGAS's distribution approach?

**Answer:** DeepEval applies software testing philosophy to LLM evaluation. Instead of computing aggregate metrics over a dataset (like RAGAS), DeepEval lets you write assertion-style tests for individual LLM outputs — if the assertion fails, the test fails, just like pytest.

This "unit test" style is more actionable than aggregate metrics. When RAGAS reports faithfulness=0.72, you know something is wrong but not what specifically. When DeepEval's test fails on test case #7 with "Expected response to mention Class A requirements; actual response did not", you know exactly what broke.

```python
import pytest
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    HallucinationMetric,
    GEval
)

# GEval: custom evaluation criterion defined in natural language
class RouteAccuracyMetric(GEval):
    name = "Route Accuracy"
    criteria = """
    Evaluate whether the capital allocation agent correctly classified
    the order as requiring approval (ESCALATE) when the total cost
    exceeds $15,000, and as auto-executable when below $15,000.
    """
    evaluation_steps = [
        "1. Check if total_cost > 15000",
        "2. If yes: verify the route is ESCALATE",
        "3. If no: verify the route is AUTO_EXECUTE",
        "4. Return 1 if correct, 0 if incorrect"
    ]

# Write test cases like pytest tests
def test_agent3_high_cost_escalation():
    test_case = LLMTestCase(
        input="SKU-001: 3 options, best option total_cost=$18,500",
        actual_output=agent3.invoke(high_cost_state),
        expected_output="route: ESCALATE",
        retrieval_context=["Capital allocation policy: orders above $15k require approval..."]
    )
    faithfulness = FaithfulnessMetric(threshold=0.8)
    route_accuracy = RouteAccuracyMetric(threshold=1.0)
    
    # Run assertions
    assert_test(test_case, [faithfulness, route_accuracy])

# Run all tests with CI integration
@pytest.mark.parametrize("case", test_cases)
def test_pipeline_regression(case):
    # ...
```

DeepEval integrates with pytest, so you can run `pytest evals/` and get pass/fail results in your CI pipeline — which is exactly the pattern ORCA uses for Layer 1.

---

### Q3: How does ORCA's Layer 1 retrieval evaluation work? Why was it designed to require no API key?

**Answer:** ORCA's Layer 1 eval (`evals/run_retrieval_eval.py`) is a deliberately simple evaluation that checks whether the RAG retriever returns the right documents for specific queries. It uses keyword-based checks rather than LLM-based semantic evaluation.

```python
# evals/run_retrieval_eval.py — simplified structure
GOLDEN_TEST_CASES = [
    {
        "query": "What triggers an emergency expedite order?",
        "agent": "agent2",
        "required_keywords": ["expedite", "emergency", "lead time", "critical"],
        "forbidden_keywords": ["GDPR", "salary", "employee"],  # wrong doc leakage check
        "expected_source": "emergency_procurement_policy"
    },
    {
        "query": "How is the capital allocation score calculated?",
        "agent": "agent3",
        "required_keywords": ["budget_score", "availability_score", "margin", "lead_time"],
        "forbidden_keywords": [],
        "expected_source": "capital_allocation_policy"
    },
    # ... 9 more test cases
]

def run_retrieval_eval(ci_mode: bool = False) -> dict:
    results = []
    for case in GOLDEN_TEST_CASES:
        agent_func = getattr(retriever_module, f"query_for_{case['agent']}")
        retrieved_context = agent_func(case["query"])

        # Check required keywords are present
        keyword_hits = sum(1 for kw in case["required_keywords"]
                          if kw.lower() in retrieved_context.lower())
        pass_rate = keyword_hits / len(case["required_keywords"])

        # Check for leakage (wrong document content in results)
        leakage = any(kw.lower() in retrieved_context.lower()
                     for kw in case["forbidden_keywords"])

        results.append({
            "query": case["query"],
            "passed": pass_rate >= 0.7 and not leakage,
            "pass_rate": pass_rate,
            "leakage": leakage
        })

    overall_pass_rate = sum(r["passed"] for r in results) / len(results)

    if ci_mode and overall_pass_rate < 0.7:
        sys.exit(1)  # fail CI gate

    return {"pass_rate": overall_pass_rate, "results": results}
```

**Why no API key required:** LLM-based evaluation (RAGAS, DeepEval's semantic metrics) requires calling an LLM API for every test case. For 11 test cases, this costs a few cents — trivial. But for CI pipelines that run on every push, there are three problems: (1) API keys need to be stored in CI secrets (security surface), (2) rate limits can cause flaky CI (test fails not because code is wrong but because API is slow), (3) the test result depends on the LLM's judgment, which can vary (non-deterministic tests are frustrating in CI).

Keyword-based Layer 1 evaluation is deterministic, requires no API, runs in seconds, and catches the most important failure mode: the retriever returning the completely wrong document. It is intentionally not comprehensive — that is Layer 2's job — but it is reliably useful as a CI gate.

---

### Q4: Explain TruLens and the RAG Triad. How does it complement RAGAS?

**Answer:** TruLens is an evaluation framework that focuses on the "RAG Triad" — three dimensions that together describe a healthy RAG pipeline:

- **Context Relevance:** Is the retrieved context relevant to the question? (RAGAS calls this Context Precision)
- **Groundedness:** Is the response grounded in the retrieved context? (RAGAS calls this Faithfulness)
- **Answer Relevance:** Does the response answer the question? (RAGAS calls this Answer Relevancy)

```python
from trulens_eval import TruChain, Feedback, Huggingface, OpenAI

# TruLens wraps your chain and evaluates live
openai = OpenAI()

# Define feedback functions
f_qa_relevance = Feedback(openai.relevance).on_input_output()
f_groundedness = Feedback(openai.groundedness).on(
    TruChain.select_context()
).aggregate(numpy.min)  # min over contexts
f_context_relevance = Feedback(openai.qs_relevance).on_input().on(
    TruChain.select_context()
).aggregate(numpy.mean)

# Wrap your RAG chain with TruLens instrumentation
tru_recorder = TruChain(orca_rag_chain,
                         app_id="orca-rag-v1",
                         feedbacks=[f_qa_relevance, f_groundedness, f_context_relevance])

# Run queries — TruLens captures traces and evaluates automatically
with tru_recorder as recording:
    orca_rag_chain.invoke({"question": "What is the policy for Class A SKUs?"})

# Launch TruLens dashboard
from trulens_eval import Tru
Tru().run_dashboard()
```

**TruLens vs RAGAS:**

```
COMPARISON:
══════════════════════════════════════════════════════════════
                  RAGAS                    TruLens
──────────────────────────────────────────────────────────────
Integration       Batch evaluation         Live chain wrapping
Ground truth      Required for recall      Not required
Metrics focus     4 core metrics           RAG Triad + custom
Dashboard         No                       Yes (Streamlit)
Streaming eval    No                       Yes
Use case          Offline benchmark        Online monitoring
LangChain support Yes                      Yes (native)
CI integration    Yes                      Less common
══════════════════════════════════════════════════════════════
```

RAGAS is better for offline evaluation with ground truth datasets. TruLens is better for monitoring live production pipelines with real user queries. They are complementary: use RAGAS during development and before deployment, use TruLens after deployment for ongoing monitoring.

---

### Q5: What is Promptfoo? How would you use it to test ORCA's agent prompts for regression?

**Answer:** Promptfoo is a command-line tool for prompt testing and regression. It lets you define a prompt, a set of test cases, and assertions in a YAML configuration file, then run all test cases and check assertions automatically. It is specifically designed for the prompt engineering workflow: "I changed the prompt — did I make things better or did I accidentally break something?"

```yaml
# promptfooconfig.yaml for ORCA Agent 3 prompt
prompts:
  - file://agents/prompts.py:CAPITAL_ALLOCATION_PROMPT

providers:
  - id: groq:llama-3.1-8b-instant
    config:
      temperature: 0.1

tests:
  - description: "High cost should escalate"
    vars:
      demand_analysis: '{"urgency": "CRITICAL"}'
      options: '[{"type": "expedite", "cost": 18500}, {"type": "standard", "cost": 12500}]'
    assert:
      - type: contains
        value: "ESCALATE"
      - type: javascript
        value: |
          const parsed = JSON.parse(output);
          return parsed.total_cost > 15000 && parsed.route === "ESCALATE";

  - description: "Low cost should auto-execute"
    vars:
      demand_analysis: '{"urgency": "MEDIUM"}'
      options: '[{"type": "standard", "cost": 4500}]'
    assert:
      - type: contains
        value: "AUTO_EXECUTE"

  - description: "Class A partial should never be recommended"
    vars:
      sku_class: "A"
      options: '[{"type": "partial", "cost": 3000}]'
    assert:
      - type: not-contains
        value: "partial"
      - type: llm-rubric
        value: "Response should not recommend partial distribution for Class A SKU"
```

Run with: `promptfoo eval`

Promptfoo outputs a table showing pass/fail for each assertion on each test case, a diff when comparing prompt versions, and a web UI for detailed inspection.

**How to use it for ORCA prompt regression:**

1. Define the current "baseline" prompt and test cases
2. Before changing a prompt, run `promptfoo eval --output baseline.json`
3. Make the prompt change
4. Run `promptfoo eval --output v2.json`
5. Run `promptfoo compare baseline.json v2.json` — shows which tests changed
6. If any previously passing test now fails: investigate before merging

```
EVALUATION FRAMEWORK DECISION GUIDE:
═══════════════════════════════════════════════════════════════════
Need                              → Use
─────────────────────────────────────────────────────────────────
CI gate, no API key               → Custom keyword checks (ORCA Layer 1)
RAG retrieval + generation eval   → RAGAS
Unit test style with custom logic → DeepEval
Live production monitoring        → TruLens + Langfuse scores
Prompt regression testing         → Promptfoo
Comprehensive offline eval suite  → RAGAS + DeepEval together
Full observability platform       → LangSmith or Langfuse
═══════════════════════════════════════════════════════════════════
```

## Key Points to Say in the Interview

- "Evaluation requires multiple complementary metrics — a single accuracy number misses failure modes that are invisible to other metrics."
- "RAGAS's four metrics: Context Precision (retriever precision), Context Recall (retriever recall), Faithfulness (no hallucination), Answer Relevancy (answers the question)."
- "ORCA's Layer 1 evaluation is intentionally LLM-free: keyword checks, deterministic, runs in CI on every push — catches document routing failures."
- "DeepEval is unittest-style: write assertions for specific test cases, run with pytest, fail CI if assertions fail."
- "TruLens wraps live chains and evaluates production traffic in real time — complements RAGAS's offline batch evaluation."
- "Promptfoo is for prompt regression: define baseline test cases, compare before/after prompt change, catch regressions before they go live."
- "Layer 1 (no API) → Layer 2 (LLM-as-judge) → Layer 3 (CI gate) is the correct evaluation layering pattern."

## Common Mistakes to Avoid

- Using only a single metric (e.g., only faithfulness) — missing other failure modes like poor retrieval or irrelevant responses.
- Building evaluation datasets once and never updating them — evaluation coverage decays as the system evolves.
- Running expensive LLM-based evaluations in CI where determinism and cost matter — use keyword/rule-based checks for CI.
- Not separating retrieval evaluation from generation evaluation — they have different failure modes and different mitigations.
- Treating high eval scores as sufficient before deployment — evaluation sets never fully cover real user input distributions.

## Further Reading

- [RAGAS documentation](https://docs.ragas.io/) — comprehensive guide to RAG evaluation metrics with Python examples
- [DeepEval documentation](https://docs.confident-ai.com/) — unit testing framework for LLM outputs with pytest integration
- [Promptfoo documentation](https://www.promptfoo.dev/docs/intro) — CLI tool for prompt regression testing with extensive assertion types
