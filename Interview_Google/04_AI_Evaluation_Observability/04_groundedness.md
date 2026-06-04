# Groundedness

## What Is It? (Plain English)

Groundedness measures whether every specific claim in an AI-generated response can be traced back to a cited, verifiable source. A grounded answer doesn't just "feel consistent" with the source material — each individual sentence or assertion in the response is explicitly attributable to a specific passage from a specific document. You could point to the answer and draw arrows from each claim back to its source.

Think of academic citation. A well-researched paper doesn't just assert facts — it cites them. "Inventory carrying costs typically range from 20–30% of inventory value (Johnson et al., 2022)" is grounded. "Inventory carrying costs are typically high" is not grounded — it may be true, but there's no verifiable source attached to it. Groundedness is the AI equivalent of proper academic citation.

Groundedness and faithfulness are closely related but distinct. Faithfulness asks: "is the answer consistent with the context?" It's a holistic check of whether anything in the answer contradicts the sources. Groundedness asks: "can I point to a specific source for every specific claim?" It's a more granular, attributable standard. A response can pass a faithfulness check but fail a groundedness check if it makes claims that are consistent with but not explicitly stated in the context — valid inferences that lack direct citations.

## How It Works

```
Groundedness Evaluation: Sentence-Level Attribution
──────────────────────────────────────────────────────────────────
Generated Answer:
  [S1] "Class A SKUs require purchase approval for orders
        exceeding $47,500."
  [S2] "Lead time must be factored in at 1.2x."
  [S3] "The procurement team should be notified 72 hours
        in advance."

Retrieved Source Documents:
  [Doc A]: "...Capital allocation threshold for Class A SKU
            reorders is $47,500..."
  [Doc B]: "...critical inventory lead time is calculated
            with a 1.2x multiplier..."
  [Doc C]: "Procurement notification: 48-hour advance notice
            required for reorders."

Attribution Check (per sentence):
  S1 → Doc A: Grounded ✓ (exact match)
  S2 → Doc B: Grounded ✓ (same fact, different phrasing)
  S3 → Doc C: NOT Grounded ✗ (Doc C says 48hr, S3 says 72hr)

Groundedness Score = 2/3 = 0.67
Issues:
  - S3 contradicts source (72hr vs 48hr) → hallucination
──────────────────────────────────────────────────────────────────
```

**Two-step groundedness evaluation:**

```
Step 1: Sentence Segmentation
  Full response ──► Split into individual sentences/claims

Step 2: Per-sentence NLI check
  For each sentence Si:
    For each retrieved chunk Cj:
      NLI(premise=Cj, hypothesis=Si) → Entail/Neutral/Contradict
  
  Si is grounded if ANY Cj entails Si
  Si is contradicted if ANY Cj contradicts Si
  
  Groundedness = (grounded sentences) / (total sentences)
  Contradiction rate = (contradicted sentences) / (total sentences)
```

## Why Google Cares About This

In regulated industries (healthcare, finance, legal), every AI-generated claim that drives a decision must be auditable — a human reviewer needs to know which document each claim came from. Vertex AI's grounding API, Google's Search AI Overview citations, and NotebookLM's inline citations are all implementations of groundedness at product level. Understanding groundedness is essential for building AI systems that meet compliance requirements, and distinguishing it from faithfulness (a more commonly confused term) shows depth.

## Interview Questions & Answers

### Q1: How does groundedness differ from faithfulness, and when does the distinction matter in practice?

**Answer:** The conceptual difference is scope and attribution. Faithfulness is a system-level property: does the response, taken as a whole, contradict anything in the context? It's asking whether the answer is consistent with the sources. Groundedness is a claim-level property: can I attach a specific source citation to each specific assertion in the response? It requires not just consistency but explicit traceability.

A response can pass faithfulness but fail groundedness in two ways. First, by making valid but unattributed inferences. If the context says "Class A SKUs have a reorder frequency of 4 weeks" and the response says "Class A SKUs should be reordered approximately monthly," the response is faithful (not contradicting the source) and probably correct — but "approximately monthly" is an inference, not a direct quote. An NLI faithfulness checker might mark this as "entailed" (because 4 weeks ≈ monthly), but a strict groundedness audit might flag it as not directly attributed.

Second, by combining information from multiple sources without attribution. If the response says "the capital allocation threshold is $47,500 and reviews are scheduled quarterly," where the $47,500 comes from Document A and "quarterly reviews" comes from Document B, a faithfulness check would confirm both claims are supported somewhere in the context. But groundedness requires each claim to be individually cited — the reader needs to know that "quarterly reviews" came from Document B, not Document A.

When does this distinction matter? In regulated industries it matters continuously. A pharmaceutical AI system that recommends drug dosages must cite each dosage from an approved prescribing document, not just be "consistent" with documents. An insurance claims AI must ground each coverage determination in the specific policy clause that supports it. In finance, each investment recommendation must be attributable to a specific compliance document. Audit trails require groundedness, not just faithfulness.

