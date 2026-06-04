# RNNs and LSTMs

## What Is It? (Plain English)

Recurrent Neural Networks (RNNs) were the dominant architecture for processing sequential data — text, speech, time series, video frames — before Transformers arrived. The core idea is simple and elegant: to process a sequence, process each element one at a time, and carry a "hidden state" (a vector of numbers) from one step to the next. This hidden state acts as a memory — it encodes what the network has seen so far, allowing it to use past context when processing the current element.

Imagine reading a sentence word by word and maintaining a mental note of the meaning accumulated so far. When you reach the word "it" in "The dog ate its food because it was hungry," your brain uses the accumulated context (the dog was eating, "it" is the subject) to resolve the pronoun correctly. An RNN does the same thing computationally — the hidden state after reading "dog" is passed forward when reading "food," and so on.

The problem: vanilla RNNs have terrible memory. The hidden state from 50 steps ago is almost entirely overwritten by later states — the gradient that would reinforce "remember this word" decays exponentially as it propagates backward through 50 time steps. This is the vanishing gradient problem in sequence modeling. LSTMs (Long Short-Term Memory networks) were invented in 1997 specifically to solve this: they add explicit memory gates that decide what to keep, what to discard, and what to output. LSTMs can reliably maintain context over hundreds of steps, enabling practical sequence modeling.

## How It Works

```
Vanilla RNN (one timestep):
  h_{t-1} ──► ┌─────────────────┐ ──► h_t ──► output_t
               │  tanh(W_h·h +   │
               │        W_x·x_t) │
  x_t ────────►└─────────────────┘

  Problem: gradients of h_{t-50} are W_h^{50} * gradient
  If |W_h| < 1: exponential decay → vanishing gradient
  If |W_h| > 1: exponential growth → exploding gradient

─────────────────────────────────────────────────────────────────
LSTM Cell (one timestep):

  ┌───────────────────────────────────────────────────────┐
  │  LSTM Cell                                             │
  │                                                        │
  │  h_{t-1} ──────────────────────────────────────────── │
  │  x_t ─────────────────────────────────────────────── │
  │         │                │                │           │ │
  │         ▼                ▼                ▼           │ │
  │  ┌────────────┐  ┌─────────────┐  ┌────────────┐   │ │
  │  │ Forget Gate│  │ Input Gate  │  │ Output Gate│   │ │
  │  │ σ(W_f·...)│  │ σ(W_i·...) │  │ σ(W_o·...) │   │ │
  │  │ f_t: 0→1  │  │ i_t: 0→1   │  │ o_t: 0→1   │   │ │
  │  └─────┬──────┘  └──────┬──────┘  └─────┬──────┘   │ │
  │        │                 │               │           │ │
  │        │    Cell state:  │               │           │ │
  │  c_{t-1}─►(× f_t)──►(+ i_t*c̃_t)─►c_t──►(tanh)─►(× o_t)─► h_t
  │                          ▲                                   │
  │                    ┌─────────────┐                          │
  │                    │ tanh(W_c·..)│ ← candidate cell state c̃_t│
  │                    └─────────────┘                          │
  └───────────────────────────────────────────────────────────────┘

  Key:
  f_t: Forget gate — what fraction of c_{t-1} to keep
  i_t: Input gate — whether to write c̃_t to cell state
  o_t: Output gate — what fraction of cell state to expose as h_t
  c_t: Cell state — the "long-term memory" (protected by gates)
  h_t: Hidden state — the "working memory" (exposed at each step)
─────────────────────────────────────────────────────────────────
```

**GRU** (Gated Recurrent Unit): a simplified version of LSTM that merges the forget and input gates into a single "update gate" and removes the separate cell state. 30% fewer parameters, comparable quality to LSTM on most tasks. Preferred when computational budget is tight.

## Why Google Cares About This

