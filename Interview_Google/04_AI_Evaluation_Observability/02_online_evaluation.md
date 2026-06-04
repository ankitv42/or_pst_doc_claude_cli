# Online Evaluation

## What Is It? (Plain English)

Online evaluation means measuring AI quality while the system is running in production, serving real users. Unlike offline evaluation (which tests pre-built scenarios in a controlled environment), online evaluation captures what's actually happening — how real users with real, unpredictable queries interact with the system, and whether the system's quality holds up under production conditions.

The core challenge is that with AI systems, you usually don't have an immediate "ground truth" for whether an answer was correct. If a user types a question and your RAG system responds, how do you know if the answer was good? The user might not tell you. You need to infer quality from indirect signals — did they read the response fully (scroll depth)? Did they click a link in the answer (engagement)? Did they ask a follow-up question (which often means the first answer was insufficient)? Did they thumbs-up or thumbs-down (explicit feedback)?

Online evaluation also catches failure modes that offline evaluation misses. Your golden test dataset is, by definition, finite and sampled from what you expected users to ask. Production users will surprise you — they'll ask questions in accents your offline eval never covered, they'll paste code snippets when you expected English sentences, they'll ask multi-turn questions that break assumptions in your system prompt. Online eval is the only way to discover these failure modes.

## How It Works

```
Online Evaluation Architecture
─────────────────────────────────────────────────────────────────
Production Traffic
  User Query
      │
      ▼
┌─────────────────┐
│  AI System      │
│  (ORCA agent    │──── logs every call ────► Observability
│   pipeline)     │                           Platform
└─────────────────┘                           (LangSmith, etc.)
      │
      ▼
  AI Response
      │
      ├─── Implicit Signals ──────────────────────────────────┐
      │    • Did user immediately rephrase? (reformulation)    │
      │    • Did user click recommended action? (engagement)   │
      │    • Session duration, scroll depth                    │
      │                                                        │
      ├─── Explicit Signals ──────────────────────────────────┤
      │    • Thumbs up / thumbs down                          │
      │    • "Was this helpful?" (1-5 stars)                   │
      │    • Bug report / feedback form                        │
      │                                                        │
      └─── Automated Signals ─────────────────────────────────┘
           • Faithfulness check (LLM judge on sampled responses)
           • Latency (P50, P95, P99)
           • Error rate (pipeline failures, fallback triggers)

All signals feed into dashboards and alerting systems
─────────────────────────────────────────────────────────────────
```

**Shadow mode** is a special online eval technique: run a new model version in parallel with the production model, serving both to every user but only showing the production model's response. The shadow model's responses are logged and scored offline. This lets you evaluate a new version against real production queries without any user impact.

**Canary deployment** serves the new model to a small fraction of users (e.g., 1–5%) and monitors quality metrics on both groups. If the new model's metrics are comparable or better after statistical validation, the rollout proceeds.

## Why Google Cares About This

Google runs hundreds of experiments in production simultaneously via its A/B testing infrastructure. Online evaluation is the final arbiter of whether an AI change ships. Senior engineers are expected to understand implicit signals, shadow mode deployments, and how to detect quality degradation in live traffic before it affects the majority of users. The ability to design an online monitoring strategy — not just say "we'll look at thumbs up/down" — is a signal of production engineering experience.

## Interview Questions & Answers

### Q1: What is the difference between offline and online evaluation, and why do you need both?

**Answer:** Offline evaluation tests a system against a curated, static dataset in a controlled environment. Online evaluation observes a system against the live, unpredictable stream of production traffic. They serve complementary purposes and catch different classes of problems.

Offline eval excels at catching regressions before deployment. If you change your chunking strategy and Recall@10 drops from 87% to 71% on your golden dataset, you catch this in CI before any user is affected. Offline eval is also repeatable — the same test on the same version always produces the same result (modulo LLM non-determinism), which makes it useful for version-to-version comparisons.

Online eval excels at catching distribution shift — when the real user query distribution differs from your golden dataset. Suppose your golden dataset consists of English supply chain questions, but 30% of your production users are asking in Spanish. Your offline eval would show 100% pass rate; your online eval would show 30% of responses returning unhelpful replies. This kind of failure is invisible to offline eval.

Online eval also catches emergent failure modes that nobody anticipated at design time. A user might discover that pasting a very long JSON blob as a query causes the pipeline to time out. Another might find that questions about competitors trigger unexpected responses. These edge cases don't appear in a thoughtfully constructed golden dataset because you didn't think to include them — but they appear in production.

