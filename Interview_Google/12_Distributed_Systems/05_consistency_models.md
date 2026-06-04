# Consistency Models

## What Is It? (Plain English)

Consistency models define the rules about what a distributed system promises when you read data after someone has written it. They are a spectrum of guarantees, ranging from "you will always see the absolute latest version of every piece of data" (strong consistency) to "you will eventually see the latest version, but we make no promises about when or in what order" (eventual consistency). Between these extremes lie several intermediate guarantees with names that describe exactly what you can and cannot rely on.

Think of a team of five colleagues sharing a Google Doc. If the document had "strong consistency," every colleague would see the same content at exactly the same millisecond — no one could see a version another colleague hasn't seen yet. In reality, Google Docs works with slightly looser guarantees: there is a brief moment (typically well under a second) where two colleagues might see slightly different versions after a rapid edit, before the system synchronises them. This is closer to "read-your-writes" consistency with near-real-time convergence.

Consistency models matter for AI systems because they determine what you can assume about the data your model reads. An inventory AI making a reorder decision reads current stock levels, current pricing, and current supplier lead times from a database. If that database provides eventual consistency, your agent might read a stock level that is 500ms stale. For most decisions, this is fine. For a decision with significant financial consequences — "should we order $500,000 of SKU-X right now?" — you want to ensure you are reading the latest, most accurate data before committing.

## How It Works

Consistency models are ordered from strongest (highest correctness guarantee, highest cost) to weakest (lowest correctness guarantee, highest performance).

```
CONSISTENCY MODEL SPECTRUM
───────────────────────────
  STRONGEST (most correct, highest cost, lowest availability)
         │
         ▼
  Linearisability (Strict Consistency)
  ─────────────────────────────────────
  Every operation appears instantaneous and atomic.
  All nodes see operations in the same total order.
  A read always returns the result of the most recent write.
  Cost: coordination on every operation; high latency.
  Examples: etcd, ZooKeeper, Google Spanner
  Use for: distributed locks, leader election, financial txns

         │
         ▼
  Sequential Consistency
  ──────────────────────
  All nodes see operations in the SAME order,
  but that order doesn't have to match real-time.
  (Like linearisability but without wall-clock ordering)
  Rarely used in practice (hard to implement efficiently)

         │
         ▼
  Causal Consistency
  ──────────────────
  Operations that are causally related are seen in order.
  Concurrent operations may be seen in different orders.
  Example: if A writes, then B reads A's write and writes,
  everyone sees A's write before B's write.
  Cost: vector clock overhead; higher latency than eventual.
  Use for: social feeds, collaborative documents

         │
         ▼
  Read-Your-Writes (Session Consistency)
  ────────────────────────────────────────
  A client always sees its OWN previous writes.
  Other clients may see stale data.
  Common in web apps: after profile update, user sees update.
  Implementation: sticky sessions, client-side write cache.

         │
         ▼
  Monotonic Reads
  ────────────────
  Once you read a value, subsequent reads never return
  an older value. Reads "move forward" in time.
  You might not see the latest, but you never go backwards.

         │
         ▼
  Monotonic Writes
  ─────────────────
  Writes from the same client are applied in order.
  Prevents: write A, write B, but B applied before A on replica.

         │
         ▼
  Eventual Consistency
  ─────────────────────
  If no new updates: all replicas will EVENTUALLY converge.
  No guarantees about timing or intermediate states.
  Reads may return stale data; different replicas may disagree.
  Cost: minimal (no coordination); maximum performance.
  Examples: Cassandra (default), DynamoDB (default), DNS
  Use for: recommendations, analytics, metrics, feeds

         ▼
  WEAKEST (most performant, lowest correctness guarantee)


STRONG vs EVENTUAL CONSISTENCY ILLUSTRATED
────────────────────────────────────────────
  Write "qty=50" to Node A at time T

  Strong consistency (Linearisable):
  T+0ms:  Node A: 50, Node B: 50, Node C: 50  ✓ (coordinated)

  Eventual consistency:
  T+0ms:  Node A: 50, Node B: 30, Node C: 30  (replication lag)
  T+5ms:  Node A: 50, Node B: 50, Node C: 30  (partial sync)
  T+12ms: Node A: 50, Node B: 50, Node C: 50  ✓ (converged)

  During those 12ms, any read on B or C returns stale data.
  For most AI workloads, 12ms staleness is acceptable.
  For a payment decision, it is not.
```

