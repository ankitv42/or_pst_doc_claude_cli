# Hybrid Search

## What Is It? (Plain English)

Hybrid search combines two fundamentally different ways of finding relevant documents: keyword search (which looks for exact word matches) and vector search (which looks for semantic meaning). Neither technique alone is sufficient for a robust RAG system — each has blindspots the other covers well.

Keyword search, powered by algorithms like BM25, works by counting how often your query words appear in a document, weighted by how rare those words are across the entire collection. If a user types "Class A SKU lead time threshold," BM25 will find every document that contains those exact words. It's precise and predictable, but completely helpless if a relevant document uses different words to express the same concept.

Vector search, on the other hand, understands meaning. It will find documents about "priority inventory lead time limits" even if none of those exact words were in the query — because the semantic vectors are similar. But vector search can fail when specificity matters: product codes like "SKU-X47B," proper nouns like "FIFO," and exact numerical thresholds like "2.5x reorder multiplier" may not survive the compression into a 768-number vector without being diluted by surrounding context.

Hybrid search fuses both signals — you run both retrieval methods in parallel and merge their ranked lists using a fusion algorithm. The result handles both exact-term matching and semantic similarity, covering each method's weaknesses.

## How It Works

```
User Query: "What is the reorder threshold for Class A items?"
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
       BM25 Keyword Search         Vector ANN Search
       (TF-IDF style scoring)      (cosine similarity)
              │                           │
       Ranked list 1:              Ranked list 2:
        Doc C  (score 8.2)          Doc A  (score 0.91)
        Doc A  (score 7.1)          Doc C  (score 0.87)
        Doc F  (score 5.5)          Doc B  (score 0.84)
        Doc B  (score 4.2)          Doc F  (score 0.79)
              │                           │
              └─────────────┬─────────────┘
                            │
                   RRF Fusion Algorithm
             (combines ranks, not raw scores)
                            │
                    Final Ranked List:
                     Doc C  (RRF: 0.97)
                     Doc A  (RRF: 0.95)
                     Doc B  (RRF: 0.81)
                     Doc F  (RRF: 0.79)
                            │
                   Return top-K to LLM
```

**BM25 scoring formula:**

```
         IDF(qi) * f(qi, D) * (k1 + 1)
BM25 = Σ ─────────────────────────────────
         f(qi, D) + k1 * (1 - b + b * |D|/avgdl)

Where:
  f(qi, D) = frequency of query term qi in document D
  |D|      = document length
  avgdl    = average document length in corpus
  k1, b    = tuning parameters (default k1=1.2, b=0.75)
  IDF      = log((N - n + 0.5) / (n + 0.5))  where n = docs containing term
```

**Reciprocal Rank Fusion (RRF):**

```
RRF_score(doc) = Σ  1 / (k + rank_i(doc))
               i∈{BM25, Vector}

Where:
  rank_i = position of document in ranked list i (1-indexed)
  k      = constant (default 60) to dampen rank differences
```

RRF only uses rank positions, not the raw scores — this sidesteps the problem of BM25 scores (0–15) and cosine similarity scores (0–1) being on incompatible scales.

## Why Google Cares About This

Google Search has operated hybrid search for years — classic TF-IDF/BM25 signals combined with neural/embedding-based ranking. For the ML Engineer role, understanding why you can't just replace BM25 with embeddings (and why Google hasn't) demonstrates practical depth. Every Vertex AI Search deployment uses hybrid retrieval. The interviewer wants to hear that you've thought about failure modes, not just that you know the definition.

## Interview Questions & Answers

### Q1: Why isn't vector-only search sufficient for a production RAG system?

**Answer:** Vector search excels at capturing semantic similarity but compresses meaning into a fixed-size representation. That compression is lossy — not every detail survives. The failure cases fall into three categories.

First, exact identifiers. Product codes ("SKU-A1047"), model numbers ("GPT-4o"), chemical formulas ("H2SO4"), or legal citation numbers ("42 U.S.C. § 1983") are meaningless to a vector model trained on natural language. These tokens appear rarely in training data and get treated as noise during the encoding. A BM25 search for "SKU-A1047" will find the exact match instantly; a vector search may return tangentially related documents with high confidence.

Second, rare or newly coined terms. "Class A SKU" is standard supply chain terminology — but a general-purpose embedding model trained before the term was common in training corpora may not have a strong representation for it. BM25 handles this perfectly because it's purely frequency-based: if the string "Class A SKU" appears in the document, BM25 will score it.

