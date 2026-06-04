# Offline Evaluation

## What Is It? (Plain English)

Offline evaluation means testing your AI system before it touches real users — using pre-built test cases with known correct answers to measure quality, consistency, and safety. It's the AI equivalent of unit tests and integration tests in traditional software engineering, but adapted for the probabilistic, non-deterministic nature of language models.

In traditional software, you test a function by giving it specific inputs and checking that the output exactly matches the expected value. With AI, the output is never identical across runs, and "correct" is often a matter of degree rather than binary yes/no. A good answer about supply chain policy might be phrased in dozens of ways, all acceptable. So offline evaluation requires thinking carefully about what "correct" means — and building measurement approaches that can handle fuzzy correctness.

Offline evaluation is essential before any production deployment because it gives you a reproducible, version-controlled quality baseline. When someone asks "is this model change an improvement?", offline eval gives you a principled answer backed by data — not just intuition or spot-checking. It also enables CI/CD for AI systems: automatically run evals on every code change, fail the pipeline if quality drops below a threshold.

## How It Works

```
Offline Evaluation Pipeline
─────────────────────────────────────────────────────────────
Step 1: Create Golden Dataset
  ┌─────────────────────────────────────────────┐
  │ Query: "What is the reorder threshold?"      │
  │ Expected: mentions Class A, $47,500 limit    │
  │ Anti-expected: no hallucinated SKU codes     │
  └─────────────────────────────────────────────┘
  × N queries (50–5000 depending on budget)

Step 2: Run System Under Test
  Golden Query ──► RAG Pipeline ──► Answer

Step 3: Score Each Answer
  ┌────────────────────────────────────────────────┐
  │ Method A: Rule-based (keyword check, regex)    │
  │ Method B: Embedding similarity (cosine ≥ 0.85) │
  │ Method C: LLM-as-judge (GPT-4 rates 1-5)       │
  │ Method D: Human annotation (gold standard)      │
  └────────────────────────────────────────────────┘

Step 4: Aggregate Metrics
  Pass rate, average score, failure category breakdown

Step 5: Gate the Deployment
  IF pass_rate >= threshold AND no regressions → SHIP
  ELSE → investigate failures → fix → re-run
─────────────────────────────────────────────────────────────
```

A critical design principle: **offline eval should be cheap enough to run on every commit.** If it takes 3 hours and costs $50 in API fees, engineers will skip it. ORCA's Layer 1 eval runs in under 60 seconds with zero API cost — this is the right design.

## Why Google Cares About This

Every AI product at Google goes through a rigorous offline evaluation before shipping. Gemini responses, Search ranking changes, YouTube recommendation updates — all are evaluated offline first. For senior roles, interviewers expect you to design eval frameworks from first principles: define the right metrics, build the right test set, choose the right scoring method, and integrate into CI. Saying "I eyeballed a few outputs" will not pass the bar.

## Interview Questions & Answers

### Q1: What are the different approaches to scoring LLM outputs in an offline evaluation, and when do you use each?

**Answer:** There are four scoring approaches, each with different cost, accuracy, and scalability profiles.

**Rule-based scoring** checks for explicit properties: does the output contain required keywords? Does it match a regex pattern? Is the length within bounds? Does it avoid forbidden phrases? This is the cheapest, fastest, and most deterministic approach — it runs in milliseconds with zero cost. It's appropriate when correctness has a clear, checkable signal. For example, ORCA's Layer 1 eval checks that retrieved context contains specific supply chain terminology (keyword presence) and does NOT contain terminology from the wrong documents (anti-keyword check). Rule-based scoring also applies for classification tasks where the valid outputs are enumerable (e.g., routing decisions: ESCALATE/AUTO_EXECUTE/SUSPEND).

**Embedding similarity scoring** embeds both the expected output and the model's actual output, then computes cosine similarity. If similarity exceeds a threshold (e.g., 0.85), the answer is marked as correct. This is better than exact string matching for natural language answers but still cheap (a few milliseconds per pair). The limitation: similar embeddings don't guarantee semantic equivalence. "The limit is $47,500" and "Orders under $47,500 don't require approval" have high cosine similarity but very different implications depending on the question.

**LLM-as-judge scoring** uses a strong LLM (typically GPT-4 or Claude) to evaluate the output with a structured rubric. You write a prompt like "Rate the following answer on correctness (1-5) and faithfulness (1-5) given this question and reference answer: ..." The LLM returns scores and optionally reasoning. This is the most accurate automated approach — comparable to human judgment for many tasks. The cost is significant ($0.01–0.10 per evaluation call) and adds latency, so you run it on a stratified sample rather than every test case. ORCA's Layer 2 eval is LLM-as-judge — currently a stub but designed for this pattern.

