# Context Windows

## What Is It? (Plain English)

A context window is the maximum amount of text an LLM can "see" at one time — its working memory. Everything the model knows about the current task must fit within this window: the system prompt, the conversation history, any documents you've retrieved, the user's current question, and the model's own response. Whatever falls outside the window is completely invisible to the model — it has no memory of it and cannot reason about it.

Think of it like a camera lens. No matter how large a scene exists in the world, the camera can only capture what fits in the frame. Information to the left or right of the frame simply doesn't exist for the camera. Similarly, information before the context window's start or after its end doesn't exist for the LLM. Early models like GPT-3 had tiny windows of 4,096 tokens (roughly 3,000 words — about 10 pages). Modern models push further: GPT-4 Turbo supports 128K tokens, Gemini 1.5 Pro supports 1 million tokens (about 750,000 words — roughly a full novel).

But bigger isn't always better. Long context has costs: it's slower (attention complexity grows quadratically with sequence length), more expensive (you pay for every input token), and models can "lose" information buried deep in the middle of long contexts — a phenomenon called the "lost in the middle" problem. Understanding context windows matters for architects because it shapes retrieval strategy (how much context can you safely inject?), cost estimation (longer contexts = higher costs), and quality (when is RAG better than just stuffing the entire document into context?).

## How It Works

```
═══════════════════════════════════════════════════════════════
                CONTEXT WINDOW STRUCTURE
═══════════════════════════════════════════════════════════════

Maximum: 128,000 tokens (e.g., GPT-4 Turbo)

[←─────────────────── 128K tokens total ───────────────────→]

┌─────────────┬──────────────────────┬───────────┬──────────┐
│System Prompt│  Conversation History │ Retrieved │  User   │
│             │  (previous messages) │  Context  │ Question │
│  ~500-2000  │    ~2000-20,000       │  ~2000-   │  ~200-  │
│   tokens    │      tokens          │  10,000   │  2,000  │
│             │                      │  tokens   │  tokens │
└─────────────┴──────────────────────┴───────────┴──────────┘
                                                       │
                                              Model generates
                                              output here ↓
                                              ~100-4,000 tokens

Budget allocation:
  System prompt:    1-5%    (instructions, persona)
  History:          10-30%  (conversation context)
  RAG context:      5-20%   (retrieved documents)
  User query:       1-5%    (current question)
  Output headroom:  5-30%   (expected response length)

═══════════════════════════════════════════════════════════════
         WHAT HAPPENS WHEN THE WINDOW FILLS UP
═══════════════════════════════════════════════════════════════

Strategy 1: SLIDING WINDOW (Truncate oldest messages)
  Turn 1: [Sys][Q1][A1]         → 500 tokens
  Turn 5: [Sys][Q1][A1][Q2][A2][Q3][A3][Q4][A4][Q5] → 2500 tokens
  Turn N: DROP Turn 1 messages when limit approached
  Limitation: Loses early conversation context

Strategy 2: SUMMARIZATION
  When approaching limit, summarize the earliest N messages:
  [Sys][Summary: "User asked about X, we resolved Y..."][Recent messages]
  Preserves key facts, reduces token count by 80%
  Requires an LLM call to generate the summary (latency + cost)

Strategy 3: RAG OVER CONVERSATION HISTORY
  Store all previous messages in a vector database
  On each turn, retrieve the N most relevant previous messages
  Only include what's relevant to the current query
  Best for very long sessions (100+ turns)

Strategy 4: CONTEXT COMPRESSION
  Use a small model to compress the retrieved context before injection
  Original chunk: 400 tokens → Compressed: 80 tokens
  Keeps the most relevant sentences, discards filler
  Tools: LLMLingua, Selective Context
```

## Why Google Cares About This