LSTMs powered Google Translate for years (before the 2017 Transformer paper), Google's speech recognition systems, and Gmail's Smart Compose. Understanding why RNNs/LSTMs were created, why they were superseded by Transformers, and when they're still preferred (online learning, resource-constrained edge devices, streaming time series) demonstrates historical depth and nuanced judgment. An interviewer who hears "RNNs are obsolete, use Transformers always" will push back.

## Interview Questions & Answers

### Q1: Explain the vanishing gradient problem in RNNs and why it makes them fail at long sequences.

**Answer:** During backpropagation through time (BPTT), gradients are computed by unrolling the RNN through all timesteps and applying the chain rule backward. For a sequence of length T, the gradient of the loss with respect to the hidden state at timestep 1 involves T multiplications of the weight matrix W_h:

```
∂L/∂h_1 ∝ (W_h^T) * (∂L/∂h_T)
```

If the largest eigenvalue of W_h is less than 1, this product shrinks exponentially with T. With T=50 timesteps and eigenvalue 0.9, the gradient is 0.9^50 ≈ 0.005 — vanishingly small. With T=100 and eigenvalue 0.9, it's 0.9^100 ≈ 0.00003. The weights in early layers of a long-sequence RNN receive gradients so small they might as well be zero — these weights never update meaningfully.

The practical consequence: plain RNNs can only "remember" information from the last 5–20 timesteps regardless of sequence length. For the sentence "The trophy doesn't fit in the suitcase because it is too large" — where "it" must resolve to "trophy" 8 words earlier — a simple RNN struggles. For longer dependencies, like a question at the start of a paragraph being answered by information at the end, plain RNNs effectively fail.

The exploding gradient problem is the mirror issue: eigenvalues > 1 cause gradients to grow exponentially, destabilizing training with NaN losses. Gradient clipping (capping gradients at a maximum norm) is the standard fix for exploding gradients. There's no symmetric fix for vanishing gradients — you need architectural changes.

LSTMs address vanishing gradients through the cell state and its gate structure. The cell state has an additive update (not multiplicative like RNNs): `c_t = f_t * c_{t-1} + i_t * c̃_t`. Gradients flow back through the cell state without the W_h matrix being in the path — the forget gate provides a nearly-unobstructed gradient highway back in time. This is why LSTMs can maintain relevant context over hundreds of timesteps while vanilla RNNs cannot.

### Q2: Explain the LSTM gates intuitively. What does each gate decide?

**Answer:** The LSTM's three gates can be understood as a filtration system for a "cell state" — a dedicated memory channel that carries information across long distances in the sequence without being directly written to at every step.

**The Forget Gate** decides how much of the previous cell state to retain. Its output f_t is a vector of values between 0 and 1 (via sigmoid activation). Multiplied with the previous cell state `c_{t-1}`, it selectively "forgets" parts of memory. When an LSTM reads "The CEO, who has been running the company since 2015, today announced..." — when it hits "today," the forget gate appropriately reduces the weight on old news (the "since 2015" context) while retaining "CEO" for the continuation. If f_t ≈ 1 for a dimension, that memory is fully preserved; f_t ≈ 0 wipes it.

**The Input Gate** decides whether to write new information to the cell state. It has two components: i_t (the gate, 0-to-1) controls how much to write, and c̃_t (the candidate, a full-range tanh vector) is what to write. The LSTM only updates cell state dimensions that the input gate "opens." When reading an important noun like "supplier" in a purchase order context, the input gate opens to write the entity type into cell memory; when reading "the" or "a," the gate stays mostly closed (no new information worth storing).

**The Output Gate** decides what fraction of the current cell state to expose as the output hidden state h_t. The cell state may contain many things remembered from far back in the sequence; the output gate selects which parts are relevant for predicting the current output token or passing to the next layer. This separation between what's stored (c_t) and what's expressed (h_t) is what makes LSTMs powerful — the cell can maintain long-term storage while the hidden state focuses on immediately relevant features.

The key insight: all three gates are learned jointly via backpropagation. Nobody programs the LSTM to "forget subject pronouns when a sentence ends." The gate weights learn from data when to open, close, and partially open — specializing automatically to the patterns in the training sequences.

