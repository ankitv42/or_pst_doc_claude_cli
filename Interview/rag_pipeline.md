# ORCA — 18 RAG Pipeline Interview Questions

> **Focus area.** Deep questions on retrieval-augmented generation as implemented in
> `docs/rag/retriever.py`. Covers hybrid search, reranking, corrective RAG, and
> production deployment decisions. Expect these at a Senior AI Engineer level.

---

## Q1 — Why does ORCA use hybrid search instead of pure vector search?

### The Question to Ask
*"You have ChromaDB for vector search. Why add BM25 on top? Isn't vector search enough?"*

### Strong Answer
Vector search finds semantically similar chunks — it understands meaning. BM25 finds chunks with exact keyword matches. They have different failure modes:

```
Query: "CP003 pool auto_approve_limit"

Vector search result:
  → "Capital pools support high-urgency procurement..."  (semantically similar)
  → "The CP001 budget refresh cycle is quarterly..."      (wrong pool!)
  BM25 search result:
  → "CP003 auto_approve_limit_aed = 25000. Pressure flag..."  ← EXACT MATCH
```

For business-specific jargon (`CP003`, `auto_approve_limit_aed`, `abc_class`), vector
embeddings offer no advantage — these terms have no "semantic neighbourhood".
BM25 finds them deterministically.

```
Hybrid = vector results + BM25 results
                │
          RRF Fusion
                │
     Documents ranking high in BOTH get boosted
     Documents appearing in only one get penalised
```

Result: 15–30% better recall on ORCA's domain queries vs vector alone.

### Why It Matters
Hybrid search is now the production standard for enterprise RAG. A candidate who
says "just use vector search" reveals they've only worked with tutorial-level RAG.

### Red Flags
- "Vector search always wins" — demonstrates no knowledge of keyword retrieval
- Can't explain what BM25 stands for (Best Matching 25 — probabilistic ranking)
- Unaware that ChromaDB alone has no BM25 — ORCA builds its own `BM25Index` class

---

## Q2 — Explain how RRF fusion merges vector and BM25 ranked lists.

### The Question to Ask
*"After vector search and BM25 both return ranked lists, how do you merge them into one ranking?"*

### Strong Answer
Reciprocal Rank Fusion (RRF) merges ranked lists by position, not raw score:

```python
# RRF score for each document:
rrf_score = 1/(k + rank_in_vector) + 1/(k + rank_in_bm25)
# k = 60 (standard constant that prevents top-rank dominance)
```

**Why position and not score?**
Vector scores (0.0–1.0 cosine) and BM25 scores (5.0–20.0 TF-IDF) are
on completely different scales — you can't add them directly.

```
Example:
  vector_results = [("chunk_A", 0.92), ("chunk_B", 0.81), ("chunk_C", 0.75)]
  bm25_results   = [("chunk_B", 12.4), ("chunk_D", 10.1), ("chunk_A", 9.8)]

  RRF scores:
    chunk_A: 1/(60+1) + 1/(60+3) = 0.01639 + 0.01563 = 0.03202
    chunk_B: 1/(60+2) + 1/(60+1) = 0.01613 + 0.01639 = 0.03252  ← WINNER
    chunk_C: 1/(60+3) + 0        = 0.01587
    chunk_D: 0        + 1/(60+2) = 0.01613

  Final order: B → A → D → C
  chunk_B wins because it ranked high in BOTH systems.
```

### Why It Matters
RRF is now the standard algorithm for hybrid search in production RAG (used by
Elasticsearch, Vespa, Pinecone). Understanding it shows the candidate has
implemented retrieval beyond a tutorial.

### Red Flags
- "Just average the scores" — breaks because vector and BM25 scores are incomparable scales
- Can't explain why k=60 helps (it dampens the advantage of being rank 1 vs rank 2)
- Unaware that RRF ignores raw score magnitude entirely — only rank matters

---

## Q3 — Why is there a BGE cross-encoder reranker after RRF fusion already ranked the chunks?