Context windows are a fundamental constraint and cost driver in LLM applications. Google's Gemini models have pushed context windows to 1 million tokens — a major engineering achievement that changes what's possible architecturally (can you put an entire codebase in context?). Senior candidates need to understand the tradeoff between long context and retrieval: when does a 1M token context help, when is targeted retrieval better, and what are the cost implications? They also need to understand the "lost in the middle" problem, which means a 1M token context doesn't give you 1M tokens of useful attention — and how to design prompts and retrieval strategies that account for this limitation.

## Interview Questions & Answers

### Q1: What is the "lost in the middle" problem, and how does it affect RAG design?

**Answer:** The "lost in the middle" problem, documented by Liu et al. (2023) in a paper of the same name, is an empirical finding that LLMs perform worse at using information that appears in the middle of a long context, compared to information at the beginning or end. When a relevant piece of information is placed at position 50 of a 100-document context, the model is significantly less likely to use it correctly than when the same information is placed first or last. The model has a U-shaped performance curve across context position.

The root cause is related to attention patterns in Transformer models. During fine-tuning on instruction-following tasks, models are primarily trained on shorter contexts where the relevant information appears prominently. They develop an implicit prior that important information is at the edges of the context. Additionally, the softmax normalization in attention means that when there are hundreds of chunks in context, each individual chunk receives a very small attention weight — the signal is diluted.

**Implications for RAG design:**
1. **Return fewer, higher-quality chunks**: Returning 20 chunks to the LLM hoping it will find the right one is worse than returning 5 highly-ranked chunks — more context dilutes attention on each chunk. Use a strong reranker to select only the top 3-5 most relevant chunks before passing to the LLM.
2. **Placement matters**: Put the most important context close to the user's question (at the end of the prompt). The model attends most strongly to recent tokens relative to the generation position.
3. **Don't rely on context for critical information**: For safety-critical or high-stakes information, don't rely on the model to find a needle in a haystack context. If only one specific fact matters, put it prominently or, better yet, do a targeted lookup and inject it directly.
4. **Summary first, details in context**: Begin the retrieved context with a concise summary of the key facts, then provide detailed evidence. The summary placement at the start ensures the key information is in a high-attention zone.

This problem is one of the reasons RAG with precise retrieval (return the 3-5 most relevant chunks) outperforms "just put everything in context" for most use cases, even when the context window is large enough to fit everything.

### Q2: When should you use RAG versus long-context LLMs, and how do you decide?

**Answer:** The choice between RAG and stuffing documents into a long context is one of the most important architectural decisions in LLM application design, and the answer is nuanced. Long-context LLMs don't eliminate the need for RAG — they change the calculus.

