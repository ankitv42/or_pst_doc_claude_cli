# ETL vs ELT

## What Is It? (Plain English)

ETL (Extract, Transform, Load) and ELT (Extract, Load, Transform) are two architectural patterns for moving data from source systems to a destination where it can be analysed. The names describe the order of operations: in ETL, you clean and reshape data before storing it; in ELT, you store raw data first and transform it later, inside the destination system.

Think of it like processing mail. ETL is like having a secretary who opens every envelope, shreds junk mail, summarises important letters, and files only the cleaned summaries in your cabinet. Nothing enters the cabinet until it has been curated. ELT is like having a very large filing cabinet and a fast assistant: everything gets filed immediately, and you run sophisticated sorting and analysis later when you need a specific answer. The first approach is careful but slow; the second is fast to store but requires a powerful sorting system (your data warehouse) to find what you need.

The shift from ETL to ELT over the last decade was driven by the rise of cloud data warehouses like Google BigQuery, Snowflake, and Amazon Redshift. These systems can run massively parallel SQL transformations against petabytes of raw data in seconds. When your destination system is that powerful, the cost-benefit calculation changes: it becomes better to load raw data quickly and transform it on-demand with SQL, rather than maintain complex pre-load transformation code.

## How It Works

```
ETL PATTERN (Traditional)
──────────────────────────
 Source DB     Custom ETL      Transformation     Data
 Source API  ──► Server     ──► runs HERE      ──► Warehouse
 Source Files   (Python,        (Python/Spark      (clean,
                Informatica,     before load)       structured)
                SSIS)

 Characteristics:
 + Sensitive data can be masked/dropped BEFORE entering warehouse
 + Warehouse stores only clean, modelled data (smaller, cheaper)
 - Transformation logic locked in ETL tool, hard to version
 - Schema-on-write: changing output schema requires ETL rebuild
 - Slow to adapt to new analytical questions


ELT PATTERN (Modern)
─────────────────────
 Source DB                     Transformation
 Source API  ──► Data      ──► runs HERE      ──► Analytics
 Source Files    Warehouse      (SQL/dbt,          Layer
                 (raw zone)     inside warehouse)  (BI, ML)

 Characteristics:
 + Raw data preserved — can re-transform as needs evolve
 + Transformations are SQL: versionable in git, testable
 + Scale handled by warehouse, not a separate server
 - Sensitive raw data enters warehouse (requires access controls)
 - Warehouse costs scale with raw data volume
 - Schema-on-read: more flexible but can produce surprises


DATA STORAGE ARCHITECTURE COMPARISON
──────────────────────────────────────

  Data Warehouse     Data Lake          Data Lakehouse
  (Snowflake,        (S3, GCS,          (Databricks Delta,
   BigQuery)          Azure ADLS)        Apache Iceberg)
  ┌───────────┐      ┌───────────┐      ┌───────────┐
  │ Structured│      │ Raw files │      │ Raw files │
  │ SQL only  │      │ Any format│      │ + ACID    │
  │ ACID      │      │ No ACID   │      │ + Schema  │
  │ Fast query│      │ Cheap     │      │ + SQL     │
  │ Expensive │      │ Slow query│      │ Moderate  │
  └───────────┘      └───────────┘      └───────────┘
  Best for: BI,      Best for: ML       Best for:
  structured         training data,     Unified BI +
  analytics          archival,          ML workloads
                     unstructured
```

**dbt (data build tool)** is the dominant ELT transformation layer. It lets analysts write SQL SELECT statements that define transformed views or tables, manages dependencies between models, runs dbt tests for validation, and generates documentation. dbt runs inside the data warehouse, leveraging its compute. It transformed data engineering by making SQL transformations version-controlled, testable, and composable.

**When ETL is still right:** Privacy regulations (GDPR, HIPAA) sometimes require that PII be masked or removed before data enters any storage system — including the warehouse. A healthcare company processing patient records may need to anonymise data before it crosses network boundaries, making pre-load transformation mandatory. ETL also makes sense when the destination system has strict schema requirements and the volume does not justify a warehouse.

## Why Google Cares About This

Google BigQuery is one of Google's flagship commercial products and the foundation of many internal analytics systems. Senior AI/ML engineers at Google are expected to understand how to architect data flows that leverage BigQuery's scale, when to use dbt for transformation, and when raw data preservation matters for ML reproducibility. ETL/ELT questions also reveal how a candidate thinks about cost, latency, and flexibility tradeoffs in data architecture decisions.

## Interview Questions & Answers

### Q1: Why did ELT replace ETL as the dominant pattern for analytical workloads?

**Answer:** ETL dominated the era when storage was expensive and compute was constrained to proprietary on-premise servers. The logic was sound for its time: transform data before storing it so the warehouse stores only what it needs, keeping storage costs manageable and query performance high on modest hardware.