Third, "needle in a haystack" precision queries. When a user asks "what is the exact reorder multiplier for Class A SKUs at 90-day lead time?" they want the specific number, not the semantically nearest discussion of reordering. Vector search may return a paragraph about reorder philosophy that's semantically close but doesn't contain the specific number. BM25, combined with careful chunking, will surface the specific table or sentence containing the exact value.

The converse is also true: BM25-only search fails at paraphrase and semantic equivalence. If the policy document says "priority inventory threshold" and the user asks about "Class A stock limits," BM25 finds nothing. Vector search handles this trivially. Production RAG systems need both.

### Q2: Explain Reciprocal Rank Fusion. Why does it use rank positions instead of raw scores?

**Answer:** Reciprocal Rank Fusion (RRF) is a rank aggregation algorithm that takes multiple ranked lists (each from a different retrieval method) and produces a single merged ranked list. For each document, it sums the reciprocal of the document's rank in each list, weighted by a smoothing constant k (default 60). Documents that rank highly in multiple lists accumulate high RRF scores; documents that rank highly in only one list get a moderate boost.

The formula `RRF(doc) = Σ 1/(k + rank)` is elegant but the key insight is **why ranks and not raw scores**. BM25 scores a document as a floating-point number in the range 0–15 (depending on term frequency and document length). Vector similarity scores are cosine similarities in the range -1 to 1, typically 0.5–0.99 for relevant documents. These are not comparable scales — a BM25 score of 8.5 and a cosine similarity of 0.85 convey different magnitudes of "relevance" with no natural way to add them.

Normalizing raw scores (e.g., min-max scaling) doesn't fully solve this because the score distributions have different shapes. BM25 scores can be heavily influenced by a single very rare term appearing multiple times. Cosine similarity has a compressed upper range near 1.0 for most embedding models. Any linear combination of normalized scores still embeds assumptions about relative importance.

Ranks are ordinal and universally comparable: "rank 1" from BM25 and "rank 1" from vector search both mean "the best result from this method." RRF's k constant (60) prevents rank 1 from dominating too strongly — `1/(60+1) ≈ 0.016` vs `1/(60+2) ≈ 0.016` — meaning small rank differences don't dominate the fusion. Empirically, RRF is competitive with or better than carefully tuned linear score combinations across many benchmarks, and requires no tuning at all.

ORCA implements this in `docs/rag/retriever.py` by running BM25 (via the `rank_bm25` library) and ChromaDB vector search in parallel, then computing RRF scores over the union of results before passing the top-K to the optional cross-encoder reranker.

### Q3: When does BM25 win over vector search, and when does vector search win? Give concrete examples.

**Answer:** BM25 wins in four categories: exact identifiers, technical jargon with no semantic neighborhood, short queries with high specificity, and freshness (newly created documents whose terminology isn't in the embedding model's training data).

Concrete BM25 wins: "What is policy PO-2024-Section-4.3?" — the exact policy identifier is meaningless to vectors. "BAAI/bge-reranker-v2-m3 latency benchmarks" — a model name. "capital allocation threshold of $47,500" — an exact dollar figure. "FIFO vs LIFO inventory accounting" — acronyms that may have diluted representations. "Lead time for supplier XYZ-Corp during Q4" — a specific supplier name. In each case, exact string matching beats semantic approximation.

Vector search wins in four categories: paraphrase and synonym queries, multi-language queries, concept-level questions without specific vocabulary, and when the user doesn't know the right terminology.

Concrete vector wins: "How do I handle low stock situations?" → finds documents about "inventory depletion risk mitigation" without sharing any words. "What happens when items can't be replenished quickly?" → finds lead-time policy documents. "supplier reliability problems" → finds documents titled "vendor performance management." A Spanish query → finds English documents (with a multilingual embedding model). In each case, semantic proximity beats lexical overlap.

The practical heuristic: use BM25 when the query contains domain-specific codes, acronyms, or proper nouns. Use vector when the query is phrased in natural language asking about concepts. Hybrid search covers both cases automatically without requiring query classification.

### Q4: How would you tune the blend between BM25 and vector search in a hybrid system?

**Answer:** There are three main tuning levers: the fusion algorithm choice, the k parameter in RRF, and weighted scoring if you bypass RRF.

The simplest approach is RRF with its default k=60, which requires no domain tuning at all. It performs remarkably well out of the box across many benchmarks. If you use weighted linear combination instead (alpha * vector_score + (1-alpha) * bm25_score, after normalization), then alpha is your primary knob — higher alpha means more weight on semantic similarity.

