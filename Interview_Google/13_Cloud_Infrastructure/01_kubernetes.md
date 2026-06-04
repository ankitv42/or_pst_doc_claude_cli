# Kubernetes — Container Orchestration at Scale

## What Is It? (Plain English)

Imagine you are managing a large warehouse with hundreds of workers (programs) doing different tasks. Without a manager, if a worker collapses, nobody fills in. If demand spikes, you have no way to quickly hire more workers. Kubernetes (often abbreviated as "K8s") is that warehouse manager. It is an open-source system that automatically deploys, scales, and heals your software containers across a cluster of machines.

A container is a lightweight, self-contained package of code and its dependencies (we cover containers fully in `02_docker.md`). Kubernetes takes those containers and decides: which machine should run them, how many copies to run, what to do if one crashes, and how to route network traffic to them. It was originally built by Google (derived from their internal system called "Borg") and is now the de-facto standard for running software at any serious scale.

For AI and ML workloads specifically, Kubernetes has become essential because training jobs, inference servers, and data pipelines all have different resource needs (some need lots of GPUs, some need lots of RAM, some need fast storage) and Kubernetes is the layer that can schedule all of them efficiently on a shared pool of machines. Tools like Kubeflow sit on top of Kubernetes and add ML-specific features like experiment tracking, pipeline orchestration, and model serving.

## How It Works

Kubernetes organises resources into a hierarchy. At the bottom are containers. Containers are grouped into **Pods** (the smallest deployable unit — usually one container per pod). Pods are managed by **Deployments** (which say "keep 5 replicas of this pod running always"). Deployments live in **Namespaces** (logical partitions, like "dev", "prod", "ml-team"). Everything runs on a **Node** (a physical or virtual machine). Nodes are grouped into a **Cluster**.

The **Control Plane** is the brain:
- `kube-apiserver` — the front door; all commands go through it
- `etcd` — the database storing all cluster state (what should exist)
- `kube-scheduler` — decides which node a new pod should land on
- `kube-controller-manager` — watches reality vs desired state, fixes differences

On each worker node, the **kubelet** agent talks to the control plane and actually starts/stops containers.

