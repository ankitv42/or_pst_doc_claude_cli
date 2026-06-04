# Chain of Thought Prompting

## What Is It? (Plain English)

Chain-of-thought (CoT) prompting is the technique of asking a language model to show its reasoning steps before giving a final answer. Instead of just "What is the answer?", you ask "Think through this step by step, then give the answer." The model produces a visible reasoning trace — a chain of thoughts — and the final answer is derived from that trace rather than generated directly.

The analogy is to how a good student solves a math problem: they do not just write the final number, they write out each step. Showing the work serves two purposes — it guides the student to the correct answer (because each step is checked against the previous one), and it makes the reasoning visible and checkable. Chain-of-thought does the same for language models: the intermediate reasoning steps serve as a scaffold that leads the model toward more accurate conclusions, especially on problems that require multiple sequential deductions.

Before chain-of-thought was discovered, large language models performed surprisingly poorly on multi-step arithmetic, logical reasoning, and commonsense reasoning tasks. A simple 3-step math word problem that a human solves easily would fool a large model asked for a direct answer. Adding "Let's think step by step" to the prompt immediately improved accuracy dramatically — sometimes from below 20% to above 70% on the same benchmark. This was one of the most impactful discoveries in prompt engineering.

## How It Works

Chain-of-thought can be applied in two ways: zero-shot (just append the trigger phrase) or few-shot (provide example reasoning chains):

```
STANDARD PROMPTING           CHAIN-OF-THOUGHT PROMPTING
────────────────────         ────────────────────────────────────
Q: SKU A-1234                Q: SKU A-1234
   Stock: 45 units              Stock: 45 units
   Daily demand: 8              Daily demand: 8
   Lead time: 7 days            Lead time: 7 days
   Unit cost: $340              Unit cost: $340
                             
   Should we escalate?          Think step by step.
                             
A: Yes, escalate.            A: Step 1: Days of stock remaining
                                = 45 / 8 = 5.6 days.
   ← direct but potentially     Step 2: Lead time = 7 days.
     wrong; hard to debug        Lead time > days remaining,
                                so stockout is certain before
                                replenishment arrives.
                                Step 3: Reorder quantity needed
                                = (7 + safety_stock_days) × 8
                                = (7 + 7) × 8 = 112 units.
                                Step 4: Cost = 112 × $340
                                = $38,080. Below $50K threshold.
                                Conclusion: AUTO_EXECUTE.
                             
                                ← traceable, auditable, correct
```

The key insight is that by generating the intermediate steps, the model is forced to commit to each fact before using it in the next step. Errors are caught earlier in the chain rather than propagated silently to the final answer.

## Why Google Cares About This

Google's AI products (Bard/Gemini, Search AI summaries, code generation tools) all use reasoning-heavy prompting internally. Chain-of-thought is a core technique for improving reliability on complex tasks without model retraining. At the senior level, interviewers expect you to know not just that CoT exists, but when it helps (multi-step reasoning), when it hurts (simple factual recall), and what the advanced variants are (tree-of-thought, self-consistency). The ability to design a prompting strategy that matches the task complexity is a key competency.

## Interview Questions & Answers

### Q1: Why does chain-of-thought improve accuracy on reasoning tasks, and what is the underlying mechanism?

**Answer:** The core mechanism is that autoregressive language models generate tokens sequentially, and each generated token becomes conditioning context for the next one. When a model is forced to produce intermediate reasoning steps, those steps serve as a working memory that constrains subsequent generation toward conclusions that are consistent with the established chain of reasoning.

Consider a multi-step problem: "If inventory turnover is 12x per year and current stock is 500 units, how many days of supply remain?" Without CoT, the model attempts to map the input directly to the output. The attention mechanism must bridge from the question to the answer across many semantic steps, and the probability mass is distributed across many plausible-but-wrong numeric answers. With CoT, the model first generates "Turnover of 12x/year means replenishment cycle = 365/12 ≈ 30 days," then uses that grounded intermediate result to compute "500 units / (500/30) units-per-day = 30 days of supply." Each step narrows the output distribution toward the correct continuation.

This is why CoT works best on tasks that have a verifiable intermediate structure: arithmetic, symbolic logic, multi-hop reasoning, planning sequences. It is less effective on tasks where the answer is a direct lookup from memorized knowledge — asking "What is the capital of France?" with CoT just produces "Let me think... Paris is the capital of France. Answer: Paris" which is correct but the reasoning trace added nothing. Worse, for simple factual questions, CoT can introduce errors by overcomplicating the path to an obvious answer.