### The Question to Ask
*"RRF already gives you a ranked list. Why run a heavy reranker model over the top chunks afterwards?"*

### Strong Answer
RRF ranking is **retrieval-level relevance** — it measures similarity between
the query and each chunk independently. The reranker does something fundamentally
different: it reads the **query and chunk together** as a pair.

```
Retrieval (bi-encoder):      embed(query)  ←cosine→  embed(chunk)
                             Each encoded separately. Fast but approximate.

Reranking (cross-encoder):   model(query + "[SEP]" + chunk)  →  relevance_score
                             Both read together. 10x slower, much more accurate.
```

The reranker can catch retrieval errors that RRF can't:

```
Query: "what happens when lead time exceeds 30 days AND urgency is CRITICAL?"

RRF rank 1: "Lead time affects supplier SLA in all categories..."  ← generic match
RRF rank 2: "CRITICAL urgency: if lead_time_days > 30, apply -20 penalty..."  ← exact answer

Reranker re-scores:
  Rank 1 rerank score: 0.21  (generic — doesn't directly answer)
  Rank 2 rerank score: 0.97  ← PROMOTED to top
```

ORCA's pipeline: retrieve top 10 (fast) → rerank to top 3 (accurate).

### Why It Matters
Reranking is one of the biggest quality improvements added to RAG systems post-2024.
ORCA uses `BAAI/bge-reranker-v2-m3` — multilingual, Apache 2.0, the current
open-source standard. A candidate aware of this knows state-of-the-art RAG.

### Red Flags
- "Reranker and retriever do the same thing" — they have fundamentally different architectures
- Doesn't know "cross-encoder" vs "bi-encoder" distinction
- Unaware of the quality/speed tradeoff — why you can't rerank all 71 chunks directly

---

## Q4 — What is Corrective RAG and when does ORCA trigger it?

### The Question to Ask
*"What happens when the retrieved chunks are poor quality — semantically distant from the query? Does the system just use them anyway?"*

### Strong Answer
ORCA implements **Corrective RAG**: if the top chunk scores below 0.35 after
RRF, the system automatically retries with a domain-enriched query.

```python
CORRECTIVE_THRESHOLD = 0.35

def _corrective_retry(original_query, chunks, doc_types):
    if chunks[0].get("score", 0) >= 0.35:
        return chunks  # good enough — no retry needed

    # query expansion with domain vocabulary
    refined = f"{original_query} {DOMAIN_TERMS}"
    # DOMAIN_TERMS = "ORCA retail UAE inventory replenishment supplier capital pool
    #                 lead time urgency CRITICAL HIGH MEDIUM Class A Class B ..."

    retry = self._hybrid_retrieve(refined, doc_types)
    retry = self._rerank(refined, retry)

    if retry[0]["score"] > chunks[0]["score"]:
        return retry  # retry was better
    return chunks     # original was better after all
```

When this fires:
- Short or ambiguous query: `"rule for high urgency"` → low score → retried with domain terms
- Domain-specific IDs: `"CP001"` alone → enriched to `"CP001 pool capital allocation UAE retail..."`

### Why It Matters
Corrective RAG is an active research technique (2024–2026 papers). ORCA applies
it selectively on the first query per agent — where the broadest context is needed.
This shows the candidate reads recent literature, not just docs.

### Red Flags
- Unaware that retrieval quality can be measured without labels (score threshold)
- "Just increase top_k" — more chunks doesn't help if they're all irrelevant
- Can't explain query expansion — the mechanism that makes the retry smarter

---

## Q5 — How does the RAG system prevent Agent 3's capital pool query from returning Agent 1's event context?

### The Question to Ask
*"There are 5 policy documents in ChromaDB. How do you ensure Agent 3 only gets capital allocation rules, not event planning content?"*

### Strong Answer
Two layers of isolation:

