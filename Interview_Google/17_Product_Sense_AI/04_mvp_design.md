# MVP Design for AI Products

## What Is It? (Plain English)

A Minimum Viable Product (MVP) for an AI feature is the simplest version you can build that is useful enough to learn from real usage. The "minimum" part is about scope: you are intentionally choosing what to leave out so you can ship faster and validate your assumptions before committing more resources. The "viable" part is critical: an MVP is not a prototype that falls apart under use. It has to work well enough that users will actually use it, because real usage is the only way to get the data you need to improve.

The most common mistake in AI MVP design is starting with the AI. Counterintuitively, the right MVP for an AI system is often a non-AI system. A rule-based system that hardcodes domain expert logic — "if stock days remaining < 5 AND reorder lead time < 7 days, then flag for reorder" — is faster to build, easier to debug, and produces labeled data that you can later use to train or evaluate an AI model. If the rule-based system already solves 80% of the problem, the ROI on adding AI needs to be re-examined. If the rule-based system fails on important edge cases, those edge cases become the clearest specification for what the AI needs to handle.

In ORCA's case, the right MVP sequence was: (1) build the data pipeline and alerting system that detects stockout risk, (2) build a deterministic rule engine that makes standard reorder recommendations, (3) add a human review workflow for edge cases and high-cost orders, (4) replace specific parts of the rule engine with AI agents where the rules become too complex. What actually happened in most AI projects — including some at major companies — is that teams jumped straight to building the AI without establishing a rule-based baseline. This means they have no way to measure whether the AI is better than the alternative.

## How It Works (or: How to Think About This)

The MVP Design Ladder for AI features:

```
STAGE 4: FULL AI PIPELINE (current ORCA state)
  ├─ 4-agent LangGraph pipeline
  ├─ RAG policy retrieval
  ├─ CrewAI sub-crew for demand analysis
  └─ HITL with interrupt/resume
  BUILD THIS when: Stage 3 shows the rule engine
  has clear failure modes AI can address

STAGE 3: HYBRID (rules + selective AI)
  ├─ Rule engine handles standard cases (80%)
  ├─ AI called only for ambiguous edge cases (20%)
  └─ Human review for high-cost orders
  BUILD THIS when: Stage 2 shows your rules
  break on complex inventory scenarios

STAGE 2: RULE-BASED + HITL
  ├─ Deterministic rules for reorder logic
  ├─ Human review dashboard
  └─ Feedback collection on all decisions
  BUILD THIS when: Stage 1 shows the alerting works
  and the data model is correct

STAGE 1: ALERTING ONLY (true MVP)
  ├─ Data ingestion pipeline
  ├─ Stockout risk calculation
  └─ Simple notification to analyst
  BUILD THIS first, always
```

Risk de-risking framework:

```
ASSUMPTION                → HOW TO TEST WITH MVP
────────────────────────────────────────────────────
"Analysts will use it"    → Build Stage 1, watch 
                            adoption rate over 30 days

"Data is reliable"        → Build Stage 1, measure
                            alert false positive rate

"Rules handle 80% of cases"→ Build Stage 2, track
                            how often humans override

"AI adds value over rules"→ Build Stage 3 with 
                            shadow mode, compare
                            AI vs rule recommendations
                            on same cases
```

## Why Google Cares About This

Google has a strong "build fast, learn, iterate" culture rooted in the principle that assumptions are dangerous and real user data is the only reliable signal. MVP thinking is how Google avoids expensive bets on features users do not want or technology that does not work in practice. For AI products specifically, the risk of over-building is higher than in traditional software: LLMs are expensive to run, complex to debug, and prone to subtle quality failures that only appear at scale. Senior candidates who demonstrate the discipline to sequence their AI investment — starting simple, measuring, then expanding — signal that they manage risk well and will not waste team resources on premature complexity.

## Interview Questions & Answers

### Q1: What would the right MVP have been for ORCA before building the 4-agent pipeline?

**Answer:** The right MVP would have been a rule-based stockout alerting system with a simple analyst dashboard — no AI at all. The reason for this sequencing is that before you invest in a 4-agent LangGraph pipeline, you need to validate three assumptions that many teams skip: that the data pipeline is reliable, that analysts will actually use a tool to review inventory decisions, and that the reorder logic is complex enough to benefit from AI.

