# Production AI Platform Design

## What Is It? (Plain English)

Running an AI model in a demo is trivial — you call an API and display the result. Running AI in production at Fortune 100 scale is one of the hardest distributed systems challenges in modern engineering. "Production at scale" means: thousands of simultaneous users, each expecting a response in under 3 seconds; model outputs that must be auditable and explainable; the ability to update or roll back models without downtime; costs that scale with usage and must be controlled; and the requirement that the system performs reliably 99.9% of the time even when individual components fail.

A production AI platform is the infrastructure layer that makes all of this possible. Think of it like the platform a bank runs on: individual financial transactions are simple, but the platform that processes billions of them reliably, securely, with full auditability and fraud detection, is enormously complex. The AI platform is analogous — it sits between the raw AI models (GPT-4, Gemini, your own fine-tuned models) and the end users or downstream applications, providing model serving, request routing, version management, monitoring, and cost control.

Google runs some of the world's largest ML platforms — Vertex AI, TensorFlow Serving, and the internal infrastructure that powers Search, Ads, Gmail's Smart Reply, Google Photos, and hundreds of other AI features. The engineering principles behind these platforms — efficient model serving, automated rollout/rollback, feature stores, model registries, shadow mode testing — are now expected knowledge for senior AI engineers. Understanding how to design this platform at scale is what separates senior engineers from junior ones.

## How It Works

```
═══════════════════════════════════════════════════════════════
              PRODUCTION AI PLATFORM ARCHITECTURE
═══════════════════════════════════════════════════════════════

Client Applications (Web, Mobile, Internal Services)
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│                  API GATEWAY / LLM PROXY                   │
│  • Authentication / Rate limiting                          │
│  • Request routing (which model version?)                  │
│  • A/B traffic splitting (90% v1, 10% v2)                 │
│  • Cost tracking (per-user, per-department)               │
│  • Semantic caching (reduce duplicate LLM calls)          │
└─────────────────────┬──────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ Model   │  │ Model   │  │ Model   │
   │Serving  │  │Serving  │  │Serving  │
   │(v1.0)  │  │(v1.1)  │  │(v2.0   │
   │         │  │ canary) │  │ shadow) │
   └─────────┘  └─────────┘  └─────────┘
   GPU cluster  GPU cluster   GPU cluster

         │
         ▼
┌────────────────────────────────────────────────────────────┐
│                   FEATURE STORE                            │
│  • User context (preferences, history)                     │
│  • Business context (inventory, products, rules)          │
│  • Pre-computed embeddings                                 │
│  • Real-time + batch features                             │
└─────────────────────┬──────────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│Model Registry│ │Experiment│ │  Monitoring  │
│• Versioning  │ │Tracking  │ │• Latency P99 │
│• Lineage     │ │• MLflow  │ │• Error rates │
│• Rollback    │ │• Weights │ │• Drift detect│
│  pointers    │ │  &Biases │ │• Cost/token  │
└──────────────┘ └──────────┘ └──────────────┘
```

**Deployment lifecycle:**
1. Model trained/selected → registered in Model Registry with metadata
2. Shadow mode: new model runs alongside production, outputs compared but not served
3. Canary: 5-10% of real traffic routed to new model, metrics compared
4. Gradual rollout: 25% → 50% → 100% if metrics hold
5. Rollback trigger: if P99 latency or error rate exceeds threshold, automatic rollback

## Why Google Cares About This

Google runs Vertex AI — a managed ML platform serving millions of developers — and manages internal ML infrastructure for products used by billions of people. Senior candidates at Google are expected to understand not just how to build AI features, but how to run them reliably at massive scale. The production AI platform design question tests several senior-level capabilities simultaneously: distributed systems thinking (model serving, load balancing), DevOps/MLOps maturity (CI/CD for models, monitoring), cost engineering (model selection, caching, batching), and quality assurance (safe rollout, rollback, shadow testing). A candidate who has only deployed models to demo environments will struggle; a candidate who can reason about the full lifecycle of a model from training to production to retirement is exactly what Google is looking for.

## Interview Questions & Answers

### Q1: Design a model serving platform that handles 100,000 requests per second with a P99 latency SLA of 500ms.

