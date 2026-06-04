# Hallucination Detection

## What Is It? (Plain English)

Hallucination is when a language model generates text that is confidently stated but factually wrong or completely fabricated. The term comes from psychology, where hallucinations are perceptions with no external stimulus — the brain generates an experience from nothing. LLMs do the same thing with text: they generate plausible-sounding sentences that have no basis in reality.

What makes hallucination particularly dangerous is that LLMs don't have an "uncertain voice." They state fabricated information in the same confident, fluent tone they use for well-established facts. "The capital of France is Paris" and "The supplier ABC-Corp was acquired by XYZ-Holdings in 2023" read identically in style — but one is true and the other might be completely invented. Without verification against an authoritative source, a human reading the output has no way to distinguish them.

Hallucinations in RAG systems are especially problematic because the whole point of RAG is to ground answers in retrieved documents. If the LLM is hallucinating, it's bypassing the grounding entirely and drawing on training knowledge (which may be wrong, outdated, or biased). A supply chain AI that hallucinates a supplier's contact information, minimum order quantity, or lead time will cause real operational and financial damage.

## How It Works

```
Types of LLM Hallucination
──────────────────────────────────────────────────────────────────
Type 1: FACTUAL HALLUCINATION
  Context: "Supplier XYZ has a minimum order of 500 units."
  Output:  "Supplier XYZ has a minimum order of 200 units."
  → Direct contradiction of a retrieved fact

Type 2: CONFABULATION (invented fact with no source)
  Context: [contains nothing about delivery windows]
  Output:  "Delivery is guaranteed within 5 business days."
  → Fabricated claim with no grounding

Type 3: KNOWLEDGE CUTOFF HALLUCINATION
  Context: [nothing about supplier status]
  Output:  "ABC-Corp is the current preferred supplier."
  → May have been true at training time, wrong now

Type 4: REASONING HALLUCINATION
  Context: "Threshold is $47,500. Order is $49,000."
  Output:  "Since $49,000 < $47,500, no approval needed."
  → Arithmetic error presented confidently

Detection Methods:
  ┌────────────────────────────────────────────┐
  │ NLI-based:    Context vs. Output claim      │
  │ Self-Consistency: Run N times, measure var  │
  │ SelfCheckGPT: Multiple samples + NLI        │
  │ RAG grounding: All claims must cite source  │
  │ Named-entity: Verify proper nouns in context│
  └────────────────────────────────────────────┘
──────────────────────────────────────────────────────────────────
```

## Why Google Cares About This

Hallucination is the defining quality problem for LLM-based products at Google scale. Every Gemini response, every AI Overview in Search, every Workspace AI feature must be checked for hallucination before shipping and monitored for hallucination in production. For the ML Engineer interview, understanding hallucination detection methods — not just "use RLHF to fix it" — and explaining how to architect a system that minimizes hallucination risk demonstrates the production engineering depth required at L5/L6.

## Interview Questions & Answers

### Q1: Why do LLMs hallucinate? What are the root causes?

**Answer:** LLMs hallucinate for several interconnected reasons rooted in how they're trained and how they generate text.

The most fundamental cause is the **training objective**: language models are trained to predict the next token given previous tokens, optimizing for perplexity (how well the model predicts the training data). This objective is indifferent to whether the generated text is factually accurate — it only asks whether the text is statistically likely given the training corpus. If medical misinformation was prevalent in the training data and was written in confident, declarative prose, the model learns to generate confident, declarative medical text — including misinformation.

**Knowledge cutoffs** create a systematic hallucination pattern: the LLM's "knowledge" is frozen at the training data cutoff. Post-cutoff facts don't exist in the model. When asked about them, the model doesn't say "I don't know" — it generates the most statistically likely continuation of the prompt, which may draw on related-but-wrong information from training. A model trained in 2023 asked about 2024 supplier pricing will confidently extrapolate from 2023 prices or invent entirely.

**Conflation of training sources**: if two contradictory facts appeared in training data (from a wrong blog post and a correct academic paper), the model averages them. It can't track provenance — it doesn't know which source was more reliable. The output may blend both facts into a confident but wrong composite.

**Confabulation under prompt pressure**: when a prompt implies that the model should know something specific, the model generates what would be expected rather than admitting uncertainty. "What is supplier ABC-Corp's current lead time?" presupposes the model knows — and the model obliges by generating a plausible-sounding number rather than saying "I don't have that information."

**Lack of calibrated uncertainty**: LLMs don't have a native mechanism to say "I'm 30% confident in this claim." The generation process doesn't output probability scores attached to factual claims — it outputs tokens. Efforts to add calibration (chain-of-thought, instructing the model to express uncertainty) help but don't solve the problem fundamentally.

### Q2: What is SelfCheckGPT and how does it detect hallucinations without reference answers?

**Answer:** SelfCheckGPT is a hallucination detection technique introduced in a 2023 paper that works purely from multiple samples of the same model, without needing ground-truth reference answers. This makes it valuable for deployment scenarios where you don't have a golden dataset to verify against.

