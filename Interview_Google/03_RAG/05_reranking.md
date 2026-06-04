# Reranking

## What Is It? (Plain English)

Reranking is the second stage of a two-stage retrieval pipeline. The first stage (retrieval) casts a wide net quickly — it uses approximate methods to pull back the top 20 or 50 candidate documents from a corpus of millions. The second stage (reranking) takes that small candidate set and applies a more expensive, more accurate model to sort them properly before passing the top 5 to the LLM.

The intuition is like hiring a job candidate. The initial screening (retrieval stage) might use keyword matching on a resume to reduce 10,000 applicants to 50 promising ones. The final ranking (reranking stage) is the face-to-face interview — slower, more expensive, but far more accurate at distinguishing between the qualified 50. You can't run the face-to-face interview with 10,000 people (too slow), but you absolutely shouldn't skip it and just pass all 50 to the hiring manager (too noisy).

Without reranking, the documents you send to the LLM are in "roughly correct" order based on a fast approximate signal. With reranking, they're in the best possible order based on a joint understanding of both the query and the document together. This directly improves answer quality: LLMs perform best when the most relevant context appears first, and context windows are finite — if the 5th-most-relevant document is actually the most useful, it needs to be at position 1 in your context.

## How It Works

```
Two-Stage Retrieval Pipeline
───────────────────────────────────────────────────────────────
Stage 1: RETRIEVAL (fast, independent encoding)

  Query ──► Bi-encoder ──► Query Vector q
  Doc 1 ──► Bi-encoder ──► Doc Vector d1   score = cos(q, d1)
  Doc 2 ──► Bi-encoder ──► Doc Vector d2   score = cos(q, d2)
  ...
  Retrieve top-20 candidates in ~5ms
  (Each document encoded independently)

Stage 2: RERANKING (slow, joint encoding)

  [Query + Doc 1] ──► Cross-Encoder ──► relevance_score: 0.94
  [Query + Doc 5] ──► Cross-Encoder ──► relevance_score: 0.91
  [Query + Doc 12]──► Cross-Encoder ──► relevance_score: 0.87
  ...
  Re-sort top-20 by reranker scores, keep top-5
  (~50ms for 20 candidates)

Final: Pass top-5 reranked documents to LLM
───────────────────────────────────────────────────────────────
```

**Bi-encoders** (used in Stage 1) encode the query and each document independently, then compute a score (cosine similarity) between the two resulting vectors. This is fast because document vectors can be precomputed and stored — at query time you only need to encode the query once and do vector math.

**Cross-encoders** (used in Stage 2) take the concatenation of the query and a candidate document as a single input and produce a single relevance score. Because the model sees both the query and document simultaneously, it can compute fine-grained interactions — "this specific phrase in the document answers exactly this part of the query." This is dramatically more accurate than bi-encoder scoring but cannot be precomputed — you must run the model once per (query, candidate) pair.

## Why Google Cares About This

Reranking is a core component of Google's search and Vertex AI Ranking API. In senior interviews, you're expected to explain the recall-precision tradeoff, why you don't just use the cross-encoder for everything (latency), and what happens to answer quality when you skip reranking. Understanding how ORCA uses `BAAI/bge-reranker-v2-m3` and why that specific model was chosen demonstrates hands-on experience, not just textbook knowledge.

## Interview Questions & Answers

### Q1: Why can't you just use a cross-encoder for the initial retrieval (instead of the two-stage pipeline)?

**Answer:** A cross-encoder requires a forward pass through a transformer model for every (query, document) pair. If your corpus has 10 million documents and you run a cross-encoder for each pair at query time, that's 10 million transformer forward passes — which would take hours on a GPU, not milliseconds. The two-stage pipeline exists precisely to make cross-encoder quality feasible at scale.

To be concrete: `BAAI/bge-reranker-v2-m3` processes roughly 100–200 (query, document) pairs per second on a CPU, or 2,000–5,000 on a GPU. At 10 million documents, cross-encoding all of them takes 50,000+ seconds on CPU or 2,000+ seconds on GPU. Neither is acceptable for a user-facing application requiring sub-second response.

The bi-encoder in Stage 1 solves this by precomputing document embeddings offline. At query time, only the query needs encoding (one forward pass), and similarity computation is simple vector math (near-instant on any hardware). The cost is accuracy — bi-encoders encode query and document independently, so they can't capture fine-grained query-document interactions. They're optimized for recall (finding all relevant documents) at the expense of precision (ranking them perfectly).