**Use long-context LLMs (no RAG) when:**
- **The document set is small and fixed**: Analyzing one contract, reviewing one codebase, Q&A on one document. If you have 5 documents and they all fit in context, just put them all in. The simplicity is worth it.
- **The task requires understanding relationships across the entire corpus**: Comparing two contracts for inconsistencies, finding dependencies across a codebase. RAG retrieves local chunks; it can miss cross-document patterns.
- **Latency is secondary**: Filling a 1M-token context and waiting for the model to process it takes seconds. If the user can wait, it's simpler.
- **The corpus is stable** (doesn't change frequently) and small enough that re-tokenizing isn't prohibitive.

**Use RAG when:**
- **The corpus is large** (thousands of documents, millions of chunks): No context window can hold all of it. You must retrieve.
- **Freshness matters**: RAG can retrieve from a continuously updated knowledge base. Long-context LLMs need to be re-prompted with updated content.
- **Cost is a constraint**: At $0.01 per 1K tokens, filling a 1M-token context costs $10 per query. RAG with 5 retrieved chunks might cost $0.05 per query. 200x cheaper.
- **Privacy is a concern**: You don't want to send your entire internal knowledge base to a third-party API on every query. RAG sends only the relevant chunks.
- **Different queries need different subsets**: If users ask about different topics, RAG retrieves different subsets. Long-context would always send everything, including irrelevant documents that dilute attention.

**The hybrid strategy** is often optimal for large, diverse corpora: use RAG to retrieve the most relevant 10-20 chunks, then use a medium-context LLM (e.g., 32K tokens) to process them. This combines RAG's scalability with long-context LLMs' ability to reason over multiple retrieved documents together. This is significantly better than RAG with a short-context model (which can only see one chunk at a time) and much cheaper than a 1M-token context.

**When in doubt, benchmark**: Run both approaches on your test set with your quality metrics and pick the one that delivers better quality at acceptable cost. The decision is empirical, not dogmatic.

### Q3: How do you manage conversation history in a long-running chatbot to stay within the context window?

**Answer:** Every chatbot message consumes tokens that accumulate over the conversation. Without management, a long conversation eventually overflows the context window. There are four main strategies, each with different quality/complexity tradeoffs.

**Sliding window (simplest)**: Keep only the last N messages in context. When adding a new message would exceed the limit, drop the oldest messages. Implementation: truncate the message list from the front. Limitation: the model forgets early context entirely. If the user asked their name in message 1 and asks "what did I tell you my name was?" in message 100, the sliding window has forgotten. This works acceptably for short-to-medium conversations and most FAQ chatbots.

**Progressive summarization**: When the conversation grows large, send the oldest N messages to the LLM with the instruction "Summarize this conversation segment in 3-5 sentences, capturing all important facts and decisions." Replace those messages with the summary. The context now contains: [System Prompt] + [Summary of early conversation] + [Recent messages]. This preserves the semantics of early conversation at a fraction of the token cost. The challenge: when to trigger summarization, and how good the summary quality is. Poor summaries lose important details. A good heuristic: summarize when the history reaches 60% of the context window budget.

**Retrieval-augmented memory**: Store all conversation messages in a vector database. On each turn, embed the current user message and retrieve the K most relevant previous messages (by cosine similarity). Include only those in context, plus a fixed window of the most recent messages. This is ideal for very long sessions (support tickets, ongoing projects) where only a subset of prior conversation is relevant to the current query. More complex to implement but scales to arbitrarily long sessions.

**Entity memory**: Maintain a structured summary of key facts extracted from the conversation — user preferences, decisions made, names mentioned, commitments made. Update this structured memory incrementally as new messages arrive. Inject only the relevant entity facts for the current query, not the full conversation. This is the most sophisticated approach and works well for personalized assistants where user context (preferences, history, identity) is the most important information to preserve.

In production, combine approaches: sliding window + summarization for cost efficiency, with entity memory for high-value user facts that must never be lost. LangChain's `ConversationSummaryBufferMemory` implements a combination of sliding window and summarization out of the box.

### Q4: What are the cost implications of different context window sizes, and how do you optimize?

**Answer:** Context window costs are linear — you pay for every token in the input, every time. At scale, context window management is a significant cost lever. Let's quantify this with concrete examples.

At OpenAI's GPT-4o pricing (as of 2024) of $0.005 per 1K input tokens and $0.015 per 1K output tokens:
- A 1K-token system prompt sent in every request at 1M requests/day = 1B tokens/day = $5,000/day just for the system prompt
- A 10K-token long-form context (a 10-page document) per request at 100K requests/day = 1T tokens/day = $5M/day

These numbers make prompt optimization a genuine engineering priority, not a premature optimization.

**Optimization strategies in order of impact:**

**1. Model routing (highest impact)**: Route cheap, simple queries to inexpensive models. A query answerable from a single retrieved paragraph doesn't need GPT-4o — GPT-4o-mini (3x cheaper) or a 7B open-source model works fine. Implementing a query classifier that routes to the appropriate model tier can reduce average cost by 60-80%.

**2. Prompt compression**: Audit system prompts for verbosity. A 2,000-token system prompt that achieves the same result as a 500-token prompt is 4x the cost. Use LLMLingua or similar tools to compress prompts while preserving semantic content. Test carefully — compressed prompts can lose nuance.

**3. RAG context size**: Don't inject 20 retrieved chunks if 5 suffice. Each additional chunk adds ~400 tokens to every request. Tune the number of retrieved chunks by measuring quality impact — often diminishing returns kick in quickly.

**4. Conversation history management**: Implement summarization so you're not re-sending the full conversation history on every turn. A summary that's 200 tokens instead of the 2,000-token original history saves 1,800 tokens per request — 36x cost reduction on the history component.

**5. Output length control**: Set explicit `max_tokens` limits and instruct the model to be concise. "Answer in 1-3 sentences" vs open-ended output can reduce output token usage by 5-10x.

**6. Prefix caching**: OpenAI, Anthropic, and Google support prompt caching — if the same prefix (system prompt + static context) appears in multiple requests, it's only billed once (or at a discount). For applications where the system prompt is large and constant, prefix caching can reduce effective token costs by 50-90%.

### Q5: What are the limits of long-context LLMs, and will larger context windows eventually make RAG unnecessary?

**Answer:** This is a genuine and important question in the field, and the answer is: not for the foreseeable future, because the limitations of long-context LLMs are not purely about window size.

**Current limitations of long-context LLMs:**

**The "lost in the middle" problem (discussed above)**: The model doesn't attend equally to all parts of a long context — information in the middle is systematically underused. This means a 1M-token context window doesn't give you 1M tokens of useful, equally-weighted context. RAG with targeted retrieval often outperforms "just put everything in context" for specific question-answering tasks because retrieved chunks are placed prominently in a shorter context where the model can focus on them.

**Cost**: A 1M-token context call costs $5+ at current pricing. Even as costs decrease, a 1M-token context is ~200x more expensive than a 5K-token RAG context for answering a single question. For applications with millions of queries per day, this is an enormous cost difference.

**Latency**: Processing a 1M-token context takes longer than processing a 5K-token context with retrieved chunks. For real-time user-facing applications, this latency difference is significant.

**Dynamic corpora**: If your knowledge base is updated daily (news, product catalog, internal policies), you can't amortize the cost of encoding a large corpus across requests. RAG with an always-updated vector index is far more efficient for dynamic knowledge.

**Privacy and data minimization**: Sending your entire internal knowledge base to an API on every query violates data minimization principles. RAG sends only the relevant excerpts.

**The likely future trajectory**: Long-context LLMs will be used when the task genuinely requires reasoning across an entire corpus (code review, contract analysis). RAG will remain dominant for large-scale knowledge retrieval and real-time information access. The two approaches are complementary, not competitive — and most sophisticated systems will use both: retrieve the right documents first, then use a long-context model to reason over them deeply.

## Key Points to Say in the Interview

- Context window = LLM's working memory; everything outside it is **invisible to the model**
- Know the **lost in the middle** problem — information placed in the middle of long contexts is underused
- Know the **three history management strategies**: sliding window, summarization, retrieval-augmented memory
- Be able to **quantify context costs**: input tokens × price per 1K tokens × request volume = monthly cost
- Long-context LLMs do **not make RAG obsolete** — they change the tradeoff but don't eliminate retrieval benefits
- Know **prefix caching** as a cost optimization for large, reused system prompts
- The **hybrid approach** (RAG to retrieve → medium-context LLM to reason over retrieved chunks) is often optimal

## Common Mistakes to Avoid

- Saying "larger context = always better" — the "lost in the middle" problem shows **position matters**
- Not quantifying cost implications — Google interviews expect you to reason about **cost at scale**
- Claiming long-context LLMs will replace RAG — they're **complementary**, not substitutes
- Forgetting that **conversation history management** is a core engineering concern, not an afterthought
- Not knowing **prefix caching** — it's a major cost optimization for production systems

## Further Reading

- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) — Liu et al. 2023, the empirical study showing position-dependent performance
- [Gemini 1.5: Long-Context Understanding](https://blog.google/technology/ai/google-gemini-next-generation-model-february-2024/) — Google's announcement and capability demonstration for 1M-token context
- [LLMLingua: Compressing Prompts](https://arxiv.org/abs/2310.05736) — Microsoft's method for compressing prompts by 3-20x with minimal quality loss
