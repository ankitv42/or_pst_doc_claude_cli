# Model Versioning: Managing Multiple Versions of a Model in Production

## What Is It? (Plain English)

Software development has had version control (Git) for over 20 years — every change is tracked, every previous version is recoverable, and you can run old and new versions side by side to compare them. ML teams discovered painfully that models need the same treatment. Without versioning, you end up with a production model that no one remembers how to reproduce, a folder named "model_v3_FINAL_use_this_one.pkl" on a shared drive, and no safe way to test a new model before exposing all users to it.

Model versioning is the practice of treating every trained model artifact as a uniquely identified, immutable version with tracked metadata. Version 7 of your demand forecaster is a specific model trained on a specific dataset with specific hyperparameters, evaluated with specific metrics. It can be promoted to "Production," demoted to "Archived," or rolled back to at any point. No version is ever overwritten or lost.

The lifecycle has named states that parallel software release management: when a new model is registered, it starts in "Staging" where integration tests run. If it passes, it gets promoted to "Production" — becoming the version all serving infrastructure loads. The previous Production model moves to "Archived" — still retrievable for rollback, but no longer serving traffic. This is the same promotion pipeline used by software teams for decades, finally applied to ML artifacts.

## How It Works

```
Model Training Run (experiment tracked in MLflow)
       │
       │  Evaluation: new model beats champion by > 1%?
       ├── NO  ─────────────────► Discard (not registered)
       │
       └── YES ─────────────────► Register in Model Registry
                                         │
                                   version = N
                                   status = "None" (default)
                                         │
                           ┌────────────▼────────────┐
                           │        STAGING          │
                           │  Integration tests run  │
                           │  Shadow mode traffic    │
                           │  Canary 5% evaluation   │
                           └────────────┬────────────┘
                                        │
                            Pass all gates?
                                        │ YES
                           ┌────────────▼────────────┐
                           │       PRODUCTION        │ ◄── Serving infrastructure
                           │  (previously Production  │     loads this version
                           │   moves to Archived)    │
                           └─────────────────────────┘
                                        │
                           ┌────────────▼────────────┐
                           │        ARCHIVED         │
                           │  (recoverable for       │
                           │   rollback at any time) │
                           └─────────────────────────┘

Rollback:
  Production v8 degrading → run one command → v7 goes back to Production
```

**Champion-Challenger Testing:**
The "champion" is the current Production model. A "challenger" is a newly trained candidate. Challenger gets a small percentage of traffic (5–20%) routed to it. Both run simultaneously. After sufficient traffic and time, metrics decide: if challenger is statistically better, it becomes the new champion. If not, it's archived. This is safer than a binary "replace" because the old champion is still serving the majority of traffic during evaluation.

**Shadow Mode:**
Even more conservative than challenger. The shadow model receives all requests, runs inference, and logs its outputs — but its outputs are never shown to users. Only the champion's outputs are used. Shadow results are compared to champion results and ground truth labels. This lets you evaluate a new model against 100% of real production traffic with zero user impact.

## Why Google Cares About This

At Google scale, a model registry is the coordination mechanism between dozens of data science teams and the serving infrastructure. Without a registry, the serving team would need to manually manage which model files are deployed where — an error-prone, unscalable process. The registry also provides the audit trail that compliance, security, and debugging require: "which model was serving users on November 15th, and what data was it trained on?" In a senior interview, model versioning knowledge signals that you think about ML deployment as a disciplined engineering process with clear rollback and audit capabilities — not as ad hoc file management.

## Interview Questions & Answers

### Q1: Walk me through the model lifecycle in a production ML system from registration to retirement.

**Answer:** The lifecycle begins when an experiment completes training. The run's metrics are compared against the current production model's metrics — the "champion." If the new model doesn't beat the champion by at least the minimum meaningful threshold (often 0.5–1% relative improvement, depending on how mature the model is and how expensive retraining is), it simply isn't registered. This avoids cluttering the registry with noise.

When a model passes the threshold, it's registered in the model registry with a version number and an initial status of "None" (MLflow's default) or "Staging" (Vertex AI). At this point, the model is available for evaluation but receives no production traffic. Automated integration tests run: does the model produce valid output format? Does it handle edge cases (empty input, missing features) without crashing? Are the prediction distributions reasonable? If any test fails, the model stays in Staging and engineers investigate.

If tests pass, a human reviewer (or in fully automated systems, a CI gate) promotes the model to "Production." The serving infrastructure — which is configured to always load the model tagged "Production" — picks up the new version at its next load or restart. The previously Production model is automatically moved to "Archived" status.

