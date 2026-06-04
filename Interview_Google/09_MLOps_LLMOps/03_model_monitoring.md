# Model Monitoring: Watching Models in Production

## What Is It? (Plain English)

Imagine you hire a new analyst who performs brilliantly during their first month. Six months later, you notice their recommendations have been slightly off. You eventually realize the world changed — a new competitor entered, seasonality shifted, customer behavior evolved — and the analyst's mental model, learned six months ago, is now out of date. ML models have the exact same problem, except they can't tell you when they're confused. They silently produce worse outputs while looking perfectly healthy from a system perspective (no errors, no crashes, normal latency).

Model monitoring is the practice of watching production models continuously to catch this kind of degradation before it causes real business harm. It answers two questions: "Is the data arriving today similar to the data the model was trained on?" and "Are the model's outputs still trustworthy?" When the answer to either is "no," the model needs to be retrained or replaced.

The unique danger in AI systems is what's called a "silent failure." A server that crashes makes noise — alerts fire, on-call engineers page. A model that starts giving subtly wrong inventory recommendations makes no noise at all. Orders go slightly wrong, stockouts tick up 2%, margins erode quietly. Months later someone runs an analysis and asks "why has reorder accuracy been declining?" Model monitoring is your early warning system to prevent that discovery from being a postmortem rather than a timely intervention.

## How It Works

```
Production Traffic
        │
        ▼
┌───────────────────────────────────────────────────────┐
│              DATA DRIFT MONITOR                       │
│  Compares:  Training data distribution                │
│                    vs                                 │
│             Today's incoming data distribution        │
│                                                       │
│  Tests: KS test, PSI, chi-squared for categoricals   │
│  Alert: drift score > threshold                       │
└───────────────────────┬───────────────────────────────┘
                        │
        ┌───────────────▼───────────────┐
        │     PREDICTION DRIFT MONITOR  │
        │  Watches: distribution of     │
        │  model outputs over time      │
        │  Alert: if prediction dist.   │
        │  shifts significantly         │
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼───────────────┐
        │     CONCEPT DRIFT MONITOR     │
        │  Compares: model prediction   │
        │  vs ground truth labels       │
        │  (when labels arrive later)   │
        │  Alert: accuracy below SLA    │
        └───────────────┬───────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  Alerting Layer │
              │  PagerDuty /    │
              │  Slack / Email  │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  Retraining     │
              │  Pipeline       │
              │  (manual or     │
              │  automated)     │
              └─────────────────┘
```

**Types of Drift:**
- **Data drift** (also called covariate shift): The *inputs* to the model change. Example: your demand forecaster was trained when COVID lockdowns were in place; now purchase patterns have normalized.
- **Concept drift**: The *relationship* between inputs and outputs changes. Example: "high social media mention" used to predict high demand; after a boycott campaign, it now predicts low demand.
- **Prediction drift**: The model's *output distribution* shifts. Example: the model starts predicting "ESCALATE" far more often than historically. May be caused by data drift or concept drift.

## Why Google Cares About This

Google's Search ranking models, YouTube recommendation engines, and Ads targeting systems all degrade if the world changes and models don't. Google has invested heavily in automated retraining systems precisely because manual monitoring at their scale is impossible. In a senior interview, they want to know if you understand that a model is not a static asset but a living component that requires continuous observation. They also want to see that you understand the business impact — a degraded model costs money (wrong inventory orders, missed ad conversions, worse search results) — and that you can quantify when retraining is warranted by connecting model metrics to business metrics.

## Interview Questions & Answers

### Q1: What is data drift and how do you detect it statistically?

**Answer:** Data drift occurs when the statistical properties of the model's input features change after deployment. The model was optimized for the training data distribution; if production data diverges significantly, the model's learned patterns no longer apply. A simple example: a fraud detection model trained when transactions averaged $50 starts seeing average transactions of $200 after a period of inflation — the feature distribution has shifted.

The most common statistical test for detecting drift in continuous features is the **Kolmogorov-Smirnov (KS) test**. It measures the maximum difference between two cumulative distribution functions (CDFs) — the training distribution and the production distribution. A KS statistic close to 0 means the distributions are similar; close to 1 means they're very different. The test produces a p-value; if p < 0.05, you conclude drift is statistically significant.

For categorical features (like "product category" or "region"), the **chi-squared test** is appropriate — it tests whether the frequency distribution of categories in production matches what was seen in training. Another popular metric is **Population Stability Index (PSI)**, borrowed from credit risk modeling. PSI buckets the feature values and computes a weighted divergence score: PSI < 0.1 means no significant drift, 0.1–0.25 is moderate drift warranting investigation, PSI > 0.25 is severe drift requiring action.

For LLM systems, traditional statistical drift tests don't directly apply — there are no numeric feature vectors to test. Instead, you monitor semantic drift: does the topic distribution of incoming queries match the training distribution? Tools like embedding-based clustering can detect when users are asking about new topics the model wasn't trained on, which shows up as query embeddings falling outside the convex hull of training embeddings.

