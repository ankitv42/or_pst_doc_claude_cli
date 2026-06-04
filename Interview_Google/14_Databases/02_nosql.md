# NoSQL Databases — When Relational Isn't the Right Fit

## What Is It? (Plain English)

NoSQL (Not Only SQL) is an umbrella term for databases that do not use the traditional relational table model. They were born out of the scaling challenges that emerged when internet companies (Google, Amazon, Facebook) needed to store and query data at scales that were impractical with relational databases of the 2000s. When you have billions of users, petabytes of data, and need sub-millisecond reads, some of the properties that make relational databases reliable (strong consistency, rigid schemas, JOIN operations) become performance bottlenecks.

NoSQL databases trade some of these guarantees for horizontal scalability, schema flexibility, and specialised performance characteristics. They come in four major flavours: **key-value stores** (Redis, DynamoDB) store arbitrary values looked up by a unique key — like a giant hash map. **Document databases** (MongoDB, Firestore) store semi-structured JSON-like documents, each potentially with different fields. **Column-family databases** (Cassandra, HBase) organise data by column groups rather than rows, optimised for write-heavy time-series. **Wide-column stores** overlap with column-family but add flexible, sparse column schemas.

Think of the trade-offs with an analogy. A relational database is like a well-organised filing cabinet with strict labelling rules, cross-references between folders, and a guarantee that every folder is in exactly one place. It is slower to file things (writes) but you can always find anything quickly, and you can ask complex questions spanning multiple folders (JOINs). A key-value store is like a locker room — you know your locker number, you can grab your things in milliseconds, but you cannot ask "show me all lockers with red shoes inside" without opening every locker. The right tool depends on what questions you actually need to ask.

## How It Works

```ascii
NOSQL DATABASE TYPES AND THEIR DATA MODELS

1. KEY-VALUE (Redis, DynamoDB)
   ┌──────────────┬────────────────────────────────────────────────┐
   │ Key          │ Value (any binary data)                        │
   ├──────────────┼────────────────────────────────────────────────┤
   │ session:u123 │ {"user_id": 123, "cart": [...], "ttl": 3600}  │
   │ cache:sku001 │ {"price": 29.99, "stock": 142, "ts": 1704...} │
   │ ratelimit:ip │ 47  (integer counter)                          │
   └──────────────┴────────────────────────────────────────────────┘
   Best for: caching, sessions, real-time counters, pub/sub

2. DOCUMENT (MongoDB, Firestore)
   ┌────────────────────────────────────────────────────────────────┐
   │ Document (JSON-like, flexible schema)                          │
   ├────────────────────────────────────────────────────────────────┤
   │ { "_id": "order_001",                                          │
   │   "customer": { "id": "C123", "name": "Acme Corp" },          │
   │   "items": [                                                   │
   │     {"sku": "SKU-001", "qty": 50, "price": 29.99},            │
   │     {"sku": "SKU-007", "qty": 10, "price": 199.99}            │
   │   ],                                                           │
   │   "status": "pending_approval",                                │
   │   "ai_recommendation": { "agent": "orca", "score": 0.87 }     │
   │ }                                                              │
   └────────────────────────────────────────────────────────────────┘
   Best for: catalogs, content management, AI output storage, events

3. COLUMN-FAMILY (Cassandra, HBase)
   ┌────────────────────────────────────────────────────────────────┐
   │ Row Key      │ Column Family: metrics          │               │
   │──────────────────────────────────────────────────────────────  │
   │ SKU001:2024  │ jan:142 │ feb:167 │ mar:201 │ ...              │
   │ SKU002:2024  │ jan:88  │ feb:91  │         │ (sparse ok)      │
   └────────────────────────────────────────────────────────────────┘
   Best for: time-series data, IoT sensor data, audit logs

4. GRAPH (Neo4j) — covered in 04_graph_databases.md
```

The defining characteristic of most NoSQL databases is that they sacrifice **consistency** for **availability and partition tolerance** (the CAP theorem). In a distributed NoSQL database, when a network partition occurs (nodes cannot communicate), the system must choose: either refuse reads/writes (maintain consistency, lose availability) or continue serving requests with potentially stale data (maintain availability, lose consistency). Most NoSQL systems choose availability, meaning you might read a value that is milliseconds behind the latest write — "eventual consistency."