**Answer:** At 100K requests per second with a 500ms P99 SLA, this is a large-scale distributed serving problem first and an AI problem second. The key constraints are: GPU memory limits the number of model replicas (large LLMs can require 40-80GB per replica), LLM inference is memory-bandwidth bound (not just compute bound), and network latency between components must be minimized.

**Infrastructure layer**: I'd use a fleet of GPU-accelerated servers (A100 or H100 for large models, T4 for smaller models) behind a load balancer. Each server runs a model serving framework — either vLLM (the current state-of-the-art for LLM serving efficiency, using PagedAttention to optimize GPU memory utilization) or TensorFlow Serving for TensorFlow models. The load balancer must do **least-connections routing** (not round-robin) because LLM inference requests have highly variable response times — a request generating 10 tokens takes 10x less time than one generating 100 tokens.

**Batching**: The single most important optimization for throughput. Instead of processing each request individually, group multiple requests and process them simultaneously on the GPU. vLLM's continuous batching allows requests of different lengths to be batched together efficiently, achieving near-linear GPU utilization. The tradeoff: batching adds queuing latency. Set the batching timeout to max 10ms — beyond that, process what's in the batch. For real-time applications, use micro-batching with very short windows.

**Caching**: Implement a semantic cache (Redis + vector similarity) at the gateway layer. For a large-scale application, 20-30% cache hit rates are achievable for FAQ-type queries, and each cache hit saves one GPU inference call entirely. Even a 10% cache hit rate at 100K RPS = 10K GPU calls saved per second.

**Horizontal scaling**: Model serving is stateless (each request is independent), so horizontal scaling is straightforward — add more GPU replicas. Use Kubernetes Horizontal Pod Autoscaler based on GPU utilization and request queue depth. Set minimum replicas to handle baseline traffic, maximum replicas to handle peak.

**SLA monitoring**: Define latency percentiles (P50, P95, P99) as the primary SLA metrics, not averages — averages hide tail latency. Alert when P99 exceeds 400ms (20% below the 500ms SLA, giving headroom for alert → response). Use circuit breakers to stop routing new requests to an unhealthy replica rather than letting it drag down P99 for all users.

At 100K RPS with 500ms P99, you'd typically need 50-200 GPU replicas depending on model size and request complexity. Plan for 2x normal capacity to handle traffic spikes and rolling deployments without SLA degradation.

### Q2: How do you safely roll out a new version of an LLM in production?

**Answer:** Safe model rollout in production requires treating the new model version with the same discipline as a software release — incremental rollout, automated quality gates, and instant rollback capability. The unique challenge with LLMs is that quality degradation may be subtle and not immediately visible in standard infrastructure metrics (latency, error rate are fine; but the model is producing worse answers).

**Shadow mode (Week 1)**: The new model runs alongside the current production model, receiving a copy of every real request. Its outputs are NOT served to users — they're logged and compared to the production model's outputs. This is completely safe for users. Shadow mode lets you compare: Does the new model produce longer/shorter responses? Are there more refusals? Are the outputs qualitatively better or worse (using an LLM-as-judge scorer)? Does the new model have higher latency or token usage? Fix any major issues found here before exposing users.

**Canary deployment (Week 2)**: Route 5% of real user traffic to the new model. This is the first time real users see the new model's outputs. Monitor: error rate, latency P99, user satisfaction signals (thumbs up/down, re-query rate as implicit dissatisfaction signal), content safety flags. Set automated rollback triggers: if error rate increases by more than 0.5% relative to baseline, automatically route all traffic back to the old model. Keep this phase for 3-7 days to observe across different time zones, usage patterns, and edge cases.

**Progressive rollout (Weeks 3-4)**: If canary metrics are good, increase to 25%, then 50%, then 100% over the course of a week. Use a feature flag system (LaunchDarkly, Flagsmith) to control the traffic split without redeployment. This allows instant rollback by flipping the feature flag — no code deploy needed, rollback is sub-minute.

**Model registry as the source of truth**: Every model version is registered with metadata: training date, dataset version, evaluation metrics (MMLU score, task-specific benchmark), known limitations, and a pointer to the serving artifact. Rollback means updating the registry to point to the previous version — the serving infrastructure reads the registry and switches models.

**Continuous post-deployment monitoring**: After full rollout, run your offline evaluation suite on a sample of production traffic daily. Compare against the baseline model to detect quality drift. Models can degrade over time as the user query distribution shifts away from what the model was optimized for.

