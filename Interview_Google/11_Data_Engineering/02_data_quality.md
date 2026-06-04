# Data Quality

## What Is It? (Plain English)

Data quality is the measure of how fit a dataset is for its intended purpose. A dataset is "high quality" not because it is large or comes from an expensive source, but because you can trust it to make decisions. Low-quality data is data that lies to you — it has missing values, wrong values, duplicate records, stale snapshots, or definitions that vary between teams. The dangerous thing about bad data is that it often looks fine at a glance.

Think of a GPS navigation system. The underlying map database is the data. If the map was last updated three years ago and a new highway was built since then, the GPS will confidently route you into a construction zone. The system is working perfectly — the data is not. This is exactly how bad training data corrupts ML models: the model is working exactly as designed, learning faithfully from data that does not reflect reality.

For AI and ML systems, data quality is a first-order concern, not an afterthought. A model trained on biased, incomplete, or inconsistent data will encode those flaws and amplify them at inference time. Unlike a dashboard where a human might notice "that number looks weird," an ML model consuming bad data will produce confident wrong predictions with no visible warning sign. This is why data quality gates — automated checks that block bad data before it reaches training or serving pipelines — are essential infrastructure.

## How It Works

Data quality is measured across five dimensions, and gates enforce these checks at each pipeline stage.

```
DATA QUALITY DIMENSIONS
───────────────────────
  Completeness  ──► Are all expected fields populated?
                    (null rates, missing record counts)

  Accuracy      ──► Do values reflect the real world?
                    (range checks, cross-system validation)

  Consistency   ──► Do values agree across systems/time?
                    (referential integrity, no contradictions)

  Timeliness    ──► Is the data fresh enough for its purpose?
                    (max age checks, late-arrival detection)

  Uniqueness    ──► Are records deduplicated?
                    (primary key uniqueness, fuzzy-match dedup)


QUALITY GATE PLACEMENT IN A PIPELINE
─────────────────────────────────────

  SOURCE ──► [Gate 1: Schema Validation]
              │  Is the schema what we expect?
              │  New/missing columns? Type changes?
              ▼
           [Gate 2: Statistical Profiling]
              │  Are null rates, distributions, cardinalities
              │  within historical baselines?
              ▼
           [Gate 3: Business Rule Checks]
              │  price > 0, quantity >= 0, date not future
              │  join key exists in dimension table
              ▼
           LOAD ──► DESTINATION (if all gates pass)
              │
              └──► DEAD LETTER / ALERT (if any gate fails)
```

**Great Expectations** is the dominant open-source library for data quality checks. You define "expectations" (e.g., `expect_column_values_to_not_be_null`, `expect_column_mean_to_be_between`) against a dataset, and GX runs them and produces a validation result. Expectations can be saved as JSON "expectation suites" and run in CI.

**dbt tests** are a lighter-weight alternative native to the dbt transformation layer. Built-in tests cover `not_null`, `unique`, `accepted_values`, and `relationships` (referential integrity). Custom SQL tests cover anything else. dbt test failures can block downstream model runs.

**Statistical profiling** goes beyond rule-based checks: it learns the baseline distribution of a column (mean, standard deviation, null rate, cardinality) and alerts when a new batch deviates significantly. This catches "soft" quality failures that no pre-written rule would catch — for example, a supplier accidentally sending prices in cents instead of dollars would pass all rule-based checks but show up as a 100x spike in a statistical baseline monitor.

## Why Google Cares About This

Google's ML systems consume training data at a scale where manual inspection is impossible. A 0.1% error rate in a dataset with 10 billion rows is 10 million corrupted training examples. Senior AI/ML engineers must be able to design quality gates that catch these errors automatically and early — before they enter training pipelines, corrupt feature stores, or silently degrade live models. Interviewers use data quality questions to assess whether a candidate understands that ML reliability is primarily a data engineering problem, not a modeling problem.

## Interview Questions & Answers

### Q1: Why is bad data worse than no data for machine learning?

**Answer:** The intuition that "more data is always better" breaks down when that data is systematically wrong. With no data on a topic, a model makes no prediction (or a prior-based prediction). With bad data, a model makes confident wrong predictions — and in production, confident wrong predictions cause harm.

The core danger is **silent corruption**. If a model produces a null output, an engineer is alerted. If a model produces a plausible-looking but wrong output caused by bad training data, it can run in production for months before the problem is detected — and detection usually requires downstream business metrics (unexplained inventory waste, declining sales) to degrade noticeably before anyone traces the cause back to data.

Consider a concrete example. An inventory AI model is trained on sales data that includes two years of COVID-era records where foot traffic was suppressed by 60%. If those records are included without a flag, the model learns that "normal" demand is 60% of true baseline. Post-pandemic, the model will systematically under-order, causing stockouts. The model is not broken — it learned exactly what the data showed. The data is the problem.

