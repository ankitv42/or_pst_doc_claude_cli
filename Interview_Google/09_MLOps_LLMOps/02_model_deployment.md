# Model Deployment: From Notebook to Production

## What Is It? (Plain English)

A data scientist builds a model in a Jupyter notebook. It works brilliantly on their laptop. Then the hard question arrives: how does anyone else actually *use* it? Model deployment is the entire set of engineering decisions that answer that question — how to package the model, where to run it, how to handle thousands of simultaneous requests, and how to introduce a new version without breaking users who depend on the old one.

The gap between "it works in my notebook" and "it runs reliably for a million users" is one of the most expensive gaps in the ML industry. Studies from surveys like the one Algorithmia publishes estimate that only 22% of ML models ever make it to production, and of those, the average time from experiment to deployment is 8 to 90 days. The reason is almost never the model itself — it's the surrounding engineering: packaging, serving infrastructure, latency guarantees, and version management.

Think of it like a restaurant kitchen. The chef creates a recipe (the model). But getting that recipe to 500 tables simultaneously requires a professional kitchen (serving infrastructure), prep cooks who follow the recipe exactly without the head chef present (containerization and model formats), and a host system that seats people efficiently without making them wait an hour (latency SLAs). Deployment is the kitchen, not the recipe.

## How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                  DEPLOYMENT JOURNEY                          │
│                                                              │
│  Jupyter Notebook                                            │
│  model.pkl (raw pickle file)                                 │
│       │                                                      │
│       ▼  Step 1: Serialize to portable format                │
│  model.onnx  OR  torchscript.pt  OR  model.pkl               │
│       │                                                      │
│       ▼  Step 2: Wrap in serving code (FastAPI)              │
│  app.py: POST /predict → loads model → returns JSON          │
│       │                                                      │
│       ▼  Step 3: Containerize                                │
│  Docker image (model + code + dependencies = one artifact)   │
│       │                                                      │
│       ▼  Step 4: Push to registry                            │
│  gcr.io/my-project/demand-forecaster:v2.1                    │
│       │                                                      │
│       ▼  Step 5: Deploy with traffic split                   │
│  Load Balancer                                               │
│       ├── 95% → v2.0 (stable / blue)                        │
│       └──  5% → v2.1 (canary / green)                       │
│       │                                                      │
│       ▼  Step 6: Promote or rollback                         │
│  Monitor 24h → if metrics OK → 100% to v2.1                  │
└──────────────────────────────────────────────────────────────┘
```

**Batch vs Real-Time Serving:**
- **Batch**: Run predictions once daily on a large table of inputs. Results stored in a database. Users query the pre-computed results. Example: overnight demand forecasts for 50,000 SKUs. Simpler, cheaper, but stale.
- **Real-Time**: Request arrives → model runs → response returned within milliseconds. Example: ORCA's agent pipeline — a stock alert comes in and the agent decides right now. More complex, but fresh.

## Why Google Cares About This

Google runs hundreds of thousands of model serving instances across products. The difference between a poorly deployed model (512 ms p99 latency, no rollback) and a well-deployed one (50 ms p99, canary releases, instant rollback) is the difference between a product that wins and one that gets killed. In a senior AI interview, Google is checking whether you understand that model quality is only one ingredient — you also need to know how models get *served*, *updated*, and *recovered from failure*. They particularly care about latency SLAs because Google's products have extremely tight user experience budgets (Search is under 200 ms end-to-end).

## Interview Questions & Answers

### Q1: What is the difference between batch and real-time model serving, and how do you choose?

**Answer:** Batch serving runs predictions on a whole dataset at a scheduled time — overnight, hourly, or weekly — and stores the results. Real-time (online) serving runs the model on demand when a request arrives and returns the result synchronously. The choice comes down to three questions: how fresh does the result need to be, how many simultaneous users will there be, and what is the cost per prediction?

Batch is appropriate when freshness requirements are loose. A product recommendation model that refreshes overnight is fine for a streaming service — movies don't change daily. Batch is also far cheaper because you can use spot instances and run during off-peak hours. The tradeoff is that batch predictions become stale: if a user watches 10 movies after the last batch run, their recommendations don't reflect those views until the next morning.

Real-time is required when the input that determines the prediction is only known at request time, or when the cost of staleness is high. ORCA's demand intelligence agent exemplifies this: the stock level, the time of day, the specific SKU, and whether a promotional event is active are all request-time inputs. Pre-computing all combinations is impossible. Real-time also handles tail cases gracefully — a new SKU that didn't exist during batch training can still get a prediction.

A hybrid "near-real-time" pattern is common in practice. Batch runs overnight to precompute baseline predictions. A lightweight real-time layer then applies personalisation on top. Search results are an example: the core relevance score is precomputed; the personalization re-ranking runs in real-time in under 5 ms.

### Q2: What are ONNX and TorchScript and why do model formats matter for deployment?

**Answer:** A PyTorch model trained in a notebook is a Python object. It can only run in an environment that has PyTorch installed — which is 2 GB of dependencies, requires specific CUDA versions, and ties your serving infrastructure to Python. Model formats like ONNX and TorchScript solve this by converting the model into a language-independent representation that specialized runtime engines can execute much faster and in more environments.

ONNX (Open Neural Network Exchange) is an open format developed by Microsoft and Meta. You export your PyTorch model to ONNX once, and then any ONNX-compatible runtime — ONNX Runtime (Microsoft), TensorRT (NVIDIA), OpenVINO (Intel) — can execute it. ONNX Runtime is typically 2–5x faster than plain PyTorch for inference because it does graph optimizations, operator fusion, and precision reduction (FP16 or INT8 quantization) automatically. It also runs on CPU efficiently, which matters enormously for cost: a CPU-only container costs 10x less than a GPU container.

TorchScript is PyTorch's own serialization format. It compiles Python-style model code into a static computation graph that can run without a Python interpreter — useful for embedding models in C++ services (which is how many of Google's serving systems work). The limitation is that TorchScript only works within the PyTorch ecosystem, while ONNX is truly cross-framework.

For LLMs specifically, neither format applies in the same way because LLM weights (70B parameters) can't be easily packed into one ONNX file. Instead, LLM deployment uses purpose-built runtimes: vLLM, TGI (Text Generation Inference by Hugging Face), or managed APIs like Groq's. These use paged attention, continuous batching, and quantization to serve LLMs efficiently. The ORCA project correctly uses Groq as a managed LLM API, which outsources all of this complexity.

### Q3: Explain blue-green deployment and canary releases — why are these important for ML models?

**Answer:** Blue-green deployment means running two identical production environments — "blue" (the current live version) and "green" (the new version). When you're ready to release, you flip the load balancer from blue to green instantly. If something goes wrong, you flip it back in seconds. No gradual rollout — it's a binary switch. Blue-green eliminates downtime during deployment because green is fully warmed up and tested before any live traffic hits it.

Canary releases are more gradual. You route a small percentage of real traffic — say, 5% — to the new version, while 95% still goes to the old version. You watch metrics on the canary group for hours or days. If everything looks good, you progressively increase the canary percentage (5% → 20% → 50% → 100%). If metrics degrade, you pull the canary back to 0% — no user harm at scale.

For ML models, canary is generally preferred over blue-green because model failures are *soft*. A buggy code deploy crashes with a 500 error — detectable immediately. A model that produces subtly worse recommendations doesn't crash; it just makes users slightly less happy. You need time to collect enough signals (click-through rates, thumbs-down rates, conversion rates) to detect this. Canary gives you that time with limited blast radius.

In practice, the canary percentage choice depends on your traffic volume. If you have 10 million daily users, 1% canary means 100,000 users experiencing the new model — enough signal within hours. If you have 10,000 users, you might need 20% canary for the same statistical power.

```
Traffic routing example:
100 requests/sec total

  ┌─────────────────────────────────┐
  │         Load Balancer           │
  └──────┬──────────────┬───────────┘
         │ 95%          │ 5%
         ▼              ▼
   [v2.0 stable]   [v2.1 canary]
   (95 req/sec)    (5 req/sec)
         │              │
    metrics OK?    metrics OK?
    ─────────       ─────────
     YES: keep      YES: promote
     NO: keep       NO: rollback
