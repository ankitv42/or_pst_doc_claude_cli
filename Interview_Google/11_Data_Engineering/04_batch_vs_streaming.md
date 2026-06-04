# Batch vs Streaming Processing

## What Is It? (Plain English)

Batch processing and streaming processing are the two fundamental models for handling data over time. They answer the question: when does the computer work on the data? In batch processing, work accumulates until a trigger fires — at midnight, or when a file arrives, or when 10,000 records queue up — and then the system processes the entire pile at once. In streaming processing, the system processes each piece of data as it arrives, continuously, with no waiting.

The everyday analogy is a restaurant vs a fast-food counter. A restaurant batches your order: the entire table's food is prepared together and delivered at once. This allows for complex, coordinated cooking — but everyone waits. A fast-food counter streams orders: each item is prepared and handed over as soon as it is ready. The throughput is similar, but the latency for any individual item is much lower.

For AI systems, the choice matters enormously. A fraud detection system needs to decide in under 100 milliseconds whether a transaction is fraudulent — before the card reader times out. That requires streaming. A recommendation system that retrains nightly on yesterday's user behaviour can tolerate batch processing. Getting this wrong costs either money (building streaming infrastructure you do not need) or capability (batch latency where real-time decisions were required).

## How It Works

```
BATCH PROCESSING
─────────────────
 Source Data ──► Accumulate ──► Trigger ──► Process ──► Output
 (events,        (hourly,         (cron,      (Spark,     (DB,
  files,          daily,           file        Hadoop,     file,
  DB rows)        threshold)       arrival)    SQL)        table)

 Latency: minutes to hours
 Throughput: very high (optimised bulk operations)
 Complexity: low (simple sequential logic)
 Examples: nightly ETL, weekly model training, monthly billing

 Timeline:  ──────[batch]──────────────────[batch]──────►
                   00:00                   01:00

STREAMING PROCESSING
─────────────────────
 Source     Kafka    Stream         Output
 Events  ──► Topic ──► Processor ──► (DB, API,
 (real-time)  │        (Flink,        dashboard,
              │         Spark         feature store)
              │         Streaming,
              │         Kinesis)
              │
              └──► Consumer Group A (fraud detection, <100ms)
              └──► Consumer Group B (analytics, eventual)
              └──► Consumer Group C (model features, ~1s)

 Latency: milliseconds to seconds
 Throughput: moderate (per-event overhead)
 Complexity: high (windowing, late arrivals, state management)
 Examples: fraud detection, real-time recommendations, IoT alerts

 Timeline:  ──e1──e2─e3────e4──e5───e6──e7─────────────►
               (each event processed immediately)


LAMBDA ARCHITECTURE (Hybrid)
──────────────────────────────
                        ┌──► Batch Layer ──────────────┐
 Raw Data ──► Storage ──┤    (Spark, hourly/daily)      ├──► Serving Layer
  Events       (S3)     │    High accuracy, slow        │    (merged view)
                        └──► Speed Layer ───────────────┘
                             (Flink/Kafka Streams)
                             Low latency, approximate

 Problem: TWO codebases to maintain (batch + streaming logic)


KAPPA ARCHITECTURE (Modern Alternative)
─────────────────────────────────────────
 Raw Events ──► Kafka ──► Stream Processor ──► Output
  (stored        (long    (Flink, handles      (real-time
   long-term)     retention)  both real-time    + reprocessing)
                             AND reprocessing
                             by replaying Kafka)

 Benefit: ONE codebase, Kafka replay handles "batch" use cases
 Trade-off: Requires long Kafka retention + streaming expertise
```

**Key streaming concepts:**