Redis specifically is an in-memory key-value store with optional persistence. It keeps all data in RAM (for microsecond latency) and periodically writes to disk for durability. Redis supports rich data structures beyond simple strings: lists, sets, sorted sets, hashes, and streams. Its sorted set data structure makes it perfect for leaderboards and priority queues. Redis pub/sub enables real-time message broadcasting.

## Why Google Cares About This

Google built Bigtable (a column-family NoSQL database) in 2004 to index the entire web — a scale impossible with relational databases of that era. Google's Firestore (document store) powers millions of applications on Firebase. Google's Cloud Spanner is a globally distributed relational database that achieves ACID guarantees at NoSQL scale (a major engineering achievement). For senior AI/ML roles, Google expects you to understand when NoSQL is the right tool and why — specifically for AI system metadata, real-time feature serving, and caching ML inference results.

## Interview Questions & Answers

### Q1: When would you choose a NoSQL database over a SQL database for an AI system?

**Answer:** The decision depends on five factors: data structure, query patterns, scale requirements, consistency requirements, and team expertise. Neither is universally better — the right answer is almost always "it depends on the specific access patterns."

Choose NoSQL when: (1) **Data is schema-flexible or hierarchical** — AI model output (JSON with varying fields), user-generated content, or event logs where each event has different attributes. Trying to store LLM agent outputs in a relational schema requires either a wide table with hundreds of nullable columns or a complex polymorphic design. A document store stores each agent output as a JSON document naturally. (2) **Extremely high write throughput** — IoT sensor data from 10,000 stores each sending inventory readings every minute (10,000 writes/second). Cassandra's distributed write design handles this; PostgreSQL on a single node would saturate. (3) **Sub-millisecond caching** — inference results, user sessions, feature vectors that are queried millions of times per second. Redis in memory delivers microsecond reads; even a perfectly optimised PostgreSQL query takes 1-5ms minimum. (4) **Massive scale with simple access patterns** — DynamoDB can handle trillions of items and millions of requests per second, but only for key-based lookups (no JOINs).

Choose SQL (relational) when: data has complex relationships requiring JOINs across multiple entities, transactions span multiple records and must be atomic, the schema is stable and well-defined, or you need ad-hoc analytical queries over historical data.

For the ORCA inventory system, a hybrid approach is natural: SQLite/PostgreSQL for the core operational data (inventory levels, orders, audit trails) where ACID and JOINs matter, Redis for caching frequently-read reference data (SKU metadata, store lists) and for real-time alert queues, and possibly a document store for storing the full JSON outputs of AI pipeline runs for easy retrieval without a rigid schema.

### Q2: What is the CAP theorem and how does it affect choosing a database for an AI application?

**Answer:** The CAP theorem, proven by Eric Brewer, states that a distributed data system can provide at most two of three guarantees simultaneously: **Consistency** (every read receives the most recent write or an error), **Availability** (every request receives a response — though it might not be the most recent data), and **Partition Tolerance** (the system continues to operate despite network partitions where nodes cannot communicate).

In practice, network partitions are a fact of life in distributed systems — your data center will eventually have a network hiccup. This means partition tolerance is non-negotiable. The real trade-off is always between consistency and availability: during a partition, do you refuse requests (preserve consistency) or serve potentially stale data (preserve availability)?

**CP systems** (Consistent, Partition-tolerant): HBase, Zookeeper, and in some configurations MongoDB. During a partition, they refuse to serve reads/writes rather than risk serving stale data. Appropriate for financial systems, inventory counts where showing incorrect stock levels would cause over-selling.

**AP systems** (Available, Partition-tolerant): Cassandra, DynamoDB (in default configuration), CouchDB. During a partition, they continue serving requests but might return data that is seconds old. "Eventually consistent" — all nodes will converge to the same value once the partition heals. Appropriate for social media feeds, recommendation data, real-time analytics where slight staleness is acceptable.