The intuition: consistent facts are more likely to be true. If you ask the same question 5 times with temperature > 0 (so each run is different), the model will repeat genuine facts across all 5 runs while hallucinated facts vary — because hallucinations are generated from noise in the probability distribution, not from firmly encoded knowledge. If the model generates "the capital of France is Paris" across all 5 runs, that's likely true. If it generates "Supplier ABC-Corp's lead time is 7 days / 12 days / 5 days / 8 days / 10 days" across 5 runs, the inconsistency signals a hallucinated fact.

**Implementation:** Generate N samples of the response (N=5 typically) at temperature > 0. For each sentence in the primary response, check whether the same information appears in the other N-1 samples. The check can use NLI (does the primary response sentence get "Entailment" from the other samples?), BERTScore, or n-gram overlap. If a sentence's claim appears in fewer than 2 of the other 4 samples, it's flagged as potentially hallucinated.

**Practical considerations:** SelfCheckGPT requires N LLM calls per query — 5x the inference cost. For ORCA, which already makes ~8 LLM calls per pipeline run (one per agent, plus any sub-calls), applying SelfCheckGPT to every agent would increase the call count to ~40. This is feasible for ORCA's low-frequency operations (reorder decisions happen occasionally, not thousands per second), but would be prohibitive for high-frequency applications.

The accuracy of SelfCheckGPT scales with N — more samples produce better hallucination detection. Empirically, N=5 is a good balance between cost and accuracy. The technique works best for factual claims (dates, numbers, names) and less well for complex reasoning steps, where multiple samples may all make the same logical error.

### Q3: What are the mitigation strategies for hallucination in a RAG system, and how effective is each?

**Answer:** Hallucination mitigation in RAG falls into three categories: retrieval-side mitigations, generation-side mitigations, and post-generation detection.

**Retrieval-side mitigations** reduce hallucination by ensuring the LLM has high-quality, relevant context to work with. If the LLM has the right information in front of it, it has less incentive to reach into training knowledge. Key techniques: (1) Improve retrieval quality — better chunking, hybrid search, reranking ensure the most relevant documents are in the context window. (2) Ensure context completeness — if the query requires information from multiple documents, ensure they're all retrieved. Partial context causes the LLM to fill gaps with training knowledge. (3) Include negative context — explicitly tell the LLM "this is all the information available; if the answer isn't here, say so." Without this guidance, the LLM may not recognize when it's supposed to stay silent.

**Generation-side mitigations** change how the LLM produces output. (1) Constrained system prompts: "Only use information from the context below. Do not use any information from your training data." This reduces but doesn't eliminate hallucination — LLMs sometimes ignore prompt constraints, especially under pressure from the query. (2) Structured output formats: requiring the LLM to output JSON with source citations for each field forces explicit grounding. If the model can't find a source, the field should be null. (3) Temperature = 0: reduces randomness in generation, which reduces the probability of low-probability (often hallucinated) tokens being selected. (4) Chain-of-thought prompting: asking the model to reason step-by-step before answering gives it an opportunity to "notice" when it's extrapolating beyond the context.

**Post-generation detection** adds a verification layer after the response is generated. (1) NLI-based faithfulness/groundedness check on every response. (2) Named-entity verification: extract all proper nouns, dates, and numerical values from the response and verify each appears in the retrieved context. (3) Self-consistency check: regenerate the response 3–5 times and flag claims that appear in fewer than 2 generations. (4) Human-in-the-loop for high-stakes decisions: ORCA's HITL approval step is the ultimate anti-hallucination safeguard for expensive reorder decisions.

The most effective comprehensive strategy combines all three layers: retrieve better (less need to hallucinate), constrain generation (reduced opportunity to hallucinate), verify outputs (detect what slipped through).

### Q4: How does ORCA's architecture prevent hallucinated supplier contacts and financial figures?

**Answer:** ORCA faces specific hallucination risks in two areas: supplier contact information (names, email addresses, phone numbers of supplier representatives) and financial figures (minimum order quantities, per-unit prices, lead time multipliers, approval thresholds). Both types of information are likely present in the LLM's training data in some form — Groq's llama-3.1-8b-instant model was trained on web-crawled text that may include supply chain industry data — making them prime hallucination candidates.

The primary defense is the RAG architecture itself: all five policy documents are ingested into ChromaDB, and agents are instructed to use the retrieved context for their decisions. However, CLAUDE.md acknowledges this risk specifically, noting that hallucinated supplier contacts are a known concern. This suggests the current system doesn't have a complete mitigation.

A structured approach to eliminate this risk would add three components. First, in the system prompt for agents that generate supplier-specific recommendations (Agent 2 and Agent 3), add an explicit instruction: "All supplier names, contact details, pricing figures, and lead times must come verbatim from the context below. Do not use any supplier information from your training knowledge." This is a generation-side mitigation.

