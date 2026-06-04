# CAP Theorem

## What Is It? (Plain English)

The CAP theorem, formulated by Eric Brewer in 2000 and later proved by Gilbert and Lynch in 2002, states that a distributed data system can provide at most two of the following three guarantees simultaneously: Consistency, Availability, and Partition tolerance. Because network partitions are an unavoidable reality in any distributed system, the practical choice is always between Consistency and Availability when a partition occurs.

Consistency (in CAP) means every read receives the most recent write or an error. If you write a value on Node 1 and immediately read it on Node 2, you get the updated value. Think of a single banking ledger: every teller always sees the same current balance, and no teller can tell a customer the wrong balance.

Availability means every request receives a response (not an error), though that response may not be the most recent data. The system keeps serving requests even if some nodes are unreachable. Think of a flight status board: it always shows something, even if the information is a few minutes stale. You get an answer, not an error.

Partition tolerance means the system continues to operate even when some messages between nodes are lost or delayed. A "partition" is a network split: Node A and Node B cannot communicate. In any real distributed system deployed across datacenters, across racks, or even within a single datacenter, partitions will eventually happen. They are not hypothetical.

## How It Works

```
THE CAP TRIANGLE
─────────────────
               Consistency
              ╱(C)╲
             ╱     ╲
            ╱  CA   ╲
           ╱─────────╲
          ╱ CP    AP  ╲
         ╱             ╲
(P)Partition ─────── Availability(A)

  CA: Consistent + Available, no partition tolerance
      → Only possible in single-node or LAN systems
      → Traditional RDBMS on a single server
      → Not viable for distributed internet-scale systems

  CP: Consistent + Partition tolerant, sacrifices availability
      → Returns error/timeout rather than stale data
      → Examples: etcd, ZooKeeper, HBase, Google Spanner*
      → Use for: config stores, leader election, financial txns

  AP: Available + Partition tolerant, sacrifices consistency
      → Returns stale data rather than an error
      → Examples: Cassandra, DynamoDB, CouchDB, DNS
      → Use for: recommendation engines, social feeds, caches


WHAT HAPPENS DURING A PARTITION?
──────────────────────────────────

  Normal operation:
  ┌─────────┐           ┌─────────┐
  │  Node A │◄─────────►│  Node B │
  │ qty: 50 │  in sync  │ qty: 50 │
  └─────────┘           └─────────┘

  Partition occurs (network cut):
  ┌─────────┐     ✗     ┌─────────┐
  │  Node A │   lost    │  Node B │
  │ qty: 50 │  network  │ qty: 50 │
  └─────────┘           └─────────┘
       │                      │
  Write arrives:          Read arrives:
  qty = 30               "What is qty?"

  CP choice: Refuse the write on A OR return error on B's read.
             Never serve inconsistent data. Availability suffers.

  AP choice: Accept write on A (qty=30). B returns 50.
             Data is inconsistent. Consistency suffers.
             B will eventually sync when partition heals.


PACELC MODEL (Extends CAP)
───────────────────────────
  CAP only describes behavior during partitions.
  PACELC adds: even during normal operation (no partition),
  you must choose between Latency and Consistency.

  PA/EL: Cassandra — partition: AP, normal: low latency
  PC/EC: etcd — partition: CP, normal: strong consistency
  PA/EC: DynamoDB — partition: AP, normal: strong consistency
         (via conditional writes, at higher latency)

  Most real systems live in the PACELC space, not just CAP.
```

**CP systems** sacrifice availability during partitions — they return errors or timeouts rather than serving potentially stale data. Examples:
- **etcd**: key-value store used for Kubernetes config; returns errors rather than stale config
- **ZooKeeper**: distributed coordination service for leader election; must be consistent
- **Apache HBase**: strongly consistent row-level operations on HDFS
- **Google Spanner**: uses TrueTime (atomic clocks) to achieve external consistency — often described as "CA" but technically CP with extremely short partition duration

