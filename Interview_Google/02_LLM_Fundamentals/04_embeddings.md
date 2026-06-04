# Embeddings

## What Is It? (Plain English)

An embedding is a way to represent the meaning of text as a list of numbers — a vector. The key insight is that words and sentences that have similar meanings end up with similar vectors, while unrelated words end up with dissimilar vectors. This is what makes "semantic search" possible: you can find documents that are *about* the same thing even if they use completely different words.

Think of it like placing every word on a map. Words that are related get placed near each other on the map: "king" and "queen" are close together, as are "dog" and "cat," and "happy" and "joyful." But "king" and "banana" are far apart. The position on this map is the embedding — a list of numbers representing coordinates in a high-dimensional space (usually 384 to 1,536 dimensions). When you want to find documents similar to a query, you convert both the query and the documents into these coordinates, then look for the documents whose coordinates are closest to the query's coordinates.

The famous example from Word2Vec (2013): if you take the vector for "king," subtract the vector for "man," and add the vector for "woman," you get a vector that's very close to the vector for "queen." This means the embedding space has captured the relationship between royalty and gender — not because we programmed this, but because the model learned it from the patterns in text. This kind of geometric representation of meaning is the foundation of semantic search, recommendation systems, clustering, and all of RAG (Retrieval-Augmented Generation).

## How It Works

```
═══════════════════════════════════════════════════════════════
          HOW EMBEDDINGS CAPTURE SEMANTIC SIMILARITY
═══════════════════════════════════════════════════════════════

Training:
  Model reads billions of sentences.
  Words/phrases appearing in similar contexts → similar embeddings.
  "He got a loan from the bank" and "She deposited at the bank" →
  "bank" (financial) embedding differs from "river bank" embedding.

Word2Vec intuition (simplified):
  Predict neighbors from center word. Update weights to make
  the predictions better. After training, weights = embeddings.

  "The dog chased the cat"
        ↕      ↕
  "dog" learns to be similar to: pet, animal, run, chase, bark
  "cat" learns to be similar to: pet, animal, meow, purr, feline

Result in 3D (simplified from actual 768-dim):
  "dog"     → [0.8, 0.3, -0.2]
  "cat"     → [0.7, 0.4, -0.3]  ← close to dog
  "car"     → [-0.5, 0.9, 0.6]  ← far from dog/cat
  "vehicle" → [-0.4, 0.8, 0.7]  ← close to car

═══════════════════════════════════════════════════════════════
          SENTENCE EMBEDDINGS FOR RAG SEARCH
═══════════════════════════════════════════════════════════════

Query: "How do I return a product?"
Document A: "Our return policy allows refunds within 30 days."
Document B: "The weather forecast shows rain tomorrow."

Step 1: Embed query and documents
  embed("How do I return a product?")  → [0.23, -0.51, 0.88, ...]
  embed("Our return policy allows...")  → [0.21, -0.48, 0.85, ...]  ← similar!
  embed("The weather forecast...")      → [-0.71, 0.32, -0.11, ...] ← different

Step 2: Compute cosine similarity
  cosine_sim(query, doc_A) = 0.94  ← HIGH similarity
  cosine_sim(query, doc_B) = 0.12  ← LOW similarity

Step 3: Retrieve doc_A as relevant context
  → Document A is surfaced, Document B is filtered out

═══════════════════════════════════════════════════════════════
          DISTANCE METRICS COMPARISON
═══════════════════════════════════════════════════════════════

Cosine Similarity:
  Range: [-1, 1], where 1 = identical direction, 0 = orthogonal, -1 = opposite
  Formula: cos(θ) = (A·B) / (|A| × |B|)
  Best for: Text similarity — ignores magnitude, only measures direction
  Use when: Comparing the "meaning" of texts regardless of length
  
Dot Product:
  Range: (-∞, +∞)
  Formula: A·B = Σ(a_i × b_i)
  Best for: Faster (no normalization), used when vectors ARE normalized
  Use when: Maximum performance in vector databases with normalized vectors

Euclidean Distance (L2):
  Range: [0, +∞), where 0 = identical
  Formula: √(Σ(a_i - b_i)²)
  Best for: Low-dimensional spaces, when magnitude carries meaning
  Use when: Image feature similarity, audio embeddings

For text/RAG: USE COSINE SIMILARITY (or dot product with normalized vectors)
```