Retirement happens when the model is old enough that it's no longer realistic to roll back to it — perhaps because the data pipeline that produced its training data no longer exists, or because it's 50 versions stale. At that point, the model is deleted from the registry. For regulated industries, model artifacts are often retained for compliance purposes even after retirement from the registry (e.g., financial services may require retaining any model that influenced a credit decision for 7 years).

### Q2: What is shadow mode deployment and when would you use it over a canary release?

**Answer:** Shadow mode (also called shadow deployment or dark launching) runs a new model in parallel with the production model. Every incoming request is duplicated: one copy goes to the production model (whose output is served to users), and one copy goes to the shadow model (whose output is logged but silently discarded). Users never see shadow model outputs. The shadow model runs on real production traffic, at full scale, with zero user impact.

The key advantage over canary is risk. In a canary release, 5% of users receive the new model's outputs. If the new model is wrong in a harmful way — for a medical diagnosis system, a financial recommendation system, or ORCA's inventory decisions — 5% of users are harmed before you catch it. In shadow mode, zero users are harmed because the shadow model's outputs are never acted upon.

Shadow mode is the right choice when: the cost of a wrong model decision is high (healthcare, finance, critical infrastructure), the model has never been tested in production before (first deployment of a completely new model type), or there is significant uncertainty about whether the model will behave in production the way it did in offline evaluation. The tradeoff is cost: running two models for every request roughly doubles the serving infrastructure cost.

The operational challenge of shadow mode is the evaluation loop. You need ground truth labels to evaluate shadow outputs. In ORCA, shadow outputs for a supply replenishment model would be compared against actual reorder outcomes — did the shadow recommendation, had it been followed, lead to a better or worse outcome than the champion's recommendation? This requires tracking both recommendations and their counterfactual outcomes, which is a non-trivial data engineering effort.

### Q3: Explain rollback in a model registry — what does it actually involve and how fast can it happen?

**Answer:** Rollback means promoting a previously archived model version back to Production status and demoting the current Production model. In a well-designed system, this is a single command: `mlflow models transition --model-name forecast_demand --version 7 --stage Production`. The registry updates the version tag, and serving infrastructure that checks the registry on each request will pick up the change within seconds (or at the next load, if model weights are loaded once at startup).

The key insight is that rollback speed depends on how serving infrastructure is configured. If the serving process loads the model artifact once at startup and holds it in memory, rollback requires either restarting the process (container restart, which can take 30–90 seconds) or building hot-reload logic. If the serving process checks the registry on every request (less common, too slow for low-latency services), rollback is instantaneous.

What makes rollback fail in practice is almost never the registry or serving infrastructure — it's data compatibility. If the new model expects different input features than the old model (e.g., you added a new feature between v7 and v8), rolling back to v7 while production continues sending v8's feature format will break v7. This means feature schema changes must be backward-compatible, or rollback must be accompanied by a feature pipeline rollback. This is why model versioning and data versioning are coupled — a complete rollback package includes the model version, the feature definition version, and the data pipeline version.

For ORCA, rollback is simpler because the "model" is a Groq API prompt system, not a retrained artifact. "Rolling back" means reverting the git commit that changed `agents/prompts.py` — a standard git revert. The key metrics to monitor for triggering rollback would be: ESCALATE rate (if it spikes or collapses unexpectedly), JSON parse failure rate (if prompt changes break output format), and human override rate in the dashboard.

### Q4: What is champion-challenger testing and how do you determine when the challenger has won?

**Answer:** Champion-challenger testing is a controlled experiment where the production model (champion) and a new candidate (challenger) receive simultaneous real traffic, and statistical tests determine which is better. It is more rigorous than a canary release because it produces a definitive statistical answer, not just "metrics look better."

The setup: at the load balancer or routing layer, X% of traffic is sent to the challenger. The assignment is randomized (sometimes stratified to ensure balanced distribution of user types). Both models' predictions and outcomes are logged with a flag indicating which model served them. After a defined period (determined by power analysis to achieve statistical significance), you compare the primary metric (say, prediction accuracy on items where ground truth is available) between the two groups.

The statistical test for binary metrics (accurate/inaccurate) is typically a chi-squared test or a z-test for proportions. For continuous metrics (RMSE, revenue), a t-test or Mann-Whitney U test. The challenger "wins" when: (1) the improvement is statistically significant (p < 0.05), (2) the improvement is practically significant (exceeds the minimum meaningful threshold, e.g., ≥0.5% accuracy improvement), and (3) no guardrail metrics have regressed (e.g., latency hasn't increased, error rate hasn't risen).

The minimum traffic and time needed for significance depends on the effect size. If you expect a 2% improvement in accuracy and your current accuracy is 90%, the statistical power to detect that difference at 80% power with p < 0.05 requires roughly 8,000 samples per arm. If you handle 1,000 predictions per day and run a 10% challenger split (100 predictions/day to challenger), you need 80 days for significance. This is why champion-challenger is most practical for high-traffic systems — low-traffic systems like ORCA's current scale would need months of challenger traffic to reach significance.

