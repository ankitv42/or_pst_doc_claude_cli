# AWS vs Azure vs GCP — Choosing the Right Cloud for AI

## What Is It? (Plain English)

Cloud computing means renting computing infrastructure (servers, storage, databases, networking) from a provider instead of buying and running your own hardware. The three dominant providers — Amazon Web Services (AWS), Microsoft Azure, and Google Cloud Platform (GCP) — together account for over 65% of the global cloud market. They offer nearly identical core capabilities but differ significantly in their AI/ML offerings, pricing models, and ecosystem maturity.

Think of the cloud providers like three large cities. All three have airports, hotels, restaurants, and taxis. But one might have the best tech scene (GCP for AI), another might be best connected to an existing enterprise ecosystem (Azure for companies already using Microsoft products), and the third might have the largest number of available services and the most mature marketplace (AWS). Choosing a cloud for an AI project is not just about raw capability — it involves data residency requirements, existing organisational relationships, staff expertise, and which managed services genuinely reduce engineering effort.

For AI and ML specifically, the cloud has transformed what is possible. Training a large language model in-house requires buying millions of dollars of GPUs, hiring specialised infrastructure engineers, and running a cooling system. On AWS, Azure, or GCP, you can rent 256 A100 GPUs for 24 hours, pay a few thousand dollars, and return them. This democratisation of compute is why AI has accelerated so rapidly in the last decade.

## How It Works

Each provider organises its services into layers. The bottom layer is raw compute and storage. Above that are managed databases and networking. Above that are application services. At the top are fully-managed AI platforms that abstract away most infrastructure concerns.

