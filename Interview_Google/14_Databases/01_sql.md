# SQL & Relational Databases — The Backbone of Data Systems

## What Is It? (Plain English)

A relational database organises data into tables — think of a spreadsheet where each row is a record and each column is a field. What makes relational databases powerful is the ability to link tables together through shared keys and query across those relationships in a single statement. SQL (Structured Query Language) is the language you use to interact with these databases — to ask questions ("show me all orders over $1,000 from last month"), to insert new data, and to modify or delete existing records.

Relational databases have been the foundation of business computing since the 1970s. When you make an online purchase, the order is stored in a relational database. When your bank shows your transaction history, it is reading from a relational database. When your company's ERP system tracks inventory, it is almost certainly using a relational database. The reason they have dominated for 50 years is that they provide strong guarantees: your data will not be lost, partially written, or inconsistent. If you transfer $100 from one account to another, the relational database guarantees that either both the debit and credit happen, or neither does — you can never lose $100 into the void.

For AI systems, SQL is essential because the training data, evaluation results, feature stores, and experiment metadata that power AI are all structured data that fits naturally into tables. The ORCA inventory management system described in this project uses SQLite — a lightweight relational database — to store all its inventory data, pipeline execution logs, and decision records. Understanding SQL is non-negotiable for anyone building production AI systems.

## How It Works

A relational database stores data in **tables** (also called relations). Each table has **columns** (attributes) with defined data types. Each row is a **record**. A **primary key** is a column (or combination of columns) whose value uniquely identifies each row. A **foreign key** is a column that references the primary key of another table, creating a relationship between tables.

```ascii
DATABASE SCHEMA EXAMPLE: Inventory Management System

┌─────────────────────────────────────────────────────────────────────┐
│  TABLE: skus                      TABLE: stores                     │
│  ─────────────────────────────    ──────────────────────────────    │
│  sku_id (PK)  │ name  │ class     store_id (PK) │ name │ region     │
│  ───────────────────────────      ────────────────────────────      │
│  SKU-001      │ Pen   │ A                    1   │ NYC  │ East       │
│  SKU-002      │ Desk  │ B                    2   │ LAX  │ West       │
│  SKU-003      │ Chair │ A                    3   │ CHI  │ Midwest    │
│                                                                      │
│  TABLE: inventory_levels           TABLE: pipeline_runs             │
│  ───────────────────────────────── ─────────────────────────────   │
│  inv_id (PK) │ sku_id │ store_id   run_id (PK) │ sku_id │ decision  │
│              │ (FK)   │ (FK)       ────────────────────────────    │
│  ─────────────────────────────     RUN-001     │ SKU-001│ AUTO      │
│  1           │ SKU-001│ 1          RUN-002     │ SKU-003│ ESCALATE  │
│  2           │ SKU-002│ 1                                           │
│  3           │ SKU-001│ 2          ↑ sku_id is a FK referencing     │
│                                      skus.sku_id                    │
│              ↑ Both sku_id and store_id are FKs (JOIN targets)      │
└─────────────────────────────────────────────────────────────────────┘

JOIN QUERY:
SELECT s.name, st.name, i.quantity
FROM inventory_levels i
JOIN skus s ON i.sku_id = s.sku_id
JOIN stores st ON i.store_id = st.store_id
WHERE s.class = 'A' AND i.quantity < 10;

RESULT:
┌─────────────┬─────────────┬──────────┐
│ sku_name    │ store_name  │ quantity │
├─────────────┼─────────────┼──────────┤
│ Pen         │ NYC Store   │ 3        │
│ Chair       │ LAX Store   │ 7        │
└─────────────┴─────────────┴──────────┘
```

**ACID properties** are the guarantees relational databases provide:
- **Atomicity**: a transaction either fully completes or fully rolls back — no partial updates
- **Consistency**: the database moves from one valid state to another — constraints are never violated
- **Isolation**: concurrent transactions do not interfere with each other — you cannot read half-written data
- **Durability**: once committed, data is permanent even through crashes (written to disk, not just memory)

**Indexes** are data structures that dramatically speed up reads by allowing the database engine to find rows without scanning every row. A B-tree index on `sku_id` means finding a specific SKU takes O(log n) time instead of O(n). However, each index slows down writes (every INSERT/UPDATE must also update the index).