**Key concepts:**

- **Linearisability** is the strongest guarantee. Every operation has a linearisation point (a moment when it appears to take effect). All observers see a consistent history. Achieves this via quorum reads/writes and consensus protocols (Raft, Paxos).

- **Read-your-writes** is a session-level guarantee. A user who writes a value will always read back at least that value in subsequent reads. Common in web applications via sticky session routing or client-side caching.

- **Causal consistency** tracks which operations "caused" which others using vector clocks or logical timestamps. A reply to a social media post is causally dependent on the original post — causal consistency ensures you never see the reply without the original post.

- **Monotonic reads** prevent "time travel" — once you have seen a value at version V, you will never see an older version in subsequent reads, even if load balancing routes you to a less-updated replica.

## Why Google Cares About This

Google has built systems spanning all points of the consistency spectrum: Bigtable and Spanner for CP/strongly consistent workloads, Firestore and Datastore with tunable consistency, and YouTube/Search caches with eventual consistency. Senior engineers must be able to reason about the consistency model appropriate for each layer of their system, articulate the user-visible consequences of their choice, and design application code that handles the consistency level they are actually getting — not the level they assume they are getting.

## Interview Questions & Answers

### Q1: What is the difference between linearisability and sequential consistency?

**Answer:** Both linearisability and sequential consistency are strong consistency models, but they differ in how they handle real-time ordering, and this difference has significant practical implications.

**Linearisability** (also called strict consistency or atomic consistency) requires that every operation appear to take effect instantaneously at some point between when it was invoked and when it completed, and that all observers see a total ordering of operations that respects real wall-clock time. If write W completes at time T, any read that starts after time T must see the effect of W. There is one globally consistent view of history that matches the real-time order of operations.

**Sequential consistency** relaxes the real-time requirement. Operations still appear to execute in some total order, and all processes agree on that order, but the order does not need to correspond to real-time occurrence. A write that completed at time T might be "visible" to different readers as if it occurred at different positions in the sequence, as long as all readers agree on the same sequence. This is more permissive — you can achieve sequential consistency without synchronising wall clocks across nodes — but it allows for "time-traveling" reads where the apparent order of events does not match when they physically occurred.

In practice, linearisability is what most engineers mean when they say "strong consistency." It is the guarantee provided by single-node databases (naturally linearisable — one CPU serialises all operations), and by distributed systems using Raft consensus (etcd, CockroachDB). Sequential consistency is more of a theoretical construct; very few production databases explicitly target it.

For AI systems, the distinction matters when reasoning about time-sensitive decisions. If ORCA's pipeline reads inventory data and then reads pricing data from two different services, linearisable stores guarantee that both reads reflect a consistent snapshot in time — if the inventory read returned data from time T, the pricing read will not return data from before T. Sequential consistency provides weaker guarantees here, potentially allowing the pipeline to make decisions based on inventory and pricing data from incompatible time periods.

### Q2: What is "read-your-writes" consistency and how is it typically implemented?

**Answer:** Read-your-writes (also called session consistency) guarantees that after a user writes a value, any subsequent reads by that same user will return at least the value they just wrote. Other users may still see stale data; only the writer is guaranteed to see their own writes immediately.

This is a common expectation that users have implicitly: "I just updated my shipping address, and now the order confirmation page is showing my old address" is a classic read-your-writes violation. The user wrote a new address, but the subsequent read was served by a replica that had not yet received the replication of that write.

Three implementation strategies exist. The first is **sticky session routing**: after a write, all reads by the same user session are routed to the node that accepted the write (or a node that has replicated from it). This works well when the user's subsequent reads happen quickly before they move to a different device or session. Load balancers implement this via session affinity (sticky sessions).

The second is **write acknowledgment with version token**: the write operation returns a token (a timestamp, a version number, or a session vector clock). The client includes this token on subsequent reads, and the serving node only responds if it has applied writes up to that version. If a replica is behind, it either waits (serving the read with higher latency) or forwards the read to a more up-to-date node. DynamoDB's consistent read option and Cassandra's LOCAL_QUORUM read level implement variations of this pattern.

