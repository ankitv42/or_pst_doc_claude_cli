# Fine-Tuning

## What Is It? (Plain English)

Fine-tuning is the process of taking a pre-trained language model — which has learned rich representations by training on billions of words — and adapting it to perform well on a specific task or domain by continuing training on a smaller, targeted dataset. The pre-trained model is the starting point; fine-tuning nudges the weights toward behavior that's useful for your specific use case.

Think of it like hiring an experienced professional. A general-purpose LLM is like a highly educated person who has read most of the internet — they know a huge amount about everything. Fine-tuning is like an intensive onboarding program that teaches them your company's specific policies, tone of voice, and decision-making frameworks. You don't re-educate them from scratch (prohibitively expensive); you build on what they already know.

The spectrum of fine-tuning techniques has expanded dramatically. At one extreme is **full fine-tuning**: update every weight in the model. At the other extreme is **prompt engineering**: change no weights at all, just change the instructions. Between these extremes are parameter-efficient fine-tuning (PEFT) methods like **LoRA** (Low-Rank Adaptation), which update only a tiny fraction of weights, and **instruction tuning** and **RLHF**, which fine-tune for behavioral alignment rather than task performance. Choosing the right technique requires understanding the tradeoffs of data requirements, compute cost, quality, and the risk of catastrophic forgetting.

## How It Works

```
Fine-Tuning Approaches — Parameter Budget vs Quality Tradeoff
──────────────────────────────────────────────────────────────────

Full Fine-Tuning:
  Pre-trained model (7B params) → update all 7B params
  ┌──────────────────────────────────────────────────────┐
  │  Transformer Layer N                                  │
  │    [W_q][W_k][W_v][W_o][W_ff1][W_ff2] ← all updated │
  └──────────────────────────────────────────────────────┘
  Cost: requires full model in GPU memory during training
  (~2x model size for weights + optimizer states)

LoRA (Low-Rank Adaptation):
  Pre-trained W (d×d) stays frozen, add:
    ΔW = B × A  where B is d×r, A is r×d, rank r << d

  Example: W (4096×4096) → B (4096×8) × A (8×4096)
  Full W: 16M params. LoRA ΔW: 65K params (0.4% overhead)

  ┌────────────────────────────────────────────────────┐
  │  h = W·x + ΔW·x = W·x + B·(A·x)                  │
  │                            ↑ only B, A are trained │
  └────────────────────────────────────────────────────┘

  At inference: merge W + ΔW → single weight, zero overhead

QLoRA (Quantized LoRA):
  Quantize W to 4-bit (NF4) for storage
  Dequantize to bfloat16 for computation
  Add LoRA adapters in full precision
  → Fine-tune 70B model on a single 48GB GPU
──────────────────────────────────────────────────────────────────
```

## Why Google Cares About This

Fine-tuning decisions directly affect Google's product quality and infrastructure costs. Should a new product use RAG + prompting, or fine-tune Gemini Flash? How much data do you need? What's the risk of the model forgetting other tasks? These are weekly product engineering decisions at Google. For the ML Engineer role, you're expected to know not just what LoRA is but when it wins over full fine-tuning, what data requirements look like for each approach, and how to avoid catastrophic forgetting.

## Interview Questions & Answers

### Q1: When should you fine-tune vs use RAG vs use few-shot prompting? What factors drive the decision?

**Answer:** This is one of the most practically important questions in applied LLM engineering. The three approaches occupy different positions on a cost-quality-flexibility tradeoff, and the right choice depends on what problem you're actually solving.

**Few-shot prompting (no training, fastest iteration)** works when: (1) The base model already has the necessary knowledge and capabilities — the task is within its training distribution. (2) You need to iterate quickly without training infrastructure. (3) Your task can be demonstrated in 5–10 examples that fit in the context window. (4) Query volume is low, so the extra context tokens per query are affordable. Prompting fails when the model's base knowledge is wrong or outdated, when the required output format is complex and hard to specify in examples, or when your cost-per-query is sensitive to context length.

**RAG (no training, knowledge injection)** works when: (1) The model needs access to specific, current, or proprietary information not in training data. (2) The information changes frequently (you update documents, not models). (3) Auditability matters — you can point to source documents. (4) You want to reduce hallucination by grounding answers in specific text. RAG fails when queries require true reasoning and synthesis (the relevant information is scattered across 50 documents and must be synthesized), when retrieval quality is inherently poor for the domain, or when sub-100ms latency is required.

**Fine-tuning (training required, highest quality for specific tasks)** works when: (1) The task requires a specific output format, tone, or persona that's hard to specify via prompting. (2) You have a large volume of task-specific examples (1,000+) and a consistent, well-defined task. (3) You want to "bake in" domain knowledge that doesn't change and would otherwise consume huge context window space per query. (4) Prompt-engineering has plateaued and you need more quality. Fine-tuning fails when you have insufficient data (< 100 examples often isn't enough to overcome prompt engineering), when data is expensive to collect, or when the task changes frequently (you'd need to retrain constantly).