The practical workflow: use offline eval as a CI gate (must pass before deployment), and use online eval as a monitoring system (detects problems after deployment). If online metrics degrade, investigate using trace data, identify the failure pattern, add it to the golden dataset, fix the system, and confirm the fix with offline eval before re-deploying.

### Q2: How do you detect AI quality degradation in live traffic without explicit user feedback?

**Answer:** Most users don't give explicit feedback — they simply leave if the answer was bad. Implicit signal extraction is the art of inferring quality from behavioral signals that users produce naturally without being asked.

The most powerful implicit signal is **query reformulation rate**: if a user receives a response and immediately asks a follow-up question that is semantically a rephrasing of the original question, the first answer probably failed. In a RAG system, you'd compute this as: "user asked Q1, received answer, then asked Q2 where embedding_similarity(Q1, Q2) > 0.85 within the same session." High reformulation rate is a leading indicator of low answer quality.

**Session abandonment after first response** is a blunter signal. If users consistently read the first response and leave immediately (especially for a system like ORCA where the expected flow is query → recommendation → action), that's a sign the response wasn't actionable.

**Action-not-taken rate** is specific to systems with downstream actions. In ORCA, the pipeline recommends a reorder decision. If the human reviewers consistently reject the recommendation (not due to business reasons but due to quality issues), that's an online quality signal. Monitoring the approval/rejection ratio on the HITL approve/reject endpoint over time would surface a degradation in recommendation quality.

**Automated sampling** can add LLM-judge scoring to a random 5–10% of production traffic. Take a production query and the system's response, run a faithfulness check or relevance check using a strong LLM, and log the score. This gives you a continuous quality metric without evaluating every single call. Alert if the rolling average faithfulness score drops below a threshold.

Latency is an indirect quality proxy too: if P95 pipeline latency suddenly jumps, something changed in the system (model serving slower, a new code path is taking longer, external API is degraded). Quality often co-degrades with latency increases.

### Q3: What is shadow mode and when would you use it for an AI system?

**Answer:** Shadow mode (also called shadow deployment or dark launching) is a technique where a new version of a model or pipeline runs in parallel with the production system on all live traffic, but its outputs are never shown to users — they're logged and evaluated offline. The production system handles user interactions normally; the shadow system quietly processes the same inputs and records what it would have said.

Shadow mode is used in two scenarios. First, when evaluating a significant change to the AI system where offline eval alone is insufficient to assess the change's impact. Maybe you're switching from Groq to a different LLM provider, or upgrading your embedding model, or redesigning your chunking strategy. Your golden dataset of 100 queries might not capture the long tail of production queries. Shadow mode lets you evaluate the new system on thousands of real production queries before exposing any user to it.

Second, shadow mode is used to calibrate your offline evaluation. By comparing shadow mode outputs (on real production traffic) to your offline eval results, you can determine how representative your golden dataset is. If the offline eval shows 90% quality but the shadow mode scores show 65% quality on production traffic, your golden dataset is not representative and needs to be updated with production query patterns.

The operational requirements for shadow mode: your architecture must support forking every request to two handlers (the production model and the shadow model) without blocking the user response on the shadow model's completion. Typically the shadow call is async and fire-and-forget from the user's perspective. The shadow system's outputs must be logged with enough context (input, output, timestamp, user_id if available) to enable offline scoring.

For ORCA, implementing shadow mode would mean: when a new version of the LangGraph pipeline is ready, deploy it alongside the production version, fork all `/pipeline/trigger` requests to both, but only return the production version's results to the dashboard. Log the shadow version's agent decisions and recommendations. After 48 hours, score the shadow outputs using the Layer 2 LLM judge eval and compare the pass rates.

### Q4: How do you design an A/B test for a RAG system change?

**Answer:** An A/B test for a RAG system change follows the same general framework as any A/B test — split traffic, measure the difference, determine statistical significance — but with challenges specific to AI systems.

First, define the primary metric before running the test. For a RAG system, good candidates: user satisfaction score (explicit feedback), answer acceptance rate (user clicked the suggested action), reformulation rate (lower is better), or LLM judge quality score on a sample. Picking the metric after seeing data is p-hacking.

Second, determine the minimum detectable effect and required sample size. If your baseline answer acceptance rate is 65% and you want to detect a 5 percentage point improvement with 80% statistical power at p<0.05, a power calculation gives you the required number of queries. For AI systems, variance tends to be high (users have diverse query types), so sample sizes tend to be larger than for simpler product changes.

