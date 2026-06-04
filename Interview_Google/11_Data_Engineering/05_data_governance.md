# Data Governance

## What Is It? (Plain English)

Data governance is the system of policies, processes, and controls that ensures an organisation's data is accurate, secure, accessible to those who need it, and inaccessible to those who do not — all in a way that meets legal obligations and builds trust. It is the difference between a library with a catalogue, classification system, and checkout policy versus a room where anyone can dump books and no one knows what is there.

Think of data governance as the legal and property system for data. Just as physical property law determines who owns land, who can use it, under what conditions, and who is responsible when something goes wrong, data governance determines who owns a dataset, who can read or write it, what it legally means, how long it must be retained, and what happens when it contains errors or is breached. Without this system, organisations accumulate data they cannot trust, cannot find, cannot use safely, and cannot defend in court.

For AI systems specifically, data governance is not optional overhead — it is a prerequisite for responsible deployment. An AI model that was trained on data that should have been deleted (violating GDPR's right to erasure) is a legal and reputational liability. A model trained on data with no documented lineage cannot be audited when it produces a discriminatory outcome. Data governance is what makes AI defensible.

## How It Works

Data governance has five interconnected components: catalog, lineage, access control, quality, and compliance.

```
DATA GOVERNANCE ARCHITECTURE
──────────────────────────────

  ┌─────────────────────────────────────────────────────┐
  │                  DATA CATALOG                       │
  │  "What data do we have and what does it mean?"      │
  │  Metadata, descriptions, owners, tags               │
  └──────────────────────┬──────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │  LINEAGE   │  │  ACCESS    │  │COMPLIANCE  │
  │            │  │  CONTROL   │  │            │
  │ Where did  │  │            │  │ GDPR, CCPA │
  │ this data  │  │ Who can    │  │ retention  │
  │ come from? │  │ read/write │  │ PII masking│
  │ What used  │  │ this data? │  │ audit logs │
  │ it?        │  │            │  │            │
  └────────────┘  └────────────┘  └────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │               DATA QUALITY LAYER                    │
  │  Is the data trustworthy enough to use?             │
  │  Contracts, SLAs, anomaly detection                 │
  └─────────────────────────────────────────────────────┘


DATA MESH vs CENTRALISED GOVERNANCE
─────────────────────────────────────
  Centralised (Traditional):
  ┌──────────────────────────────────────────────────┐
  │         Central Data Team (owns all data)         │
  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │
  │  │Team │ │Team │ │Team │ │Team │ │Team │        │
  │  │  A  │ │  B  │ │  C  │ │  D  │ │  E  │        │
  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘        │
  │     └───────┴───────┴───┬───┘       │            │
  │                         ▼           │            │
  │              Central Data Warehouse  │            │
  └──────────────────────────────────────────────────┘
  Risk: bottleneck, central team can't keep up

  Data Mesh (Federated):
  ┌──────────────────────────────────────────────────┐
  │ Team A owns    Team B owns    Team C owns         │
  │ its data as    its data as    its data as         │
  │ a product      a product      a product           │
  │    │               │               │              │
  │    ▼               ▼               ▼              │
  │ [Central governance platform provides:            │
  │  policy templates, access control infra,          │
  │  catalog tooling, compliance checks]              │
  └──────────────────────────────────────────────────┘
  Risk: inconsistency without strong federated standards
```

**Data catalog tools**: DataHub (LinkedIn, open source), Apache Atlas, Google Dataplex, Alation, Collibra. A catalog stores metadata about every dataset: owner, description, schema, update frequency, quality score, and sensitivity classification.

**Data lineage** tracks the provenance of every dataset: which source systems contributed, which transformations were applied, which models were trained on it. Tools: OpenLineage (open protocol), Marquez, dbt's built-in lineage, Google Cloud Data Catalog.

**PII classification** automatically identifies columns containing personally identifiable information (names, email addresses, phone numbers, social security numbers, IP addresses) so access controls and retention policies can be applied. Google Cloud DLP and AWS Macie are managed services for this.

**Data contracts** are the emerging standard for governance at the producer level: a YAML specification checked into the producing team's repository that defines schema, quality guarantees, and breaking-change notification requirements.

## Why Google Cares About This

Google operates in a regulatory environment where GDPR, CCPA, COPPA, and sector-specific regulations apply to its data globally. Senior AI/ML engineers are responsible not just for building accurate models, but for ensuring those models can be audited, explained, and if necessary, retracted. A model trained on improperly retained user data is a legal liability. A model whose training data lineage cannot be documented is a regulatory exposure. Data governance knowledge signals that a candidate understands the full lifecycle of production AI, not just the modelling layer.

## Interview Questions & Answers

### Q1: What is data lineage and why does it matter for AI systems?

**Answer:** Data lineage is the documented history of where a piece of data came from, what transformations it underwent, and what downstream systems have consumed it. It answers the question: "If I told you row 4,572 in your training dataset is wrong, could you tell me which model is affected, how to fix it, and whether the same wrong data appears anywhere else?"

For AI systems, lineage is critical for three reasons. First, **debugging model degradation**. When a model's accuracy drops, the first question is whether the input data changed. Lineage metadata tells you immediately: "This feature column was produced by dbt model X, which reads from table Y, which was last refreshed at timestamp Z." Without lineage, finding the root cause of a data issue can take days or weeks of manually tracing SQL joins and ETL scripts.

Second, **regulatory compliance**. GDPR's right to erasure (Article 17) requires that when a user requests deletion of their data, the organisation must delete it everywhere — including all copies, all derived datasets, and ideally all model training artifacts that incorporated it. Without lineage, you cannot know which datasets contain a specific user's data. With lineage, you can run a downstream impact analysis: "User ID 12345 appears in source table A, which flows into training dataset B, model C, and recommendation log D."

Third, **reproducibility**. A trained ML model is only reproducible if you can reconstruct the exact training data. Lineage provides the version pointer: "Model v3.2 was trained on dataset snapshot from 2024-03-15 14:30 UTC, derived from source tables at version hash abc123." Without this, retraining "the same model" may produce different results because the underlying data changed.

OpenLineage is the emerging open protocol for lineage — it defines a standard event format emitted by data systems (Spark, dbt, Airflow, Flink) that lineage tools can consume and visualise. For ORCA, documenting that Agent 2's supply options are computed from lead times in the supplier table and safety stock rules from the policy RAG documents is basic lineage that would make the system auditable.

### Q2: How do you implement GDPR compliance in a data pipeline, specifically the right to erasure?

**Answer:** GDPR's right to erasure (often called the "right to be forgotten") requires that when a user exercises their right, their personal data must be deleted from all processing systems within 30 days. For a data engineering team, this is one of the most architecturally challenging compliance requirements because personal data tends to propagate widely through data systems.

The implementation has three phases: discovery, deletion, and verification.

**Discovery** requires data lineage and a PII catalog. Before you can delete data, you must know where it lives. A data catalog with automatic PII classification (Google Cloud DLP, AWS Macie) identifies every column in every table that contains personal data. Lineage tracking tells you which downstream tables, model training datasets, and logs were derived from a user's personal records. This is why lineage is essential for GDPR compliance — without it, discovery is manual and unreliable.

**Deletion** must happen at every layer. In operational databases, a `DELETE WHERE user_id = X` is straightforward. In data warehouses, deletion is harder — BigQuery and Snowflake support `DELETE` but it can be slow on large partitioned tables. The common pattern is to maintain a "deletion manifest" (a list of user IDs to be excluded) and filter it out of all queries, then run a periodic physical deletion sweep during off-peak hours. In object storage (data lake files, ML training datasets), records are extracted and the files are re-written without those records — computationally expensive but necessary.

The hardest part is **trained ML models**. A model trained on data containing a user's personal information has "learned" from that data in a diffuse, distributed way across its weights. Retraining the model from scratch on a dataset that excludes the user satisfies the legal requirement for most interpretations, but it is expensive. Machine unlearning (algorithmically removing a data point's influence from a trained model without full retraining) is an active research area but not yet production-ready for large models.