```ascii
SERVICE ABSTRACTION LAYERS (all three clouds follow this pattern)

HIGH ─────────────────────────────────────────────────────────────── LOW
      Fully-managed AI     Managed Services      Raw Infrastructure
         (highest                                  (most control,
      abstraction, least                           most ops burden)
        control)
─────────────────────────────────────────────────────────────────────────
AWS   SageMaker           RDS, DynamoDB,         EC2, S3, VPC
      Bedrock             ElastiCache, EKS        Lambda

Azure Azure ML            Azure SQL, Cosmos DB,   VMs, Blob Storage,
      Azure OpenAI        Azure Cache, AKS        Azure Functions

GCP   Vertex AI           Cloud SQL, Firestore,   GCE, GCS, VPC
      Gemini API          Memorystore, GKE        Cloud Run
─────────────────────────────────────────────────────────────────────────

COMPUTE COMPARISON:
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Category         │ AWS              │ Azure            │ GCP              │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ VMs              │ EC2              │ Virtual Machines │ Compute Engine   │
│ Object Storage   │ S3               │ Blob Storage     │ Cloud Storage    │
│ Serverless       │ Lambda           │ Azure Functions  │ Cloud Run        │
│ Managed K8s      │ EKS              │ AKS              │ GKE              │
│ ML Platform      │ SageMaker        │ Azure ML         │ Vertex AI        │
│ Managed LLM API  │ Bedrock          │ Azure OpenAI     │ Vertex Gemini    │
│ GPU VMs          │ p4d (A100)       │ NDv4 (A100)      │ a2 (A100)        │
│ TPUs             │ Not available    │ Not available    │ TPU v4/v5        │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

**Serverless compute** (Lambda/Functions/Cloud Run) lets you run code without managing servers — you provide a function or a container, and the cloud provider handles scaling from zero to thousands of invocations and back. You pay only for the milliseconds your code actually runs. For AI, serverless is excellent for lightweight API endpoints that wrap a model call, or for preprocessing pipelines with variable load.

**Managed ML platforms** (SageMaker/Azure ML/Vertex AI) provide integrated environments for the full ML lifecycle: data labelling, experiment tracking, feature stores, model training (with auto-scaling GPU clusters), model registries, and model deployment with A/B testing. The trade-off is that they are opinionated — they work best when you use their entire stack. Mixing, for example, Azure ML training with SageMaker deployment creates friction.

## Why Google Cares About This

Google invented GCP and Vertex AI. For a senior AI/ML role at Google, you must understand multi-cloud realities (many Google Cloud customers also have workloads on AWS), the competitive landscape (why customers might choose Vertex AI over SageMaker), and the architectural trade-offs involved. Questions about cloud architecture are a proxy for whether you can design systems that scale, handle failure, and manage costs — all of which are central to senior engineering roles.

## Interview Questions & Answers

### Q1: How would you choose between AWS, Azure, and GCP for a new AI/ML project?

**Answer:** The choice is rarely purely technical — organisational, contractual, and ecosystem factors often dominate. The right framework is to evaluate five dimensions: existing infrastructure, team expertise, AI/ML ecosystem quality, data residency requirements, and commercial relationships.

If the company is an enterprise already deep in Microsoft products (Office 365, Active Directory, Power BI), Azure is often the default because integration with existing identity management (Azure Active Directory), security tooling, and analytics is dramatically simpler. The Azure OpenAI Service (which provides enterprise-grade access to GPT-4 and other models) is a major draw for companies building on OpenAI's models with enterprise SLAs.

If the primary use case is cutting-edge ML research or training large models, GCP has genuine advantages: access to TPUs (Google's custom AI accelerators, which can be 3-10x faster than GPUs for certain transformer workloads), first-party access to Gemini models, and Vertex AI's tight integration with Google's ML research output. The fact that TensorFlow and JAX were developed at Google means GCP tooling for these frameworks is often more mature.

AWS is the default for greenfield projects when no other constraint applies, primarily because of ecosystem breadth. AWS has the most managed services (over 200), the largest community, the most third-party integrations, and the most available talent in the job market. SageMaker is mature and has the deepest feature set among managed ML platforms. The breadth of choice is also a risk: the AWS learning curve is steep, and choosing from competing services (there are five ways to run a container on AWS) requires expertise.

The honest answer in an interview: "I would evaluate existing enterprise agreements first, then team skills, then whether the project requires any cloud-specific capabilities (like TPUs on GCP). I would avoid strong cloud lock-in — using open standards like Kubernetes and open-source ML tools — so the system can be migrated if priorities change."

### Q2: What is the difference between serverless and containerised compute, and when would you use each for an ML inference endpoint?

**Answer:** Containerised compute (EC2 + Docker, GKE, EKS, AKS) means you provision a server (virtual machine), deploy your Docker container on it, and that server is running continuously. You pay whether it is processing requests or sitting idle. You control the instance type, networking, and runtime environment completely. Scale is managed either manually or through an autoscaler.

Serverless compute (Lambda, Cloud Run, Azure Container Apps) means you deploy a function or container and the cloud provider handles all server management. The service scales from zero instances to hundreds automatically, and you pay only for actual compute time. The trade-off is that serverless has cold start latency (a dormant function takes 100ms–2s to wake up), execution time limits (Lambda max is 15 minutes), and limited ability to use large amounts of GPU.

For ML inference, the choice depends on the model size and latency requirements. A lightweight API that calls a third-party LLM (Groq, OpenAI) is a perfect fit for serverless — the heavy compute happens at the API provider, your code just formats the request and returns the response. A fine-tuned 7B parameter model loaded into GPU memory is not suitable for serverless — it requires a GPU instance that loads model weights once and stays warm. Unloading and reloading a 7B model on every request would take 30+ seconds.

A common production pattern is hybrid: use serverless for the API gateway (request validation, auth, rate limiting) that calls a containerised model server running on a persistent GPU instance. Cloud Run on GCP handles this well — you can run containerised inference with GPU support, minimum instance count of 1 (avoiding cold starts for the model), and scale to 100s of replicas under load. It bridges the gap between pure serverless and full container management.

### Q3: What is S3 (or equivalent object storage) and why is it critical for ML systems?

**Answer:** Amazon S3 (Simple Storage Service) — and its equivalents GCS (Google Cloud Storage) and Azure Blob Storage — is a massive distributed key-value store for files of any size. You access objects via a simple API: put, get, delete, list. There is no directory structure (though the key naming convention uses `/` to simulate folders). Objects are stored redundantly across multiple availability zones, providing 11 nines (99.999999999%) of durability. You pay only for storage used and data transferred.

S3 is critical for ML systems for multiple reasons. First, **training data at scale**: a dataset of 100 million images might be 50 TB. You cannot fit that on a local disk, and you cannot version it in a Git repository. S3 stores it cheaply (roughly $2/TB/month) and makes it accessible from any training instance in the same region with high bandwidth. Second, **model artefact storage**: trained model weights (a fine-tuned LLaMA model might be 13 GB) need to be stored somewhere accessible for inference servers and for re-loading after a restart. S3 is the canonical location. Third, **data lake architecture**: raw data lands in S3, transformation pipelines process it and write processed data back to S3, feature pipelines read from S3. S3 becomes the single source of truth in a data lake design.

Specific ML patterns built around S3: versioning model checkpoints (each training epoch saves a checkpoint to `s3://bucket/model/run-id/epoch-10/`), storing evaluation results as JSON files for experiment tracking, and configuring lifecycle policies to automatically move old checkpoints from expensive standard storage to cheap archive storage (Glacier on AWS, Coldline on GCP) after 30 days.

A common interview follow-up: the difference between storage classes. "Standard" is hot storage for frequently accessed data. "Infrequent Access" is for data read monthly. "Glacier" (AWS) / "Archive" (GCP) is for data read once a year. Choosing the right storage class for ML artefacts can reduce storage costs by 80%.

### Q4: What is a managed ML platform (SageMaker / Vertex AI / Azure ML) and what problem does it solve compared to building your own ML infrastructure?

**Answer:** A managed ML platform provides an integrated environment for the entire machine learning lifecycle — data management, experiment tracking, model training, evaluation, deployment, and monitoring — as a managed cloud service. The alternative is building your own: deploy your own MLflow for experiment tracking, your own Kubernetes cluster for training, your own model registry in S3, your own canary deployment system. Building this from scratch takes months and requires specialised DevOps expertise.