The scale threshold matters: Wei et al. (2022) showed that chain-of-thought only reliably improves performance in models above roughly 100 billion parameters. Smaller models produce incoherent reasoning chains that actually hurt accuracy. This is relevant when choosing between model sizes — a smaller, faster model might not benefit from CoT at all.

### Q2: Explain zero-shot CoT vs. few-shot CoT. Which is better in practice?

**Answer:** Zero-shot CoT uses a trigger phrase — the canonical one is "Let's think step by step," but "Think carefully and reason through this step by step" works similarly — appended to the prompt without providing example reasoning chains. The model generates its own reasoning path. This was discovered by Kojima et al. (2022) and is remarkable because such a simple addition produces large accuracy gains.

Few-shot CoT provides 3-5 example input/reasoning chain/answer triplets in the prompt before the actual question. The model observes the expected reasoning style and length from the examples and produces a reasoning chain in the same format. This consistently outperforms zero-shot CoT because: (1) the examples anchor the reasoning format (how many steps, what level of detail), (2) the examples demonstrate the correct reasoning pattern for the task domain, and (3) the model's few-shot pattern matching reinforces the CoT behavior beyond the trigger phrase alone.

In practice, the choice depends on your constraints. Zero-shot CoT is better when: you have no labeled examples, the task definition is still evolving, or prompt length is constrained. Few-shot CoT is better when: you have labeled reasoning chains, the task has a specific reasoning pattern you need to enforce, or you are seeing inconsistent reasoning structure from zero-shot. For ORCA's agents, the prompts implicitly use zero-shot CoT by asking agents to provide a "rationale" field, which encourages the model to document its reasoning even when not explicitly told to "think step by step."

A practical hybrid: few-shot examples that demonstrate the correct answer but only brief reasoning ("Stock < reorder point AND cost > threshold → ESCALATE"), combined with a zero-shot CoT trigger for the actual query. This keeps example length short while still eliciting detailed reasoning on the real problem.

### Q3: What is self-consistency decoding, and when should you use it?

**Answer:** Self-consistency is an extension of chain-of-thought where you sample multiple reasoning paths (with temperature > 0) and take a majority vote over the final answers. Instead of one CoT trace, you generate 10-20, then count how many arrive at each candidate answer and return the most common one. The intuition is that correct reasoning paths are more likely to converge on the right answer than wrong ones — diverse wrong paths reach diverse wrong answers, which cancel each other out in the vote, while the correct path is consistently reached.

Self-consistency significantly improves accuracy on math and logic benchmarks (often 5-15 percentage points on top of CoT alone) at the cost of N times the inference compute and latency. It is best used for high-stakes offline tasks where accuracy matters more than speed: medical diagnosis support, legal document analysis, complex financial modeling, or batch analytics pipelines where results are computed once and used many times.

For ORCA, self-consistency would be appropriate for the Capital Allocation scoring in Agent 3, where the formula is deterministic but the model's application of it to edge cases can vary. Running 5 completions and taking a majority vote on the ESCALATE/AUTO_EXECUTE/SUSPEND decision would reduce the variance in routing decisions — especially for borderline cases near the cost threshold. The cost is 5x the token spend on Agent 3 calls, which may be acceptable for high-value SKU alerts above a certain cost threshold.

When not to use self-consistency: real-time interactive applications (too slow), tasks with unique correct answers that depend on the specific context (majority vote is nonsensical), and tasks where the reasoning chain is as important as the answer (legal or medical explanations where you need to show the specific reasoning, not just count votes).

### Q4: What is Tree of Thought (ToT) prompting and how does it differ from chain-of-thought?

**Answer:** Tree of Thought is a generalization of chain-of-thought where the model explores multiple possible reasoning paths in parallel and applies an explicit evaluation step to decide which branch to continue. Chain-of-thought is a linear sequence of reasoning steps (a chain); Tree of Thought is a search tree where at each step the model proposes multiple continuations, evaluates each, and either continues the promising ones or backtracks from dead ends.

The architecture looks like a deliberate search process:

```
                [Problem Statement]
                        |
          ┌─────────────┼─────────────┐
       [Path A]      [Path B]      [Path C]
      Reorder 200   Reorder 100   Expedite
          |              |              |
       Evaluate       Evaluate       Evaluate
       Score: 0.8    Score: 0.6    Score: 0.5
          |
       Continue...
          |
       [Final Answer from best path]
```

