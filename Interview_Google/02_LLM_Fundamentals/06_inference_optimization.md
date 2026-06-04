# Inference Optimization

## What Is It? (Plain English)

Training a large language model happens once (or rarely). Inference — generating responses for users — happens billions of times per day. Every millisecond of latency and every cent of compute cost is multiplied by every user request. For a model serving 10 million users, making inference 2x faster is worth more than almost any other engineering effort. Inference optimization is the discipline of making that multiplication factor as small as possible.

Think of it like a pizza restaurant. Training is like developing the recipe — done once by the chef. Inference is like cooking every pizza for every customer — done millions of times. You can use the same recipe and equipment (the model) but dramatically speed up service by: preparing ingredients in advance (KV cache), cooking multiple pizzas at once (batching), using a lighter pan that heats faster (quantization), or training apprentices who cook faster using a simplified technique (distillation). None of these change the recipe, but they all change how quickly and cheaply you can serve customers.

The key metrics in inference optimization are **latency** (how quickly the first/last token arrives) and **throughput** (how many requests per second the system handles). These two metrics are often in tension: batching improves throughput but increases latency for individual requests. Different applications have different tradeoffs — a real-time chatbot prioritizes low latency; a batch document processing pipeline prioritizes high throughput. Understanding both, and the techniques that optimize each, is essential for production AI engineering.

## How It Works

```
═══════════════════════════════════════════════════════════════
       LLM INFERENCE: FROM REQUEST TO TOKENS
═══════════════════════════════════════════════════════════════

Request: "Write a haiku about autumn."
               │
               ▼
       ┌───────────────┐
       │  Prefill Phase │  Process ALL input tokens at once
       │  (parallel)    │  = "Write a haiku about autumn." (6 tokens)
       │                │  Duration: ~10-50ms for short prompts
       └───────┬────────┘
               │
               ▼
       ┌───────────────┐
       │  Decode Phase  │  Generate output tokens ONE AT A TIME
       │  (sequential)  │  Token 1: "Crimson"   → 50ms
       │                │  Token 2: " leaves"   → 50ms
       │                │  Token 3: " fall"     → 50ms
       │                │  ...
       │  KV Cache used │  (Saves recomputing previous tokens)
       └───────────────┘
       Total latency = prefill + (output_tokens × time_per_token)

═══════════════════════════════════════════════════════════════
            KEY OPTIMIZATION TECHNIQUES
═══════════════════════════════════════════════════════════════

1. QUANTIZATION: Reduce weight precision
   ┌───────────────────────────────────────────────────┐
   │  FP32 (full):  32 bits per weight  → 140GB model  │
   │  FP16 (half):  16 bits per weight  → 70GB model   │
   │  INT8:          8 bits per weight  → 35GB model   │
   │  INT4:          4 bits per weight  → 17.5GB model │
   │  GGUF/Q4_K_M:  4 bits mixed prec  → ~4GB (7B)    │
   └───────────────────────────────────────────────────┘
   Quality: FP32 > FP16 ≈ BF16 >> INT8 (small loss) >> INT4 (noticeable loss)
   Cost savings: INT4 is 8x cheaper memory than FP32, 2-4x faster

2. BATCHING: Process multiple requests together
   ┌────────────────────────────────────────────────────┐
   │  No batching:  Request A: 200ms, Request B: 200ms  │
   │                Total: 400ms                        │
   │                                                    │
   │  Batching:     Request A + B together: 220ms       │
   │                Total: 220ms  (1.8x faster)         │
   │                GPU utilization: 40% → 85%          │
   └────────────────────────────────────────────────────┘
   vLLM continuous batching: new requests join mid-generation

3. SPECULATIVE DECODING
   ┌────────────────────────────────────────────────────┐
   │  Draft model (small, fast) generates 5 tokens      │
   │  "autumn" "leaves" "gently" "fall" "down"         │
   │         ↓                                          │
   │  Target model (large, accurate) verifies ALL 5    │
   │  at once via one forward pass                      │
   │         ↓                                          │
   │  Accept all 5 if correct, else accept up to error │
   │  Net result: 2-4x speedup for target model latency│
   └────────────────────────────────────────────────────┘

4. KV CACHE: Avoid recomputing previous tokens
   ┌────────────────────────────────────────────────────┐
   │  Without: Each new token recomputes K,V for ALL    │
   │           previous tokens. Cost: O(n²) per step   │
   │                                                    │
   │  With KV cache: Store computed K,V vectors         │
   │  Each new token: compute only its own K,V          │
   │  Cost: O(n) per step (99% compute saved)          │
   └────────────────────────────────────────────────────┘
```