For AI applications, the practical implications: a feature store serving real-time ML features should be an AP system (Redis/Cassandra) — a slightly stale feature value is acceptable; refusing to serve a prediction is not. An experiment metadata store (tracking training runs, hyperparameters, results) should be CP (PostgreSQL/MySQL) — you need to know exactly what parameters produced which result; an inconsistent read could cause incorrect conclusions about model comparisons. An inference result cache can be AP — showing a cached result from 5 seconds ago is fine.

### Q3: Explain Redis data structures and how they enable common AI system patterns.

**Answer:** Redis is far more than a simple key-value store. It provides several data structures, each enabling specific patterns at in-memory speed.

**Strings** are the basic building block — any binary data up to 512 MB. Used for: caching serialised JSON (inference results, feature vectors), atomic counters (`INCR rate_limit:user:123`), distributed locks (`SET lock:job-001 "locked" NX EX 60` — set only if not exists, expire in 60s). **Hashes** store a field-value map under one key, like a row in a database. Ideal for user session data or model metadata: `HSET model:llama-70b version "2.1" loaded_at "2024-01-15" accuracy "0.87"`. **Lists** are linked lists supporting push/pop from both ends — perfect for job queues: `LPUSH inference_queue '{"job_id": "j001", "input": "..."}'; BRPOP inference_queue 30` (blocking pop, wait up to 30s). **Sorted sets** maintain elements ordered by a float score — ideal for leaderboards and priority queues: `ZADD sku_risk_queue 0.95 "SKU-001" 0.72 "SKU-007"` then `ZRANGE sku_risk_queue 0 9 REV` to get the 10 highest-risk SKUs.

**Pub/Sub** enables real-time event broadcasting: an inventory monitoring service publishes `PUBLISH alerts "{'sku': 'SKU-001', 'risk': 'CRITICAL'}"`, and multiple subscriber processes (dashboard, email notifier, pipeline trigger) all receive it instantly. **Redis Streams** are a more durable pub/sub with consumer groups and acknowledgement, ideal for the alert pipeline in ORCA.

For an AI inference system, a common Redis pattern is the **read-through cache**: when a request arrives, check Redis first (`GET cache:inference:{hash(input)}`). Cache hit → return immediately. Cache miss → call the model, store result in Redis with TTL (`SET cache:inference:{hash} {result} EX 3600`), return result. For prompts with repeated identical inputs (e.g., a FAQ bot), this cache can reduce actual LLM calls by 60-80%.

### Q4: What is MongoDB and when does a document database outperform a relational database for AI workloads?

**Answer:** MongoDB stores data as BSON documents (a binary-encoded version of JSON). Each document can have a different structure — there is no enforced schema. Documents are grouped into collections (analogous to tables but without fixed columns). MongoDB supports rich querying including nested field access, array operators, and aggregation pipelines that can perform GROUP BY, JOIN-like `$lookup`, and complex transformations.

A document database outperforms relational for three AI-specific scenarios. First, **storing heterogeneous ML outputs**: an AI pipeline might produce wildly different output structures depending on the decision branch taken. Agent 1 might return `{urgent: true, lead_time_impact: "high", demand_trend: "accelerating"}` while a different run returns `{urgent: false, available_alternatives: ["SKU-002", "SKU-003"]}`. In MongoDB, both documents live in the same `pipeline_outputs` collection. In PostgreSQL, you'd need `JSONB` columns or a complex polymorphic design. MongoDB's query language natively handles deeply nested JSON queries.

Second, **content management and product catalogues**: a retailer's product catalogue has wildly varying attributes (a shirt has size/colour/material; a laptop has CPU/RAM/screen-size; a book has author/ISBN/pages). Storing this in a relational table requires either a "vertical" design (one row per attribute — very slow to reconstruct a product) or hundreds of nullable columns (wasteful). In MongoDB, each product is a document with exactly its own attributes.

Third, **event sourcing and activity logs**: ML pipeline execution events, user interaction logs, and model prediction logs are naturally document-shaped (each event has different fields) and write-heavy (billions of events per day). MongoDB's sharding capability distributes collections across many servers automatically, enabling horizontal scaling of write throughput.

