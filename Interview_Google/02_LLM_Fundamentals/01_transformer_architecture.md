# Transformer Architecture

## What Is It? (Plain English)

The Transformer is the neural network architecture that powers every modern large language model — GPT-4, Gemini, LLaMA, Claude, and virtually all other LLMs are based on it. Introduced in the 2017 paper "Attention Is All You Need" by Google Brain researchers, it replaced the previously dominant Recurrent Neural Networks (RNNs) and became the foundation of the modern AI era. Understanding the Transformer is like understanding the internal combustion engine if you work in the automotive industry — you don't need to build one, but you need to understand why it works and what its characteristics are.

The key innovation of the Transformer is the **attention mechanism** — a way for the model to decide which words in the input are most relevant to understanding any given word, regardless of how far apart they are in the sentence. In older RNNs, information had to be passed sequentially (word 1 → word 2 → word 3...), so the model had difficulty connecting a pronoun at position 50 to its antecedent at position 5. The Transformer processes all words simultaneously and uses attention to directly connect any word to any other, making it far better at capturing long-range relationships in language.

There are two main variants you'll encounter. **BERT** (and its descendants) uses the encoder portion of the Transformer and is trained to understand text by predicting masked words — it excels at classification, question answering, and embedding tasks. **GPT** (and its descendants, including most modern LLMs) uses the decoder portion and is trained to predict the next word — it excels at generation. Modern LLMs like Gemini and GPT-4 are decoder-only models. Understanding this distinction matters because it explains why some models are better at classification (BERT-style) and others at generation (GPT-style).

## How It Works

