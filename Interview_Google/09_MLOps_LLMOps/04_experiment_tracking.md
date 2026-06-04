# Experiment Tracking: The Scientific Lab Notebook for ML

## What Is It? (Plain English)

Imagine running dozens of scientific experiments — different hypotheses, different equipment settings, different sample sizes — but writing your findings on loose scraps of paper scattered across the lab. Three months later, someone asks "which experiment produced that great result?" You have no idea. This is exactly the situation most data science teams find themselves in without experiment tracking.

Experiment tracking is the practice of automatically recording everything about an ML experiment: what hyperparameters you used (learning rate, batch size, number of trees), what results you got (accuracy, loss, RMSE), what code was running at the time (commit hash), what dataset was used, and any artifacts produced (model weights, plots). Tools like MLflow and Weights & Biases (W&B) do this recording automatically — you add a few lines of code to your training script and everything is captured to a central database.

The benefit that matters most in practice is not the tracking itself — it's the **comparison**. When you can lay 50 experiments side by side and sort by validation loss, you immediately see which configurations work. This transforms "I vaguely remember that run on Tuesday did well" into a queryable, reproducible scientific record. Reproducibility — the ability to get the same result again from the same inputs — is the foundation of trustworthy ML. Without it, the entire field degrades into folklore.

## How It Works

```
Training Script
       │
       │  mlflow.log_param("learning_rate", 0.01)
       │  mlflow.log_param("n_estimators", 200)
       │  mlflow.log_metric("val_accuracy", 0.91)
       │  mlflow.log_artifact("model.pkl")
       │  mlflow.log_artifact("confusion_matrix.png")
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                MLflow Tracking Server                   │
│                                                         │
│  Experiment: "demand_forecast_v2"                       │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Run ID   │ lr   │ n_est │ val_acc │ git_hash    │   │
│  ├──────────┼──────┼───────┼─────────┼─────────────┤   │
│  │ abc123   │ 0.01 │  200  │  0.91   │ 3f7a2d      │   │
│  │ def456   │ 0.1  │  200  │  0.87   │ 3f7a2d      │   │
│  │ ghi789   │ 0.01 │  500  │  0.93   │ 8c1e9b      │   │  ← best
│  └──────────┴──────┴───────┴─────────┴─────────────┘   │
│                                                         │
│  [Compare Runs] [Download Artifacts] [Register Model]   │
└─────────────────────────────────────────────────────────┘
       │
       │  Promotes best run to Model Registry
       ▼
 model_registry: "demand_forecast" version 3 → Staging
```

**What to Log:**
1. **Parameters** — the settings you chose (hyperparameters, model type, feature list)
2. **Metrics** — the results (train loss, val accuracy, evaluation scores by time window)
3. **Artifacts** — files produced (model weights, plots, confusion matrices, feature importance charts)
4. **Tags** — metadata (dataset version, experiment purpose, author, ticket number)
5. **Code version** — the git commit hash, so you can exactly reproduce the code state

## Why Google Cares About This

At Google, ML experiments are run by hundreds of data scientists simultaneously across the same products. Without shared experiment tracking, two teams might run near-identical experiments — waste compute — and there's no institutional memory when team members change. Google's internal infrastructure (Vertex AI Experiments, TFX) is built on experiment tracking. In a senior interview, they want to see that you treat ML as an engineering discipline — with reproducibility, auditability, and systematic comparison — not as art. They also want to hear you mention that experiment tracking is the foundation of a model registry: you can only promote the *best* run to production if you've tracked all runs objectively.

## Interview Questions & Answers

### Q1: What is the difference between MLflow and Weights & Biases, and when would you choose each?

**Answer:** MLflow and Weights & Biases (W&B) both solve the experiment tracking problem but come from different philosophical origins and serve different use cases best.

MLflow is an open-source platform created by Databricks. It has four components: Tracking (logging experiments), Projects (packaging code for reproducibility), Models (packaging model artifacts in a standard format), and Registry (managing model lifecycle). Because it's open-source, it can run entirely on-premises — critical for regulated industries (healthcare, finance) where data cannot leave the company's infrastructure. MLflow integrates deeply with Databricks and Spark ecosystems. It's the standard choice for enterprise and regulated environments.

Weights & Biases is a SaaS-first platform with a beautiful web interface. Its strongest suit is rich visualization: training curves, gradient distributions, data sample logging (you can log actual images/text that the model saw during training), and system resource utilization. W&B also offers "Sweeps" — an automated hyperparameter search system. It's particularly popular in the research community because of its visual richness and the collaborative "Reports" feature (shareable experiment analyses, like a notebook but for experiment results). The tradeoff is that your experiment data lives on W&B's servers, which creates data residency concerns for sensitive applications.

