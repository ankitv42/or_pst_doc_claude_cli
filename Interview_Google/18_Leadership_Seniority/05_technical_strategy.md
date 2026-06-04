# Technical Strategy for AI Teams

## What Is It? (Plain English)

Technical strategy is the deliberate set of choices about what your engineering team will invest in, what it will defer, and what it will stop doing — in service of a specific business or product outcome. It is the answer to the question: given our goals, constraints, and the current technical landscape, what is the most important thing we should build next, and how should we build it?

The word "deliberate" is important. Most teams have an implicit technical strategy — they work on whatever seems most urgent, or whatever the most recent stakeholder asked for, or whatever the most senior engineer is most interested in. An explicit technical strategy is one that has been articulated, debated, documented, and communicated to the whole team. The act of making the strategy explicit forces trade-off decisions that otherwise get deferred, and it creates alignment that allows the team to make consistent decisions without escalating every choice.

For an AI team, technical strategy has a few distinctive elements. First, the "buy vs. build" question is live on almost every component: do you use a managed vector database service or run your own ChromaDB? Do you use a commercial LLM API or fine-tune an open-source model? Do you use a managed agent framework like LangGraph Cloud or self-host? These decisions compound: each "buy" decision adds cost and vendor risk but reduces engineering burden; each "build" decision adds capability and control but increases maintenance obligation. The net of these choices defines the team's operational burden and shapes what they are able to build next.

## How It Works (or: How to Think About This)

The technical strategy document structure:

```
TECHNICAL STRATEGY DOCUMENT STRUCTURE

1. CONTEXT (1 page)
   ├─ Where are we now? (honest current state)
   ├─ Where are we trying to go? (1-2 year vision)
   └─ What constraints shape the choices? (team size, budget, timeline)

2. STRATEGIC BETS (3-5 items maximum)
   ├─ Bet 1: Invest heavily in evaluation infrastructure BEFORE 
   │         adding features (because quality gates are the 
   │         foundation for safe iteration speed)
   ├─ Bet 2: Build on managed APIs (Groq, then OpenAI) rather than 
   │         self-hosting models (because the team is too small to 
   │         maintain model infrastructure)
   └─ Bet 3: Platform the data layer before expanding agent count 
             (because db/queries.py is the most stable part of the 
             system and other components depend on its quality)

3. EXPLICIT DEFERALS (what we are NOT doing and why)
   ├─ Not building a fine-tuned model: insufficient training data
   ├─ Not migrating to PostgreSQL now: SQLite meets current needs
   └─ Not building Layer 3 CI beyond Layer 1: insufficient eval coverage

4. TECHNICAL DEBT MAP (prioritized)
   ├─ CRITICAL: CrewAI + Groq bug in Agent 1 (HIGH priority fix)
   ├─ HIGH: No pytest unit tests for API endpoints
   └─ MEDIUM: Layer 1 keyword calibration may not match actual docs

5. PRINCIPLES (3-5 guidelines for day-to-day decisions)
   ├─ Evaluation before features
   ├─ Hardcode safety constraints; LLM handles judgment only
   └─ Reversible decisions made fast, irreversible decisions deliberated
```

Build vs. buy decision matrix for AI infrastructure:

```
COMPONENT          BUILD          BUY            ORCA CHOICE
─────────────────────────────────────────────────────────────────
LLM inference      Fine-tune      API (Groq/     BUY — team too
                   your own       OpenAI)        small, free tier 
                                                 enough for MVP

Vector storage     Run ChromaDB   Pinecone,      BUILD locally 
                   yourself       Weaviate Cloud (ChromaDB) — free,
                                                 sufficient for 
                                                 71 chunks

Agent framework    Custom state   LangGraph,     BUY (LangGraph)
                   machine        CrewAI         — HITL is too
                                                 hard to build 
                                                 from scratch

Embeddings         Fine-tune      nomic-embed,   BUY — quality
                   domain-        OpenAI ada     sufficient, cost 
                   specific                      manageable

Evaluation         Custom evals   RAGAS,         BUILD custom 
                   (golden set)   DeepEval       Layer 1 — tighter 
                                                 fit to ORCA logic
```

## Why Google Cares About This

At Google, the most impactful engineers are not the ones who write the most code — they are the ones who make the team collectively more effective and move the product in the right direction. Technical strategy is how senior and staff engineers demonstrate organizational influence. An engineer who can write a compelling technical strategy document, get it ratified by stakeholders, and then execute it over 12-18 months is demonstrating the full range of skills that Google promotes for at L6+. Interviewers will ask about technical direction you have set, roadmaps you have defined, or platforms you have created — all of these are expressions of technical strategy.

