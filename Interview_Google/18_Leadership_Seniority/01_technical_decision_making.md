# Technical Decision Making at the Senior Level

## What Is It? (Plain English)

Senior engineers are defined not just by the quality of their technical skills, but by the quality of their decisions. A mid-level engineer implements a solution. A senior engineer decides which solution to implement — and can defend that choice to both technical peers and non-technical stakeholders. This distinction matters because at senior levels, your decisions affect not just your own work but the work of an entire team or organization.

Technical decisions range from small (which library to use for a specific function) to large (should we build this on Kubernetes or serverless). The interesting decisions — the ones interviewers will ask you about — are the medium-to-large ones where there was genuine ambiguity, real tradeoffs, and a risk of being wrong. These are also the decisions where process matters most: how did you gather information? Who did you consult? How did you document your reasoning? What was your process for handling the situation where you turned out to be wrong?

The single most important distinction in decision-making that senior engineers understand is the difference between **reversible and irreversible decisions**. Reversible decisions (also called "two-way doors" in Amazon's vocabulary, a concept Google implicitly endorses) should be made quickly, with incomplete information, because you can course-correct if you are wrong. Irreversible decisions (one-way doors) deserve much more careful deliberation: data schema design, public API contracts, infrastructure choices that create deep lock-in. Treating every decision as if it were irreversible leads to paralysis. Treating irreversible decisions as if they were easily reversible leads to expensive migrations and broken contracts.

## How It Works (or: How to Think About This)

The RFC (Request for Comments) process is the standard for making large technical decisions collaboratively:

```
RFC PROCESS FLOW

┌──────────────────────────────────────────────────────────┐
│  PHASE 1: PROBLEM STATEMENT (1 page)                      │
│  • What problem are we solving?                           │
│  • Who is affected?                                       │
│  • What is the cost of not solving it?                    │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│  PHASE 2: OPTIONS ANALYSIS (decision matrix)              │
│                                                           │
│  Criterion     │ Option A   │ Option B   │ Option C      │
│  ─────────────┼────────────┼────────────┼───────────── │
│  Cost          │ Low        │ High       │ Medium        │
│  Scalability   │ Medium     │ High       │ High          │
│  Team famil.   │ High       │ Low        │ Medium        │
│  Op. burden    │ Low        │ High       │ Medium        │
│  Reversibility │ High       │ Low        │ Medium        │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│  PHASE 3: RECOMMENDATION + RATIONALE                      │
│  • Recommended option and WHY                             │
│  • Explicit acknowledgment of what you are giving up      │
│  • What would change your recommendation?                 │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│  PHASE 4: REVIEW PERIOD                                   │
│  • 5-10 days async comment window                         │
│  • Named decision owner who aggregates feedback           │
│  • Decision recorded in writing before execution          │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│  PHASE 5: DECISION RECORD (ADR format)                    │
│  • Context, decision, consequences, status                │
│  • Stored in /docs/adr/ directory in the repo             │
│  • Revisited if assumptions change                        │
└──────────────────────────────────────────────────────────┘
```

Reversibility test for ORCA-like decisions:

```
DECISION                     REVERSIBLE?  PROCESS
──────────────────────────────────────────────────────────
Switch from Groq to OpenAI   YES          Try it, measure, commit
Add a new agent to pipeline  YES          Build behind feature flag
Change SQLite to PostgreSQL  HARD         Full RFC required
Change API response schema   NO           RFC + versioning strategy
Switch from LangGraph to     HARD         RFC required
custom state machine
Add new RAG policy doc       YES          Do it, run Layer 1 eval
Change embedding model       MEDIUM       RFC + eval comparison
```

## Why Google Cares About This

At Google's scale, bad architectural decisions can affect hundreds of engineers for years. The RFC/design doc culture at Google is legendary — every significant technical decision is written up, reviewed, and archived. This is not bureaucracy for its own sake; it is a mechanism for catching mistakes before they are built, for distributing architectural knowledge across teams, and for creating a record that explains why the system is the way it is three years later. Senior candidates who cannot describe their decision-making process clearly signal that their decisions may not have been as deliberate as they should be.

## Interview Questions & Answers

### Q1: Describe a significant technical architecture decision you made. How did you approach it?

**Answer:** When building ORCA, I had to decide whether to implement the 4-agent pipeline using LangGraph's StateGraph or to build a custom state machine in plain Python. Both were technically feasible — plain Python would have given more control, while LangGraph offered built-in checkpointing and the interrupt/resume pattern needed for HITL.

My process started with writing down the key criteria explicitly: did we need the HITL capability at launch (yes, it was a core requirement), did we need the team to be able to understand and modify the code easily (yes, this was a solo project that needed to be maintainable), and did we need to be able to evolve the graph topology without rewriting core infrastructure (yes, we expected to add agents over time). I then evaluated both options against these criteria explicitly rather than just based on familiarity.

LangGraph scored better on every criterion except one: the team (at that point, one person) had zero LangGraph experience, which created an onboarding cost. My decision was to use LangGraph and document the learning curve explicitly in CLAUDE.md. The key piece of reasoning I recorded was: LangGraph's interrupt_before mechanism maps directly to the HITL requirement, and implementing that in custom Python would take more time than learning LangGraph, with higher risk of subtle bugs in the resume logic.

What I would do differently knowing what I know now is also worth noting: I would have run a two-day spike on LangGraph before committing, specifically to validate that the interrupt/resume pattern worked the way the documentation described. The MemorySaver vs SqliteSaver distinction — which matters for production persistence — was something I discovered later rather than upfront.

### Q2: How do you make technical decisions when you do not have complete information?

**Answer:** The first thing I do is distinguish between decisions that need to be made now versus decisions that can be deferred until more information is available. Many decisions that feel urgent are actually not blocking anything — they can wait a week while you gather better data. The ones that are truly blocking need to be made with incomplete information, and the question becomes: which assumption, if wrong, would require the most expensive reversal?

For decisions that must be made with incomplete information, I use a pre-mortem technique: before committing to an option, I spend 30 minutes imagining that the decision turned out to be wrong. Why might it have been wrong? What signals would have appeared early? This exercise often surfaces critical assumptions that I had not made explicit, and it helps identify which of those assumptions can be tested quickly with a small experiment before committing.

For ORCA, the decision to use ChromaDB for vector storage was made with incomplete information — I did not know whether ChromaDB would be stable enough for a multi-threaded FastAPI server under load. The pre-mortem exercise identified this as the key risk. Rather than switching to Pinecone (the "safer" choice), I made the decision with a contingency built in: I isolated all ChromaDB calls behind a single abstraction layer (docs/rag/retriever.py) so that if ChromaDB proved unstable, I could swap it for another vector store by changing one file. That reversibility design reduced the cost of being wrong enough to make the decision comfortable.

The meta-lesson is: with incomplete information, invest in reversibility over optimization. Make the choice that is easiest to undo, even if it is not theoretically the best choice.

### Q3: How do you communicate a complex technical decision to a non-technical stakeholder?

**Answer:** The key is to lead with the business implication of the decision, not the technical mechanism. Non-technical stakeholders do not need to understand how LangGraph works; they need to understand what capability it gives them, what it costs, and what the risks are. My standard format for communicating technical decisions to non-technical stakeholders is: one sentence on what we decided, one sentence on what it enables, one sentence on the main tradeoff or risk, and one sentence on the mitigation.

For the ORCA agent framework decision, that translates to: "We chose LangGraph as the framework for coordinating the four AI agents (decision). This gives us the ability to pause the pipeline mid-way and ask a human manager to approve large orders before they are placed — which is a core safety requirement (what it enables). The tradeoff is that LangGraph is a relatively new framework and the team is still building expertise in it (risk). We have mitigated this by creating extensive documentation in the codebase and by building a Layer 1 evaluation suite that catches regressions automatically (mitigation)."

The most important thing to avoid is using the technical decision communication as an opportunity to demonstrate your technical knowledge. Stakeholders interpret long technical explanations as evidence that the engineer cannot simplify — which they associate with poor judgment. Be prepared to go one level deeper on any point if asked, but start at the highest level and let the stakeholder's questions drive the depth.

### Q4: What is an Architecture Decision Record (ADR) and when would you write one?

**Answer:** An Architecture Decision Record is a short document that captures a significant technical decision, including the context in which it was made, the options considered, the decision reached, and the consequences (both expected and unexpected). ADRs are typically stored in the code repository alongside the code they document, because the code and the reasoning behind the code belong together.

The when-to-write criteria I use: any decision that is not fully obvious from the code itself, any decision that a new team member reading the code would question ("why did they use SQLite instead of PostgreSQL?"), and any decision with significant reversibility risk. For ORCA, the repo already has a docs/adr directory with 5 ADRs covering the LangGraph choice, the RAG hybrid search design, and the HITL implementation approach.

The practical value of ADRs is most visible when the person who made the original decision is no longer available to explain it. Three months after making a decision, you yourself may not remember exactly why you chose one option over another. Two years later, a new team member reading the code may think the decision was wrong and want to change it — but without the ADR, they cannot see the constraints that made it the right choice at the time. ADRs are a form of organizational memory that prevents teams from repeatedly relitigating the same decisions.

### Q5: How do you handle a situation where you need to push back on a technically flawed direction from a senior leader?

**Answer:** The approach I use is to separate the technical concern from the personal dynamics. The goal is not to win an argument; it is to prevent the organization from building something that will hurt them later. With that frame, the conversation changes from "I disagree with your decision" to "I want to make sure we have thought through X before we commit."

My process is: first, write down the specific technical concern as precisely as possible, with a concrete failure scenario. Vague concerns ("I just have a bad feeling about this approach") are easy to dismiss. Specific concerns ("if we use SQLite for a multi-instance deployment, we will have write contention problems that will manifest as intermittent 500 errors under load above N requests per second") are much harder to dismiss because they are falsifiable.

Second, bring data. If I have time before the meeting, I run a quick experiment or find a reference to a similar case. Arriving with "I wrote a benchmark that shows the issue at 10x our current traffic" is fundamentally different from arriving with "I think this might be a problem."

Third, I explicitly ask for a commitment to revisit if the concern materializes. "I want to flag this risk in the design doc and propose that we add a load test at the 30-day mark" gives the leader a way to acknowledge the concern without overturning their decision. Most leaders who are genuinely confident in their direction will accept this kind of conditional deference. If a leader refuses to allow even a documented contingency test, that is a signal about the culture, not just the decision.

## Key Points to Say in the Interview
- The reversible/irreversible distinction is the first question to ask about any significant decision
- RFC/design doc process ensures decisions are explicit, reviewed, and recorded
- Pre-mortems surface hidden assumptions before they become expensive mistakes
- Communicate technical decisions to stakeholders as: decision, capability, tradeoff, mitigation
- ADRs are organizational memory — they prevent teams from relitigating settled decisions
- Push back with specific, falsifiable concerns and data, not vague discomfort
- Build reversibility into irreversible-seeming decisions via abstraction layers

## Common Mistakes to Avoid
- Making decisions without writing them down — creates a knowledge gap that hurts the team months later
- Treating all decisions as if they require the same level of process (RFC for every library choice = paralysis)
- Presenting technical decisions to non-technical stakeholders with too much implementation detail
- Failing to document what you gave up in a decision, not just what you chose
- Confusing "we discussed this verbally" with "we made a decision" — decisions need to be recorded

## Further Reading
- [Michael Nygard: ADR Templates](https://github.com/joelparkerhenderson/architecture-decision-record) — widely used templates for writing Architecture Decision Records
- [Google Engineering Practices: Design Docs](https://google.github.io/eng-practices/) — Google's own guidance on design documentation
- [Amazon Leadership Principles: Bias for Action](https://www.amazon.jobs/content/en/our-workplace/leadership-principles) — explains the reversible/irreversible decision framework in practice
