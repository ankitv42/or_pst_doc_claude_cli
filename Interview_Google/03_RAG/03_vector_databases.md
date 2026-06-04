# Vector Databases

## What Is It? (Plain English)

A vector database is a specialized storage system designed to hold and search through millions of high-dimensional vectors at speed. When you embed a document into a 768-number list (a vector), you need somewhere to store it and — more importantly — somewhere that can quickly answer "which of my 10 million stored vectors is closest to this new query vector?" A regular database like Postgres can store numbers, but asking it to scan every row and compute cosine similarity for a 10M-row table would take minutes. A vector database is optimized for this exact operation and can answer in milliseconds.

Think of it like a library. A regular library stores books and lets you look them up by exact title or ISBN. A vector database is like a library with a brilliant librarian who, when you describe a book's *theme* or *plot*, instantly points you to the most relevant books — even if the exact words you used don't appear in any title. The library's organization is built around conceptual proximity, not alphabetical ordering.

The core technology inside every vector database is an Approximate Nearest Neighbor (ANN) index. Rather than checking every vector (exact search, exhaustive), ANN algorithms build a clever data structure at index time that lets you find "close enough" neighbors extremely fast — accepting a small chance of missing the absolute best match in exchange for a 1000x speedup.

## How It Works

The most widely used ANN algorithm is **HNSW** (Hierarchical Navigable Small World), which organizes vectors as a multi-layer graph.

```
HNSW Index Structure
───────────────────────────────────────────────────────
Layer 2 (few nodes, long-range connections):
    [A] ─────────────────── [E]

Layer 1 (more nodes, medium-range):
    [A] ──── [B] ──── [C] ──── [D] ──── [E]

Layer 0 (all nodes, short-range connections):
    [A]-[B]-[B2]-[C]-[C2]-[D]-[D2]-[D3]-[E]

Query: start at top layer, find approximate region,
       descend layers, refine, return top-K neighbors
───────────────────────────────────────────────────────
```

**At index build time:** Each new vector is inserted into the graph. It gets assigned to a random highest layer (most vectors live only in Layer 0). Connections are created to its nearest neighbors at each layer.

**At query time:** Start at the top layer, greedily walk toward the query vector using graph edges (fast, few nodes). Descend to Layer 1, refine. Descend to Layer 0, do a local exhaustive search among neighbors. Return top-K results. This is O(log N) versus O(N) for brute-force.

**Metadata filtering:** Real-world queries aren't just "find similar vectors" — they're "find similar vectors for documents with `category='policy'` and `date > 2023-01-01`." Vector databases support pre-filtering (apply metadata filter before ANN search) or post-filtering (apply filter to ANN results). Pre-filtering can hurt recall if the filtered set is small; post-filtering can miss relevant items if the top-K set is small. Modern systems use hybrid approaches.

## Why Google Cares About This

Google's core products — Search, Maps, YouTube recommendations, Google Photos, Vertex AI Search — all rely on large-scale vector retrieval. Understanding the ANN index tradeoffs, when approximate search is acceptable, and how metadata filtering interacts with vector search is essential for any ML Engineer role. You're expected to know not just "use Pinecone" but why specific architectural decisions (HNSW vs IVF, cosine vs dot product, filtering strategy) matter at different scales.

## Interview Questions & Answers

### Q1: Explain HNSW intuitively. Why is it preferred over brute-force or IVF for many RAG use cases?

**Answer:** Hierarchical Navigable Small World (HNSW) is inspired by the "six degrees of separation" observation in social networks — in a well-connected graph, you can reach any node from any other in a small number of hops. HNSW builds this property into a multi-layer graph structure. The top layers are sparse "highway" connections spanning large distances in vector space; the bottom layers are dense "local street" connections. When you search, you start on the highway to get close to your target, then descend to local streets for precision.

Brute-force (exact k-NN) computes the distance from the query vector to every stored vector. It's perfectly accurate but O(N) — doubling your dataset doubles your search time. With 100 million vectors, that's seconds per query, which is unacceptable for a real-time application. HNSW reduces this to roughly O(log N) search time while returning results that are 95–99% as good as exact search in practice.

IVF (Inverted File Index) is an older ANN approach that clusters vectors into buckets (like Voronoi cells) and only searches vectors in the N nearest buckets. IVF requires a training phase to learn the cluster centroids, making it less dynamic than HNSW — adding new vectors often requires periodic re-clustering. HNSW supports fully incremental insertion without re-indexing, which is critical for RAG systems where new documents are added continuously.

The practical choice: for datasets under 10M vectors where recall quality is critical and writes are frequent, HNSW is usually preferred. For datasets with 1B+ vectors where memory is the bottleneck (HNSW is memory-hungry), IVF with product quantization (IVF-PQ) or DiskANN (which spills to disk) become necessary. ORCA uses ChromaDB with its default HNSW index — entirely appropriate for a few thousand policy document chunks.