Bad data also **encodes and amplifies biases** in ways that are difficult to audit after the fact. If the training data reflects historical decisions made by a biased process (e.g., loan approvals that discriminated by ZIP code as a proxy for race), a model trained on that data will replicate those decisions at scale, systematically and automatically.

The solution is not to distrust all data, but to build quality gates that characterise and document data before it enters training. Flagged data can be excluded, weighted, or treated as a separate distribution. The goal is conscious, documented data selection — not naive ingestion of whatever arrives.

### Q2: How would you design a data quality gate in a CI/CD pipeline for an ML system?

**Answer:** A CI-integrated data quality gate treats data like code: every change to a training dataset triggers automated validation before the model can be retrained or served. This is analogous to running unit tests before merging a code change.

The gate has three layers. The first is **schema validation**: verify that the incoming dataset has the expected columns, types, and no unexpected new columns that might indicate a source system change. This is cheap to run and catches the most obvious breakages. Tools: Great Expectations `expect_table_schema_to_match_pandas_df`, or a simple JSON Schema check for API responses.

The second layer is **statistical baseline comparison**: for each critical column, compare the current batch's statistics (null rate, mean, standard deviation, percentiles, cardinality) against the rolling baseline computed from the last N batches. Alert if any metric deviates beyond a configurable threshold (e.g., null rate increases by more than 5 percentage points, mean shifts by more than 3 standard deviations). This layer catches the "prices in cents instead of dollars" class of errors that pass schema checks.

The third layer is **business rule validation**: custom assertions that encode domain knowledge. For inventory data: `quantity_on_hand >= 0`, `unit_price > 0`, `sku_id exists in product catalog`, `supplier_id exists in supplier table`. These are written as dbt tests or Great Expectations expectations and maintained by domain experts alongside the pipeline code.

In the CI pipeline (GitHub Actions, Cloud Build), the gate runs as a step between data ingestion and model training. If any layer fails, the pipeline fails with a detailed report identifying which checks failed and how many rows were affected. The model is not retrained on bad data. An alert fires to the data engineering team with a link to the validation report.

The key design principle is: fail explicitly and loudly rather than silently degrading. A failed quality gate that blocks a training run is a success — it caught the problem before it corrupted the model. For ORCA, this pattern would mean: before the AI pipeline consumes the 102 alert records, a gate checks that SKU IDs are valid, quantities are non-negative, and no more than 5% of records have null lead times.

### Q3: Explain the five data quality dimensions with concrete examples from a retail inventory context.

**Answer:** The five dimensions provide a structured vocabulary for diagnosing and communicating data problems. Each has different causes and different fixes.

**Completeness** measures whether all expected data is present. For inventory data, a lead time field that is null for 40% of SKUs is a completeness failure. A batch that was supposed to contain 500 store-SKU combinations but arrived with 350 is a completeness failure. The cause is usually upstream: a data feed was misconfigured, a store system was offline, or a JOIN dropped records. The fix is to identify the root cause upstream and implement dead-letter logging to capture dropped records.

