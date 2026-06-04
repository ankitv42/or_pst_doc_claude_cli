# Faithfulness

## What Is It? (Plain English)

Faithfulness, in the context of RAG systems, measures whether every claim in the generated answer is directly supported by the retrieved documents. A faithful answer says only what the retrieved context says — it doesn't add information from outside the context, doesn't extrapolate beyond what's written, and doesn't contradict the source material.

Imagine an employee who is asked to summarize a policy document for their manager. A faithful summary includes only what's in the document. An unfaithful summary includes the employee's own opinions, recollections from a different document, or "facts" they think are true but aren't in the document you handed them. The summary might still be factually correct by coincidence — the employee might "remember" the right number — but it's unfaithful because the answer didn't come from the authoritative source.

This distinction matters critically in enterprise AI systems. A customer service bot that gives a correct answer but from memory (not from the current policy document) will eventually give a wrong answer when the policy changes. A procurement system that recommends reorder quantities based on "what it learned in training" rather than from the current supplier contracts is a compliance and financial risk. Faithfulness is the property that grounds every answer to an auditable source — so you can always ask "where did this come from?" and get a verifiable answer.

## How It Works

```
Faithfulness Evaluation Pipeline
─────────────────────────────────────────────────────────────────
Retrieved Context:
  "Class A SKUs require reorder approval when total cost
   exceeds $47,500. Lead time is factored at 1.2x for
   critical inventory."

Generated Answer:
  "For Class A SKUs, reorder approval is required when
   the order total exceeds $47,500. The system applies
   a 20% lead time buffer. You should also notify the
   CFO for orders over $100,000."

Faithfulness Check (claim by claim):
  Claim 1: "reorder approval required when total > $47,500"
           → Context says exactly this. SUPPORTED ✓

  Claim 2: "20% lead time buffer applied"
           → Context says "1.2x", which equals 20%. SUPPORTED ✓

  Claim 3: "notify CFO for orders over $100,000"
           → Not in retrieved context. NOT SUPPORTED ✗

Faithfulness Score = (supported claims) / (total claims)
                   = 2/3 = 0.67
─────────────────────────────────────────────────────────────────
```