```

### Q4: What are latency SLAs for ML models and how do you design to meet them?

**Answer:** An SLA (Service Level Agreement) for latency is a promise about how fast your system responds — typically expressed as "P99 latency must be under X milliseconds." P99 means the 99th percentile: 99% of requests must complete within that time. The 1% that exceed it are called "tail latency" and often represent the worst user experiences.

For interactive ML applications, Google's research suggests user tolerance drops sharply beyond 200 ms for web interactions. For mobile, 300 ms feels instant; 1000 ms feels slow. For LLM applications, latency has two components: Time to First Token (TTFT — how long until the user sees the first word) and total generation time. Streaming responses (sending tokens as they're generated) dramatically improve perceived latency even if total time is the same, because users see output immediately.

To design to meet an SLA, you profile the full request path. For ORCA's pipeline, the path is: HTTP request → FastAPI → LangGraph → Agent 1 (CrewAI + Groq API call) → Agent 2 (Groq call) → Agent 3 (Groq call) → Agent 4 (routing) → database write → HTTP response. Each step contributes latency. You identify the biggest contributor (almost certainly the Groq API calls, at ~1-3 seconds each) and optimize there first — caching, parallelizing agent calls where possible, or using a faster model (llama-3.1-8b-instant vs llama-3.3-70b-versatile).

For traditional ML models (not LLMs), the biggest lever is model complexity and format. A 1000-tree Random Forest is 10x slower than a 100-tree one at inference time. Converting to ONNX Runtime with INT8 quantization can cut latency by 4x. For extreme latency requirements (sub-10 ms), you might need to simplify the model itself — trading a percentage point of accuracy for an order-of-magnitude latency improvement.

### Q5: How do you containerize a model for deployment and what goes into the Docker image?

**Answer:** Containerizing a model means packaging it and all its dependencies into a Docker image — a self-contained snapshot of the exact environment needed to run the model. The image includes: the Python version, all pip packages (pinned to exact versions), the serving code (FastAPI app), and the model artifact itself (weights file, ONNX file, or a pointer to a model registry).

A well-written `Dockerfile` for ML follows the principle of layer caching. Layers that change rarely (base OS, Python install, pip packages) go first. Layers that change frequently (application code, model weights) go last. This means most Docker rebuilds only re-execute the last few lines — taking seconds instead of minutes.

```dockerfile
# Good layer ordering for ML Docker images
FROM python:3.11-slim           # base OS — almost never changes
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt   # packages — changes rarely
COPY model.onnx /app/model/           # model — changes on new version
COPY api/ /app/api/                   # code — changes most often
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

