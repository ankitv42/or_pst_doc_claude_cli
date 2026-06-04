# Architecture Reviews

## What Is It? (Plain English)

An architecture review is a structured discussion where a team presents a proposed technical design and a group of senior engineers evaluates it before any significant code is written. The purpose is to catch mistakes and gaps early, when they are cheap to fix, rather than after six months of implementation when they are expensive. It is not a rubber-stamp ceremony — a good architecture review should produce concrete feedback that changes the design in measurable ways.

Architecture reviews are distinct from code reviews in scope and timing. A code review happens after the code is written and checks that the implementation is correct. An architecture review happens before significant implementation begins and checks that the approach itself is sound. The questions in a code review are: is this code correct, readable, and secure? The questions in an architecture review are: are we building the right thing, in the right way, on the right foundations?

At senior levels, you will both receive architecture reviews (when proposing a new system) and lead or participate in architecture reviews (when evaluating proposals from others). The ability to lead a review — to ask the questions that expose weaknesses without demoralizing the presenter, to give structured feedback that is actionable rather than vague, and to drive toward a clear outcome within a time-boxed meeting — is one of the key behavioral differences between staff-level and senior-level engineers.

## How It Works (or: How to Think About This)

The standard AI system architecture review checklist:

```
ARCHITECTURE REVIEW CHECKLIST FOR AI SYSTEMS

1. DATA LAYER
   ├─ Where does the data come from? What is the SLA on data freshness?
   ├─ What happens if the data source is unavailable?
   ├─ How is PII handled? What data is stored, for how long?
   └─ How is data quality validated? What is the false-positive rate?

2. MODEL / AI LAYER  
   ├─ What model(s) are used? What is the cost per inference?
   ├─ How is model quality evaluated? Is there a golden dataset?
   ├─ What is the failure behavior? Is there a fallback?
   └─ How does the model handle edge cases / distribution shift?

3. INTEGRATION LAYER
   ├─ How does the AI output integrate with downstream systems?
   ├─ Is the API contract versioned? What is the deprecation policy?
   ├─ What is the SLA on latency and availability?
   └─ How are partial failures handled (circuit breaker, retry)?

4. OPERATIONAL LAYER
   ├─ How is the system monitored? What are the alert thresholds?
   ├─ How do you deploy a new model version safely (canary, blue-green)?
   ├─ What is the rollback procedure?
   └─ Who is on-call? What runbooks exist?

5. SECURITY LAYER
   ├─ What can the AI access? Is least-privilege enforced?
   ├─ Can the AI be manipulated by adversarial inputs (prompt injection)?
   ├─ How are API keys and credentials managed?
   └─ What is the audit log for AI-initiated actions?

6. SCALABILITY
   ├─ What is the expected load? What is the load at 10x?
   ├─ What breaks first under load?
   ├─ Is state shared across instances? (SQLite is a common trap here)
   └─ How is rate limiting handled for external API calls?
```

Common anti-patterns in AI systems with examples:

```
ANTI-PATTERN              EXAMPLE                  CORRECT APPROACH
──────────────────────────────────────────────────────────────────────
God Agent                 One LLM call handles      Separate agents with
                          all reasoning             single responsibilities

Prompt in Code            System prompt hardcoded   Prompts in prompts.py
                          in graph.py               or a prompt registry

No Fallback               CrewAI fails →            Fallback to simpler
                          pipeline crashes          output path

Raw SQL Scattered          db.execute("SELECT...")   All queries in
                          in every file             db/queries.py

No Evaluation             Ship without golden       Layer 1 eval with
                          dataset or CI gate        golden dataset + CI

Synchronous Everything    FastAPI blocks on         202 + background task
                          60-second LLM calls       + polling pattern

Shared Mutable State      SQLite in multi-process   PostgreSQL or
                          FastAPI deployment         process-safe DB
```

## Why Google Cares About This

Google's engineering culture is built on the design document review process. At Google, nothing significant gets built without a design doc, and design docs are reviewed by relevant stakeholders before the project starts. Senior engineers at Google are expected to be proficient at both writing and reviewing design docs — this is not optional for promotion to Staff or Principal. The ability to quickly identify the three most important weaknesses in a proposed architecture, articulate them clearly, and propose specific fixes is a direct marker of senior-level engineering judgment.

## Interview Questions & Answers

### Q1: What are the most important questions to ask when reviewing an AI pipeline architecture?

