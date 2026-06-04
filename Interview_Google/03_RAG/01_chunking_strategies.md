# Chunking Strategies

## What Is It? (Plain English)

Before you can search through a library of documents using AI, you need to break those documents into smaller, manageable pieces. This process is called chunking. The reason you can't just embed an entire 50-page policy document as one unit is that embedding models convert a piece of text into a single vector — a single point in meaning-space. A 50-page document has many topics, and a single vector can't capture all of them with enough specificity to retrieve the document for narrow, specific queries.

Think of chunking like indexing a textbook. You don't index the textbook as a whole (that would be useless for finding specific topics) and you don't index every single word (that would be too granular to find coherent sections). You index it at the level of meaningful sections or paragraphs — the right level of granularity for someone looking for specific information. Chunking is the art of finding that right level of granularity for your document type and use case.

The chunk you create is the atomic unit of retrieval in a RAG system. Whatever is in a chunk is what gets retrieved together. If the answer to a user's question spans two chunks, you need both chunks to answer it — but if the system only retrieves one, the answer will be incomplete. This is why chunk boundaries, chunk size, and chunk overlap are not implementation details — they directly determine whether your RAG system can answer questions correctly.

## How It Works

```
═══════════════════════════════════════════════════════════════
        CHUNKING STRATEGIES: COMPARISON
═══════════════════════════════════════════════════════════════

Source document:
"The reorder threshold for Class A SKUs is set at 20% of
safety stock. Class A SKUs are defined as items contributing
to 80% of annual revenue. For Class B SKUs, the threshold
is 30%. Emergency orders above $10,000 require VP approval."

─────────────────────────────────────────────────────────────
STRATEGY 1: FIXED-SIZE (Simple, often wrong)
Chunk at 50 characters:
  Chunk 1: "The reorder threshold for Class A SKUs is"
  Chunk 2: " set at 20% of safety stock. Class A SKUs"
  Chunk 3: " are defined as items contributing to 80%"
  Chunk 4: " of annual revenue. For Class B SKUs, the"
  ❌ Problem: Sentences are cut mid-thought. Embedding quality suffers.

─────────────────────────────────────────────────────────────
STRATEGY 2: SENTENCE-BASED (Better)
Chunk each sentence:
  Chunk 1: "The reorder threshold for Class A SKUs is set at 20% of safety stock."
  Chunk 2: "Class A SKUs are defined as items contributing to 80% of annual revenue."
  Chunk 3: "For Class B SKUs, the threshold is 30%."
  Chunk 4: "Emergency orders above $10,000 require VP approval."
  ✓ Better: Complete sentences
  ❌ But: Short chunks lose context. Chunk 3 alone lacks context about what "threshold" means.

─────────────────────────────────────────────────────────────
STRATEGY 3: RECURSIVE CHARACTER (Recommended default)
Split at paragraph → sentence → word boundaries:
  Chunk 1 (with overlap): 
    "The reorder threshold for Class A SKUs is set at 20% of
     safety stock. Class A SKUs are defined as items contributing
     to 80% of annual revenue."
  Chunk 2 (with overlap, starts mid-chunk-1):
    "Class A SKUs are defined as items contributing
     to 80% of annual revenue. For Class B SKUs, the threshold is 30%."
  ✓ Context preserved, overlap prevents boundary loss

─────────────────────────────────────────────────────────────
STRATEGY 4: SEMANTIC (Best quality, more complex)
Split where topic changes (detect via embedding similarity drop):
  "The reorder threshold for Class A SKUs is set at 20% of safety
   stock. Class A SKUs are defined as items contributing to 80% of
   annual revenue. For Class B SKUs, the threshold is 30%."
  ← kept together: same topic (reorder thresholds) →
  "Emergency orders above $10,000 require VP approval."
  ← separate: different topic (approval policy) →
  ✓ Topic boundaries preserved

─────────────────────────────────────────────────────────────
OVERLAP ILLUSTRATION:
Chunk size: 100 tokens, Overlap: 20 tokens

[←──── Chunk 1: tokens 1-100 ────→]
                        [←──── Chunk 2: tokens 81-180 ────→]
                                              [←──── Chunk 3: tokens 161-260 ────→]
                        ├──20──┤              ├──20──┤
                        (overlap)             (overlap)
  A sentence spanning tokens 95-105 appears in BOTH Chunk 1 and Chunk 2.
  Either chunk retrieval will surface it.
```