The third is **client-side optimistic caching**: the client caches the value it just wrote locally and returns the cached value for immediate subsequent reads, bypassing the database entirely. This is simple and zero-latency but requires careful invalidation logic and does not help if the user switches devices.

For ORCA's HITL approval flow, read-your-writes consistency is essential. When a human clicks "Approve" on the dashboard, the subsequent pipeline resume operation must read that approval — not a stale state where the approval has not yet replicated to the node serving the pipeline worker. This argues for using a strongly consistent read for the approval check, even if the rest of the system uses eventual consistency.

### Q3: Why is strong consistency expensive? What are the concrete performance costs?

**Answer:** Strong consistency is expensive because it requires coordination — before any operation can complete, the system must ensure all nodes agree on the outcome. This coordination has inherent latency, and in distributed systems, latency comes from the physics of network communication and the mathematics of consensus protocols.

The fundamental cost is **round-trip time for consensus**. The Raft consensus algorithm, used by etcd and CockroachDB, requires a write to be acknowledged by a majority (quorum) of nodes before it is committed. In a 3-node cluster with nodes in different availability zones (typical for production), a write must travel from the client to the leader, from the leader to two followers, and wait for two acknowledgments — minimum 2 network round trips. In the same region, this is 2-5ms per write. Across regions (multi-region Spanner), this is 50-200ms per write.

The second cost is **read coordination**. Strong consistency requires reads to also coordinate — you cannot serve a read from a local replica without verifying that the replica has the latest data. A linearisable read must either be served from the leader (which adds routing overhead) or use a quorum read (which adds coordination overhead). Cassandra configured for QUORUM consistency has roughly 2-4x the latency of eventual consistency (ONE) reads.

The third cost is **reduced throughput**. Consensus protocols serialise operations through a leader. A 3-node Raft cluster processes all writes through a single leader — you cannot spread write load across all three nodes. The leader becomes the bottleneck for write throughput. Sharding (having multiple Raft groups, each owning a partition of the data) increases throughput but adds complexity.

The fourth cost is **availability during partitions**. As established by CAP, strong consistency requires refusing requests when a quorum cannot be reached. A network partition that isolates one of three nodes means the isolated node stops serving requests. With eventual consistency, all three nodes continue serving requests at the cost of potential staleness.

For an AI inventory system like ORCA, this analysis leads to tiered consistency: use eventual consistency for high-throughput read workloads (agent queries for demand history, supplier lookups) and reserve strong consistency for the critical path (approval writes, order commit confirmations) where the cost is justified by correctness requirements.

### Q4: What consistency model is appropriate for an AI inventory system vs a recommendations engine? Justify the difference.

**Answer:** The key question for selecting a consistency model is: what is the business cost of reading stale data, and what is the business cost of increased latency or unavailability?

For an **AI inventory management system like ORCA**, different components require different models. The reorder recommendation itself — the analysis of demand, lead times, and safety stock — can tolerate eventual consistency. If ORCA's Agent 1 reads demand history that is 500ms stale, the reorder quantity it recommends will be essentially identical to what it would recommend with perfectly fresh data. The decision horizon is weeks (lead time for restocking), not milliseconds.

However, the **approval and execution path** requires strong consistency. When Agent 4 determines an order exceeds the budget threshold and escalates to HITL, the approval record must be consistent: no double-processing, no lost approvals. The write that records "human approved order ID 12345 for $47,000" must be linearisable — when the pipeline worker reads this approval to resume execution, it must see the write. A read-your-writes guarantee (at minimum) is required; full linearisability is preferable.

For a **recommendations engine** (e.g., Netflix, YouTube, Spotify), the entire stack can operate at eventual consistency with minimal consequence. A movie recommendation being 2 seconds stale because the freshness score has not replicated to the serving node is invisible to the user. If the recommendations service is unavailable for 100ms because a CP database refused a read, the user sees a loading spinner — which is far more disruptive than serving a slightly stale recommendation. User engagement metrics justify AP over CP.