**Layer 1 — Doc-type metadata filter:**
Every chunk ingested into ChromaDB gets a `doc_type` metadata tag:
`policy`, `event`, `supplier`, `graph`.

Each agent queries only its relevant doc types:
```python
# Agent 1: ordering rules + event + entity relationships
doc_types = ["policy", "event", "graph"]

# Agent 3: capital pool rules + entity relationships only
doc_types = ["policy", "graph"]
# "event" excluded — Agent 3 never needs event planning content
```

ChromaDB's `where` filter applies this at query time:
```python
results = self._collection.query(
    query_texts=[query],
    where={"doc_type": {"$in": doc_types}},
    ...
)
```

**Layer 2 — Targeted query construction:**
Agent 3's queries are built from structured state data, not generic strings:
```python
q1 = f"{approval_pool} pool pressure HIGH MEDIUM LOW auto approve limit {category}"
q2 = f"budget score availability score margin score formula lead time penalty"
```

These queries only attract capital pool and scoring formula chunks — semantically
far from event planning content.

### Why It Matters
Leakage between agents is a real production RAG failure mode. ORCA's eval
framework specifically tests for this with `must_not_contain` assertions.

### Red Flags
- No awareness of ChromaDB's `where` filter for metadata
- Thinks one global query per agent is fine — misses cross-contamination risk
- Can't explain what a "doc type" metadata filter is

---

## Q6 — Why does each agent have its own `query_for_agentN` function instead of a generic `query(text)` call?

### The Question to Ask
*"Why not have one retrieval function that all agents call? Why four separate functions?"*

### Strong Answer
Each agent needs different contextual queries built from its specific state variables:

```python
# GENERIC approach (naive):
context = retriever.query("get relevant policy context")
# Problem: returns random chunks with no relevance to the current SKU, category, urgency

# ORCA's targeted approach:
context = retriever.query_for_agent3(
    category      = "Electronics",       # from sku_data
    urgency       = "CRITICAL",          # from demand_summary
    abc_class     = "B",                 # from sku_data
    approval_pool = "CP003",             # from options_package
)
# Fires: "CP003 pool pressure threshold Electronics"
#   AND: "budget score margin score formula Class B CRITICAL"
#   AND: "scoring formula table capital allocation 0 100 points"
```

Each function also:
1. Filters different doc types (`agent1` uses `["policy", "event", "graph"]`,
   `agent3` uses `["policy", "graph"]`)
2. Fires 2–3 targeted sub-queries and deduplicates
3. Returns different `top_k` (Agent 3 returns 4 chunks, Agent 4 returns 3)

This is called **metadata-aware targeted retrieval** — a production pattern.

### Why It Matters
The quality difference between generic RAG and targeted RAG is enormous in practice.
A system that fires a generic query usually retrieves the wrong chunks. Context
built from structured state data is 40–60% more precise.

### Red Flags
- "One function is simpler" — misses that simplicity trades away retrieval quality
- Can't name what each agent's queries cover (ordering rules, event context, scoring formula)
- Doesn't know "multi-query RAG" as a technique (firing 3 queries, merging, deduplicating)

---

## Q7 — Why does the retriever use a singleton pattern?

### The Question to Ask
*"Every time an agent runs, it calls `get_retriever()`. Why not create a new `ORCARetriever()` each time?"*

### Strong Answer
`ORCARetriever.__init__` loads:
- The embedding model (`nomic-ai/nomic-embed-text-v1.5` — ~270 MB)
- ChromaDB client + collection connection
- BGE reranker model (`BAAI/bge-reranker-v2-m3` — ~1.1 GB)
- Initialises empty BM25 cache

Creating this object once takes 15–30 seconds and ~1.5 GB of RAM.