## Interview Questions & Answers

### Q1: How do you create a technical roadmap for an AI team?

**Answer:** A technical roadmap for an AI team has two inputs that a traditional software roadmap often lacks: a quality dimension and a data flywheel dimension. The quality dimension means that evaluation infrastructure — golden datasets, automated eval suites, quality dashboards — often needs to appear on the roadmap as first-class work items before feature development, because without quality gates you are building on sand. The data flywheel dimension means that many AI improvements require data that can only be collected from running the system, so the roadmap needs to account for feedback loops: ship, collect data, evaluate, retrain or reprompt, re-evaluate.

My process for building the roadmap starts with an honest current-state assessment. For ORCA, that means acknowledging that Layer 2 eval is a stub, that the CrewAI bug is active, that SQLite is a scale ceiling, and that there are no pytest unit tests. These are not just backlog items; they are constraints on what can be safely built next. A team that adds a 5th agent before fixing the Agent 1 bug is adding complexity on top of an unstable foundation.

From that honest baseline, I work backward from a 12-month vision: what does the system look like at the end of the period, and what is the minimum set of investments required to get there? For ORCA, the 12-month vision is a production-grade system that handles 10x current volume, has 85%+ auto-approval acceptance rate, and can be operated by a team member who was not involved in building it. Working backward from that vision, the roadmap is: Q1 fix technical debt (Agent 1 bug, Layer 2 eval, unit tests), Q2 scale the data layer (PostgreSQL migration), Q3 improve recommendation quality (Layer 2-informed prompt improvements), Q4 production hardening (monitoring, alerting, runbooks).

### Q2: How do you manage technical debt in an AI system without stalling product development?

**Answer:** Technical debt in AI systems is more dangerous than in traditional software because it tends to hide until it catastrophically fails. A slow database query creates latency. A miscalibrated RAG retrieval creates silently wrong recommendations that no one catches until an expensive order is placed incorrectly. This asymmetry means that AI teams need to be more aggressive about addressing technical debt than traditional software teams.

The framework I use is to categorize technical debt by failure mode: safety-critical debt (things that, if they fail, cause the system to take harmful actions or produce dangerously wrong outputs), quality-critical debt (things that silently degrade recommendation quality), and reliability debt (things that cause visible failures or increased operational burden). Safety-critical debt is addressed immediately. Quality-critical debt is addressed in the next sprint. Reliability debt is scheduled on the roadmap and tracked as a formal deliverable.

For ORCA, the CrewAI + Groq bug is quality-critical debt — it causes Agent 1 to produce lower-quality demand analysis, which flows into Agent 2 and Agent 3 decisions. It has been tolerable because of the fallback path, but it should be addressed before the system is deployed at higher volume. The no-pytest-unit-tests gap is reliability debt — it means regressions may slip through CI. It is important but not blocking.

The practical mechanism for preventing product development from stalling is the "20% rule": protect 20% of each sprint for technical debt, evaluation improvements, and documentation. This is not a negotiable line item to sacrifice when sprints get full — it is a fixed allocation that prevents the debt from accumulating to the point where it requires a full "debt sprint" later.

### Q3: How do you make a "build vs. buy" decision for a critical AI infrastructure component?

**Answer:** The build vs. buy decision has four dimensions that I work through explicitly: capability fit, cost structure, operational burden, and strategic alignment.

Capability fit: does the bought solution actually do what we need? For ORCA's vector database, ChromaDB meets the capability requirements for a 71-chunk RAG corpus. Pinecone would also meet those requirements, but with more features than needed. When the capabilities match, buy.

Cost structure: at current scale, what is the recurring cost of the bought solution versus the engineering cost of building and maintaining it? ChromaDB is free and open source. Pinecone has a free tier but costs $70+/month at meaningful scale. For an MVP on Groq's free tier, ChromaDB is the right choice. For a production system at a large retailer with millions of chunks, the cost calculus changes and Pinecone or Weaviate Cloud becomes competitive.

Operational burden: how much effort does it take to keep the bought solution running at production quality? Managed services trade cost for operational simplicity. Self-hosted solutions trade cost savings for operational complexity. ORCA uses self-hosted ChromaDB, which is fine while one person maintains it. At 5-person team scale, the operational burden of self-hosting starts to compete with product development time.

