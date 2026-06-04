# RAG System Design

## What Is It? (Plain English)

Retrieval-Augmented Generation (RAG) is a technique that gives a language model access to a knowledge base it wasn't trained on. Think of it as the difference between a consultant answering from memory versus a consultant who, before answering, opens a filing cabinet, pulls out the five most relevant documents, reads them quickly, and then answers. The LLM is the consultant; the filing cabinet is your document store; the act of pulling and reading the right documents is retrieval.

The problem RAG solves is fundamental: LLMs are trained on data up to a cutoff date, they can't access proprietary company documents, and they hallucinate when asked about things they don't know confidently. RAG addresses all three: by retrieving up-to-date, company-specific documents and inserting them into the model's context, you get answers that are grounded in real information rather than the model's training data. A legal chatbot built with RAG can answer questions about your specific contracts; a customer service bot can answer questions about your exact return policy; a financial assistant can answer about your company's actual Q3 earnings.

From a systems design perspective, RAG has two distinct pipelines that must be designed separately: an **ingest pipeline** (run offline when documents change) and a **query pipeline** (run in real-time when a user asks a question). Getting either one wrong degrades end-to-end quality. Senior engineers need to be able to describe both pipelines in detail, reason about the tradeoffs at each step, and explain how to measure and improve performance.

## How It Works

```
═══════════════════════════════════════════════════════════════
                     INGEST PIPELINE (Offline)
═══════════════════════════════════════════════════════════════

Raw Documents (PDFs, Word, HTML, databases…)
        │
        ▼
┌───────────────────┐
│  Document Loader  │  Extract text, preserve structure
│  (PDFs → text)    │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│     Chunking      │  Split into 256-512 token chunks
│  (with overlap)   │  Overlap: 50-100 tokens between chunks
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Embedding Model  │  Each chunk → dense vector (e.g., 768-dim)
│ (nomic/BGE/ada)   │  nomic-embed-text, text-embedding-3-small…
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Vector Database  │  Indexed with HNSW for fast ANN search
│ (ChromaDB/Pinec.) │  Stores: chunk text + vector + metadata
└───────────────────┘

═══════════════════════════════════════════════════════════════
                  QUERY PIPELINE (Real-time, <2s)
═══════════════════════════════════════════════════════════════

User Question: "What is the reorder threshold for Class A SKUs?"
        │
        ▼
┌───────────────────┐
│  Query Embedding  │  Same embedding model as ingest
└─────────┬─────────┘
          │
          ├────────────────────────────────────┐
          ▼                                    ▼
┌──────────────────────┐           ┌─────────────────────┐
│   Vector Search      │           │    BM25 / Keyword   │
│ (semantic similarity)│           │       Search        │
│  Top-K=20 results    │           │  Top-K=20 results   │
└──────────┬───────────┘           └──────────┬──────────┘
           │                                  │
           └────────────┬─────────────────────┘
                        │ Merge with RRF
                        ▼
             ┌─────────────────────┐
             │   Reranker          │  Cross-encoder scores
             │ (BGE-reranker)      │  all candidates → top 5
             └──────────┬──────────┘
                        │ Top 5 chunks
                        ▼
             ┌─────────────────────┐
             │  Context Assembly   │  Format chunks + query
             │  + Prompt Build     │  into LLM prompt
             └──────────┬──────────┘
                        │
                        ▼
                   LLM (Gemini/GPT)
                        │
                        ▼
                  Grounded Answer
```

## Why Google Cares About This

RAG is the dominant pattern for enterprise AI applications, and Google ships RAG in products ranging from Vertex AI Search to NotebookLM to Google's AI-powered Search features. Interviewers at Google test RAG knowledge at depth because shallow RAG (just embed and retrieve) is easy to build but breaks in subtle ways at production scale. They want to know if you understand chunking strategy's effect on retrieval quality, when hybrid search beats pure vector search, how to measure and improve recall and precision, and how to design for low latency with high accuracy. A candidate who can describe the full system — both pipelines, all the tradeoffs, and the evaluation framework — demonstrates genuine production experience.

## Interview Questions & Answers

### Q1: Walk me through the full design of a production RAG system for a large enterprise knowledge base with 100,000 documents.