The practical decision: choose MLflow when you need on-premises control, Databricks integration, or a built-in model registry tightly coupled to the tracking server. Choose W&B when your team prioritizes visualization richness, research-style exploration, or you're fine with a managed SaaS. Many production teams use both — W&B for interactive experiment exploration during research, MLflow for the formal model registry in the deployment pipeline.

### Q2: How do you ensure reproducibility in an ML experiment?

**Answer:** Reproducibility requires locking down every source of randomness and every input. There are four inputs to an ML experiment: code, data, environment, and random state. Failing to pin any one of them makes the experiment unreproducible.

Code is pinned via the git commit hash. Every MLflow run automatically logs the git SHA of the active commit — but only if there are no uncommitted changes. A discipline that many teams fail to enforce is: never log an experiment from "dirty" (uncommitted) code, because the SHA won't match what was actually run. Good teams enforce this in CI with a pre-experiment check that aborts if `git status` shows uncommitted files.

Data is pinned via DVC (as discussed in CI/CD for AI). The experiment logs the DVC dataset hash alongside the model run. If someone clones the repo and runs `dvc checkout abc123`, they get the exact data used. Without data versioning, "I ran the experiment on the July dataset" is not reproducible — datasets get overwritten, filtered, augmented.

Environment is pinned via a `requirements.txt` with exact version numbers or a Docker image hash. Libraries like NumPy and scikit-learn have minor behavioral differences across versions. A model trained with `scikit-learn==1.2.0` may produce slightly different results with `1.3.0` due to internal algorithm changes. The Docker image approach is the strongest lock: the entire Python environment, OS, and CUDA version are frozen.

Random state is pinned via explicit seeding. Set `numpy.random.seed(42)`, `torch.manual_seed(42)`, and in CUDA environments, `torch.cuda.manual_seed_all(42)`. Log the random seed as a parameter. For GPU-accelerated training, note that full determinism is sometimes impossible because certain CUDA operations are non-deterministic by design — you can enable `torch.use_deterministic_algorithms(True)` but this disables some optimizations. The pragmatic approach is to run each experiment 3 times with different seeds and report the mean and standard deviation of the metric, which is statistically more meaningful than a single run anyway.

### Q3: What is "metric logging best practice" and what do teams usually forget to track?

**Answer:** The standard advice is to log training loss and validation loss over every epoch, plus the final evaluation metrics on a held-out test set. The commonly forgotten items are far more interesting.

First, **per-class or per-segment metrics**. A model might achieve 92% overall accuracy while performing at 60% accuracy for a rare but important class (say, the highest-value SKU tier). Logging only aggregate metrics hides this. Always log metrics broken down by the dimensions that matter for your business — class, region, time period, customer segment.

Second, **computational cost metrics**. Log training time, number of GPU hours, and peak memory usage alongside accuracy metrics. This is how you make informed tradeoffs: if Run A gets 0.01 better RMSE than Run B but takes 10x longer to train, Run B is almost certainly the right choice for production. Teams that don't log cost metrics end up blindly optimizing for accuracy while burning GPU budget unnecessarily.

Third, **data statistics at training time**. Log the number of training examples, the class balance, the date range of the training data, and key feature statistics (mean, std of important features). Six months later, when you retrain and wonder "did the model improve because the data got better or because the hyperparameters improved?", you need these baselines to answer the question.

Fourth, for LLM systems specifically, log **token counts and API costs per run**. An ORCA pipeline run that costs $0.08 in Groq tokens vs one that costs $0.40 is a meaningful difference at scale. Log prompt token count, completion token count, and estimated cost. Over time, this reveals cost regression when prompt changes increase token consumption.

### Q4: How do you handle the "I can't reproduce that result" problem in a real team setting?

**Answer:** The reproducibility crisis in ML teams is almost always a culture and process problem, not a technology problem. The tools (MLflow, DVC, Docker) exist — the failure is in whether teams use them consistently. Solving it requires making reproducibility the path of least resistance, not an extra burden.

The most effective intervention I've seen is a **run checklist enforced by CI**. Before a model can be promoted to the registry, an automated check verifies: (1) the run has a git commit hash with no dirty files, (2) the run has a DVC dataset version logged, (3) the run has a requirements.txt or Docker image hash logged, (4) the run has a random seed logged. If any of these are missing, the promotion fails. This makes cutting corners impossible without conscious effort.

The second intervention is **experiment naming discipline**. Runs named "experiment3" or "test_v2_final" are uninterpretable six months later. Enforce a naming convention: `{model_type}_{dataset_version}_{key_change}_{date}` — for example, `xgboost_v3data_featureEngineering_20260601`. When you're debugging six months later, you can immediately understand what each run was attempting.