Three forces reversed this calculus. First, **cloud storage became effectively free**. Object storage (S3, GCS) costs roughly $0.02 per GB per month. The cost savings from pre-filtering data before storage became negligible compared to the engineering cost of maintaining transformation code.

Second, **cloud data warehouses became massively scalable**. BigQuery, Snowflake, and Redshift can execute distributed SQL against terabytes of raw data in seconds. The bottleneck shifted from "storage too large to query efficiently" to "transformation logic too complex to maintain in a custom ETL server."

Third, **analytical questions became less predictable**. In the ETL era, analysts defined questions upfront and the ETL was built to answer those specific questions. In the modern data-driven enterprise, analytical questions change constantly — new product launches, regulatory requests, ML feature engineering. ELT preserves raw data, allowing teams to ask new questions against historical data without waiting for ETL changes. Schema-on-read beats schema-on-write when requirements are volatile.

The result is the modern ELT stack: Fivetran or Airbyte extract data from sources and load raw copies into a warehouse (the EL part), and dbt handles all transformations inside the warehouse using version-controlled SQL (the T part). This stack has almost completely replaced custom ETL servers for analytical workloads.

### Q2: What is dbt and how does it fit into an ELT architecture?

**Answer:** dbt (data build tool) is the transformation layer of a modern ELT stack. It occupies exactly the T in ELT: given raw data that has already been loaded into a warehouse by an extraction tool like Fivetran, dbt defines and executes the SQL transformations that produce clean, analysis-ready tables.

The core concept is the **dbt model**: a SQL SELECT statement saved as a `.sql` file. dbt compiles the model into a CREATE TABLE AS or CREATE VIEW AS statement and executes it in the warehouse. Models can reference other models using the `{{ ref('model_name') }}` macro, which dbt compiles into the correct warehouse-specific syntax and builds a dependency graph (DAG) from. This means dbt figures out the correct order to execute transformations automatically.

dbt adds several capabilities that raw SQL lacks. **Tests**: built-in `not_null`, `unique`, `accepted_values`, and `relationships` tests run after each model executes and fail the build if assertions are violated. **Documentation**: every model and column can have a description in YAML, and dbt generates a browsable HTML data catalog. **Lineage**: dbt generates a visual DAG showing how every table in the warehouse is derived from what sources. **Snapshots**: dbt can track slowly changing dimension data (how did this record look yesterday?) using Type 2 SCD logic in a single declarative file.

For a senior Google role, dbt is relevant because it makes data transformations auditable and maintainable at scale. The "analytics engineering" role — writing production-quality SQL in dbt — has become a standard function in data teams. Understanding dbt means understanding how clean features get built for ML models: typically a dbt model produces a feature table that the ML pipeline reads.

### Q3: When would you choose a data warehouse vs a data lake vs a lakehouse?

**Answer:** Each architecture reflects a different set of priorities, and the choice depends on the primary consumers of the data and the maturity of the organisation's data practices.

A **data warehouse** (BigQuery, Snowflake, Redshift) is the right choice when your primary consumers are analysts and BI tools querying structured, relational data. Warehouses enforce schemas at write time, guarantee ACID transactions, and provide sub-second query performance on well-designed tables. They are the ideal home for sales dashboards, financial reports, and operational metrics. Their weaknesses are cost at extreme scale, limited support for unstructured data (images, text, audio), and the difficulty of storing the raw, uncleaned data that ML teams need for feature engineering and model training.

A **data lake** (files in S3, GCS, or Azure ADLS) is the right choice when you need to store everything cheaply and worry about structure later. Raw JSON logs, clickstream events, images, audio, video — all can be dumped into a lake at minimal cost. The weakness is that lakes lack governance: files accumulate, schemas are inconsistent, and there are no ACID guarantees. A poorly governed lake becomes a "data swamp" — data exists but no one can find or trust it.

A **lakehouse** (Apache Iceberg tables on S3, Databricks Delta Lake, Google BigLake) attempts to combine the best of both worlds. It stores data as files in cloud object storage (cheap, flexible) but adds a metadata layer that provides ACID transactions, schema enforcement, time-travel queries, and SQL access comparable to a warehouse. This architecture is increasingly popular for unified ML + BI workloads: the same storage layer serves both the ML training pipelines that need raw historical data and the BI dashboards that need clean aggregated metrics.

For ORCA at scale, I would recommend a lakehouse architecture: raw inventory events stored in Iceberg format on GCS, dbt running on BigQuery for aggregated operational metrics, and the ML training pipeline reading historical events directly from the Iceberg table for feature engineering.

### Q4: How do you handle slowly changing dimensions (SCDs) in an ELT pipeline?

