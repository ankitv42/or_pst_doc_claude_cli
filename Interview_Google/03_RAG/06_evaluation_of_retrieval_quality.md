# Evaluation of Retrieval Quality

## What Is It? (Plain English)

Evaluating retrieval quality means answering a simple question: when a user asks a question, does your RAG system pull back the right documents? This sounds obvious, but it's surprisingly hard to measure well. You can't just ask "did the final answer look right?" — a good-looking answer might be hallucinated, or the correct document might have been retrieved but ignored by the LLM, or the wrong document might have been retrieved but coincidentally contained a useful fact.

To measure retrieval specifically, you need a golden dataset: a set of questions paired with which documents (or document chunks) should ideally be retrieved. Then you can measure precisely how often your retrieval system returns the right documents — independently of what the LLM does with them. This separates the "retrieval problem" from the "generation problem," which is essential for debugging a broken RAG pipeline.

Metrics like Recall@K, Precision@K, MRR, and NDCG give you different lenses on retrieval quality. Recall@K tells you if the right document was anywhere in the top K. Precision@K tells you if the top K was mostly relevant. MRR tells you if the right document was near the top. NDCG handles cases where there are multiple degrees of relevance. Each metric surfaces a different failure mode, and a production RAG system should track all of them.

## How It Works

```
Evaluation Framework Overview
────────────────────────────────────────────────────────────────
Golden Dataset:
  Query Q1: "What is the reorder threshold for Class A items?"
  Expected: [chunk_id_47, chunk_id_52]

  Query Q2: "When is human approval required for orders?"
  Expected: [chunk_id_18]

             │
             ▼
  Retrieval System returns for Q1:
  [chunk_id_52, chunk_id_88, chunk_id_47, chunk_id_12, chunk_id_31]
  (ranked list of top-5 retrieved chunks)

             │
             ▼
  Compute Metrics:
  ┌──────────────────────────────────────────────────────────┐
  │ Recall@5:   both chunk_47 and chunk_52 in top-5? YES → 1.0│
  │ Precision@5: 2 of 5 retrieved are relevant → 0.40         │
  │ MRR:        chunk_52 at rank 1 → 1/1 = 1.0               │
  │ NDCG@5:     gains weighted by rank position               │
  └──────────────────────────────────────────────────────────┘

  Average over all queries in the golden dataset
  → Overall Recall@5, Precision@5, MRR, NDCG@5
────────────────────────────────────────────────────────────────
```

**Metric formulas:**

```
Recall@K    = (relevant docs in top-K) / (total relevant docs)

Precision@K = (relevant docs in top-K) / K

MRR         = (1/|Q|) * Σ  1 / rank_of_first_relevant_doc
                         q

NDCG@K      = DCG@K / IDCG@K
where DCG@K = Σ  (2^rel_i - 1) / log2(i + 1)
               i=1..K
and IDCG@K  = DCG@K of the ideal (perfect) ranking
```

## Why Google Cares About This

Google's production LLM systems (Search, Bard/Gemini grounding, Vertex AI Search) are evaluated rigorously before any change ships. The ability to design an eval framework — define golden datasets, choose the right metrics, run evals without LLM API calls — is a senior ML engineer skill. In interviews, explaining how you would debug a drop in RAG answer quality (trace it to retrieval metrics first, then generation) demonstrates systematic thinking. ORCA's Layer 1 eval is a direct example of this — 11 golden cases, no API key needed, runs in CI.

## Interview Questions & Answers

### Q1: What are Recall@K, Precision@K, MRR, and NDCG, and when would you use each for evaluating retrieval?

**Answer:** Each metric captures a different aspect of retrieval quality, and the right one to optimize depends on your use case.

**Recall@K** answers: "Did I find all the relevant documents?" It's defined as the fraction of all relevant documents that appear in the top-K retrieved results. If there are 3 relevant chunks for a query and your system retrieves 2 of them in the top-5, Recall@5 = 0.67. This metric is critical when missing a relevant document is costly — for example, in a medical RAG system where missing a drug interaction document could cause patient harm. In RAG pipelines, you typically want high recall at the retrieval stage because the LLM can ignore irrelevant documents, but it can't generate correct answers from documents it never saw.

**Precision@K** answers: "How clean is my retrieved set?" It's the fraction of top-K retrieved documents that are actually relevant. If you retrieve 5 documents and 2 are relevant, Precision@5 = 0.40. This matters when you're passing K documents directly to the LLM and context noise is a problem — too many irrelevant chunks dilute attention and degrade answer quality. The LLM context window is precious; every irrelevant chunk takes space away from relevant ones.

**MRR (Mean Reciprocal Rank)** answers: "How quickly do I surface the first relevant document?" It's the average of 1/rank for the first relevant document across queries. If the first relevant result is at rank 1 for one query and rank 3 for another, MRR = 0.5*(1/1 + 1/3) = 0.67. MRR is relevant when only the single best document matters — for example, in a question-answering system where the top-1 result is shown prominently and only one answer is expected.