The limitation to be clear about: MongoDB is not good at JOINs. If your queries frequently need to combine data from multiple collections (the `$lookup` operator is expensive), PostgreSQL with JSONB often outperforms MongoDB. The design principle: if you can retrieve complete entities in a single document lookup and do not need cross-document joins at query time, MongoDB excels. If your queries span multiple entity types, relational is likely better.

### Q5: How would you design the metadata store for a production ML experiment tracking system using NoSQL?

**Answer:** ML experiment tracking has specific requirements: high write throughput (many training runs writing metrics every second), flexible schema (different experiments track different metrics), rich querying (find all runs with accuracy > 0.85 and batch_size = 128), and support for nested artefact references (model checkpoints stored in object storage). This is a natural fit for a document database with some caching.

The design: use MongoDB as the primary store with two collections. The `experiments` collection stores one document per training run: `{run_id, project, user, start_time, end_time, status, hyperparameters: {lr: 0.001, batch_size: 128, ...}, metrics: {best_val_loss: 0.24, final_accuracy: 0.87, ...}, artefacts: {model_checkpoint: "s3://bucket/run-001/epoch-50.pt", confusion_matrix: "s3://..."}`. The `metric_timeseries` collection stores one document per (run, step): `{run_id, step, timestamp, loss, accuracy, gpu_utilisation}` — the fine-grained time-series data for plotting training curves.

Index strategy: compound index on `(project, status, metrics.final_accuracy)` for the common query "best models in project X"; index on `(run_id, step)` for time-series retrieval; TTL index on `metric_timeseries` documents older than 90 days (auto-delete old granular data while keeping the summary document in `experiments`).

Add Redis as a live experiment layer: during training, write metrics to Redis (`HSET run:001:latest_metrics loss 0.24 step 5000`) for real-time dashboard display without hammering MongoDB on every step. A background job flushes Redis metrics to MongoDB every 60 seconds. This gives the dashboard sub-second metric updates (from Redis) while MongoDB stores the durable historical record.

This is essentially how MLflow, Weights & Biases, and Comet ML are architected internally — a combination of document storage for flexible experiment metadata and caching for real-time updates.

## Key Points to Say in the Interview

- NoSQL comes in four flavours: key-value (Redis), document (MongoDB), column-family (Cassandra), and graph (Neo4j)
- CAP theorem: distributed systems must choose between consistency and availability during network partitions
- Redis is in-memory — microsecond reads — ideal for caching inference results and real-time feature serving
- MongoDB's flexible schema is ideal for AI output storage where structure varies per pipeline run
- Cassandra excels at write-heavy time-series (IoT, sensor data, audit logs)
- Most production AI systems use SQL + NoSQL together — relational for operational data, NoSQL for caching and event streams
- "Eventually consistent" means all nodes converge to the same value — acceptable latency for many AI use cases

## Common Mistakes to Avoid

- Do not say "NoSQL is faster than SQL" — it depends entirely on the access pattern; a relational database with the right index beats MongoDB for the wrong workload
- Do not use MongoDB for financial transactions — without ACID guarantees, multi-document updates can leave data in inconsistent states
- Do not ignore TTL (time-to-live) for Redis caches — without expiry, the cache grows until RAM is exhausted
- Do not model NoSQL like a relational database with "JOIN" operations — if you constantly need $lookup in MongoDB, your design needs rethinking
- Do not forget that eventual consistency means reads can return stale data — document this assumption for any AI feature that uses AP databases

## Further Reading

- [Redis Documentation](https://redis.io/docs/) — Official Redis docs; start with "Data Types" for the full list of structures
- [MongoDB Architecture Guide](https://www.mongodb.com/docs/manual/core/document/) — Document model and query patterns
- [Apache Cassandra Documentation](https://cassandra.apache.org/doc/latest/) — Column-family database used for large-scale time-series
- [AWS DynamoDB Developer Guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html) — Managed key-value / document database; excellent for learning access pattern design
- [Martin Kleppmann — Designing Data-Intensive Applications](https://dataintensive.net/) — The definitive book on database trade-offs; Chapter 2 covers NoSQL comprehensively
