# Transformers

## What Is It? (Plain English)

The Transformer is the neural network architecture that powers virtually every modern AI system: GPT, BERT, T5, Gemini, Claude, LLaMA, Whisper, DALL-E, and thousands of others. Introduced in the 2017 paper "Attention Is All You Need" by Google researchers, it replaced RNNs and LSTMs as the dominant architecture for language tasks — and then spread to images (Vision Transformers), audio, protein structure prediction, genomics, and virtually every other domain.

The Transformer's central innovation is the **self-attention mechanism**: every element in a sequence can directly "attend to" (compare itself with and pull information from) every other element, regardless of distance. This is profoundly different from RNNs, where information from step 1 must propagate through every intermediate step to reach step 100. In a Transformer, the word at position 1 and the word at position 100 have the same direct connection cost. Long-range dependencies that were practically impossible for LSTMs are trivial for Transformers.

The second key property is **full parallelism during training**: unlike RNNs which must process tokens sequentially (step t depends on step t-1), Transformers process all positions in the sequence simultaneously. This makes training on GPUs — which are designed for parallel operations — extremely efficient. This parallelism is why it became feasible to train models on trillions of tokens.

## How It Works

```
Transformer Architecture Overview
──────────────────────────────────────────────────────────────────

   ENCODER                          DECODER
   (BERT-style)                     (GPT-style)

  ┌──────────────────┐           ┌──────────────────┐
  │  Input Embedding  │          │  Output Embedding │
  │  + Positional Enc │          │  + Positional Enc │
  └────────┬─────────┘           └────────┬──────────┘
           │                              │
  ┌────────▼─────────┐           ┌────────▼──────────┐
  │  Multi-Head       │          │  Masked Self-Attn  │
  │  Self-Attention   │          │  (causal mask)      │
  └────────┬─────────┘           └────────┬──────────┘
           │   Add & Norm                  │   Add & Norm
  ┌────────▼─────────┐           ┌────────▼──────────┐
  │  Feed-Forward Net │          │  Cross-Attention   │
  │  (2 linear layers)│          │  (attends encoder) │
  └────────┬─────────┘           └────────┬──────────┘
           │   Add & Norm                  │   Add & Norm
           │   (repeated N times)          │
           │                     ┌────────▼──────────┐
           │                     │  Feed-Forward Net  │
           │                     └────────┬──────────┘
           │                              │   Add & Norm
           │                              │   (repeated N times)
           │                              │
  Encoder Output ─────────────► Decoder Output → Linear → Softmax

──────────────────────────────────────────────────────────────────
Self-Attention Computation:

  Input: sequence of vectors X = [x_1, x_2, ..., x_n]
  
  For each position i:
    Q_i = W_Q · x_i  (Query: "what am I looking for?")
    K_j = W_K · x_j  (Key:   "what do I offer?")
    V_j = W_V · x_j  (Value: "what information do I carry?")
  
  Attention score: a_{ij} = softmax(Q_i · K_j / √d_k)
  Output at position i: y_i = Σ_j a_{ij} * V_j
  
  Interpretation: position i "looks" at all positions j,
  weights each by relevance (Q·K score), and takes a
  weighted average of their values.
──────────────────────────────────────────────────────────────────
```

**Multi-head attention**: Run H independent attention operations in parallel ("heads"), each with its own W_Q, W_K, W_V matrices of size d_model/H. Concatenate all head outputs and project. Each head can specialize in different types of relationships: one head tracks subject-verb agreement, another tracks coreference, another tracks positional relationships.

**Positional encoding**: Self-attention is permutation-invariant — it doesn't inherently know that position 3 comes before position 7. Positional encodings inject position information by adding a position-dependent signal to each input embedding. The original paper used sinusoidal encodings; modern models use learned positional embeddings or RoPE (Rotary Position Embedding) which scales better to long contexts.

## Why Google Cares About This