**Answer:** I'd design this in two phases — ingest and query — with careful attention to the tradeoffs at each step, and I'd instrument everything so we can measure and improve quality over time.

**Ingest pipeline**: First, document loading. At 100K documents, we need a reliable, idempotent pipeline that can handle diverse formats (PDF, Word, HTML, Confluence pages). I'd use a library like Unstructured or LlamaIndex's document loaders, and critically, I'd track document hashes so we only re-ingest documents that have actually changed. Next, chunking strategy: I'd use recursive character splitting with a chunk size of ~400 tokens and 50-token overlap. The overlap prevents a relevant passage from being split across two chunks and missing context at boundaries. For structured documents (policy docs, tables), I'd use semantic chunking — splitting at sentence and paragraph boundaries rather than fixed character counts. I'd also embed metadata into each chunk: document title, section header, page number, last-modified date. This metadata is crucial for filtering and attribution.

For embeddings, at enterprise scale I'd benchmark several models on a sample of the actual documents: `nomic-embed-text-v1.5` (free, good quality), `text-embedding-3-small` (OpenAI, low cost), and a BGE model if Chinese content is involved. I'd run MTEB benchmarks and also domain-specific tests on internal document types. The embedding model choice is a **one-way door** at scale — migrating 100K documents to a new embedding model requires re-embedding everything, so choose carefully upfront.

Vector database: for 100K documents averaging 5 chunks each = ~500K vectors. At this scale, Pinecone, Weaviate, or pgvector all work. I'd choose based on existing infrastructure — if we're on GCP, Vertex AI Matching Engine; if it's greenfield, Weaviate for its hybrid search support. HNSW index with ef=200, m=16 gives good recall/latency tradeoff.

**Query pipeline**: query → embed → vector search (top-20) + BM25 (top-20) → RRF fusion → reranker (top-5) → LLM. The latency budget: query embedding ~30ms, vector search ~50ms, BM25 ~20ms, reranking ~150ms, LLM ~1-3s. Total: under 4 seconds for complex queries. I'd set P95 SLA at 3 seconds and alert if exceeded. I'd also add a result quality check: if the top retrieved chunk has cosine similarity below 0.6 to the query, return a "I don't have information on this" response rather than hallucinating.

### Q2: What chunking strategy would you choose, and how does chunk size affect retrieval quality?

**Answer:** Chunking is one of the highest-leverage decisions in a RAG system, and it's frequently underestimated. The chunk is the atomic unit of retrieval — whatever you put in a chunk is what gets retrieved together. If a chunk is too small, it loses context; too large, it adds irrelevant information that dilutes the relevance signal.

**Chunk size effects on retrieval quality:**
- **Too small (50-100 tokens)**: Individual sentences or short passages. High precision (the retrieved text is likely relevant) but low recall (the full answer often requires context from the surrounding paragraph). The embedding of a single sentence often doesn't capture enough meaning for reliable semantic matching.
- **Too large (1000+ tokens)**: Full pages or long sections. High recall but low precision — the chunk likely contains the relevant information, but also a lot of irrelevant information. The embedding is an average of the whole chunk, diluting the signal. Also, large chunks consume more of the LLM's context window.
- **Sweet spot (256-512 tokens)**: Usually 2-4 paragraphs. Rich enough for meaningful embeddings, focused enough for precision. This is the empirical sweet spot for most use cases.

**Chunking strategies in order of sophistication:**
1. **Fixed-size**: Split every N characters or tokens, regardless of semantic boundaries. Simple, fast, but breaks sentences and paragraphs arbitrarily. Use only for homogeneous, unstructured text.
2. **Sentence-based**: Split on sentence boundaries. Better for preserving meaning, but sentences vary wildly in length, so chunk sizes are inconsistent.
3. **Recursive character splitting**: Try to split on paragraph boundaries first, then sentence boundaries, then word boundaries, then characters. This is LangChain's default and a good starting point.
4. **Semantic chunking**: Use embedding similarity to detect topic shifts — if two consecutive sentences have low cosine similarity, that's a good split point. Highest quality, but slower and more complex to implement.

**Overlap**: Always use overlap (50-100 tokens). The overlap window ensures that context near a chunk boundary isn't lost — if the relevant sentence is the last sentence of chunk 3 and the first sentence of chunk 4, both chunks will contain it and retrieval will find at least one.