**Human annotation** is the gold standard for calibrating your other scoring methods. You have domain experts (or paid annotators) review model outputs and score them. This is expensive and slow but necessary to validate that your automated scoring correlates with human judgment. Best practice: annotate a "calibration set" of 100–200 examples with human scores, then measure how well each automated scoring method correlates. Use the automated method that has the highest Spearman correlation with human scores as your primary CI metric.

### Q2: How do you create a good golden dataset for a RAG system? What are the common pitfalls?

**Answer:** Building a golden dataset is the most important and most underrated step in RAG evaluation. A weak golden dataset produces metrics that don't reflect real-world quality — you can hit 95% pass rate on your eval while users are getting bad answers in production.

The right process starts with query collection from multiple sources. The first source is expert-written queries — engineers and domain experts who know what questions the system should handle write representative test cases. The second source is hypothetical user queries — imagine the range of users and what they'd actually ask, including non-expert phrasings. The third source (if available) is production logs — real queries from real users are the most valuable because they reveal the actual distribution of use cases, including edge cases experts didn't anticipate.

For each query, you need to annotate what a correct answer looks like. This annotation strategy matters enormously. Option A: annotate at the retrieval level (which document chunks should be returned). This is what ORCA's Layer 1 eval does and it enables fast LLM-free evaluation. Option B: annotate at the answer level (write a reference answer or key facts the answer must include). This enables both retrieval and generation evaluation but requires more annotation work. Option C: annotate at the citation level (which source supports each claim in the answer). This is the most thorough but most expensive.

Common pitfalls: First, building a dataset from document headers only — "What is the inventory reorder policy?" is answered right at the top of the policy doc, so it tests the easy case. Paraphrase queries like "when should I resupply Class A items?" test whether the system actually understands semantic meaning. Second, not including "out of scope" queries — a question the system isn't supposed to answer (e.g., "write me a poem") should be tested too. Third, letting the dataset decay — when you update the document corpus, some golden queries become unanswerable or have different correct answers. Version your eval dataset alongside your documents.

### Q3: How does ORCA's offline evaluation framework work, and what is its test coverage gap?

**Answer:** ORCA's eval framework has three intended layers with different coverage levels. Layer 1 (`run_retrieval_eval.py`) is fully implemented and runs in CI. Layer 2 (`run_judge_eval.py`) is a stub. Layer 3 (`.github/workflows/eval_gate.yaml`) runs Layer 1 as a CI gate.

Layer 1 tests retrieval quality using 11 golden test cases. Each case specifies a query string, expected keywords (terms that should appear in the retrieved context), and anti-keywords (terms from unrelated documents that should NOT appear, testing cross-document contamination). The test calls `query_for_agent1()` through `query_for_agent4()` functions directly — the same functions agents call at runtime — and checks the returned context string. No LLM API key is required. The test passes if recall meets a 70% threshold and zero leakage (anti-keywords never appear).

The test coverage gap is significant. Layer 1 covers retrieval quality only and uses keyword presence as a proxy for retrieval correctness — which can produce false positives (right keyword, wrong context). It does not test: agent decision correctness (does Agent 3 compute the capital allocation formula correctly?), HITL routing accuracy (does Agent 4 correctly route ESCALATE vs AUTO_EXECUTE?), faithfulness of LLM answers (does the generated recommendation stick to retrieved policy?), or end-to-end answer quality (is the final reorder recommendation sensible?).

Layer 2 is intended to address these gaps via LLM-as-judge evaluation of agent decisions, RAG grounding, HITL accuracy, and formula correctness. The CLAUDE.md marks this as a "HIGH" known issue. The correct implementation would create 20–30 golden (SKU alert, expected_routing_decision, expected_recommendation_structure) triples, run the full pipeline, and use a GPT-4 or Claude judge to score whether the agent decisions are correct and well-grounded.

### Q4: What metrics should you track when evaluating an LLM-based multi-agent system like ORCA?

**Answer:** Multi-agent systems have evaluation challenges beyond single LLM calls because errors can compound across agents and the overall pipeline output depends on decisions made earlier.

For individual agents, the relevant metrics are task-specific. Agent 1 (Demand Intelligence) should be evaluated on whether its urgency classification matches expert judgment (a classification accuracy metric). Agent 2 (Supply Replenishment) should be evaluated on whether its three reorder options are correctly constructed — particularly whether Class A SKUs never get partial distribution (a hard constraint). Agent 3 (Capital Allocation) should be evaluated on formula correctness — does the scoring formula produce consistent, sensible rankings across diverse SKU scenarios? Agent 4 (Routing) should be evaluated on routing accuracy — does ESCALATE trigger at exactly the right cost thresholds?