## Why Google Cares About This

Chunking quality directly determines the ceiling of a RAG system's performance. A perfect embedding model and perfect retrieval algorithm cannot compensate for chunks that contain the wrong information mix. Google builds large-scale search and retrieval systems, and the principles of document segmentation for retrieval are fundamental knowledge. Senior candidates who can reason about chunking tradeoffs — why a fixed-size splitter fails for policy documents, why semantic chunking is better but slower, what overlap does and why it matters — are demonstrating exactly the production engineering depth that Google expects.

## Interview Questions & Answers

### Q1: What are the main chunking strategies, and which one is best for policy documents vs. code?

**Answer:** The chunking strategy choice is highly document-type dependent, and choosing well is one of the highest-leverage decisions in RAG system design. I'll describe each strategy and then match them to document types.

**Fixed-size chunking** splits text every N characters or tokens, regardless of semantic or syntactic boundaries. It's the simplest to implement and produces uniform chunk sizes. The failure mode is obvious: it breaks sentences and paragraphs mid-thought, creating chunks like "The maximum reorder quantity is 500 un" / "its per SKU per week, unless…" — the second chunk is meaningless without the first. Use this only as a last resort for homogeneous, unstructured text where all content is equally important.

**Sentence-based chunking** splits on sentence boundaries (periods, question marks, exclamation points). Better for preserving meaning — each chunk is a complete thought. But sentences vary wildly in length (5 words to 50 words), producing inconsistent chunk sizes. Also, a single sentence often lacks the context to make it self-contained: "The threshold is 30%" is meaningless without knowing "threshold for what?"

