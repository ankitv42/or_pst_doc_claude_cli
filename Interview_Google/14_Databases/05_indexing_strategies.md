# Indexing Strategies — Making Database Queries Fast

## What Is It? (Plain English)

When a database needs to find rows matching a condition (e.g., `WHERE sku_id = 'SKU-001'`), without an index it must scan every single row in the table from beginning to end — like reading an entire book to find one sentence. A database index is a separate data structure, maintained alongside the table, that organises a copy of certain column values in a way that allows the database to jump directly to the relevant rows. It is like the index in the back of a textbook — instead of reading every page, you look up the keyword in the index and jump to the right page number.

Adding an index to the right column can transform a query from taking 30 seconds (scanning 10 million rows) to taking 0.001 seconds (following a B-tree to the exact rows). This is not an exaggeration — correct indexing is one of the highest-leverage performance improvements available to a data engineer. Many AI systems fail in production not because the model is wrong, but because the feature pipeline queries that feed the model time out after 30 seconds at scale.

The trade-off is that indexes are not free. Every time you INSERT, UPDATE, or DELETE a row, the database must also update every index on that table. A table with 10 indexes requires 10 extra write operations per row modification. For AI feature pipelines that ingest millions of rows per hour, over-indexing can make the database the bottleneck for write throughput. The art of indexing is knowing exactly which queries need to be fast, and building only the indexes that serve those queries — nothing more.

## How It Works

```ascii
B-TREE INDEX STRUCTURE (most common index type)

TABLE: inventory_snapshots (10 million rows)
sku_id column values (unsorted in table):
Row 1: SKU-501, Row 2: SKU-003, Row 3: SKU-201, Row 4: SKU-001, ...

B-TREE INDEX ON sku_id:
                    [SKU-300]
                   /         \
          [SKU-100]           [SKU-500]
          /       \           /       \
    [SKU-050] [SKU-200] [SKU-400] [SKU-700]
      / \       / \       / \       / \
[001] [040] [101] [150] [201] [350] [501] [650]
 ↑     ↑     ↑     ↑     ↑     ↑     ↑     ↑
Leaf nodes contain: index_value → row_pointer(s) to table

QUERY: SELECT * FROM inventory_snapshots WHERE sku_id = 'SKU-001'
WITHOUT INDEX: Scan all 10M rows → 10M comparisons → ~10 seconds
WITH B-TREE:   Traverse 3-4 tree levels → ~3 comparisons → <1ms

B-TREE SUPPORTS:
  ✓ Equality:   WHERE sku_id = 'SKU-001'
  ✓ Range:      WHERE quantity < 10
  ✓ ORDER BY:   ORDER BY sku_id (no separate sort needed)
  ✓ LIKE with prefix: WHERE name LIKE 'SKU%'
  ✗ LIKE with wildcard prefix: WHERE name LIKE '%pen'

COMPOSITE INDEX ON (sku_id, snapshot_ts):
  INDEX KEY ORDER matters!
  Can speed up: WHERE sku_id = 'X' AND snapshot_ts > '2024-01-01'
  Cannot skip:  WHERE snapshot_ts > '2024-01-01' (no sku_id filter)
  Rule: leading column must be in WHERE clause
```

**B-tree indexes** are ordered trees. Each leaf node stores index values sorted in order, with pointers to the corresponding table rows. Equality lookups, range scans, and ORDER BY all benefit. B-trees are the default index type in PostgreSQL, MySQL, SQLite, and most relational databases.

**Hash indexes** store a hash table mapping hash(value) → row pointer. Equality lookups are O(1) — faster than B-tree for pure equality searches. But hash indexes cannot do range queries (values are not ordered in a hash table), and PostgreSQL's hash index does not support concurrent operations as efficiently as B-tree. In practice, B-tree is preferred for most use cases.

**Composite indexes** cover multiple columns in a specified order. The order matters enormously: a composite index on `(sku_id, snapshot_ts)` can speed up queries that filter on `sku_id` alone OR on both `(sku_id, snapshot_ts)`. It cannot speed up queries that filter on `snapshot_ts` alone without `sku_id`. The leftmost column in the index is the "leading column" and must appear in the query's WHERE clause for the index to be used.

