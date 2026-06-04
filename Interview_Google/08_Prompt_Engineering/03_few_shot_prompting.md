# Few-Shot Prompting

## What Is It? (Plain English)

Few-shot prompting means teaching a language model how to do a task by showing it a small number of worked examples directly in the prompt, before presenting the actual problem you want solved. Instead of explaining the rules abstractly, you demonstrate: "Here are three examples of input and the correct output. Now do the same for this new input." The model pattern-matches to your examples and generalizes.

The name comes from machine learning terminology. "Zero-shot" means the model gets no examples — just the task description. "One-shot" means one example. "Few-shot" usually means 3 to 8 examples. Compare this to "fine-tuning," where you train the model on thousands of examples by updating its weights. Few-shot prompting achieves similar behavior changes but at zero training cost — the examples live in the prompt, not in the model's parameters.

Think of it like teaching a junior employee. Zero-shot is handing them the manual and saying "figure it out." Few-shot is showing them three completed reports and saying "make the next one look like these." Fine-tuning is having them do 10,000 practice reports until it becomes muscle memory. For most tasks, showing 3-5 examples in the prompt gets you 80% of the way there, at a fraction of the cost and time.

## How It Works

The structure of a few-shot prompt has a fixed pattern: system instruction, then examples in input/output pairs, then the actual query:

```
ZERO-SHOT                    FEW-SHOT
─────────────────────────    ─────────────────────────────────────
[System instruction]         [System instruction]
[Task query]                 
                             [Example 1 Input]
Output: ???                  [Example 1 Output]
                             
                             [Example 2 Input]
                             [Example 2 Output]
                             
                             [Example 3 Input]
                             [Example 3 Output]
                             
                             [Actual query Input]
                             Output: ← model continues here
```

The model reads the examples as demonstrations of the pattern, then continues the sequence by producing an output consistent with what it observed. This works because LLMs are trained to predict the next token — in a few-shot context, the most probable continuation of the pattern is the correct answer.

## Why Google Cares About This

Few-shot prompting is often the first tool a Google engineer should reach for when a zero-shot prompt produces inconsistent results. It is cheaper than fine-tuning, faster than training data collection, and reversible — you can update examples without model retraining. Google's ML teams use few-shot prompts extensively in production pipelines, and interviewers test for practical knowledge: how many examples, how to select them, when to use dynamic retrieval, and when to admit that fine-tuning is the right answer instead. Understanding few-shot prompting signals hands-on experience building real LLM applications.

## Interview Questions & Answers

### Q1: How many examples are needed for few-shot prompting to work well, and how should they be chosen?

**Answer:** Research consistently shows that 3-8 examples captures most of the benefit of few-shot prompting. Adding more examples beyond 8 produces diminishing returns — you are consuming context window tokens that could hold more of the actual task, and the model is usually not extracting meaningfully new patterns from the 9th example that it did not learn from the first five. In context windows of 128K+ tokens, this constraint is relaxed, but the principle still holds for cost and latency optimization.

Example selection is more important than example count. The core principle is diversity: examples should cover the range of input variations the model will encounter in production. If your task is classifying support tickets and all your examples are about billing issues, the model will underperform on technical support tickets. Aim for examples that represent different semantic clusters in your input space.

Examples should also be representative of the distribution of inputs, not just edge cases. A common mistake is selecting examples that demonstrate all the hard cases — if 90% of your real inputs are simple cases, your examples should reflect that distribution, otherwise the model will overcomplicate its handling of routine inputs. Additionally, make sure your examples are correct — wrong examples actively mislead the model. Auditing your few-shot examples for ground-truth accuracy is as important as auditing training data labels for fine-tuning.

Finally, examples should be balanced if your task involves categories. If you are demonstrating a 3-class classification (REORDER / HOLD / ESCALATE), include examples of each class rather than 5 REORDER examples and 1 HOLD — class imbalance in examples biases the model's predictions toward the majority class.

### Q2: What is the order effect in few-shot prompting, and how do you mitigate it?

**Answer:** The order effect is the empirically observed phenomenon that the sequence of examples in a few-shot prompt influences the model's outputs, often significantly. Models tend to be recency-biased — examples near the end of the prompt (closest to the actual query) have more influence on the response than examples at the beginning. Additionally, if the last example in the prompt is from a particular class, the model is more likely to predict that class for the actual query.

This creates a subtle but real problem in production. Imagine an inventory alert classification system with examples ordered: HOLD, HOLD, ESCALATE, REORDER. The REORDER example is last, and the model is slightly more likely to predict REORDER for ambiguous cases. If you shuffle the examples and order them REORDER, HOLD, ESCALATE, HOLD, now HOLD has recency advantage. The model's behavior changes based on a detail you did not intend to matter.

Mitigation strategies include: (1) Randomizing example order across calls, which averages out the bias over a large request volume. (2) Ensemble prompting: making multiple calls with different orderings and taking a majority vote. (3) Moving to a structured format where the relationship between examples and the query is explicit rather than sequential (e.g., XML-tagged examples with a clear separator before the actual query). (4) Fine-tuning: order effects are largely absent in fine-tuned models because the examples are distributed throughout the training data.