**Parent-child chunking** is an advanced technique worth knowing: store small chunks (128 tokens) for retrieval (high precision) but, when retrieved, return their parent chunk (512 tokens) to the LLM for richer context. This gets the best of both worlds — precise retrieval targeting, rich generation context.

### Q3: Why is hybrid search better than pure vector search, and how does RRF fusion work?

**Answer:** Pure vector search is excellent at semantic matching — finding documents that "mean the same thing" even when they use different words. If the user asks "how do I cancel my subscription?" and the document says "membership termination procedure," vector search finds the match because the embeddings are similar. But vector search fails when exact terms matter: product codes, proper nouns, version numbers, specific legal terms. "Error code 0x80070005" in vector space is close to lots of error codes; BM25 keyword search matches exactly on "0x80070005."

BM25 (Best Match 25) is the classic keyword search algorithm, an improved version of TF-IDF. It ranks documents by: how often the query terms appear in the document (term frequency), how rare those terms are across the whole corpus (inverse document frequency), and document length normalization (to avoid always preferring longer documents). BM25 is exact and deterministic; it excels when the user uses the same terminology as the documents.

The combination — hybrid search — gets the best of both: semantic understanding from vectors, exact matching from BM25. The key question is how to merge two ranked lists into one. **Reciprocal Rank Fusion (RRF)** is the standard answer. The formula is simple: for each document, compute `score = Σ 1 / (k + rank_in_list)` across all ranked lists, where k is a constant (typically 60). A document ranked #1 in vector search and #3 in BM25 scores higher than a document ranked #5 in both. The beauty of RRF is that it's parameter-free in the sense that k=60 works well empirically across many domains without tuning.

```
Vector Search Results:  BM25 Results:     RRF Fusion:
1. Doc C (score: 0.95)  1. Doc A          Doc C: 1/61 + 1/62 = 0.0326
2. Doc B (score: 0.89)  2. Doc C          Doc A: 1/63 + 1/61 = 0.0322
3. Doc A (score: 0.82)  3. Doc D          Doc B: 1/62 + 1/64 = 0.0317
4. Doc D (score: 0.78)  4. Doc B          Doc D: 1/64 + 1/63 = 0.0313
```

In practice, the optimal blend depends on the query type. For a code search system where queries contain function names and syntax, weight BM25 more heavily. For a support chatbot where users describe their problem in natural language, weight vector search more. A learned hybrid (using a small model to predict the optimal alpha between BM25 and vector scores given the query) is the state-of-the-art approach used by Elasticsearch's ELSER and Vertex AI Search.

### Q4: What is the latency budget for a production RAG query pipeline, and how do you stay within it?

**Answer:** For a user-facing application, the target end-to-end latency is typically under 3-5 seconds for a complete response. For a conversational interface with streaming, users can tolerate longer generation times if they see tokens appearing progressively. The latency budget must be allocated across each stage of the query pipeline, with the LLM call typically consuming the largest share.

A realistic budget breakdown for a production RAG pipeline:
- Query embedding: 20-50ms (cached embedding model on GPU)
- Vector search: 20-100ms (depends on index size and ef setting)
- BM25 search: 10-30ms (if using Elasticsearch or Lucene-based index)
- RRF fusion + result de-dup: <5ms (in-memory, trivial)
- Reranking (cross-encoder): 100-300ms (this is often the bottleneck)
- Prompt assembly: <5ms
- LLM generation: 500ms-5s (depends on model size, output length)
- Post-processing: <20ms

The **reranker** is often the surprise latency bottleneck. Cross-encoder reranking requires running the full encoder model on (query, chunk) pairs — for 20 candidates, that's 20 forward passes. On CPU this can be 2-3 seconds; on GPU, 100-200ms. Options: run the reranker on GPU; use a smaller reranker model (e.g., `bge-reranker-base` instead of `bge-reranker-large`); reduce the candidate pool (top-10 instead of top-20); or use a bi-encoder approximation for speed with slight quality loss.