The Stage 1 MVP would have been: ingest inventory data from all stores, calculate a "days of stock remaining" metric per SKU, flag any SKU below a threshold (say, 5 days), and send a daily notification to the inventory analyst. This is perhaps 2 weeks of engineering work. After 30 days, you know whether the alerting is producing actionable signals (or mostly noise), whether the data quality issues are manageable, and whether analysts find the alerts useful enough to act on.

The Stage 2 MVP would add a simple rule engine: given an alert, calculate the standard reorder quantity using the existing EOQ (Economic Order Quantity) formula, pre-fill an order recommendation, and give the analyst a one-click approve workflow. This validates whether the recommendation workflow increases analyst efficiency — and it also starts collecting labeled data (approved vs. modified vs. rejected recommendations) that is invaluable for later AI development.

Only after Stage 2 is running and you can see that analysts are regularly modifying the rule-based recommendations in ways that follow a pattern — that is the signal that AI would add value. Those modifications are the AI training signal. Without that signal, you are building an AI to solve a problem you have not yet fully understood.

### Q2: How do you decide what to hardcode versus what to make intelligent in an AI product?

**Answer:** A useful heuristic is: hardcode anything that is a business rule that will not change, and make intelligent anything that requires context-sensitive judgment. Business rules are things like "we never place a partial order for Class A SKUs" (ORCA's Agent 2 hard rule) — this is a policy decision, not a judgment call, and it should not be delegated to an LLM that might occasionally forget it. Context-sensitive judgments are things like "how much demand increase does this promotion imply?" — this is exactly the kind of nuanced pattern recognition that LLMs handle better than explicit rules.

The danger of making too much intelligent is that it becomes harder to reason about the system's behavior, debug failures, or explain decisions to auditors. If the Class A SKU rule were implemented as an LLM instruction ("please never recommend partial orders for Class A SKUs"), you would periodically get pipeline runs where the LLM ignores it, especially for novel edge cases. The hard-coded rule in Python never ignores it.

A practical test for where to draw the line is to ask: "Could a domain expert write this rule down in an Excel spreadsheet?" If yes, hardcode it. If the rule requires reading 200 pages of policy documents and synthesizing them in context — that is what the RAG + LLM is for. The architecture of ORCA actually follows this principle well: the routing logic in Agent 4 is pure Python (hardcoded thresholds), while the demand analysis and option generation are LLM-based (context-sensitive).

The third consideration is safety: any rule that, if violated, has a significant negative consequence should be hardcoded. In an inventory system, always check the budget ceiling in Python before executing an order, even if the AI also checked it. Defense in depth means the hardcoded rules are a backstop against AI errors at the critical boundary between "recommendation" and "action."

### Q3: How do you de-risk an AI investment before writing a single line of model code?

**Answer:** There are four types of risk in an AI project: data risk (the training or retrieval data does not actually support the task), task risk (the AI cannot solve the problem reliably enough to be useful), adoption risk (users will not change their behavior to use the AI), and integration risk (the AI cannot be integrated into the existing workflow at acceptable cost or latency). Each of these can be de-risked with low-cost experiments before committing to the full build.

Data risk: Before writing any model code, do a manual qualitative analysis of the data you plan to use. For ORCA's RAG component, this meant reading the 5 policy documents and asking: are these documents actually policy guidance, or are they procedural documentation? Do they contain the specific constraints that Agent 2 and Agent 3 need? This manual review would take a day and would surface any fundamental data quality issues before you spend two weeks building an ingestion pipeline.

Task risk: Run a "Wizard of Oz" experiment — have a human pretend to be the AI for a small number of test cases. If a human analyst, given the same inputs as the AI (inventory data, demand trends, retrieved policy docs), cannot produce a consistent, high-quality recommendation, that is a strong signal that the task is underspecified. If the human produces good, consistent recommendations, you know the task is learnable and the data is sufficient.

Adoption risk: Shadow mode is the best tool here. Build the AI system but do not change the existing workflow. Have the AI produce recommendations alongside the current process for 2-4 weeks. Measure: how often do the AI recommendations match what the analyst would have done anyway? How often does the analyst say "I wish I had seen this AI recommendation before I made my decision"? This directly measures the AI's added value before you commit to changing the workflow.

### Q4: What is the relationship between MVP thinking and technical debt in AI systems?

**Answer:** MVP thinking, done correctly, actually reduces technical debt, because it forces you to build only what you need right now and to make deliberate, documented decisions about what you are deferring. The problem is that many teams treat "MVP" as an excuse to cut corners on the things that do not affect the demo — monitoring, testing, documentation, data validation — and these are exactly the things that create technical debt.

For ORCA, the MVP discipline looks like: shipping with llama-3.1-8b-instant on Groq's free tier (a deliberate deferral of production-grade model selection), but also shipping with a Layer 1 retrieval eval that runs on every push (not deferred, because RAG quality is too important to leave unmonitored). The Agent 1 CrewAI bug is an example of incurred technical debt: the fallback is functional, but the sub-crew was the original design intent and the bug makes Agent 1's output less reliable. That is a debt you carry until you fix it.

The meta-principle is: the things you defer in an MVP should be things that are reversible — model upgrades, UI polish, additional agents. The things you should not defer are irreversible structural decisions — data schema design, evaluation framework, API contract. If you get those wrong in the MVP and build features on top of them, the cost of fixing them grows exponentially. ORCA's clean separation between the data layer (db/queries.py), the agent layer, and the API layer is a good example of not cutting corners on structure, even in an MVP.

### Q5: How do you present an MVP proposal to a stakeholder who wants the full-featured AI system immediately?

**Answer:** The most effective approach is to reframe the MVP not as a lesser version of what they want, but as a risk-reduction strategy that gets them to the full system faster and with higher confidence. Stakeholders who push for the full system immediately are usually expressing a concern: they do not want to waste time on a watered-down version when the real value is in the complete AI. Addressing that concern directly is more effective than arguing for the MVP on its own terms.

My standard framing is: "I can build the full system in 12 weeks, and there is a 40% chance we will discover in week 10 that a core assumption was wrong and need to rebuild part of it. Or I can build the alerting and rule-based layer in 3 weeks, validate our assumptions with real data in weeks 4-6, and then build the AI layer on top in weeks 7-12 — with much higher confidence that we are solving the right problem. The total timeline is similar, but the risk-adjusted outcome is much better with the staged approach."

Concrete examples from other AI projects are powerful here. The history of enterprise AI is full of projects that built the full system first — 18 months of work — and then discovered that users did not adopt it, or that the underlying data quality was insufficient, or that the "AI" was solving a problem the business had already solved another way. Citing one such example (without naming specifics) makes the risk real and concrete for the stakeholder.

If the stakeholder still insists on the full system, the right response is to negotiate scope within the full system: "Okay, we'll build all four agents, but Agent 1 will use a simplified demand analysis for V1 and we will log all the edge cases it handles poorly for V2 improvement." That is MVP thinking applied at the feature level rather than the system level, and it is usually an acceptable compromise.

## Key Points to Say in the Interview
- The right MVP for an AI system often contains no AI at all — start with rules and data
- Always validate data quality, task feasibility, and user adoption before committing to AI
- Hardcode business rules in Python; use LLMs for context-sensitive judgment only
- Shadow mode experiments let you measure AI value before changing the existing workflow
- MVP should defer reversible decisions (model choice, UI) but not irreversible ones (data schema, API contract)
- Staged builds reduce risk without extending the total timeline materially

## Common Mistakes to Avoid
- Starting the MVP with the AI component rather than the data and alerting infrastructure
- Using "MVP" as an excuse to skip monitoring, evaluation, and data validation
- Building all four agents simultaneously when Agent 3 alone would validate the core hypothesis
- Failing to collect labeled data from the rule-based phase that can later be used to evaluate AI quality
- Presenting a simplified MVP to stakeholders without explaining the risk reduction rationale

## Further Reading
- [Shreyas Doshi on Ruthless Prioritization](https://twitter.com/shreyas/status/1218483712122404865) — practical framework for MVP scope decisions from a senior product leader
- [a16z: Building AI Products](https://a16z.com/ai/) — essays on AI product development including MVP and iteration patterns
- [LangGraph Quickstart](https://langchain-ai.github.io/langgraph/tutorials/introduction/) — shows how incrementally building a LangGraph pipeline mirrors MVP thinking
