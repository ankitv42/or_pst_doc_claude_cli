# Experimentation for AI Products

## What Is It? (Plain English)

An experiment in the context of AI products is a controlled test that lets you measure whether a change to your AI system actually improves the outcome you care about — and whether that improvement is real, or just random noise. Without experimentation, you are flying blind. You might upgrade your model, see slightly better numbers, and conclude the upgrade worked. But if the improvement was within normal variation, you just spent money and added maintenance complexity for nothing.

The fundamental challenge with AI experiments is that AI outputs are probabilistic. If you run the same prompt twice on the same data, you may get slightly different responses. This variance is built into LLM systems through the "temperature" parameter. When you are measuring whether model version B is better than model version A, you need to account for this variance by running enough experiments that you can distinguish a real improvement from random fluctuation. This is called statistical significance, and it is the reason most serious AI teams run thousands of automated evaluation cases rather than manually reviewing a dozen outputs.

A/B testing for AI products has one important additional complication compared to traditional software A/B tests: the quality of the AI output is often difficult to measure automatically. In a traditional product, you measure clicks, sign-ups, or purchases — clear, binary outcomes. For an AI recommendation system, you often want to measure whether the recommendation was correct, which requires either a human reviewer (expensive) or an automated judge (which itself may be an LLM, introducing another layer of uncertainty). This is why evaluation framework design — deciding what "correct" means and how to measure it automatically — is as important as the experiment design itself.

## How It Works (or: How to Think About This)

The experiment lifecycle for an AI feature:

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXPERIMENT LIFECYCLE                          │
│                                                                  │
│  1. HYPOTHESIS         "Replacing llama-8b with llama-70b       │
│                         on Agent 3 will increase auto-approval  │
│                         acceptance rate by ≥5% with no cost     │
│                         increase >$0.05/run"                    │
│           │                                                      │
│           ▼                                                      │
│  2. CONTROL DEFINITION  Define exactly what "current state" is  │
│                         and how it is measured                  │
│           │                                                      │
│           ▼                                                      │
│  3. METRIC SELECTION   Primary: acceptance rate                 │
│                         Guardrail: cost/run, latency            │
│           │                                                      │
│           ▼                                                      │
│  4. SAMPLE SIZE CALC   How many runs needed to detect a 5%      │
│                         improvement at 95% confidence?          │
│           │                                                      │
│           ▼                                                      │
│  5. RANDOMIZATION       Assign pipeline runs to A/B by         │
│                         hash(run_id) % 2                        │
│           │                                                      │
│           ▼                                                      │
│  6. GUARDRAIL MONITORING Watch during experiment; kill if       │
│                         guardrail degrades                      │
│           │                                                      │
│           ▼                                                      │
│  7. ANALYSIS            Statistical test; ship or roll back     │
└─────────────────────────────────────────────────────────────────┘
```

For ORCA's Layer 1 retrieval eval, the experiment structure looks like this:

```
ORCA RETRIEVAL EVAL EXPERIMENT DESIGN

Golden Dataset (11 test cases):
  ┌─────────────────┬────────────────────┬─────────────────┐
  │ Query           │ Expected keywords  │ Forbidden docs  │
  ├─────────────────┼────────────────────┼─────────────────┤
  │ "Class A SKU    │ "A-class", "never  │ doc: finance    │
  │ partial order?" │ partial", "stockout│ doc: logistics  │
  │                 │ prevention"        │                 │
  └─────────────────┴────────────────────┴─────────────────┘

Control: BM25-only retrieval
Treatment: BM25 + Vector + RRF fusion + cross-encoder reranking

Metrics:
  Primary:  keyword hit rate per test case (target ≥ 70%)
  Guardrail: doc leak rate (must be 0.0)
  Secondary: retrieval latency (p95 < 500ms)

Interpretation:
  Pass:    ≥8/11 test cases pass, 0 leaks, p95 latency < 500ms
  Failure: <8 passes OR any leak OR p95 > 500ms