### Q5: How would you implement model versioning for an LLM application where the "model" is a third-party API and you control only the prompts?

**Answer:** This is an important reframe of model versioning for the LLM era. When using a managed LLM API (Groq, OpenAI, Anthropic), the model weights are not yours to version — Groq's llama-3.1-8b-instant is llama-3.1-8b-instant. But the system prompt, few-shot examples, output format instructions, retrieval configuration, and agent tool definitions are your code and must be versioned.

The practical implementation is to treat prompt configurations as code artifacts, versioned in Git and logged to the experiment tracker. Every time `agents/prompts.py` in ORCA changes, the git commit hash captures it. But code versioning alone is not enough for rollback — you need to be able to run the *old* prompt on *new* traffic quickly. This means prompt versions should live in a configuration store (a database or YAML file) that the application reads at startup, not hardcoded in Python. Changing the active prompt version becomes a config change, not a code deploy.

A minimal "prompt registry" for ORCA would be: a table in SQLite (or a YAML file in version control) with columns: `prompt_id`, `agent_name`, `system_prompt_text`, `version_number`, `status` (staging/production/archived), `eval_pass_rate`, `created_date`. The application reads the Production-status prompt for each agent at startup. Rollback is: update the status column for the previous version to "Production" — takes 1 second, no code redeploy needed.

A more sophisticated version uses MLflow to log prompt text as an artifact alongside the retrieval eval metrics that qualified it. Each "model version" in the registry is actually a prompt bundle: system prompts for all 4 agents + RAG configuration + output format specifications. This gives you a complete audit trail of every prompt change and its associated quality metrics, plus one-click rollback via the registry UI.

```
Prompt Registry (simplified):
─────────────────────────────────────────────────────────────
ID  | Agent    | Version | Status    | eval_pass | Created
─────────────────────────────────────────────────────────────
 1  | agent1   | v1.0    | archived  |   73%     | 2026-01-10
 2  | agent1   | v1.1    | archived  |   78%     | 2026-02-14
 3  | agent1   | v1.2    | production|   84%     | 2026-05-20  ← active
 4  | agent1   | v1.3    | staging   |   81%     | 2026-06-01  ← testing
─────────────────────────────────────────────────────────────
Rollback: UPDATE status SET status='production' WHERE id=2;
          UPDATE status SET status='archived'  WHERE id=3;
```

## Key Points to Say in the Interview

- Model versioning gives you the rollback path — the most critical operational safety net for any production ML system
- The lifecycle stages are: None → Staging (tests) → Production (serving traffic) → Archived (recoverable)
- Champion-challenger runs two models simultaneously on real traffic and uses statistical tests to determine the winner
- Shadow mode has zero user impact — the safest way to evaluate a new model, at the cost of doubled serving infrastructure
- Rollback speed depends on how serving infrastructure loads models — container restart vs hot-reload vs per-request registry check
- For LLM systems, version prompts and retrieval configurations in a prompt registry, not just in Git
- Rollback includes data compatibility — rolling back a model is only safe if the serving infrastructure is still sending the features the old model expects

## Common Mistakes to Avoid

- Do NOT conflate model versioning with experiment tracking — tracking is for managing experiments; versioning is for managing what's in production
- Do NOT suggest the serving infrastructure hardcodes model file paths — always load the Production-tagged version by name
- Do NOT forget that feature schema compatibility limits rollback — a rollback that can't be executed is not a real rollback plan
- Do NOT describe canary and shadow mode as the same thing — shadow mode has zero user exposure; canary has a small percentage
- Do NOT skip the statistical rigor of champion-challenger — "metrics look better" is not a conclusion; statistical significance is

## Further Reading

- [MLflow Model Registry Documentation](https://mlflow.org/docs/latest/model-registry.html) — Comprehensive guide to staging, promoting, and transitioning model versions in MLflow
- [Google Cloud: Vertex AI Model Registry](https://cloud.google.com/vertex-ai/docs/model-registry/introduction) — Google's production-grade model management documentation; directly relevant to a Google interview
- [Martin Fowler: Canary Release](https://martinfowler.com/bliki/CanaryRelease.html) — The canonical definition and explanation of canary releases from the original author of the pattern
- [Shadow Mode Deployment — Chip Huyen](https://huyenchip.com/2022/01/02/real-time-machine-learning-challenges-and-solutions.html) — Detailed explanation of shadow mode and real-time ML serving challenges from a leading ML systems practitioner
- [AWS: Blue/Green Deployments with SageMaker](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails-blue-green.html) — AWS's implementation of model rollback and traffic shifting for production ML models
