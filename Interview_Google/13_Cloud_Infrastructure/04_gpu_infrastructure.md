# GPU Infrastructure — Running AI at Scale

## What Is It? (Plain English)

A GPU (Graphics Processing Unit) was originally designed to render video game graphics — a task that requires performing thousands of simple mathematical operations simultaneously. It turned out that training neural networks requires exactly the same kind of computation: thousands of matrix multiplications happening in parallel. This is why GPUs became the dominant hardware for AI. A modern NVIDIA A100 GPU can perform 312 trillion floating-point operations per second (312 TFLOPS). A high-end CPU manages perhaps 2-4 TFLOPS. For AI workloads, the GPU is 100x faster.

Understanding GPU infrastructure is now a core competency for senior AI engineers. The cost of training large models is enormous (GPT-3 cost approximately $4 million in compute), and the cost of serving them at scale (billions of inference requests per day) can be even larger. Making good decisions about which GPU to use, how to distribute training across multiple GPUs, and how to manage costs with spot/preemptible instances is the difference between a project that is economically viable and one that is not.

CUDA is NVIDIA's programming platform that lets developers write code that runs on NVIDIA GPUs. Almost all major AI frameworks (PyTorch, TensorFlow, JAX) rely on CUDA under the hood. When you run a PyTorch training script on a GPU, CUDA is the layer that actually executes those operations on the GPU hardware. This is why "NVIDIA + CUDA" has dominated AI hardware despite competition from AMD and Intel — the software ecosystem built around CUDA is enormous.

## How It Works