**NDCG (Normalized Discounted Cumulative Gain)** is the most sophisticated metric. It handles the case where documents have graded relevance (not just relevant/irrelevant) and penalizes systems that put highly relevant documents at low ranks. It's ideal when you have multiple levels of relevance ("perfect answer," "partial answer," "marginally relevant") and care about ranking quality throughout the list. For RAG with binary relevance labels, NDCG and MRR are correlated; NDCG becomes distinctly valuable when you have expert-annotated multi-level relevance scores.

For ORCA's Layer 1 eval, Recall@K is the primary metric — the goal is to confirm that the correct policy chunks appear somewhere in the retrieved context. The 11 golden test cases test whether specific keywords (proxy for specific documents) appear in the retrieval results.

### Q2: What is a golden dataset and how do you build one for a RAG system?

**Answer:** A golden dataset is a curated collection of (query, expected_document_set) pairs created by domain experts, used as ground truth for measuring retrieval quality. Building it well is the most important part of the evaluation framework — a poorly constructed golden dataset will give you metrics that don't reflect real user experience.

The construction process has four steps. First, collect representative queries. These should come from multiple sources: anticipated user questions (thought up by domain experts), actual user queries from logs (if you have production traffic), and adversarial queries designed to stress-test the system (paraphrase attacks, out-of-domain questions, ambiguous queries). For ORCA, relevant queries include "what is the approval threshold for reorders?" and "how should Class A SKUs be handled?" and "what is the lead time policy for critical inventory?"

Second, annotate which documents/chunks are relevant for each query. This is ideally done by domain experts who know the corpus well. For ORCA's policy documents, the engineers who wrote the policies annotate which chunks answer which questions. For large corpora, annotation can be expensive — you can partially automate it using an LLM to propose candidate relevant documents, then have humans validate (human-in-the-loop annotation).

Third, determine relevance levels. For simple binary relevance (relevant/not relevant), the annotation is straightforward. For graded relevance (perfect/partial/marginal/irrelevant), you get richer signal for NDCG computation but annotation is slower and less consistent between annotators (low inter-annotator agreement is a sign your rubric is unclear).

Fourth, ensure the dataset is balanced and doesn't overfit to easy queries. If all 11 golden cases test the exact topic headers from the policy documents, you're not testing whether the system handles paraphrase. ORCA's Layer 1 eval explicitly tests both keyword matching (what terms appear in results) and anti-leakage (what terms from the wrong documents do NOT appear), which is a more robust dual-criterion test.

### Q3: How does ORCA's Layer 1 evaluation work, and why does it require no API key?

**Answer:** ORCA's Layer 1 eval (`evals/run_retrieval_eval.py`) tests retrieval quality completely independently of the LLM. It calls the `query_for_agent*()` functions directly — the same functions the agents use — and examines the returned text strings. Since these functions run the BM25+vector hybrid search and optional reranking locally, without any API call to Groq or any other LLM service, the eval is runnable in a CI environment with zero cost and zero network dependency.

Each of the 11 golden test cases specifies: (1) an input query string, (2) a list of "expected keywords" — terms that must appear in the retrieved context if the right documents were found, and (3) a list of "anti-keywords" — terms from the wrong policy documents that must NOT appear (testing for cross-document contamination). A test case passes if all expected keywords are found and no anti-keywords are present.

This design has a notable advantage and a notable limitation. The advantage: it's extremely fast to run (seconds, not minutes), requires no LLM, and produces a stable pass/fail CI gate. You can catch retrieval regressions immediately when someone modifies the chunking strategy, changes the embedding model, or modifies document ingestion. The `.github/workflows/eval_gate.yaml` CI workflow runs this on every push to main.

The limitation: keyword presence is a proxy for document relevance, not a direct measure. A retrieved chunk might contain the expected keyword in a completely irrelevant context. The CLAUDE.md notes this explicitly as a "medium" known issue — the golden dataset keywords were written from memory and may not match exact document wording. The right fix is to annotate expected chunk IDs directly (not keywords), which requires reading the actual ingested chunks and assigning ground-truth IDs.

### Q4: What is the RAGAS framework and how does it extend beyond retrieval-only evaluation?

**Answer:** RAGAS (Retrieval-Augmented Generation Assessment) is an open-source evaluation framework published in 2023 that provides a suite of metrics specifically designed for end-to-end RAG pipeline evaluation. While retrieval metrics (Recall@K, MRR) only evaluate Stage 1, RAGAS adds generation-stage metrics that can be computed automatically using an LLM as a judge.

RAGAS defines four primary metrics:

**Context Recall** measures whether the retrieved context contains the information needed to answer the question, judged against a ground-truth answer. It's computed by breaking the ground-truth answer into atomic statements and checking how many of them are supported by the retrieved context. High context recall means the retrieval system found the right information.