**Verification** requires automated testing: after deletion, automated checks confirm that no queries against the deleted user ID return records. An audit log records when the deletion request arrived, which systems were processed, and when each deletion completed.

### Q3: What is a data catalog and how should it be maintained in a large organisation?

**Answer:** A data catalog is the searchable inventory of an organisation's data assets. Think of it as a library catalog for datasets: every table, file, API endpoint, and ML model has a catalog entry with metadata — what it contains, who owns it, when it was last updated, what quality SLA it carries, who has access, and how it relates to other assets.

A catalog has three layers of metadata. **Technical metadata** is machine-generated: schema (column names and types), row count, last update timestamp, storage location, partitioning scheme. This can be automatically harvested by the catalog tool from the data systems. **Business metadata** is human-authored: what does this table represent, what does each column mean in business terms, what is the primary use case, who is the authoritative source. This requires human input and is often the hardest to keep current. **Operational metadata** is pipeline-generated: data lineage, quality scores, freshness SLAs, access logs.

Maintaining a catalog in a large organisation requires treating it like a product, not a project. The common failure mode is to build a catalog as a one-time initiative — someone documents every table at launch — and then watch it stale within 6 months as tables change and nobody updates the catalog. Prevention requires three practices: first, catalog entries are required before a new table is promoted to production (enforced by CI checks); second, ownership is assigned and owners are alerted when their tables' quality or freshness degrades; third, catalog metadata is automatically harvested where possible so the technical layer stays current without human effort.

For AI systems, the catalog is also the home for ML model cards: documentation of a model's training data sources, evaluation results, known biases, and intended use cases. This is increasingly required by regulators and by enterprise customers evaluating AI products.

### Q4: Explain the data mesh architecture. What problem does it solve and when does it fail?

**Answer:** Data mesh is a decentralised architecture for data ownership proposed by Zhamak Dehghani in 2019. It addresses a specific failure mode of centralised data teams: the central data team becomes a bottleneck because it owns all data, and as the organisation scales, the central team cannot keep pace with the data needs of dozens of domain teams.