## Why Google Cares About This

Embeddings are the foundation of Google Search's semantic understanding, Google's recommendation systems (YouTube, Play Store, Google Maps), and every RAG application. When a senior candidate understands embeddings deeply — what makes a good embedding model, how to choose dimensions, what MTEB benchmark is, why cosine vs. dot product matters — they're demonstrating they can make informed architectural decisions for AI systems rather than just using whichever default embedding appears in a tutorial. Google's own embedding models (Universal Sentence Encoder, Gecko) are trained for specific downstream tasks, and understanding the training objectives and their implications for retrieval quality is fundamental knowledge for a senior AI/ML engineer at Google.

## Interview Questions & Answers

### Q1: What are embeddings, and how do they enable semantic search?

**Answer:** An embedding is a fixed-length, dense vector of floating-point numbers that represents the semantic meaning of a piece of text. "Dense" means most numbers are non-zero (contrast with sparse representations like TF-IDF vectors, where most entries are zero). "Fixed-length" means the vector has the same dimensionality (say, 768 numbers) regardless of whether the input was a 5-word phrase or a 5,000-word document.

The key property that makes embeddings useful is that **semantic similarity maps to geometric proximity**: texts with similar meanings have similar vectors, as measured by cosine similarity. "What is the weather like?" and "How is the weather today?" should have vectors very close to each other in the embedding space, even though they share no words except "the" and "weather." This is learned from data: an embedding model trained on billions of text passages learns that certain phrases co-occur in the same contexts and should have similar representations.

Semantic search works by converting both the query and all documents in the knowledge base into embedding vectors, then finding documents whose vectors are closest to the query vector. This is a **vector search** problem. For small datasets, you can do brute-force comparison (compute cosine similarity between the query and every document). For large datasets, you use an approximate nearest neighbor (ANN) index (like HNSW) to find close vectors efficiently without comparing every pair.

The contrast with traditional keyword search illustrates the value: keyword search for "canine vaccines" returns documents containing those exact words; semantic search additionally returns documents about "dog immunizations" and "puppy shots" — because the embedding of "canine vaccines" is close to the embeddings of those related phrases. This is why semantic search dramatically outperforms keyword search for natural language queries, and why it's the retrieval foundation of RAG.

The limitation: semantic similarity is not always the same as topical relevance. An embedding model might place "What are the symptoms of COVID?" close to "The patient reported fever and cough" — semantically related — even if the specific document is not the most useful one. This is why reranking (using a more expensive cross-encoder that considers the full (query, document) pair jointly) is often used after initial embedding-based retrieval.

### Q2: How are sentence embeddings trained, and what makes one embedding model better than another?

**Answer:** The dominant approach for training sentence embedding models today is **contrastive learning** — specifically, training the model to map semantically similar (query, document) pairs close together and semantically dissimilar pairs far apart in the embedding space.

The most influential framework is **SBERT (Sentence-BERT)** by Reimers & Gurevych (2019). The key insight was that BERT, while producing excellent token-level embeddings, produced poor sentence-level embeddings when naively pooled (the [CLS] token or mean of all token embeddings). SBERT fine-tuned BERT using siamese network training: feed two sentences through the same BERT model, compare their pooled embeddings, and update weights to make similar sentence pairs more similar and dissimilar pairs more different.

Modern embedding models (BGE, nomic-embed, E5, GTE) use **multiple stages of training**:
1. **Pre-training**: Start from a large pre-trained language model (BERT, RoBERTa, or a decoder model like LLaMA) that already has strong language understanding
2. **Large-scale contrastive pre-training**: Train on hundreds of millions of (query, positive passage, negative passage) triplets. Positive passage = a passage that answers the query. Negative passage = a passage from a different topic. Loss function: minimize distance to positive, maximize distance to negatives. This builds strong retrieval capability.
3. **Fine-tuning on specific tasks**: Fine-tune on a mixture of labeled datasets (NLI, semantic similarity, QA pairs) to improve performance across evaluation benchmarks.