### Q3: When should you use RNNs/LSTMs instead of Transformers?

**Answer:** Transformers have largely replaced LSTMs for most NLP and sequence modeling tasks at scale, but LSTMs retain genuine advantages in specific scenarios.

**Online (streaming) inference**: Transformers require the full input sequence to compute attention. For a streaming application — processing audio frames in real time, running inference on each new sensor reading as it arrives — you need an architecture that processes one element at a time with a fixed-size state. LSTMs are natively streaming: process x_t, update hidden state, emit output, discard all previous inputs. For a smart speaker doing real-time speech recognition or a production line sensor doing anomaly detection, LSTMs are far more practical than Transformers.

**Severe memory constraints (edge deployment)**: A Transformer's attention matrix is O(T²) in memory for sequence length T. For long sequences on resource-constrained hardware (microcontrollers, embedded systems), this is prohibitive. An LSTM's memory usage is O(hidden_dim) regardless of sequence length — constant memory for a streaming sequence. LSTMs are still the dominant choice for voice-activated IoT devices.

**Very long sequences with local structure**: For sequences of millions of elements (genomics: entire chromosome sequences; physics simulations), Transformer attention over the full sequence is computationally infeasible. Hierarchical LSTMs, or LSTMs with restricted attention windows, remain practical. Though modern alternatives like S4/Mamba (state space models) are increasingly preferred here.

**Small datasets where inductive biases help**: Transformers require large amounts of data to learn useful representations from scratch (the positional encoding provides little structural bias). LSTMs have stronger sequential inductive biases built in — they process elements in order, naturally respecting causality. On small time-series datasets (a few thousand examples), LSTMs often outperform Transformers that haven't been pretrained.

**Transformers are strictly better when**: you have large datasets, you need long-range dependencies that span the full sequence, you want to pretrain and fine-tune, or you need parallel training (LSTMs are inherently sequential and cannot be parallelized across time steps).

### Q4: What is backpropagation through time (BPTT) and why is truncated BPTT used in practice?

**Answer:** Backpropagation Through Time (BPTT) is the algorithm for training RNNs. The RNN is "unrolled" across all T timesteps, creating a computational graph that looks like a T-layer feedforward network. Standard backpropagation is then applied through this unrolled graph to compute gradients with respect to the shared weights (W_h and W_x, which are the same at every timestep).

The problem with full BPTT: for a sequence of length T=1,000 (common in language modeling where documents have thousands of tokens), the unrolled graph has 1,000 copies of the network stacked vertically. This requires storing activations for all 1,000 timesteps simultaneously (for backpropagation), which can exhaust GPU memory. The gradient computation is also O(T) time steps — slow for long sequences.

Truncated BPTT (TBPTT) is the practical solution: process the sequence in chunks of k timesteps. Forward pass through k steps, backpropagate through those k steps, update weights, then continue with the next k steps (but carry the hidden state forward as a constant, not differentiating through it). This limits gradient computation to k steps, making memory O(k) instead of O(T).

The tradeoff: TBPTT can't learn dependencies longer than k timesteps, because gradients don't flow back further than k steps. Choosing k: typically 32–256 for language modeling. For time series where you know the relevant dependencies are short (e.g., only the last 10 minutes of sensor data matter), k can be set to match the known dependency length.

For LSTMs specifically, the cell state carries long-term information forward as a constant across TBPTT chunk boundaries. The hidden state is also carried forward. So even with TBPTT(k=32), an LSTM can use context from 200 steps ago — it just can't credit that context through backpropagation (it can't learn to explicitly remember things for more than k steps based on gradient signal, but information in the cell state from earlier can still influence outputs).

### Q5: What replaced RNNs/LSTMs for NLP and why, and what are SSMs (state space models)?

**Answer:** Transformers (2017) replaced LSTMs as the dominant NLP architecture for three reasons: parallelism, long-range attention, and pretraining scalability.