- **Windowing**: aggregating events over a time window (last 5 minutes, last hour). Tumbling windows (non-overlapping), sliding windows (overlapping), session windows (activity-based gaps).
- **Watermarks**: the stream processor's estimate of how far behind real time it is willing to wait for late-arriving events before closing a window.
- **State**: streaming processors maintain in-memory state (e.g., "how many orders has this user made in the last hour?"). State can be lost on crashes — stream processors checkpoint state to durable storage.
- **Exactly-once semantics**: guaranteeing each event is processed exactly once even in the presence of failures. Kafka + Flink support this; it is expensive.

## Why Google Cares About This

Google processes hundreds of billions of events per day across Search, Ads, YouTube, and Maps. The internal streaming platform (Pub/Sub + Dataflow) and batch platform (BigQuery + Dataflow batch mode) are products that senior engineers both use and contribute to. Candidates must understand when to choose streaming vs batch for AI/ML workloads — feature freshness requirements, model serving latency SLAs, and infrastructure cost all depend on this decision.

## Interview Questions & Answers

### Q1: When would you use streaming processing vs batch processing for an AI/ML system?

**Answer:** The decision hinges on two questions: how quickly must the system react, and how much complexity is the team prepared to operate? Streaming is the right answer when the cost of latency exceeds the cost of complexity. Batch is the right answer when near-real-time processing is not required and the team wants lower operational overhead.

Use streaming when the use case demands sub-minute response times. Fraud detection must fire before a transaction clears — latency measured in seconds. Real-time ride-pricing (surge pricing) must respond to supply/demand shifts as they happen. Ad bidding must evaluate bid requests in under 10 milliseconds. An inventory system that needs to alert a store manager to a stockout within minutes of it happening (rather than the next morning) requires streaming.

Use batch when the use case can tolerate hourly or daily latency. Model retraining on yesterday's data is inherently batch — you cannot retrain on data that has not happened yet, and daily cadence is usually sufficient for stable models. Generating product recommendations that refresh nightly is batch. Building a data warehouse for BI reporting is batch.

The practical consideration is complexity. Streaming systems are significantly harder to build and operate than batch systems. They require understanding of windowing, late arrivals, state management, and exactly-once delivery semantics. The operational toil of managing Kafka brokers, Flink clusters, and consumer lag monitoring is real. Many organisations over-engineer into streaming when their actual latency requirement is "within 30 minutes" — which batch pipelines running every 15 minutes can satisfy at a fraction of the cost.

For ORCA, the reorder decision pipeline is currently batch: `data/scheduler.py` runs periodically to generate alerts, and the AI pipeline processes them on demand. Upgrading to streaming would make sense only if the business SLA shifted to "detect a stockout risk within 2 minutes of POS data arriving" — which would require real-time POS event streaming into Kafka and a Flink-based alert generator.

### Q2: Explain Kafka's architecture and how consumer groups work.

**Answer:** Apache Kafka is a distributed event streaming platform. At its core, Kafka is a distributed commit log: producers write events to the log, consumers read from it, and the log is retained for a configurable period (hours, days, or indefinitely) regardless of whether consumers have read it. This durability-first model is what distinguishes Kafka from traditional message queues, which delete messages after delivery.

Kafka organises events into **topics**, and topics are divided into **partitions**. A partition is an ordered, immutable sequence of events with a sequential offset. Partitions are distributed across Kafka brokers (servers) for parallelism and fault tolerance. A topic with 12 partitions across 3 brokers means each broker holds 4 partitions and can fail independently without losing data (with replication enabled).

**Consumer groups** are the mechanism for parallel consumption. A consumer group is a logical subscriber to a topic. Kafka assigns each partition to exactly one consumer within the group at any point in time. This means a group with 12 consumers reading a 12-partition topic achieves maximum parallelism — each consumer reads one partition. A group with 4 consumers on 12 partitions means some consumers read 3 partitions each. Adding a 13th consumer does not increase parallelism — one consumer sits idle because there are only 12 partitions.

The power of consumer groups is that different groups read independently at their own pace. The fraud detection consumer group can read events as fast as they arrive (low lag). The analytics consumer group can fall behind during maintenance and catch up later without affecting fraud detection. Each group maintains its own committed offset — the position up to which it has processed events. Kafka retains events until the retention window expires regardless of consumer group offsets.