ToT is most useful for tasks that require search, planning, or creative exploration — problems where the first reasoning path is unlikely to be optimal and backtracking is necessary. Classic examples: puzzle solving, code debugging (where multiple debugging hypotheses need exploration), strategic planning (where multiple approaches should be evaluated before committing).

The implementation complexity is high: ToT requires multiple LLM calls per problem (the proposer and the evaluator can be the same model or different), a tree-search algorithm (BFS or MCTS), and a stopping criterion. For most production AI applications, the accuracy gains over standard CoT do not justify this complexity. The exception is when you need the model to generate and evaluate multiple distinct options — exactly what ORCA's Agent 2 does when constructing three reorder options (standard, partial, expedite). Agent 2 is implicitly doing a limited form of ToT by generating multiple paths and presenting them for evaluation. A full ToT implementation would also evaluate and rank those options within the same model call.

### Q5: When does chain-of-thought hurt performance rather than help it?

**Answer:** Chain-of-thought reliably hurts performance on tasks where the correct answer is a direct factual recall that does not benefit from sequential reasoning. For "What year was the first iPhone released?", asking the model to think step by step produces: "Let me think... Apple was founded in 1976... Steve Jobs returned in 1997... The iPhone was announced at Macworld... The original iPhone was released in 2007." This is correct, but the CoT trace is a reconstruction post-hoc, not a genuine reasoning chain. Worse, for questions where the model's knowledge is genuinely uncertain, the CoT trace can lead the model down a garden path of plausible-sounding but incorrect intermediate steps, arriving at a confident wrong answer that it would not have given with a direct response.

For classification tasks with simple decision rules, CoT can introduce errors. If an inventory alert classifier needs to output CRITICAL / HIGH / MEDIUM based on days-of-supply brackets (< 7 = CRITICAL, 7-14 = HIGH, > 14 = MEDIUM), asking the model to reason about this before classifying can lead it to over-think ambiguous boundary cases that a rule-based lookup would handle correctly. In these cases, the correct solution is not CoT but a structured prompt with explicit decision rules.

CoT also hurts when the model is small (under ~7B parameters). Small models lack the capacity to generate coherent reasoning chains and instead produce random-sounding intermediate steps that corrupt the final answer. On small models, zero-shot direct prompting with clear instructions and few-shot format examples typically outperforms CoT.

Finally, CoT increases token count — both input tokens (the reasoning trigger and few-shot examples) and output tokens (the reasoning trace itself). For high-volume, latency-sensitive applications, the added cost can make CoT economically infeasible. In these cases, consider distillation: use CoT to generate correct answers offline, then fine-tune a smaller model on the (question, answer) pairs to internalize the reasoning without needing to generate it at inference time.

## Key Points to Say in the Interview

- Chain-of-thought works because intermediate reasoning steps serve as a working memory that constrains subsequent generation toward consistent conclusions
- Zero-shot CoT ("Think step by step") is a free accuracy boost on reasoning tasks; few-shot CoT is better when you have labeled reasoning examples
- CoT only reliably helps models above ~100B parameters; avoid it for small models where it can actually hurt accuracy
- Self-consistency (sample N paths, majority vote) is the accuracy-maximizing extension of CoT at the cost of N times the compute
- Tree of Thought is the search-tree generalization of CoT — powerful for planning and puzzle tasks but high implementation complexity
- CoT hurts on direct factual recall, simple rule lookups, and small models — know when not to use it

## Common Mistakes to Avoid

- Assuming CoT always improves performance — test it on your specific task and model size, as it can hurt on simple lookup tasks
- Using CoT on small models (under 7B) without empirical validation — the reasoning chains degrade and can reduce accuracy
- Treating the reasoning trace as ground truth — the model can generate confident but incorrect reasoning chains; the final answer must still be validated
- Not accounting for the additional token cost of reasoning traces in production cost estimates — CoT can 2-5x output token volume
- Forgetting self-consistency as an option for batch, high-stakes tasks where the additional compute is justified by accuracy gains

## Further Reading

- [Chain-of-Thought Prompting Elicits Reasoning (Wei et al., 2022)](https://arxiv.org/abs/2201.11903) — the original CoT paper demonstrating few-shot reasoning chains on math and logic benchmarks
- [Large Language Models are Zero-Shot Reasoners (Kojima et al., 2022)](https://arxiv.org/abs/2205.11916) — the zero-shot CoT paper introducing "Let's think step by step"
- [Tree of Thoughts: Deliberate Problem Solving with LLMs (Yao et al., 2023)](https://arxiv.org/abs/2305.10601) — the ToT paper with game-of-24 and creative writing benchmarks showing search-based reasoning