### Q2: Compare Pinecone, Weaviate, ChromaDB, and pgvector. When would you choose each?

**Answer:** These four tools occupy different positions on the complexity vs. control spectrum.

| | Pinecone | Weaviate | ChromaDB | pgvector |
|---|---|---|---|---|
| **Type** | Managed cloud | Self-hosted / cloud | Embedded / cloud | Postgres extension |
| **Setup** | API key, done | Docker or cloud | `pip install`, local | `CREATE EXTENSION` |
| **Scale** | Billions of vectors | Hundreds of millions | Millions | Tens of millions |
| **Metadata filtering** | Strong | GraphQL-based | Basic | Full SQL |
| **Cost** | Paid (free tier limited) | Open source | Open source | Open source |
| **Best for** | Production SaaS, no infra | Semantic search product | Dev/test, small prod | Existing Postgres stack |

**Pinecone** is the right choice when you need a fully managed service with guaranteed SLAs, your team cannot operate infrastructure, and your dataset is large (hundreds of millions of vectors). The operational simplicity is valuable. The downside is cost and vendor lock-in — you're paying per vector per month, and migrating away requires re-embedding and re-indexing.

**Weaviate** is a full-featured open-source vector database with its own schema system, GraphQL API, and pluggable module ecosystem (including built-in vectorization via OpenAI or Cohere API). It's appropriate when you want operational control, need to self-host for data privacy reasons, and require richer features like multi-tenancy or cross-referencing objects.

**ChromaDB** is optimized for developer experience. `pip install chromadb` and you're running a local persistent vector store in 5 lines of Python. It's perfect for prototyping, small RAG applications, and CI/test environments. ORCA uses ChromaDB because the policy document corpus is small (71 chunks), the system runs locally and on Render's free tier, and ChromaDB's simplicity fits the stack perfectly.

**pgvector** is the right choice when you already have a Postgres database and want to avoid operational complexity. Adding vector search to an existing Postgres deployment with `CREATE EXTENSION vector` is powerful — you get ACID transactions, familiar SQL joins, and can combine vector similarity with regular SQL filters in a single query. The limitation is scale: pgvector works well under ~10M vectors with proper HNSW indexing, but it's not the right choice for billion-vector workloads.

### Q3: How does metadata filtering work in a vector database, and what are the tradeoffs between pre-filtering and post-filtering?

**Answer:** In a RAG system, users rarely want to search all documents — they want to search within a subset. "Show me relevant policy documents from Q4 2023 with category='procurement'" involves both a semantic condition (vector similarity) and structured conditions (date range, category). Metadata filtering is the mechanism that combines these.

**Post-filtering** is the naive approach: run the ANN search first, retrieve the top-K vectors, then apply the metadata filter to the results. The problem is that if only 2 of the top-100 vectors match the filter, you return only 2 results even if there are 50 matching documents elsewhere in the database. With tight filters and small K values, recall collapses dramatically.

**Pre-filtering** applies the metadata filter first to narrow the candidate set, then runs ANN search within that subset only. This gives correct recall but damages ANN quality — if the filtered subset contains only 500 vectors, the HNSW graph built for 10 million vectors has few useful connections within that 500-vector region. You end up doing something close to brute-force within the subset, which defeats the purpose of ANN.

**Hybrid filtering** is what modern systems use. Weaviate uses a strategy where it estimates the filter's selectivity (what fraction of vectors it matches) and chooses between pre-filter and post-filter dynamically. Pinecone builds a separate namespace structure that allows efficient filtered search. ChromaDB applies simple post-filtering with a sufficient over-fetch factor (retrieve 10x the requested K, then filter).

For ORCA's use case, metadata filtering is used to constrain retrieval to specific policy document types — e.g., only retrieve from supplier reliability documents when Agent 2 is running. With only 71 chunks, this is trivial, but understanding the tradeoff is essential for scaling the system.

### Q4: What is the difference between cosine similarity and dot product similarity for vector search, and when does it matter?

**Answer:** Both cosine similarity and dot product are ways to measure how "similar" two vectors are, but they emphasize different things.

**Cosine similarity** measures the angle between two vectors, completely ignoring their magnitude (length). Two vectors pointing in exactly the same direction have cosine similarity of 1.0, even if one is 100x longer. This is ideal when vector magnitude is meaningless — which is true for normalized embeddings where all vectors have the same length. Cosine similarity equals dot product when both vectors are L2-normalized to unit length.

