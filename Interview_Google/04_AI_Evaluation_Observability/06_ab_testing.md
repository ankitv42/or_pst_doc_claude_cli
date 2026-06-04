# A/B Testing for AI Systems

## What Is It? (Plain English)

A/B testing is a controlled experiment where you randomly split your users into two groups — Group A (the control, using the current system) and Group B (the treatment, using the new system) — and measure whether the new system produces better outcomes. It's the scientific method applied to product decisions: instead of guessing whether a change is an improvement, you measure it empirically with real users.

For traditional software, A/B tests are relatively straightforward: does the green button get more clicks than the blue button? For AI systems, A/B testing becomes significantly more complex. The "output" of an AI system is high-dimensional text, not a single binary action. What does "better" mean for a language model response? How do you measure it at scale? How do you handle the fact that AI outputs are non-deterministic? How do you account for users who can tell they're in an experiment and change their behavior?

Despite these challenges, A/B testing remains the gold standard for validating AI changes before full rollout. No amount of offline evaluation can perfectly predict how a model change will perform in the wild with real users asking real questions. The offline dataset is always a simplification of reality — A/B testing on live traffic is the ground truth for whether a change actually helps users.

## How It Works

```
A/B Test Architecture for an AI System
──────────────────────────────────────────────────────────────────
Incoming Request
      │
      ▼
┌─────────────────────────────┐
│   Traffic Splitter          │
│   hash(user_id) % 100       │
│   0-49 → Control (Model A)  │
│   50-99 → Treatment (Model B)│
└─────────────────────────────┘
      │                  │
      ▼                  ▼
  Control Pipeline   Treatment Pipeline
  (current system)   (new system)
      │                  │
      ▼                  ▼
  Response A         Response B
  (shown to user)    (shown to user)
      │                  │
      └─────────┬─────────┘
                ▼
       Log: {user_id, group, query,
             response, metrics, timestamp}
                │
                ▼
       Statistical Analysis
       (after N days)

Primary Metric: answer_acceptance_rate
Guard Rails: latency_p95, error_rate
Sample Size: ~1000 queries per group minimum
Duration: ≥ 14 days (capture weekly patterns)
──────────────────────────────────────────────────────────────────
```

**Statistical significance calculation:**

```
Two-proportion z-test for binary metrics (accept/reject):
  H0: p_control = p_treatment
  H1: p_treatment > p_control (one-tailed)

  z = (p_B - p_A) / sqrt(p_pool * (1 - p_pool) * (1/n_A + 1/n_B))
  p_pool = (x_A + x_B) / (n_A + n_B)

  Reject H0 if z > 1.645 (α=0.05, one-tailed)
  → treatment is statistically significantly better
```

## Why Google Cares About This

Google runs thousands of simultaneous A/B tests across its products. Every search ranking change, every Gemini response format update, every Workspace AI feature rollout goes through A/B testing. Senior engineers at Google are expected to design statistically rigorous experiments, understand the unique pitfalls of A/B testing AI systems (non-stationarity, novelty effects, position bias), and make principled shipping decisions from experimental results. "We just rolled it out to 100% because the offline metrics looked good" is not acceptable.

## Interview Questions & Answers

### Q1: How do you set up an A/B test for a RAG system change, step by step?

**Answer:** Setting up a rigorous A/B test for a RAG system change involves eight steps, and skipping any of them introduces bias or reduces the experiment's statistical power.

Step 1 — Define the hypothesis. "Switching from pure vector search to hybrid BM25+vector retrieval will increase answer acceptance rate by at least 5 percentage points." The hypothesis specifies the change, the direction, and the minimum meaningful effect size. This prevents post-hoc rationalization where you accept a 1% improvement because "it's statistically significant" even though it doesn't justify the engineering complexity.