**Context Precision** measures whether the retrieved context is focused (low noise). It asks: "given that the answer comes from these chunks, how many of the chunks are actually useful?" A system that retrieves 10 chunks when 2 were sufficient scores lower on context precision.

**Faithfulness** (covered in depth in `03_faithfulness.md`) measures whether the generated answer sticks to what was retrieved — no fabrication.

**Answer Relevance** measures whether the answer actually addresses the question asked. An answer can be faithful to the context but still miss the point of the question.

The power of RAGAS is that all four metrics can be computed automatically using an LLM (typically GPT-4) as the judge — no human annotation needed. This makes it practical for running after every code change. The limitation: the evaluating LLM is itself a source of variance and cost. Using GPT-4 to evaluate 1000 queries costs money and introduces LLM judge bias. ORCA's Layer 1 eval deliberately avoids this by working at the retrieval level only, with zero LLM calls.

### Q5: How would you debug a RAG system where answer quality has degraded — what's your diagnostic process?

**Answer:** Debugging RAG quality degradation requires isolating which component failed: retrieval, reranking, context construction, or LLM generation. The diagnostic ladder works from bottom to top.

Step 1: Run the retrieval eval. Before investigating the LLM, run your golden-dataset retrieval evaluation (e.g., ORCA's Layer 1 eval). If Recall@K has dropped, the problem is in retrieval — don't blame the LLM. Common retrieval regressions: embedding model changed or re-loaded incorrectly, document corpus updated without re-ingestion, chunking parameters changed, hybrid search weights misconfigured.

Step 2: Inspect specific failure cases. Pick 5–10 queries where the answer quality dropped. Manually run the retrieval step and look at what documents were returned. Are the expected documents in the top-5? If they're in top-20 but not top-5, the reranker is the problem. If they're not in top-20 at all, the vector search or BM25 step failed.

Step 3: Trace the LLM context. Take a query where retrieval looks correct (right documents in top-5) but the answer is still wrong. Inspect the exact context string passed to the LLM. Is the relevant information actually there, clearly expressed? Is it buried in irrelevant noise? Is the chunk cut in a way that removes the key sentence (chunking boundary problem)?

Step 4: Investigate the LLM prompt and generation. If the context is correct and complete, but the LLM's answer is still wrong, the problem is in the system prompt, the prompt structure, or (in degraded cases) model drift. Try the same context with a direct prompt outside your pipeline to isolate whether the generation logic is at fault.

For ORCA specifically, Agent 1's CrewAI sub-crew falls back to a raw-data demand summary when the Groq `cache_breakpoint` error occurs — which means the LLM receives a less structured context. This is a generation-level issue, not a retrieval issue, and debugging correctly requires distinguishing between the two.

## Key Points to Say in the Interview
- Recall@K is the primary retrieval metric for RAG — missing a relevant document cannot be compensated by the LLM
- Golden datasets must be built by domain experts annotating actual queries, not generated from document headers
- Separate the retrieval eval from the generation eval — running LLM-free retrieval tests in CI is cheap and fast
- RAGAS automates end-to-end evaluation using an LLM judge, but at the cost of API calls and judge variance
- Debug RAG quality by isolating the layer: retrieval → reranking → context construction → LLM generation
- ORCA's Layer 1 eval tests keyword presence as a retrieval proxy — a pragmatic approximation, but knows its limitations

## Common Mistakes to Avoid
- Measuring only final answer quality and assuming retrieval is fine (most RAG bugs are retrieval bugs)
- Building golden datasets with only easy, obvious queries — add paraphrases, edge cases, and adversarial examples
- Using MRR as the only metric when multiple relevant documents exist — MRR only measures the first hit
- Running RAGAS without inspecting individual failure cases — the aggregate metric hides which specific queries fail
- Not versioning the golden dataset — if you update the document corpus, the golden dataset annotations may become stale

## Further Reading
- [RAGAS: Automated Evaluation of Retrieval-Augmented Generation (arXiv)](https://arxiv.org/abs/2309.15217) — Original paper introducing the RAGAS evaluation framework
- [BEIR Benchmark Paper (arXiv)](https://arxiv.org/abs/2104.08663) — How retrieval metrics are computed at scale across diverse domains
- [Evaluation of RAG Systems — Hugging Face blog](https://huggingface.co/blog/rag-evaluation) — Practical guide to setting up a RAG eval pipeline
- [NDCG Explained — Towards Data Science](https://towardsdatascience.com/demystifying-ndcg-bee3be58cfe0) — Clear walkthrough of NDCG computation with examples
- [LangSmith Evaluation Docs](https://docs.smith.langchain.com/evaluation) — How to integrate retrieval evals into a LangChain/LangGraph pipeline using LangSmith's eval runner