**Answer:** I group the questions into four categories, in order of importance. The first category is failure behavior: what happens when the AI is wrong, slow, or unavailable? Many architecture proposals describe the happy path in great detail but give minimal attention to failure modes. For an inventory pipeline, I want to know: if the LLM call times out, does the pipeline return an error or fall back to a rule-based recommendation? If the vector database is unavailable, can the pipeline continue without RAG context? These failure questions often reveal the brittleness of an architecture before it is built.

The second category is cost and scale: what does one pipeline run cost in API fees, and what happens to that cost at 10x current volume? I ask reviewers to work through the math explicitly in the design doc. For ORCA at 500 runs/day and $0.15 per run, that is $75/day or $2,250/month. At 10x volume (5,000 runs/day), that is $750/day or $22,500/month. Is the budget ceiling in Agent 4's routing logic going to hold at that volume, or does the cost model change?

The third category is observability: how will you know when this system is degrading? A pipeline that produces wrong outputs silently is often worse than one that fails noisily. The review question I ask is: "Show me the dashboard you would look at if an on-call engineer called you at 2am saying something is wrong." If the presenter cannot describe that dashboard, the system is not sufficiently instrumented.

The fourth category is the human-in-the-loop contract: who is responsible for the AI's outputs, and how are they held accountable? For any AI system that initiates actions with real-world consequences (placing orders, sending notifications, making approvals), the architecture must include an audit trail, a clear escalation path, and a mechanism for humans to override or roll back the AI's decisions.

### Q2: How do you give effective feedback in an architecture review without demoralizing the author?

**Answer:** The most effective framework I use is to structure feedback as questions rather than corrections, at least initially. "Have you considered what happens when the supplier API is unavailable?" is much easier to receive than "You missed the supplier API failure case." Both convey the same gap, but the question form respects the author's intelligence, invites their thinking, and often produces a better answer than the one you had in mind.

A second principle is to lead with what is strong before surfacing weaknesses. Architecture reviews where the reviewer begins immediately with a list of problems create a defensive dynamic that makes it harder to receive the substantive feedback. Spending the first two minutes acknowledging the clear strengths of the design — the well-reasoned HITL mechanism, the clean separation between the data and agent layers — signals that the reviewer has read the document carefully and is engaging in good faith.

For serious structural concerns — the kind that require re-architecture rather than refinement — I ask to take them offline rather than airing them in a group review meeting. A group setting is not the right place to process the emotional reaction to discovering that a core assumption in your design is wrong. The correct process is: flag the concern briefly in the group review, schedule a direct 1:1 meeting to work through it, and then come back to the group with a revised proposal.

The outcome of every architecture review should be written down in the meeting itself: the top 3 action items, who owns each, and by when. Verbal feedback that is not recorded is forgotten within 48 hours and creates the impression that nothing was decided.

### Q3: What are the most common architectural anti-patterns you see in AI systems built by less experienced teams?

**Answer:** The most common is what I call the God Agent pattern: a single, massive LLM prompt that is expected to do all the reasoning in one call. The appeal is simplicity — it feels like one call is better than four. The reality is that a single massive prompt is brittle in ways that are very hard to debug. When the output is wrong, you cannot tell which part of the reasoning failed. When you want to improve one aspect of the analysis, you risk regressing another. And the prompt eventually grows to a length that exceeds the context window, or costs more than four focused calls.

The second anti-pattern is no evaluation mechanism. Teams build a pipeline, do some manual testing to confirm it produces reasonable-looking outputs, and ship. Three months later, they change a prompt to fix one issue and inadvertently break a related output they never tested. ORCA's Layer 1 retrieval eval running as a CI gate on every push is the correct pattern — it creates a safety net that lets you make changes with confidence.

The third anti-pattern is synchronous LLM calls in a web API endpoint. If a user clicks a button that triggers an LLM call, and that call takes 45 seconds, you have a blocking HTTP request that will time out in most browsers and frustrate users. The correct pattern — which ORCA uses — is 202 Accepted immediately, run the pipeline in a background task, provide a polling endpoint. This is a fundamental distributed systems pattern applied to LLM latency.

The fourth anti-pattern is raw SQL scattered throughout the codebase. In ORCA, all database operations go through db/queries.py. This is not just a style preference — it makes it possible to change the underlying schema or switch database backends without hunting through 20 files. Teams that skip this pattern discover it is a problem exactly at the worst time: when they need to add an index, change a schema, or migrate to a different database engine.