## Why Google Cares About This

Google serves billions of LLM inference requests per day through Gemini, Search AI Overviews, Gmail Smart Compose, and dozens of other products. Even a 10% efficiency improvement at that scale translates to hundreds of millions of dollars in annual compute savings and millions of users experiencing faster responses. Senior engineers at Google are expected to understand the efficiency techniques — quantization, batching, speculative decoding, KV cache management — not as abstract concepts but as practical tools they would apply when cost or latency SLAs are challenged. Demonstrating this knowledge signals readiness to work on the production infrastructure that makes Google's AI products viable at scale.

## Interview Questions & Answers

### Q1: What is quantization, and how does it reduce inference cost without destroying quality?

**Answer:** Quantization is the process of representing model weights with fewer bits of precision. A standard neural network stores each weight as a 32-bit floating point number (FP32). By converting to 16-bit (FP16), 8-bit (INT8), or even 4-bit (INT4), you reduce memory consumption and often speed up computation significantly.

The intuition: imagine a paint color palette. A 32-bit color has 4 billion possible shades. An 8-bit color has 256 shades. For most practical painting tasks, you can't tell the difference between the 32-bit and 8-bit versions. Neural network weights are similar — the exact precision of each weight often doesn't matter much for the final output, because the model has learned robust representations that are not very sensitive to small perturbations.

**Types of quantization:**
- **Post-training quantization (PTQ)**: Take a trained FP32 model and convert the weights to lower precision without retraining. Fastest to apply, but some quality loss, especially at INT4.
- **Quantization-aware training (QAT)**: Simulate quantization during fine-tuning, so the model learns to be robust to reduced precision. Better quality, but requires fine-tuning compute.
- **GPTQ and AWQ**: Advanced algorithms specifically designed for LLMs that identify which weights are most sensitive to precision reduction and apply different compression rates to different layers. These achieve INT4 quantization with quality close to FP16.

**Practical quality/efficiency tradeoffs:**
- FP16 vs FP32: Essentially no quality difference for most tasks. FP16 is 2x cheaper in memory and faster on modern GPUs (which have native FP16 hardware). This is the standard for production LLM serving.
- INT8: <1% quality loss on most benchmarks. 2x cheaper memory than FP16. Supported by bitsandbytes library.
- INT4 (GPTQ/AWQ): 2-5% quality loss on harder tasks. 4x cheaper memory than FP16. Enables running a 70B-parameter model on consumer hardware that couldn't fit FP16. This is the sweet spot for running large models on cost-constrained hardware.

**Practical impact**: A 7B-parameter model in FP32 requires ~28GB of GPU memory. In INT4, it requires ~4GB — fitting on a single consumer GPU (RTX 4090 with 24GB VRAM). This is why GGUF (the quantization format used by llama.cpp) made local LLM inference accessible to consumers and small teams.

### Q2: What is the difference between latency and throughput in LLM inference, and how do you optimize each?

**Answer:** Latency and throughput measure different things about a serving system's performance, and they often trade off against each other.

**Latency** is the time from when a user sends a request to when they receive a response (or the first token, for streaming). Key sub-metrics: Time To First Token (TTFT) — how long until the user sees anything; Time Per Output Token (TPOT) — how fast tokens appear once generation starts; total end-to-end time. Latency is what individual users experience.

**Throughput** is how many requests (or tokens) the system processes per unit time — requests per second or tokens per second. Throughput determines how many users the system can serve simultaneously with a fixed amount of hardware. Throughput is what determines infrastructure cost at scale.

**The tension**: Batching dramatically improves throughput (process 32 requests at once instead of 1) but increases latency for each individual request (you must wait for a batch to form before processing begins). A request that would be processed in 200ms if served immediately might wait 100ms for a batch, then take 200ms, for 300ms total — 50% slower, but the system handled 32 requests instead of 1.

**Optimizing for low latency:**
- Minimize input token count (shorter prompts)
- Use streaming (start showing output immediately)
- Use a smaller model (faster per-token generation)
- Reserve dedicated GPU capacity (no queuing)
- Speculative decoding (2-4x speedup for target model token generation)
- Prioritize the request in the queue (priority scheduling)

