# Autoscaling — Automatically Adjusting Capacity

## What Is It? (Plain English)

Autoscaling is the ability of a system to automatically add or remove computing resources in response to changing demand. Without autoscaling, you must decide in advance how much capacity to provision: too little and your service falls over during peak traffic; too much and you pay for idle servers at 3 AM. Autoscaling lets you run with exactly the right amount of capacity at all times, responding to real-world demand dynamically.

Think of a restaurant. A fixed-staff restaurant hires 10 servers and they work every day — fine during the lunch rush, wasteful at 2 PM, and disastrous during an unexpected catering order. An autoscaling restaurant automatically calls in extra servers when the queue gets long and sends them home when it quiets down. Cloud computing made this possible because servers can be rented by the minute and provisioned in seconds.

For AI systems, autoscaling is particularly important and particularly challenging. An ML inference endpoint might handle 100 requests per minute at 2 AM and 50,000 requests per minute at 2 PM on a Monday. Without autoscaling, you either provision for the peak (paying for idle capacity 23 hours a day) or provision for the average (and your service crashes during peaks). With autoscaling, you run with minimal capacity at night and automatically scale out to handle the peak, then scale back down. The challenge — which we explore in depth — is that AI models have startup latency (loading model weights takes time) that makes rapid scale-out harder than for stateless web services.

## How It Works

In Kubernetes, autoscaling operates at two levels that work together.

The **Horizontal Pod Autoscaler (HPA)** operates within the existing cluster. It watches a metric (CPU utilisation, memory usage, or custom metrics like request queue depth) and increases or decreases the number of pod replicas. If 3 replicas are running at 80% CPU and the target is 50%, HPA calculates `ceil(3 × 80/50) = 5` replicas and creates 2 more. It also has a cooldown period to prevent oscillation (waiting 5 minutes before scaling down to avoid thrashing).

The **Cluster Autoscaler (CA)** operates at the infrastructure level. When HPA wants to create new pods but the cluster has no nodes with available capacity, those pods remain "Pending" (unscheduled). CA detects pending pods, requests new VMs from the cloud provider (EC2/GCE/Azure VM), waits for them to join the cluster (typically 2-5 minutes), and then HPA's new pods get scheduled on the fresh nodes. When demand drops and pods are removed, CA detects underutilised nodes and removes them (after gracefully draining their pods).

```ascii
AUTOSCALING FLOW

  User Traffic
       │
       ▼
  Load Balancer
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Horizontal Pod Autoscaler (HPA)             │  │
│  │   Watches: CPU / custom metric (queue depth, RPS)        │  │
│  │   Decision: more replicas? fewer replicas?               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│               ┌──────────▼──────────┐                          │
│  Node 1       │     Pod Pool        │        Node 3            │
│  ┌─────────┐  │  Pod 1  Pod 2  Pod3 │  ┌─────────┐  (waiting  │
│  │CPU: 75% │  │   ↑ scale up to     │  │CPU: 30% │   for more │
│  └─────────┘  │   5 pods...         │  └─────────┘   capacity)│
│               └──────────-──────────┘                          │
│                          │                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Cluster Autoscaler (CA)                     │  │
│  │   Detects: pending pods that can't be scheduled          │  │
│  │   Action: request new VM from cloud provider             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│              Cloud Provider API (AWS/GCP/Azure)                 │
│              "Provision one more VM of type g4dn.xlarge"        │
│              [2-5 minutes later: new node joins cluster]        │
└─────────────────────────────────────────────────────────────────┘

SCALE-TO-ZERO (Knative / KEDA):
Traffic = 0 ──► All pods terminated (no idle cost)
Traffic spike ──► Cold start: ~60-120s for ML models
                  Warm start: ~2s for stateless API
```

**KEDA (Kubernetes Event-Driven Autoscaling)** extends Kubernetes with the ability to scale based on external event sources — the length of an SQS queue, the number of messages in a Kafka topic, the depth of a Redis list, or the request rate to a REST endpoint. For ML batch inference (where jobs arrive in a queue), KEDA is more accurate than CPU-based HPA: if the queue has 10,000 pending items and each pod processes 100 items/minute, KEDA can immediately scale to the exact number of pods needed to drain the queue within an SLA.