The Transformer was invented at Google (the "Attention Is All You Need" paper has 8 Google Brain/Research authors). Every Google AI product — Gemini, Search, Translate, Assistant, Workspace AI features — is built on Transformer variants. For any senior ML role at Google, you need to explain self-attention from the math up, explain the BERT/GPT/T5 design choices, explain scaling laws, and discuss modern variants (RoPE, Flash Attention, sparse attention, mixture of experts). This is the architecture. Master it.

## Interview Questions & Answers

### Q1: Explain self-attention in detail. What are Q, K, and V and why do you divide by √d_k?

**Answer:** Self-attention computes, for each position in the input sequence, a weighted combination of information from all other positions. The weight between position i and position j is determined by how "relevant" j is to i — formally, by the inner product of their query and key vectors.

The three projections have intuitive roles. The **Query (Q)** vector represents "what information is position i looking for?" The **Key (K)** vector represents "what information does position j have to offer?" The **Value (V)** vector is "what information will position j actually share if it's attended to?" The attention weight between i and j is computed as the inner product of i's query and j's key — a measure of how well what i is searching for matches what j offers.

Concrete example: in the sentence "The bank can guarantee deposits will cover future tuitions," the word "bank" has ambiguous meaning (financial institution vs riverbank). During self-attention, "bank" computes its query vector (encoded "what context resolves my meaning?"). "deposits," "guarantee," and "tuitions" have key vectors that score high against this query, pulling their value vectors toward "bank"'s output representation — resolving the ambiguity toward the financial meaning.

The **√d_k scaling**: without the scaling, when d_k (the dimension of queries and keys) is large, the dot products Q·K can become very large in magnitude. When you pass large values through softmax, the function becomes saturated — the gradient of softmax becomes near-zero and learning stalls. Dividing by √d_k keeps the dot products in a regime where softmax produces meaningful gradients. This is a detail of numerical stability, but it matters practically — without it, training Transformers with large d_k would be unstable.

Why **multiple heads**: a single attention head applies one query-key-value projection, learning one "type" of relationships across all sequence positions. Multiple heads run H independent attention operations in parallel, each in a subspace of dimension d_model/H. This allows different heads to specialize: empirically, one head might attend to syntactic dependencies (subject → verb), another to semantic associations (pronoun → referent), another to local context (adjacent tokens). The outputs are concatenated and projected, combining these diverse relationships into a single representation.

### Q2: What is the difference between BERT, GPT, and T5? When do you use each architecture?

**Answer:** BERT, GPT, and T5 are three different ways to use the Transformer architecture for language, differing in their training objective and which part of the encoder-decoder architecture they use.

**BERT (Bidirectional Encoder Representations from Transformers)** uses only the Transformer encoder. It's trained with a masked language modeling (MLM) objective: randomly mask 15% of input tokens and predict them from context on both sides (bidirectional). The word "The [MASK] sat on the mat" requires reading both the left context ("The") and the right context ("sat on the mat") to predict "cat." This bidirectional context makes BERT excellent for understanding tasks: sentence classification, named entity recognition, question answering, document retrieval. BERT is an encoder — it produces contextual representations of text but cannot generate text. Use BERT for classification, embeddings, and discriminative tasks.

**GPT (Generative Pre-trained Transformer)** uses only the Transformer decoder with a causal (left-to-right) language modeling objective: predict the next token given all previous tokens. The causal mask ensures the model cannot "cheat" by looking at future tokens. This makes GPT fundamentally generative — it predicts what comes next, token by token. GPT-family models (GPT-4, LLaMA, Gemini) are the basis for chatbots, code generation, and RAG generation. The tradeoff: because the model only sees past context (not future), BERT-style understanding tasks where you need to read an entire input are less natural for GPT.

**T5 (Text-to-Text Transfer Transformer)** uses the full encoder-decoder architecture. Every task is framed as text-to-text: the encoder reads the input ("translate English to French: The cat sat"), the decoder generates the output ("Le chat s'est assis"). This unified framing allows T5 to handle translation, summarization, question answering, and classification with the same architecture and training objective. T5 pretraining uses span corruption (mask spans of tokens, predict the full span). Use T5 when you need an architecture that handles both comprehension (encoder) and generation (decoder) in a single model.