**What makes an embedding model better:**
- **Dimensionality**: Higher-dimensional embeddings (1536 vs 384) can capture more nuance but cost more storage and are slower to compare. Dimension is not the same as quality — a well-trained 384-dim model can outperform a poorly-trained 1536-dim model.
- **Training data**: Models trained on domain-specific data (scientific text, code, legal text) typically outperform general models on that domain.
- **Sequence length**: Some models are limited to 512 tokens input; others support 8192 or more. For embedding long documents, maximum sequence length matters.
- **MTEB benchmark score**: The Massive Text Embedding Benchmark evaluates embedding models across 56 tasks (retrieval, clustering, classification, etc.). Sort by the Retrieval MTEB score for RAG applications specifically. As of 2024, top models: text-embedding-3-large (OpenAI), nomic-embed-text-v1.5 (Nomic, open-source), BGE-M3 (BAAI, multilingual).

**License matters in production**: OpenAI's embedding models have commercial usage in their terms; open-source models like nomic-embed, BGE, and Sentence Transformers can be self-hosted for free and without data sharing restrictions.

### Q3: How do you choose between cosine similarity, dot product, and Euclidean distance for comparing embeddings?

**Answer:** The right choice depends on whether the embeddings are normalized and what geometric property best captures "similarity" for your use case. For text embeddings in RAG, cosine similarity or dot product on normalized vectors is almost always the right choice.

**Cosine similarity** measures the angle between two vectors, ignoring their magnitude. It ranges from -1 (opposite directions) to +1 (same direction). The formula is the dot product of the two vectors divided by the product of their magnitudes. For text, magnitude carries no meaningful information — a long document and a short document about the same topic should be equally "similar" to a query, even though the long document's embedding might have higher magnitude simply because it contains more text. By normalizing out the magnitude, cosine similarity gives us pure directional similarity — that is, "are these texts pointing in the same semantic direction?"

**Dot product** is faster to compute (no normalization step) and is equivalent to cosine similarity when both vectors are L2-normalized to length 1. Most embedding models normalize their outputs, making dot product the practical choice in vector databases where speed matters. Pinecone's "cosine" metric actually computes the dot product after normalizing, so they're equivalent there.

**Euclidean (L2) distance** measures the straight-line distance between two vector endpoints. It considers both direction AND magnitude. For text embeddings, this is usually suboptimal because magnitude doesn't have a consistent semantic meaning. However, Euclidean distance performs well for image feature embeddings and audio embeddings where magnitude does carry information. For clustering algorithms (k-means), Euclidean distance is the standard.

**Practical decision table:**
```
Are embeddings L2-normalized?
  YES → Use dot product (fastest, equivalent to cosine)
  NO  → Use cosine similarity (normalizes out spurious magnitude effects)

Is the task text similarity / semantic search?
  → Cosine / dot product (ignore magnitude)

Is the task image/audio feature matching?
  → Could use Euclidean (magnitude may matter)

Is the task clustering?
  → Euclidean distance (k-means assumption)
```

**Negative inner product**: Some vector databases (Faiss) use "negative inner product" for maximum inner product search — they invert the score so the "nearest" neighbor has the smallest negative inner product. This is just an implementation detail, not a different metric.

### Q4: What is MTEB and how do you use it to select an embedding model for your use case?

**Answer:** MTEB (Massive Text Embedding Benchmark) is the standard evaluation benchmark for embedding models, published by Hugging Face researchers in 2022. It evaluates models across 56 datasets and 8 task categories: bitext mining, classification, clustering, pair classification, reranking, retrieval, semantic textual similarity (STS), and summarization. It's the "ImageNet" of embedding evaluation — the community standard for comparing models.

The MTEB leaderboard (huggingface.co/spaces/mteb/leaderboard) shows hundreds of models ranked by average score across all tasks, and importantly, ranked by individual task category. For building a RAG system, **don't look at the overall average** — look at the **Retrieval** sub-score. A model optimized for STS (sentence similarity) may not be the best for retrieval-style tasks where the query and document have different styles ("What is the refund policy?" vs "Refunds are processed within 7-10 business days").

**How to read MTEB for RAG selection:**
1. Filter to "Retrieval" task category
2. Consider max sequence length (for long documents, need 512+ tokens)
3. Consider model size (larger = slower; check inference latency)
4. Consider license (commercial use requires specific licenses)
5. Consider language (multilingual MTEB for non-English content)
6. Shortlist top 3, run on a **sample of your actual data** — MTEB scores on generic benchmarks don't always transfer to domain-specific content