Second, add a post-generation named-entity extraction check. After each agent generates its recommendation, extract all proper nouns (supplier names) and numerical values (prices, quantities, lead times). For each extracted value, verify it appears in the retrieved context using string matching. If a supplier name doesn't appear in the retrieved context, flag the recommendation for human review before proceeding. This is a post-generation detection step.

Third, consider adding supplier-specific factual data to the RAG corpus. If the 5 current policy documents don't include a supplier directory with contacts and pricing, these facts are simply not available to the agents — making hallucination inevitable when agents try to mention specific suppliers. Adding structured supplier data to the corpus (even as a simple CSV-style document) gives the agents authoritative source material to draw from.

### Q5: How would you handle hallucination detection at Google's production scale (millions of queries per day)?

**Answer:** At millions of queries per day, running full hallucination detection on every query is economically infeasible — NLI checks and LLM-judge calls add up to significant compute costs. The production architecture uses sampling and tiering.

**Tiered detection strategy:**

Tier 1 (every query, < 1ms): Rule-based checks only. Verify output length is within bounds. Check for known hallucination markers: date ranges that exceed the model's training cutoff, numerical ranges that are clearly outside realistic bounds (order quantities of 0 or negative numbers, percentages > 100%), forbidden phrases indicating confusion ("As an AI, I..."). These checks catch obvious failures with near-zero cost.

Tier 2 (5% sample, ~50ms per sample): NLI-based faithfulness check on sampled responses. Run `cross-encoder/nli-deberta-v3-base` to check whether the sampled response's claims are supported by retrieved context. Log scores to a monitoring database. Alert if the rolling 1-hour average faithfulness score drops below a threshold (e.g., 0.80). This is continuous quality monitoring without evaluating every query.

Tier 3 (0.1% sample or flagged responses, ~2s per sample): Full LLM-judge evaluation. Use a strong LLM to evaluate specific failure cases — responses flagged by Tier 1 or with low Tier 2 faithfulness scores. The LLM judge provides a detailed breakdown of what was wrong, used for debugging and for adding new cases to the golden dataset.

**Architectural requirements:** All tiers must be asynchronous and non-blocking — the user receives the response immediately while the detection pipeline runs in the background. Results are logged to a centralized observability platform (LangSmith, Datadog, or a custom pipeline). Automated alerts page on-call engineers if any tier's failure rate exceeds threshold. Feedback loops: cases detected by Tier 3 are reviewed by engineers and either added to the offline golden dataset (for CI coverage) or used to fine-tune the system prompt (for generation mitigation).

The key insight for Google scale: you're not trying to catch every hallucination — you're trying to maintain SLA quality levels and detect systemic issues quickly. A 0.5% hallucination rate on 10 million queries/day is 50,000 bad responses — too many in absolute terms but potentially acceptable if the domain has low stakes. In high-stakes domains, the tiering should be more aggressive and Tier 3 coverage should be higher.

## Key Points to Say in the Interview
- LLMs hallucinate because their training objective (next-token prediction) is indifferent to factual accuracy
- Knowledge cutoffs create systematic hallucination for post-cutoff facts — the model extrapolates instead of saying "I don't know"
- SelfCheckGPT detects hallucinations without ground truth by measuring consistency across multiple samples
- Mitigation is layered: better retrieval (reduce the need to hallucinate) + constrained prompts (reduce the opportunity) + post-generation verification (detect what slipped through)
- At production scale, use sampling tiers — not every query can afford full NLI + LLM judge evaluation
- HITL (human approval) is the ultimate safeguard for high-stakes decisions — ORCA's approve/reject flow is correct for expensive reorders

## Common Mistakes to Avoid
- Assuming RAG completely eliminates hallucination — LLMs can still ignore the context and use training knowledge
- Relying only on RLHF/instruction tuning as the fix — these reduce hallucination frequency but don't eliminate it
- Running hallucination detection only in eval, not in production monitoring
- Not distinguishing hallucination types — factual contradiction and confabulation require different detection methods
- Ignoring hallucination in reasoning steps (arithmetic errors, logical fallacies) — detection frameworks often focus only on factual claims

## Further Reading
- [Lilian Weng: Hallucination in Large Language Models (blog)](https://lilianweng.github.io/posts/2024-07-07-hallucination/) — Comprehensive taxonomy of hallucination types and mitigation strategies
- [SelfCheckGPT: Zero-Resource Hallucination Detection (arXiv)](https://arxiv.org/abs/2303.08896) — The original paper introducing consistency-based hallucination detection
- [Survey of Hallucination in Natural Language Generation (arXiv)](https://arxiv.org/abs/2202.03629) — Authoritative survey covering hallucination causes, types, and detection methods
- [FACTSCORE: Fine-grained Atomic Evaluation of Factual Precision (arXiv)](https://arxiv.org/abs/2305.14251) — Method for decomposing LLM output into atomic facts and checking each against a knowledge source
- [TruthfulQA Benchmark (arXiv)](https://arxiv.org/abs/2109.07958) — Benchmark for measuring LLM truthfulness across 817 questions designed to elicit hallucination
