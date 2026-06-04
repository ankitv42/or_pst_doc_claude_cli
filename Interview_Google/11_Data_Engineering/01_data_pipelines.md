# Data Pipelines

## What Is It? (Plain English)

A data pipeline is the automated conveyor belt of the modern data world. Just as a physical assembly line takes raw materials in at one end and delivers finished products out the other, a data pipeline takes raw data from source systems, processes and cleans it, and delivers transformed, trustworthy data to its destination — whether that is a database, a data warehouse, an ML model, or a dashboard.

Think of a city's water system. Water is collected from rivers and reservoirs (ingestion), filtered and treated at purification plants (transformation), and delivered via pipes to homes and businesses (loading). You never think about the infrastructure unless it breaks — which is the mark of a well-built pipeline. When it does break, the consequences cascade: residents run out of water, restaurants cannot operate, hospitals sound alarms.

The difference between a data pipeline and a one-off script is the same as the difference between a water utility and carrying buckets. A production-grade pipeline handles failures gracefully, retries automatically, logs every step, alerts on anomalies, scales to volume changes, and can be audited long after the fact. It runs on a schedule or on trigger, not when someone remembers to run it manually.

## How It Works

A pipeline has four conceptual stages: Ingest, Transform, Validate, Load.

```
SOURCE SYSTEMS
   │
   │  Raw data (JSON, CSV, DB rows, API responses, logs)
   ▼
┌──────────────┐
│   INGEST     │  Pull from APIs, databases, files, streams
│   (Extract)  │  Handle rate limits, auth, partial reads
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  TRANSFORM   │  Clean, join, aggregate, enrich, type-cast
│              │  Apply business rules and feature logic
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   VALIDATE   │  Schema checks, null checks, range checks
│  (Quality    │  Reject bad batches before they propagate
│   Gate)      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    LOAD      │  Write to warehouse, feature store, DB
│              │  Append, upsert, or full-replace patterns
└──────────────┘
       │
       ▼
 DESTINATION (BigQuery, Snowflake, Postgres, S3, ChromaDB)
```

**Orchestration tools** manage dependencies between pipeline steps and schedule runs:

- **Apache Airflow** — the industry standard; defines pipelines as Python DAGs (Directed Acyclic Graphs); strong ecosystem but operationally heavy
- **Prefect** — modern Python-native orchestrator with a better developer experience; dynamic tasks; cloud-managed execution
- **Dagster** — asset-centric approach; thinks in terms of "software-defined assets" rather than tasks; excellent for ML pipelines where outputs are versioned datasets or models

**Idempotency** means running the pipeline twice produces the same result as running it once. This is critical for backfilling (re-running historical data after a bug fix) and for safe retries after failures. Achieved by using upsert patterns, writing to dated partitions, and deduplicating on natural keys.

**Backfilling** is the process of re-processing historical data — either to fix a past bug, apply a new transformation logic retroactively, or populate a new column. Good pipeline design makes backfills trivial; bad design makes them terrifying.

## Why Google Cares About This

At Google's scale, data pipelines underpin every product — Search ranking signals, Ads targeting features, YouTube recommendation inputs, and internal ML training datasets all flow through pipelines processing petabytes per day. Senior AI/ML roles at Google require candidates who understand that model quality is a downstream function of data pipeline quality: a brilliant model trained on corrupted or stale features is worse than useless. Interviewers probe for pipeline thinking to assess whether a candidate can design systems that are reliable and maintainable over years, not just accurate on the day they ship.

## Interview Questions & Answers

### Q1: What makes a data pipeline "production-grade" as opposed to a one-off script?

**Answer:** A one-off script accomplishes a task once under controlled conditions. A production-grade pipeline is a system designed to run reliably, repeatedly, and without human supervision in a dynamic environment. The distinctions are architectural, not merely cosmetic.

A production pipeline is **observable**: every run emits structured logs with timestamps, row counts, processing durations, and error codes. Downstream teams can answer "did today's pipeline run succeed?" by querying a metadata store, not by asking the data engineer. Alerting fires when SLAs are missed or anomalies are detected.

It is **idempotent**: re-running the pipeline on the same input produces identical output. This enables safe retries after failures and allows backfills to fix historical data without human coordination. Idempotency typically requires upsert logic, partition-based writes, or exactly-once processing semantics.

It is **resilient**: it handles partial failures without corrupting state. The pipeline can resume from checkpoints rather than restarting from scratch. Failed tasks are retried with exponential backoff. Dead-letter queues capture records that cannot be processed so they can be inspected and reprocessed later without blocking the main flow.