A GPU has thousands of small cores (an A100 has 6912 CUDA cores) optimised for parallel arithmetic. It has its own dedicated memory (VRAM), which is physically on the GPU card and much faster than CPU RAM for the GPU to access. The GPU and CPU communicate via PCIe (Peripheral Component Interconnect Express) or, in high-end servers, via NVLink (NVIDIA's proprietary high-bandwidth interconnect).

```ascii
GPU SERVER ARCHITECTURE (single node)

┌─────────────────────────────────────────────────────────────────────┐
│                           GPU SERVER                                │
│                                                                     │
│  CPU (host)           System RAM (DRAM)                             │
│  ┌──────────┐         ┌────────────────────┐                       │
│  │ 64 cores │◄────────│  1 TB system RAM   │                       │
│  └────┬─────┘         └────────────────────┘                       │
│       │ PCIe bus (bidirectional data transfer)                      │
│       │                                                             │
│  ┌────▼────────────────────────────────────────────────────────┐   │
│  │                   GPU ARRAY (8x A100)                       │   │
│  │                                                             │   │
│  │  A100 #0  ◄─NVLink─► A100 #1  ◄─NVLink─► A100 #2           │   │
│  │  80GB VRAM           80GB VRAM           80GB VRAM          │   │
│  │                          │                                  │   │
│  │                       NVLink                                │   │
│  │                          │                                  │   │
│  │  A100 #3 ◄──NVLink──► A100 #4  ◄─NVLink─► A100 #5          │   │
│  │  80GB VRAM            80GB VRAM           80GB VRAM         │   │
│  │                                                             │   │
│  │  A100 #6  ◄─NVLink─► A100 #7                               │   │
│  │  80GB VRAM            80GB VRAM                            │   │
│  │                                                             │   │
│  │  Total VRAM: 640 GB   NVSwitch bandwidth: 600 GB/s          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  NVMe Storage: 30 TB (fast local storage for checkpoints)           │
│  Network: 200 Gbps InfiniBand (for multi-node communication)        │
└─────────────────────────────────────────────────────────────────────┘

MULTI-NODE TRAINING:
Node 1 (8x A100) ◄──InfiniBand──► Node 2 (8x A100) ◄──► Node 3 (8x A100)
640 GB VRAM                       640 GB VRAM                640 GB VRAM
                Total: 1920 GB VRAM across 24 GPUs
```

For distributed training, two primary strategies exist. **Data Parallelism (DDP — Distributed Data Parallel)** puts a full copy of the model on each GPU, splits the batch of training data across GPUs, runs forward and backward passes in parallel, then synchronises the gradients (the "how much to adjust each weight" signals) across GPUs. This works when the model fits in one GPU's VRAM. **FSDP (Fully Sharded Data Parallel)** shards (splits) the model itself across GPUs so no single GPU holds the full model. This enables training models that are larger than any single GPU's memory — essential for 70B+ parameter models.

## Why Google Cares About This

Google operates one of the largest GPU and TPU fleets in the world. They invented the TPU specifically because GPUs were not cost-efficient enough at their scale. For senior AI/ML roles, understanding GPU infrastructure signals that you can reason about training costs, inference economics, and engineering trade-offs at scale. Google's DeepMind and Google Cloud AI teams routinely make decisions worth millions of dollars about how to train and serve models — they need engineers who understand the infrastructure these decisions depend on.

## Interview Questions & Answers

### Q1: What is the difference between an A100, H100, and T4 GPU, and when would you use each?

**Answer:** These three NVIDIA GPUs represent different generations and price-performance tiers, suited to different ML workloads and budget constraints.

The **T4** (Turing architecture, released 2018) is a mid-range inference GPU with 16 GB VRAM and 65 TFLOPS of FP16 performance. It is cheap to rent (approximately $0.35–0.75/hour on cloud providers) and highly available as a "commodity" GPU. It is excellent for production inference of small-to-medium models (up to approximately 7B parameters at reduced precision), for fine-tuning small models, and for development and experimentation. The T4 is the workhorse of low-cost AI deployments.

The **A100** (Ampere architecture, released 2020) comes in 40 GB and 80 GB VRAM variants and delivers 312 TFLOPS of FP16 and 77.6 TFLOPS of FP64. It introduced bfloat16 (BF16) precision natively, which is preferred for stable LLM training. The 80 GB A100 can train or serve models up to approximately 40B parameters in standard precision. It is the current standard for production LLM training and high-throughput inference. Cloud cost is approximately $3–5/hour. NVIDIA's NVLink allows 8 A100s on one server to share data at 600 GB/s — critical for large model parallelism.

The **H100** (Hopper architecture, released 2022) is the current flagship, with 80 GB HBM3 VRAM, 989 TFLOPS of FP16, and a new "Transformer Engine" that dynamically switches between FP8 and BF16 precision during training to maximise speed without losing accuracy. The H100 is roughly 3x faster than the A100 for LLM training and inference. Cloud cost is approximately $10–15/hour. For training models in the 70B–700B parameter range, H100s are the standard. The H100 NVL variant (liquid-cooled, two-GPU modules) is what runs in the latest hyperscale AI clusters.

The decision rule: T4 for cost-sensitive inference and development; A100 for production LLM training up to 40B parameters and high-throughput inference; H100 for frontier model training, fastest time-to-result when the project justifies the cost.

### Q2: What is GPU memory (VRAM) and why does it constrain what models you can run?

**Answer:** VRAM (Video RAM) is the GPU's local, high-bandwidth memory. Unlike CPU RAM (which the GPU accesses slowly via PCIe), VRAM is physically attached to the GPU die and can be accessed at 2–3 TB/s. For a neural network to run on a GPU, all the data it needs for computation — model weights, activations, gradients, optimizer states — must fit in VRAM. If anything overflows to CPU RAM, the computation must go through the slow PCIe bus, causing 10-100x slowdowns.

Model weight memory is the most intuitive constraint. A 7B parameter model in FP32 (32-bit floating point, 4 bytes per parameter) requires 7,000,000,000 × 4 bytes = 28 GB just for the weights. An 80 GB A100 can hold them with 52 GB to spare. A 70B parameter model requires 280 GB — more than 3 full A100s just for weights. In practice, training requires even more: gradients (another copy of weights), optimizer states (for Adam, another 2× copies of weights), and activations (intermediate computation results, proportional to batch size and sequence length). A 70B model trained with Adam in FP32 needs approximately 280 × 4 = 1120 GB of VRAM — requiring 14+ A100s for weights and optimizer state alone.

This is why **quantization** (reducing precision from FP32 to FP16, BF16, INT8, or INT4) is so important. A 7B model in INT4 (4-bit integer, 0.5 bytes per parameter) requires only 3.5 GB. This fits on a single 16 GB T4 with room for context. Tools like bitsandbytes and llama.cpp enable 4-bit quantization with acceptable quality loss for inference. For training, BF16 is the standard (14 GB for 7B model weights + comparable gradients/optimizer states = approximately 56 GB, fitting on one 80 GB A100 with careful gradient checkpointing).

The mental model for estimating VRAM needs: (parameters × bytes per parameter) × 4 for training (weights + gradients + optimizer states + activations) = minimum VRAM. This is why GPU memory, not compute throughput, is often the binding constraint for modern LLMs.

### Q3: Explain Distributed Data Parallel (DDP) and Fully Sharded Data Parallel (FSDP) — when do you use each?

**Answer:** Both DDP and FSDP are strategies for using multiple GPUs to train a single model faster. They differ in how they handle the constraint that the model might be larger than a single GPU's VRAM.

**DDP (Distributed Data Parallel)** is the simpler approach, applicable when the full model fits on a single GPU. Each GPU holds a complete copy of the model. The training batch is split across GPUs — GPU 0 processes data samples 1-64, GPU 1 processes samples 65-128, etc. Each GPU independently computes the forward pass (predictions) and backward pass (gradients) on its portion of the batch. After every step, an "AllReduce" communication collective averages the gradients across all GPUs, so every GPU's copy of the model parameters is updated identically. The result: you effectively train with a batch size of `64 × num_GPUs` at the speed of one GPU's forward/backward pass. DDP scales nearly linearly — 8 GPUs process ~8x as much data per unit time. PyTorch's `DistributedDataParallel` implements this, and it is the standard for training models up to approximately 10-40B parameters (depending on GPU memory).

**FSDP (Fully Sharded Data Parallel)** is required when the model does not fit on a single GPU. Instead of each GPU holding a full model copy, FSDP shards the model parameters, gradients, and optimizer states across all GPUs. Each GPU only holds 1/N of each tensor. When a layer needs to do a forward pass computation, the GPUs communicate to temporarily reconstruct the full layer, compute, then discard the other shards. This "gather on demand" approach means peak VRAM usage per GPU is approximately (total_model_memory / N) + activation memory for one layer — enabling training of truly massive models. The trade-off is higher communication overhead compared to DDP — FSDP requires more all-gather collectives (inter-GPU communication rounds) than DDP's single AllReduce per step.

PyTorch FSDP (introduced in PyTorch 1.12) is the standard implementation. For Google's internal use, the equivalent is "GShard" or model parallelism in JAX/XLA. The practical guideline: if your model fits on one GPU with room for activations, use DDP. If the model is too large for one GPU even with quantization, use FSDP.

### Q4: What are spot/preemptible instances and how do you design a training job to survive interruptions?

**Answer:** Cloud providers keep a pool of spare capacity that they sell at steep discounts (60-90% cheaper than on-demand prices) with the caveat that the provider can reclaim the instance with 30-120 seconds notice when they need the capacity back. AWS calls these "spot instances", GCP calls them "preemptible" (or "Spot VMs"), Azure calls them "spot VMs". For GPU instances (which are expensive), this discount is transformative — a p4d.24xlarge (8x A100) that costs $32/hour on-demand might be available for $12/hour as a spot instance.

The risk is that your training job is interrupted mid-run. Without preparation, this means losing all training progress. With proper checkpointing, an interruption is a minor setback. The standard approach: save a full checkpoint (model weights, optimizer state, current epoch/step, random number generator state) to durable storage (S3/GCS) every N training steps (typically every 500-1000 steps, or every 30 minutes). When the instance is interrupted and a new one starts, the training script detects the latest checkpoint in storage and resumes from that point.

The architecture for interruptible training on AWS: use a **SageMaker Managed Spot Training** job (or AWS Batch with spot instances), with checkpoint directory pointing to S3. SageMaker handles instance replacement automatically when a spot instance is reclaimed. On Kubernetes, this is implemented with KEDA + checkpointing — when a spot node is drained (given the 2-minute warning), Kubernetes saves a checkpoint, the pod is evicted, and when a new spot node provisions, the training pod reschedules and resumes.

A cost optimisation strategy: use on-demand GPU instances for the last 10-20% of training (when checkpointing more frequently and where an interruption would be most costly) and spot instances for the bulk of training. This balances cost savings (90% of training at spot prices) with reliability (guaranteed completion on on-demand).

### Q5: What is MIG (Multi-Instance GPU) and GPU time-slicing, and when would you use each?

**Answer:** Running one large model on a single GPU is straightforward. The challenge is when you have many small inference requests, each needing only a fraction of the GPU's capacity. A GPU is a fixed resource — if you have 10 small models each needing 8 GB of an 80 GB A100, you want 10 isolated slices of the same GPU. MIG and time-slicing are two approaches to this problem, with very different properties.

**MIG (Multi-Instance GPU)** is NVIDIA's hardware partitioning feature (available on A100, H100, and A30 GPUs). It physically partitions a GPU into up to 7 independent instances, each with isolated VRAM, compute engines, and memory bandwidth. A 80 GB A100 can be split into, for example, seven 10 GB MIG instances. Each instance is hardware-isolated — workloads on different MIG instances cannot access each other's memory and cannot interfere with each other's performance (no "noisy neighbor" problem). In Kubernetes, MIG instances appear as distinct resources (`nvidia.com/mig-1g.10gb`) that pods can request individually. MIG is the right choice for multi-tenant inference services where isolation guarantees matter: serving different clients' models on the same GPU without any cross-contamination risk.

**GPU time-slicing** is a software approach (no hardware isolation) where multiple pods share a single GPU by switching between them rapidly. NVIDIA's Kubernetes device plugin supports time-slicing — you configure how many "virtual" GPUs to advertise for a physical GPU (e.g., 8 virtual GPUs per physical GPU). The Kubernetes scheduler then assigns one virtual GPU per pod, and NVIDIA's driver time-multiplexes between them. There is no memory isolation (a misbehaving pod can crash others) and no bandwidth isolation (a heavy workload starves lighter ones). Time-slicing is suitable for development environments, batch jobs with low isolation requirements, or inference servers where you control all the workloads.

The decision: production multi-tenant serving with SLA requirements → MIG. Development and experimentation clusters to maximise pod density → time-slicing. The cost calculation for MIG: instead of running 7 A100 instances for 7 small models, run 1 A100 with MIG partitioning. At ~$3/hour per A100, that is a 7x cost reduction for suitable workloads.

## Key Points to Say in the Interview

- GPU VRAM is the binding constraint for model size — always calculate (parameters × bytes) × 4 for training requirements
- T4 for cost-sensitive inference; A100 for production LLM training; H100 for frontier model training
- DDP requires model to fit on one GPU (fast, simple); FSDP shards the model across GPUs (enables larger models, more communication overhead)
- Checkpoint every 500-1000 steps to enable spot/preemptible instance usage, cutting GPU costs 60-90%
- Quantization (INT8/INT4) reduces VRAM requirements 4-8x for inference, enabling larger models on smaller GPUs
- MIG provides hardware-isolated GPU partitions; time-slicing provides software-level sharing (no isolation guarantees)
- NVLink is the high-bandwidth interconnect between GPUs on the same node — critical for FSDP performance
- InfiniBand is the high-bandwidth network between nodes in a multi-node training cluster

## Common Mistakes to Avoid

- Do not say "just add more GPUs" without discussing communication overhead — beyond a certain scale, network bandwidth becomes the bottleneck
- Do not confuse GPU memory (VRAM) with CPU RAM — the GPU cannot efficiently use CPU RAM; overflow causes severe slowdowns
- Do not recommend FP32 training for large models — BF16 is standard and uses half the VRAM with equivalent training stability
- Do not forget optimizer state memory — Adam optimizer stores two extra gradient moment tensors, tripling the memory needed for weights alone
- Do not ignore spot instance interruptions — training without checkpointing on spot instances will eventually result in complete job loss

## Further Reading

- [NVIDIA A100 GPU Architecture Whitepaper](https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/a100/pdf/nvidia-a100-datasheet-us-nvidia-1758950-r4-web.pdf) — Technical specifications and architecture details
- [PyTorch FSDP Tutorial](https://pytorch.org/tutorials/intermediate/FSDP_tutorial.html) — Official guide to fully sharded data parallel training
- [Google TPU Documentation](https://cloud.google.com/tpu/docs/intro-to-tpu) — Google's custom AI accelerators as an alternative to GPUs
- [AWS EC2 Spot Instances for ML](https://docs.aws.amazon.com/sagemaker/latest/dg/model-managed-spot-training.html) — SageMaker managed spot training documentation
- [NVIDIA MIG User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/) — Official documentation for Multi-Instance GPU partitioning