The core services provided by platforms like Vertex AI include: a **feature store** (a managed system to compute, store, and serve ML features with consistent transformations between training and serving), **experiment tracking** (logs hyperparameters, metrics, and artefacts for every training run — essential for comparing "why did v2 outperform v1?"), **managed training** (submit a training job specifying instance type, GPU count, and Docker image — the platform handles provisioning, scaling, and teardown), a **model registry** (versioned storage for model artefacts with metadata — stage a model from "candidate" to "production"), and **prediction endpoints** (deploy a model as a REST API with autoscaling, load balancing, and monitoring in one click).

The trade-off is platform lock-in. If you build your entire ML workflow around SageMaker Pipelines, migrating to Vertex AI later is a significant rewrite. For organisations at early stages, managed platforms save enormous time. For organisations with strong ML engineering teams who need deep customisation, self-managed Kubeflow on Kubernetes often provides more flexibility.

For Google specifically, Vertex AI is the answer they want to hear for "how would you serve a model in production on GCP." The interview context is often about whether you know the managed abstractions and understand their trade-offs — not whether you can configure raw Kubernetes from scratch.

### Q5: What is multi-cloud architecture and when is it a good or bad idea for an AI system?

**Answer:** Multi-cloud means deliberately running workloads across more than one cloud provider — for example, training models on GCP (for TPU access) while serving them on AWS (where existing backend infrastructure lives), and storing data on Azure (because the enterprise contract is there). It is motivated by avoiding vendor lock-in, optimising costs by using each cloud's cheapest or best service for each task, and meeting compliance requirements (some regulators require workloads to run in specific jurisdictions served by specific providers).

The genuine benefits are real: no single vendor can hold you hostage on pricing, you can use TPUs on GCP and SageMaker on AWS, and regional availability varies — if AWS us-east-1 has an outage, you can route traffic to GCP. Major enterprises (large banks, government agencies) often have multi-cloud strategies for exactly these reasons.

However, multi-cloud adds enormous operational complexity. Network egress fees (you pay to move data between clouds — typically $0.08–0.09/GB) can be prohibitive when moving training data and model checkpoints between providers. Security boundary management is harder — you must manage identity and access policies across multiple IAM systems. Operational tooling must be multi-cloud aware (your monitoring, alerting, and cost management tools need to aggregate across providers). Developer experience fragments — engineers need expertise in multiple ecosystems.

For most AI projects, **the honest recommendation is: default to single cloud, design for portability.** Use open-source tools (Kubernetes instead of ECS, MLflow instead of SageMaker Experiments, open model formats) so migration is feasible if needed, but do not pay the multi-cloud operational tax unless you have a specific, justified reason. When the interviewer asks this question, they want to see that you understand the trade-offs rather than reflexively saying multi-cloud is always better (it is not) or always worse (it is not).

## Key Points to Say in the Interview

- Cloud choice is driven by existing enterprise contracts, team skills, and specific capability needs — not just raw features
- GCP has unique advantages for ML: TPUs, first-party Gemini access, Vertex AI tightly integrated with Google's research
- Serverless is excellent for lightweight inference that calls external APIs; persistent GPU containers are needed for self-hosted large models
- Object storage (S3/GCS/Blob) is the backbone of every ML data lake — training data, checkpoints, and artefacts all live there
- Managed ML platforms (Vertex AI, SageMaker) save months of infrastructure work but create platform lock-in
- Design for portability (Kubernetes, open ML formats) even if you deploy on one cloud
- Multi-cloud is operationally expensive — justify it only with specific, concrete requirements

## Common Mistakes to Avoid

- Do not say "GCP is always best for AI" — it is the right answer for some workloads, but AWS SageMaker and Azure ML are genuinely competitive
- Do not ignore data egress costs — moving data between clouds or out of a cloud can be more expensive than compute
- Do not confuse serverless with "no infrastructure concerns" — cold starts, execution limits, and memory limits all require careful design for ML workloads
- Do not recommend multi-cloud without acknowledging the operational overhead and data transfer costs
- Do not forget about data residency — many enterprise clients have legal requirements about which regions and which cloud providers can store their data

## Further Reading

- [Google Cloud Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs) — The definitive reference for GCP's ML platform
- [AWS SageMaker Developer Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/whatis.html) — AWS's managed ML platform documentation
- [Azure Machine Learning Documentation](https://learn.microsoft.com/en-us/azure/machine-learning/) — Microsoft's ML platform reference
- [Google TPU Documentation](https://cloud.google.com/tpu/docs/intro-to-tpu) — Understanding Google's custom AI accelerators
- [Cloud Run for ML Serving](https://cloud.google.com/run/docs/tutorials/gpu-tensorflow-model) — Practical guide to deploying ML models on Cloud Run with GPUs