To determine the optimal alpha, you need a golden evaluation dataset: 50–200 queries with known relevant documents. For each candidate alpha value, run retrieval and compute Recall@K or nDCG@10. Plot the metric across alpha values and pick the peak. This is the right engineering approach rather than guessing.

In practice, the optimal alpha is usually in the 0.5–0.8 range (favoring vectors slightly), but it varies significantly by domain. A codebase search system might favor BM25 heavily (alpha=0.2) because function names and variable names are exact-match critical. A customer support FAQ system might favor vectors (alpha=0.8) because users describe problems in their own words. A supply chain policy retrieval system like ORCA sits in the middle — policy documents use standard terminology (favoring BM25) but user queries may use different phrasing (favoring vectors).

A second tuning dimension is the top-K for each method before fusion. If you retrieve 100 from BM25 and 100 from vector search, RRF has 200 candidates to work with. If you retrieve only 5 from each, RRF is handicapped by small candidate sets. Start with retrieving 50–100 from each method for robust recall, then let reranking narrow to the final top-5 or top-10.

### Q5: How does ORCA implement hybrid search and what would you improve at scale?

**Answer:** ORCA's `docs/rag/retriever.py` implements a two-stage hybrid pipeline. Stage 1 runs BM25 (using the `rank_bm25` library's BM25Okapi implementation) against the raw text of all chunks stored in memory, alongside ChromaDB's vector ANN search. Both methods return ranked lists of chunk IDs. Stage 2 fuses these using RRF with k=60. The fused top-K candidates are then optionally passed to a cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) which scores each candidate against the query more precisely.

The public API exposes four specialized query functions (`query_for_agent1` through `query_for_agent4`) that pre-configure the query with agent-specific filters and context hints. This separation ensures each agent receives only the most relevant policy context for its specific decision type — Agent 2 gets supply replenishment policies, Agent 3 gets capital allocation thresholds.

At scale (millions of documents), three things would need to change. First, BM25 can't run in-memory against millions of chunks — you'd replace it with an inverted index via Elasticsearch or OpenSearch, which implements BM25 natively and scales horizontally. Second, ChromaDB would be replaced with a distributed vector database (Weaviate, Qdrant, or Pinecone). Third, the fusion step becomes a service — not Python code in the retriever module, but a dedicated retrieval microservice that accepts a query and returns fused results, allowing independent scaling of keyword and vector search infrastructure.

An important improvement even at ORCA's current scale: the BM25 index is rebuilt every time the application starts because `rank_bm25` doesn't persist its index. For a small corpus this is fine (milliseconds), but as the corpus grows you'd want to persist the BM25 index (or switch to Elasticsearch) and only rebuild on document changes.

## Key Points to Say in the Interview
- BM25 handles exact terminology, product codes, and acronyms where vector search compresses meaning too much
- Vector search handles paraphrase, synonyms, and concept-level queries where exact words don't match
- RRF uses rank positions, not raw scores, to avoid incompatible scale problems between BM25 and cosine similarity
- The default RRF k=60 is surprisingly robust — it requires no domain-specific tuning to beat naive weighted combinations
- Tune the blend using a golden evaluation dataset — measure Recall@K or nDCG@10 across alpha values
- ORCA runs BM25 in-memory (fine for 71 chunks), but at scale this needs Elasticsearch for the keyword component

## Common Mistakes to Avoid
- Discarding BM25 entirely because "embeddings are better" — this is wrong for domains with specialized terminology
- Linearly combining raw BM25 and cosine scores without normalizing — the scales are completely incompatible
- Forgetting that BM25 requires the corpus to be indexed separately from the vector store — two data structures to maintain
- Tuning the fusion blend on the training set without a held-out validation set — you'll overfit the alpha parameter
- Not retrieving enough candidates before fusion — if each method only returns top-5, RRF has nothing to work with

## Further Reading
- [Reciprocal Rank Fusion (RRF) paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) — Original 2009 paper introducing RRF for combining multiple search rankings
- [Hybrid Search with Weaviate](https://weaviate.io/blog/hybrid-search-explained) — Practical walkthrough of implementing hybrid search with BM25 + vector fusion
- [BM25 Explained](https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables) — Elastic's deep dive into BM25 parameters and tuning
- [BEIR Benchmark: Zero-Shot Retrieval Evaluation](https://arxiv.org/abs/2104.08663) — Benchmark showing where lexical vs semantic methods win across domains
- [rank_bm25 Python library](https://github.com/dorianbrown/rank_bm25) — Lightweight BM25 implementation used in ORCA