```python
# WITHOUT singleton:
agent1_node: retriever = ORCARetriever()  # loads models (30s, 1.5 GB)
agent2_node: retriever = ORCARetriever()  # loads AGAIN (30s, 1.5 GB)
agent3_node: retriever = ORCARetriever()  # loads AGAIN (30s, 1.5 GB)
# = 90 second overhead + 4.5 GB RAM for one pipeline run

# WITH singleton:
agent1_node: retriever = get_retriever()  # loads once (30s, 1.5 GB)
agent2_node: retriever = get_retriever()  # returns cached instance (1ms)
agent3_node: retriever = get_retriever()  # returns cached instance (1ms)
```

```python
_instance: Optional[ORCARetriever] = None

def get_retriever() -> ORCARetriever:
    global _instance
    if _instance is None:
        _instance = ORCARetriever()
    return _instance
```

The BM25 cache also benefits — built once per doc-type combination, reused across agents.

### Why It Matters
Model loading overhead is a common production performance trap. The singleton pattern
is the standard solution. Knowing it shows production engineering awareness.

### Red Flags
- "Python imports are cached anyway" — imports cache the module, not an instantiated class
- No mention of memory impact — 1.5 GB × 4 = 6 GB would OOM most containers
- Unaware of thread-safety implications of a shared singleton (the BM25 cache dict)

---

## Q8 — How does the RAG system degrade gracefully when the vector DB is unavailable?

### The Question to Ask
*"ORCA runs on Windows but RAG is unavailable on Windows. Does the pipeline crash? How does it keep working?"*

### Strong Answer
There are three layers of graceful degradation:

**Layer 1 — `is_available()` check in every public method:**
```python
def query_for_agent3(self, ...):
    if not self.is_available():
        return "Knowledge base unavailable."  # safe fallback string
```

**Layer 2 — `_init()` self-healing:**
```python
def is_available(self) -> bool:
    if self._collection is None:
        self._init()  # retry initialisation — handles delayed model load
    return self._collection is not None
```

**Layer 3 — `graph.py` conditional check before every RAG call:**
```python
if retriever and retriever.is_available():
    policy_context = retriever.query_for_agent1(...)
else:
    policy_context = "Knowledge base unavailable — using LLM knowledge."
```

The LLM still receives the live database facts (via MCP) and uses its own
parametric knowledge for policy rules. Quality degrades slightly but the
pipeline completes — agents never see a traceback.

### Why It Matters
Production systems must continue operating in a degraded state. A RAG system that
crashes the pipeline when ChromaDB is unavailable is not production-grade. The health
endpoint also reports `"rag": "unavailable (Windows path conflict)"` — visible to ops.

### Red Flags
- "It would crash" — no awareness of the fallback chain
- Only mentions one layer, not all three
- Doesn't know that the Windows path conflict is a `sys.path` conflict with
  `FlagEmbedding`'s native libraries (not a ChromaDB connection issue)

---

## Q9 — What is the PRIORITY RULE prepended to every RAG context string, and why?

### The Question to Ask
*"Every context string returned by the retriever starts with a specific rule. What is it and why?"*

### Strong Answer
```python
PRIORITY_RULE = (
    "PRIORITY RULE: If any value in this knowledge context conflicts "
    "with the live database data provided above (costs, contacts, "
    "lead times, pool balances, emails), always trust the live data. "
    "This knowledge provides rules and planning context only — not live facts."
)
```

This prevents a specific failure mode: **RAG context overriding live database values**.

Example scenario:
```
Policy document says: "Standard lead time for Electronics = 45 days"
Live database says:   "effective_lead_time = 54.5 days" (supplier changed SLA)

WITHOUT priority rule:
  LLM might use 45 days from policy context (stale!)

WITH priority rule:
  LLM knows: if DB says 54.5, use 54.5. Policy is for rules, not facts.
```

The rule is prepended by `_format_context()` so it can never be forgotten or omitted.

### Why It Matters
RAG hallucination via stale policy context is a production failure mode specific
to hybrid (live DB + knowledge base) systems. The PRIORITY RULE is an example of
**prompt-level safety guardrail** — a technique for constraining LLM behaviour.