**Answer:** A slowly changing dimension (SCD) is a dimension (usually a lookup table like products, customers, or stores) whose attributes change occasionally but not frequently. The challenge is: when an attribute changes, do you overwrite the old value (losing history) or preserve both the old and new values (maintaining history)?

The three common strategies are called Type 1, Type 2, and Type 3. **Type 1** simply overwrites the old value with the new one. Simple, space-efficient, but you lose the ability to answer "what was the product's category when this order was placed?" This is appropriate when historical accuracy for that attribute is not important.

**Type 2** creates a new row for each change, with effective_from and effective_to timestamps (or a boolean is_current flag). The original row remains in the table with its effective_to set to the change date. Queries join the fact table to the dimension by matching the fact's event date to the dimension's effective date range. This preserves full history but grows the dimension table over time and makes queries more complex. Type 2 is the standard for attributes like product category, pricing tier, or customer segment where historical accuracy matters for ML training.

**Type 3** adds a "previous value" column alongside the current value. Simpler than Type 2 but only retains one level of history. Rarely used in practice.

In a dbt ELT stack, Type 2 SCDs are handled by dbt's built-in **snapshots** feature. You define a snapshot with a unique key and a strategy (timestamp or check), and dbt handles the insert/update logic automatically, adding `dbt_valid_from` and `dbt_valid_to` columns. For ORCA, the supplier table would be a good SCD candidate: when a supplier's lead time changes, we want to record when it changed so that historical demand analysis uses the correct historical lead time, not the current one.

### Q5: A data scientist complains that their model performance degrades every time the data team makes changes to the raw source tables. How would you solve this with data contracts?

**Answer:** This is one of the most common and costly friction points in ML organisations: the data engineering team and the ML team are operating on different assumptions about what the data looks like, and there is no formal agreement or automated enforcement of those assumptions.

A **data contract** is a formal, versioned agreement between a data producer (the team writing data to a table) and a data consumer (the ML team reading from it). It specifies the schema (column names, types, nullability), the semantics (what does `quantity_on_hand` actually mean — does it include in-transit inventory?), the quality guarantees (max null rate, freshness SLA), and the change notification process (how much notice before a breaking change).

The immediate fix is to implement a data contract for the tables the ML training pipeline reads. This can be as lightweight as a YAML file checked into the producer's repository specifying the schema and quality guarantees, with a CI check that fails if a change to those tables would break the contract. More mature implementations use tools like Soda, Great Expectations, or dedicated contract platforms (Atlan, Metaphor) to enforce contracts automatically at write time.

The deeper fix is a change in process. Breaking changes to tables consumed by ML pipelines require a deprecation notice (e.g., 30 days), a migration guide, and coordination between teams. Non-breaking changes (adding nullable columns, adding enum values) can be made freely. The contract defines what is breaking and what is not.

For ORCA, I would define a data contract on the `inventory_alerts` table that `agents/graph.py` reads: the schema (SKU ID, category, quantity, lead time, risk level, timestamp), the null constraints (SKU ID and risk level never null), and a freshness guarantee (max 1 hour old at pipeline start time). Any change to `data/scheduler.py` that would break this contract would fail in CI before it reaches main.

## Key Points to Say in the Interview

- ELT replaced ETL because cloud storage became cheap and cloud warehouses became fast — the bottleneck shifted from storage size to transformation maintainability
- dbt is the dominant ELT transformation layer: SQL-based, version-controlled, testable, with auto-generated lineage and documentation
- ETL is still correct when PII must be masked before entering any storage system, or when the destination has strict schema requirements
- Warehouse = structured SQL, ACID, fast queries; Lake = cheap, flexible, schema-on-read; Lakehouse = both, increasingly the default for ML + BI
- Type 2 SCDs preserve attribute history critical for ML training accuracy — use dbt snapshots to implement them
- Data contracts prevent "surprise breaks" between data producers and ML consumers

## Common Mistakes to Avoid

- Assuming ELT is always better — ETL is still the right choice when data privacy requires pre-load transformation
- Treating a data lake as "just a bucket" — without governance, metadata, and access controls, lakes become swamps
- Building transformation logic in application code rather than dbt — this makes transformations untestable, unversioned, and invisible to data lineage tools
- Ignoring slowly changing dimensions in ML training data — training on current attribute values for historical events produces biased models
- Conflating the storage layer (warehouse vs lake) with the transformation layer (dbt) — they are independent decisions

## Further Reading

- [dbt Documentation](https://docs.getdbt.com/docs/introduction) — Full reference for dbt models, tests, snapshots, and documentation patterns
- [Google BigQuery Architecture](https://cloud.google.com/bigquery/docs/storage_overview) — How BigQuery separates storage from compute to enable the ELT pattern at Google scale
- [Apache Iceberg Documentation](https://iceberg.apache.org/docs/latest/) — The open table format enabling lakehouse architectures with ACID guarantees on object storage