It is **maintainable**: schema changes, new data sources, and business rule updates can be made without rewriting the pipeline. Configuration is externalised, dependencies are explicit (a DAG, not implicit script order), and tests cover critical transformation logic. A new engineer can understand what the pipeline does and why within hours, not weeks.

Finally, it is **documented and auditable**: lineage metadata records where data came from, what transformations were applied, and who triggered a run. This is increasingly important for regulatory compliance (GDPR, CCPA) and for debugging model degradation.

### Q2: Explain idempotency in the context of data pipelines. How do you achieve it?

**Answer:** Idempotency is the property that applying the same operation multiple times has the same effect as applying it once. In pipeline terms: if I run the 9 AM pipeline at 9 AM and again at 9:05 AM (because the first run seemed to hang), the destination table looks identical to if I had run it once successfully.

Without idempotency, a retry doubles row counts, corrupts aggregates, or produces duplicate model training examples. These bugs are insidious because they are silent — the pipeline "succeeds" but produces wrong data.

The most reliable technique is **upsert (merge) logic**: instead of appending rows, use an INSERT ... ON CONFLICT DO UPDATE pattern keyed on a natural identifier. If a row already exists, it is updated with the same values; if it does not, it is inserted. The result is identical regardless of how many times the pipeline runs.

A second technique is **partition-based writes**: write each batch to a dated partition (`date=2024-01-15`), then atomically swap the partition in. If the pipeline re-runs for the same date, it overwrites the partition entirely, producing identical results. This is standard in Hive and BigQuery.

A third technique is **deduplication on arrival**: write to a staging table with duplicates allowed, then merge into the production table as a separate idempotent merge step. The staging write need not be idempotent because the merge provides the safety net.

For ORCA, `data/scheduler.py` achieves idempotency by checking whether an alert record with a given SKU and timestamp already exists before inserting. Re-running the scheduler after a failure does not double the 102 alert records.

### Q3: How do orchestration tools like Airflow, Prefect, and Dagster differ? When would you choose each?

**Answer:** All three tools solve the same core problem — scheduling, dependency management, and retry logic for multi-step data workflows — but they embody different philosophies about how pipelines should be expressed and operated.

**Apache Airflow** defines pipelines as Python DAGs where nodes are operators and edges are dependencies. It has a massive ecosystem (hundreds of provider packages for every cloud service), a mature UI, and is deeply embedded in the GCP/Google Composer offering. Its weaknesses are operational complexity (the Airflow scheduler and webserver require careful tuning at scale) and its static DAG model, which struggles with dynamic fan-out (creating tasks at runtime based on data). Choose Airflow when you are on GCP, your org has existing Airflow expertise, and your pipelines have relatively static structure.

**Prefect** is the modern challenger. It is Python-first — you decorate ordinary functions with `@task` and `@flow`, which means pipelines look like normal code and are easy to unit-test. Prefect handles dynamic task creation naturally. The cloud-managed execution layer (Prefect Cloud) removes the operational burden of hosting a scheduler. Choose Prefect when you value developer experience, need dynamic fan-out, and prefer managed infrastructure.

**Dagster** takes the most opinionated approach: it models pipelines as graphs of **software-defined assets** (a DataFrame, a trained model, a warehouse table) rather than tasks. This asset-centric model makes lineage first-class — you can see exactly which assets depend on which, trigger partial re-runs when upstream assets change, and track asset freshness. Choose Dagster when your team is ML-heavy, data assets need versioning and lineage tracking, and you want tight integration with dbt and ML experiment tracking tools.

For a senior Google role, I would highlight that the choice of orchestrator is less important than understanding its failure modes — specifically, what happens when the scheduler itself crashes during a run.

### Q4: Describe how you would build a pipeline to backfill 3 years of historical data after discovering a transformation bug.

**Answer:** Discovering a bug in a transformation that has been running for 3 years is stressful but manageable if the pipeline was designed correctly. The approach has four phases: assess, isolate, replay, verify.

**Assess the blast radius.** Identify which downstream consumers (models, dashboards, reports) have been reading the corrupted data. Quantify how wrong the data is — a systematic off-by-one error is different from random corruption. Decide whether consumers need to be frozen (blocking reads) or can tolerate a temporary inconsistency window while the fix runs.

**Isolate and fix the bug.** Fix the transformation logic and write a test that specifically covers the failure case. Deploy to a staging environment and validate on a single month of historical data before running the full backfill. This is the most important step — running a 3-year backfill with the wrong fix is worse than the original bug.