Across the pipeline, you want end-to-end metrics. HITL accuracy: what fraction of high-cost orders are correctly escalated for human approval (false negatives, where an expensive order slips through to AUTO_EXECUTE, are critical failures). Faithfulness: are recommendations grounded in retrieved policy? Coherence: does Agent 3's decision reference Agent 2's output correctly?

For retrieval specifically (supporting all agents): Recall@K at each agent's query function, anti-leakage (Agent 1's retrieval shouldn't surface Agent 3's capital allocation policy), and retrieval latency (since the pipeline is already multi-step, slow retrieval compounds the total latency).

Finally, operational metrics: pipeline success rate (what fraction of runs complete without the CrewAI error fallback?), total pipeline latency (end-to-end from trigger to final recommendation), and HITL engagement rate (what fraction of escalated decisions do humans actually act on?).

### Q5: How do you integrate offline evaluation into a CI/CD pipeline for an AI system?

**Answer:** CI integration for AI eval requires solving three practical problems: cost, latency, and determinism.

Cost is managed by tiered evaluation. Cheap, fast evals (rule-based, keyword checks, regex) run on every commit — these catch regressions in minutes and cost nothing. Medium-cost evals (embedding similarity, small LLM judge model) run on every pull request to main. Expensive evals (full LLM-as-judge with GPT-4 on large test sets, human spot-check workflow) run on release candidates only. ORCA uses this pattern: CI runs Layer 1 (zero cost, zero API key) on every push, while the more expensive Layer 2 eval is deferred to manual execution before release.

Latency is managed by parallelism and batching. If you have 500 golden test cases, run them in parallel (async coroutines or thread pool). For LLM judge calls, use batch APIs where available (OpenAI and Anthropic both offer batch endpoints that are cheaper and suitable for offline eval). Set a timeout — if an eval run takes more than 10 minutes, something is wrong (rate limits, network issues) and it should fail rather than block the pipeline indefinitely.

Determinism is the hardest problem. LLMs are non-deterministic — the same input can produce different outputs across runs. Two strategies: First, use temperature=0 for evaluation runs to minimize variance. Second, use metrics that are stable to minor output variation (keyword presence, structured output parsing) rather than exact string matching. Third, account for expected variance in your pass threshold — if your system normally achieves 87% pass rate on a specific metric, flag as failure only if it drops below 80%, not 86.9%. ORCA's 70% pass rate threshold is appropriate for this reason.

The CI workflow in `.github/workflows/eval_gate.yaml` runs `python evals/run_retrieval_eval.py --ci` with the `--ci` flag, which exits with code 1 if pass rate drops below 70%, blocking the merge. This is the right pattern — make quality gates concrete, automated, and blocking.

## Key Points to Say in the Interview
- Offline eval separates retrieval quality from generation quality — debug them independently
- Build a tiered eval strategy: cheap evals run on every commit, expensive evals run pre-release
- LLM-as-judge is powerful but costs money — calibrate it against human annotations before trusting it
- Golden datasets must include paraphrase queries and adversarial cases, not just "document header" questions
- ORCA's Layer 1 runs zero-cost, zero-API in CI — this is the right design principle for CI evals
- Multi-agent systems need per-agent metrics AND end-to-end pipeline metrics (errors compound)

## Common Mistakes to Avoid
- Building golden datasets from document headings only — misses paraphrase and semantic generalization
- Running expensive LLM judge evals on every commit — they're too slow and costly for CI
- Using pass/fail thresholds without accounting for metric variance (LLM outputs fluctuate by ±5%)
- Not versioning the golden dataset alongside the application code — eval dataset becomes stale after document updates
- Measuring only "accuracy" without breakdown by failure category — you need to know WHY failures occur

## Further Reading
- [RAGAS Paper (arXiv)](https://arxiv.org/abs/2309.15217) — Automated evaluation framework for RAG systems covering multiple quality dimensions
- [Evaluating LLMs: A Survey (arXiv)](https://arxiv.org/abs/2307.03109) — Comprehensive survey of evaluation methodologies for language models
- [LangSmith Evaluation Framework](https://docs.smith.langchain.com/evaluation) — Practical CI-integrated evaluation framework used with LangChain/LangGraph
- [Evals (OpenAI framework)](https://github.com/openai/evals) — OpenAI's open-source eval framework with patterns for building golden datasets
- [Braintrust AI Evaluation](https://www.braintrust.dev/docs/guides/evals) — Modern eval platform with CI integration and human annotation workflow