The modern trend: instruction-tuned decoder-only models (GPT-4, Claude, Gemini) have largely subsumed T5's use cases because they're more flexible and have scaled further. BERT-style encoders remain dominant for embedding generation and discriminative tasks (search relevance, sentence similarity, NLI) where generation is unnecessary.

### Q3: What are scaling laws and what do they tell us about training large language models?

**Answer:** Scaling laws describe the empirical relationship between model performance, model size (parameters), training data (tokens), and compute (FLOPs). The landmark work by Kaplan et al. (OpenAI, 2020) and Hoffmann et al. (DeepMind/Chinchilla, 2022) established clean power-law relationships:

```
Loss ∝ C^(-α)  (compute scaling)
Loss ∝ N^(-β)  (parameter scaling)
Loss ∝ D^(-γ)  (data scaling)

where C = compute, N = parameters, D = tokens
and α, β, γ are empirically measured exponents
```

The key insight from Kaplan (2020): if you have a fixed compute budget, how should you allocate it between more parameters vs more training tokens? The answer: scale both together, but the exponent on parameters is larger than on data, so parameter-heavy models trained on less data tend to perform well. This led to the trend of training very large models (175B, 540B parameters) on relatively less data.

Hoffmann et al. (Chinchilla, 2022) re-ran this analysis more carefully and found the opposite conclusion: models were severely undertrained. For a compute-optimal model, you should have roughly equal scaling of parameters and tokens — specifically, 20 tokens per parameter. A 70B parameter model should be trained on 1.4 trillion tokens (Chinchilla-optimal). GPT-3 (175B parameters, 300B tokens) was dramatically undertrained by this criterion.

Practical implications: (1) Inference cost matters as much as training cost — a smaller, well-trained model (like Chinchilla at 70B) is cheaper to serve than a large undertrained model while achieving similar quality. (2) Data quality matters: the scaling law exponents assume clean, diverse training data — low-quality data (repetitive, noisy) shifts the curves unfavorably. (3) There are no sharp "emergent" capability thresholds — capabilities appear to improve continuously with scale, though at different rates for different tasks.

For Google, scaling laws informed decisions about Gemini's training — how large to make the model, how many training tokens, how to balance quality vs inference cost across model sizes (Gemini Nano, Flash, Pro, Ultra).

### Q4: What is Flash Attention and why does it matter for training and inference at scale?

**Answer:** Standard self-attention is memory-bandwidth bottlenecked, not compute-bottlenecked. For a sequence of length T, the attention matrix (all pairwise Q·K scores) has T² entries. For T=2,048 tokens, that's 4M floats — for T=32,768, that's 1 billion floats, requiring ~4GB for a single layer's attention matrix. This matrix must be written to and read from GPU High Bandwidth Memory (HBM) multiple times during the attention computation, creating massive memory traffic.

Flash Attention (Dao et al., 2022) reorders the computation to avoid materializing the full T×T attention matrix in HBM. Instead, it tiles the computation into small blocks that fit in the GPU's much faster on-chip SRAM, computes the softmax and weighted sum within each tile using a numerically stable online algorithm (tracking running maximum for numerical stability), and never writes the full attention matrix to HBM. The final output is identical to standard attention.

The speedup: Flash Attention is 2–4x faster than standard attention and reduces memory usage from O(T²) to O(T). For T=4,096, that's a 4,096-slot saving on the bottleneck resource. Flash Attention 2 and 3 pushed further with better parallelism and support for modern GPU architectures, achieving near-theoretical compute utilization.

The practical impact: Flash Attention made training with long context lengths (32K, 128K, 1M tokens) practical. Without it, the memory required for the attention matrix would exceed GPU memory for sequences longer than a few thousand tokens. Gemini's 2M context window is feasible in part because of Flash Attention-style optimizations. For model developers: Flash Attention v2/v3 should be used by default for any Transformer training or inference at meaningful scale. It's a pure engineering optimization — no quality tradeoff, only speed and memory gains.