Third, ensure proper randomization. Users should be consistently assigned to the same treatment group throughout the experiment (not randomized per-request). If the same user gets Control on query 1 and Treatment on query 2, you risk carryover effects (user learned from the Treatment response, affecting their next Control query). Use a user_id hash for stable assignment.

Fourth, run the test long enough to capture weekly cycles. User behavior on Monday (business users checking inventory) may differ from Thursday. Run for at least two full weeks before making a shipping decision.

AI-specific pitfall: **novelty effect**. Users may interact differently with a clearly "better" new system simply because it feels new, not because it's genuinely better. This effect fades after 1–2 weeks, which is another reason to run tests for at least two weeks.

Second AI-specific pitfall: **non-stationarity**. The data distribution can shift during the test — new types of inventory alerts, new suppliers added to the database, seasonal changes in demand patterns. If distribution shifts happen during your A/B test, your results may be confounded.

### Q5: How would you set up online monitoring for ORCA in production?

**Answer:** ORCA is currently deployed on Render with LangSmith tracing configured. A production monitoring strategy would build on this foundation to add quality monitoring on top of the existing operational metrics.

Operational monitoring (already achievable with Render's built-in metrics and LangSmith): API request rate, P50/P95/P99 latency per endpoint, pipeline success rate (fraction completing without the CrewAI fallback error), HITL escalation rate (fraction of pipelines that route to ESCALATE), and error rates by exception type.

Quality monitoring (requires additional implementation): Sample 10% of production pipeline runs and score them with a lightweight faithfulness check — retrieve the context that was passed to the LLM, extract the recommendation text, and run a fast NLI classifier to check if the recommendation is supported by the context. Log the faithfulness score per run. Alert if the 7-day rolling average drops below 0.80.

Leading indicators of degradation to monitor: the Agent 1 CrewAI fallback rate (currently 100% due to the known `cache_breakpoint` bug — if this changes it signals a Groq API behavior change), retrieval latency P95 (if ChromaDB or the cross-encoder slows down, retrieval degrades), and LLM token usage per run (a sudden spike in tokens may indicate a prompt injection or unexpected input type).

Human feedback loop: add a lightweight thumbs-up/thumbs-down to the ORCA dashboard's recommendation display. Even 5 explicit annotations per day, persisted to a feedback table in `orca.db`, provides a weekly quality signal that can be correlated with the automated metrics to validate that the automated signals are meaningful.

## Key Points to Say in the Interview
- Online eval catches distribution shift — real users diverge from your offline golden dataset in ways you can't fully anticipate
- Implicit signals (reformulation rate, session abandonment, action-not-taken) are usually more abundant than explicit feedback
- Shadow mode evaluates a new system on 100% of production traffic with zero user impact
- A/B tests for AI systems need longer run times (2+ weeks) to account for novelty effects and weekly cycles
- Always define your primary metric before running any test — no post-hoc metric selection
- Operational metrics (latency, error rate) are leading indicators — quality degradation often shows in latency first

## Common Mistakes to Avoid
- Relying only on thumbs up/down for quality signal — most users never click, so it's a biased sample
- Running A/B tests for only 3 days — misses weekly cycles and novelty effects
- Using per-request randomization instead of per-user randomization — causes carryover contamination
- Ignoring implicit signals entirely because they're "indirect" — they're abundant and unbiased
- Deploying a new model version to 50% of traffic immediately instead of starting with 1–5% canary

## Further Reading
- [A/B Testing at Airbnb](https://medium.com/airbnb-engineering/https-medium-com-jonathan-parks-scaling-knowledge-at-airbnb-875d73eff091) — Real-world lessons on running A/B tests at scale including AI features
- [Evidently AI: LLM monitoring in production](https://www.evidentlyai.com/blog/llm-monitoring-production) — Open-source framework for monitoring ML/LLM systems with drift detection
- [LangSmith Monitoring Docs](https://docs.smith.langchain.com/monitoring) — How to set up online quality monitoring for LangChain-based systems
- [Google's ML Test Score](https://storage.googleapis.com/pub-tools-public-publication-data/pdf/aad9f93b86b7addfea4c419b9100c6cdd26cacea.pdf) — Google's rubric for production ML system readiness including monitoring requirements
- [SelfCheckGPT (arXiv)](https://arxiv.org/abs/2303.08896) — Technique for automated hallucination detection without reference answers, applicable for online scoring