### Red Flags
- Doesn't know the PRIORITY RULE exists (they should have read the retriever code)
- "The LLM will figure it out" — LLMs actively do NOT figure this out without explicit instruction
- Can't explain the failure mode it prevents (policy context overriding live DB facts)

---

## Q10 — How does the BGE reranker degrade gracefully if the model isn't available?

### The Question to Ask
*"The BGE reranker model is downloaded at runtime. What happens to retrieval if the model fails to load?"*

### Strong Answer
`BGEReranker` has a two-level fallback:

**Level 1 — Model selection cascade:**
```python
for model_name in [
    "BAAI/bge-reranker-v2-m3",   # primary — best open-source 2026
    "BAAI/bge-reranker-base",     # fallback 1 — smaller, still good
    "cross-encoder/ms-marco-MiniLM-L-6-v2",  # fallback 2 — English only
]:
    try:
        self._model = FlagReranker(model_name, use_fp16=True)
        self._available = True
        return
    except Exception:
        pass
```

**Level 2 — `rerank()` method fallback:**
```python
def rerank(self, query, chunks, top_k=3):
    if not self._available or not chunks:
        return [(i, 1.0 - i*0.1) for i in range(min(top_k, len(chunks)))]
    # ^ returns original order with fake scores — no crash
```

So if all 3 models fail to load:
- RRF-ranked order is preserved (still useful — better than random)
- Pipeline completes normally
- No error surfaces to the user

### Why It Matters
This is defence-in-depth for model loading failures. On constrained environments
(Render free tier, limited disk) models sometimes fail to download.

### Red Flags
- Thinks a model load failure crashes the pipeline
- Unaware that the fallback preserves RRF order — not completely blind ordering
- Doesn't know `use_fp16=True` halves GPU memory with minimal quality loss

---

## Q11 — How does the BM25 index handle the case where a query term never appears in any document?

### The Question to Ask
*"If a user query contains a term that doesn't exist in any policy document, what does the BM25 index return for that term?"*

### Strong Answer
BM25 silently skips missing terms:

```python
def search(self, query: str, top_k: int = 10):
    for token in self._tokenize(query):
        if token not in self.index:  # ← term not in any document
            continue                 # skip — don't crash, don't score
        # ... score documents containing this token
```

For a query like `"CP003 reorder trigger flag"`:
- `"CP003"` → found in index → scored
- `"reorder"` → found → scored
- `"trigger"` → NOT found → skipped silently
- `"flag"` → found → scored

The IDF formula also handles rare terms correctly:
```
IDF = log((N - df + 0.5) / (df + 0.5) + 1)
```
For `df = 1` (appears in 1 of 71 chunks): IDF is high → that term is weighted heavily.
For `df = 71` (appears in all chunks, e.g. "the", "and"): IDF ≈ 0 → stop-words naturally suppressed.

### Why It Matters
BM25 behaves gracefully for out-of-vocabulary terms without needing an explicit
stopword list. This shows the candidate understands the algorithm, not just the API.