### Q2: What is concept drift and why is it harder to detect than data drift?

**Answer:** Concept drift means the underlying relationship between inputs and outputs has changed — even if the inputs themselves look the same. The model learned a rule that was once true but is no longer. For example, a sentiment classifier trained before a company scandal might have learned that mentions of the brand are positive signals; after the scandal, those same mentions are negative. The input (text containing the brand name) is the same; the correct output has flipped.

Concept drift is harder to detect than data drift because you need *ground truth labels* to observe it, and labels often arrive with a delay. In fraud detection, ground truth is "was this transaction actually fraud?" — which you don't know until a customer files a dispute, weeks later. In demand forecasting, ground truth is "did the product actually sell?" — known only at end of day or end of week. The monitoring system must be designed to hold predictions, wait for labels to arrive, then retrospectively compute accuracy. This creates a lag in your drift detection.

The detection approach is to track accuracy metrics (F1, RMSE, accuracy) over sliding time windows and compare to the baseline established right after training. A healthy model fluctuates within a narrow band; concept drift causes a trend downward. The tricky part is distinguishing concept drift from seasonal patterns — a sales model's accuracy naturally drops slightly in atypical weeks (holidays, extreme weather). You need to account for this with seasonally-adjusted baselines.

For AI agent systems like ORCA, concept drift manifests differently. The agents use LLMs with RAG, so "concept drift" might mean the company's procurement policies have changed but the policy documents in the RAG index haven't been updated. The agents start giving recommendations based on outdated policy. The detection signal is human override rate — if agents are escalated or overridden more frequently, that's a proxy label for degraded accuracy.

### Q3: What are silent failures in AI and how do you build monitoring to catch them?

**Answer:** A silent failure is when an AI system is technically operational (no errors, no crashes, normal response times) but is producing outputs that are subtly, harmfully wrong. The term "silent" refers to the fact that standard infrastructure monitoring — CPU, memory, error rate, latency — shows nothing unusual. The system appears healthy while quietly misbehaving.

A classic example: an image classification model in a medical system starts slightly under-classifying malignant tumors because the camera hardware was upgraded and the new camera produces slightly different color profiles. The model runs fine and returns results at normal speed; the error rate for benign images is unchanged. Only among a specific subgroup (malignant cases) does accuracy quietly degrade — potentially for weeks before clinical outcomes data accumulates enough to trigger suspicion.

Building monitoring to catch silent failures requires moving beyond infrastructure metrics to *business metric proxies*. For ORCA, you'd monitor: What fraction of auto-execute recommendations were later manually overridden by warehouse managers? What is the trend in stockout events for SKUs the system classified as "safe"? Is the escalation rate to human review consistent with historical patterns? A spike in overrides or a drift in escalation rate is a proxy signal that something in the agent pipeline has degraded.