The deeper principle: CP is justified when the cost of acting on stale or inconsistent data exceeds the cost of latency and availability reduction. In financial systems, inventory commitment systems, and approval flows, this cost is high. In content recommendation, user preference personalisation, and analytics, this cost is low.

For a Google interview, I would frame this as: "I would design ORCA's approval and execution path on Cloud Spanner (strong consistency, ACID, globally distributed) and ORCA's query and analytics path on Bigtable (eventual consistency, extremely high throughput). These are both GCP products that Google makes explicit consistency commitments about, which makes the guarantees auditable and the design defensible."

### Q5: How do vector clocks work and when are they needed for causal consistency?

**Answer:** A vector clock is a data structure that tracks causal relationships between events in a distributed system. Each node maintains a vector of counters — one counter per node in the system. When a node performs an operation, it increments its own counter. When it sends a message, it includes its current vector. When it receives a message, it updates each counter to the maximum of its current value and the received value, then increments its own counter.

The result is that by comparing two events' vector clocks, you can determine their causal relationship: if event A's vector clock is element-wise ≤ event B's vector clock, then A happened-before B (A causally preceded B). If neither is element-wise ≤ the other, they are concurrent (neither caused the other).

Vector clocks are needed when you want causal consistency without paying the cost of full linearisability. Consider a social media comment thread. User A posts a message (event A). User B reads the message and replies (event B). Causal consistency requires that any user who sees B also sees A — because B's existence is causally dependent on A. Without causal tracking, a replica might serve B's reply without having replicated A's original message, creating the confusing experience of a reply with no original post visible.

Vector clocks encode this dependency. B's vector clock is strictly greater than A's in at least A's entry, because B happened after A. A system enforcing causal consistency will not serve B until it has also served all events causally prior to B (those with smaller or equal vector clocks).

Amazon DynamoDB's internal replication used a form of causal consistency tracking. Apache Cassandra supports lightweight causal consistency via compare-and-swap operations. The challenge with vector clocks is storage and computation overhead: vectors grow linearly with the number of nodes. For large clusters (hundreds of nodes), this becomes expensive. Practical systems often use dotted version vectors (a more compact encoding) or hybrid logical clocks (HLC, combining physical and logical time) to reduce overhead.

For ORCA's audit log — recording the sequence of agent decisions and the causal chain from alert to recommendation to approval — causal consistency would ensure the log always shows a coherent timeline: Agent 2's supply option is always preceded by Agent 1's demand analysis, and approval is always preceded by Agent 4's escalation decision. This makes the audit trail trustworthy for regulatory review.

## Key Points to Say in the Interview

- Consistency models are a spectrum: linearisability (strongest) → sequential → causal → read-your-writes → monotonic reads → eventual (weakest)
- Strong consistency = coordination on every operation = higher latency, lower throughput, lower availability
- Read-your-writes is the minimum bar for user-facing writes — implement via sticky sessions, version tokens, or client-side caching
- Causal consistency tracks "happened-before" relationships with vector clocks — essential for social feeds and collaborative systems
- Design ORCA's approval path on CP-tier storage (Cloud Spanner) and its analytics/query path on AP-tier storage (Bigtable, Cassandra)
- The question to ask is: "What is the business cost of reading stale data?" — this determines required consistency level

## Common Mistakes to Avoid

- Assuming your database provides stronger consistency than it does by default — Cassandra default is ONE (eventual), not QUORUM
- Applying the same consistency model to the entire system — different data has different staleness tolerance
- Conflating ACID consistency (within a database, no constraint violations) with distributed consistency (across replicas, all agree on current value)
- Ignoring read-your-writes at the application layer — even in a strongly consistent database, load balancing can violate this if not configured correctly
- Not testing for consistency violations — eventual consistency bugs are rare in normal operation but appear under load or network degradation; chaos engineering reveals them

## Further Reading

- [Martin Fowler: Eventual Consistency](https://martinfowler.com/articles/microservices.html) — Discussion of consistency tradeoffs in distributed microservices architectures
- [AWS: Consistency Models in DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html) — Concrete explanation of eventually consistent and strongly consistent reads with latency and cost implications
- [System Design Primer: Consistency Patterns](https://github.com/donnemartin/system-design-primer#consistency-patterns) — Weak, eventual, and strong consistency patterns explained with database examples for interview preparation