### Red Flags
- Thinks BM25 crashes on unseen tokens (it doesn't — `continue` handles it)
- Can't explain IDF intuitively: rare words matter, common words don't
- No awareness that common words are naturally down-weighted without explicit removal

---

## Q12 — How are documents ingested into ChromaDB? What metadata is stored per chunk?

### The Question to Ask
*"Before the retriever can work, 5 PDF documents must be ingested. What does that process produce and what metadata does each chunk carry?"*

### Strong Answer
The ingest pipeline (`docs/rag/ingest.py`) processes 5 policy PDFs:
1. Emergency Procurement Policy
2. Supplier Agreements
3. UAE Retail Event Calendar
4. RCC Capital Pool Rules
5. Entity Relationships (supplier ↔ category ↔ pool chains — "GraphRAG")

Each PDF is chunked and each chunk stored with:
```python
{
    "text":     "...chunk content...",
    "metadata": {
        "doc_type":      "policy",           # filters which agents retrieve this
        "section_name":  "Section 3 — ...",  # shown in context for transparency
        "element_type":  "text" or "table",  # special flag for scoring tables
        "chunk_summary": "...",              # 1-line summary used in context header
        "source":        "file.pdf",
        "page":          3,
    }
}
```

Total: 71 chunks across all 5 documents. The scoring formula for Agent 3 is specifically
stored as `element_type=table` so Agent 3 can target it with a table-specific query.

### Why It Matters
Chunk metadata is what makes per-agent filtering possible. The candidate must
know the ingest output, not just the retrieval side.

### Red Flags
- Thinks ChromaDB automatically generates metadata from PDFs (it doesn't)
- Unaware of `element_type=table` — misses that structure matters for retrieval
- Can't explain why `doc_type` matters at retrieval time (it enables per-agent filtering)

---

## Q13 — What is "GraphRAG" as implemented in ORCA, and how does it differ from standard RAG?

### The Question to Ask
*"ORCA's retriever comment mentions GraphRAG. What does that mean in this context?"*

### Strong Answer
ORCA implements a **text-based GraphRAG** pattern. One of the 5 ingested documents
(`entity_relationships.pdf`) is a graph description of relationships:

```
Electronics → TechLine Asia (supplier) → CP004 (standard pool) → CP003 (expedite)
Grocery     → UAE Fresh Co (supplier)  → CP001 (standard pool)
Dates       → Gulf Foods LLC (supplier)→ CP001 (standard pool)
```

These entity chains are embedded and searchable like any other chunk. When an
agent queries for `"Electronics supplier pool chain"`, the entity relationship
chunk surfaces — giving the LLM the full chain from category to pool.

This is "text-based GraphRAG" vs full GraphRAG (Microsoft's approach):
```
Full GraphRAG: builds actual graph in-memory (nodes, edges, community summaries)
ORCA GraphRAG: stores graph as natural language, retrieves it like a document
```

ORCA's approach is simpler and sufficient — the graph is small (10 entity chains),
static, and retrieved by exact keyword matching.

### Why It Matters
GraphRAG is a 2024–2025 research trend. Understanding that ORCA uses a lightweight
version — and why a full graph wasn't needed — shows engineering pragmatism.

### Red Flags
- "GraphRAG is the same as Neo4j" — conflates knowledge graphs with GraphRAG
- Can't explain what the entity relationship document contains
- Thinks ORCA builds an in-memory graph (it doesn't — just embeds the text description)

---

## Q14 — How does the RAG context get injected into the LLM prompt?

### The Question to Ask
*"The retriever returns a string. Exactly where and how does that string appear in the final LLM prompt?"*

### Strong Answer
The context string is injected as the `{policy_context}` placeholder in each agent's
`ChatPromptTemplate` (defined in `agents/prompts.py`):

```python
# In agents/graph.py — agent3_node:
policy_context = retriever.query_for_agent3(
    category      = sku_data.get("category"),
    urgency       = demand_summary.get("urgency"),
    abc_class     = sku_data.get("abc_class"),
    approval_pool = approval_pool,
)

messages = PROMPTS["agent3"].format_messages(
    pipeline_id     = state["pipeline_id"],
    sku_id          = sku_id,
    demand_summary  = json.dumps(state["demand_summary"], indent=2),
    options_package = json.dumps(state["options_package"], indent=2),
    sku_data        = json.dumps(sku_data, indent=2),
    cp001_data      = json.dumps(cp001_data, indent=2),
    cp003_data      = json.dumps(cp003_data, indent=2),
    policy_context  = policy_context,   # ← RAG context injected here
)
```

The human message in Agent 3's prompt template ends with:
```
POLICY KNOWLEDGE (capital pool rules, scoring formula, approval thresholds):
{policy_context}
```

So the LLM receives both:
- **FACTS** (live DB data injected as JSON blocks from MCP)
- **RULES** (policy context from RAG — retrieved from knowledge base)

### Why It Matters
Understanding how RAG connects to the LLM call is the end-to-end view.
Many candidates understand retrieval in isolation but can't trace the data flow
through to the prompt.

### Red Flags
- Can't name the placeholder (`{policy_context}`)
- Thinks RAG replaces the live DB data — both are needed
- Unaware that the PRIORITY RULE is prepended before any retrieved text

---

## Q15 — What is the `RETRIEVE_TOP_K=10` → `FINAL_TOP_K=3` funnel and why those specific numbers?

### The Question to Ask
*"The retriever first retrieves 10 chunks, then reranks down to 3. Why not just retrieve 3 directly?"*

### Strong Answer
This is the **retrieve-then-rerank funnel** — an industry standard:

```
10 candidates retrieved cheaply (vector + BM25, ~5ms)
        │
Reranker scores all 10 individually against query (~200ms)
        │
Top 3 returned to the agent
```

**Why not retrieve 3 directly?**
Retrieval (vector + BM25) is approximate — it often misses the best chunk at
low k. You need a buffer. With k=10, the correct chunk is nearly always in the
candidate set. The reranker then finds it precisely.

**Why only 3 in the final context?**
LLM context windows have costs and noise. 3 well-reranked chunks reliably
contain the answer. 10 chunks increase noise: wrong chunks can distract the LLM.
For ORCA's 71-chunk collection, 3 × ~200 tokens per chunk = ~600 tokens —
a small fraction of the 8K context window.

**The math:**
- Retrieval recall at k=10: ~85% (correct chunk in top 10)
- Reranker precision at k=3 from k=10: ~90% (correct chunk promoted to top 3)
- Combined: ~76% vs ~65% for direct k=3 retrieval

### Why It Matters
The funnel architecture is the production standard (Pinecone, Cohere, Weaviate
all recommend it). The candidate must understand both stages and the tradeoff.

### Red Flags
- "Just retrieve 3" — misses that retrieval recall improves with larger candidate set
- Thinks more chunks in context is always better (noise increases with count)
- Can't estimate the token cost — shows no awareness of context window budgeting

---

## Q16 — How would you improve ORCA's RAG pipeline if you had more time?

### The Question to Ask
*"If you had two more weeks on this project, what would you improve in the RAG pipeline?"*

### Strong Answer
Four concrete improvements, prioritised by impact:

**Priority 1 — Calibrate golden dataset keywords (MEDIUM urgency):**
The 11 golden cases use keywords written from memory. Some may not match
exact wording in the policy PDFs. Run the eval and fix failing cases with
actual document text.

**Priority 2 — Add LLM-as-judge eval for RAG grounding (HIGH):**
Layer 2 eval (`run_judge_eval.py`) is a stub. The LLM judge should verify:
"Is Agent 3's scoring formula calculation grounded in the retrieved policy context,
or is it hallucinating?" This tests the end-to-end RAG → LLM chain.

**Priority 3 — Chunk overlap and hierarchical chunking:**
Current chunks are fixed-length with no overlap. Important sentences sometimes
split across chunk boundaries. Hierarchical chunking (small + large chunks,
parent retrieved when child matches) would improve continuity.

**Priority 4 — Query rewriting with LLM before retrieval:**
Instead of rule-based query construction in `query_for_agentN`, use a small
LLM to rewrite the query from AgentState. More robust to unusual input values.

### Why It Matters
A senior candidate should know both what they built and its gaps. Being specific
about known issues (golden dataset calibration, Layer 2 stub) shows intellectual
honesty and system ownership.

### Red Flags
- "Everything is fine" — no senior engineer says this about a prototype
- Only suggests adding more data (misses algorithmic improvements)
- Can't distinguish Layer 1 (retrieval quality) from Layer 2 (decision quality)

---

## Q17 — How does ORCA test the RAG pipeline without running the LLM?

### The Question to Ask
*"LLM calls are expensive and non-deterministic. How do you run CI on a RAG system without either of those problems?"*

### Strong Answer
Layer 1 eval tests the **retrieval function** only — no LLM is ever called:

```python
# evals/run_retrieval_eval.py

# Call the REAL retriever function that agents use:
context = retriever.query_for_agent3(
    category      = "Electronics",
    urgency       = "CRITICAL",
    abc_class     = "B",
    approval_pool = "CP003",
)

# Assert that expected facts appeared:
must_contain = ["auto_approve_limit", "CP003", "budget_score"]
for keyword in must_contain:
    assert keyword.lower() in context.lower()

# Assert that wrong-doc content didn't leak in:
must_not_contain = ["supplier contact", "event planning"]
for keyword in must_not_contain:
    assert keyword.lower() not in context.lower()
```

**Properties of this eval:**
- No API key needed
- Deterministic (embedding model is deterministic)
- Runs in ~30 seconds (loads models, runs 11 queries)
- CI gate: `--ci` flag exits 1 if pass rate < 70% or any leak detected
- GitHub Actions runs this on every push to main

### Why It Matters
This is a key insight about AI system testing: test the deterministic components
(retrieval, data pipelines) in CI; test the non-deterministic components (LLM output)
with sampling and LLM-as-judge offline.

### Red Flags
- "You can't test AI in CI" — misses the retrieval/LLM separation
- No mention of the `must_not_contain` / zero-leak requirement
- Unaware that embedding models are deterministic (same query → same embedding every time)

---

## Q18 — Why are there two embedding models — primary and fallback?

### The Question to Ask
*"The retriever tries to load `nomic-ai/nomic-embed-text-v1.5` first, then falls back to `all-MiniLM-L6-v2`. When would the fallback be needed?"*

### Strong Answer
`nomic-ai/nomic-embed-text-v1.5` is the primary embedding model:
- Better quality (better at domain-specific text)
- Requires `trust_remote_code=True` — runs custom code from Hugging Face
- Download size: ~270 MB

Scenarios where it fails and `all-MiniLM-L6-v2` is used instead:
1. **Corporate network policy** blocks `trust_remote_code=True` model downloads
2. **Offline environment** — model not yet cached, internet unavailable
3. **Disk space constraints** — free tier container with < 270 MB spare

**Critical constraint:** The **same model must be used at ingest time and retrieval time**.
If ChromaDB was indexed with `nomic-ai`, querying with `all-MiniLM` returns garbage
(different vector spaces — completely incompatible embeddings).

```python
def _get_embedding_fn():
    for model_name in [PRIMARY, FALLBACK]:
        try:
            ef = SentenceTransformerEmbeddingFunction(model_name=model_name, ...)
            ef(["test"])   # actually run it to verify it loads
            return ef, model_name
        except Exception:
            continue
    raise RuntimeError("No embedding model available.")
```

### Why It Matters
The "same model at ingest and query" constraint is a critical production pitfall.
Changing embedding models after indexing requires re-ingesting all documents.
The candidate should know this, not just know there are two models.

### Red Flags
- Thinks you can mix embedding models in the same ChromaDB collection (you can't)
- No awareness of the deployment scenarios that trigger the fallback
- "All-MiniLM is good enough" — without acknowledging quality vs reliability tradeoff

---

## Scoring Guide for Recruiters

| Score | What It Means |
|---|---|
| Answers all 3 parts (what, why, tradeoffs) | Strong hire — knows production RAG stack |
| Answers what + why, misses tradeoffs | Solid hire — needs exposure to scale |
| Knows terminology but can't explain mechanics | Caution — may be surface-level familiarity |
| "I used LangChain's RAG tutorial" | Red flag — no custom implementation experience |

**Questions that most separate senior from junior RAG candidates:**
- Q2 (RRF mechanics — why position, not score)
- Q3 (cross-encoder vs bi-encoder distinction)
- Q7 (singleton and memory cost)
- Q9 (PRIORITY RULE — hallucination prevention)
- Q18 (embedding model consistency at ingest vs query time)