### Q3: What is a feature store, and why is it important for production AI systems?

**Answer:** A feature store is a centralized data system that manages the features — the computed data inputs — that ML models need at both training time and serving time. Think of it as a highly reliable, versioned database specifically designed for ML feature data. The reason it exists is to solve what's called the **training-serving skew** problem: the single most common cause of production ML failures is that the features computed at training time are different from the features available at serving time.

Imagine training a fraud detection model using a feature "transactions in the last 7 days." At training time, you compute this from a data warehouse query that runs overnight. At serving time, you need this feature in real-time (the fraud transaction is happening right now). If these two computations use different logic, different time zones, or different source tables, the model sees different data in production than it was trained on, and performance degrades silently.

A feature store solves this by providing a **single definition** of each feature that is shared between batch training and real-time serving. There are two stores within a feature store:
- **Offline store** (usually a data warehouse like BigQuery or Snowflake): stores historical feature values for training and batch inference. Used by data scientists to create training datasets.
- **Online store** (usually a fast key-value store like Redis or Bigtable): stores the latest feature values for real-time serving. Latency must be under 10ms. Updated from the offline store on a schedule (hourly/daily) or in real-time via a streaming pipeline.

For LLM applications, features in the feature store might include: user profile embeddings, historical query embeddings, product catalog embeddings, user satisfaction history, and contextual flags like "user is on mobile" or "user has premium subscription." These are retrieved at serving time and injected into the prompt.

Well-known feature store implementations: Google's internal Feast (which was open-sourced), Tecton (commercial), Feast (open source), and Vertex AI Feature Store (managed on GCP). The investment in a feature store is high initially but pays off massively at scale by eliminating training-serving skew bugs and enabling feature reuse across multiple models.

### Q4: How do you monitor an LLM application in production, and what metrics matter most?

**Answer:** Monitoring an LLM application requires a two-tier approach: **infrastructure metrics** (the system is up and fast) and **quality metrics** (the system is producing good outputs). Traditional monitoring tools (Prometheus, Datadog) handle the first tier well. The second tier is unique to AI and requires custom instrumentation.

**Infrastructure metrics (standard):**
- Latency: P50, P95, P99 end-to-end response time; also broken down by component (retrieval latency, LLM latency, post-processing latency)
- Error rate: HTTP 4xx and 5xx rates; LLM provider API errors; timeouts
- Throughput: requests per second, tokens per second
- Resource utilization: GPU utilization, GPU memory utilization, CPU/memory for non-GPU components
- Cost: tokens consumed per request, cost per user, cost per department (for chargebacks)

**Quality metrics (AI-specific):**
- **Refusal rate**: How often does the model refuse to answer ("I can't help with that")? A sudden spike in refusal rate indicates either a prompt regression or a shift in user queries.
- **Output length distribution**: Sudden changes in average output length often indicate a prompt regression or model behavior change. Track mean and variance of output tokens.
- **Faithfulness score** (for RAG systems): Run automated faithfulness scoring on a sample of production outputs using an LLM judge. Alert if the moving average drops below a threshold.
- **User satisfaction signals**: If the UI has explicit feedback (thumbs up/down), track the satisfaction rate. Also track implicit signals: did the user immediately re-ask the same question (indicating a bad answer)? Did the user continue the conversation (indicating engagement)?
- **Latency by complexity**: Monitor latency separately for simple queries (short, focused) and complex queries (long, multi-step). If complex query latency degrades, it may indicate context window pressure or model routing issues.

**Alerting strategy**: Set alerts at two levels — **warning** (metrics degrading but within tolerance) and **critical** (immediate action required, consider rollback). Warning thresholds: P99 latency > 70% of SLA, refusal rate > 2x baseline. Critical thresholds: P99 latency > SLA, error rate > 1%, refusal rate > 5x baseline.

**Tracing for debugging**: Every request should emit a full trace through the system — input, constructed prompt (with retrieved context), model response, all timestamps, all intermediate steps. Tools like LangSmith, Langfuse, or OpenTelemetry with a custom LLM exporter enable this. When a user reports a bad answer, you should be able to look up the trace for that exact request and see exactly what context was retrieved, exactly what prompt was sent, and exactly what the model returned.