```ascii
┌─────────────────────────────────────────────────────────────────────┐
│                         KUBERNETES CLUSTER                          │
│                                                                     │
│  ┌──────────────────── CONTROL PLANE ────────────────────────────┐  │
│  │  kube-apiserver  │  etcd (state)  │  scheduler  │  controller │  │
│  └──────────────────────────────────────────────────────────────-┘  │
│           │ (instructions)                  ↑ (status reports)      │
│           ▼                                 │                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                      WORKER NODES                              │  │
│  │                                                                │  │
│  │  Node 1 (CPU)          Node 2 (CPU)        Node 3 (GPU)        │  │
│  │  ┌──────────────┐     ┌──────────────┐    ┌──────────────┐    │  │
│  │  │ Namespace:   │     │ Namespace:   │    │ Namespace:   │    │  │
│  │  │   prod       │     │   prod       │    │  ml-training │    │  │
│  │  │ ┌──────────┐ │     │ ┌──────────┐ │    │ ┌──────────┐ │    │  │
│  │  │ │  Pod A   │ │     │ │  Pod A   │ │    │ │ TrainJob │ │    │  │
│  │  │ │(api:v2)  │ │     │ │(api:v2)  │ │    │ │(CUDA)    │ │    │  │
│  │  │ └──────────┘ │     │ └──────────┘ │    │ └──────────┘ │    │  │
│  │  │ ┌──────────┐ │     │ ┌──────────┐ │    │              │    │  │
│  │  │ │  Pod B   │ │     │ │  Pod C   │ │    │   kubelet    │    │  │
│  │  │ │ (cache)  │ │     │ │ (worker) │ │    │   (agent)    │    │  │
│  │  │ └──────────┘ │     │ └──────────┘ │    └──────────────┘    │  │
│  │  └──────────────┘     └──────────────┘                        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Services (stable IPs)  │  Ingress (external traffic routing)  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

When a pod crashes, the controller notices actual state (4 pods) diverges from desired state (5 pods) and schedules a replacement. This is **auto-healing**. When CPU load spikes, the Horizontal Pod Autoscaler adds more pod replicas. When the cluster itself runs out of nodes, the Cluster Autoscaler provisions new VMs from the cloud provider.

## Why Google Cares About This

Google invented the concepts behind Kubernetes (their internal system Borg ran millions of containers). For senior AI/ML roles, Google expects you to understand how models actually get deployed and scaled — not just the algorithm side. Production ML requires running multiple services (feature pipelines, model servers, monitoring daemons), managing GPU resources, and ensuring zero-downtime deployments. Kubernetes is the foundation for all of that. Questions about K8s signal whether you have genuinely shipped AI systems to production, not just trained models in a notebook.

## Interview Questions & Answers

### Q1: What is a Kubernetes Pod and why is it the basic unit rather than a container?

**Answer:** A Pod is the smallest deployable unit in Kubernetes and represents one or more containers that should always run together on the same node and share the same network namespace (they communicate via `localhost`) and storage volumes. The reason Kubernetes chose the pod as its basic unit rather than a raw container is that real-world applications sometimes require tightly-coupled helper processes.

A classic example is a web server container paired with a log-shipping "sidecar" container. These two containers need to share a filesystem (the web server writes logs, the sidecar reads and ships them) and must always be co-located. If Kubernetes scheduled them independently as raw containers, it could not guarantee they land on the same node. The pod concept solves this by treating the group as one atomic unit.

For AI workloads, a common pattern is a model-serving pod that contains the inference server plus a lightweight Prometheus metrics exporter as a sidecar. The inference server writes metrics to a shared volume; the exporter reads them and exposes them on port 9090. Both are in one pod, always co-located, and Kubernetes manages them as a single unit.

In practice, the vast majority of pods contain just one container. The multi-container pod is a design pattern ("sidecar", "ambassador", "adapter") rather than the default. When you see a Kubernetes Deployment file, the `spec.template.spec.containers` list usually has a single entry — but the architecture allows for more when needed.

### Q2: Explain the difference between a Deployment, a StatefulSet, and a DaemonSet.

**Answer:** These three are Kubernetes "workload resources" — higher-level objects that manage pods for you. They differ in the guarantees they make about pod identity and scheduling.

A **Deployment** is for stateless applications. Every pod is interchangeable — you can kill pod A and replace it with pod B and nothing breaks because they hold no unique state. Your web API servers, ML inference endpoints, and background workers are typically Deployments. If you have a Deployment with 5 replicas and one pod crashes, Kubernetes creates a new replacement pod with no memory of what the crashed pod was doing.

A **StatefulSet** is for stateful applications like databases (PostgreSQL, Cassandra, ZooKeeper). Each pod gets a stable, predictable name (`pod-0`, `pod-1`, `pod-2`), a stable network identity (the DNS name stays the same even after restart), and its own persistent volume that follows it around. If `pod-1` crashes, Kubernetes recreates it with the same name and reattaches the same volume. This is essential for distributed databases that elect a leader by pod name, or for ML systems where each worker needs to know exactly which shard of data it owns.

A **DaemonSet** ensures exactly one pod runs on every node (or every node matching a label selector). This is perfect for infrastructure-level concerns: log collectors (fluentd), metrics agents (Prometheus node-exporter), security scanners, or — relevantly for AI — GPU device plugins that make the GPU visible to other pods. When a new node joins the cluster, Kubernetes automatically schedules the DaemonSet pod onto it.

The mental model: Deployment = "run N copies somewhere", StatefulSet = "run N copies, each with a permanent identity", DaemonSet = "run one copy everywhere".

### Q3: How does Kubernetes handle scaling for ML inference workloads, and what are the challenges?

**Answer:** Kubernetes provides two main scaling mechanisms. The **Horizontal Pod Autoscaler (HPA)** adds or removes pod replicas based on metrics like CPU utilisation or custom metrics (e.g., requests per second). The **Cluster Autoscaler** adds or removes nodes from the underlying cloud cluster when pods cannot be scheduled due to insufficient capacity.

For ML inference, the challenge is that model servers have a **cold start problem**. A PyTorch model server might take 30-120 seconds to start up: it needs to pull a Docker image (often several GB), load model weights from storage into GPU memory, and warm up the JIT compiler. During this window, new pods cannot serve traffic. If you scale from 2 to 5 replicas in response to a traffic spike, the 3 new pods will not be ready for 1-2 minutes, during which your 2 existing pods are overloaded.

Mitigation strategies include: (1) **pre-warming** — always keeping a minimum number of pods running even at low traffic, never scaling to zero; (2) **readiness probes** — telling Kubernetes not to send traffic to a pod until it passes a health check (model weights loaded); (3) **KEDA (Kubernetes Event-Driven Autoscaling)** — scaling based on queue depth (if 500 inference requests are queued, scale up) rather than CPU, which is a more accurate signal for ML workloads; (4) **cached model weights** on a fast shared filesystem (NFS or CSI) so new pods load weights in seconds rather than fetching from object storage.

GPU scheduling adds another layer: Kubernetes requires the `nvidia.com/gpu` resource plugin (a DaemonSet) to be installed on GPU nodes. You request GPUs in the pod spec with `resources.limits["nvidia.com/gpu"]: 1`. The scheduler only places the pod on a node with available GPUs. For multi-GPU pods (distributed training), tools like Kubeflow's `MPIJob` or `PyTorchJob` custom resources manage multi-pod coordination automatically.

### Q4: What is a Kubernetes Service and why do you need it if pods already have IP addresses?

**Answer:** Every pod gets its own IP address — but pod IP addresses are ephemeral. When a pod crashes and is replaced, its replacement gets a completely different IP address. If Service A needs to call Service B and is hardcoded to Service B's pod IP `10.0.0.45`, it will break the moment that pod is replaced and gets IP `10.0.0.78`.

A **Kubernetes Service** is a stable, permanent virtual IP address (and DNS name) that acts as a load balancer in front of a set of pods selected by label. You create a Service with `selector: app=model-server`, and Kubernetes automatically routes traffic from the Service IP to any pod with that label, distributing load across all healthy replicas. The Service IP never changes even as pods come and go.

There are four types of Services: **ClusterIP** (internal-only, the default), **NodePort** (exposes a port on every node's public IP), **LoadBalancer** (provisions a cloud load balancer with an external IP — this is how you expose an ML API to the internet), and **ExternalName** (maps to an external DNS name for calling outside services).

For AI systems, a typical setup is: a `LoadBalancer` Service exposing the FastAPI inference endpoint to the internet, a `ClusterIP` Service for internal communication between the API and the model server, and a `ClusterIP` Service for the vector database (ChromaDB). External clients hit the LoadBalancer; the API calls the model server and vector DB via stable internal DNS names like `model-server.default.svc.cluster.local:8080`.

### Q5: What is Kubeflow and how does it extend Kubernetes for ML workloads?

**Answer:** Kubeflow is an open-source ML platform that runs on top of Kubernetes and adds ML-specific abstractions that raw Kubernetes lacks. It was created by Google and is essentially "Kubernetes for ML teams." Where Kubernetes provides generic pod scheduling, Kubeflow provides purpose-built resources for the specific patterns that ML engineers encounter daily.

The core components include: **Kubeflow Pipelines** — a workflow orchestration tool (similar to Airflow but designed for ML) that lets you define multi-step ML pipelines (data preprocessing → training → evaluation → deployment) as Python functions with automatic caching, artifact tracking, and a visual UI. **KFServing / KServe** — a model serving layer that handles autoscaling, canary deployments, and multi-model serving with a simple interface, supporting TensorFlow, PyTorch, and custom models. **Katib** — automated hyperparameter tuning using Bayesian optimisation, running many parallel training jobs and tracking which hyperparameters produce the best validation loss.

The **PyTorchJob and TFJob** custom resources (part of the Training Operator) let you describe distributed training jobs. You specify the number of workers and parameter servers, and the operator handles pod creation, inter-pod communication setup (via MPI or NCCL), and clean-up after training completes. This is far simpler than manually orchestrating distributed training with raw Kubernetes.

For a senior AI engineer at Google, the key thing to communicate is that Kubeflow provides **reproducibility** (every pipeline run is logged with its exact code version, data version, and hyperparameters), **resource efficiency** (training jobs release GPU nodes when done; inference services scale to zero at night), and **governance** (access control on pipelines, experiment lineage for audits). These are exactly the properties Google DeepMind and Google Cloud AI teams care about when building production ML systems.

## Key Points to Say in the Interview

- Kubernetes manages desired state vs actual state — the control loop reconciles differences
- Pods are ephemeral; Services provide stable network identity
- Namespaces partition a cluster for multi-team use (dev/prod separation, cost attribution)
- HPA scales pods; Cluster Autoscaler scales nodes — both are needed for ML workloads
- GPU scheduling requires the NVIDIA device plugin (DaemonSet) + resource requests in pod spec
- Cold start latency is the main scaling challenge for ML inference — mitigate with readiness probes and minimum replica counts
- Kubeflow adds ML-specific abstractions on top of raw Kubernetes
- KEDA enables event-driven scaling for queue-based inference workloads

## Common Mistakes to Avoid

- Do not say "Kubernetes replaces Docker" — Docker creates the images; Kubernetes orchestrates the containers
- Do not confuse a Pod with a container — a pod wraps one or more containers and adds network/storage sharing
- Do not claim you can just use `HPA` alone for ML workloads — GPU cold starts make naive CPU-based scaling dangerous without readiness probes
- Do not forget that StatefulSets are required for any database workload — using a Deployment for a database is a data-loss risk
- Do not describe Kubernetes as "just a scheduler" — the control plane is a full distributed systems platform with API server, state store, and multiple controllers

## Further Reading

- [Kubernetes Official Documentation](https://kubernetes.io/docs/home/) — The authoritative reference; start with the "Concepts" section
- [Kubeflow Documentation](https://www.kubeflow.org/docs/) — Full guide to ML workloads on Kubernetes
- [Google's Borg Paper (original K8s predecessor)](https://research.google/pubs/pub43438/) — The academic paper describing the system that inspired Kubernetes
- [KEDA — Kubernetes Event-Driven Autoscaling](https://keda.sh/docs/) — The standard way to autoscale ML inference queues
- [NVIDIA GPU Operator for Kubernetes](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/overview.html) — How to enable GPU scheduling in a Kubernetes cluster