### Q4: How do you evaluate whether a proposed AI architecture is production-ready versus MVP-ready?

**Answer:** Production-ready and MVP-ready have different requirements along several dimensions. I evaluate them on five axes: observability, failure handling, scalability, security, and operational burden.

For observability: MVP-ready needs at minimum a log that tells you what happened and why. Production-ready needs structured logging, metrics dashboards, alerting on key thresholds, and distributed tracing across service boundaries. ORCA's current state is MVP-ready in observability — there is logging, but there is no structured metrics dashboard and no automated alerting.

For failure handling: MVP-ready needs a fallback for the most critical failure mode. Production-ready needs fallbacks for all expected failure modes, circuit breakers for external dependencies, and documented runbooks for the failure scenarios that are too rare to test but too expensive to handle ad hoc. ORCA's Agent 1 fallback is good MVP-level failure handling for the CrewAI bug.

For scalability: MVP-ready is "works at current load." Production-ready is "works at 10x current load and has a documented capacity plan for 100x." SQLite, which ORCA uses, is a known scalability constraint — it handles ORCA's current load fine, but a production deployment at a large retailer (50,000+ SKUs) would need a proper database like PostgreSQL.

For security: MVP-ready is "doesn't obviously leak secrets." Production-ready is "has been through a security review, has least-privilege API access, has an audit log for all AI-initiated actions, and has prompt injection mitigations."

The honest assessment of ORCA is that it is MVP-ready — it works reliably at current scale and has the core safety mechanisms (HITL, cost thresholds, Class A rules) in place — but it is not production-ready for a large enterprise deployment without addressing the scalability and observability gaps.

### Q5: How would you conduct an architecture review for ORCA if you were the reviewer?

**Answer:** I would structure the 60-minute review as follows: 15 minutes for the presenter to walk through the design doc (they would have sent it to reviewers 3 days in advance for reading), 35 minutes of questions and discussion, 10 minutes to document action items.

My top five questions going in, based on a reading of the ORCA architecture: First, how does the system behave if the Groq API rate limit is hit mid-pipeline? Does Agent 3 get a partial result, does the whole pipeline fail, or is there retry logic? Second, SQLite is currently used for the orca.db — what is the write throughput limit, and have you tested what happens with concurrent pipeline runs from different threads? Third, the Layer 2 LLM-as-judge is listed as "under development" in the Known Issues. At what stockout rate or auto-approval acceptance rate threshold would you prioritize building Layer 2 over other work? Fourth, the CrewAI + Groq cache_breakpoint error causes Agent 1 to fall back to raw data. How long has this been in production? What is the measured impact on recommendation quality? Fifth, if a human manager approves an escalated order and the inventory data has changed in the 4 hours since the pipeline ran, what is the safety mechanism?

The action items from this review would likely be: document the SQLite concurrency limit and run a load test, add a retry wrapper around Groq API calls with exponential backoff, add a timestamp and data-freshness check to the HITL approval card, and prioritize fixing the CrewAI bug given its impact on Agent 1 quality.

## Key Points to Say in the Interview
- Architecture reviews prevent expensive mistakes before code is written — not a bureaucratic ceremony
- Review failure modes before happy path — most AI architectures have thin failure coverage
- Frame feedback as questions before corrections, especially for serious structural issues
- Always write down the top 3 action items with owners at the end of the meeting
- Use the 5-axis framework: observability, failure handling, scalability, security, operational burden
- The God Agent anti-pattern and synchronous LLM blocking are the two most common AI architecture mistakes

## Common Mistakes to Avoid
- Reviewing the document for typos and style instead of architectural substance
- Giving vague feedback like "this seems fragile" without specifying the exact failure scenario
- Trying to re-architect the entire system in a single 60-minute meeting
- Missing the cost-at-scale analysis — API costs are invisible in architectures until they become a crisis
- Conflating "production-ready" with "MVP-ready" — different standards apply at each stage

## Further Reading
- [Google Site Reliability Engineering Book](https://sre.google/sre-book/table-of-contents/) — the canonical reference for production-readiness criteria, including the production readiness review checklist
- [Martin Fowler: Software Architecture Guide](https://martinfowler.com/architecture/) — core architectural patterns and anti-patterns explained clearly
- [LangGraph Production Deployment Guide](https://langchain-ai.github.io/langgraph/concepts/deployment/) — official guidance on production architecture for LangGraph pipelines