Step 2 — Define primary metric and guardrails before running. Primary metric: answer acceptance rate (fraction of users who click "Approve recommendation" in ORCA's HITL interface, or equivalent engagement metric). Guardrails: P95 latency must not increase by more than 200ms; pipeline error rate must not increase by more than 0.5%. Guardrails prevent shipping something that improves quality metrics while silently degrading operational metrics.

Step 3 — Calculate required sample size. Use a power calculation with α=0.05, power=0.80, and the minimum detectable effect from Step 1. For binary metrics, you need roughly 1,600 samples per group to detect a 5-point difference from a 65% baseline. For continuous metrics, you need variance estimates from historical data.

Step 4 — Implement stable user assignment. Assign users to groups using `hash(user_id) % 100 < 50` (not random per request). The user_id hash ensures the same user always gets the same experience throughout the experiment — critical for measuring behavioral changes without carryover contamination.

Step 5 — Run for the required duration. Minimum 14 days for a business application to capture Monday-Friday and weekend patterns. If the initial analysis at 14 days shows strong significance, resist the temptation to call it early — optional stopping inflates false positive rates.

Step 6 — Analyze with appropriate statistical test. Two-proportion z-test for binary primary metrics. t-test or Mann-Whitney U for continuous metrics. Check for heterogeneous treatment effects across user segments (experienced users may react differently from new users).

Step 7 — Check guardrails before shipping. Even if the primary metric improved significantly, a guardrail failure (latency P95 increased 400ms) means investigating before shipping.

Step 8 — Make a shipping decision with documented rationale. "We ship because the primary metric improved by 6.2 pp (p=0.012, n=3,200 per group) and all guardrails passed." This documentation is reviewed in code review and creates an audit trail.

### Q2: What are the unique pitfalls of A/B testing AI systems that don't appear in traditional software A/B tests?

**Answer:** Several pitfalls are specific to AI A/B tests and can invalidate results even with perfect statistical methodology.

**Novelty effect**: users interact differently with something that feels new or better. If Treatment (new model) produces noticeably different-style responses, users may engage more enthusiastically at first simply because it's different — not because it's objectively better. This effect fades after 1–2 weeks. An experiment run for only 3 days will overstate the treatment effect. Run for at least 14 days to let novelty wash out.

**Non-stationarity**: unlike a button color test (the button is the same button every time), AI systems are sensitive to the query distribution, which can shift during the experiment. A new product launched mid-experiment, a news event that changes user queries, a seasonal inventory cycle in ORCA — all can shift the query distribution between when the experiment starts and when you analyze it. If the shift is large, your control and treatment groups may have seen systematically different queries, making the comparison unfair. Monitoring query distribution shift (embedding-space drift) during the experiment is good practice.

**Position bias**: in multi-document RAG, the position where the relevant document appears in the context affects LLM quality. If Treatment retrieves the same documents but in a different order, the quality difference may be due entirely to position, not to the retrieval algorithm change. This confounds interpretation.

**User learning effects**: in a multi-turn system, users learn how to interact with the AI over time. Control group users who have been using the system for two weeks know how to phrase queries effectively. New users assigned to Treatment may query differently, reducing the apparent quality of Treatment even if the model is objectively better.

**Indirect treatment effects**: in ORCA's HITL context, one human can be both a regular user (triggering pipeline runs) and the final decision-maker (approving/rejecting recommendations). If the Treatment produces better recommendations, the same human in Treatment may calibrate their expectations upward and become more critical, reducing the apparent acceptance rate. This feedback loop doesn't exist in traditional A/B tests.

**Small sample sizes**: enterprise AI systems often serve hundreds or thousands of users, not millions. With 200 pipeline runs per day and 14 days, you have 2,800 observations — enough to detect a 10+ point difference but not a 2–3 point difference. Know your power limits before expecting statistically significant results.

### Q3: What statistical considerations are unique to evaluating AI quality metrics in A/B tests?

**Answer:** AI quality metrics have statistical properties that differ from simple click-through rates, requiring adapted analysis approaches.

AI quality metrics are often **non-Gaussian and bounded**. LLM judge scores on a 1–5 scale are ordinal, not continuous. Applying a t-test (which assumes approximately normal distribution) is technically inappropriate. Use Mann-Whitney U test (non-parametric, no distribution assumptions) for continuous-looking but bounded quality scores. For binary metrics (accept/reject), use the two-proportion z-test.

**High variance** is common with AI quality metrics because query complexity varies enormously. A simple inventory replenishment query might always get a quality score of 4.5; a complex multi-SKU cross-supplier analysis might get scores ranging from 2.0 to 5.0. This variance increases required sample sizes compared to traditional product metrics. Stratify your analysis by query complexity bucket and check if the treatment effect is consistent across strata.

**Correlated observations** arise when the same user makes multiple queries. Standard statistical tests assume independent observations, but if one user contributes 50 queries, those 50 observations are correlated (the user's preferences, domain expertise, and query style are constant). The effective sample size is the number of unique users, not the total number of queries. Use cluster-robust standard errors or bootstrap the user level (sample users with replacement, not individual queries) when computing confidence intervals.

**Multiple comparison problem**: if you measure 10 different quality metrics in one A/B test, you'd expect one of them to show a statistically significant result by chance even if the treatment has no effect (at α=0.05, 10 tests ≈ 40% chance of at least one false positive). Use Bonferroni correction or the Benjamini-Hochberg procedure when testing multiple metrics simultaneously. Alternatively, pre-commit to one primary metric and treat the others as exploratory.

**Metric choice validity** is unique to AI: a metric that correlates with quality offline may not correlate with actual user value online. Thumbs-up rates may reflect response aesthetics rather than factual accuracy. Always validate that your chosen primary metric is meaningfully correlated with user satisfaction through a calibration study before committing it as the A/B test primary.

### Q4: How would you run an A/B test comparing two embedding models for ORCA's RAG system?

**Answer:** This is a particularly interesting A/B test because the treatment isn't the model the user sees directly — it's the retrieval system whose effects manifest in recommendation quality.

The experimental change: Control uses `nomic-ai/nomic-embed-text-v1.5` (current), Treatment uses `BAAI/bge-large-en-v1.5` (proposed upgrade). Both require re-indexing the ChromaDB corpus before the experiment starts — there's no way to run both embedding models in production without having two separate index stores. The architecture: deploy two instances, each with its own ChromaDB collection and its own embedding model, and route users to their assigned instance.

The primary metric: recommendation quality score. Since ORCA is a HITL system, the most direct measure is the human approval rate — do human reviewers approve the AI's reorder recommendation more often with Treatment? Secondary metrics: retrieval latency P95 (bge-large is a larger model and may be slower), pipeline success rate.

The challenge specific to ORCA: the number of daily pipeline runs may be small (dozens to hundreds, not thousands). With 50 runs/day, you need 64 days to get 3,200 observations for a 5-point effect size — an impractically long experiment. Options: (1) Run Layer 1 offline eval as a fast proxy and only run the A/B test if offline eval shows improvement (reduces the risk of wasting 64 days on a change that clearly doesn't work). (2) Use a synthetic traffic generator to simulate pipeline runs with realistic query distributions — run thousands of test runs quickly without real user impact, then validate with a shorter 2-week live test.

For pre-experiment validation: run the offline Layer 1 eval with both embedding models. If bge-large shows meaningfully higher recall@5 (say, +5 points) on the golden dataset, it's worth running the live A/B test. If they're within 1–2 points, the quality difference likely won't be detectable with ORCA's traffic volume, and the operational complexity isn't justified.

### Q5: How do you handle the situation where your A/B test shows the new model is better by primary metric but worse on guardrails?

**Answer:** A guardrail violation is a hard stop — it means the treatment cannot ship in its current form, even if the primary metric improved. Guardrails exist precisely to prevent shipping changes that have hidden costs or risks.

The typical scenario: Treatment improves answer quality score by 8 percentage points (primary metric win), but P95 pipeline latency increased from 12 seconds to 18 seconds (guardrail violated). This is a real tradeoff — better quality at the cost of 6 seconds of added latency.

The decision process: First, investigate why latency increased. In this case, `bge-large-en-v1.5` is a larger model than nomic-embed-text-v1.5 — the embedding inference at query time is slower. Is the 6-second increase in P95 latency coming from the embedding step specifically? Can it be mitigated by moving embedding to a GPU or by batching? If the latency increase is caused by something fixable (not an inherent property of the model choice), fix it and re-test.

Second, check if the guardrail threshold was appropriate. If you set P95 latency guardrail at 12s but the product team says 18s is still acceptable for a non-real-time inventory system, the guardrail should be revised — before running the test, or with documented post-hoc reasoning that will be scrutinized in review. Don't just waive the guardrail because you like the primary metric result.

Third, consider partial shipping. Deploy Treatment to a small segment of users (10%) where the quality improvement matters most (e.g., users triggering ESCALATE decisions on high-value inventory) and keep Control for the remaining 90%. This captures most of the quality gain while limiting exposure to the latency regression.

Fourth, if the guardrail truly cannot be met with the proposed change, document clearly: "We found that bge-large improves recommendation quality by 8 pp but increases latency beyond acceptable bounds. The change is blocked pending a latency solution." This creates a clear engineering roadmap item — make the model fast enough, then ship.

## Key Points to Say in the Interview
- Define primary metric and guardrails BEFORE running the experiment — no post-hoc metric selection
- Use hash(user_id) for stable treatment assignment, never randomize per-request
- Run for at least 14 days to capture weekly patterns and let novelty effects wash out
- AI-specific pitfalls: novelty effects, non-stationarity, user learning, small sample sizes in enterprise
- Cluster at the user level when computing statistics — queries from the same user are correlated
- A guardrail violation is a hard stop — don't ship even if the primary metric improved

## Common Mistakes to Avoid
- Running experiments for only 3–5 days and calling significance early — misses novelty effects and weekly cycles
- Randomizing per-request instead of per-user — carryover contamination destroys the experiment
- Ignoring the multiple comparisons problem when reporting 10 metrics and highlighting the one that's significant
- Setting guardrail thresholds after seeing results — this is HARKing (Hypothesizing After Results are Known)
- Not documenting the decision rationale — future engineers won't know why a particular model was chosen

## Further Reading
- [Trustworthy Online Controlled Experiments (book)](https://experimentguide.com/) — The definitive reference on A/B testing by Microsoft/Google veterans (Kohavi, Tang, Xu)
- [Overlapping Experiment Infrastructure at Google (paper)](https://storage.googleapis.com/pub-tools-public-publication-data/pdf/36500.pdf) — How Google runs thousands of simultaneous experiments without interference
- [Statistical Significance Explained for A/B Testing](https://www.evanmiller.org/ab-testing/sample-size.html) — Interactive sample size calculator with clear explanation of power analysis
- [Pitfalls of A/B Testing in AI Products (arXiv)](https://arxiv.org/abs/2206.01910) — Academic treatment of AI-specific A/B testing challenges
- [LangSmith Experiments](https://docs.smith.langchain.com/evaluation/concepts#experiments) — How to run structured experiments comparing LLM configurations in LangChain/LangGraph systems