**Replay the historical data.** Because the pipeline was designed with idempotency (partition-based writes or upsert logic), rerunning it for historical dates overwrites the corrupted data with correct data. In Airflow, this is `airflow dags backfill -s 2021-01-01 -e 2023-12-31 <dag_id>`. In Prefect or Dagster, date-range parameters trigger the same. For large backfills, run in parallel across date partitions using a maximum concurrency setting to avoid overwhelming the source system.

**Verify and communicate.** Compare aggregate statistics (row counts, sum of key metrics, null rates) between the old and new data. Use a data diff tool (e.g., data-diff) to quantify changes. Notify downstream consumers with a "data corrected" event so they can re-run their own downstream jobs. Publish a post-mortem that identifies the root cause and the gap in test coverage that allowed the bug to run for 3 years undetected.

### Q5: ORCA's `data/scheduler.py` generates 102 SKU alert records. How would you make this production-grade if ORCA were deployed at Walmart scale?

**Answer:** ORCA's `data/scheduler.py` is a solid proof-of-concept: it generates synthetic inventory risk data and populates the SQLite database on demand. Making it production-grade at Walmart scale (4,700 stores, 100,000+ SKUs per store, sub-minute freshness requirements) requires rethinking every component while preserving the conceptual pipeline structure.

At Walmart scale, inventory events are generated continuously by POS systems, RFID sensors, and supplier EDI feeds. The scheduler pattern (run once, generate data) would be replaced by a **streaming ingest layer** — Apache Kafka topics receiving real-time inventory delta events from stores. Each event is a record of a transaction: a sale, a receipt, a transfer, an adjustment. The pipeline's job shifts from generating data to consuming and enriching this stream.

The transformation layer would run on Apache Flink or Spark Streaming, computing rolling 7-day and 30-day demand rates, lead-time-adjusted reorder points, and risk classifications (CRITICAL, AT_RISK, HEALTHY) per SKU per store. This is computationally intensive — pre-aggregating by SKU reduces the dimensionality that the AI pipeline sees downstream.

The storage layer would be a horizontally sharded relational database (Cloud Spanner or a sharded Postgres cluster) with SQLite replaced entirely. The AI pipeline would read from read replicas to avoid contention with the write path.

The scheduler itself would become an Airflow or Dagster DAG with two modes: a streaming trigger (Kafka consumer group that fires the pipeline when a SKU crosses a risk threshold) and a batch catch-all (runs every 15 minutes to catch any SKUs missed by the streaming trigger due to event backpressure). Monitoring would track lag between an inventory event occurring at a store and an ORCA reorder recommendation being generated — the SLA target would be under 5 minutes for critical SKUs.

## Key Points to Say in the Interview

- A production pipeline is observable, idempotent, resilient, and auditable — not just accurate
- Idempotency enables safe retries and backfills; achieve it via upserts, partitioned writes, or deduplication
- Orchestration tools differ in philosophy: Airflow (task-centric, ecosystem-rich), Prefect (developer-friendly, dynamic), Dagster (asset-centric, lineage-first)
- Backfills require four steps: assess blast radius, fix and test, replay with idempotent logic, verify and communicate
- Pipeline monitoring should include both infrastructure metrics (latency, throughput, error rate) and data quality metrics (null rates, schema drift, row count anomalies)
- "The quality of your ML model is bounded above by the quality of the data pipeline feeding it"
- Scale changes the architecture: from scheduled scripts to streaming ingest at large volumes

## Common Mistakes to Avoid

- Assuming a pipeline that "works once" is production-ready — it needs failure handling, observability, and idempotency
- Writing transformation logic directly in SQL without tests — bugs introduced here can silently corrupt data for months
- Not considering backfill complexity upfront — pipelines that are hard to backfill are technical debt with compounding interest
- Building pipelines with implicit ordering (script 1 then script 2) rather than explicit dependency graphs — the next engineer will not know the order
- Treating orchestrator complexity as free — Airflow at scale requires significant operational investment

## Further Reading

- [The Airflow Project](https://airflow.apache.org/docs/) — Official docs covering DAG authoring, operators, and scheduling best practices
- [Dagster Asset-Based Pipelines](https://docs.dagster.io/concepts/assets/software-defined-assets) — Explanation of the software-defined assets model and how it differs from task-based orchestration
- [Martin Fowler: DataMesh](https://martinfowler.com/articles/data-mesh-principles.html) — Architectural thinking on data ownership and pipeline responsibility at scale