The core insight of data mesh is that data should be owned by the domain teams that understand it best, treated as a **product** (with SLAs, documentation, and consumers in mind), and made available over a shared infrastructure. A retail company might have a Sales domain team that owns and publishes a "Sales Transactions" data product, an Inventory domain team that owns "Stock Levels," and a Customer domain team that owns "Customer Profiles." Each team is responsible for their data product's quality, freshness, and accessibility.

The four principles of data mesh are: **domain ownership** (data is owned by the teams closest to the source), **data as a product** (data products have SLAs, documentation, and discoverable interfaces), **self-serve data infrastructure** (a central platform team provides the infrastructure for hosting, cataloging, and accessing data products, but does not own the data), and **federated computational governance** (policies are set centrally — GDPR, PII handling, data contracts — but enforced locally through tooling).

Data mesh fails in two scenarios. First, when the organisation lacks the cultural maturity for domain ownership: teams are not held accountable for data quality, "everyone owns it" becomes "no one owns it," and data products decay. Second, when the governance layer is weak: without strong central policies and automated enforcement, inconsistencies proliferate across domain-owned datasets, making cross-domain analysis (joining Sales data with Inventory data) unreliable. The self-serve infrastructure investment is also substantial — building a data platform that teams can use independently requires significant engineering effort.

### Q5: How would you classify and protect PII in an AI training pipeline?

**Answer:** PII (Personally Identifiable Information) protection in an AI training pipeline requires addressing data at three points: at ingestion (classify what you have), during storage (apply appropriate controls), and at model training (ensure compliance).

**At ingestion**, automatic PII classification scans incoming datasets using pattern matching (regular expressions for email, phone, SSN, credit card formats) and NLP models that identify names, addresses, and other contextual PII. Google Cloud Data Loss Prevention (DLP) and AWS Macie are managed services for this. The output is a PII sensitivity label attached to each column in the data catalog: `PII_EMAIL`, `PII_NAME`, `PII_LOCATION`, `SENSITIVE_FINANCIAL`, and so on. Columns with these labels receive automatic access restrictions.

**During storage**, sensitive columns are either tokenised (replaced with a reversible token so downstream systems can join records without seeing raw PII) or hashed (irreversibly anonymised for training purposes). Tokenisation preserves join capability; hashing enables inclusion in training data where re-identification must be impossible. Encryption at rest and in transit applies to all PII data, with key management handled separately from the data.

**At model training**, the standard approach is to use only anonymised or pseudonymised data in training datasets. The ML training pipeline explicitly reads from a "training-safe" version of the dataset where PII columns have been hashed or removed. A CI check verifies that the training data read path cannot accidentally pull raw PII columns — this is enforced through column-level access controls in the data warehouse. If the model must learn from PII (e.g., a name-entity recognition model), differential privacy techniques can be applied during training to provide mathematical guarantees that the trained model cannot be used to recover individual training records.

For ORCA, no customer PII is currently processed — the system works with SKU-level inventory data. If ORCA were extended to incorporate customer purchase history for demand forecasting, the training pipeline would need PII classification of any customer identifiers, hashing of those identifiers before the data enters the training set, and a lineage record documenting that the training data was derived from pseudonymised customer records.

## Key Points to Say in the Interview

- Data governance covers five areas: catalog, lineage, access control, quality, and compliance — none of these is optional at enterprise scale
- Lineage is the prerequisite for debugging model degradation, GDPR erasure, and ML reproducibility
- GDPR right to erasure is technically hard: data propagates across tables, lakes, and model training datasets — lineage makes it tractable
- Data mesh decentralises ownership to domain teams with federated governance; it fails without cultural accountability and strong policy infrastructure
- PII protection happens at ingestion (classify), storage (tokenise/hash), and training (use anonymised-only data)
- A data catalog is a product, not a project — it must be maintained continuously through ownership and automation
- Data contracts are the emerging standard for producer-level governance

## Common Mistakes to Avoid

- Treating data governance as a compliance checklist rather than an engineering system — governance without automation does not scale
- Building a data catalog once and never maintaining it — catalog entries stale within months without enforced update processes
- Assuming PII protection means "just encrypt the database" — PII propagates into training data, model outputs, logs, and caches
- Implementing data mesh without strong central governance standards — decentralisation without policy federation creates inconsistency
- Overlooking model lineage — knowing which model was trained on which data version is as important as table lineage for GDPR compliance

## Further Reading

- [Google Cloud Dataplex](https://cloud.google.com/dataplex/docs/introduction) — Google's managed data governance and catalog service for GCP data assets
- [OpenLineage Project](https://openlineage.io/) — Open standard for data lineage collection across Spark, Airflow, dbt, and other pipeline tools
- [Zhamak Dehghani: Data Mesh Principles](https://martinfowler.com/articles/data-mesh-principles.html) — Original data mesh manifesto published on Martin Fowler's site
