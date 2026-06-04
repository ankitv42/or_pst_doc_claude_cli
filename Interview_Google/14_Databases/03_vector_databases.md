# Vector Databases — The Infrastructure for Semantic Search and RAG

## What Is It? (Plain English)

A vector database is a database designed to store and search high-dimensional numerical vectors efficiently. To understand why this matters, you need to understand how modern AI represents meaning. When an embedding model processes the text "low inventory risk for Class A SKU", it produces a list of 768 numbers (a vector). Similar meanings produce similar vectors — the numbers are close in mathematical space. "Stock shortage for premium product" would produce a vector very close to the first one, even though the words are different.

Traditional databases find records by exact match: "find the row where sku_id = 'SKU-001'". They cannot answer "find the 5 most semantically similar descriptions to this query." A vector database is designed specifically for this second type of search — finding vectors that are mathematically close to a query vector, even when there is no exact match. This is called **approximate nearest neighbour (ANN)** search.

This capability powers several transformative AI applications. **RAG (Retrieval-Augmented Generation)** systems embed a knowledge base into vectors, then at query time find the relevant documents by embedding the user's question and finding the nearest document vectors — this is how AI systems can answer questions about private, up-to-date knowledge that was not in the training data. **Recommendation systems** represent users and items as vectors; finding the nearest item vectors to a user's taste vector generates personalised recommendations. **Semantic search** replaces keyword search with meaning-based search, finding relevant results even when the exact words don't match. The ORCA system uses ChromaDB as its vector database to power RAG retrieval of inventory policy documents.

## How It Works

The core operation is: given a query vector `q`, find the `k` vectors in the database that are most similar to `q` by some distance metric (typically cosine similarity or L2/Euclidean distance). For a database with 1 million vectors of dimension 768, exact nearest-neighbour search requires computing the distance from `q` to all 1 million vectors — O(n × d) operations. At a million vectors and 768 dimensions, that is 768 million multiplications per query, which takes roughly 1 second. At 100 milliseconds per query (the typical user-facing requirement), this is 10x too slow. The solution is **approximate** nearest-neighbour (ANN) indexing.

**HNSW (Hierarchical Navigable Small World)** is the dominant ANN algorithm used in production vector databases. It builds a multi-layer graph where each vector is a node. The top layer has few nodes with long-range connections ("express highways"); lower layers have more nodes with shorter connections ("local roads"). Search starts at the top layer, greedily navigates toward the query, then drops to the next layer for finer search, repeating until the bottom layer yields the final candidates.

```ascii
HNSW INDEX STRUCTURE

Layer 2 (sparse, long-range):
  A ─────────────────────────── E
  │                             │
Layer 1 (medium density):
  A ──── B ──────── D ──────── E
         │          │
Layer 0 (all nodes, dense connections):
  A ─ B ─ C ─ D ─ E ─ F ─ G ─ H
      │       │           │
      └───────┘           │
                          │
Query vector Q enters at Layer 2:
  1. Start at A (Layer 2)
  2. A's neighbour E is closer to Q → move to E
  3. Drop to Layer 1: E's neighbours D are checked
  4. Drop to Layer 0: fine-grained search near D
  5. Return top-k nearest neighbours

Trade-offs:
  ─ ef_construction (higher = better recall, slower build)
  ─ M (connections per node: higher = better recall, more memory)
  ─ ef_search (higher = better recall, slower query)

SIMILARITY METRICS:
Cosine similarity:  cos(θ) = (A·B) / (|A| × |B|)  — angle between vectors
                    Range: [-1, 1], 1 = identical direction
L2 (Euclidean):     √(Σ(Aᵢ - Bᵢ)²)  — geometric distance
                    Range: [0, ∞], 0 = identical
```

**IVF-Flat (Inverted File Index)** is an alternative that clusters vectors into groups at index build time (using k-means). At query time, it only searches the nearest cluster centroids, then examines vectors within those clusters. Faster to build than HNSW but slightly lower recall. **LSH (Locality Sensitive Hashing)** uses hash functions designed so that similar vectors hash to the same bucket with high probability — very fast but lower recall than HNSW.