```
═══════════════════════════════════════════════════════════════
              TRANSFORMER BLOCK (one layer of many)
═══════════════════════════════════════════════════════════════

Input Tokens: ["The", "cat", "sat", "on", "the", "mat"]
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                  INPUT EMBEDDINGS                       │
│  Each token → 768-dim (or 4096-dim) dense vector        │
│  "The" → [0.2, -0.5, 0.8, … ] (768 numbers)           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              POSITIONAL ENCODING                        │
│  Add position signal: token at position 3 ≠ token       │
│  at position 7 even if they're the same word            │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────┴────────────────────────────┐
         ▼                                         │
┌──────────────────────────────────┐               │ Residual
│     MULTI-HEAD SELF-ATTENTION    │               │ Connection
│                                  │               │ (skip path)
│  Q = Xₙ × Wq (Query matrix)     │               │
│  K = Xₙ × Wk (Key matrix)       │               │
│  V = Xₙ × Wv (Value matrix)     │               │
│                                  │               │
│  Attention(Q,K,V) = softmax(     │               │
│    QKᵀ / √d_k) × V              │               │
│                                  │               │
│  8 (or 32) heads running in     │               │
│  parallel, each attending to     │               │
│  different relationship types    │               │
└────────────────┬─────────────────┘               │
                 │                                  │
                 └─────────────┐                   │
                               ▼                   │
                     ┌──────────────────┐          │
                     │  ADD + NORM      │◄─────────┘
                     │ (LayerNorm)      │
                     └────────┬─────────┘
                              │
                    ┌─────────┴──────────────────┐
                    ▼                             │ Residual
         ┌──────────────────────┐                │ Connection
         │  FEED-FORWARD LAYER  │                │
         │  (Position-wise MLP) │                │
         │  Linear → ReLU/GELU  │                │
         │       → Linear       │                │
         └────────────┬─────────┘                │
                      │                          │
                      └────────────┐             │
                                   ▼             │
                         ┌──────────────────┐    │
                         │  ADD + NORM      │◄───┘
                         └────────┬─────────┘
                                  │
                                  ▼ (to next layer)
                    [Repeat for N layers: GPT-3=96 layers]

═══════════════════════════════════════════════════════════
ENCODER (BERT): bidirectional        DECODER (GPT): causal
  Can attend to ALL tokens             Can only attend to
  (left AND right context)             PAST tokens (masked)
═══════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google's researchers invented the Transformer ("Attention Is All You Need" is a Google Brain paper), and Google's AI products are all built on Transformer-based models. When interviewing at Google for a senior AI/ML role, you're expected to understand the architecture that underpins everything — not to implement it from scratch, but to reason about its properties: why it's parallelizable (enabling training at scale), why context windows matter (the quadratic attention complexity), why BERT and GPT have different strengths, and what limits Transformer capabilities. This knowledge signals that you understand WHY the AI works, not just THAT it works, which is essential for making good design decisions.

## Interview Questions & Answers

### Q1: Explain the Transformer architecture to a non-expert. What are the key components and why do they matter?

**Answer:** I'll build it up from first principles. Imagine you're reading the sentence "The bank by the river was steep." To understand what "bank" means, you need to look at "river" — those two words are closely related even though they might be 5 words apart. The Transformer's attention mechanism lets every word "look at" every other word in the sentence simultaneously to figure out these relationships, rather than processing words one at a time.

The Transformer has four major components. The first is **embedding**: each word is converted to a vector of numbers (say, 768 numbers). These numbers encode the word's meaning — "king" and "queen" have similar embeddings because they're semantically related. The second is **positional encoding**: since the Transformer processes all words simultaneously (not left-to-right like humans), it needs to inject information about word position. A special mathematical signal is added to each word's embedding based on its position in the sentence, so the model knows "the" at position 1 is different from "the" at position 7.

The third, and most important, is **multi-head self-attention**. For each word, the model computes three vectors: a Query (what am I looking for?), a Key (what do I contain?), and a Value (what information do I carry?). Attention scores are computed by comparing every word's Query to every other word's Key. High score = strong attention = the model routes information from that word into the current word's representation. "Multi-head" means this process runs N times in parallel (e.g., 8 or 32 heads), with each head learning to attend to different relationship types (one head might learn subject-verb relationships, another might learn pronoun-antecedent relationships).

The fourth is the **feed-forward network**: after attention, each word's updated vector is passed through a two-layer neural network. This is where the model applies non-linear transformations — it's where much of the model's "knowledge" is stored. The entire block (attention + feed-forward) is repeated many times (GPT-3 has 96 layers), and each pass enriches the word representations with deeper contextual understanding.

### Q2: What is the difference between an encoder-only model (BERT) and a decoder-only model (GPT), and when do you use each?

**Answer:** The difference comes down to **what the model can see during processing**, and this shapes what tasks each is suited for.

**BERT (Encoder-only)** processes the entire input sequence bidirectionally — every word can attend to every other word, both to the left and to the right. BERT is trained with "masked language modeling" — randomly mask 15% of tokens and train the model to predict them using context from both sides. This bidirectional context gives BERT a rich understanding of each token's meaning in the full sentence. However, because BERT sees the whole sequence at once, it cannot generate text autoregressively (token by token) — you can't use it to write an essay.

BERT excels at: text classification (is this review positive or negative?), named entity recognition (which words are person names?), question answering (given a passage, find the answer to this question), and — most relevant for RAG — **embedding generation** (representing a sentence as a single meaningful vector for semantic search). The transformer encodes the full sentence, and the [CLS] token representation serves as the sentence embedding.

**GPT (Decoder-only)** uses a causal attention mask — each token can only attend to tokens that came before it in the sequence. This is necessary for generation: when generating token #50, the model must not "cheat" by looking at token #51. GPT is trained with "next token prediction" — predict the next word given all previous words. This makes GPT excellent at generation tasks (completing text, answering questions, writing code, following instructions) but less suited for tasks that benefit from bidirectional context.

**Encoder-Decoder (T5, BART)** combines both: an encoder processes the input bidirectionally (great for understanding), and a decoder generates the output autoregressively (great for generation). These are particularly suited for translation, summarization, and other sequence-to-sequence tasks.

**Practical guidance:**
- Text classification, embeddings, semantic search: encoder (BERT, RoBERTa, nomic-embed)
- Text generation, conversation, code generation, instruction following: decoder (GPT, Gemini, LLaMA)
- Translation, summarization, structured output generation: encoder-decoder (T5, BART)

Most modern LLMs (GPT-4, Gemini, LLaMA, Claude) are decoder-only because instruction following and generation are the primary use cases at scale.

### Q3: Why did Transformers replace RNNs, and what are the Transformer's own limitations?

**Answer:** Recurrent Neural Networks (RNNs) and their variants (LSTMs, GRUs) dominated sequence modeling before 2017. To understand why Transformers replaced them, you need to understand RNNs' core limitation: **sequential processing**. An RNN processes tokens one at a time, left to right. The information from token 1 is compressed into a "hidden state" that's passed to token 2, which updates it and passes it to token 3, and so on. By token 100, much of the information from token 1 has been overwritten or diluted — this is the "vanishing gradient" problem.

The Transformer solved this by processing all tokens simultaneously (parallelism) and using direct attention connections between any two tokens (no gradient-vanishing path). The benefits were enormous: faster training (parallelism → better GPU utilization), much better at capturing long-range dependencies (no information bottleneck), and more scalable (larger models converge better with attention than with RNNs). The empirical results were immediate and dramatic — Transformers dominated NLP benchmarks within months of publication.

**Transformer limitations:**
1. **Quadratic attention complexity**: Computing attention requires comparing every token to every other token — O(n²) time and memory with respect to sequence length. A 4,096-token sequence requires 4096² = 16 million attention score computations per head. This is why context windows are limited and why long-context models are expensive. (Alternatives: Flash Attention reduces the constant, linear attention approximations exist but sacrifice quality.)

2. **Fixed context window**: Transformers cannot process sequences longer than their context window. Information outside the window is simply inaccessible. This is why RAG is necessary — it's a workaround for the fact that LLMs can't fit an entire knowledge base into their context.

3. **No persistent memory**: Each inference call is stateless. The model doesn't remember previous conversations unless you re-inject them into the context window. This is why conversation history management and external memory systems are necessary for agents.

4. **Expensive training**: Large Transformers require enormous compute to train — GPT-3 reportedly cost $4-12M to train. This concentrates capability development at a small number of well-funded organizations.

5. **Interpretability**: Attention patterns are human-inspectable (you can visualize which words attend to which), but the meaning of individual attention heads and feed-forward weights is not straightforward to interpret. This is an active research area.

### Q4: What is positional encoding, and why does the Transformer need it?

**Answer:** This is one of the most interesting "gotcha" questions about Transformers. The self-attention mechanism, as described, is **permutation-invariant** — it treats the input as a set of tokens, not a sequence. If you shuffled the words of a sentence and fed them to a Transformer (without positional encoding), the model would produce the same output regardless of the order. "Dog bites man" and "Man bites dog" would look identical — same tokens, same attention scores. This is clearly wrong.

Positional encoding solves this by adding a position-dependent signal to each token's embedding before it enters the attention layers. The original Transformer used **sinusoidal positional encoding** — a mathematical function based on sine and cosine waves of different frequencies. For token at position p, the encoding adds a unique pattern of numbers based on p. The key property: nearby positions have similar encodings (so the model can detect proximity), and the patterns repeat at different frequencies (so the model can detect both local and global position).

The intuition: imagine adding a differently-colored background behind each word, where the color encodes position. The attention mechanism can now distinguish two occurrences of the same word based on their position. "She" at position 5 and "She" at position 50 have different encodings, so the model can learn that they refer to different entities in different parts of a passage.

Modern LLMs have largely moved to **learned positional embeddings** (a table of trainable vectors, one per position) or **rotary positional embeddings (RoPE)**, which is particularly elegant. RoPE encodes position by rotating the Query and Key vectors before computing attention scores — position information is incorporated into the attention computation directly rather than added to the embeddings. RoPE has better generalization to sequence lengths longer than those seen during training and is used by LLaMA, Mistral, and many other modern models.

The limitation of fixed positional encoding: the model can only handle sequences up to its maximum trained position. If trained on sequences up to 4,096 tokens, it may not generalize well to 8,192-token sequences. Techniques like ALiBi and YaRN extend position encodings to longer sequences, but the quality of long-context reasoning remains an active research area.

### Q5: How does scaling affect Transformer performance, and what are the scaling laws?

**Answer:** One of the most important empirical findings in deep learning is that Transformer performance scales predictably with compute, data, and model size. This finding, formalized in the "scaling laws" papers (Kaplan et al. 2020 from OpenAI, and the "Chinchilla" paper from DeepMind in 2022), has fundamentally shaped how the industry trains LLMs.

The core finding: **loss (model error) decreases as a power law with respect to model parameters, dataset size, and compute**. Doubling the model size, doubling the data, or doubling the training compute each reduces error by a predictable, consistent amount. Importantly, these improvements continue over many orders of magnitude without any observed ceiling — larger models trained on more data with more compute continue to get better.

The **Chinchilla scaling laws** (Hoffmann et al. 2022) refined this with a specific recommendation: for optimal performance at a given compute budget, model size and dataset size should scale roughly equally. Before Chinchilla, models like GPT-3 (175B parameters) were trained on relatively small datasets (300B tokens) — they were "over-parameterized and undertrained." Chinchilla showed that a 70B model trained on 1.4 trillion tokens (20 tokens per parameter) matched GPT-3's performance at half the parameters. This insight shifted the field toward training smaller models on much more data — LLaMA 2 and Mistral 7B are examples of this philosophy.

**What emerges from scale?** A fascinating phenomenon called **emergent capabilities**: abilities that appear suddenly and non-linearly as models cross certain size thresholds. Models below ~10B parameters show near-zero performance on multi-step arithmetic; models above ~100B parameters show strong performance on the same tasks, without this ability existing as a gradual slope. Similarly, in-context learning (learning from examples in the prompt), chain-of-thought reasoning, and instruction following all emerge at certain scales. This is why "just use a bigger model" is sometimes genuinely the answer.

**Practical implications for system design**: Larger models have higher latency and higher per-token cost. The optimal model size for a task is the smallest model that meets the required quality threshold. In production, this means: run benchmarks on your specific task with models of increasing size; find the inflection point where quality meets requirements; deploy that model. Don't default to the largest model available — it's likely overkill for most tasks.

## Key Points to Say in the Interview

- The Transformer processes tokens **in parallel**, not sequentially — this enables training scale
- **Self-attention** lets every token attend to every other token directly, solving the vanishing gradient of RNNs
- Know **BERT vs GPT**: encoder (bidirectional, classification/embedding) vs decoder (causal, generation)
- Name **positional encoding** as necessary because attention is permutation-invariant
- Know **quadratic complexity** of attention: O(n²) with sequence length — this is why context windows are limited
- **Chinchilla scaling laws**: 20 tokens per parameter is optimal for training efficiency
- Name **emergent capabilities** — abilities that appear suddenly at scale thresholds

## Common Mistakes to Avoid

- Saying "RNNs and Transformers are similar" — they have fundamentally different parallelism and long-range dependency properties
- Confusing BERT and GPT — BERT is for understanding/classification, GPT is for generation
- Saying attention has O(n) complexity — it is **O(n²)** and this matters for long contexts
- Forgetting positional encoding — without it, the Transformer can't distinguish word order
- Not knowing that modern LLMs use **RoPE** (rotary positional embeddings) rather than the original sinusoidal encoding

## Further Reading

- [Attention Is All You Need (original paper)](https://arxiv.org/abs/1706.03762) — The 2017 paper introducing the Transformer architecture
- [The Illustrated Transformer](https://jalammar.github.io/illustrated-transformer/) — Jay Alammar's superb visual explanation of every component
- [Chinchilla Scaling Laws](https://arxiv.org/abs/2203.15556) — DeepMind's paper on optimal model size vs. data tradeoffs
