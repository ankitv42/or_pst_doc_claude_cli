# CI/CD for AI: Automating the ML Lifecycle

## What Is It? (Plain English)

In traditional software, a "CI/CD pipeline" is the automated assembly line that takes code a developer writes, tests it to make sure it works, and ships it to users — without a human doing each step manually. Think of it like a car factory: the engineer designs the car, but robots weld, paint, and assemble it. CI/CD is those robots for software.

For machine learning, the same idea applies, but the "product" isn't just code — it's a trained model. And models have a nasty property that regular software doesn't: they can fail silently. A bug in normal code usually crashes loudly. A degraded model just gives quietly wrong answers. So the CI/CD pipeline for ML must also test whether the model is *good* — not just whether it *runs*.

LLMOps (Large Language Model Operations) is the next evolution of MLOps, specific to systems like GPT, Llama, or the Groq-backed agents in ORCA. Because LLMs aren't retrained every sprint but *prompts* change constantly, LLMOps adds a new concern: "did this prompt change make the outputs worse?" This requires prompt regression testing, retrieval quality evaluations, and semantic similarity checks — the equivalent of unit tests for language model behavior.

## How It Works

```
Developer pushes code / prompt / data change
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                   CI STAGE                          │
│  1. Lint & type-check Python code                   │
│  2. Unit tests (mocked LLM calls)                   │
│  3. Data validation (schema checks, null counts)    │
│  4. Retrieval eval — does RAG return right chunks?  │
│  5. Prompt regression — do outputs stay on-policy?  │
└─────────────────────────────────────────────────────┘
         │ (all green)
         ▼
┌─────────────────────────────────────────────────────┐
│              MODEL TRAINING STAGE                   │
│  1. Pull versioned data from DVC / data store       │
│  2. Train (or fine-tune) model                      │
│  3. Log params + metrics to MLflow / W&B            │
│  4. Compare against champion model                  │
│  5. Gate: new model must beat champion by ≥1%       │
└─────────────────────────────────────────────────────┘
         │ (passes gate)
         ▼
┌─────────────────────────────────────────────────────┐
│               CD STAGE                              │
│  1. Register model in Model Registry (MLflow)       │
│  2. Push Docker image with model baked in           │
│  3. Deploy to staging — run integration tests       │
│  4. Canary release: 5% traffic → new model          │
│  5. Monitor metrics; promote to 100% or rollback    │
└─────────────────────────────────────────────────────┘
         │
         ▼
    Production (users see new model)
```

**Data Versioning with DVC:** DVC (Data Version Control) works like Git but for large datasets and model weights. Instead of storing a 10 GB CSV in Git (which breaks it), DVC stores a tiny pointer file in Git and keeps the actual data in S3/GCS. You can do `dvc checkout v2.3` to get the exact dataset that produced a particular model.

## Why Google Cares About This

At Google's scale, dozens of ML models are updated every day across Search, Ads, Maps, and YouTube. Without automated pipelines, each update would require a data scientist to manually train, evaluate, and deploy — taking weeks. Google pioneered the idea of "ML as software" — treating model changes with the same rigor as code changes. In senior AI/ML interviews, they want to know if you understand that a model is not a static artifact but a continuously evolving product that needs the same automation guardrails as any production software. They also want to see that you understand the *unique* failure modes of ML (silent degradation, training-serving skew) that make standard CI/CD insufficient.

## Interview Questions & Answers

### Q1: How would you design a CI/CD pipeline for an LLM-powered application?

**Answer:** I'd think of an LLM app as having three distinct moving parts, each needing its own tests: the application code, the prompts, and the retrieval layer (if RAG is involved). Standard software CI handles the code — linting, unit tests, integration tests. But prompts and retrieval need their own eval stages.

For prompt testing, I'd maintain a "golden set" of (input, expected_output) pairs. When a prompt changes, the CI pipeline runs the new prompt against all golden cases and uses an LLM-as-judge or a semantic similarity scorer to check whether the output quality dropped. This is what ORCA's `evals/run_judge_eval.py` is designed to do — it's a Layer 2 gate. If the answer to "Did the capital allocation agent correctly identify ESCALATE vs AUTO_EXECUTE?" changes, the pipeline fails.