## Why Google Cares About This

SQL is the lingua franca of data — every data engineer, analyst, scientist, and AI engineer uses it daily. For senior AI roles at Google, SQL competency signals that you can design data schemas that power AI systems, debug data quality issues, and optimise queries that run over billions of rows in BigQuery (Google's managed SQL data warehouse). Questions about SQL design are a proxy for systems thinking: how you structure data today determines how efficiently AI pipelines can query it tomorrow.

## Interview Questions & Answers

### Q1: What is database normalisation and when might you intentionally denormalise for an AI workload?

**Answer:** Normalisation is the process of structuring a database to reduce data redundancy and improve data integrity. The core idea is "store each piece of information in exactly one place." The guiding principles are called **Normal Forms** (1NF, 2NF, 3NF, BCNF). In practice, achieving 3NF means: each table has a primary key, every column depends only on the full primary key (not part of it), and no column depends on another non-key column.

Consider a naive inventory table: `(order_id, sku_id, sku_name, sku_category, store_id, store_city, quantity)`. This is not normalised — `sku_name` depends on `sku_id`, and `store_city` depends on `store_id`. If you change a SKU's name, you must update hundreds of rows (one per store). If you miss any, the data becomes inconsistent. Normalised design splits this into three tables: `skus (sku_id, name, category)`, `stores (store_id, city)`, and `inventory (sku_id, store_id, quantity)`. Now a name change is one row in the `skus` table — automatic consistency.

For AI workloads specifically, **denormalisation is often intentional and justified**. A feature store for ML might precompute and flatten features into wide tables, even at the cost of some redundancy, because: (1) training data reads are far more frequent than updates, (2) JOINs at query time add latency, and (3) the reading pattern is fixed (always the same ML features) rather than ad-hoc. Google BigQuery is designed for denormalised, wide tables — it is a columnar store where redundancy is cheap (columns are compressed independently) and JOINs are expensive (scan cost). The art of ML data engineering is knowing when normalisation's write integrity benefits matter (production operational data) and when denormalisation's read performance benefits dominate (training datasets, feature stores).

### Q2: Explain window functions in SQL and give an example relevant to an inventory AI system.

**Answer:** Window functions perform calculations across a "window" of rows related to the current row — without collapsing the results into a single group (as GROUP BY does). They allow you to answer questions like "what is each store's inventory relative to the average across all stores?" while still keeping each individual row in the output.

The syntax is: `FUNCTION() OVER (PARTITION BY ... ORDER BY ... ROWS/RANGE ...)`. The PARTITION BY is like GROUP BY but doesn't collapse rows — it defines the window. ORDER BY within the window allows cumulative calculations. ROWS/RANGE specifies how many rows around the current row to include.

```sql
-- For each SKU, show current stock, the 7-day average, and
-- how many days until stockout at the current sales rate.
SELECT
    sku_id,
    store_id,
    date,
    quantity_on_hand,
    AVG(daily_sales) OVER (
        PARTITION BY sku_id, store_id
        ORDER BY date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7day_avg_sales,
    quantity_on_hand / NULLIF(
        AVG(daily_sales) OVER (
            PARTITION BY sku_id, store_id
            ORDER BY date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 0
    ) AS days_to_stockout,
    RANK() OVER (
        PARTITION BY date
        ORDER BY quantity_on_hand ASC
    ) AS scarcity_rank_across_stores
FROM daily_inventory_snapshots;
```

Common window functions: `ROW_NUMBER()` (unique sequential row number within partition), `RANK()` / `DENSE_RANK()` (ranking with ties), `LAG(col, n)` / `LEAD(col, n)` (access values from n rows before/after current), `SUM() OVER (...)` / `AVG() OVER (...)` (running totals/averages), `FIRST_VALUE()` / `LAST_VALUE()` (first/last value in window).

For the ORCA inventory system, window functions are the natural tool for computing trending metrics: "is this SKU's velocity accelerating (comparing last 7 days vs previous 7 days)?" — a question answered with two LAG windows. These computed metrics then become input features for the AI agents' demand intelligence analysis.

### Q3: What are CTEs (Common Table Expressions) and when do they improve query readability and performance?

**Answer:** A CTE is a named temporary result set defined at the start of a query with the `WITH` keyword. You can reference it by name in the main query (and in subsequent CTEs). CTEs have two benefits: readability (they let you break a complex query into named, logical steps that read like a story) and, in some databases, materialisation (the CTE result is computed once and reused, rather than re-executed for every reference).

```sql
-- Without CTE: deeply nested, hard to read
SELECT sku_id, avg_velocity FROM (
    SELECT sku_id, AVG(daily_sales) AS avg_velocity FROM (
        SELECT sku_id, date, SUM(units_sold) AS daily_sales
        FROM sales_events WHERE date >= CURRENT_DATE - 30
        GROUP BY sku_id, date
    ) AS daily GROUP BY sku_id
) AS velocity WHERE avg_velocity > 100;

-- With CTEs: reads like a business narrative
WITH sales_last_30_days AS (
    SELECT sku_id, date, SUM(units_sold) AS daily_sales
    FROM sales_events
    WHERE date >= CURRENT_DATE - 30
    GROUP BY sku_id, date
),
sku_velocity AS (
    SELECT sku_id, AVG(daily_sales) AS avg_velocity
    FROM sales_last_30_days
    GROUP BY sku_id
),
high_velocity_skus AS (
    SELECT sku_id, avg_velocity
    FROM sku_velocity
    WHERE avg_velocity > 100
)
SELECT h.sku_id, h.avg_velocity, s.class, s.supplier_lead_time
FROM high_velocity_skus h
JOIN skus s ON h.sku_id = s.sku_id
ORDER BY h.avg_velocity DESC;
```

**Recursive CTEs** are a powerful extension for hierarchical data — supply chain bills-of-materials, org charts, or product category trees. A recursive CTE references itself to iteratively traverse a hierarchy.

On performance: most modern databases (PostgreSQL, BigQuery, SQL Server) treat CTEs as optimiser hints but do not always materialise them. PostgreSQL prior to version 12 always materialised CTEs (an "optimisation fence" — the query optimiser could not push predicates inside), which could hurt performance for large CTEs. PostgreSQL 12+ uses inline CTEs by default (treats them like a subquery the optimiser can fold). For AI feature pipelines that compute complex features over large tables, understanding whether your database materialises CTEs can mean the difference between a 10-second query and a 10-minute query.

### Q4: How would you design a database schema for the ORCA-style AI inventory management system?

**Answer:** The schema should capture four domains: the product catalogue, the store network, real-time inventory levels, and AI pipeline execution history. Separating these domains gives you normalised integrity for the reference data and a queryable audit trail for AI decisions.

The core tables are: `skus (sku_id PK, name, category, class CHAR(1), unit_cost, supplier_id FK, lead_time_days INT)` — the product master. `stores (store_id PK, name, region, country)` — the store network. `inventory_snapshots (snapshot_id PK, sku_id FK, store_id FK, snapshot_ts TIMESTAMP, quantity_on_hand INT, reorder_point INT, demand_30d FLOAT)` — a time-series of inventory levels (append-only, never update). `pipeline_runs (run_id PK, sku_id FK, store_id FK, started_at TIMESTAMP, status VARCHAR, agent1_output JSONB, agent2_output JSONB, agent3_output JSONB, decision VARCHAR, approved_by VARCHAR, cost_of_order DECIMAL)` — the AI pipeline execution log. `alerts (alert_id PK, sku_id FK, store_id FK, created_at TIMESTAMP, risk_level VARCHAR, resolved_at TIMESTAMP)` — the alert queue that triggers pipeline runs.

Key design decisions: First, use `JSONB` (or `JSON` in SQLite) for agent outputs rather than trying to normalise the semi-structured LLM responses — AI output structures change as prompts evolve. Second, use an append-only `inventory_snapshots` table rather than an updatable `current_inventory` table — this gives you a time-series history for trend analysis (critical for AI demand forecasting) and an audit trail. Third, index on `(sku_id, snapshot_ts)` for time-series queries and `(risk_level, resolved_at IS NULL)` for the active alert queue. Fourth, add `check(class IN ('A', 'B', 'C'))` constraint on SKU class — database-level enforcement of business rules catches bugs that application code might miss.

This schema directly supports the AI pipeline: Agent 1 queries `inventory_snapshots` for demand trends, Agent 2 reads `skus` for lead times and costs, the `pipeline_runs` table provides the HITL audit trail, and `alerts` drives the pipeline trigger queue.

### Q5: What is a database index and what are the trade-offs of adding one?

**Answer:** A database index is a separate data structure (most commonly a B-tree) that the database maintains alongside the table data. It stores a sorted copy of one or more columns, with pointers back to the full rows. When a query filters or sorts on an indexed column, the database uses the index to find matching rows in O(log n) time instead of scanning every row (O(n)). For a table with 10 million rows, this can be the difference between a 0.001-second query and a 10-second full-table scan.

The B-tree index is sorted, which makes it useful for equality lookups (`WHERE sku_id = 'SKU-001'`), range queries (`WHERE quantity < 10`), and ORDER BY without a separate sort step. A **hash index** stores a hash table instead of a B-tree — O(1) for equality lookups but cannot do range queries. A **composite index** covers multiple columns and is useful when queries always filter on two or more columns together: `CREATE INDEX ON inventory_snapshots (sku_id, snapshot_ts)` speeds up queries like `WHERE sku_id = 'SKU-001' AND snapshot_ts > '2024-01-01'`. A **covering index** includes all columns the query needs, so the database can answer the query entirely from the index without touching the table rows — very fast for frequent read-heavy queries.

The trade-offs: every index adds write overhead. Every INSERT, UPDATE, or DELETE must also update all indexes on the table. For a table with 10 indexes, a single INSERT requires 11 write operations (1 table + 10 index updates). This matters for append-heavy workloads like ML feature pipelines that ingest millions of rows per hour. Additionally, indexes consume disk space (a B-tree index might be 30-60% of the table size) and must fit in the buffer pool (RAM) to be fast — too many large indexes can evict each other from cache.

The practical rule: index columns that appear in WHERE, JOIN ON, and ORDER BY clauses of your most frequent, most critical queries. Do not index every column. Do not add an index "just in case." Run `EXPLAIN ANALYZE` (PostgreSQL) or `EXPLAIN QUERY PLAN` (SQLite) to see whether the query planner is using your indexes, and check the index hit rate in `pg_stat_user_indexes`.

## Key Points to Say in the Interview

- ACID guarantees (Atomicity, Consistency, Isolation, Durability) are what make relational databases trustworthy for transactional data
- Normalisation prevents data inconsistency; denormalisation trades redundancy for read performance — AI feature stores often justify denormalisation
- Window functions perform calculations across related rows without collapsing them — essential for time-series metrics in ML feature engineering
- CTEs break complex queries into readable named steps — readability is critical for queries maintained by multiple engineers
- Indexes speed reads at the cost of write overhead — index selectively based on actual query patterns
- Use `JSONB` columns for semi-structured AI output (agent decisions, LLM responses) — don't over-normalise dynamic ML outputs
- Always run `EXPLAIN ANALYZE` to verify the query planner is using your indexes

## Common Mistakes to Avoid

- Do not say "I'll add an index on every column to make everything fast" — indexes slow writes and can hurt overall performance if overdone
- Do not use `SELECT *` in production queries — it fetches all columns including large ones, wastes bandwidth, and breaks when schemas change
- Do not forget NULL handling in SQL — `NULL != NULL` in SQL comparisons; use `IS NULL` / `IS NOT NULL`
- Do not design an AI system's operational database as a pure analytical (OLAP) schema — the append-only / analytical patterns that work for BigQuery will cause problems in a transactional (OLTP) SQLite/PostgreSQL database
- Do not skip database constraints (CHECK, FOREIGN KEY, NOT NULL) thinking application code will enforce them — databases are shared resources and direct writes bypass your application

## Further Reading

- [PostgreSQL Documentation — SQL](https://www.postgresql.org/docs/current/sql.html) — The definitive SQL reference; PostgreSQL is the most feature-complete open-source relational database
- [SQLite Documentation](https://www.sqlite.org/docs.html) — Reference for SQLite, used in ORCA and in many AI prototyping systems
- [Use the Index, Luke — SQL Indexing Guide](https://use-the-index-luke.com/) — The best practical resource for understanding database indexing
- [Google BigQuery SQL Reference](https://cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax) — SQL for Google's large-scale analytical database
- [Mode Analytics SQL Tutorial](https://mode.com/sql-tutorial/) — Practical SQL tutorial covering window functions and CTEs with real datasets