**AP systems** sacrifice consistency during partitions — they keep serving requests but may return stale data. Examples:
- **Apache Cassandra**: "write to any node, eventually consistent"; tunable consistency levels
- **Amazon DynamoDB**: eventually consistent by default; strongly consistent reads available at higher cost
- **DNS**: highly available, eventually consistent by design
- **CDN caches**: serve potentially stale content while the origin is unreachable

## Why Google Cares About This

Google operates globally distributed systems where network partitions are not theoretical but regularly occurring events. Google Spanner (globally consistent distributed SQL) and Bigtable (AP, high throughput) are canonical examples of different CAP tradeoffs made intentionally for different use cases. Senior engineers must be able to articulate which consistency guarantee their system requires and why, and explain what user-visible behaviour results from their choice. The CAP theorem is one of the most common system design interview topics at Google.

## Interview Questions & Answers

### Q1: Explain the CAP theorem. If partition tolerance is always required, is the real choice just CP vs AP?

**Answer:** Yes — for any distributed system deployed across multiple machines with real networks, the practical choice reduces to CP vs AP. Partition tolerance is not optional because network partitions are inevitable: hardware fails, cables are cut, switches misbehave, cloud provider availability zones lose connectivity. Any system that claims to sacrifice partition tolerance is either running on a single node (not distributed) or is planning to fail during the next network incident.

Given that P is required, the theorem narrows to a binary choice during a partition: do you prioritise Consistency or Availability? This is not a permanent system-wide decision but a policy applied at the moment a partition occurs. A CP system detects the partition and refuses to serve requests (or serves errors) on isolated nodes rather than risk serving stale data. An AP system continues serving requests on isolated nodes, accepting that some reads may return stale data until the partition heals and nodes re-synchronise.

The subtlety that many candidates miss is that this choice has user-visible consequences. A CP system's "availability sacrifice" means users see 503 errors during a partition. An AP system's "consistency sacrifice" means two users may see different values for the same data simultaneously. Which is less bad depends entirely on the application. For a banking transaction ("is there enough balance to authorise this payment?"), serving stale data that approves an invalid transaction is worse than returning an error. For a social media like counter ("how many people liked this post?"), returning a slightly stale count is far preferable to returning an error — users do not care if the count is off by a few for a few seconds.

A nuance worth mentioning: CAP is a theorem about worst-case network partitions, which are infrequent. PACELC extends the model to also characterise the latency vs consistency tradeoff during normal operation, which is the dominant concern for most systems most of the time. Systems like Cassandra are high-availability and low-latency normally; the CAP behavior only manifests during actual partitions.

### Q2: Compare etcd and Cassandra from a CAP perspective. When would you use each?

**Answer:** etcd and Cassandra represent the two poles of the CP vs AP spectrum, and comparing them clearly illustrates the real-world implications of the CAP tradeoff.

etcd is a CP system. It uses the Raft consensus algorithm, which requires a quorum (majority) of nodes to agree before any write is committed or any read is served. During a network partition, if a node cannot reach a quorum, it refuses to serve requests — it returns an error rather than potentially serving stale data. etcd prioritises correctness over availability: you will never read a stale value from etcd, but you may get errors during network incidents. This makes etcd ideal for use cases where incorrect data is worse than no data: Kubernetes control plane state (pod assignments, service configurations), distributed locks, leader election, and feature flag stores. If etcd serves a stale Kubernetes node assignment, Kubernetes might schedule a pod to a node that is actually dead. Better to error out and let the operator investigate.

Cassandra is an AP system. It uses a gossip protocol for node discovery and allows writes to any node at any time, replicating to other nodes asynchronously. Reads can be served from any replica, which may not have the latest write yet. Cassandra offers tunable consistency levels (ONE, QUORUM, ALL) — you can request stronger consistency at the cost of higher latency and lower availability. During a partition, Cassandra continues serving both reads and writes on isolated nodes, accepting that those nodes' data may diverge temporarily and will reconcile when the partition heals. This makes Cassandra ideal for high-throughput, high-availability workloads where eventual consistency is acceptable: user activity feeds, session data, IoT telemetry, product recommendation scores, and time-series metrics. A slightly stale recommendation score is invisible to users; 503 errors on every profile load are not.