A useful heuristic: try prompting first, then RAG if knowledge is the gap, then fine-tuning if behavior/format is the gap. For ORCA specifically: the LLM has general supply chain knowledge from training, so prompting works for reasoning. Domain-specific policies are injected via RAG. Fine-tuning would only add value if ORCA needed a very specific recommendation format or decision style that couldn't be achieved by the current prompt engineering.

### Q2: Explain LoRA in detail. Why does low-rank decomposition work for fine-tuning?

**Answer:** LoRA (Low-Rank Adaptation) is built on an empirical observation: the weight changes needed to adapt a pre-trained model to a downstream task are inherently low-rank. When you fine-tune a model, the difference between the starting weights W_0 and the final weights W_0 + ΔW can be approximated well by a matrix of much lower rank than the full d×d weight matrix.

Why does this observation hold? Large pre-trained models live in a high-dimensional parameter space but the "space of meaningful task adaptations" is much lower-dimensional. Fine-tuning for sentiment classification, for example, doesn't require learning new fundamental linguistic representations — it requires adjusting a small number of task-relevant directions in the already-rich representation space. The intrinsic dimensionality of the adaptation is much smaller than d.

LoRA exploits this by decomposing ΔW = BA where B is d×r and A is r×d with rank r typically 4–64. For a weight matrix of size 4096×4096 (16M parameters), LoRA with r=8 adds 2×4096×8 = 65,536 parameters — 0.4% overhead. These 65K parameters are trained while the original 16M stay frozen. At inference time, ΔW = BA is computed once and added to W — producing the same result as full fine-tuning with ΔW but requiring only 0.4% of the training parameters.

Initialization matters: A is initialized from a random Gaussian; B is initialized to zero. This means at initialization, ΔW = BA = 0 — the fine-tuned model starts exactly as the pre-trained model, and adapts from there. The scale factor α/r is applied to ΔW during training to control the magnitude of adaptation.

Which matrices to apply LoRA to: the original paper applies it to the attention weight matrices W_Q and W_V; recent work shows applying it to all weight matrices (W_Q, W_K, W_V, W_O, W_FF1, W_FF2) with smaller rank per matrix often achieves better results than large rank on fewer matrices. The total parameter count is what matters.

### Q3: What is QLoRA and how does it make fine-tuning 70B models possible on a single GPU?

**Answer:** QLoRA (Quantized LoRA) combines two techniques to reduce the memory requirement for fine-tuning large models: 4-bit quantization of the frozen base model weights, and LoRA adapters in full precision on top.

Standard full fine-tuning of a 70B parameter model in bfloat16 requires 140GB for weights alone, plus optimizer states (Adam uses 2× weights = 280GB), totaling ~420GB — impossible on even the largest single GPUs (A100 80GB, H100 80GB). LoRA without quantization reduces the trained parameters but still requires the frozen 70B model in memory in bfloat16 (140GB) plus optimizer states for the LoRA params. Still too large.

QLoRA's solution: store the frozen base model in NF4 (Normal Float 4-bit) quantization — a new data type that exploits the observation that pre-trained model weights are approximately normally distributed. NF4 quantizes this normal distribution into 16 equally spaced bins, achieving near-optimal quantization for normally distributed values. The 70B model goes from 140GB (bfloat16) to 35GB (NF4) — fitting on a single 40GB A100.

During forward passes, NF4 weights are dequantized to bfloat16 in small chunks (block-wise quantization) for computation — never in full. The LoRA adapters (1–5% of model size) are stored and trained in full bfloat16 precision. Gradients flow into the LoRA adapter weights only; the frozen NF4 base weights never receive gradient updates.

The memory footprint for QLoRA on 70B: ~35GB (NF4 base) + ~2GB (LoRA adapters) + ~2GB (optimizer states for adapters) = ~39GB — fitting on a single 40GB A100. This democratized large-model fine-tuning, making 70B+ model adaptation accessible without a cluster. The quality of QLoRA fine-tuned models is generally within 1–3% of full fine-tuning on most tasks.

### Q4: What is catastrophic forgetting and how do you mitigate it?

**Answer:** Catastrophic forgetting is the phenomenon where fine-tuning a neural network on a new task causes it to forget previously learned capabilities. When you optimize weights toward Task B, you move them away from the configuration that was optimal for Task A. If the update is large (high learning rate, many epochs, too much new data), the model can lose Task A performance almost completely.

For LLMs, catastrophic forgetting manifests as: (1) A model fine-tuned for SQL generation losing its ability to write Python. (2) A model fine-tuned for formal document analysis losing its conversational capability. (3) A model fine-tuned for one language degrading on others. (4) Safety-tuned models losing safety properties when further fine-tuned for a specific task — a real concern for production AI systems.

Mitigation strategies:

**LoRA and PEFT methods** naturally reduce forgetting because they update very few parameters. The frozen base model weights retain all pre-trained knowledge; only the small adapter is task-specific. When you need the original model behavior back, you remove the adapter.

**Low learning rates and early stopping**: a small learning rate limits how far from pre-trained initialization the weights move. Combined with early stopping (stop before the validation loss stops improving), you limit the overfitting/forgetting that comes from too many training steps.

