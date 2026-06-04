# ADR-004: Pre-Built ChromaDB Index Committed to Repository for CI

**Status:** Accepted  
**Date:** 2026-05-20  
**Authors:** ORCA Engineering

---

## Context

The retrieval eval (`evals/run_retrieval_eval.py`) is the CI gate that runs on every push to main. It calls the real retriever methods (`query_for_agent1..4`) against the live ChromaDB collection and checks that 12 golden test cases return the correct keywords.

For this to work in CI, the ChromaDB collection must exist. There are two ways to make it available:

**Option A — Re-ingest in CI:** Run `python docs/rag/ingest.py --reset` as part of the CI job. This parses the 5 PDF documents, chunks them, embeds them, and builds the ChromaDB index from scratch.

**Option B — Commit the pre-built index:** Check the `db/chroma/` directory into git. CI runs `git checkout` and the index is immediately available.

The re-ingest approach was attempted first. It failed for a straightforward reason: the ingest pipeline depends on `docling` for PDF parsing and `einops` for tensor operations. These packages:

- `docling`: ~800MB install including PDF parsing models
- `einops`: tensor library required by some docling components
- Combined install time: 8–12 minutes on a GitHub Actions runner
- GitHub Actions timeout: 20 minutes (with buffer for the eval itself)

The first CI run that attempted re-ingestion timed out at the `pip install` step without reaching the eval. A second attempt with a higher timeout succeeded but took 17 minutes — leaving only 3 minutes for the actual eval, which is insufficient for model loading + 12 retrieval queries.

Additionally, docling downloads its own PDF parsing models at runtime (~400MB). These are not cached between CI runs on GitHub Actions free tier, adding another 4–6 minutes.

---

## Decision

**Commit the pre-built ChromaDB index to the repository** at `db/chroma/`. The CI workflow installs only the lightweight retrieval dependencies and uses the committed index directly.

```yaml
# .github/workflows/eval_gate.yaml
- name: Install eval dependencies
  run: |
    pip install "chromadb==1.1.1" "sentence-transformers==5.5.0" \
      "rank-bm25==0.2.2" python-dotenv einops
    # Note: NO docling, NO ingest step
```

The committed index consists of:
- `db/chroma/chroma.sqlite3` — ChromaDB metadata: chunk texts, metadata, collection config
- `db/chroma/{collection-uuid}/data_level0.bin` — HNSW vector index (binary)
- `db/chroma/{collection-uuid}/header.bin` — HNSW header
- `db/chroma/{collection-uuid}/length.bin` — HNSW length file
- `db/chroma/{collection-uuid}/link_lists.bin` — HNSW link lists

Total size on disk: ~15MB. Git checkout time: <1 second.

**When to re-ingest locally (and commit the new index):**

1. A policy document (`docs/*.pdf`) is updated
2. The embedding model is changed
3. Chunk size or metadata fields are changed in `ingest.py`

The workflow for this is:
```bash
python docs/rag/ingest.py --reset   # takes 2 minutes locally
git add db/chroma/
git commit -m "rebuild: update ChromaDB index after policy doc change"
git push
```

CI then uses the new committed index on the next run.

---

## Consequences

**Positive:**

- **CI runs in under 3 minutes.** The eval completes in 90–120 seconds including model loading. The CI timeout (20 minutes) is never approached.
- **Reproducible.** Every CI run uses the exact same index — the same chunks, same embeddings, same HNSW graph. Results are deterministic given the same retrieval code.
- **Fast developer feedback.** A developer pushing a retrieval code change sees eval results in 2–3 minutes, not 15–20.
- **No CI infrastructure requirements.** No GPU, no model download quota, no external storage needed.

**Negative:**

- **Binary files in git.** The HNSW `.bin` files are opaque binary blobs. `git diff db/chroma/` shows nothing meaningful. Reviewers cannot see what changed in the index.
- **Repository size grows over time.** Each index rebuild adds ~15MB to git history (old collection stays in history even after deletion). Over 50 rebuilds: ~750MB of git history.
- **Platform-specific HNSW behavior.** The HNSW index was built on Windows (local development). CI runs on Ubuntu. Testing confirmed the index is cross-platform compatible, but this assumption must be re-validated when upgrading ChromaDB versions.
- **Nomic model version drift.** The index was embedded with `nomic-ai/nomic-embed-text-v1.5`. If HuggingFace releases an updated version of the model code (`configuration_hf_nomic_bert.py`, `modeling_hf_nomic_bert.py`), query embeddings change while index embeddings don't — retrieval quality degrades silently. Mitigated by pinning package versions in CI (`chromadb==1.1.1`, `sentence-transformers==5.5.0`).

---

## The ChromaDB Version Guardrail

From the CLAUDE.md:
> **ChromaDB version mismatch → Rust panic 'range start index out of range'.** Fix: delete `db/chroma` and re-ingest (`python docs/rag/ingest.py --reset`). The on-disk index format must match the installed chromadb version.

The committed index was built with `chromadb==1.1.1`. The CI workflow pins `chromadb==1.1.1`. If a developer upgrades ChromaDB locally and rebuilds the index, they must update the CI pin to match — otherwise CI will crash with a Rust-level panic when trying to load the mismatched HNSW binary format.

---

## Alternatives Considered

| Option | Why Rejected |
|---|---|
| Re-ingest in CI with docling | 8–12 min install + 4–6 min model download = CI timeout |
| Store index in S3/GCS | Adds cloud dependency, IAM permissions, and 30–60s download time for every CI run |
| Use a lighter PDF parser (PyPDF2, pdfplumber) | Destroys table structure. Policy documents have multi-column tables (pool limits, scoring formula). Naive text extraction loses row/column relationships, breaking retrieval quality. |
| Skip CI retrieval eval | The retrieval eval is the primary quality gate. Skipping it means a RAG regression can merge to main undetected. |