The decision rule: if the consequence of serving stale data is incorrect business outcomes (financial loss, safety issues, legal liability), choose CP. If the consequence of unavailability (errors, downtime) is worse than serving slightly stale data, choose AP. Most AI recommendation and analytics systems are AP workloads; most financial, configuration, and coordination systems are CP workloads.

### Q3: What is the PACELC model and why is it a more complete picture than CAP?

**Answer:** The PACELC model, proposed by Daniel Abadi in 2012, extends CAP by recognising that the CAP theorem only describes system behavior during network partitions — a relatively rare event. For most of a distributed system's lifetime, it is operating normally with no partition. During normal operation, there is still a fundamental tradeoff, but it is between Latency and Consistency, not Availability and Consistency.

PACELC reads as: "If Partition, then trade-off between Availability and Consistency; Else (normal operation), trade-off between Latency and Consistency." Every distributed system makes both decisions, and they can be made independently.

The Latency vs Consistency tradeoff during normal operation is often more consequential than the partition behavior, because normal operation is 99.9%+ of the time. Achieving strong consistency (every read returns the most recent write) in a distributed system requires coordination: before a read can return, the system must verify with other nodes that it has the latest data. This coordination adds latency. A Cassandra cluster serving reads from the local replica (no coordination) returns results in 1-2ms; serving strongly consistent reads (QUORUM) takes 5-15ms because it must wait for responses from multiple replicas.

PACELC classifications reveal more useful system characteristics. Cassandra is classified as PA/EL: partition-available, else low-latency — it optimises for availability during partitions and latency during normal operation, at the cost of consistency in both cases. etcd is PC/EC: partition-consistent, else consistent — it always prioritises consistency. DynamoDB is PA/EC: available during partitions, but eventually consistent reads are available, and strongly consistent reads (at higher cost) are supported during normal operation.

For AI system design, PACELC helps reason about feature store design. A feature store serving real-time model predictions needs sub-millisecond read latency — an EL optimisation. A feature store serving model training needs historical accuracy — an EC requirement. The same data might be served by different systems with different PACELC profiles depending on whether the consumer is online inference or offline training.

### Q4: How does the CAP theorem affect the design of an AI inventory management system like ORCA?

**Answer:** Applying CAP to ORCA requires thinking about what consistency means for each type of data the system manages, and what the business consequence of inconsistency is.

The **inventory alert data** (which SKUs are at risk, with what severity) drives the AI pipeline's reorder recommendations. The consistency requirement here is moderate: if two ORCA pipeline instances simultaneously read slightly different views of inventory levels (because of AP replication lag), they might generate slightly different recommendations. In practice, the lag in an AP system is milliseconds to seconds — well within the tolerance of an inventory system whose data reflects sensor scans from minutes ago. An AP database (Cassandra or DynamoDB) is appropriate for inventory metrics. Serving a reorder recommendation based on data that is 500ms stale is not a business problem.

The **HITL approval state** is different. When a human approves or rejects a $50,000 reorder, the system must not allow that decision to be processed twice (double-ordering) or lost. This is a CP requirement: strong consistency for the approval record, with coordination ensuring exactly one approval is processed. A CP store like Postgres (with row-level locking) or etcd (for distributed coordination) is appropriate here.

The **LangGraph pipeline checkpoint state** (used for HITL pause/resume) needs to be consistent enough that when an agent resumes after human approval, it picks up exactly where it left off. This is a CP requirement — inconsistent checkpoint state could cause the pipeline to re-execute a step, potentially placing a duplicate order. The MemorySaver checkpointer in ORCA's current implementation stores state in memory, which is consistent but not durable. A production replacement would use a CP-configured distributed key-value store.