For LLM-specific silent failures, you also monitor output quality proxies: response coherence (does the output parse as valid JSON if it's supposed to?), output length distribution (outputs suddenly much shorter may indicate the model is truncating thought), and factual grounding rate (is the model citing the retrieval context, or making things up?). Tools like Evidently AI and WhyLabs provide dashboards for this kind of behavioral monitoring.

```
Example: ORCA Silent Failure Detection
─────────────────────────────────────────
Metric               Normal Range    Alert Threshold
─────────────────────────────────────────
ESCALATE rate        15–25%          >40% or <5%
Human override rate  5–10%           >20%
Stockout after AUTO  <2%/week        >5%/week
JSON parse failures  <0.1%           >1%
─────────────────────────────────────────
```

### Q4: How do you decide when to retrain a model?

**Answer:** Retraining has a cost (compute time, engineer time, validation time) and a benefit (improved accuracy). The decision framework is: retrain when the expected benefit exceeds the expected cost, with a safety margin for the risk of a worse retrained model.

The most principled approach is **scheduled retraining with drift-triggered acceleration**. By default, retrain on a fixed cadence (daily, weekly, monthly) based on how fast your domain changes. A model predicting next week's sales in a stable retail category might need retraining monthly. A model predicting ride-share demand in a city needs retraining daily because patterns change with events, weather, and seasons. The cadence is domain-specific, determined by historical analysis of how fast your model's accuracy degrades over time.

When drift is detected before the scheduled retraining date, accelerate the trigger. If PSI > 0.25 on a key feature, retrain immediately — don't wait for the monthly schedule. This requires an automated retraining pipeline (exactly what CI/CD for ML provides) so retraining isn't a manual effort.

One important trap to avoid is **retraining too eagerly**. If a model retrains on the last 7 days of data every day, it will quickly overfit to recent patterns and become fragile to one-off events. A major promotion creates a spike; retraining on spike data teaches the model that spikes are normal; the model then over-orders stock the following week. The solution is to retrain on a rolling window of sufficient length (30–90 days) that includes normal variation, and to flag outlier events in the training data so the model learns to discount them.

For LLM systems in ORCA, "retraining" usually means refreshing the RAG index (adding new policy documents, re-chunking if policy language changed) or updating few-shot examples in prompts. Full LLM fine-tuning is expensive and rarely needed for internal tools — prompt and retrieval updates are the standard levers.

### Q5: What monitoring dashboards would you build for an AI inventory management system like ORCA?

**Answer:** I would build monitoring in three layers: infrastructure, model behavior, and business outcomes. Each layer has different audiences and alerting urgencies.

The infrastructure layer is the standard devops dashboard: API latency (P50, P95, P99), error rate, request volume, database query times, and LLM API response times and error rates. For ORCA specifically, I'd add: Groq API call success rate (it has strict rate limits on the free tier), pipeline completion rate (what fraction of triggered pipelines reach a final state), and pipeline stage timing (which agent is the bottleneck). This layer alerts within seconds and wakes up on-call engineers.

The model behavior layer watches the AI decision patterns: ESCALATE vs AUTO_EXECUTE vs SUSPEND distribution over time, distribution of recommended order quantities (are they realistic?), RAG retrieval confidence scores, and LLM output parse failure rate. These metrics should be stable over time; sudden shifts indicate drift or prompt degradation. Alerts here go to the ML engineer with an SLA of minutes to hours, not seconds.

The business outcomes layer closes the feedback loop: stockout rate per SKU class (A, B, C), over-order rate (inventory that expires without sale), human override rate on auto-execute decisions, and time-to-decision (how quickly the pipeline resolves a stock alert). These are weekly trend metrics reviewed by the product manager. A deteriorating model shows up here as slowly worsening KPIs — this is your early warning system for silent failures that the model behavior layer missed.

```
ORCA Monitoring Dashboard (3-layer view)
─────────────────────────────────────────────────────────
Layer 1: Infrastructure (refresh: 10s, alert: page)
  • API latency P99   ████████░░░░  120ms  (SLA: 200ms)
  • Error rate        ██░░░░░░░░░░  0.3%   (threshold: 1%)
  • Groq API errors   █░░░░░░░░░░░  0.1%   (threshold: 5%)

Layer 2: Model Behavior (refresh: 1m, alert: slack)
  • ESCALATE rate     ████░░░░░░░░  18%    (normal: 15-25%)
  • JSON parse fail   █░░░░░░░░░░░  0.05%  (threshold: 1%)
  • RAG coverage      ████████████  95%    (threshold: 80%)

Layer 3: Business Outcomes (refresh: daily, alert: email)
  • Stockout rate     ██░░░░░░░░░░  1.2%   (target: <2%)
  • Override rate     ███░░░░░░░░░  8%     (threshold: 20%)
  • Order accuracy    ████████░░░░  91%    (target: >90%)
─────────────────────────────────────────────────────────
```

## Key Points to Say in the Interview

- Silent failures are the unique danger in ML monitoring — the system looks healthy while producing subtly wrong outputs
- Distinguish data drift (input distribution changes), concept drift (input-output relationship changes), and prediction drift (output distribution changes)
- Statistical tests: KS test and PSI for continuous features, chi-squared for categorical features
- Ground truth delay is what makes concept drift hard to detect — your monitoring system must accommodate label latency
- Retraining cadence should be domain-driven, with drift-triggered acceleration
- For LLM systems, monitor proxy metrics (override rate, parse failure rate, retrieval coverage) because traditional feature-based drift tests don't apply
- Always connect model metrics to business metrics — monitoring accuracy in isolation misses the business impact

## Common Mistakes to Avoid

- Do NOT say monitoring is just about error rates and latency — this completely misses the concept of silent failure
- Do NOT conflate data drift and concept drift — they have different detection methods and different remediation strategies
- Do NOT suggest retraining on a fixed short window (e.g., last 7 days) without acknowledging the overfitting risk
- Do NOT forget to mention ground truth delay as a challenge — it's a common interview follow-up
- Do NOT describe monitoring as a one-time setup — it requires tuning thresholds over time as you learn what "normal" looks like for your specific system

## Further Reading

- [Evidently AI: ML Monitoring Guide](https://www.evidentlyai.com/blog/ml-monitoring-metrics) — Comprehensive overview of what to monitor and how to set up drift detection in practice
- [Google Cloud: Model Monitoring for Vertex AI](https://cloud.google.com/vertex-ai/docs/model-monitoring/overview) — Google's production-grade model monitoring service; useful for understanding what a top-tier monitoring solution includes
- [WhyLabs Data & AI Observatory](https://whylabs.ai/model-monitoring) — One of the leading SaaS monitoring platforms; their documentation explains monitoring concepts clearly
- [Chip Huyen: Designing Machine Learning Systems (Chapter 8)](https://www.oreilly.com/library/view/designing-machine-learning/9781098107956/) — The gold standard ML systems textbook; Chapter 8 covers data distribution shifts and monitoring in depth
- [Evidently AI: Data Drift Detection Methods](https://www.evidentlyai.com/blog/data-drift-detection-large-datasets) — Technical comparison of statistical tests for drift detection (KS, PSI, Jensen-Shannon divergence)
