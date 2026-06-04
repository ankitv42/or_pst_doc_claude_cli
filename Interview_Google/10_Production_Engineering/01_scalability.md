# Scalability: Designing Systems That Grow

## What Is It? (Plain English)

Scalability is a system's ability to handle increasing load without requiring a complete redesign. A system that handles 100 users on Monday should, with the right architectural decisions, handle 100,000 users on Friday — either by buying bigger machines or by adding more machines. Systems that can't do this require expensive rewrites at exactly the moment the business is most stressed (during rapid growth), which is why scalability decisions made early in a project's life are disproportionately consequential.

The analogy is a restaurant. A food cart serves 50 customers per day — the owner cooks everything. When demand triples, they hire another cook (that's vertical scaling — making the cart "bigger" with more capacity). When demand grows 100x, the owner opens a second location (that's horizontal scaling — adding more units). The best restaurants design their kitchens so that opening a second location is straightforward: standardized recipes, trainable staff, processes that don't depend on one person knowing everything.

Software systems face identical choices. The most important design insight is that horizontal scaling (adding more servers) is almost always preferable at internet scale because it's cheaper, more flexible, and doesn't hit physical limits. But horizontal scaling only works for *stateless* services — where any server can handle any request without needing to know what the others are doing. Designing systems to be stateless is the central discipline of scalability engineering.

## How It Works

```
VERTICAL SCALING (Scale Up)
─────────────────────────────────────────────────
 Before:   [Server: 8 CPU, 32GB RAM]
            handles 1,000 req/sec

 After:    [Server: 64 CPU, 256GB RAM]
            handles 8,000 req/sec
            (but hits physical limit at some point,
             and a single point of failure)

HORIZONTAL SCALING (Scale Out)
─────────────────────────────────────────────────
 Before:   Load Balancer → [Server 1]
                        → [Server 2]

 After:    Load Balancer → [Server 1]
                        → [Server 2]
                        → [Server 3]  (added)
                        → [Server 4]  (added)
                        (add as many as needed,
                         load balancer distributes evenly)

AUTO-SCALING (Dynamic Horizontal)
─────────────────────────────────────────────────
    Low traffic (night):     2 servers
    Normal traffic (day):    4 servers
    Peak traffic (evening):  10 servers

    CPU > 70% for 5 min → add 1 server
    CPU < 30% for 10 min → remove 1 server
    (Cloud providers do this automatically)

DATABASE SHARDING
─────────────────────────────────────────────────
 Without sharding:
  All data → [One database] (bottleneck at scale)

 With sharding:
  SKUs A-F  → [Shard 1]
  SKUs G-N  → [Shard 2]
  SKUs O-Z  → [Shard 3]
  (each shard handles 1/3 the load)
```