**Rehearsal / replay**: include a small fraction (5–10%) of general-domain data from pre-training in each fine-tuning batch. This "reminds" the model of its original capabilities while it learns new ones. The cost is that you need access to samples from the pre-training distribution.

**Elastic Weight Consolidation (EWC)**: computes a Fisher information matrix measuring which weights are most important for Task A, then adds a regularization term to the fine-tuning loss that penalizes large changes to these important weights. More principled than rehearsal but computationally expensive.

**Multi-task fine-tuning**: instead of fine-tuning on Task B alone, fine-tune on Task A + Task B jointly. This maintains Task A performance while learning Task B. The cost: you need a Task A dataset during fine-tuning.

For ORCA's use case, the LLM (llama-3.1-8b-instant via Groq) is used API-only without fine-tuning. If ORCA were to fine-tune, LoRA would be the natural choice — it updates only the adapters, leaving the base model's general capabilities intact, and the adapter can be turned off when non-ORCA tasks need to be answered.

### Q5: How much data do you need for fine-tuning, and how do you evaluate whether fine-tuning worked?

**Answer:** The data requirement for fine-tuning depends critically on what you're teaching: format/style changes need less data than new factual knowledge, and new factual knowledge needs less data than completely new skills.

**Format and style adaptation** (changing how the model outputs, not what it knows) can be effective with 100–500 carefully curated examples. Instruction-tuning a model to always respond in JSON, to adopt a specific persona, or to follow a strict prompt template falls into this category. The model already has the underlying capability; you're just redirecting the surface behavior.

**Domain adaptation** (learning domain-specific terminology, reasoning patterns, decision styles) typically requires 1,000–10,000 examples. For a supply chain AI, fine-tuning on examples of good reorder recommendations in the exact ORCA format might need 2,000–5,000 high-quality (input_state, ideal_recommendation) pairs.

**New knowledge acquisition** (teaching facts that weren't in the training data) is the hardest case and may require tens of thousands of examples — and still may not stick reliably. LLMs are notoriously bad at memorizing new facts from fine-tuning (they tend to generalize the style without accurately memorizing specific numbers and dates). For new knowledge, RAG is almost always better than fine-tuning.

**Evaluating whether fine-tuning worked** requires a held-out evaluation set that was not used in training (standard ML practice) plus domain-specific metrics. Three checks: (1) Task performance: does the fine-tuned model score better on your task metric (F1, BLEU, acceptance rate) than the base model on the hold-out set? (2) Catastrophic forgetting: run the model on a benchmark testing general capabilities (MMLU, HellaSwag) — if scores drop significantly, you've over-tuned. (3) Distribution shift robustness: test on a slightly out-of-distribution held-out set — if performance collapses, the model overfit to your training distribution rather than learning the underlying task.

For data quality: 1,000 excellent examples beat 10,000 mediocre ones. Quality trumps quantity for fine-tuning — inconsistent labels, wrong examples, or noisy text will teach the model inconsistent behavior. Budget annotation time for data quality, not just data quantity.

## Key Points to Say in the Interview
- Decision hierarchy: try prompting first → add RAG if knowledge gap → fine-tune if behavior/format gap
- LoRA works because weight changes for fine-tuning are empirically low-rank — you don't need to update all parameters
- QLoRA: 4-bit NF4 quantization of frozen base + full-precision LoRA adapters = fine-tune 70B on one 48GB GPU
- Catastrophic forgetting: LoRA mitigates it (frozen base), low LR limits it, rehearsal maintains original capabilities
- Data requirements: 100–500 for format/style, 1K–10K for domain adaptation, RAG beats fine-tuning for new facts
- Always eval for catastrophic forgetting alongside task performance metrics

## Common Mistakes to Avoid
- Fine-tuning when prompting would suffice — adds engineering complexity and maintenance burden without quality gain
- Using a high learning rate that causes catastrophic forgetting of the base model's capabilities
- Confusing LoRA rank with model quality — very high rank (r=256) doesn't always outperform moderate rank (r=32)
- Not holding out evaluation data before collecting — if eval examples leak into training, your metrics are meaningless
- Fine-tuning for factual knowledge instead of using RAG — LLMs are unreliable memorizers of specific facts

## Further Reading
- [LoRA: Low-Rank Adaptation of Large Language Models (arXiv)](https://arxiv.org/abs/2106.09685) — Original LoRA paper with theoretical justification and empirical results
- [QLoRA: Efficient Finetuning of Quantized LLMs (arXiv)](https://arxiv.org/abs/2305.14314) — QLoRA paper demonstrating 70B fine-tuning on a single GPU
- [Finetuning Large Language Models (Sebastian Raschka)](https://sebastianraschka.com/blog/2023/llm-finetuning-llama.html) — Comprehensive practical guide with code for full fine-tuning, LoRA, and QLoRA
- [RLHF: Training Language Models to Follow Instructions (arXiv)](https://arxiv.org/abs/2203.02155) — InstructGPT paper introducing RLHF for behavioral alignment fine-tuning
- [Hugging Face PEFT Library](https://huggingface.co/docs/peft) — The standard library for LoRA and other PEFT methods, with examples for Llama, Mistral, and other open models