**Scale-to-zero** means reducing to 0 running instances when there is no traffic, eliminating all idle costs. Knative and KEDA both support this. For ML inference, scale-to-zero is attractive for infrequently-used endpoints but requires careful handling of cold start latency.

## Why Google Cares About This

Google runs services at a scale where inefficient resource utilisation is catastrophically expensive. A 10% reduction in idle capacity across Google's fleet would save hundreds of millions of dollars annually. For AI workloads, Google has developed sophisticated autoscaling for Borg (their internal cluster manager) and for Kubernetes/GKE. In interviews for senior roles, autoscaling questions assess whether you understand system design at scale — not just "it scales automatically" but the specific mechanisms, trade-offs, and failure modes.

## Interview Questions & Answers

### Q1: Explain the difference between Horizontal Pod Autoscaler and Vertical Pod Autoscaler in Kubernetes.

**Answer:** Horizontal Pod Autoscaler (HPA) and Vertical Pod Autoscaler (VPA) both respond to resource pressure, but they scale in different directions. HPA adds more pod replicas (scaling out); VPA adjusts the CPU and memory resource requests of existing pods (scaling up). The analogy: HPA hires more workers; VPA gives each worker a bigger desk.

HPA is appropriate for stateless, horizontally scalable workloads where running more copies of the same pod provides more capacity. Most web services, API servers, and batch processors fall into this category. HPA integrates tightly with Kubernetes' native scheduling and works in real-time — it can add pods within 15-30 seconds of detecting the trigger metric.

VPA is appropriate for workloads where the bottleneck is that individual pods are under-resourced rather than that there are too few pods. A machine learning model server that was originally allocated 4 GB of RAM but is actually using 12 GB will be killed by Kubernetes OOM (Out of Memory) killer. VPA detects this, recommends (or automatically applies) a higher memory limit, and prevents the crashes. The trade-off is that applying VPA recommendations currently requires restarting pods (the new resource allocation takes effect on the next pod startup), which creates brief service interruptions.

In practice, HPA and VPA can conflict if both try to resize the same deployment simultaneously (VPA restarts pods while HPA is actively scaling them). The recommended pattern is to use VPA in "recommendation mode" (it suggests resource changes but does not apply them) to right-size your resource requests, commit those to your Deployment manifest, and then use HPA for live scaling. For ML workloads specifically, VPA is valuable during the initial deployment phase when you do not know the true memory footprint of a model server, and HPA takes over for production scaling.

### Q2: What is cold start latency and how do you mitigate it for ML inference autoscaling?

**Answer:** Cold start latency is the time between "a new pod is requested by the autoscaler" and "that pod is ready to serve its first inference request." For a stateless web API, cold start might be 2-5 seconds (pull a small image, start the process). For an ML inference server, cold start can be 2-10 minutes. The sequence is: provision a VM (2-5 min if a new node is needed), pull the Docker image (30-120s for a multi-GB image), start the Python process and import libraries (10-30s), load model weights from storage into GPU memory (30-120s depending on model size and storage speed), run warmup requests to initialise the CUDA kernels and JIT compiler (15-60s for PyTorch).

During this entire window, the new pod is not handling user traffic. If a traffic spike triggers scale-out, users are impacted for the full duration of the cold start before additional capacity is available.

Mitigation strategies, in order of effectiveness: First, **never scale to zero for user-facing endpoints** — keep a minimum of 2-3 pods always running (1 for traffic, 1-2 on standby). The idle cost is minimal compared to the SLA risk. Second, **reduce image pull time** by pre-fetching images onto nodes before they are needed. Kubernetes supports `imagePullPolicy: IfNotPresent` and you can daemonize a pre-puller. DaemonSets can pull ML images to all nodes nightly, so the image is already present when a new pod is scheduled. Third, **use a fast model weight cache** — store weights on a shared filesystem (NFS, AWS EFS, GCP Filestore) rather than pulling from object storage. Weights that live on NFS can be memory-mapped, reducing load time from 90 seconds to under 5 seconds. Fourth, **use Kubernetes readiness probes correctly** — configure the probe to return "ready" only after the model is fully loaded (call a `/health` endpoint that returns 200 only after the first warmup inference succeeds). HPA will not send traffic to the pod until it passes the readiness check. Fifth, **pre-warm with scheduled scaling** — if you know traffic spikes at 9 AM every Monday, use a CronJob or KEDA's scheduled scaler to begin scaling at 8:45 AM rather than reactively at 9:05 AM.