### Q5: How does the pre-training and fine-tuning paradigm work, and why did it become the dominant approach?

**Answer:** The pre-training / fine-tuning paradigm is a two-phase training strategy that has become the foundation of modern AI: first train a large model on a massive, general dataset (pre-training), then adapt it to a specific downstream task using a much smaller, task-specific dataset (fine-tuning).

Pre-training trains the Transformer on vast quantities of unlabeled or self-supervised data. For language models: next-token prediction on web text, books, code (trillions of tokens). This phase is expensive — training GPT-3 cost ~$5M in compute. But it only needs to be done once, and the resulting model learns representations that encode vast factual, linguistic, and reasoning knowledge.

Fine-tuning takes the pre-trained model and trains it on a labeled task-specific dataset, typically 100x–10,000x smaller. The pre-trained weights are used as the starting point (warm initialization). Only a small number of additional gradient steps are needed because the model already understands language structure and world knowledge — fine-tuning just teaches it the specific format and domain of the task. BERT fine-tuned on a 10,000-example legal document classification dataset can achieve 92% accuracy — comparable to a CNN trained from scratch on 1M examples — because it starts with rich linguistic representations.

Why it became dominant: (1) **Data efficiency** — you can solve specialized tasks with small labeled datasets that would be impossible to train a model from scratch on. (2) **Cost sharing** — the expensive pre-training is done once by a large organization; everyone fine-tunes on top. The research and deployment economics separate cleanly. (3) **Performance** — pre-trained models represent the state of the art across nearly every benchmark, even after fine-tuning on relatively small domain data. (4) **Generalization** — the representations learned in pre-training generalize across many tasks, unlike task-specific features.

For ORCA, this paradigm means using `llama-3.1-8b-instant` (a pre-trained model already containing supply chain knowledge from training data) rather than training a language model on supply chain text. The RAG architecture then injects domain-specific policy knowledge at inference time — a complement to pre-training that handles information that's too specific or too recent to have been in the training data.

## Key Points to Say in the Interview
- Self-attention: every position directly attends to every other position — eliminates the distance problem of RNNs
- Q (what I'm looking for), K (what I offer), V (what I share) — divide by √d_k for numerical stability in softmax
- Multi-head attention allows different heads to specialize in different relationship types simultaneously
- BERT = encoder only (bidirectional, for understanding). GPT = decoder only (causal, for generation). T5 = encoder-decoder (both)
- Scaling laws: compute-optimal training requires ~20 tokens per parameter (Chinchilla result)
- Flash Attention makes long-context Transformers practical by avoiding materializing the T² attention matrix in HBM

## Common Mistakes to Avoid
- Confusing BERT and GPT direction — BERT is bidirectional (sees future tokens), GPT is causal (only past tokens)
- Not knowing why positional encoding is needed — self-attention is permutation-invariant without it
- Claiming attention is O(T) — it's O(T²) in both time and memory, which is the fundamental scaling bottleneck
- Forgetting that layer normalization in Transformers typically comes BEFORE attention (Pre-LN) in modern architectures, not after (Post-LN as in the original paper)
- Not being able to explain multi-head attention beyond "multiple attention heads" — explain that each head specializes in different relationship types

## Further Reading
- [Attention Is All You Need (arXiv)](https://arxiv.org/abs/1706.03762) — The original Transformer paper — required reading
- [The Illustrated Transformer (Jay Alammar blog)](https://jalammar.github.io/illustrated-transformer/) — The best visual explanation of the Transformer architecture
- [BERT: Pre-training of Deep Bidirectional Transformers (arXiv)](https://arxiv.org/abs/1810.04805) — Original BERT paper introducing the encoder-only pre-training paradigm
- [Scaling Laws for Neural Language Models (arXiv)](https://arxiv.org/abs/2001.08361) — Kaplan et al. establishing power-law scaling relationships
- [FlashAttention-2: Faster Attention with Better Parallelism (arXiv)](https://arxiv.org/abs/2307.08691) — How Flash Attention makes long-context Transformers practical