**Optimization strategies:**
- **Parallel retrieval**: Run vector search and BM25 simultaneously (they're independent); merge results after both complete. This cuts retrieval time roughly in half.
- **Caching**: Cache embedding computations for repeated queries (semantic cache keyed on query embedding); cache reranking results for (query, doc_id) pairs.
- **Index warming**: Ensure the vector index is loaded into memory before queries arrive; cold starts are 10x slower than warm queries.
- **Streaming generation**: Start streaming the LLM response to the user as soon as the first token is generated, rather than waiting for the complete response. This dramatically reduces perceived latency.
- **Progressive retrieval**: For simple queries, return top-3 results from vector search alone and skip reranking; use the full pipeline only for complex queries where a classifier detects ambiguity.

### Q5: How would you evaluate and improve a RAG system's performance after deployment?

**Answer:** RAG evaluation is a multi-layer problem, and teams that skip it end up with systems that work in demos but fail in production. I'd implement evaluation at three levels: retrieval quality, generation quality, and end-to-end task completion.

**Retrieval quality metrics** answer: "Are we finding the right chunks?" Key metrics:
- **Recall@K**: Of all relevant chunks that exist in the knowledge base, what fraction are in the top-K retrieved? Recall@5 > 0.8 is a reasonable target.
- **Precision@K**: Of the top-K retrieved chunks, what fraction are actually relevant? High precision means less noise in the LLM's context.
- **MRR (Mean Reciprocal Rank)**: For each query, what's the reciprocal of the rank of the first relevant chunk? Rewards systems that surface the best result near the top.

To compute these, you need a **golden dataset**: a set of (query, list of relevant chunk IDs) pairs curated by domain experts. Creating this dataset is expensive but essential. For a 100K document enterprise system, I'd create 200-500 golden examples covering the most common query types, then run automated evaluation on every code change.

**Generation quality metrics** answer: "Is the answer correct and grounded?" Using a framework like RAGAS:
- **Faithfulness**: Does every claim in the answer appear in the retrieved chunks? (Prevents hallucination)
- **Answer relevancy**: Does the answer actually address the question asked? (Catches tangential responses)
- **Context precision/recall**: Are the right chunks being retrieved, and are retrieved chunks being used?

**End-to-end improvement loop**: Collect production query logs with user feedback signals (thumbs up/down, re-queries as implicit dissatisfaction signal). Use disagreement cases — queries where faithfulness is low or users gave negative feedback — as the starting point for improvements. Common improvements in order of ROI: fix chunking for document types with poor recall; add BM25 for exact-match queries; add query rewriting (LLM rephrases the query before retrieval, improving recall for ambiguous queries); fine-tune the embedding model on domain-specific (query, relevant chunk) pairs.

The evaluation framework should be fully automated and run on every deployment, acting as a quality gate — don't ship a RAG update that degrades retrieval recall below your threshold.

## Key Points to Say in the Interview

- Always describe **two separate pipelines**: ingest (offline) and query (real-time)
- Name the **chunk size sweet spot** (256-512 tokens) and explain why with both directions
- Explain **why hybrid search**: BM25 for exact terms, vector for semantic meaning, RRF to fuse
- Know the **latency budget** for each stage; call out the reranker as the common bottleneck
- Mention **metadata filtering** as a way to scope retrieval (e.g., "retrieve only from 2024 documents")
- Know **golden dataset evaluation**: Recall@K, Precision@K, MRR for retrieval; faithfulness, relevancy for generation
- Parent-child chunking is an **advanced concept** that signals depth — mention it if possible

## Common Mistakes to Avoid

- Describing RAG as just "put documents in a vector database and search" — miss all the pipeline complexity
- Forgetting that **the embedding model used at ingest must be the same at query time** — any mismatch breaks the system
- Claiming pure vector search is always best — **BM25 for exact terms** is a crucial qualification
- Not mentioning **evaluation** — a RAG system without a measurement framework is not production-ready
- Ignoring **ingest pipeline maintenance** — documents change, and re-indexing strategy is a real operational concern

## Further Reading

- [RAG Survey Paper](https://arxiv.org/abs/2312.10997) — Comprehensive survey of retrieval-augmented generation techniques (2023)
- [Building RAG-based LLM Applications for Production](https://www.anyscale.com/blog/a-comprehensive-guide-for-building-rag-based-llm-applications-part-1) — Anyscale's production guide with benchmarks and tradeoffs
- [RAGAS: Automated Evaluation of RAG Pipelines](https://docs.ragas.io/en/stable/) — Official documentation for the RAGAS evaluation framework