**The CAP Theorem (brief overview, detailed in 12_Distributed_Systems):**
When a network partition occurs (servers can't talk to each other), you must choose: do you maintain **C**onsistency (all servers agree on data) or **A**vailability (every request gets a response)? You cannot have both. This is not a technology limitation — it is a mathematical proof. Every scalability decision for distributed systems operates under this constraint.

## Why Google Cares About This

Google operates at a scale no other company matches — billions of Search queries per day, petabytes of data, services spanning hundreds of countries. The engineers who designed Google's infrastructure (MapReduce, Bigtable, Spanner, Colossus) invented many of the fundamental scalability patterns that the industry uses today. In a senior interview, scalability knowledge is table stakes. They want to see that you understand *why* stateless services scale and stateful services don't, that you can identify bottlenecks, and that you understand the scalability challenges specific to AI systems (GPU costs for LLM inference, memory requirements for embedding models) on top of general compute scalability.

## Interview Questions & Answers

### Q1: What is the difference between horizontal and vertical scaling, and why is horizontal scaling generally preferred?

**Answer:** Vertical scaling means upgrading a single machine — adding more CPU cores, more RAM, or faster storage. It's simple: your application doesn't change, you just run it on bigger hardware. The appeal is that there are no distributed systems complications. A PostgreSQL database that runs on a 4-core machine will run identically on a 64-core machine without any code changes.

The problem with vertical scaling is that it has hard limits and creates single points of failure. The world's largest server has finite RAM. At some point, no single machine can handle your load — you have to distribute regardless. Furthermore, a single powerful server is a single failure point: when it crashes (and all hardware eventually crashes), 100% of your service goes down.

Horizontal scaling adds more machines of similar size and distributes load among them. It has no theoretical upper limit — you can keep adding servers. It also provides resilience: if one of 10 servers crashes, 90% of your capacity remains. The catch is that horizontal scaling only works cleanly for *stateless* services — services where any server can handle any request. If your server holds session data or in-memory state, you can't freely route users to any server, because they need to hit the server that has their state.

The practical answer is to use both but differently: vertical scale databases and stateful components (because distributing state is hard), and horizontal scale application servers and API layers (because making them stateless is usually straightforward). In AI systems, this maps to: horizontal scale the FastAPI serving layer (stateless — any server can handle any inference request), but be careful with the model weights loading (a 7B parameter model takes 2 GB of RAM — you need enough RAM on each server).

### Q2: What does it mean for a service to be "stateless" and why does it matter for scalability?

**Answer:** A service is stateless when it treats every request as completely independent, relying only on the data provided in the request (and in persistent external storage like a database) to produce a response. No information from previous requests is stored in the server's memory. A stateless server is interchangeable — any server in the pool could have handled the request equally well.

A stateful service remembers something between requests. Classic example: a web server that stores a user's shopping cart in local memory. If user Alice adds 3 items to her cart (handled by Server 1) and then checks out (routed by the load balancer to Server 2), Server 2 has no knowledge of the 3 items — they were in Server 1's memory. This is "session affinity" or "sticky sessions" — the load balancer must always route Alice back to Server 1, which destroys the flexibility of horizontal scaling.

Making a service stateless typically means moving the state out of the server's memory and into a shared external store — a database, a Redis cache, a message queue. Alice's cart moves from Server 1's RAM to Redis, where any server can read it. Now the load balancer can route Alice's checkout request to any server; they all see the same cart from Redis. The service becomes stateless and horizontally scalable.

For ORCA, the FastAPI service is designed as a stateless REST API — it receives a request, triggers the pipeline, and stores results in SQLite. HITL approval state (whether a run is waiting for human approval) is stored in the database, not in server memory. This means ORCA's API layer could be horizontally scaled tomorrow by running multiple instances behind a load balancer — the database serves as the shared state store.

### Q3: How do you scale a database when a single database becomes a bottleneck?

**Answer:** Database bottlenecks typically appear as either read overload (too many queries slowing each other down) or write overload (too many updates contending for locks). The solutions differ depending on the type.

For read overload, the first lever is **read replicas** — secondary databases that are synchronized copies of the primary, available for read queries. Writes go to the primary; reads are distributed across replicas. This works well when reads vastly outnumber writes (typical for analytics, recommendations, catalogs). A single primary can support 3–5 read replicas, multiplying read capacity. If replicas fall slightly behind the primary (replication lag), you get "eventual consistency" — reads might return slightly stale data. For most use cases (product catalog, historical analytics), a few seconds of staleness is acceptable.

For write overload, the solution is **sharding** (also called horizontal partitioning). The data is divided into partitions ("shards") based on a shard key, and each shard lives on a separate database server. If sharding by customer ID, customers 0–9,999 go to Shard 1, 10,000–19,999 to Shard 2, etc. Each shard handles a fraction of the total write load. The application must know which shard to query — a routing layer handles this. Sharding is operationally complex: rebalancing shards when load is uneven, handling queries that span multiple shards (aggregations), and ensuring no "hot shards" (shards that receive disproportionate traffic) are all engineering challenges.

For AI-specific database scaling: vector databases (Chroma, Pinecone, Qdrant) face unique scalability challenges because similarity search across millions of vectors is computationally expensive. The solution is approximate nearest neighbor (ANN) algorithms (HNSW, IVF) that trade a small amount of recall for large speed gains, and index sharding across nodes. For ORCA's ChromaDB (71 chunks), this isn't a concern — but at Google-scale RAG with billions of documents, it's a first-order engineering problem.

### Q4: What are the specific scalability challenges for AI and LLM systems that don't exist for traditional web services?

**Answer:** Traditional web services scale compute and memory linearly — double the servers, double the capacity. AI systems break this model in several important ways that require specialized solutions.

The first is **GPU contention and cost**. LLM inference requires GPU hardware that is 10–100x more expensive per unit than CPU hardware. You can't just auto-scale by adding GPU instances the way you auto-scale web servers — GPUs take minutes to allocate (not seconds), cost $3–$10 per hour (vs $0.05 for CPU), and have a minimum batch size below which they're heavily underutilized. The response to this is batching: instead of processing one LLM request at a time, accumulate multiple requests and process them as a batch through the GPU simultaneously. vLLM's continuous batching algorithm does this automatically, achieving 10–20x better GPU utilization than naive single-request processing.

The second is **memory requirements for model weights**. A Llama 3 8B model requires approximately 16 GB of GPU RAM in FP16 precision. A 70B model requires approximately 140 GB — requiring multiple GPUs. This is not elastic the way RAM is for regular services. When a new serving instance starts, it must load the model weights (10–30 seconds for large models) before it can serve traffic. Auto-scaling groups for LLMs must maintain "warm" standby instances or accept long cold-start times — neither is free.

The third is **inference latency vs throughput tradeoff**. LLMs generate tokens sequentially — each token depends on all previous tokens. This makes LLM inference inherently sequential and limits parallelism. A 100-token completion takes ~1-3 seconds regardless of GPU speed. The scaling lever is serving *more users simultaneously* (throughput) by batching, not making individual responses faster (latency). This is fundamentally different from a database query or a traditional ML inference, where throwing more hardware at it directly reduces per-request latency.

### Q5: How would you scale ORCA if it needed to handle 10,000 stock alert events per hour instead of its current scale?

**Answer:** ORCA in its current form is a single-server application where the API, pipeline execution, and database all run on one Render instance. At 10,000 events/hour (roughly 3 per second), this would saturate the system because each pipeline run takes 15–30 seconds (multiple Groq API calls). At 3 events/second, you'd need to process 45–90 pipeline runs concurrently — impossible on a single server.

The architectural change is to decouple event receipt from pipeline execution using a message queue. The API layer receives stock alert events and puts them into a queue (Redis Queue, SQS, or Kafka). Multiple worker instances subscribe to the queue and each processes one pipeline run at a time. The number of workers scales horizontally based on queue depth.

```
Stock Alert Events (10,000/hr)
         │
         ▼
┌─────────────────┐    ┌─────────────────────────────────┐
│  FastAPI API    │───►│       Message Queue (Redis/SQS)  │
│  (stateless,    │    │  [alert1][alert2][alert3]...     │
│   3 instances)  │    └──────────┬──────────────────────┘
└─────────────────┘               │
                        ┌─────────▼──────────────────┐
                        │    Worker Pool              │
                        │  [Worker 1] ── pipeline run │
                        │  [Worker 2] ── pipeline run │
                        │  [Worker 3] ── pipeline run │
                        │  [Worker N] ── auto-scaled  │
                        └─────────────────────────────┘
                                   │
                        ┌──────────▼──────────────┐
                        │  PostgreSQL (replicated)  │
                        │  (replace SQLite at scale)│
                        └──────────────────────────┘
```

Two critical migrations would be required: SQLite to PostgreSQL (SQLite can't handle concurrent writes from multiple workers), and the LangGraph MemorySaver checkpoint to a database-backed checkpoint (SqliteSaver or PostgresSaver) so HITL state survives across worker restarts. The Groq API rate limit (30 req/min on free tier) becomes the real bottleneck — the solution there is to either upgrade to paid Groq tiers or distribute requests across multiple API keys.

## Key Points to Say in the Interview

- Horizontal scaling adds more machines; vertical scaling makes one machine bigger — prefer horizontal because it's elastic and has no single point of failure
- Stateless services scale horizontally; stateful services require sticky sessions or external shared state
- Database scaling: read replicas for read load, sharding for write load — understand the tradeoffs of each
- CAP theorem: in a distributed system, when a partition occurs, choose consistency OR availability — you cannot have both
- LLM scalability challenges (GPU cost, cold start time, sequential generation) are fundamentally different from traditional compute scalability
- Auto-scaling is reactive — configure it to maintain quality-of-service thresholds (CPU%, queue depth) rather than fixed instance counts
- Queue-based decoupling is the standard architectural pattern for handling bursty workloads without blocking the API layer

## Common Mistakes to Avoid

- Do NOT say "just add more servers" without explaining that stateful services require special handling
- Do NOT confuse sharding with replication — replication copies data for redundancy and read scaling; sharding partitions data for write scaling
- Do NOT ignore the specific scalability challenges of AI systems (GPU costs, model loading time) — these differentiate a deep answer from a shallow one
- Do NOT present auto-scaling as a silver bullet — auto-scaling has a warm-up delay; traffic spikes that last only 2 minutes may not trigger a scale-out before they end
- Do NOT skip the CAP theorem — it's foundational to distributed systems and will almost certainly come up in follow-up questions

## Further Reading

- [System Design Primer on GitHub: Scalability](https://github.com/donnemartin/system-design-primer#scalability) — The most comprehensive free resource for system design interviews; covers every scaling pattern with diagrams
- [High Scalability Blog](http://highscalability.com/blog/category/example) — Real-world case studies of how companies like Twitter, Netflix, and Uber scaled their systems
- [Google: The Datacenter as a Computer (Luiz Barroso et al.)](https://research.google/pubs/the-datacenter-as-a-computer-an-introduction-to-the-design-of-warehouse-scale-machines-second-edition/) — Google's canonical paper on warehouse-scale computing; foundational for understanding how Google thinks about scale
- [ByteByteGo: Scale from Zero to Millions of Users](https://blog.bytebytego.com/p/scale-from-zero-to-millions-of-users) — Step-by-step walkthrough of scaling a system from one server to a global distributed architecture
- [AWS Auto Scaling Documentation](https://docs.aws.amazon.com/autoscaling/ec2/userguide/what-is-amazon-ec2-auto-scaling.html) — Practical reference for configuring auto-scaling with real-world policies and cooldown periods
