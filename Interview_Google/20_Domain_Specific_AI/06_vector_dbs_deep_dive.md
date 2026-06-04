# Vector Databases: Deep Dive

## What Is It? (Plain English)

A vector database is a database optimised for storing and searching numerical vectors (arrays of floating point numbers). When an embedding model converts a sentence into a 768-dimensional vector, a vector database lets you efficiently find the 5 most similar vectors already stored — which translates to finding the 5 most semantically similar sentences. This is the technical foundation of all RAG (Retrieval-Augmented Generation) systems.

The "why not just use a regular database" question is important. In a SQL database, you can efficiently find rows where name = 'Alice' because equality checks and range queries work on indexed values. Finding the "nearest" vector requires computing the cosine similarity between your query vector and every stored vector — a linear scan that becomes impossibly slow at millions of vectors. Vector databases solve this with specialised indexing structures (most commonly HNSW — Hierarchical Navigable Small World) that make approximate nearest-neighbour search fast.

There are now dozens of vector databases to choose from, each with different trade-offs. ChromaDB is easy to set up locally and perfect for development. Pinecone is fully managed and serverless, requiring zero infrastructure work. pgvector adds vector search to PostgreSQL, avoiding a new system entirely. Qdrant is designed for high-performance production workloads. Weaviate has the richest feature set for hybrid search.

## How It Works

```
HNSW INDEX: HOW APPROXIMATE NEAREST NEIGHBOUR WORKS
═══════════════════════════════════════════════════════════════════
Think of HNSW as a multi-layer skip list for vectors.

Layer 2 (long-range connections):   A ────────────────── F
Layer 1 (medium connections):       A ─── C ─── D ─── E ─── F
Layer 0 (all nodes, short range):   A ─ B ─ C ─ D ─ E ─ F ─ G

SEARCH for vector Q (similar to E):
  1. Enter at Layer 2: find closest to Q among {A, F} → F
  2. Move to Layer 1: from F, find closest among {D, E, F} → E
  3. Move to Layer 0: from E, search neighbourhood → {D, E, F, G}
  4. Return {E, D, F} as approximate nearest neighbours

PARAMETERS:
  M            = number of connections per node (higher → better recall, more memory)
  efConstruction = search quality during construction (higher → better index, slower build)
  ef (search)   = candidates to consider during search (higher → better recall, slower query)
  
TRADE-OFF: approximate (not exact) → much faster than exact search
  Exact search: O(n) — compare query to all n vectors
  HNSW search:  O(log n) — navigate the graph

DISTANCE METRICS:
  Cosine similarity: angle between vectors (text embeddings — use this)
  L2 (Euclidean):    straight-line distance (image embeddings)
  Dot product:       magnitude × cosine (OpenAI recommends for their embeddings)
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Every Google AI product that retrieves relevant content — Search AI Overviews, Bard/Gemini, Vertex AI Search — involves vector similarity search at massive scale. A senior AI engineer is expected to understand not just "use ChromaDB" but when to use what, what HNSW parameters mean, how metadata filtering affects performance, and the trade-offs between managed and self-hosted solutions. This is also a topic where architectural decisions made early are expensive to change — choosing the wrong vector database requires reingesting all embeddings.

## Interview Questions & Answers

### Q1: Compare ChromaDB, Pinecone, pgvector, and Qdrant. How do you choose for a production RAG system?

**Answer:** The choice depends on scale, operational constraints, existing infrastructure, and the need for hybrid search.

**ChromaDB** is an embedded vector database that runs in-process (no separate server) or as a lightweight server. It is the easiest to get started with, requires zero infrastructure, and is persistent via a local directory. The limitations: it is not designed for horizontal scale, and its concurrent write performance is limited. Perfect for ORCA's use case (5 policy documents, single-server deployment on Render).

**Pinecone** is a fully managed, serverless vector database. You provision an index, insert vectors via API, and query them — no server management, no capacity planning. It scales automatically to billions of vectors. The cost: per-query pricing that adds up at high query volumes, and data residency concerns (your vectors live on Pinecone's infrastructure).

```python
# Pinecone usage
import pinecone
pc = pinecone.Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index("orca-policies")

# Upsert vectors
index.upsert(vectors=[
    {"id": "chunk_001", "values": embedding, "metadata": {"source": "policy_doc.pdf", "chunk": 0}},
])