### Q3: How does KEDA differ from HPA and when is it the right choice for an ML workload?

**Answer:** HPA's built-in scalers primarily watch CPU utilisation and memory usage (with the Metrics Server) or custom Prometheus metrics. For synchronous web services (user makes a request, waits for a response), CPU is often a reasonable proxy for load — more requests equals more CPU. But for async, queue-based ML workloads, CPU is a lagging and unreliable indicator.

Consider a batch ML inference pipeline: images are submitted to an SQS queue by upstream services, and worker pods pull from the queue and run inference. When the queue has 5,000 pending messages, the currently-running pods might be at 70% CPU — not high enough to trigger HPA scale-out. But the business SLA says inference must complete within 1 hour, requiring at least 10 pods. HPA (watching CPU) would not scale to 10 until CPU hits the target threshold, potentially missing the SLA.

KEDA (Kubernetes Event-Driven Autoscaling) scales directly on the queue depth. You configure: "desired replicas = queue_length / 500 (items each pod can process per minute), min = 1, max = 50." When 5,000 messages are in the queue, KEDA immediately creates 10 pods. When the queue drains to zero, KEDA scales back to 1 (or 0 if scale-to-zero is enabled). KEDA integrates natively with AWS SQS, Google Pub/Sub, Azure Service Bus, Kafka, Redis, Prometheus, and dozens of other event sources — requiring no custom metric adapter.

For LLM inference workloads, KEDA can scale on the number of requests in a request queue (using a Redis or Kafka queue as a buffer in front of the model server). This decouples the rate of incoming requests from the capacity of the model server, giving the autoscaler time to respond to spikes without dropping requests. This is the production-grade pattern used by companies running LLM APIs at scale.

### Q4: What is scheduled scaling and when does it outperform reactive autoscaling for AI systems?

**Answer:** Reactive autoscaling responds to metrics as they happen — it observes CPU or queue depth, determines capacity is insufficient, and triggers scale-out. There is always a lag between "load increases" and "new capacity is available." For ML workloads with cold start times of several minutes, this lag can cause significant SLA breaches.

Scheduled scaling pre-provisions capacity before demand arrives, based on known usage patterns. If your data shows that inference traffic spikes every weekday morning at 9 AM (when business users arrive), you configure a scheduled scaler to increase replica count from 3 to 10 at 8:45 AM — 15 minutes before the spike — and scale back to 3 at 6 PM. The capacity is ready when demand arrives, not 5 minutes after.

In Kubernetes, scheduled scaling is implemented via KEDA's `CronTriggerAuthentication` and `ScaledObject` with a cron schedule, or by a simple Kubernetes CronJob that patches the Deployment's replica count via the API. On GCP, Cloud Scheduler + a Cloud Run function that calls the Kubernetes API is another approach. AWS Application Auto Scaling supports scheduled scaling natively for ECS and DynamoDB, and SageMaker Inference has a similar feature.

The practical implementation for an ORCA-like inventory system: the system knows from historical data that procurement managers run analyses at 8-10 AM every morning. You schedule an increase in inference endpoint replicas from 2 to 8 at 7:45 AM, reducing ML API latency during peak usage. The cost is 6 extra GPU-hours per day (one A100 × 6 additional pods for ~1 hour) — far less than the SLA cost of 5-minute cold starts hitting 50 concurrent users.

Scheduled scaling works best when combined with reactive scaling as a baseline. The schedule handles predictable patterns; HPA handles unexpected spikes above the scheduled level.

### Q5: What are the autoscaling challenges specific to ML inference compared to regular web services, and how do you design around them?