For ORCA, groundedness matters for the reorder recommendation: "Use supplier XYZ at $42 per unit" must be grounded in a retrieved supplier contract document. If it comes from the LLM's training knowledge (where it may have seen that supplier mentioned in some general training text), it's unfaithful and ungrounded — potentially using outdated or incorrect pricing.

### Q2: How would you implement automated groundedness checking in a production pipeline?

**Answer:** Production groundedness checking is a pipeline: segment the response into claims, retrieve the grounding sources, run NLI or LLM-judge per claim, aggregate scores and produce a groundedness report.

Step 1 is claim extraction. Simple segmentation: split on sentence boundaries. Better: use a claim extraction prompt with a small LLM — "Extract each individual factual claim from this response as a separate bullet point." This separates compound sentences ("the threshold is $47,500 AND Class A items never receive partial distribution") into two independently checkable claims. Claim extraction quality directly affects groundedness measurement quality.

Step 2 is NLI or LLM-judge per claim. For each extracted claim, run it against all retrieved context chunks. An NLI model like `cross-encoder/nli-deberta-v3-base` is fast (milliseconds per pair) and works well for direct entailment. An LLM judge is more accurate for subtle cases but slower and more expensive. The practical compromise: use NLI for the initial pass to flag potentially ungrounded claims, then use an LLM judge to resolve ambiguous cases.

Step 3 is aggregation. Sum grounded, neutral, and contradicted claims. Compute three metrics: Groundedness (fraction grounded), Neutrality (fraction that are inferences — neither grounded nor contradicted), and Contradiction Rate (fraction that contradict the sources, which is the most serious failure mode). Return these as a structured report alongside the response.

Step 4 is action. In ORCA's context, you could add groundedness checking as a validation step after Agent 3's recommendation is generated. If groundedness score < 0.8 or contradiction rate > 0, flag the run for human review rather than automatically proceeding. This is especially important for the ESCALATE path where a human is about to approve a large financial commitment based on the AI's recommendation.

The biggest practical challenge is latency. Running NLI on 10 claims × 5 context chunks = 50 NLI forward passes, which takes 1–2 seconds on CPU. This might be acceptable in ORCA's pipeline (which already takes 10–30 seconds end-to-end) but would be unacceptable in a real-time chat application. For latency-sensitive applications, use lighter-weight groundedness proxies or run the check asynchronously after returning the response.

### Q3: What is NLI-based grounding and what are its limitations?

**Answer:** NLI (Natural Language Inference) is the core mechanism for automated groundedness checking. An NLI model takes (premise, hypothesis) pairs and classifies each as Entailment, Neutral, or Contradiction. Applied to groundedness: premise = a retrieved context chunk, hypothesis = a claim from the generated response. Entailment means the claim is grounded; Neutral means the claim is an unsupported assertion; Contradiction means the claim conflicts with the source.

The advantage of NLI: it's fast, doesn't require an LLM API call, runs locally, and produces interpretable labels. `cross-encoder/nli-deberta-v3-base` on CPU can process ~50 pairs per second. For ORCA's pipeline generating a recommendation with ~10 claims checked against 5 context chunks, that's 50 NLI calls taking about 1 second — very practical.