The two-stage design gives you the best of both worlds: bi-encoder recall (nothing important is dropped from the candidate set) + cross-encoder precision (the top-K passed to the LLM are correctly ordered). The key design parameter is how many candidates Stage 1 retrieves for Stage 2 — too few and you might miss relevant documents, too many and Stage 2 latency becomes noticeable.

### Q2: How does a cross-encoder model like BGE-reranker-v2-m3 actually work internally?

**Answer:** BGE-reranker-v2-m3 is built on a bidirectional transformer encoder (similar architecture to BERT). The input is the query and document concatenated with a separator token: `[CLS] query [SEP] document [SEP]`. The model processes this entire sequence through all transformer layers with full bidirectional attention — every token in the query attends to every token in the document and vice versa. This cross-attention between query and document tokens is the source of its accuracy advantage over bi-encoders.

The output is taken from the `[CLS]` token's final-layer representation, which is passed through a linear classification head to produce a single relevance score (a logit, converted to probability 0–1 via sigmoid). The model is fine-tuned on large relevance datasets — MSMARCO passage ranking, BEIR benchmark data — with pairs labeled as relevant or not relevant, using a binary cross-entropy loss. This direct supervision on (query, document) relevance pairs makes it an accurate judge of whether a document answers a query.

BGE-reranker-v2-m3 specifically is a multilingual model from the Beijing Academy of AI (BAAI), designed to work across 100+ languages with a single model. "v2-m3" indicates the second iteration of their multilingual reranking family. It balances quality with inference speed — it's not the most accurate reranker (BGE-reranker-v2-gemma or Cohere Rerank v3 beat it on English benchmarks) but it runs efficiently on CPU without requiring GPU infrastructure, which is important for ORCA's Render deployment.

The model's output score can be interpreted as "how likely is this document to be the correct answer to this query?" — not just similar, but actually answering. This is a stronger signal than cosine similarity between independently encoded vectors.

### Q3: What is the recall-precision tradeoff in retrieval, and how does reranking help navigate it?

**Answer:** Recall measures "what fraction of all relevant documents did I retrieve?" A system with perfect recall returns every document that could possibly help the user, but may also return many irrelevant ones. Precision measures "what fraction of my retrieved documents are actually relevant?" A high-precision system returns mostly useful documents but might miss some that would have helped.

In the context of RAG, the tension is this: the LLM's context window is finite (8K, 16K, 128K tokens). You can only pass a limited number of document chunks to the LLM. If you optimize for recall by sending 50 chunks, you flood the context with noise and the LLM's attention dilutes across irrelevant content, degrading answer quality. If you optimize for precision by sending only 3 chunks, you risk missing the one chunk that contains the crucial answer.

Reranking resolves this tension elegantly. Stage 1 (retrieval) optimizes for recall — retrieve 50 candidates and accept that many are irrelevant. Stage 2 (reranking) optimizes for precision — rerank those 50 and return the top 5, which are now highly likely to all be relevant. You get high recall from Stage 1 and high precision for the final LLM context from Stage 2.

Without reranking, you face a painful choice: retrieve 50 (high recall, low precision, LLM degraded by noise) or retrieve 5 (low recall, may miss the answer). With reranking, you retrieve 50 and surface the 5 best — high recall and high precision simultaneously.

The practical numbers: in ORCA's evaluation framework, the system retrieves top-20 candidates from hybrid search, then reranks to top-5 for the LLM. This means the answer quality depends critically on whether the correct chunk is in the top-20 after hybrid retrieval (recall@20) and then whether it rises to top-5 after reranking (precision@5).

### Q4: What are the latency implications of adding a reranker, and when would you skip it?