# Query with metadata filtering
results = index.query(
    vector=query_embedding,
    top_k=5,
    filter={"access_level": {"$in": ["public", "manager"]}}
)
```

**pgvector** is a PostgreSQL extension. You add a vector column to a regular table and create an HNSW index on it. The massive advantage: your vectors live in the same database as your application data, enabling SQL JOINs between vector search results and relational data. No new system to manage. The limitation: PostgreSQL is not optimised for pure vector workloads at very large scale (>50M vectors).

```sql
-- pgvector in PostgreSQL
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(768),   -- 768-dim embedding
    access_level VARCHAR(20)
);
CREATE INDEX ON documents USING hnsw(embedding vector_cosine_ops);

-- Semantic search with SQL filtering
SELECT content, 1 - (embedding <=> '[0.1, 0.2, ...]') AS similarity
FROM documents
WHERE access_level = 'public'
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 5;
```

**Qdrant** is a Rust-based vector database focused on high performance and rich filtering. It supports filtering on any payload field before or during vector search (as opposed to filtering after retrieval), which significantly improves performance when you have many metadata categories and need filtered results quickly.

```
COMPARISON TABLE:
══════════════════════════════════════════════════════════════════════
              ChromaDB    Pinecone    pgvector     Qdrant
─────────────────────────────────────────────────────────────────────
Scale         Small-Med   Billions    Med-Large    Large
Ops burden    Very low    Zero        Low (PG)     Medium
Self-hosted   Yes         No          Yes          Yes
Hybrid search Limited     No          Limited      Excellent
SQL JOINs     No          No          Yes          No
Filtering     Basic       Good        SQL          Excellent
Cost          Free OSS    Per query   PG hosting   Free OSS
ORCA use      Current     Best SaaS   Best for     Best perf
              choice      option      PG shops     OSS
══════════════════════════════════════════════════════════════════════
```

**Decision rule:** Use pgvector if you already run PostgreSQL and have <50M vectors. Use Pinecone if you want zero ops and can accept vendor lock-in. Use Qdrant for high-performance self-hosted production with complex filtering. Use ChromaDB for development and small production deployments.

---

### Q2: Explain HNSW index parameters: M, efConstruction, and ef. How do you tune them?

**Answer:** HNSW (Hierarchical Navigable Small World) has three key parameters. Understanding them lets you reason about the trade-off between index quality, memory, and query speed.

**M** (typically 8-64) is the number of bidirectional connections each node has in the graph. Higher M means each node is connected to more other nodes. This improves recall (fewer approximate nearest neighbours are actually wrong) at the cost of more memory and longer index build time.

- M=8: minimal memory, acceptable recall for small datasets
- M=16: default for most use cases (LangChain's ChromaDB default)
- M=64: high recall, ~4x memory vs M=16, for production high-stakes retrieval

**efConstruction** (typically 100-500) controls the quality of the HNSW graph built during index construction. Higher efConstruction means more candidates are considered when placing each node in the graph, resulting in a better-connected graph and higher recall. It only affects index build time, not query time.

- efConstruction=100: fast index build, reasonable quality
- efConstruction=200: default for most cases
- efConstruction=500: high quality, slower build (run this offline if you have time)

**ef** (ef_search, typically 10-500) controls the search quality at query time. Higher ef means more candidates are explored during the traversal, which improves recall but increases latency.

- ef=10: fast queries, lower recall (~90-95% of true nearest neighbours)
- ef=50: default for most cases (good balance)
- ef=200: high recall (>99%), ~4x slower queries

```python
# Tuning in ChromaDB
collection = client.create_collection(
    name="orca_policies",
    metadata={
        "hnsw:M": 16,                # connections per node
        "hnsw:construction_ef": 200, # build quality
        "hnsw:search_ef": 100,       # query quality
        "hnsw:space": "cosine"       # distance metric
    }
)
```

**Practical tuning approach:**
1. Start with defaults (M=16, efConstruction=200, ef=50)
2. Measure recall on a validation set (compare HNSW results to brute-force exact search)
3. If recall is below target: increase M and efConstruction
4. If query latency is too high: reduce ef (or increase ef_construction during build to compensate)
5. For ORCA's 71 chunks: defaults are more than sufficient — HNSW tuning matters for 100k+ vectors

---

### Q3: What is metadata filtering in vector databases, and how does it affect query performance?

**Answer:** Metadata filtering adds a constraint on document attributes alongside the vector similarity search. For example: "find the 5 most similar documents to my query, but only among documents where `access_level = 'public' AND source = 'policy_doc.pdf'`."

Most vector databases implement filtering in one of three ways, with very different performance characteristics:

**Post-filtering (worst performance):** Retrieve top-k results from the full collection, then filter out those that don't match the metadata predicate. Simple to implement but if the filter is selective (only 1% of documents match), you may need to retrieve 500x more candidates to get 5 results that satisfy the filter. LangChain's basic ChromaDB integration uses this approach.

**Pre-filtering (not natively supported by HNSW):** Filter the document set first, then run HNSW search on the filtered subset. This requires maintaining separate indexes per filter combination — practically impossible at scale.

**During-filtering (best for production):** Qdrant and Weaviate implement this correctly. The HNSW traversal checks the metadata predicate at each step, pruning branches that cannot lead to matching results. This combines vector similarity with metadata constraints efficiently.

```python
# Metadata filtering in ChromaDB (post-filter, simple)
results = collection.query(
    query_embeddings=[query_vector],
    n_results=5,
    where={"access_level": "public"},        # filter
    where_document={"$contains": "Class A"}  # content filter
)