The key mechanism for automated faithfulness checking is **Natural Language Inference (NLI)**. An NLI model takes two inputs: a premise (the retrieved context) and a hypothesis (a claim from the generated answer). It outputs one of three labels: Entailment (the premise logically implies the hypothesis), Neutral (the premise doesn't confirm or deny the hypothesis), or Contradiction (the premise contradicts the hypothesis). Claims that get "Entailment" are faithful; claims that get "Neutral" or "Contradiction" are unfaithful.

## Why Google Cares About This

Faithfulness is a core property for any Google product that uses Gemini or another LLM to surface information from authoritative sources — Search grounding, NotebookLM, Workspace AI features. In regulated domains (healthcare, legal, finance), unfaithful answers are compliance violations, not just quality issues. Senior engineers are expected to explain not just what faithfulness means but how to measure it automatically at scale, and how to architect a system that enforces faithfulness by design rather than hoping the LLM stays on topic.

## Interview Questions & Answers

### Q1: What is the difference between faithfulness and factual accuracy, and why does the distinction matter?

**Answer:** Faithfulness is about whether the answer is grounded in the provided context. Factual accuracy is about whether the answer is true in the real world. These are independent dimensions that can diverge in important ways.

An answer can be factually accurate but unfaithful: "The recommended reorder quantity is 500 units." This might happen to be correct based on the LLM's training knowledge — but if this number didn't come from the retrieved policy document (which might say 450 units, or might have been updated last week), the answer is unfaithful even though it's accidentally correct today. Tomorrow, when the policy changes to 550 units, the LLM will still say 500 — faithfully wrong.

An answer can be faithful but factually incorrect: if the retrieved document contains an error ("reorder threshold is $47,50" — a typo for $47,500), a faithful answer that repeats "the threshold is $47,50" is technically faithful (it accurately reflects the source) but wrong. This is the case for "garbage in, garbage out" — faithfulness evaluates grounding, not document quality.

An answer can be faithful AND factually accurate — which is the goal: every claim traces to the retrieved context, and the retrieved context is correct and current.

Why this distinction matters for system design: faithfulness is testable automatically (with NLI classifiers or LLM judges that check whether claims are supported by given text), while factual accuracy requires external knowledge or ground truth that may not be available. For a RAG system, you optimize for faithfulness because you control the context — you don't always control whether the context is "the truth." Faithfulness ensures the system at least stays honest to its sources; document quality is a separate concern handled by the ingestion and curation pipeline.

For ORCA, this means the agents should ground every reorder recommendation in the retrieved policy chunks. If an agent says "expedited orders should use supplier ABC-Corp," that supplier name must appear in the retrieved context — not come from the LLM's training data.

### Q2: How do NLI-based faithfulness checkers work?

**Answer:** Natural Language Inference (NLI) is a text classification task where the model is given a premise and a hypothesis and must predict: does the premise entail (support) the hypothesis, contradict it, or is it neutral (neither confirms nor denies)? NLI models are trained on large datasets of (premise, hypothesis, label) triples — SNLI, MultiNLI, ANLI — and learn to detect logical relationships between text fragments.

For faithfulness evaluation, the mapping is: premise = retrieved context, hypothesis = one specific claim from the generated answer. Run the NLI model on each (context, claim) pair. If the model outputs "Entailment," the claim is supported. If it outputs "Neutral" or "Contradiction," the claim is unsupported (and possibly hallucinated).

The pipeline in practice requires a step before the NLI check: claim extraction. The generated answer is broken into atomic claims using a text parser or another LLM call. "The reorder threshold is $47,500 and Class A items require CFO approval" is split into Claim 1: "The reorder threshold is $47,500" and Claim 2: "Class A items require CFO approval." Then each claim is individually tested against the context.

Popular NLI models for faithfulness checking: `cross-encoder/nli-deberta-v3-base` (strong quality, runs on CPU), `microsoft/deberta-large-mnli`, and `roberta-large-mnli`. For a production system, you might use a strong LLM (GPT-4) as the NLI judge with a structured prompt: "Given the following context, is the following claim supported, contradicted, or neutral? Context: {ctx}. Claim: {claim}. Answer: Entailment/Contradiction/Neutral." The LLM-based approach is more flexible for complex claims but costs more.

The limitation of NLI-based faithfulness: NLI models are trained on general-domain text and may struggle with domain-specific reasoning. "1.2x lead time factor" and "20% lead time buffer" are mathematically equivalent but an NLI model might label this as Neutral (not obviously entailed from the context's phrasing) rather than Entailment. Domain fine-tuning of the NLI model can help, or using an LLM judge with chain-of-thought reasoning.

### Q3: How would you measure faithfulness in ORCA's agent pipeline automatically?

**Answer:** ORCA's faithfulness measurement would operate at two levels: per-LLM-call faithfulness (does each agent's output stay within its retrieved context?) and end-to-end faithfulness (does the final reorder recommendation trace to retrieved policy?).

For per-LLM-call faithfulness, the approach is: (1) Capture the context string passed to each agent (already available in the LangGraph state — the `retrieved_context` field). (2) Capture the LLM's output for that agent (also in state). (3) Post-hoc, run an NLI checker on the (context, agent_output) pair, or use a lightweight faithfulness prompt: "Rate 0-1 whether every claim in {agent_output} is directly supported by {context}."

The most practical implementation for ORCA given its Groq-based architecture: since Groq is already used for LLM calls, add a lightweight faithfulness check after each agent runs. Use a small, fast model (like `llama-3.1-8b-instant` at temperature=0) with a structured faithfulness prompt that returns a JSON: `{"supported_claims": [...], "unsupported_claims": [...], "faithfulness_score": 0.XX}`. Log this to the pipeline log table in SQLite. If any agent has faithfulness_score < 0.7, flag the run in the dashboard.

For the specific risk of hallucinated supplier contacts (flagged in CLAUDE.md as a known concern), a targeted check is more efficient: extract all proper nouns from the agent output (supplier names, SKU codes, dollar amounts) and verify each appears in the retrieved context. A simple regex/NER extraction + string search is faster and more reliable than full NLI for this specific failure mode.

At ORCA's scale (tens of pipeline runs per day, not thousands), running a faithfulness check on every pipeline run is feasible. At Google scale (millions of daily queries), you'd sample 1–5% of responses for faithfulness scoring.

### Q4: What architectural patterns make a RAG system more faithful by design, not just by measurement?

**Answer:** Faithfulness can be encouraged through system design choices before any measurement or post-hoc checking. These patterns reduce the probability that the LLM drifts beyond its context.

**Constrained system prompts** are the first line of defense. Explicitly instruct the LLM to only use information from the provided context: "Answer ONLY using the information provided in the context below. If the answer is not in the context, say 'I don't have this information in the retrieved documents.'" This doesn't guarantee faithfulness (LLMs sometimes ignore system prompt constraints) but significantly reduces the incidence of the model drawing on training knowledge.

**Context-only prompting** is a stronger version: instead of giving the LLM both context and a question, structure the prompt so the question and context are explicitly linked. "Based only on the following policy excerpt: [context], answer this question: [question]." The explicit reference to "only" and the tight linkage between context and question keeps the model anchored.

**Citation enforcement** is a structural approach: require the LLM to cite specific context passages for every claim it makes. "For each claim in your answer, include a [Source: excerpt...] citation." If the LLM cannot cite a source, it cannot make the claim. This is architecturally enforcing faithfulness through output format requirements.

**Temperature reduction** helps: at temperature=0, the LLM is more deterministic and tends to stay closer to the provided context. Temperature=1 encourages more "creative" generation, which can mean drawing on training knowledge beyond the context.

**Short context windows** with highly relevant content help: if the LLM's context window contains 50 chunks, many tangentially related, the LLM may average across them in a way that blends accurate and inaccurate information. Providing a small, tightly relevant context (5 high-quality chunks from the reranker) gives the LLM less noise to drift into.

### Q5: Can a faithful answer still be a bad answer? What does faithfulness not capture?

**Answer:** Yes — faithfulness is a necessary but not sufficient condition for a good RAG answer. Several failure modes produce faithful-but-bad answers.

**Incomplete faithfulness**: an answer that is entirely grounded in the context but omits crucial information. If the context says "Class A SKUs require approval when cost exceeds $47,500 AND when lead time exceeds 30 days," and the answer says only "Class A SKUs require approval when cost exceeds $47,500," the answer is faithful (everything it says is supported) but critically incomplete. A system optimizing for faithfulness score would give this a perfect 1.0.

**Incorrect reasoning from faithful premises**: "The context says the threshold is $47,500 and the order costs $50,000, so I conclude no approval is needed." Every individual claim is grounded in context, but the logical inference is wrong. NLI-based faithfulness checking tests whether claims are supported, not whether the reasoning chain is valid.

**Wrong context retrieval + faithful generation**: if the retrieval stage surfaces the wrong document and the LLM faithfully generates an answer based on it, the answer is faithful to its context (which was wrong) but incorrect for the user's actual question. Faithfulness metrics would show a high score, but the answer would mislead the user.

**Relevant information missing from corpus**: if the user asks about a supplier policy that isn't in the RAG corpus, a faithful system should say "I don't have this information." But if the system retrieved a loosely related document and generated a "faithful" answer based on it, the user gets a plausible-sounding wrong answer with high faithfulness score.

These gaps are why a complete RAG evaluation requires multiple metrics: faithfulness (is the answer grounded?), context recall (did retrieval find the right documents?), answer relevance (does the answer address the actual question?), and completeness (does the answer include all important information from the context?). Faithfulness alone is insufficient.

## Key Points to Say in the Interview
- Faithfulness tests whether the answer is grounded in the retrieved context — not whether the context is correct
- Factual accuracy and faithfulness are independent — an answer can be accurate but unfaithful (used training knowledge instead of context)
- NLI models measure faithfulness by checking if each claim is entailed by the context
- Faithfulness is enforced architecturally (constrained prompts, citation requirements) AND measured post-hoc
- A faithful answer can still be incomplete, logically wrong, or based on retrieved wrong documents
- Faithfulness score alone is insufficient — combine with context recall, relevance, and completeness metrics

## Common Mistakes to Avoid
- Treating high faithfulness score as equivalent to "good answer" — it's one dimension of quality, not the whole picture
- Using faithfulness and factual accuracy interchangeably — they're different, measurable independently
- Not decomposing generated answers into atomic claims before NLI checking — NLI models work best on single claims
- Relying only on NLI classifiers without LLM-judge validation — NLI models miss implicit entailment relationships
- Building a faithfulness checker that only runs in eval, not in production monitoring — faithfulness degradation can happen after deployment

## Further Reading
- [RAGAS: Automated Evaluation of RAG (arXiv)](https://arxiv.org/abs/2309.15217) — Defines and implements automated faithfulness measurement as part of a full RAG eval suite
- [TruLens: RAG evaluation framework](https://www.trulens.org/trulens/getting_started/quickstarts/langchain_quickstart/) — Open-source library with NLI-based faithfulness and groundedness scoring for LangChain pipelines
- [FaithDial: Faithful Dialogue (arXiv)](https://arxiv.org/abs/2204.10757) — Research on building faithfully grounded conversational agents
- [NLI with DeBERTa (Hugging Face)](https://huggingface.co/cross-encoder/nli-deberta-v3-base) — The NLI model commonly used for production faithfulness checking
- [Lilian Weng: Hallucination in LLMs](https://lilianweng.github.io/posts/2024-07-07-hallucination/) — Comprehensive blog post covering hallucination types including faithfulness failures