**Answer:** A cross-encoder reranker adds fixed latency proportional to the number of candidates you rerank. On CPU (which is ORCA's Render free-tier environment), `BAAI/bge-reranker-v2-m3` reranking 20 candidates takes approximately 150–400ms. On GPU, this drops to 20–50ms. This is significant for real-time applications but acceptable for ORCA, which already runs a multi-step LangGraph pipeline where total latency is seconds, not milliseconds.

When to skip reranking: (1) When your retrieval quality is already very high due to excellent chunking and hybrid search — reranking adds complexity and latency with diminishing returns if BM25+vector already ranks correctly 95% of the time. (2) When your corpus is very small — with 71 chunks like ORCA, the initial retrieval set is already nearly exhaustive, so reranking provides minimal lift. (3) When you're latency-constrained with strict SLAs under 100ms total — skip reranking entirely and compensate with a larger initial retrieval set or better chunking.

When reranking is essential: (1) When you have a large diverse corpus where BM25 and vector search produce noisy rankings. (2) When the LLM's answer quality is visibly poor because the most relevant document is appearing 10th instead of 1st in the context. (3) When queries are complex multi-part questions where the document needs to answer all parts, not just be semantically similar overall.

An alternative to cross-encoder reranking is Cohere Rerank v3, which is an API-based reranker. The quality is comparable to BGE-reranker for English, it requires no local model infrastructure, and latency is typically 50–200ms (network-dependent). The tradeoff is cost (per API call) and data privacy (your documents are sent to Cohere's servers). For ORCA's open-source-first, free-tier architecture, running the model locally is preferable.

### Q5: How does ORCA use BAAI/bge-reranker-v2-m3 and what would you change to improve retrieval quality?

**Answer:** ORCA's retrieval pipeline in `docs/rag/retriever.py` loads `BAAI/bge-reranker-v2-m3` via the `sentence-transformers` library's `CrossEncoder` class. After RRF fusion produces a ranked list of top-20 candidate chunks, the cross-encoder scores each (query, chunk_text) pair and re-sorts them. The top-5 chunks by reranker score are returned as the final context string passed to whichever agent called the retrieval function.

Three improvements would meaningfully increase retrieval quality given more resources:

First, use a larger, more accurate reranker. BGE-reranker-v2-m3 is a practical balance for CPU deployment, but `BAAI/bge-reranker-v2-gemma` (based on Gemma) or Cohere Rerank v3 score higher on BEIR benchmarks. The quality gain for ORCA's specific supply chain domain is unknown without empirical testing — which leads to the second improvement.

Second, build domain-specific golden test cases specifically for reranking quality, not just retrieval recall. ORCA's Layer 1 eval tests whether correct keywords appear in the retrieved context, but doesn't directly measure whether the most relevant chunk is ranked first. A reranking-specific eval would construct (query, ideal_doc_id, decoy_docs) triples and measure whether the reranker consistently promotes the ideal document above the decoys.

Third, experiment with query expansion before sending to the reranker. If the user's query is short ("Class A lead time"), a language model can generate an expanded hypothetical answer ("Class A SKUs require lead times of X days and should be reordered when stock falls below Y units..."). Using this expanded query for reranking often improves results because the cross-encoder now has more signal to work with. This technique is called HyDE (Hypothetical Document Embeddings) when applied to the retrieval stage, and a similar idea applies to the reranking query.

## Key Points to Say in the Interview
- Two-stage retrieval: bi-encoder for recall (fast, precomputed), cross-encoder for precision (slow, joint encoding)
- Cross-encoders see both query and document together — this joint attention is why they're more accurate
- Reranking resolves the recall-precision tradeoff: retrieve 50 for recall, rerank to top-5 for precision
- BGE-reranker-v2-m3 runs on CPU without GPU infrastructure — practical for cost-constrained deployments
- Reranking latency is proportional to N candidates × model inference time — profile before adding to your pipeline
- Skip reranking when corpus is small, retrieval quality is already high, or strict latency SLAs don't allow it

## Common Mistakes to Avoid
- Using the same model for retrieval and reranking (they are different model types with different training objectives)
- Reranking too few candidates (top-5) — defeats the purpose; retrieve at least 20 to give the reranker material to work with
- Ignoring reranker latency until after deployment — always benchmark on your target hardware before integrating
- Assuming a higher MTEB reranking score always beats a lower one for your specific domain — always domain-eval before committing
- Sending reranked results in the wrong order to the LLM — the LLM should receive the most relevant document first, not last

## Further Reading
- [BGE Reranker Model Card (Hugging Face)](https://huggingface.co/BAAI/bge-reranker-v2-m3) — Official documentation for the model ORCA uses, including benchmark scores and usage examples
- [Cohere Rerank Documentation](https://docs.cohere.com/docs/reranking) — Production-grade API-based reranking alternative with strong English benchmarks
- [ColBERT: Efficient and Effective Late Interaction (arXiv)](https://arxiv.org/abs/2004.12832) — Alternative to cross-encoders that achieves similar quality with better latency via late interaction
- [Sentence Transformers: CrossEncoder documentation](https://sbert.net/docs/cross_encoder/pretrained_models.html) — Library used in ORCA with a curated list of pretrained cross-encoder models
- [Lost in the Middle: LLM performance vs document position](https://arxiv.org/abs/2307.03172) — Stanford paper showing LLMs perform best when relevant context is at the beginning, motivating correct reranking order