**Parallelism**: LSTMs process sequences step-by-step — step t cannot start until step t-1 completes. This is inherently sequential, making training on GPUs (which excel at parallel operations) inefficient. Transformers compute attention over all positions simultaneously — all timesteps are processed in parallel, making training dramatically faster and enabling scaling to larger datasets.

**Long-range attention**: LSTMs struggle with dependencies hundreds of steps apart (despite LSTMs being better than vanilla RNNs, they still degrade on very long dependencies). Transformers compute direct attention between any two positions — the distance between tokens doesn't matter. "The trophy [200 words earlier] ... it" — Transformers handle this trivially; LSTMs would likely fail.

**Pretraining scalability**: Transformers scale well with data and parameters (scaling laws). BERT, GPT, and their successors demonstrate that massive pretrained Transformers transfer powerfully to downstream tasks. LSTMs don't scale as cleanly — very large LSTMs (>1B parameters) are difficult to train efficiently.

However, Transformers have an O(T²) attention complexity that becomes prohibitive for very long sequences. This gap motivated **State Space Models (SSMs)**, particularly **S4** (Structured State Space Sequence Model, 2021) and **Mamba** (2023). SSMs are a class of models that maintain a hidden state like RNNs but can be computed as a convolution (like CNNs) during training for full parallelism. At inference time, they revert to RNN-mode — O(1) memory per step.

Mamba specifically adds selective state space — a mechanism analogous to LSTM gates that allows the model to selectively remember or forget information. Mamba matches Transformer quality on many sequence modeling benchmarks while scaling to sequences of millions of elements at O(T log T) complexity. Google's recent Gemini models incorporate ideas from this space. For long-context tasks (processing entire codebases, genomic sequences), SSMs are a rapidly growing alternative to Transformers.

## Key Points to Say in the Interview
- Vanilla RNNs vanish gradients exponentially with sequence length — practically limited to ~20 timesteps of memory
- LSTM gates (forget/input/output) give explicit control over what to keep, write, and read from a dedicated cell state
- GRUs are simplified LSTMs (single update gate) with 30% fewer parameters and similar quality
- LSTMs still win over Transformers for: streaming inference, memory-constrained edge devices, small datasets
- BPTT unrolls the RNN through time — truncated BPTT limits gradient computation to k steps for memory efficiency
- State Space Models (Mamba) combine RNN-mode inference efficiency with Transformer-quality and sub-quadratic scaling

## Common Mistakes to Avoid
- Saying "RNNs are obsolete" — they're still used in production for streaming applications and edge devices
- Confusing the cell state (c_t, long-term storage) with the hidden state (h_t, output at each step) in LSTMs
- Forgetting that gradient clipping is needed even for LSTMs to handle exploding gradients
- Applying LSTMs to very long sequences without truncated BPTT — will run out of memory
- Claiming LSTMs solve vanishing gradients completely — they significantly mitigate it but very long sequences still challenge them

## Further Reading
- [Understanding LSTMs (Colah's blog)](https://colah.github.io/posts/2015-08-Understanding-LSTMs/) — The definitive intuitive explanation of LSTM gates with excellent diagrams
- [Original LSTM Paper (Hochreiter & Schmidhuber, 1997)](https://www.bioinf.jku.at/publications/older/2604.pdf) — The original 1997 paper introducing LSTMs
- [Sequence to Sequence Learning (arXiv)](https://arxiv.org/abs/1409.3215) — The seq2seq LSTM paper that powered early Google Translate
- [Mamba: Linear-Time Sequence Modeling with Selective State Spaces (arXiv)](https://arxiv.org/abs/2312.00752) — The modern SSM paper that challenges Transformers for long-sequence tasks
- [Empirical Evaluation of Gated Recurrent Neural Networks (arXiv)](https://arxiv.org/abs/1412.3555) — The GRU paper comparing GRU, LSTM, and vanilla RNNs empirically