For production pipelines where order effects could affect high-stakes decisions (like ORCA's ESCALATE routing), randomizing example order per call is the low-cost mitigation. Log the example order used for each call so you can diagnose order-related variance if you observe it.

### Q3: When does few-shot prompting beat fine-tuning, and when does fine-tuning win?

**Answer:** Few-shot prompting wins when the training data volume is small (fewer than ~1,000 high-quality examples), when the task definition is still evolving (changing examples is free; changing a fine-tuned model costs compute and time), when you need to handle many different tasks in a single deployed model (fine-tuning specializes; few-shot can be swapped per request), and when you need to ship quickly — a few-shot prompt can be tested in minutes, while a fine-tuning run takes hours to days.

Fine-tuning wins when you have a large volume of task-specific data (10,000+ examples), when the task requires consistent stylistic behavior that few-shot examples cannot reliably enforce, when context window cost is a constraint (examples consume tokens; a fine-tuned model does not need them), and when latency is critical at very high throughput (shorter prompts = faster inference = lower cost at scale).

There is a middle ground worth knowing: retrieval-augmented few-shot prompting (also called dynamic few-shot) selects examples from a pool at inference time based on similarity to the current query. This combines the flexibility of few-shot with a larger effective example set. A FAISS or ChromaDB index over ~500 examples, retrieving the top 3-5 most similar to each query, achieves near-fine-tuning performance on classification tasks while remaining fully updateable without model retraining. This is the approach Google would likely use in a production annotation pipeline where ground-truth examples accumulate over time.

### Q4: Explain dynamic few-shot selection. How would you implement it for ORCA's inventory alert classification?

**Answer:** Dynamic few-shot selection is the practice of choosing which examples to include in the prompt based on the current query, rather than using a fixed set. The idea is that the most informative demonstrations for a query are the ones that are most similar to it — if the current SKU is a Class A item with a 3-day lead time, you want examples from your pool that involve Class A items or short lead times, not examples about Class C clearance items.

Implementation requires an example pool with embeddings. You store your labeled examples (SKU alert inputs + correct agent decisions) in a vector database. At inference time, you embed the current query, retrieve the K nearest neighbors from the pool, and inject those as your few-shot examples. The retrieval is the same mechanism as RAG, but instead of retrieving policy documents, you are retrieving worked examples.

For ORCA specifically: (1) Build an example pool from past human-approved routing decisions — each record contains the input alert data, the agent's analysis, and the human's final decision. (2) Embed each example's input using the same embedding model used for RAG (nomic-embed-text-v1.5). (3) At pipeline runtime, embed the incoming alert, retrieve the 3 most similar past decisions. (4) Format these as few-shot examples in the Agent 3 prompt alongside the policy context from RAG. This is a form of case-based reasoning — "here are the 3 most similar situations we have faced and what we decided" — and it significantly improves consistency on unusual SKU profiles that fixed examples might not cover.

The implementation cost is low if RAG infrastructure already exists, as in ORCA. The example pool doubles as both few-shot demonstration storage and as a growing record of human-validated decisions, which is also a valuable audit trail for compliance.

### Q5: Why might few-shot prompting fail even with well-chosen examples, and how do you diagnose this?

**Answer:** The most common failure mode is label leakage through surface features rather than genuine task learning. If all your ESCALATE examples happen to mention "Class A" and all your AUTO_EXECUTE examples mention "Class C," the model may learn to key on the class label rather than the actual escalation logic (cost threshold). When a Class A item falls below the cost threshold, the model incorrectly escalates it because "Class A" is surface-correlated with ESCALATE in the examples.

Diagnosis: ablation testing. Remove one feature from all examples (e.g., remove the SKU class label) and check whether model performance drops dramatically. If removing a supposedly irrelevant feature causes large performance drops, the model was using that feature as a shortcut. Mitigation: rebalance examples so that each label appears with each level of the correlated feature.

Another failure mode is that the examples teach format but not reasoning. The model learns "when the input looks like this, the output looks like that" without understanding why. This typically shows up as poor generalization to inputs that are syntactically different from the examples but semantically identical. Mitigation: use chain-of-thought examples (input → reasoning → output) so the model learns the decision process, not just the input-output mapping.

A third failure mode is context window dilution. With very long examples (detailed agent analyses), 5 examples might consume 80% of the context window, leaving little room for the actual query and retrieved policy context. Symptoms: outputs that seem to reference the examples rather than the actual query, or truncated responses. Mitigation: trim examples to their essential inputs and outputs, removing verbose reasoning unless it is specifically needed for chain-of-thought transfer.

## Key Points to Say in the Interview

- 3-5 examples captures most of the few-shot benefit; more examples show diminishing returns beyond that
- Example selection quality matters more than quantity — diverse, representative, balanced, and correct examples outperform many mediocre ones
- The order effect is real and measurable — recency bias means the last example disproportionately influences the output
- Dynamic few-shot (retrieve examples by similarity to the current query) closes the gap with fine-tuning for many classification tasks
- Few-shot wins on iteration speed and flexibility; fine-tuning wins on cost at very high token volume and strict stylistic consistency
- Always test whether few-shot examples are teaching the right signal (reasoning) or a spurious surface correlation

## Common Mistakes to Avoid

- Using examples that all belong to the same class or scenario — this biases the model toward that class for ambiguous inputs
- Ignoring the order effect — in high-stakes pipelines, example order should be randomized or explicitly controlled
- Treating few-shot prompting as a permanent solution for tasks where fine-tuning would be more appropriate — at large scale, per-call example injection costs compound significantly
- Including examples with incorrect labels or ambiguous inputs — wrong examples actively harm performance and are hard to diagnose
- Not measuring few-shot effectiveness with an eval suite — assuming examples are helping without measuring their actual impact on output quality

## Further Reading

- [Few-Shot Learners (Brown et al., GPT-3 paper)](https://arxiv.org/abs/2005.14165) — the original empirical demonstration that large language models are few-shot learners; establishes the scaling laws for in-context learning
- [Prompt Engineering Guide: Few-Shot Prompting](https://www.promptingguide.ai/techniques/fewshot) — practical reference with examples across different task types
- [What Makes Good In-Context Examples for GPT-3? (Liu et al.)](https://arxiv.org/abs/2101.06804) — research paper on example selection strategies, showing that nearest-neighbor retrieval substantially outperforms random selection