**Answer:** Standard web services (REST APIs, microservices) are lightweight, stateless, and start in seconds. ML inference services are heavyweight, stateful (model weights in memory), and start in minutes. This difference makes direct application of standard autoscaling wisdom incorrect for AI.

The first challenge is **state and warm-up**. A web service can be killed and replaced instantly with no consequences. An ML inference pod that is in the middle of a long (60+ second) inference job cannot be killed without either aborting the job (losing work and failing the user) or waiting for it to drain (which delays scale-down). The solution is a Kubernetes `terminationGracePeriodSeconds` setting that gives the pod time to finish in-flight requests before being killed, plus a `/shutdown` endpoint in the model server that stops accepting new requests and waits for current ones to complete.

The second challenge is **GPU resource fragmentation**. GPU-backed pods can only land on nodes with available GPU capacity. If your cluster has 10 GPU nodes, each with 1 A100, and all 10 pods are running at 60% load (each on one node), HPA wants to scale to 15 pods. But there are only 10 GPU nodes. The Cluster Autoscaler must provision 5 more GPU nodes — which takes 3-5 minutes on AWS. Meanwhile, the 10 existing pods are overloaded. The solution is to keep "warm spare" GPU nodes at minimum scale (e.g., always maintain 2 empty GPU nodes) so that scale-out pod scheduling is immediate.

The third challenge is **autoscaling metrics for LLMs**. For traditional services, CPU is a reasonable proxy for throughput. For LLM inference, the bottleneck is often GPU memory bandwidth and the number of tokens being processed (not CPU). A model server might have 30% CPU but 98% GPU utilisation. Standard HPA (watching CPU) would not trigger scale-out. The solution: expose GPU utilisation, GPU memory usage, or request latency as custom Prometheus metrics, and configure HPA with `custom.metrics.k8s.io` or KEDA to scale on these signals. NVIDIA's DCGM Exporter provides GPU metrics in Prometheus format automatically.

The design principle that resolves all three challenges: **accept that ML autoscaling cannot be fully reactive**. Build hybrid systems that use scheduled scaling for predictable patterns, maintain warm capacity buffers, expose the right metrics (GPU, queue depth, latency — not just CPU), and set generous readiness probes so traffic routing is correct before a pod counts as available.

## Key Points to Say in the Interview

- HPA scales pod count; Cluster Autoscaler scales node count — both are needed for end-to-end autoscaling
- ML inference has 2-10 minute cold starts — reactive autoscaling alone is not sufficient; use minimum replica counts and scheduled scaling
- KEDA enables scaling on queue depth, making it more accurate than CPU-based HPA for batch ML workloads
- Scale-to-zero eliminates idle costs but requires handling cold start latency — only suitable for non-latency-sensitive workloads
- GPU nodes take 3-5 minutes to provision — maintain warm spare GPU nodes to avoid this delay on scale-out
- Readiness probes prevent traffic from reaching pods before model weights are fully loaded
- Scheduled scaling handles predictable traffic patterns; reactive scaling handles unexpected spikes

## Common Mistakes to Avoid

- Do not say "just watch CPU for ML autoscaling" — GPU utilisation and request queue depth are more accurate signals
- Do not recommend scale-to-zero for user-facing ML endpoints without addressing the cold start problem
- Do not forget `terminationGracePeriodSeconds` — without it, Kubernetes kills pods mid-inference
- Do not ignore the Cluster Autoscaler — HPA can only work within existing cluster capacity; someone has to provision the nodes
- Do not treat autoscaling as a one-size-fits-all solution — the right configuration requires load testing with realistic traffic patterns

## Further Reading

- [Kubernetes HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) — Official reference for Horizontal Pod Autoscaler configuration
- [KEDA Documentation](https://keda.sh/docs/2.13/concepts/) — Complete guide to event-driven autoscaling for Kubernetes
- [Kubernetes Cluster Autoscaler](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md) — FAQ covering common Cluster Autoscaler questions and failure modes
- [Google Cloud Run Autoscaling](https://cloud.google.com/run/docs/about-instance-autoscaling) — Google's serverless autoscaling documentation
- [AWS Application Auto Scaling for SageMaker](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling.html) — SageMaker-specific autoscaling patterns