For the retrieval layer, I'd use retrieval evals: given a known query, does the RAG system return the correct documents in the top-3? This is Layer 1 in ORCA — `run_retrieval_eval.py` tests 11 golden cases. The CI gate (`eval_gate.yaml`) fails the push if the pass rate drops below 70%. This prevents a new embedding model or chunking strategy from silently degrading retrieval.

For deployment, I'd use canary releases routed at the load balancer. New LLM app version gets 5% of traffic. I'd monitor output quality metrics (user thumbs-down rate, fallback rate, latency) for 24 hours before promoting. The key insight is that LLM failures are soft — the app doesn't crash, it just answers poorly — so you need behavioral metrics, not just error rates.

```
Code commit
    │
    ├─► Code tests (pytest, mypy)
    ├─► Retrieval eval (keyword match, no-leak checks)
    ├─► Prompt regression (LLM judge, semantic sim)
    └─► Integration test (full pipeline, mocked APIs)
         │ all pass
         ▼
    Staging deploy → Canary 5% → Full deploy
```

### Q2: What is DVC and why can't you just use Git for ML data?

**Answer:** Git is designed for text files that change in small, meaningful increments. A Python file might change 50 lines at a time — Git stores the diff efficiently. But a training dataset might be a 50 GB Parquet file, and "changing" it means uploading an entirely new 50 GB blob. Git would balloon to terabytes in weeks and become unusable.

DVC (Data Version Control) solves this by treating large files like pointers. The actual data lives in object storage (S3, GCS, Azure Blob), and DVC stores a tiny `.dvc` file in Git that says "this dataset is at s3://my-bucket/datasets/abc123.parquet". When you run `dvc pull`, it fetches the right version. The `.dvc` file is committed to Git, so your data is version-controlled *by reference*.

The deeper value is reproducibility. An ML experiment has three inputs: code (Git), config (Git), and data (DVC). If all three are pinned, anyone can reproduce the exact experiment. Without DVC, teams end up with folders named `data_final_v3_FINAL_USE_THIS.csv` and no way to know which model was trained on what. DVC eliminates that by making data versioning as natural as `git tag`.

In an LLMOps context, DVC also versions prompt datasets and evaluation sets. The golden test cases in ORCA are small JSON files — they'd go in Git directly. But a fine-tuning dataset of 10,000 examples would use DVC.

### Q3: What is a model registry and how does it fit into the deployment pipeline?

**Answer:** A model registry is a centralized catalog that tracks every trained model artifact — its metrics, the code that produced it, the data it was trained on, and its current deployment status. Think of it like a package registry (npm, PyPI) but for ML models. MLflow Model Registry and Google's Vertex AI Model Registry are the most common options.

The workflow is: train model → log metrics to the tracking server → if metrics pass the gate, register the model with a version number and `Staging` status → run integration tests in staging → promote to `Production` → the previous production model moves to `Archived`. Every running service always loads the `Production` version by name, never by hardcoded path.

This matters enormously for rollback. If a newly promoted model starts producing bad outputs at 2 AM, an on-call engineer doesn't need to re-train anything. They run one command: `mlflow models transition-to-production --model-name demand_forecaster --version 7` (reverting from v8 to v7). The serving infrastructure picks up the change within seconds.

For LLMs, the registry isn't for model weights (you're usually using an API-served LLM like Groq or OpenAI) but for prompt versions, system messages, and RAG configurations. You'd register "Prompt v3 for Agent 2 — Supply Replenishment" alongside the evaluation scores that qualified it.

### Q4: How do LLMOps concerns differ from traditional MLOps concerns?

**Answer:** Traditional MLOps centers on the model artifact: you train a model, evaluate it on held-out data, version the weights, and deploy them. The model is fixed until the next retraining run. Failure looks like metric regression (accuracy drops, RMSE rises).

LLMOps shifts the action from model weights to prompts, retrieval, and orchestration. The model (Llama 3.1, GPT-4, Gemini) is usually a third-party API you don't control. What *you* control is the system prompt, the few-shot examples, the retrieval chunk size, the agent tool definitions, and the output parsers. These change frequently — sometimes daily. So the CI/CD loop runs on prompt diffs, not model diffs.