Modern vector databases add critical features beyond raw ANN search: **metadata filtering** (find the 10 nearest vectors AND `category = 'policy'`), **real-time upserts** (vectors can be added/deleted without rebuilding the entire index), **namespace/collection separation** (different logical vector spaces for different use cases), and **hybrid search** (combining ANN results with BM25 keyword search using Reciprocal Rank Fusion, as used in ORCA's RAG retriever).

## Why Google Cares About This

Every Google product that uses semantic similarity — Search, Gmail Smart Compose, YouTube recommendations, Google Photos — operates on embedding vectors at billion-scale. Google has pioneered vector search research (Google's ScaNN paper and FAISS-like algorithms are widely studied). For senior AI/ML roles, vector databases represent the production infrastructure for RAG systems, which are currently one of the most commercially important AI patterns. Knowing the specific trade-offs between HNSW, IVF, filtering architectures, and the major vendor options signals genuine production experience.

## Interview Questions & Answers

### Q1: How does HNSW work and what parameters control the trade-off between speed and recall?

**Answer:** HNSW builds a multi-layer graph where vectors are nodes and edges represent "nearest neighbour" connections. The intuition comes from the "small world" phenomenon in social networks — in any social network, any two people are connected through a short chain of acquaintances (six degrees of separation). HNSW deliberately constructs this property for vectors.

During index construction, each new vector is inserted at a randomly chosen maximum layer (most vectors end up only in layer 0; a few appear in layer 1; fewer still in layer 2, etc. — following a log-normal distribution). At each layer where the vector appears, HNSW finds its nearest neighbours and creates bidirectional edges. The crucial property: higher layers have sparse, long-range connections that enable fast traversal of the space; lower layers have dense, short-range connections that enable precise final search.

At query time, search enters at the top layer with a single random entry point, greedily moves to whichever neighbour is closest to the query vector, then drops to the next layer and repeats with finer granularity. This hierarchical greedy search achieves O(log n) average time complexity — searching 1 million vectors in under 1 millisecond in RAM.

Three key parameters control HNSW's behaviour: `M` (the number of bidirectional connections per node at construction) — higher M means each node is more connected, leading to better recall but more memory (each connection takes memory) and slower construction. `ef_construction` (the size of the dynamic candidate list during index build) — higher ef_construction produces better-quality connections during index build, improving recall at query time, at the cost of slower index construction. `ef_search` (the candidate list size during query time) — higher ef_search checks more candidates before returning results, improving recall at the cost of query latency. The typical production trade-off: `M=16, ef_construction=200, ef_search=50` gives ~95% recall with queries under 5ms for millions of vectors.

### Q2: What is metadata filtering in a vector database and what are the implementation challenges?

**Answer:** In a pure ANN search, you retrieve the k vectors most similar to the query from the entire database. Metadata filtering adds the constraint that results must also satisfy a structured predicate — for example, "find the 10 most similar policy chunks where `document_type = 'reorder_policy' AND created_after = '2023-01-01'`." This is essential for RAG systems: you do not want your inventory query to retrieve HR documents; you want to limit retrieval to the relevant document types.

The implementation challenge is that HNSW and other ANN indexes are designed for pure similarity search — they do not natively support filtering. There are three main approaches, each with trade-offs. **Pre-filtering** applies the metadata filter first (using a traditional inverted index or column store), then runs ANN search only over the filtered subset. This is accurate but can be slow when the filter is highly selective (a very small subset remains, too small to navigate efficiently with HNSW). **Post-filtering** runs ANN search over all vectors first to get a large candidate set (e.g., top 1000), then applies the metadata filter to that set. Fast but inaccurate: if none of the top 1000 candidates match the filter, you return too few results. **Hybrid filtering** (used by Weaviate, Qdrant) maintains separate filterable indexes alongside the vector index, integrating filter evaluation into the graph traversal itself. This is the most accurate approach but architecturally complex.

Pinecone chose a metadata architecture where each vector has a small set of metadata fields stored in a compact side-store. Queries combine ANN search with bitmap-based filtering, which is efficient for low-cardinality filters (document type, category, date range) but less efficient for high-cardinality string filters. ChromaDB (used in ORCA) uses a simpler approach: SQLite stores metadata with traditional indexes, and post-filtering is applied to a candidate set from the vector index. For small-to-medium collections (under 1 million chunks), this works well and is what makes ChromaDB an ideal embedded database for prototyping RAG systems.

### Q3: Compare Pinecone, Weaviate, ChromaDB, and pgvector — when would you choose each?

**Answer:** These four represent different points on the complexity-control spectrum.

**Pinecone** is a fully managed, proprietary vector database-as-a-service. You never manage servers, indexes, or scaling — you just call the API to upsert and query vectors. Pinecone's HNSW implementation is production-hardened, supports real-time upserts, and scales to billions of vectors. The trade-offs: it is expensive at scale (pricing based on vector storage and query volume), data leaves your infrastructure (compliance concern for some enterprises), and you have limited control over index parameters. Best for: teams that want to ship a RAG product quickly without infrastructure expertise, or for very high query volumes where managed scaling is worth the cost.

**Weaviate** is an open-source vector database with a REST and GraphQL API, multi-modal embedding support (text, images, audio), a built-in embedding model inference layer (you send raw text; Weaviate embeds it internally), and schema-based data modelling. It runs in Kubernetes or as a managed cloud service. Weaviate's "hybrid search" natively combines BM25 and vector search. Best for: teams that want the full feature set of a production vector database with the option for self-hosting, and who are building multi-modal RAG systems.

**ChromaDB** is an open-source, embeddable vector database designed for Python development and prototyping. It runs in-process (no server needed) or as a standalone server. It uses HNSW (via `hnswlib`) for vector indexing and SQLite for metadata. The API is simple, pure Python, and integrates natively with LangChain and LlamaIndex. The ORCA system uses ChromaDB for exactly this reason — it is the simplest path to a working RAG system. The limitation: ChromaDB's performance at millions of vectors is not competitive with Pinecone or Weaviate; it is a prototyping and small-production tool.

**pgvector** is a PostgreSQL extension that adds a vector type and HNSW/IVF-Flat indexes to a regular PostgreSQL database. If you are already using PostgreSQL, pgvector lets you add vector search without a separate database. The advantage is unified data management (vectors and metadata in the same database, enabling true SQL-integrated filtering). The limitation: PostgreSQL was not designed as a vector database; at very high query volumes (millions of QPS), a dedicated vector database outperforms pgvector. Best for: teams already on PostgreSQL who need moderate-scale vector search and want to avoid operating another database.

### Q4: How does hybrid search (BM25 + vector) work and why does it outperform pure vector search for RAG?

**Answer:** Pure vector search excels at semantic similarity — finding documents that are conceptually related even without shared keywords. But it has a documented failure mode: for rare, specific terms (SKU codes like "A7-SUP-2024", technical identifiers, proper nouns), the embedding model may not have a strong semantic representation, causing relevant documents to have low cosine similarity despite being exactly what the user wants.

BM25 (Best Match 25) is a classical keyword-based ranking algorithm — an improvement over TF-IDF that accounts for document length normalisation and term saturation. It excels precisely where vector search fails: exact keyword matching, rare terms, product codes, and jargon. BM25 would score a document mentioning "A7-SUP-2024" very highly for a query containing "A7-SUP-2024", regardless of semantic similarity.

Hybrid search combines both signals. The standard fusion method is **Reciprocal Rank Fusion (RRF)**. For a query, run BM25 ranking (gives ranked list of documents by keyword relevance) and vector ANN search (gives ranked list by semantic similarity) independently. For each document, compute `RRF_score = 1/(k + rank_BM25) + 1/(k + rank_vector)` where k is a small constant (typically 60). Re-rank by combined RRF score. Documents that rank highly in both lists are elevated; documents that rank well in one but not the other get partial credit.

```
BM25 ranking:    doc_A (rank 1), doc_C (rank 3), doc_B (rank 5)
Vector ranking:  doc_B (rank 1), doc_A (rank 2), doc_D (rank 4)

RRF (k=60):
  doc_A: 1/61 + 1/62 = 0.0164 + 0.0161 = 0.0325  ← wins (top of both lists)
  doc_B: 1/65 + 1/61 = 0.0154 + 0.0164 = 0.0318
  doc_C: 1/63 + 0    = 0.0159             (only in BM25)
  doc_D: 0    + 1/64 = 0.0156             (only in vector)
```

The ORCA RAG retriever uses exactly this pattern: BM25 retrieval over the 71 policy document chunks + vector retrieval from ChromaDB, fused with RRF, then re-ranked with a cross-encoder (BAAI/bge-reranker-v2-m3). Benchmarks consistently show hybrid search improves recall@10 by 10-20% over pure vector search for domain-specific knowledge bases.

### Q5: What are the real-time upsert challenges for production vector databases and how are they solved?

**Answer:** "Real-time upsert" means adding, updating, or deleting vectors while the index remains available for queries — no downtime for index rebuilds. For RAG systems, this is critical when your knowledge base is constantly updated (new documents, updated policies, changed product information). Building or rebuilding an HNSW index from scratch takes minutes to hours for large collections; you cannot take the vector database offline every time a new document is ingested.

The core challenge: HNSW, like most ANN indexes, is an in-memory graph structure that assumes a fixed dataset during index construction. Insertions must add nodes to the graph while maintaining the small-world connectivity property. Deletions are even harder — you cannot simply remove a node from the middle of the graph without corrupting the graph structure. HNSW handles soft deletes (marking nodes as deleted without removing them from the graph; the deleted nodes are skipped in search results). Actual memory reclamation requires periodic index compaction.

Weaviate and Qdrant solve this with a "write-ahead log + segment" architecture. New vectors are written to a fast in-memory buffer (the write-ahead log). Queries search both the existing HNSW index and the buffer (using exact search for the small buffer). Periodically, the buffer is merged into the main HNSW index in a background process (index compaction). This provides real-time write visibility with near-constant query performance.

Pinecone uses a different approach: it shards the index across many nodes. Each shard handles its own HNSW subgraph. An upsert goes to the appropriate shard based on the vector ID hash; that shard updates its local HNSW graph. This horizontal sharding also provides scalability — as the collection grows, more shards are added. The distributed query fan-outs to all shards simultaneously and results are merged.

For ORCA-scale applications (71 document chunks, rarely updated), ChromaDB's simple approach of full index rebuilds on batch ingestion is perfectly adequate. For a production RAG system with thousands of documents updated hourly, the write-ahead log + segment approach (Weaviate or Qdrant self-hosted) or managed Pinecone is appropriate.

## Key Points to Say in the Interview

- Vector databases find semantically similar items by nearest-neighbour search in embedding space — exact match is not required
- HNSW is the dominant ANN algorithm: graph-based, hierarchical, O(log n) search with high recall
- Key HNSW parameters: M (graph connectivity), ef_construction (build quality), ef_search (query recall/latency trade-off)
- Metadata filtering enables SQL-like constraints alongside vector similarity search — critical for multi-tenant RAG systems
- Hybrid search (BM25 + vector + RRF fusion) outperforms pure vector search for specific terms and domain jargon
- ChromaDB for prototyping and small scale; pgvector for PostgreSQL-integrated use cases; Pinecone/Weaviate for large-scale production
- Real-time upserts use write-ahead log + index compaction — not full index rebuilds

## Common Mistakes to Avoid

- Do not conflate ANN search with exact nearest-neighbour — ANN trades perfect recall for speed; 95% recall at 1ms is far better than 100% recall at 1 second
- Do not use cosine similarity without normalising vectors first — raw L2 distance and cosine give different rankings for un-normalised embeddings
- Do not assume ChromaDB scales to billions of vectors — it is an embedded database, not a distributed system
- Do not forget that metadata filtering interacts with ANN in non-trivial ways — post-filtering can return fewer than k results
- Do not skip the cross-encoder reranking step in a production RAG system — ANN retrieves candidates; a cross-encoder re-scores for actual relevance quality

## Further Reading

- [HNSW Paper — Efficient and robust approximate nearest neighbor search](https://arxiv.org/abs/1603.09320) — The original academic paper describing the HNSW algorithm
- [ChromaDB Documentation](https://docs.trychroma.com/) — The vector database used in ORCA
- [Pinecone Documentation](https://docs.pinecone.io/) — Managed vector database; excellent documentation on metadata filtering and hybrid search
- [Weaviate Documentation](https://weaviate.io/developers/weaviate) — Open-source vector database with built-in hybrid search
- [pgvector GitHub](https://github.com/pgvector/pgvector) — PostgreSQL vector extension; useful for teams already running PostgreSQL