As of 2024, strong choices for RAG:
- **OpenAI text-embedding-3-small**: Excellent quality, low cost, managed API (no infra)
- **nomic-embed-text-v1.5**: Top open-source option, Apache 2.0 license, supports 8192 context
- **BGE-M3**: Best multilingual option, strong MTEB retrieval score, self-hostable
- **Cohere embed-v3**: Strong all-around, designed for enterprise RAG

**Fine-tuning embeddings**: For domain-specific content (medical, legal, financial), generic embedding models often underperform. Fine-tuning on (query, relevant document, irrelevant document) triplets from your domain can improve retrieval recall by 10-20%. The cost: you need labeled data (manually curated positive/negative pairs) and compute for fine-tuning. This investment is worth it for mature production systems but not for early-stage development.

### Q5: How do you handle long documents that exceed an embedding model's maximum input length?

**Answer:** This is a critical practical challenge because many embedding models are limited to 512 tokens (roughly 380 words), while real-world documents can be thousands of words. Several strategies exist, each with different quality-versus-complexity tradeoffs.

**Truncation (simplest, often wrong)**: Take only the first 512 tokens of the document and embed those. This works only if the relevant information consistently appears at the beginning of the document (executive summaries, news articles). For many document types (legal contracts, research papers, policy documents), the most relevant information may be in the middle or end. Truncation systematically loses this information.

**Chunking (standard RAG approach)**: Split the document into smaller pieces (256-512 tokens each, with overlap) and embed each chunk separately. This is the standard approach for RAG — the ingest pipeline produces many chunk embeddings per document, and retrieval returns individual chunks rather than full documents. The quality of this approach depends heavily on the chunking strategy: splitting mid-sentence loses coherence; splitting at paragraph boundaries preserves it. This is covered in depth in the Chunking Strategies file.

**Sliding window with max pooling**: Embed the document using a sliding window (embed tokens 1-512, then 257-768, then 513-1024...) with overlap, producing multiple embedding vectors for one document. Then aggregate: take the element-wise maximum across all window embeddings. The intuition: the maximum captures the "most activated" semantic dimensions across the document. This produces one embedding for the full document, though it loses fine-grained positional information. Useful for document-level classification or deduplication.

**Hierarchical embedding**: First embed all chunks of a document, then embed a summary of those chunk embeddings (mean pooling), then optionally embed a manually curated abstract if one exists. The hierarchy creates embeddings at multiple granularities — chunk-level for fine-grained retrieval, document-level for broader contextual matching. Some RAG systems combine both: retrieve at the chunk level but use document-level embeddings to boost the score of chunks from highly relevant documents.

**Long-context embedding models**: Models like nomic-embed-text-v1.5 (8192 tokens) and models in the Voyage and Jina families support much longer input sequences. This eliminates the truncation problem for most documents. The trade-off is slower embedding (quadratic attention applies here too) and higher cost per document. For production RAG, moving to a long-context embedding model is often the cleanest architectural choice when document length is a concern.

## Key Points to Say in the Interview

- Embeddings are **dense vectors where geometric proximity = semantic similarity** — this is the core concept
- Know **cosine similarity** for text: ignores magnitude, measures direction of meaning
- Know **MTEB benchmark** for comparing embedding models — filter to "Retrieval" sub-score for RAG
- For RAG, name **nomic-embed, BGE-M3, text-embedding-3-small** as current strong choices
- Mention **fine-tuning embeddings** on domain data as a route to significantly better RAG performance
- Know the **long document problem**: chunking (standard), sliding window, hierarchical, long-context models
- Word2Vec's "king - man + woman = queen" is the classic analogy — use it to explain the concept

## Common Mistakes to Avoid

- Saying embeddings are "one number per word" — they are **high-dimensional vectors** (hundreds to thousands of dimensions)
- Confusing embedding models with generative LLMs — embeddings are for **representation**, not generation
- Not knowing that **MTEB Retrieval score** is what matters for RAG (not overall MTEB average)
- Forgetting that different embedding models **cannot be compared** in the same vector database (you must re-embed all documents when switching models)
- Saying "just use OpenAI embeddings" without knowing the **open-source alternatives** — shows limited depth

## Further Reading

- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) — The definitive ranking of embedding models by task type
- [Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks](https://arxiv.org/abs/1908.10084) — The paper that launched modern sentence embedding
- [Lilian Weng — Learning Word Embedding](https://lilianweng.github.io/posts/2017-10-15-word-embedding/) — Deep dive on Word2Vec, GloVe, and the mathematics of word embeddings