For ORCA scaled to enterprise, the inventory event Kafka topic would have consumer groups for: the ORCA AI pipeline (process within minutes), the BI analytics warehouse (can lag by hours), and the audit logging system (process everything, guaranteed once).

### Q3: What is the Lambda architecture and why has the Kappa architecture been proposed as a replacement?

**Answer:** Lambda architecture, proposed by Nathan Marz around 2012, addresses a genuine problem: how do you build a system that provides both low-latency approximate results (from recent data) and accurate historical results (from all data), when stream processing at the time could not guarantee correctness?

The Lambda solution uses two parallel processing paths. The **batch layer** reprocesses all historical data periodically (hourly, daily) with full accuracy using a system like Hadoop or Spark. It produces the "ground truth" view. The **speed layer** processes new events in real time using a streaming system, producing approximate results for data that has not yet been processed by the batch layer. The **serving layer** merges the two views, returning batch results for old data and speed-layer results for recent data.

Lambda's problem is maintenance burden: you maintain two completely separate codebases implementing the same business logic — one in batch (Spark), one in streaming (Kafka Streams or Flink). When business logic changes, both codebases must change in sync. This is expensive, error-prone, and a major source of subtle bugs where the batch and stream results differ slightly.

Kappa architecture, proposed by Jay Kreps in 2014, eliminates the batch layer entirely. It uses a single streaming system for both real-time processing and historical reprocessing. Kafka's long message retention makes this possible: to reprocess history, you simply reset a consumer group's offset to the beginning of the topic and replay all events through the same streaming logic. Modern streaming systems like Apache Flink are sufficiently accurate and efficient to replace batch for most use cases.

Kappa is the preferred modern architecture when your streaming system can handle the historical data volume and you want to maintain one codebase. Lambda is still justified when your batch workloads are fundamentally different from streaming workloads (e.g., complex multi-pass algorithms that do not translate to streaming) or when the streaming infrastructure cannot keep up with historical reprocessing volume.

### Q4: Explain windowing in stream processing. What is the difference between tumbling, sliding, and session windows?

**Answer:** Windowing is the mechanism by which a streaming processor groups events over time to compute aggregations. Without windowing, stream processing can only compute per-event operations. With windowing, you can compute "total sales in the last 15 minutes" or "fraud score based on the last 10 transactions by this user" — the kinds of aggregations that make streaming valuable for AI.

**Tumbling windows** are non-overlapping, fixed-size time intervals. The stream is divided into consecutive buckets — 00:00 to 00:15, 00:15 to 00:30, 00:30 to 00:45. Each event belongs to exactly one window. Tumbling windows are simple to reason about and efficient to compute. They are ideal for metrics that should not double-count (total orders per 15-minute period, total revenue per hour).

**Sliding windows** have a fixed size and a slide interval shorter than their duration. A 1-hour window that slides every 15 minutes produces four overlapping windows per hour. Each event can belong to multiple windows (all windows that overlap its timestamp). Sliding windows are better for "rolling" metrics like "average response time over the last 60 minutes, updated every 15 minutes." They are more computationally expensive because the same events are processed multiple times.

**Session windows** are dynamically sized based on activity. A session window starts when the first event arrives and ends after a configurable inactivity gap (e.g., 30 minutes of silence). If a user clicks five pages over 20 minutes, pauses for 45 minutes, then clicks two more pages, the session window produces two sessions. Session windows do not have a fixed size — they are event-driven. They are ideal for user engagement analysis, clickstream analysis, and detecting activity bursts.

The complicating factor for all window types is **late-arriving events** — events that arrive after the window has closed due to network delays or mobile clients coming back online. Stream processors handle late arrivals with a **watermark**: a threshold of acceptable lateness. Events arriving within the watermark delay the window closing; events arriving after the watermark is exceeded are either dropped, counted in a side output, or trigger a window recomputation (at the cost of emitting updated results).