**Accuracy** measures whether values reflect the real world. A SKU showing 500 units on hand when the physical count is 12 is an accuracy failure. Accuracy failures are the hardest to detect automatically because they require either a ground-truth source for comparison (physical audits, cross-system reconciliation) or statistical anomaly detection (this SKU's on-hand count is 40 standard deviations above its historical average). In ML, accuracy failures in training data are the origin of confident wrong predictions.

**Consistency** measures whether data agrees with itself across time and systems. If the warehouse management system says SKU-X has 200 units on hand and the ERP system says 150, that is a consistency failure. If a SKU was classified as Class A in yesterday's export and Class C today with no explanation, that is a temporal consistency failure. Consistency checks require cross-system joins and temporal comparisons — more expensive than single-table validation.

**Timeliness** measures whether data is fresh enough for its purpose. For ORCA, a reorder recommendation based on demand data that is 3 days old during a flash sale is a timeliness failure — demand has already spiked and the model is acting on stale signal. Timeliness checks are time-window assertions: "this dataset's max timestamp must be less than 4 hours old."

**Uniqueness** measures whether records are deduplicated. A duplicate order record in a training set teaches the model that this type of order is twice as common as it really is. Primary key uniqueness checks and fuzzy-match deduplication (for customer names, addresses) enforce this dimension.

### Q4: How do Great Expectations and dbt tests differ? When would you use each?

**Answer:** Great Expectations (GX) and dbt tests solve overlapping problems from different angles. Understanding the difference is important for designing a coherent data quality strategy.

**dbt tests** live inside the dbt transformation layer. They are SQL assertions that run after a model (transformation) executes. Built-in tests — `not_null`, `unique`, `accepted_values`, `relationships` — cover 80% of common cases and require only a few lines of YAML configuration. Custom tests are SQL queries that return rows when the test fails. Because dbt tests run in your data warehouse, they are fast and scalable. Their limitation is scope: they only run on dbt model outputs, not on raw source data before transformation. Use dbt tests to validate that your transformation logic produces correct outputs.

**Great Expectations** is a standalone data validation framework that can run against any data — raw files, Pandas DataFrames, database tables, Spark DataFrames. Its key strength is the concept of "expectation suites" — saved, versioned sets of expectations that can be run repeatedly. GX also generates HTML "data docs" that provide a visual report of validation results over time. Its richer statistical expectations (distribution checks, column-pair relationships) go beyond what dbt tests support natively. Use Great Expectations to validate raw source data before it enters the dbt layer, or to validate ML training datasets before model retraining.

In practice, a mature data quality stack uses both: GX or a similar tool for source validation and ML dataset validation, dbt tests for transformation output validation. The two layers are complementary — GX catches "bad data coming in," dbt tests catch "bad transformation logic."

For a senior Google role, I would also mention **Soda** (a GX competitor with a SQL-native syntax) and the emerging practice of **data contracts** — schema and quality agreements between data producers and consumers that are enforced at write time, shifting quality left to the source system.

### Q5: A model that was performing well for 6 months suddenly shows a significant accuracy drop. How do you investigate whether data quality is the cause?

**Answer:** A sudden accuracy drop 6 months after a model was working well is a classic symptom of data distribution shift, and the first question is always: did the world change, or did the data pipeline change? These require different responses.

Start with **pipeline observability**. Pull up the data pipeline monitoring dashboard and look for anomalies in the last week: row count changes, null rate spikes, schema changes, new source system versions. If the pipeline monitoring shows nothing unusual, the problem is likely genuine world-change (real distribution shift). If the pipeline shows anomalies, you have found the proximate cause.

If the pipeline looks clean, run **statistical profile comparisons** between the training distribution and the current inference distribution on key input features. Use tools like Evidently AI or a custom Great Expectations comparison. Look for: shifted means (e.g., average order size has doubled), changed cardinalities (e.g., a new product category was added to the catalog that the model never saw), or increased null rates in features the model relies on heavily.

For ORCA specifically, I would check: are the 102 alert records in the recent batch consistent in structure with historical batches? Have SKU classifications changed? Has the supplier lead-time field (which feeds Agent 1's urgency calculation) developed a new null pattern? A single null-heavy field can dramatically change the model's input distribution without any obvious "failure" in the traditional sense.

Once the root cause is identified, the response depends on its nature. If it is a pipeline bug, fix the pipeline, backfill the affected period, retrain if the bug corrupted training data. If it is genuine distribution shift, collect new labelled data reflecting the current world and retrain. If it is a schema change (new feature values), add the new values to the feature encoding and retrain. In all cases, add a new test to the quality gate that would have caught this failure earlier — so the same issue cannot recur silently.

## Key Points to Say in the Interview

- Data quality is measured across five dimensions: completeness, accuracy, consistency, timeliness, and uniqueness
- Bad data is worse than no data for ML because models produce confident wrong predictions with no visible warning
- Quality gates belong at three places: source validation, transformation validation (dbt tests), and ML dataset validation (Great Expectations)
- Statistical profiling catches "soft failures" that rule-based checks miss — distribution shifts, scale errors, cardinality explosions
- A failed quality gate that blocks a pipeline run is a success, not a failure — it did its job
- For ML accuracy drops, the investigation always starts with data pipeline monitoring before assuming model degradation
- Shift quality left: the closer to the source you catch bad data, the cheaper it is to fix

## Common Mistakes to Avoid

- Treating data quality as a one-time setup task rather than an ongoing monitoring function — distributions shift as the world changes
- Writing only rule-based checks and skipping statistical profiling — "price > 0" passes for a data feed that accidentally multiplied all prices by 100
- Running quality checks only on outputs (trained model), not on inputs (raw data) — by the time the model degrades, bad data has already been ingested
- Using data quality metrics only for alerting but not as model features — data quality metadata (null rate, freshness) can be useful signals for the model itself
- Ignoring the consistency dimension — cross-system discrepancies are often the hardest to detect and the most business-critical

## Further Reading

- [Great Expectations Documentation](https://docs.greatexpectations.io/docs/) — Comprehensive guide to writing, running, and managing expectation suites
- [dbt Testing Documentation](https://docs.getdbt.com/docs/build/tests) — Built-in and custom dbt test patterns for transformation validation
- [Martin Fowler: Data Quality](https://martinfowler.com/articles/data-mesh-principles.html) — Data mesh principles that include data quality as a product attribute owned by domain teams