### Q5: How do you manage costs in a large-scale LLM production deployment?

**Answer:** LLM costs at scale are a real engineering constraint, not just a business consideration. A single GPT-4 call for a complex task might cost $0.10-$0.50. At 1 million calls per day, that's $100K-$500K per day. Cost management is an engineering discipline, not an afterthought.

**Cost optimization layer 1 — Model selection**: Not all queries need the most expensive model. Use a query classifier to route simple queries (factual lookups, short summaries) to cheap, fast models (Gemini Flash, GPT-3.5-turbo, LLaMA 3 8B) and complex queries to expensive models (GPT-4o, Gemini Pro). A well-designed router can reduce average cost per query by 60-80% while maintaining quality on complex tasks. The routing decision itself must be cheap — use a small, fast classifier.

**Cost optimization layer 2 — Caching**: As discussed, semantic caching can achieve 20-30% hit rates for FAQ-type applications, eliminating those LLM calls entirely. For deterministic operations (same input always produces the same right answer), exact caching is even more effective. Also cache expensive computed artifacts: if you run a 5-minute RAG ingest pipeline to generate an analysis document, cache the result for hours rather than regenerating on every request.

**Cost optimization layer 3 — Prompt optimization**: Token length = cost. Audit your prompts regularly to remove unnecessary verbosity. A system prompt that's 2,000 tokens vs 500 tokens is 4x more expensive per request, at no quality benefit if the extra tokens are redundant. Compress few-shot examples. Summarize long conversation history rather than appending indefinitely. Use structured output formats (JSON) rather than free-text when the output will be parsed anyway — structured prompts tend to be shorter.

**Cost optimization layer 4 — Batching for non-real-time workloads**: For offline batch processing (document analysis, nightly summaries, model evaluation), use batch API modes. OpenAI's batch API is 50% cheaper than the real-time API. Schedule non-urgent LLM work during off-peak hours when you have spare capacity.

**Cost optimization layer 5 — Fine-tuning and distillation**: Once you have a working system with a large, expensive model, collect its high-quality outputs and use them to fine-tune a smaller, cheaper model on your specific task. The smaller fine-tuned model often matches the large general model on the narrow task at 10% of the cost. This is the trajectory of all mature AI products at scale — they start with powerful general models and over time replace specific components with smaller specialized models.

**Governance**: Implement per-user, per-department, and per-feature cost quotas. Alert when any quota exceeds 80%. Require approval for new features that will consume more than a threshold of LLM calls per day. Treat LLM budget like cloud infrastructure budget — it needs the same governance.

## Key Points to Say in the Interview

- Always describe a **safe rollout sequence**: shadow → canary → progressive → full
- Name **feature stores** and the **training-serving skew** problem — this is a classic Google interview topic
- Know **two tiers of monitoring**: infrastructure metrics (latency, errors) AND quality metrics (refusal rate, faithfulness, user satisfaction)
- Name **model routing** as the highest-ROI cost optimization: small models for simple tasks, large for complex
- Know **vLLM and continuous batching** as the state-of-the-art for high-throughput LLM serving
- Mention **rollback capability** as a non-negotiable requirement — model registry with version pointers
- The **LLM proxy / gateway** layer (cost tracking, routing, caching) is often overlooked — mention it

## Common Mistakes to Avoid

- Describing production AI as just "deploying a Docker container with a model" — miss the full MLOps lifecycle
- Not mentioning **quality metrics** — infrastructure monitoring alone is not enough for AI systems
- Forgetting **cost engineering** — Google will absolutely ask about cost at scale
- Not knowing the **training-serving skew** problem — it's a classic ML systems trap
- Treating rollout as binary (old model → new model overnight) rather than **gradual with automated rollback**

## Further Reading

- [Google's Machine Learning Engineering Best Practices (Rules of ML)](https://developers.google.com/machine-learning/guides/rules-of-ml) — 43 rules from Google's experience running ML in production
- [Vertex AI Model Serving Documentation](https://cloud.google.com/vertex-ai/docs/predictions/overview) — Google's managed ML serving platform documentation
- [vLLM: Easy, Fast, and Cheap LLM Serving](https://vllm.readthedocs.io/en/latest/) — The leading open-source LLM serving framework with PagedAttention