```

## Why Google Cares About This

Experimentation is the core of Google's product development culture. Google runs thousands of A/B experiments per year across its products, and the expectation at senior levels is that you can design, analyze, and interpret experiments without help. For AI products specifically, Google has invested heavily in evaluation infrastructure (LLM-as-judge, automated eval suites, golden datasets), and interviewers want to know whether you have the same rigor. Saying "we tried the new model and it seemed better" is not an acceptable answer. Saying "we ran a holdout experiment on 200 pipeline runs, measured acceptance rate and cost, and found a 6.2% improvement in acceptance rate with no statistically significant cost change" is what they want to hear.

## Interview Questions & Answers

### Q1: How do you design an A/B test for an AI feature when the output quality is hard to measure automatically?

**Answer:** The key insight is that you need to define "quality" operationally before you design the experiment — not as an abstract concept, but as a specific measurement you can compute on every test case. There are three levels of measurement to consider, from least to most expensive: heuristic metrics, automated LLM-judge metrics, and human evaluation metrics.

Heuristic metrics are fast and cheap but incomplete. For ORCA's Agent 2, a heuristic metric is whether the output contains exactly three options (standard, partial, expedite) and whether the Class A SKU partial-order constraint is respected. You can check these programmatically in milliseconds. They catch structural failures but miss quality failures like a poorly reasoned option description.

LLM-judge metrics are more powerful: you write a second prompt that takes the AI output as input and asks an LLM to score it on specific dimensions. For ORCA's Agent 3, an LLM judge might evaluate: "Does this capital scoring output correctly apply the formula budget_score + availability_score + margin_score + lead_time_penalty? Does it provide a clear recommendation?" The judge itself may make errors, but averaged over many test cases, its aggregate scores are a reliable signal. ORCA's Layer 2 eval (the LLM-as-judge component, currently a stub) is designed to fill exactly this role.

Human evaluation is the gold standard but only scales to a small number of test cases. The pragmatic approach is to use human evaluation to build and validate the golden dataset, use heuristic and LLM-judge metrics for the automated experiment, and then have a human spot-check a random sample of "borderline" cases — cases where the heuristic says pass and the LLM judge says fail, or vice versa. This hybrid approach gives you the scale of automation with the accuracy of human judgment at the margin.

### Q2: What is a holdout experiment and when is it better than an A/B test?

**Answer:** A holdout experiment withholds a feature from a defined group of users or use cases indefinitely, allowing you to measure the counterfactual — what would have happened without the feature — continuously over time. It is different from an A/B test, which typically runs for a defined period, measures a primary metric, and then ships the winner.

Holdouts are better than A/B tests when you expect the benefit of the feature to appear over a long time horizon. In inventory management, the north star metric (stockout rate) has a multi-week observation period. A two-week A/B test might not be long enough to see the stockout reduction that results from better reorder decisions made today. A holdout group — say, 10% of stores permanently excluded from the AI pipeline — gives you an ongoing measurement of the system's impact at the business level.

Holdouts are also better when the outcome you are measuring can only be evaluated by a human and that evaluation process is slow. If your experiment requires a human expert panel to review 200 AI recommendations and rate their quality, running three sequential A/B tests would take months. A holdout design lets you accumulate that human evaluation data continuously at a fixed cadence (weekly panel review) rather than in bursts.

The cost of a holdout is that you are permanently withholding a potentially valuable feature from the holdout group. In consumer products, this is an ethical consideration (users in the holdout may have worse experiences). In an enterprise inventory system, the holdout stores may have higher stockout rates for the duration of the experiment. This tradeoff needs to be negotiated with business stakeholders upfront.

### Q3: How do you handle interference effects in experiments on AI recommendation systems?

**Answer:** Interference (sometimes called spillover or network effects) occurs when the treatment assigned to one unit of randomization affects the outcomes of another unit. In inventory systems, this is a real problem: if the AI pipeline is applied to SKU-A and generates a large reorder, that order may affect the supplier's capacity to fulfill orders for SKU-B (which might be in the control group). The measured difference between treatment and control SKUs would then reflect this supply constraint effect, not just the quality of the AI recommendation.

The solution is to randomize at the right level of independence. For inventory experiments, that usually means randomizing at the store level or the supplier level, not the SKU level. If an entire store is in the treatment group, all SKUs in that store get the AI pipeline, and the interference is contained within the group rather than crossing between groups.

A second source of interference specific to AI systems is the LLM itself: if the model is being fine-tuned or updated during the experiment, the treatment group might be receiving different model quality at the end of the experiment than at the start. The solution is to freeze model versions for the duration of the experiment and use feature flags to control which pipeline version each run uses.

The third source of interference is temporal: inventory demand is seasonal, and a two-week experiment that overlaps with a promotional period will produce different results than the same experiment during a steady-state period. For experiments on ORCA, I would specifically avoid running experiments during peak retail periods (holiday seasons, major promotions) or at minimum, stratify the analysis to separate results from normal and promotional periods.

### Q4: What is the minimum sample size required to run a valid experiment on a low-traffic AI pipeline?

**Answer:** The sample size question is really a statistical power question: how many observations do you need to reliably detect the smallest effect size you care about? The standard approach uses a power analysis, which takes three inputs: the baseline metric value, the minimum detectable effect (MDE) — the smallest improvement you consider meaningful — and the desired statistical confidence level (typically 95%).

For ORCA, if the current auto-approval acceptance rate is 80% (control) and you want to detect an improvement to 85% (treatment) at 95% confidence with 80% power, a standard two-proportion z-test power calculation gives you approximately 420 observations per group — 840 pipeline runs total. If ORCA processes 50 pipeline runs per day, that experiment would take about 17 days.

If the traffic volume is too low to reach the required sample size in a reasonable time, you have a few options. First, reduce the MDE: if you are willing to only detect a 10% improvement rather than a 5% improvement, you need far fewer observations. Second, use a more sensitive metric: instead of a binary pass/fail, use a continuous score (like Agent 3's capital score on a 0-100 scale), which has more statistical information per observation. Third, use a sequential test design (like a Bayesian sequential test) that lets you stop the experiment early if the evidence is already strong enough — this is particularly useful for low-traffic pipelines where waiting for the full planned sample size would take too long.

The key point to communicate in the interview is that running an underpowered experiment is worse than running no experiment, because you are likely to draw incorrect conclusions from noisy data. If you cannot reach adequate sample size, it is better to use offline evaluation (golden dataset testing) and staged rollout with careful monitoring than to run an underpowered online experiment.

### Q5: How would you run an experiment to measure whether adding the CrewAI sub-crew to Agent 1 improves ORCA's overall recommendation quality?

**Answer:** This is a classic A/B test on an AI pipeline component. The experiment design would have two groups: the control group uses Agent 1 in fallback mode (raw data demand summary, which is the current state given the CrewAI bug), and the treatment group uses Agent 1 with the full CrewAI sub-crew output once the bug is fixed. Both groups go through the same Agent 2, 3, and 4 pipeline.

The primary metric would be the human approval acceptance rate for ESCALATED decisions: when a pipeline run hits the HITL review path, how often does the human manager approve the AI recommendation without modification? This is a direct measure of recommendation quality that does not require an automated judge.

The secondary metrics would be: Agent 3 capital score distribution (does using the CrewAI output produce systematically different scores?), time-to-decision (does the sub-crew add unacceptable latency?), and pipeline error rate (does the sub-crew introduce new failure modes?).

One important design consideration: the CrewAI sub-crew failure needs to be fully fixed before running the experiment. Running the experiment while the treatment group has a partial failure rate would confound the results — you would not know whether any observed difference was due to the sub-crew's quality or due to the frequency of failures. The experiment should start with a clean baseline where the treatment group runs the sub-crew successfully on 99%+ of cases.

The randomization unit should be the pipeline run (not the SKU), and runs should be stratified by SKU class (A/B/C) to ensure both groups have similar distributions of order complexity. After approximately 2 weeks of data (assuming ~50 runs/day, ~700 runs per group), you would have sufficient power to detect a 5% difference in acceptance rate. If the treatment group shows meaningfully higher acceptance rates and the latency guardrail is not violated, you ship the sub-crew fix.

## Key Points to Say in the Interview
- Define "quality" operationally before designing the experiment — not as an abstract concept
- Use heuristic + LLM-judge + human eval as a layered quality measurement strategy
- Randomize at the right level to avoid interference (store-level for inventory, not SKU-level)
- Power analysis is required before running any experiment — underpowered experiments produce wrong conclusions
- Holdout experiments are better than A/B tests for long-horizon outcomes like stockout rate
- Freeze model versions during experiments to avoid temporal confounds

## Common Mistakes to Avoid
- Running experiments without first specifying the minimum detectable effect and required sample size
- Randomizing at the SKU level for inventory experiments (interference from shared suppliers)
- Using only binary pass/fail metrics when continuous scores are available (lower statistical efficiency)
- Running experiments during seasonal peaks without stratifying the analysis
- Treating any observed improvement as significant without a statistical test

## Further Reading
- [Trustworthy Online Controlled Experiments (Ron Kohavi)](https://experimentguide.com/) — the definitive textbook on A/B testing, by Google and Microsoft veterans
- [Evan Miller: Sample Size Calculator](https://www.evanmiller.org/ab-testing/sample-size.html) — free tool for running power calculations before experiments
- [RAGAS Documentation](https://docs.ragas.io/en/stable/) — the evaluation framework built specifically for RAG pipelines, including experiment design guidance