### Q5: How would you decide whether ORCA's AI pipeline should use batch or streaming processing, and what would change architecturally if you switched to streaming?

**Answer:** The decision for ORCA starts with the latency SLA: how quickly after an inventory risk event occurs does the business need a reorder recommendation? Currently, the system runs on demand — a user triggers the pipeline from the dashboard. For a small retailer, this is entirely adequate. For a large grocery chain where a stockout in produce translates to immediate lost sales and spoilage, the SLA might be "detect risk and recommend reorder within 10 minutes of POS data arriving."

If the SLA is "within 10 minutes," batch works fine — a batch pipeline running every 5 minutes satisfies the SLA with margin, at low cost and complexity. If the SLA is "within 2 minutes," or if the system must respond to events at hundreds of stores simultaneously, streaming becomes appropriate.

Switching to streaming would require five architectural changes. First, **event ingestion**: POS systems and warehouse management systems would publish inventory delta events to a Kafka topic rather than ORCA's scheduler generating synthetic data. Each event would carry the SKU, store, quantity change, and timestamp.

Second, **streaming alert generation**: a Flink or Kafka Streams job would consume inventory events, maintain per-SKU rolling demand and on-hand state, evaluate risk thresholds in near real-time, and publish `RISK_DETECTED` events to a separate Kafka topic when thresholds are crossed.

Third, **pipeline trigger**: the LangGraph AI pipeline would be triggered by consuming from the `RISK_DETECTED` topic rather than polling `data/scheduler.py`. The FastAPI backend would subscribe to the topic and launch pipeline runs asynchronously.

Fourth, **state management**: streaming requires durable state storage for the per-SKU demand calculations. This would shift from SQLite to Redis (for low-latency reads) with periodic checkpoints to Postgres or BigQuery for durability.

Fifth, **monitoring**: streaming systems require lag monitoring (are consumers keeping up with the producer?), per-partition throughput metrics, and alerting on consumer group lag exceeding the SLA threshold.

## Key Points to Say in the Interview

- Batch = process accumulated data periodically; Streaming = process each event as it arrives
- The decision is driven by latency SLA, not by technical preference — batch is simpler and should be preferred unless real-time is required
- Kafka is a distributed commit log, not a traditional queue — retention, consumer groups, and replay are its distinctive features
- Lambda architecture maintains two codebases; Kappa uses one streaming system for both real-time and historical reprocessing
- Windowing (tumbling, sliding, session) is how streaming systems compute aggregations over time
- Late-arriving events are handled with watermarks — the tolerance threshold before a window closes
- Streaming complexity is real: state management, exactly-once semantics, and consumer lag monitoring all require operational investment

## Common Mistakes to Avoid

- Over-engineering into streaming when batch satisfies the latency requirement — streaming has real operational costs
- Assuming Kafka is always the right message bus — for simple use cases, AWS SQS or Cloud Pub/Sub are cheaper and simpler
- Ignoring late-arriving events in streaming system design — they are common in mobile/IoT scenarios and can corrupt window aggregations
- Building Lambda architecture without acknowledging the dual-codebase maintenance cost — prefer Kappa when streaming can handle the volume
- Conflating event time (when the event happened) with processing time (when the processor saw it) — the difference matters for windowing accuracy

## Further Reading

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/) — Comprehensive reference covering topics, partitions, consumer groups, and delivery semantics
- [Apache Flink Documentation](https://nightlies.apache.org/flink/flink-docs-stable/) — Windowing, state, watermarks, and exactly-once semantics in production streaming systems
- [Jay Kreps: Questioning the Lambda Architecture](https://www.oreilly.com/radar/questioning-the-lambda-architecture/) — The original Kappa architecture proposal explaining why Lambda's complexity can be avoided