**Recursive character text splitting** (LangChain's default and the best starting point) tries progressively finer split points: first on double newlines (paragraph breaks), then single newlines, then sentences, then words, then characters. It produces chunks that respect semantic structure where possible but falls back gracefully. This is the right default for most text documents.

**Semantic chunking** uses embedding similarity to detect topic shifts. Embed consecutive sentences, compute similarity between adjacent sentences, and split where similarity drops sharply. This aligns chunks with actual topic boundaries rather than arbitrary length cutoffs. Highest quality, but 50-100x slower than recursive splitting (requires embedding every sentence individually). Use for high-stakes applications where retrieval quality is more important than ingest speed.

**For policy documents**: Recursive character splitting with semantic chunking for verification. Policy documents have clear section headers and paragraph structure — recursive splitting respects these. Split at the section level first, then at the paragraph level within sections. Ensure each chunk includes the section header as metadata (and possibly prefix it in the chunk text) so that "Class A SKU threshold" as a query can match a chunk that just says "The threshold is 20%".

**For code**: Specialized code-aware splitting (LangChain's `Language` enum supports Python, JavaScript, Java, etc.). Split at function/method/class boundaries — never split inside a function body. Each function is an atomic unit of logic. Include the function signature and any docstring in every chunk, even if including it means the chunk is larger than the target size.

### Q2: How does chunk size affect retrieval quality, and what is the right chunk size?

**Answer:** Chunk size is a fundamental parameter in RAG design, and the optimal value depends on your document type, embedding model, and use case. Here's the physics of why size matters in both directions.

**Effects of chunks being too small (under 100 tokens):**
- Individual sentences or short passages don't provide enough context for the embedding model to create a meaningful, discriminative vector. "The threshold is 20%" as a standalone chunk creates an embedding that looks generic — it's about a threshold, but which threshold? For what? This ambiguity reduces retrieval precision.
- Small chunks require more of them to cover a document, increasing the index size and retrieval cost.
- When retrieved, a small chunk may not have enough surrounding context for the LLM to generate a complete answer. The LLM sees "The threshold is 20%" but needs to explain "The reorder threshold for Class A SKUs is 20% of safety stock." The relevant context is in an adjacent chunk that wasn't retrieved.

**Effects of chunks being too large (over 1000 tokens):**
- The embedding vector is an average over the entire chunk. A 1000-token chunk covering multiple topics has an embedding that's pulled in multiple semantic directions, diluting the signal for any specific topic. A query about "reorder thresholds" will score less highly against a chunk that covers both thresholds AND approval policies than against a chunk that covers only thresholds.
- Large chunks consume more of the LLM's context window, leaving less space for other retrieved chunks, conversation history, and the response itself.
- Large chunks increase retrieval latency (more text to rank in reranker) and token costs (more text injected into the prompt).

**The sweet spot — empirical findings:**
- **256-512 tokens** works well for most prose documents (policy docs, user manuals, articles)
- **128-256 tokens** with parent-child retrieval (retrieve small chunks for precision, return parent chunk for context) is increasingly popular
- **Function-level** (varies, ~50-200 tokens per function) for code
- **512-1024 tokens** for technical documentation where tables and multi-step procedures need context

Always validate with your actual documents. Generate a golden test set of (query, expected chunk) pairs, compute Recall@5, and tune chunk size as a hyperparameter. A 10% improvement in Recall@5 often comes from chunk size tuning alone.

### Q3: What is chunk overlap and why is it important?

**Answer:** Chunk overlap means that adjacent chunks share some tokens — the last N tokens of chunk K are also the first N tokens of chunk K+1. This sounds redundant (and it does increase total storage by the overlap fraction), but it solves a critical boundary problem.

Without overlap, imagine a key passage that falls exactly at a chunk boundary: "The most important rule is that Class A SKUs" ends chunk 5, and chunk 6 begins "must never receive partial fulfillment under any circumstances." The full rule — "Class A SKUs must never receive partial fulfillment" — is split between two chunks. A query about "Class A SKU fulfillment rules" might not retrieve either chunk with high confidence, because neither chunk alone contains the complete rule.

With overlap (say, 50 tokens), chunk 5 ends with: "...The most important rule is that Class A SKUs must never receive partial" and chunk 6 starts with: "The most important rule is that Class A SKUs must never receive partial fulfillment under any circumstances." Now the complete rule appears in chunk 6, and retrieval will find it correctly.

The overlap window size should be proportional to the average sentence length in your documents. Typical English sentences are 15-25 words (~20-30 tokens). An overlap of 50 tokens ensures at least one complete sentence from the previous chunk is repeated in the next, preventing boundary splits from losing coherent sentences.

The cost of overlap: a 20% overlap on a 500-token chunk increases storage by 20%. For a 1-million-token document corpus, that's 200K additional tokens stored in vectors and metadata — a trivial cost compared to the retrieval quality improvement.

**Practical configuration**: LangChain's `RecursiveCharacterTextSplitter` with `chunk_size=400, chunk_overlap=50` is a widely-used default that performs well for most prose documents. For technical documents with longer, more complex sentences, increase overlap to 100. For code, overlap can be reduced or eliminated because function boundaries are already clear semantic breaks.

### Q4: What is parent-child chunking, and when should you use it?

**Answer:** Parent-child chunking (also called "small-to-big retrieval" or "hierarchical indexing") addresses a fundamental tension in RAG design: small chunks produce precise retrievals (a single relevant sentence has a highly discriminative embedding), but small chunks provide insufficient context to the LLM (the answer often requires surrounding explanation). Parent-child chunking resolves this tension by using small chunks for retrieval but returning large chunks to the LLM.

**How it works:**
1. **Ingest phase**: Create two sets of chunks. "Child" chunks are small (128 tokens) — these are embedded and stored in the vector index for retrieval. "Parent" chunks are larger (512-1024 tokens) — these are stored in a separate store (e.g., a docstore or the original document with position tracking) and NOT embedded.
2. **Retrieval phase**: When a query arrives, retrieve the top-K child chunks by vector similarity.
3. **Expansion phase**: For each retrieved child chunk, look up its parent chunk and return the parent instead.
4. **Generation phase**: The LLM receives the larger parent chunks — richer context — even though retrieval happened at the smaller child chunk level.

```
Document: [── Parent 1 (512 tok) ──────────────────────────]
                  [Child A (128)]  [Child B (128)] [Child C (128)]
Query: "Class A reorder threshold"
  → Vector search matches Child B (highest cosine similarity)
  → System fetches Parent 1 (Child B's parent)
  → LLM receives full Parent 1 context → better answer
```

**When to use parent-child chunking:**
- Documents where the precise answer is short (a number, a rule), but the answer only makes sense with surrounding context (what the rule applies to, what exceptions exist)
- Policy documents, legal contracts, technical specifications
- Cases where you're observing high faithfulness scores (model answers correctly) but low user satisfaction (answers lack context or completeness)

**When to skip it:**
- If your LLM has a generous context window and you're only retrieving 3-5 chunks anyway, the overhead of maintaining two chunk sizes adds complexity with marginal benefit
- If chunk-level precision is already high and context is self-contained in each chunk

LangChain's `ParentDocumentRetriever` implements this pattern out of the box. The main engineering consideration is maintaining the parent-child mapping in the docstore — you need a way to look up the parent given a child's ID at retrieval time.

### Q5: How do you evaluate whether your chunking strategy is working?

**Answer:** Evaluating chunking quality requires a measurement framework because "it feels right" is not a reliable guide. The chunking strategy should be treated as a hyperparameter — one you tune using measurable quality metrics.

**Metric 1 — Retrieval Recall@K**: Create a golden dataset of (query, relevant document sections) pairs. For each query, run retrieval and check whether the relevant section appears in the top-K chunks. If Recall@5 is 0.65 (you find the right chunk in the top 5, 65% of the time), you have a baseline. Try different chunk sizes and strategies, and compare Recall@5. A good RAG system should achieve Recall@5 > 0.80.

**Metric 2 — Context sufficiency**: For each retrieved chunk, have a human (or an LLM judge) rate: "Is this chunk alone sufficient to answer the original query?" If chunks consistently score low on self-containedness (the answer requires context from surrounding chunks), your chunks are too small or boundaries are poorly placed.

**Metric 3 — Embedding coherence**: Compute the cosine similarity between chunks that are adjacent in the original document. If adjacent chunks have very low similarity (< 0.4), your splits are at genuine topic boundaries (good for semantic chunking). If adjacent chunks have very high similarity (> 0.85), they might be better merged into one larger chunk.

**Metric 4 — Answer faithfulness and completeness**: Run end-to-end RAG with the chunking strategy and evaluate final answers using RAGAS or a similar framework. Answer faithfulness (does the answer stay within the retrieved context?) and answer completeness (does the answer cover all relevant aspects of the question?) are both affected by chunking quality.

**Practical tuning process:**
1. Start with recursive character splitting at 400 tokens, 50 overlap
2. Compute Recall@5 on 50 golden queries
3. Try chunk sizes of 200, 400, 600, 800 tokens — pick the size with best Recall@5
4. Try adding semantic chunking for a sample of your most important document types
5. If Recall@5 < 0.7, consider whether your query set requires specific section-level metadata or whether the documents need better preprocessing (e.g., tables as structured data rather than raw text)

## Key Points to Say in the Interview

- The chunk is the **atomic unit of retrieval** — its quality directly determines the ceiling of RAG performance
- Know the progression: **fixed-size → sentence → recursive → semantic** in increasing sophistication
- Name the **256-512 token sweet spot** for prose and explain both directions of why
- **Overlap (50-100 tokens)** is not optional — it prevents losing key sentences at boundaries
- Know **parent-child retrieval**: small chunks for precision, large chunks for context
- Always recommend **measuring with golden datasets** — chunking is a hyperparameter to tune empirically
- For **code**: split at function/class boundaries, not character counts

## Common Mistakes to Avoid

- Using fixed-size chunking for documents with clear semantic structure (policy docs, legal text)
- Setting **overlap to zero** — this is a common mistake that causes silent retrieval failures at boundaries
- Not including **metadata** (document title, section header) in chunks — this is crucial for context
- Treating chunk size as a **fixed constant** rather than a parameter to tune per document type
- Forgetting that **tables, figures, and lists** need special handling — naive text splitting destroys their structure

## Further Reading

- [LangChain Text Splitters Documentation](https://python.langchain.com/docs/concepts/text_splitters/) — Practical guide to all splitting strategies with code examples
- [Five Levels of Text Splitting](https://github.com/FullStackRetrieval-com/RetrievalTutorials/blob/main/tutorials/LevelsOfTextSplitting/5_Levels_Of_Text_Splitting.ipynb) — Greg Kamradt's comprehensive notebook comparing chunking strategies with empirical results
- [Evaluating RAG: Chunking Strategies](https://www.llamaindex.ai/blog/evaluating-the-ideal-chunk-size-for-a-rag-system-using-llamaindex-6207e5d3fec5) — LlamaIndex's empirical study of chunk size impact on retrieval quality