The failure modes are also different. A bad traditional model produces measurably worse RMSE. A bad LLM prompt might produce outputs that look fine to a rule-based check but are subtly off-policy — for example, recommending an order that violates a Class A SKU rule that the prompt forgot to mention. Detecting this requires an LLM-as-judge or human spot-check, not a simple numeric threshold. This is why ORCA's Layer 2 eval uses an LLM judge, not a metric comparison.

Finally, LLMOps must handle provider-level concerns that don't exist in traditional MLOps: rate limits (Groq's 30 req/min free tier), model version deprecations (OpenAI retiring gpt-3.5-turbo-0301), and cost per token. A proper LLMOps pipeline tracks token consumption per pipeline run and alerts when cost anomalies appear — something never needed for a locally-served scikit-learn model.

### Q5: Walk me through how you would implement automated eval gates in a GitHub Actions workflow for a RAG system.

**Answer:** The goal is to prevent any merge to `main` that degrades retrieval quality. The workflow triggers on every pull request that touches `docs/rag/`, `agents/prompts.py`, or `requirements.txt` — changes that could affect retrieval.

The workflow file (`.github/workflows/eval_gate.yaml`) would: check out the code, install dependencies (using a requirements file without heavy packages to keep CI fast), run `python evals/run_retrieval_eval.py --ci`, and fail the job if the exit code is non-zero. The `--ci` flag makes the script exit with code 1 if pass rate is below 70% — ORCA already does exactly this.

The more sophisticated version adds a *comparative* gate. Before the PR, run the eval on `main` and record a baseline score. After the PR, run on the feature branch. Fail the PR if the score regressed by more than 2 percentage points. This is relative gating — it's stricter than an absolute threshold because it catches small regressions that still pass the 70% bar.

For LLM judge evals (Layer 2), the same pattern applies but the gate is more expensive — it costs real tokens to run LLM-as-judge evaluations. The pragmatic approach is to run cheap retrieval evals on every PR and expensive judge evals only on merges to main or on a nightly schedule. This balances CI speed against thoroughness.

```yaml
# .github/workflows/eval_gate.yaml (simplified)
on:
  push:
    branches: [main]
  pull_request:
    paths:
      - 'docs/rag/**'
      - 'agents/prompts.py'
jobs:
  eval_gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install -r requirements.api.txt
      - run: python evals/run_retrieval_eval.py --ci
```

## Key Points to Say in the Interview

- CI/CD for ML is not just "does the code run" — it also gates on *model quality*, which is a unique ML concern
- DVC solves the problem of data versioning that Git cannot handle at scale
- A model registry provides the rollback path — the most important operational safety net
- LLMOps is different from MLOps because the action is on prompts and retrieval, not model weights
- Canary releases are mandatory for LLM apps because failures are soft (no crash, just bad outputs)
- The eval suite should have multiple layers: cheap retrieval evals (every PR), expensive judge evals (nightly/merge)
- Token cost tracking is a first-class LLMOps concern that has no traditional MLOps equivalent

## Common Mistakes to Avoid

- Do NOT say "we just run pytest and if it passes, deploy" — this misses the entire model quality gating concern
- Do NOT suggest storing large datasets or model weights in Git — this will immediately signal inexperience
- Do NOT conflate CI/CD with monitoring — CI/CD is pre-deployment quality gates; monitoring is post-deployment observation
- Do NOT forget that LLM model weights are usually not yours to version — the versioning action is on prompts, configs, and eval results
- Do NOT skip mentioning rollback — any deployment story that doesn't include "how do we undo this" is incomplete

## Further Reading

- [Continuous Delivery for Machine Learning — Martin Fowler](https://martinfowler.com/articles/cd4ml.html) — The canonical reference for applying CD principles to ML, written by the GoF-era software architect
- [DVC Documentation: Get Started](https://dvc.org/doc/start) — Official DVC quickstart; covers data versioning, pipelines, and experiments
- [MLflow Model Registry Guide](https://mlflow.org/docs/latest/model-registry.html) — Official MLflow docs for staging, promoting, and rolling back model versions
- [Google Cloud Vertex AI Pipelines](https://cloud.google.com/vertex-ai/docs/pipelines/introduction) — How Google's own MLOps platform handles automated training and deployment pipelines
- [LLMOps: Operationalizing LLM Applications — DeepLearning.AI](https://www.deeplearning.ai/short-courses/llmops/) — Short course specifically covering prompt versioning, eval frameworks, and deployment patterns for LLM apps