# Metadata filtering in Qdrant (during-filter, efficient)
from qdrant_client.models import Filter, FieldCondition, MatchValue
results = client.search(
    collection_name="orca_policies",
    query_vector=query_vector,
    query_filter=Filter(must=[
        FieldCondition(key="access_level", match=MatchValue(value="public"))
    ]),
    limit=5
)
```

For ORCA's 71-chunk collection, metadata filtering performance is irrelevant — the collection is tiny. For an enterprise knowledge base with 1 million documents and 50% of queries filtered to a specific department, the choice between post-filtering and during-filtering could be the difference between 100ms and 2 second query latency.

---

### Q4: ORCA uses ChromaDB with nomic-embed-text-v1.5. Explain this choice and when you would migrate to a different setup.

**Answer:** ORCA uses ChromaDB for three pragmatic reasons: it requires zero infrastructure (runs embedded in the same Python process), it is free, and it is well-integrated with LangChain's document processing pipeline. For a system with 71 chunks from 5 policy documents deployed on Render's free tier, these properties are exactly right.

The embedding model `nomic-ai/nomic-embed-text-v1.5` is a high-quality open-source embedding model with several advantages:
- 768-dimensional embeddings (good quality, reasonable memory)
- Supports long contexts (8192 tokens) — important for policy documents that have long sections
- Open-source and runs locally — no API calls to OpenAI for embedding
- Strong performance on retrieval benchmarks relative to its size

The fallback model `all-MiniLM-L6-v2` is faster and smaller (384 dimensions, 22MB) but lower quality. ORCA uses it as a fallback if the primary model fails to load.

**When to migrate from this setup:**

**Scale trigger (>100k chunks):** ChromaDB begins to show performance degradation at large scale. The HNSW index becomes less efficient, and ChromaDB's concurrency model becomes a bottleneck. Migration path: Qdrant (keep self-hosting, better performance) or Pinecone (fully managed).

**Team/multi-process deployment:** ChromaDB's embedded mode does not support concurrent writes from multiple processes safely. If the API server spawns multiple workers (e.g., `uvicorn --workers 4`), all writing to the same ChromaDB collection, you will get corruption. Migration path: ChromaDB's server mode, or any client-server vector database.

**Render deployment constraint:** Render's free tier has a 512 MB memory limit. Loading `nomic-embed-text-v1.5` (stored in the container) requires ~500MB of RAM, leaving very little for the rest of the application. This is why ORCA's `requirements.api.txt` excludes `sentence-transformers` — the API-only deployment does not use local embedding. For full local embedding, you need either a paid Render tier or a different deployment strategy.

**Enterprise search quality:** If retrieval quality drops below acceptable levels despite hybrid search + reranking, migrate to a provider with better query understanding (Weaviate's text2vec module, Pinecone's inference API).

---

### Q5: What is the difference between vector search, keyword search, and hybrid search? Why does ORCA use all three?

**Answer:** These three retrieval approaches have complementary strengths and weaknesses.

**Keyword search (BM25)** is the traditional information retrieval algorithm (used by Google Search until neural approaches were added). It matches exact terms and their stemmed variants, weighted by term frequency and inverse document frequency. It is extremely good when the query contains rare, specific terms that should appear verbatim in the target document. It is poor at semantic understanding — "reorder trigger" and "replenishment threshold" are the same concept but BM25 treats them as completely different.

**Vector/semantic search** finds documents by semantic similarity, regardless of the exact words used. The query "when should I rush an order?" retrieves "emergency procurement procedures" even though no words overlap, because their vector representations are close in the embedding space. It is poor at rare terms — a part number ("P/N: 4721-B") is unique but might not have a meaningful vector representation.

**Hybrid search** combines both. ORCA's retriever runs both BM25 and vector search in parallel, then fuses the result lists using Reciprocal Rank Fusion (RRF) before reranking with a cross-encoder.

```
ORCA's 3-stage hybrid retrieval:
═══════════════════════════════════════════════════════════════════
User query: "Class A SKU emergency reorder"