The general pattern: CP for anything where acting on wrong data causes business harm (financial transactions, approval records, audit logs); AP for anything where the cost of unavailability exceeds the cost of brief staleness (metrics, recommendations, analytics). ORCA needs both, and the architecture should reflect that different data layers have different consistency requirements.

### Q5: What does "eventual consistency" mean in practice? How do you build systems on top of it?

**Answer:** Eventual consistency is the guarantee that, if no new updates are made to a piece of data, all replicas will eventually converge to the same value. The word "eventually" is deliberately unspecified — in practice for well-designed AP systems, it means milliseconds to seconds under normal conditions. The guarantee says nothing about how long convergence takes, which is the source of both its power and its danger.

The danger of eventual consistency is **reading your own writes**. You write a record to Node A, then immediately read from Node B (which routes your read differently due to load balancing). If the write has not yet replicated to Node B, you read stale data. This breaks user expectations: "I just updated my profile picture and it still shows the old one." Three patterns address this:

**Read-your-writes consistency**: after a write, the application routes subsequent reads by the same user to the node that accepted the write (sticky session routing), or waits for a minimum replication acknowledgment before confirming success to the user.

**Monotonic reads**: ensure that once a user reads version N of a value, subsequent reads by that user never return a version earlier than N. Even if the exact current value is not guaranteed, you do not show users data that "goes backwards."

**Causal consistency**: if operation B is causally dependent on operation A (A must have happened before B makes sense), ensure B is never visible without A. Social feeds use this: a reply to a post must never appear without the original post being visible.

Building on eventual consistency also requires thinking about **conflict resolution**. If two nodes accept conflicting writes during a partition (Cassandra allows this), how is the conflict resolved when the partition heals? Common strategies: last-write-wins (using wall clock timestamps — vulnerable to clock skew), vector clocks (causally-aware conflict detection), and application-specific merge logic (CRDTs — conflict-free replicated data types — for commutative operations like counters and sets).

For ORCA, eventual consistency means that the inventory dashboard showing 50 units might briefly show 50 on one browser tab and 45 (post-sale) on another. Designing around this means: UI polling at short intervals to converge quickly, not making critical decisions based on a single read without acknowledging potential staleness, and using CP-tier storage for the approval flow where consistency is truly required.

## Key Points to Say in the Interview

- In any real distributed system, partition tolerance is required — the real choice is CP vs AP during a partition
- CP: return errors rather than stale data (etcd, ZooKeeper, HBase, Spanner)
- AP: return stale data rather than errors (Cassandra, DynamoDB, DNS)
- PACELC extends CAP: during normal operation the tradeoff is Latency vs Consistency, which matters more than partition behavior for 99.9% of operating time
- CAP is not a system-wide binary — different data in the same system may need different consistency levels
- Eventual consistency requires designing for: read-your-writes, monotonic reads, conflict resolution
- "Which is worse: serving stale data or returning an error?" is the decision question

## Common Mistakes to Avoid

- Saying "we need strong consistency everywhere" — this ignores the latency and availability costs, and many AI workloads do not need it
- Confusing CAP Consistency with ACID Consistency — they are different concepts; CAP C is about distributed read/write recency
- Treating CAP as binary for the entire system — different tables, endpoints, and flows can have different consistency requirements
- Ignoring the PACELC latency tradeoff — consistency during normal operation matters more day-to-day than partition behavior
- Not handling eventual consistency in the application layer — read-your-writes and monotonic read violations are application bugs, not database failures

## Further Reading

- [Google: Spanner, TrueTime, and the CAP Theorem](https://cloud.google.com/spanner/docs/true-time-external-consistency) — How Spanner uses atomic clocks to push the boundaries of CAP guarantees
- [Amazon: Dynamo — Amazon's Highly Available Key-Value Store](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf) — The foundational paper on AP design at scale that influenced DynamoDB
- [System Design Primer: CAP Theorem](https://github.com/donnemartin/system-design-primer#cap-theorem) — Concise CAP overview with CP and AP database examples for interview preparation