The third is **documenting the "why" as a run tag, not just the "what"**. MLflow lets you add free-text tags. Require a "hypothesis" tag for every run: "Hypothesis: adding 30-day rolling mean reduces RMSE because it captures seasonality." When the run is over, add a "conclusion" tag. This creates institutional memory that survives team turnover.

In an LLM context, reproducibility also means versioning prompts. Every time you change a system prompt in ORCA's `agents/prompts.py`, that change should be logged against the eval results it produced — just like a model training parameter change. Prompt changes that weren't tracked are the most common source of "why did the LLM start behaving differently last week?" investigations.

### Q5: How would you use experiment tracking to compare a new RAG configuration against the existing one in ORCA?

**Answer:** The goal is to objectively answer: "Is RAG configuration B (new embedding model, new chunk size) better than configuration A (current)?" without relying on qualitative impressions.

I'd set up an MLflow experiment called "rag_retrieval_eval" and run both configurations against ORCA's golden test set (the 11 cases in `run_retrieval_eval.py`). For each run, I'd log the parameters: embedding model name, chunk size, chunk overlap, number of retrieved chunks, whether BM25 is enabled, and whether cross-encoder reranking is enabled. I'd log the metrics: overall pass rate, pass rate per query category (Agent 1 queries, Agent 2 queries, etc.), mean retrieval rank of the correct document, and number of "leak" violations (wrong-doc content appearing).

I'd also log the latency of the retrieval pipeline as a metric. A configuration that improves pass rate from 73% to 80% but triples retrieval latency may not be worth it — the tradeoff needs to be visible in the tracking server.

To compare, I'd use MLflow's "Compare Runs" view, which produces a parallel coordinates plot showing all parameters and metrics together. If configuration B dominates on every metric, the choice is clear. If it's better on pass rate but worse on latency, I'd need to compute a business-weighted score — perhaps `pass_rate - 0.5 * (latency_ms / 100)` — and log that as a composite metric.

```
MLflow Experiment: rag_retrieval_eval
────────────────────────────────────────────────────────────────────
Run      embedding_model      chunk_sz  pass_rate  latency  leak_ct
────────────────────────────────────────────────────────────────────
run_A    nomic-embed-v1.5       400      73%       210ms      0
run_B    nomic-embed-v1.5       200      80%       380ms      0     ← better accuracy
run_C    all-MiniLM-L6-v2       400      68%       90ms       1     ← fastest, leaks
run_D    nomic-embed-v1.5       200      80%       220ms      0     ← best: B+overlap tweak
────────────────────────────────────────────────────────────────────
Promote run_D to production RAG config
```

## Key Points to Say in the Interview

- Experiment tracking = reproducibility + systematic comparison — not just logging for logging's sake
- The four pillars of reproducibility: code (git SHA), data (DVC), environment (Docker/requirements), random seed
- Always log per-segment metrics, not just aggregate metrics — overall accuracy can hide class-level failures
- Log computational cost alongside quality metrics — accuracy improvements have a cost, and that cost is worth tracking
- Culture and process (mandatory checklists) matter more than tooling choice for solving reproducibility problems
- For LLMs, track prompt versions, token counts, and API costs — these are the ML parameters of an LLM system
- The run naming and tagging convention is often more valuable long-term than the raw metric values

## Common Mistakes to Avoid

- Do NOT say "we just use notebooks" — notebooks are experiment execution environments, not tracking systems; you still need to log results somewhere queryable
- Do NOT forget that random seed logging is required for reproducibility — many candidates forget this
- Do NOT log only final metrics — logging metrics per epoch reveals training dynamics (overfitting, learning rate issues) that final metrics hide
- Do NOT treat W&B and MLflow as interchangeable — understand their distinct strengths and be able to justify a choice
- Do NOT ignore the LLM-specific logging concerns (token costs, prompt versions) when discussing LLMOps experiments

## Further Reading

- [MLflow Documentation: Tracking](https://mlflow.org/docs/latest/tracking.html) — Official MLflow tracking API reference; shows exactly what can be logged and how
- [Weights & Biases: Experiment Tracking Best Practices](https://docs.wandb.ai/guides/track) — W&B's official guide to what, when, and how to log during training
- [Reproducibility in Machine Learning — Papers With Code](https://paperswithcode.com/rc2020) — The ML reproducibility challenge; excellent resource for understanding what makes experiments reproducible
- [Google Cloud: Vertex AI Experiments](https://cloud.google.com/vertex-ai/docs/experiments/intro-vertex-ai-experiments) — Google's own experiment tracking product; understanding it is directly relevant to a Google interview
- [Made With ML: Experiment Tracking](https://madewithml.com/courses/mlops/experiment-tracking/) — Practical hands-on walkthrough of setting up MLflow for a real ML project