**Dot product** (inner product) measures both the angle and the magnitude. A long vector pointing in the right direction scores higher than a short vector pointing in the right direction. This is appropriate when magnitude carries information — for example, in recommendation systems where an "item popularity score" embedded as magnitude is semantically meaningful.

For most RAG embedding models, the model outputs L2-normalized vectors (or you normalize them at ingest). In this case, cosine similarity and dot product are mathematically equivalent, and the choice makes no difference. Most production systems use dot product because it's faster to compute (no division) and ANN indexes like HNSW support it natively.

Where it matters: if your embedding model does NOT normalize its outputs (some older models don't), using dot product search will favor longer vectors (often corresponding to longer documents with more content), introducing a length bias into retrieval. This can cause long documents to rank above short, more relevant ones. The fix is explicit normalization at ingest time.

Euclidean distance (L2) is a third option used less often for text embeddings. It's appropriate when the vector space was designed with Euclidean structure in mind, which is rare for transformer-based text embeddings. Stick to cosine/dot product for text.

### Q5: How is ChromaDB used in ORCA, and what would you change if the corpus grew from 71 chunks to 50 million?

**Answer:** ORCA uses ChromaDB as a lightweight embedded vector store running in-process with the FastAPI backend. The 5 policy documents are ingested via `docs/rag/ingest.py`, which chunks them, embeds each chunk with `nomic-embed-text-v1.5`, and upserts the vectors into ChromaDB's persistent local store. At query time, the `retriever.py` module queries ChromaDB for candidate chunks using vector similarity, combines these with BM25 keyword scores via RRF, and optionally reranks with a cross-encoder. Total corpus: 71 chunks. This is perfectly appropriate for the current scale.

At 50 million chunks, this architecture breaks in three ways. First, ChromaDB running as an embedded in-process store will run out of memory — 50M × 768 dims × 4 bytes = 150GB of vectors alone, far beyond any single server's RAM. Second, running ChromaDB in-process means every FastAPI worker process loads its own copy of the vectors — you'd need a shared external vector database. Third, embedding 50M chunks at ingest time requires a distributed batch embedding pipeline, not a single Python script.

The migration path: replace ChromaDB with a distributed vector database — Weaviate or Pinecone for managed, Qdrant for self-hosted with good Rust performance. Use a separate embedding service (batch jobs on GPU instances) to pre-compute vectors. Deploy the vector DB as its own service with its own horizontal scaling. Consider chunking strategy more carefully at this scale — 50M chunks suggests either a very large corpus or too-small chunks, and each direction has retrieval quality implications.

For the query path, 50M vectors with HNSW is still feasible — HNSW scales to hundreds of millions with sufficient RAM or with hybrid disk/memory approaches. But metadata filtering becomes critical at this scale because you almost certainly want to scope queries to subsets of the corpus (by document type, date, tenant, etc.).

## Key Points to Say in the Interview
- HNSW builds a multi-layer graph for O(log N) ANN search vs O(N) brute-force
- ANN accepts a small accuracy tradeoff (typically <5% recall loss) for 1000x speed gain
- Metadata filtering strategy (pre vs post vs hybrid) directly impacts recall — get it wrong and you return empty results
- ChromaDB is excellent for prototyping and small corpora; Pinecone/Weaviate/Qdrant for production at scale
- Cosine similarity and dot product are equivalent when vectors are L2-normalized (which most embedding models do by default)
- HNSW is memory-resident — at 1B vectors you need DiskANN or IVF-PQ to manage memory footprint
- pgvector is the underrated choice when you're already on Postgres and scale is modest

## Common Mistakes to Avoid
- Treating vector search as a black box and not understanding why recall can degrade (too-small K, poor metadata filtering, wrong similarity metric)
- Using chromadb in embedded mode for a multi-worker production deployment (each worker gets its own copy of the index, diverging over time)
- Not normalizing embedding vectors before using dot product search with models that don't auto-normalize
- Choosing a vector DB based on hype without checking if its filtering strategy matches your query patterns
- Ignoring the index build time cost — HNSW build is O(N log N) and can take hours at 100M+ scale

## Further Reading
- [HNSW Paper (arXiv)](https://arxiv.org/abs/1603.09320) — Original HNSW algorithm paper by Malkov and Yashunin
- [Pinecone Vector Database Explained](https://www.pinecone.io/learn/vector-database/) — Excellent conceptual overview of ANN indexing for practitioners
- [ChromaDB Documentation](https://docs.trychroma.com/) — Official docs covering collections, embeddings, and metadata filtering
- [pgvector: Open-source vector similarity for Postgres](https://github.com/pgvector/pgvector) — When you want vector search without leaving Postgres
- [ANN Benchmarks](http://ann-benchmarks.com/) — Standardized recall vs. throughput benchmarks across all major ANN algorithms