**Optimizing for high throughput:**
- Use continuous batching (vLLM's key feature): new requests join existing in-flight batches mid-sequence, maximizing GPU utilization at all times
- Use larger batches (accepting higher latency per request)
- Tensor parallelism (split the model across multiple GPUs to process larger batches)
- Increase hardware (more GPUs, larger GPU memory)
- Use INT8/INT4 quantization (model fits in memory with smaller footprint, allowing larger batches)

**The real-world decision**: User-facing chatbots → optimize for P99 latency. Batch document processing jobs → optimize for throughput. Mixed workloads → use priority queues, where interactive requests get priority over batch jobs.

### Q3: How does speculative decoding work, and when is it most effective?

**Answer:** Speculative decoding is a clever algorithm that exploits the observation that LLM inference is memory-bandwidth bound, not compute bound — the GPU has spare compute capacity that's wasted in the standard sequential decoding loop. Speculative decoding uses that spare capacity to run a smaller draft model in parallel with the main model, effectively "speculating" about future tokens and verifying those speculations with the main model.

**The algorithm:**
1. A small, fast "draft model" (e.g., a 7B model drafting for a 70B target model) generates K tokens quickly (K=5-8 is typical)
2. The large "target model" verifies all K draft tokens in a single forward pass — because all K tokens can be processed in parallel during prefill
3. The target model accepts all tokens up to the first one it disagrees with, then generates its own token for that position
4. The process repeats from the last accepted token

The key insight: the target model does one forward pass to verify K tokens, instead of K forward passes to generate K tokens sequentially. If the draft model is right at least 50% of the time, this is faster. In practice, draft acceptance rates of 80-90% are achievable for predictable text, giving 3-4x effective speedup.

**When speculative decoding is most effective:**
- **Highly predictable output**: Code completion, summarization, translation — predictable patterns → high draft acceptance rate
- **Large model size gap**: The larger the target model vs draft model (e.g., 70B vs 7B), the greater the benefit, because the target model is expensive and the draft model is cheap
- **Low-entropy token distributions**: If the next token is nearly certain (common in factual text), the draft model will predict correctly almost always

**When it's less effective:**
- **Creative generation**: High-entropy outputs (diverse creative text) have low draft acceptance rates → draft overhead without speed benefit
- **Short sequences**: The overhead of running the draft model is not worth it for 5-10 token outputs
- **Draft model too slow**: If the draft model is itself expensive, the overhead erodes the benefit

vLLM, TensorRT-LLM, and other production inference frameworks support speculative decoding as a configuration option. Google uses it internally for specific high-volume, predictable output tasks.

### Q4: What is continuous batching (as implemented in vLLM), and why is it better than static batching?

**Answer:** Traditional batch inference processes requests in static batches — you wait until you have N requests, process them all together, and then wait for the next batch. The problem: LLM requests have wildly different lengths. If one request generates 10 tokens and another generates 500 tokens in the same batch, the entire batch is blocked for the duration of the 500-token request — even though the shorter requests finished 490 tokens ago. GPU utilization drops because GPUs are waiting for the long request.

Static batching analogy: imagine a bus that only departs when all seats are full. Short-trip passengers must wait for the long-trip passengers to board, even if the bus is ready. And during the trip, the short-trip passengers reach their stop while the long-trip passengers continue — but the whole bus waits until everyone has arrived.

**Continuous batching** (also called "in-flight batching," popularized by vLLM) solves this by allowing new requests to join an in-progress batch. As soon as one request in a batch finishes generating (hits its stop token), that "slot" in the batch is freed, and a new waiting request immediately takes its place. The GPU is continuously busy; no slot is wasted waiting for a batch to fill or for slow requests to complete.

```
Static batching:
Req A (10 tokens):  [============] DONE  [GPU IDLE waiting for batch]
Req B (50 tokens):  [==================================================]
                    Time → 50 tokens of GPU work, but A finishes at 10

Continuous batching:
Req A (10 tokens):  [============]
Req B (50 tokens):  [==================================================]
Req C (joins at 10):[            ][================================]
Req D (joins at 10):[            ][==================]
GPU utilization: ~95% vs ~30% with static batching
```

**PagedAttention** (vLLM's second key innovation): Standard inference pre-allocates a fixed block of GPU memory for the KV cache of each request, based on the maximum expected output length. This wastes memory — a request that generates 50 tokens was allocated space for 2,048. PagedAttention manages KV cache memory in non-contiguous "pages" (like virtual memory in an OS), allocating only what's needed and reclaiming it when a request completes. This allows more concurrent requests to fit in GPU memory, further improving throughput.

Together, continuous batching + PagedAttention give vLLM 10-20x higher throughput than naive serving at similar or better latency. This is why vLLM became the de facto standard for open-source LLM serving in production.

### Q5: What is knowledge distillation, and when do you use it versus quantization?

**Answer:** Knowledge distillation is a technique for training a small "student" model to mimic the behavior of a large "teacher" model. The goal is a small, fast model that achieves most of the quality of the large model on a specific task. The intuition: a large model has learned rich internal representations, but for any specific task, much of that richness is unused. Distillation extracts the task-relevant knowledge into a compact form.

**How distillation works:**
1. Take a large teacher model (e.g., GPT-4) that performs well on your task
2. Generate a dataset of (input, teacher output) pairs by running the teacher on many examples
3. Train a smaller student model (e.g., a 7B model) to reproduce the teacher's outputs
4. The student learns not just from hard labels ("the correct answer is X") but from the teacher's full probability distribution over all outputs — these "soft labels" carry more information and make training more efficient

The result: a student model that often achieves 90-95% of the teacher's quality on the target task, at a fraction of the size. GPT-4-distilled versions of smaller models have been used in production by many companies for cost reduction.

**Distillation vs Quantization — when to use each:**

| Factor | Distillation | Quantization |
|--------|-------------|--------------|
| Training required? | Yes (fine-tuning the student) | No (applied post-training) |
| Quality preservation | Can be excellent (task-specific) | Good at FP16, degrading at INT4 |
| Size reduction | 10-100x (7B vs 70B) | 2-8x (FP16 vs INT4) |
| Complexity | High (need teacher data generation) | Low (one-time conversion) |
| Best for | When you can't afford to serve a large model, and you have clear task boundaries | When you need to fit a model on specific hardware or reduce memory cost |

**When to use distillation**: You have a specific, well-defined task (customer service for your product; code completion for your codebase). You have access to or can generate a large teacher model's outputs for that task. You're willing to invest in creating training data and running a fine-tuning run. The payoff: a much smaller, much cheaper model that does that specific task as well as the large model.

**When to use quantization**: You need a general-purpose model (can't narrow to one task). You can't afford fine-tuning compute. You need to reduce hardware requirements quickly. The payoff: same model, less memory, faster inference, minimal quality loss.

In practice, the highest-performing production systems often combine both: start with distillation to create a smaller specialized model, then apply quantization to that distilled model for additional inference efficiency gains.

## Key Points to Say in the Interview

- Know the **two phases of LLM inference**: prefill (parallel, fast) and decode (sequential, slow)
- **Latency vs. throughput**: individual user experience vs. system capacity — often trade off
- **KV cache** is standard; know it saves O(n²) recomputation per decode step
- **Continuous batching** (vLLM) achieves near-100% GPU utilization vs. 30-40% for static batching
- **INT4 quantization** enables large models on limited hardware with <5% quality loss
- **Speculative decoding** works by draft-model speculation + target-model parallel verification
- Distinguish **distillation** (train a smaller model to mimic a larger one) from **quantization** (reduce weight precision)

## Common Mistakes to Avoid

- Saying "just use a bigger GPU" without mentioning **algorithmic optimizations** like batching and KV cache
- Confusing **latency and throughput** — they measure different things and often trade off
- Claiming quantization always degrades quality significantly — at **FP16 and INT8, loss is negligible**
- Not knowing **vLLM** by name — it's the industry-standard production LLM serving framework
- Treating distillation and quantization as alternatives — they **compound** (apply both for maximum efficiency)

## Further Reading

- [vLLM: Easy, Fast, and Cheap LLM Serving](https://vllm.readthedocs.io/en/latest/) — Official vLLM documentation covering continuous batching and PagedAttention
- [FlashAttention-2: Faster Attention](https://arxiv.org/abs/2307.08691) — Tri Dao's optimized attention implementation used in production inference
- [Fast Inference from Transformers via Speculative Decoding](https://arxiv.org/abs/2211.17192) — Google's original speculative decoding paper with theory and results