Strategic alignment: is this component in your core domain — the thing you are trying to build expertise and differentiation in — or is it infrastructure that supports your core domain? ORCA's core domain is the multi-agent pipeline logic and the inventory management policy encoding. The vector database is infrastructure. You should buy infrastructure and build domain.

### Q4: How do you describe a technical strategy you defined and executed to a Google interviewer?

**Answer:** The structure I recommend for this story is: context, decision, mechanics, outcome, and reflection. Context establishes why a strategy was needed — what was broken or missing that made an explicit strategy necessary. Decision describes the specific strategic choices made and why. Mechanics describes how the strategy was implemented and communicated. Outcome gives concrete, quantified results. Reflection shows that you learned from the experience and would refine the approach.

For ORCA, the technical strategy story might go: Context — the project had a working prototype but no quality measurement infrastructure, so every change was a leap of faith. The team (solo at that point) could not tell if a prompt change improved or degraded recommendation quality. Decision — I made the explicit strategic bet to build evaluation infrastructure before adding new features, and to run evaluations as a CI gate rather than a manual process. This meant deferring the Layer 2 LLM judge (too complex for MVP) and committing to a Layer 1 golden dataset approach that could be implemented and run in under 10 minutes. Mechanics — I wrote 11 golden test cases against the five policy documents, implemented the retrieval eval in run_retrieval_eval.py, and added it to the CI pipeline via GitHub Actions. Outcome — the eval suite runs on every push to main, catches retrieval regressions automatically, and has already caught two cases where a prompt change degraded RAG retrieval quality before it shipped. Reflection — I would have built the eval suite before writing any agent code, not after. Retrofitting evals is harder than building them alongside the system because you have to reverse-engineer what the system was supposed to do.

### Q5: How do you balance platform thinking with product thinking on an AI team?

**Answer:** Platform thinking and product thinking are two different lenses on the same work, and the right balance depends on where the team is in its maturity curve. Early-stage teams should lean heavily toward product thinking: ship features that solve real problems, measure business impact, iterate based on user feedback. Platform investments that are not yet demanded by multiple products are premature.

As the team matures and multiple products start sharing infrastructure — shared embedding models, shared evaluation frameworks, shared feature stores — platform thinking becomes necessary. Without it, each product team builds its own version of the same infrastructure, creating duplication, inconsistency, and the operational burden of maintaining N copies.

The forcing function for platform investment is when the same infrastructure pain appears in three or more different places. If two different AI features both need a way to evaluate LLM output quality, that is a signal to build a shared evaluation framework (like RAGAS or a custom eval suite) rather than having each team build their own. If three different features all retrieve from the same vector store, that is a signal to platform the retrieval layer.

For ORCA, the platform candidate is the RAG retrieval component. The hybrid search with BM25 + vector + RRF + reranking in docs/rag/retriever.py is sophisticated enough that other agent features should not have to reinvent it. The public API (query_for_agent1, query_for_agent2, etc.) is a step in that direction — it is a platform interface that abstracts the retrieval complexity from the agent code. The next platform investment would be making that interface configurable enough to serve multiple different retrieval needs without hard-coding agent-specific versions.

## Key Points to Say in the Interview
- Technical strategy is explicit, written, debated, and communicated — not the sum of individual decisions
- Quality infrastructure (evals, monitoring) is a strategic investment that precedes features, not follows them
- Categorize technical debt by failure mode: safety-critical (fix now), quality-critical (next sprint), reliability (scheduled)
- Build vs. buy: buy infrastructure, build domain; managed services trade cost for operational simplicity
- Platform investment is triggered when the same infrastructure pain appears in 3+ places
- The 20% rule: protect 20% of every sprint for technical debt and evaluation improvements

## Common Mistakes to Avoid
- Treating the technical roadmap as a pure feature list without quality and debt items
- Deferring all technical debt until it creates a crisis requiring a dedicated "debt sprint"
- Making build vs. buy decisions based on preference rather than capability, cost, burden, and strategy
- Building platform infrastructure before there is demonstrated demand from multiple products
- Failing to communicate the strategy to the team — a strategy that only exists in one person's head is not a strategy

## Further Reading
- [Will Larson: Staff Engineer](https://staffeng.com/book) — detailed treatment of technical strategy at Staff+ levels
- [Martin Fowler: Technical Debt Quadrant](https://martinfowler.com/bliki/TechnicalDebtQuadrant.html) — framework for categorizing and prioritizing technical debt
- [a16z: Technical Roadmaps for AI Products](https://a16z.com/ai-product-strategy/) — essays on AI-specific strategic planning from practitioners