**Covering indexes** include all columns that a query needs, so the database can answer the query entirely from the index without ever touching the main table (called an "index-only scan"). This is the highest-performance index pattern.

**Index selectivity** measures how many unique values the index has. A column with high selectivity (e.g., `sku_id` — every row is different) is an excellent index candidate: the index quickly narrows to a tiny set of rows. A column with low selectivity (e.g., a boolean `is_active` with 99% TRUE) is a poor index candidate: the index narrows to 99% of rows, giving almost no benefit over a table scan. The database query planner may choose to ignore a low-selectivity index and do a full scan instead.

## Why Google Cares About This

Google's systems handle thousands to millions of queries per second against databases with billions to trillions of rows. Correct indexing is the difference between a query running in 1ms and running in 30s — at Google's scale, that 30,000x difference determines whether a product is viable. BigQuery (Google's SQL analytics platform) uses columnar storage and zone-map "indexing" rather than traditional B-trees — understanding why shows deep knowledge of how storage format and access pattern interact. For senior AI/ML roles, indexing questions come up in the context of feature stores, model evaluation pipelines, and production serving databases.

## Interview Questions & Answers

### Q1: How does a B-tree index work and why does it make range queries fast?

**Answer:** A B-tree (Balanced Tree) is a self-balancing search tree where all leaf nodes are at the same depth, ensuring O(log n) lookup time regardless of which value you search for. Internal nodes store separator keys that guide the search direction (left subtree has smaller values, right has larger values). Leaf nodes store the actual index entries: the indexed value plus a pointer to the row in the table (a "row pointer" or "heap tuple ID").

The balanced property means the tree height grows logarithmically: a B-tree over 1 million rows is at most 20 levels deep (log₂(1,000,000) ≈ 20), so any lookup requires at most 20 node accesses. In practice, the top levels of the B-tree are kept in the database's memory buffer pool, making most lookups 2-4 disk reads.

Range queries benefit for a crucial reason: B-tree leaf nodes are stored in sorted order and are linked together in a doubly-linked list. Once the B-tree finds the first leaf entry matching `quantity < 10`, it simply walks along the linked list of leaf nodes (all of which are in sorted order) until it finds a quantity ≥ 10. No further tree traversal is needed. This is called a "range scan" — finding the start point in O(log n) and then doing a sequential scan of the relevant portion. For time-series data like inventory snapshots, a range scan on `snapshot_ts` between two dates is extremely fast with a B-tree index.

The write cost: every INSERT or UPDATE that touches the indexed column must also update the B-tree — finding the right position and inserting a new entry. If the leaf node is full, a "page split" occurs: the leaf node is split into two, and the parent node must be updated too. Page splits can cascade up the tree (though rarely). For write-heavy workloads like real-time IoT inventory data ingestion, having many B-tree indexes on a table adds measurable write overhead.

### Q2: What is a composite index and how does the "leftmost prefix" rule affect query planning?

**Answer:** A composite (or multi-column) index stores entries sorted by the first column, then within each group of equal first-column values, sorted by the second column, and so on. When PostgreSQL decides whether to use an index for a query, it evaluates whether the query's filter conditions match the "leftmost prefix" of the index column list.

Consider an index on `(sku_id, snapshot_ts, store_id)`. This index can be used for queries that filter on:
- `sku_id` alone: the index can locate all rows for a sku_id quickly
- `sku_id AND snapshot_ts`: the index handles both filters efficiently
- `sku_id AND snapshot_ts AND store_id`: full index use
- `sku_id AND store_id` (skipping snapshot_ts): the index can use sku_id to narrow the search, but cannot use store_id as a range (skipping middle columns breaks the sort order)
- `snapshot_ts` alone: cannot use this index at all (first column is sku_id, not snapshot_ts)
- `store_id` alone: cannot use this index at all

This is the "leftmost prefix rule." A practical consequence: if you have two queries — `WHERE sku_id = X` and `WHERE sku_id = X AND snapshot_ts > Y` — you need only one index `(sku_id, snapshot_ts)` to serve both. If you also have a query `WHERE snapshot_ts > Y` (without sku_id), you need a separate index on `(snapshot_ts)` because the composite index cannot help.

For the ORCA inventory system, the ideal composite index for the "fetch recent history for a SKU" query is `CREATE INDEX ON inventory_snapshots (sku_id, snapshot_ts DESC)`. The `DESC` order matches the typical query order (most recent first), potentially allowing an index-only scan.

A common mistake: creating separate indexes on `(sku_id)` and `(snapshot_ts)` when a composite index on `(sku_id, snapshot_ts)` would serve both columns in combination queries. The composite index is typically more efficient for combined-column queries than the database performing a "bitmap AND" of two separate index scans.

### Q3: What is index bloat and how do you detect and fix it?

**Answer:** Index bloat is the gradual accumulation of dead (logically deleted) entries in an index, causing the index to consume more disk space and memory than necessary and slow down scans. It occurs because most databases (PostgreSQL, SQL Server) do not immediately reclaim space from deleted rows — they mark rows as dead and reclaim space later during maintenance operations (VACUUM in PostgreSQL). In the meantime, dead index entries remain in the B-tree.

For write-heavy ML feature pipelines that constantly insert, update, and delete rows (e.g., updating feature values as new data arrives), index bloat can become severe. A table with 1 million live rows might have an index with entries for 5 million rows (4 million dead), making the index 5x larger than necessary. This means 5x more disk reads for index scans and 5x more memory usage in the buffer pool — directly impacting query performance.

Detection in PostgreSQL: `SELECT schemaname, tablename, indexname, pg_size_pretty(pg_relation_size(indexrelid)) AS index_size FROM pg_stat_user_indexes ORDER BY pg_relation_size(indexrelid) DESC;` identifies large indexes. The `pgstattuple` extension provides detailed bloat information: `SELECT * FROM pgstatindex('inventory_snapshots_sku_id_idx')` shows the percentage of dead tuples.

Remediation: `VACUUM` reclaims dead tuples but does not compact the index (does not return space to OS). `VACUUM FULL` or `REINDEX` rebuilds the index from scratch, eliminating bloat — but requires an exclusive lock (table unavailable during rebuild, which can be hours for large tables). `REINDEX CONCURRENTLY` (PostgreSQL 12+) rebuilds without blocking reads/writes but takes longer. For production AI systems, scheduling `REINDEX CONCURRENTLY` during low-traffic windows (e.g., 2 AM Sunday) is the standard maintenance practice.

### Q4: How do you choose what to index in a new database? Walk me through the decision process.

**Answer:** The decision process starts with understanding your actual query patterns — not guessing, but measuring. Before adding any indexes, enable slow query logging (PostgreSQL: `log_min_duration_statement = 100` logs all queries over 100ms) and run the application under realistic load for 24-48 hours. Then analyse the slow query log to find which queries are the most frequent and the most expensive.

For each slow query, run `EXPLAIN ANALYZE` to see the query plan. Look for `Seq Scan` (sequential table scan) on large tables — that is the signal that an index is missing or not being used. Look for the estimated row count vs actual row count — large discrepancies indicate stale statistics (run `ANALYZE table_name` to update). Look for `Sort` operations — if the query has `ORDER BY sku_id`, an index on `sku_id` can eliminate the sort step.

Apply the decision criteria in this order: (1) **Selectivity**: only index columns with high cardinality (many unique values). A boolean column (`is_active`) rarely benefits from an index. A UUID or SKU code column always does. (2) **Query frequency**: prioritise indexes for your most frequent queries. An index that helps a query running 1,000 times/second is worth more than one that helps a query running once/day. (3) **JOIN columns**: any column that appears in a `JOIN ON` clause should almost always be indexed on both sides of the join (one is usually the primary key; the other often needs an explicit index). (4) **WHERE columns**: filter columns in the most critical queries, with selectivity consideration. (5) **Avoid over-indexing**: each index has write overhead. Stop when new indexes no longer improve measured query performance.

For the ORCA inventory system, the high-priority indexes are: `(sku_id, snapshot_ts)` for time-series lookups, `(risk_level, resolved_at)` for the active alert queue, and `(run_id)` on pipeline_runs for status polling. No index is needed on `status` (low selectivity: only a few distinct values) or on free-text description columns.

### Q5: How is indexing different in vector databases (HNSW vs IVF-Flat vs LSH) compared to relational databases?

**Answer:** Relational database indexes solve an exact-match and range-search problem on low-dimensional, discrete data. Vector database indexes solve an approximate-nearest-neighbour problem on high-dimensional, continuous data. These are fundamentally different algorithmic problems requiring fundamentally different data structures.

**HNSW (Hierarchical Navigable Small World)** is the dominant production choice (used by ChromaDB, Qdrant, Weaviate). It is an in-memory graph structure where each vector is a node and edges connect approximate nearest neighbours at multiple granularity levels. HNSW offers the best recall-to-query-speed trade-off: typically 95-99% recall in under 5ms for millions of vectors. Build time is O(n log n). Memory usage is significant (each vector stored plus graph edge pointers: approximately (4 × dimensions + M × 8) bytes per vector, where M is the connectivity parameter). HNSW is the right default unless memory is the constraint.

**IVF-Flat (Inverted File Index with Flat storage)** divides the vector space into k clusters (using k-means clustering at build time). At query time, it identifies the nearest `nprobe` cluster centroids, then searches all vectors within those clusters using exact distance computation. IVF-Flat uses less memory than HNSW (no graph structure, just cluster assignments) and can be computed on disk. Build time is O(n × k × iterations) for k-means, which is slower than HNSW for large k. The recall at low `nprobe` values is lower than HNSW, but with `nprobe = k` (search all clusters), it approaches 100% recall. IVF-Flat is appropriate when memory is limited or when the dataset is too large to build an HNSW graph.

**LSH (Locality Sensitive Hashing)** uses hash functions where similar vectors hash to the same bucket with high probability. It is the fastest to query (O(1) hash lookup) and requires no training or graph construction. The trade-off is the lowest recall of the three — LSH produces many false negatives (similar vectors that hash to different buckets). It is appropriate for extremely large-scale applications where recall can be sacrificed for speed (billions of vectors, query time under 0.1ms requirement), or as a first-pass filter before a more accurate re-ranking step.

The analogy to relational indexing: HNSW is like a B-tree (high recall, sorted structure, good for most workloads), IVF-Flat is like an inverted index (groups similar things together, memory-efficient), and LSH is like a hash index (blazing fast equality-style lookup, poor range/approximate performance).

## Key Points to Say in the Interview

- B-tree indexes enable O(log n) lookup for equality and range queries; leaf nodes are linked for efficient range scans
- Composite index "leftmost prefix rule" — only leading columns in a composite index can anchor a query
- Index selectivity determines usefulness — high-cardinality columns (IDs, timestamps) benefit most from B-tree indexes
- Every index adds write overhead — index only columns that serve your most frequent, most critical read queries
- Index bloat accumulates in write-heavy systems — schedule `REINDEX CONCURRENTLY` during maintenance windows
- `EXPLAIN ANALYZE` is the essential tool for understanding query plans and confirming index usage
- HNSW is the standard vector index for production RAG systems; IVF-Flat trades recall for memory efficiency; LSH trades recall for query speed

## Common Mistakes to Avoid

- Do not index low-selectivity columns like boolean flags — the query planner will prefer a table scan anyway
- Do not create indexes "defensively" on every column — write performance degradation is real and measurable
- Do not forget to `ANALYZE` after bulk loads — stale statistics cause the query planner to choose wrong query plans, ignoring good indexes
- Do not assume that adding an index will always be used — the query planner has a cost model and may choose a different strategy
- Do not use hash indexes for range queries in vector databases — approximate nearest-neighbour search requires index structures that understand distance, not just equality

## Further Reading

- [Use the Index, Luke — B-Tree Fundamentals](https://use-the-index-luke.com/sql/anatomy/the-tree) — The best visual explanation of B-tree index structure
- [PostgreSQL Index Types](https://www.postgresql.org/docs/current/indexes-types.html) — Official documentation covering B-tree, Hash, GIN, GiST, and BRIN index types
- [FAISS Documentation (Facebook AI Similarity Search)](https://faiss.ai/index.html) — The library underlying most vector database indexes; detailed explanations of IVF, HNSW, and LSH
- [Qdrant Vector Index Benchmarks](https://qdrant.tech/benchmarks/) — Real-world benchmarks comparing HNSW vs IVF performance
- [PostgreSQL EXPLAIN Documentation](https://www.postgresql.org/docs/current/sql-explain.html) — How to read and interpret query execution plans