One important deployment decision is whether to bake the model weights into the image or load them at startup from a model registry. Baking weights makes the image self-contained and portable — it starts instantly with no network dependency. But a 1 GB model makes the image huge, and pushing a new 1 GB image to a container registry for every code change is slow. The alternative — loading weights from a registry (like MLflow artifacts or S3) at container startup — keeps images small but requires network access and adds 10-30 seconds to cold start time.

For ORCA's use case, the model is a third-party API (Groq), so there are no model weights to package. The Docker image contains only the FastAPI application code, the RAG index (ChromaDB), and the policy documents. This is why `requirements.api.txt` deliberately excludes `torch` and `sentence-transformers` — the Render deployment keeps the image under 512 MB by removing the heavy embedding packages used only during local development.

## Key Points to Say in the Interview

- The "notebook to production" gap is an engineering problem, not a data science problem — it requires packaging, serving, monitoring, and rollback
- Batch vs real-time is a freshness-vs-cost tradeoff; explain both and when each is right
- ONNX/TorchScript decouple the model from Python and enable faster, cheaper runtimes
- Blue-green is for instant cutover; canary is for gradual validation — use canary for ML because failures are soft
- P99 latency, not P50, is the relevant SLA metric — tail latency is where user experience breaks
- For LLMs, TTFT (time to first token) and streaming are as important as total latency
- Layer your Dockerfile properly: dependencies first, code last, for fast rebuilds

## Common Mistakes to Avoid

- Do NOT say "just pickle the model and serve it from Flask" — this ignores portability, format, and production robustness concerns
- Do NOT forget rollback in any deployment story — always have a plan to undo the deployment
- Do NOT conflate model training time with model inference time — they are separate phases with completely different performance profiles
- Do NOT assume GPU is always needed for inference — most traditional ML models and quantized LLMs run fine on CPU
- Do NOT ignore cold start time when designing containerized ML deployments — a model that takes 90 seconds to load is unusable in auto-scaling scenarios

## Further Reading

- [Patterns for Model Deployment — Martin Fowler](https://martinfowler.com/articles/ml-deployment-strategy.html) — Systematic catalog of ML deployment patterns from a software architecture perspective
- [ONNX Runtime Performance Tuning](https://onnxruntime.ai/docs/performance/tune-performance.html) — Official docs on quantization and graph optimizations for faster inference
- [Google Cloud: Serving ML Predictions](https://cloud.google.com/architecture/ml-on-gcp-best-practices) — Google's own best practices for production ML serving on GCP
- [ByteByteGo: How to Deploy ML Models](https://blog.bytebytego.com/p/how-to-deploy-machine-learning-models) — Visual system design walkthrough of model serving infrastructure
- [vLLM: High-throughput LLM Serving](https://docs.vllm.ai/en/latest/) — The leading open-source LLM serving framework; relevant for understanding how managed APIs like Groq work internally