Stage 1: Parallel retrieval
  BM25 results:    [doc_class_a_1 (r=1), doc_emergency (r=2), doc_skus (r=3)]
  Vector results:  [doc_emergency (r=1), doc_class_a_1 (r=2), doc_policy (r=3)]

Stage 2: RRF fusion
  RRF score = Σ(1 / (k + rank_i)) for each result list
  doc_class_a_1: 1/(60+1) + 1/(60+2) = 0.0164 + 0.0161 = 0.0325
  doc_emergency:  1/(60+2) + 1/(60+1) = 0.0161 + 0.0164 = 0.0325
  doc_policy:     0 + 1/(60+3) = 0.0159
  → Fused ranking: [doc_class_a_1, doc_emergency, doc_policy]

Stage 3: Cross-encoder reranking
  Cross-encoder (BAAI/bge-reranker-v2-m3) scores each candidate
  by reading the query AND the full document text together
  → Final ranking with nuanced relevance scores
═══════════════════════════════════════════════════════════════════
```

The cross-encoder reranker is the highest quality but most expensive step — it runs a BERT-style model over every (query, document) pair. Running it over 20 retrieved candidates (BM25 top-10 + vector top-10) is feasible; running it over all 71 chunks in the collection every time would be too slow. The funnel approach (cheap parallel retrieval → moderate fusion → expensive reranking on a small candidate set) is the production-correct pattern.

## Key Points to Say in the Interview

- "HNSW is approximate nearest-neighbour: O(log n) instead of O(n), trades a small recall loss for massive speed gain."
- "M controls memory per node; efConstruction controls index quality at build time; ef controls recall/latency at query time."
- "pgvector is the right choice when you already run PostgreSQL and have <50M vectors — no new system to manage."
- "Metadata filtering performance varies: post-filter (bad for selective predicates), during-filter (Qdrant/Weaviate — best for production)."
- "ORCA's hybrid search: BM25 for keyword precision + vector for semantic recall + cross-encoder reranking for quality."
- "RRF (Reciprocal Rank Fusion) combines ranked lists from multiple retrievers without requiring score normalisation."
- "ChromaDB embedded mode is not safe for concurrent writes from multiple processes — use server mode or a different DB for multi-worker deployments."

## Common Mistakes to Avoid

- Assuming cosine similarity is always the right distance metric — use the metric your embedding model was trained with.
- Forgetting to normalise embeddings before storing them when using cosine similarity in pgvector.
- Over-indexing on benchmark performance — pick a vector DB that your team can operate, not just the fastest one.
- Using default HNSW parameters for production at large scale without testing recall.
- Not implementing metadata-level access control — every document chunk needs access metadata, and retrieval must filter by it.

## Further Reading

- [HNSW paper (Malkov & Yashunin 2018)](https://arxiv.org/abs/1603.09320) — the original HNSW algorithm paper, readable and explains the navigable small world intuition clearly
- [Weaviate vector database docs](https://weaviate.io/developers/weaviate) — excellent technical documentation on HNSW, hybrid search, and production deployment patterns
- [pgvector GitHub](https://github.com/pgvector/pgvector) — README includes performance benchmarks and HNSW tuning guidance for PostgreSQL deployments