Limitation 1: NLI models struggle with domain-specific terminology and multi-hop reasoning. "The lead time factor of 1.2x corresponds to a 20% buffer" requires arithmetic reasoning, not just textual entailment. An NLI model trained on natural language text may label this as Neutral (the relationship isn't textually obvious) when it's actually fully grounded.

Limitation 2: Long context chunks confuse NLI models. NLI models were trained on short premise-hypothesis pairs (SNLI pairs average 14 words). When the "premise" is a 500-word policy document chunk, performance degrades. The fix: break context chunks into sentences or short paragraphs before using them as NLI premises.

Limitation 3: Paraphrase and abstraction. "The approval threshold is $47,500" and "Orders costing more than forty-seven thousand and five hundred dollars require sign-off" are fully equivalent, but an NLI model may rate the second as Neutral with the first as premise. This produces false negatives — claims marked as ungrounded when they actually are grounded in a paraphrased way.

Limitation 4: Missing cross-chunk reasoning. A claim might be grounded across two chunks: "Class A SKUs (defined in Policy 3.1) must use the capital allocation threshold (defined in Policy 5.2) for all reorders." Neither chunk alone entails the claim, but both together do. Standard per-chunk NLI misses this.

For production systems, address these limitations by: using sentence-level NLI premises (not chunk-level), using an LLM judge for flagged Neutral cases, and accepting that groundedness scores have ±10% uncertainty in complex domains.

### Q4: Why does groundedness matter especially for regulated industries?

**Answer:** In most consumer applications, a slightly unfaithful AI answer is an inconvenience. In regulated industries — healthcare, finance, legal, pharmaceuticals — an ungrounded AI claim can cause patient harm, financial fraud, or compliance violations. The regulatory frameworks that govern these industries explicitly require that every decision be auditable and traceable to documented sources.

In healthcare, clinical decision support tools must be able to explain why they made a recommendation in terms of specific guidelines (e.g., "this treatment recommendation is based on NCCN Guideline Version 2.2024, Section 3.1"). An AI that recommends a drug dose from its training knowledge (not from the current, approved prescribing information) may have learned from outdated data — drug dosing guidelines change, interaction databases are updated, and a dose that was safe two years ago may now carry a warning. Groundedness in healthcare is a patient safety requirement.

In finance, every investment recommendation or risk assessment must reference specific regulatory documents, market data, or contractual obligations. SEC rules require that investment advice be substantiated. An AI that asserts "this investment carries moderate risk" without grounding that claim in a specific risk assessment document or quantitative model output creates regulatory liability.

In legal AI, every claim must cite the specific statute, case law, or contract clause that supports it. A legal brief with ungrounded AI-generated claims is not just wrong — it's potentially malpractice.

The key design implication: for regulated industry applications, groundedness should be a hard constraint, not just a quality metric. Consider adding a "citation enforcement" layer in the system prompt ("you must cite the specific policy section for every claim") and a post-generation validator that rejects responses with groundedness score below a threshold, requiring regeneration or human escalation.

### Q5: How would you add groundedness checking to ORCA without significantly increasing latency?

**Answer:** ORCA's pipeline already takes 10–30 seconds end-to-end due to the multi-agent LangGraph pipeline, Groq API calls, and optional reranking. Adding groundedness checking should aim to add no more than 1–2 seconds.

The efficient approach is asynchronous sampling with critical-path checking. Two tiers:

**Tier 1 (synchronous, on critical path):** Run a lightweight contradiction check only — not full groundedness. Extract claims containing dollar amounts, SKU codes, and supplier names (high-risk factual claims). Check each against the retrieved context using a fast string search: does the dollar amount appear anywhere in the retrieved context? This is O(n) string matching, not NLI, and takes <10ms. If a critical fact doesn't appear in the context, flag it immediately before the pipeline proceeds. This catches the most dangerous failure mode (hallucinated financial figures) with negligible latency.

**Tier 2 (asynchronous, off critical path):** After returning the recommendation to the dashboard, asynchronously run full NLI-based groundedness on the complete response. Log the results to a `groundedness_log` table in `orca.db`. This doesn't block the user response and adds zero latency to the user experience. The logged data feeds into monitoring dashboards and is reviewable by the human approver during the HITL step.

The dashboard improvement: display the groundedness score alongside the recommendation in the ORCA dashboard. Show a "Source citations" expandable panel that lists each claim with its source document and the specific excerpt that supports it. This gives the human approver immediate traceability for every claim in the recommendation — turning groundedness from a background quality metric into a user-facing feature that builds trust.

For the HITL approve/reject flow specifically, display the groundedness score prominently. A recommendation with groundedness < 0.7 should show a yellow warning; groundedness < 0.5 should show a red warning with the specific ungrounded claims listed. This helps the human reviewer focus their scrutiny on the parts of the recommendation that aren't backed by retrieved evidence.

## Key Points to Say in the Interview
- Groundedness is claim-level attribution — can you point from each claim to its specific source?
- Faithfulness is the absence of contradiction; groundedness is the presence of positive attribution
- NLI-based groundedness checking: premise=context chunk, hypothesis=extracted claim, measure Entailment rate
- In regulated industries (healthcare, finance, legal), groundedness is a compliance requirement, not just quality
- Run lightweight contradiction checks synchronously; run full NLI groundedness asynchronously to avoid latency impact
- Groundedness is best surfaced to end users as inline citations, not just a backend quality score

## Common Mistakes to Avoid
- Treating faithfulness and groundedness as synonyms — they're related but measure different things
- Running NLI on full context chunks (500+ words) instead of sentence-level premises — NLI quality degrades on long text
- Only checking groundedness in eval, not in production — groundedness can drift with model updates or context changes
- Building groundedness checks that only test retrieval quality, not the LLM generation step
- Not surfacing groundedness results to the human reviewer in HITL systems — the whole point is auditability

## Further Reading
- [TruLens Groundedness Documentation](https://www.trulens.org/trulens/guides/trulens_eval/evaluation_benchmarks/) — Open-source RAG evaluation framework with NLI-based groundedness scoring
- [ARES: Automated RAG Evaluation System (arXiv)](https://arxiv.org/abs/2311.09476) — Framework for automated context relevance and groundedness evaluation
- [AttributionBench (arXiv)](https://arxiv.org/abs/2402.04883) — Benchmark specifically for measuring attribution quality in generated text
- [Vertex AI Grounding](https://cloud.google.com/vertex-ai/generative-ai/docs/grounding/overview) — Google's production implementation of grounding for Gemini-based applications
- [NLI Models for Faithfulness Evaluation (Hugging Face)](https://huggingface.co/cross-encoder/nli-deberta-v3-base) — The DeBERTa NLI model widely used for automated grounding checks
