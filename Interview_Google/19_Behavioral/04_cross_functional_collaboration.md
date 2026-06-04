# Cross-Functional Collaboration

## What Is It? (Plain English)

Cross-functional collaboration means working effectively with people who have different skills, different incentives, and sometimes different views of what success looks like. A data scientist working on a product feature will interact with product managers (who care about user experience and metrics), software engineers (who care about reliability and performance), business stakeholders (who care about revenue and cost), and sometimes legal and compliance (who care about risk). Each group speaks a slightly different language and has different concerns.

The challenge is not just technical translation — explaining what "precision and recall" means to a product manager. It is also alignment work: getting people with different priorities to agree on what to build, what timeline is acceptable, and what trade-offs are worth making. And it is often unblocking work: identifying when a dependency or a misunderstanding is holding up progress, and removing that obstacle even if it is not technically "your job."

Senior engineers are distinguished by this skill. A strong individual contributor writes great code. A senior engineer writes great code and coordinates the work of others to deliver something bigger than any one person could build alone. At Google, this is sometimes called "glue work" — and the most effective senior engineers are not embarrassed by it; they are proud of it.

## How It Works

```
CROSS-FUNCTIONAL COLLABORATION MAP
══════════════════════════════════════════════════════════════════
                    ┌─────────────────┐
                    │   Your Project  │
                    └────────┬────────┘
          ┌─────────────────┬┴─────────────────┐
          ▼                 ▼                   ▼
  Product Manager    Data Engineering      ML Platform
  ─────────────────  ─────────────────     ─────────────────
  Speaks: metrics,   Speaks: pipelines,    Speaks: infra,
  user stories,      SLAs, schemas,        serving latency,
  roadmap            data quality          compute cost

  They care about:   They care about:      They care about:
  feature adoption   pipeline stability    system reliability
  user impact        backfill correctness  resource efficiency

  How to work with:  How to work with:     How to work with:
  Translate ML       Write clear specs,    Document resource
  trade-offs into    agree on SLAs,        requirements early,
  business impact    handle schema         give lead time
                     changes gracefully

KEY SKILLS THAT DISTINGUISH SENIOR ENGINEERS:
──────────────────────────────────────────────────────────────────
1. Translation: can speak the language of the room you're in
2. Alignment: can get people with conflicting goals to agree
3. Unblocking: can identify and remove the obstacle, whoever "owns" it
4. Documentation: writes things down so everyone has the same understanding
5. Escalation judgment: knows when to resolve at peer level vs. when to escalate
══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google's most impactful projects are inherently cross-functional. Search quality involves ML engineers, linguists, UX researchers, and legal reviewers. Vertex AI involves platform engineers, developer advocates, product managers, and customer success. No single function owns these projects end-to-end. Interviewers assess collaboration because someone who can only work in their lane creates coordination bottlenecks and misses opportunities to improve the whole. Google's performance system explicitly rewards impact that extends beyond your immediate team — and delivering that kind of broad impact almost always requires effective cross-functional collaboration.

## Interview Questions & Answers

### Q1: Tell me about a time you successfully delivered a project that required tight collaboration across multiple teams.

**Answer (STAR):**

**Situation:** I was a senior data scientist leading the deployment of a real-time product recommendation engine for an e-commerce platform. The project required work from four teams: my data science team (model development), data engineering (streaming feature pipeline), software engineering (API integration), and product management (defining success metrics and overseeing A/B testing). All four teams had other priorities. None of the others reported to me. The project had a hard launch date tied to a seasonal sales event.

**Task:** My job was to deliver a working, production-deployed recommendation engine by a fixed date with no formal authority over three of the four required teams. I also needed to keep the project moving while managing the ambiguity inherent in ML projects — nobody knew exactly how good the model would be until we tested it.

**Action:** I started with a cross-functional kickoff where I asked each team to tell me — in their own words — what success looked like for them. Data engineering wanted stable, predictable feature requirements (no late schema changes). Software engineering wanted clear API contracts and a realistic performance SLA. Product management wanted clear criteria for when the model was good enough to launch. I documented all of this in a project brief and circulated it.

I then created a shared progress tracker — a simple table in Confluence that each team updated daily. Critically, it tracked not just "what is done" but "what is blocked." I ran a 20-minute weekly sync across all four teams that focused entirely on blockers, not status.

When data engineering hit a problem — their real-time feature pipeline was producing null values for new users — I was in their Slack channel helping triage rather than waiting for them to report it to me. I knew the business logic better than they did, which helped diagnose the issue (new users needed a fallback to category-level features, which required a model change on my side too).

For product management, I provided a weekly "model performance preview" — translation of technical metrics (NDCG@10, precision@5) into the language they understood: "The model would have recommended at least one item the user bought in 38% of sessions — that compares to 22% for the current rule-based system."

**Result:** The recommendation engine launched on time. The A/B test showed a 7% lift in click-through rate and a 4.2% lift in conversion for sessions with recommendations. More importantly, all four teams felt ownership of the outcome — not just "data science's project" — which made the subsequent iteration cycle much faster because everyone was invested in improving it.

---

### Q2: Describe a time when you had to translate a complex technical concept for a non-technical business stakeholder to get a decision made.

**Answer (STAR):**

**Situation:** I was working on an inventory forecasting system where I needed the head of supply chain (non-technical, 25 years of operations experience) to approve a change in forecast horizon from 4 weeks to 12 weeks. The change required significant engineering work and a change to how his team would use the output. He was comfortable with the 4-week forecast and skeptical of whether a 12-week forecast could be reliable enough to act on.

**Task:** I needed to explain why a longer forecast horizon was valuable, address his concerns about accuracy at 12 weeks, and get his decision before the next planning cycle began — without losing him in technical details about time-series models, confidence intervals, and error accumulation.

**Action:** I did not use the words "MAPE," "confidence interval," or "model accuracy." Instead, I asked him what the most expensive supply chain mistakes he had seen were. He described two: a major stockout during peak season because suppliers were not given enough lead time to manufacture (4 weeks was not enough), and an expensive emergency air freight shipment that could have been sea freight if they had known 8 weeks in advance.

I reframed the entire conversation around those two stories. "A 12-week forecast is not a prediction of what will happen — it's an early warning system. If the forecast says high demand at week 10, we alert the supplier at week 1. If the forecast turns out wrong at week 10, we cancel or reduce. The value is in having time to act cheaply, not in being right."

I prepared one slide: a historical backtest showing that had the 12-week model been running for the past 2 years, we would have caught the peak-season stockout 11 weeks early (enough time for sea freight from the main supplier). I showed the cost of the actual emergency air freight: $218,000. I showed the estimated cost if we had had the 12-week warning: $34,000 sea freight.

**Result:** He approved the engineering work in that meeting. He specifically asked that I brief his logistics director using "those two stories." The 12-week forecast system became one of the supply chain team's highest-valued data assets. The lesson I took: the best technical translation is not simplification — it is reframing in terms of decisions the business already cares about.

---

### Q3: Tell me about a time when cross-functional misalignment caused a problem, and how you resolved it.

**Answer (STAR):**

**Situation:** Three months into building ORCA's pipeline, I discovered a fundamental misalignment between what I had built and what would be deployable in production. I had designed the system assuming the Groq API would be the LLM backend and had built significant optimisation around Groq's specific rate limits and response format. Meanwhile, the infrastructure context I had been working from assumed future deployment on Google Cloud, which would use Vertex AI's Gemini models. Nobody had explicitly said "use Groq and stay on Groq" — I had made a practical choice for development (free tier) that had inadvertently become an architectural assumption.

This is a self-collaboration story (as a solo developer), but it maps directly to cross-functional misalignment: I had two "teams" — the development-speed goal and the production-deployment goal — that had made different assumptions without explicitly aligning.

**Task:** Resolve the architectural misalignment before it became even more deeply embedded in the codebase. Without breaking the functioning system I had built.

**Action:** I did an explicit "assumption audit" — wrote down every place in the codebase where I had made a choice that would need to change if the LLM provider changed. I found 23 such locations spread across `agents/graph.py`, `agents/prompts.py`, `agents/llm_factory.py`, and the RAG retriever.

I then implemented an abstraction — the `llm_factory.py` module — that centralises all LLM instantiation behind a single function driven by environment variables (`LLM_PROVIDER`, `GROQ_MODEL`). Every other file calls `get_llm()` instead of directly instantiating `ChatGroq`. This meant that switching providers in the future requires changing one file and the environment variables, not 23 files.

I also wrote a CLAUDE.md entry documenting the assumption explicitly: "Stack: Python 3.11, FastAPI, Streamlit, LangGraph, CrewAI, ChromaDB, SQLite, Groq (free tier LLM), Docker" — making the current state of deployment assumptions explicit and findable.

**Result:** The system remained on Groq for current deployment (appropriate for the free-tier Render deployment), but the architecture now cleanly supports swapping to Vertex AI or any LangChain-compatible LLM without code changes. The alignment was restored by making the hidden assumption explicit and building an abstraction layer around it. The cross-functional lesson: misalignments usually stem from unstated assumptions — the fix is to state them explicitly, not to argue about whose assumption was right.

## Key Points to Say in the Interview

- "I start cross-functional conversations by asking what success looks like for them — not just presenting my ask."
- "Technical translation means speaking in terms of decisions and business impact, not explaining how the model works."
- "I maintain visible shared artefacts — a project tracker, a weekly status note — so everyone has the same understanding of status and blockers."
- "I remove blockers regardless of whose lane they're in — coordination is everyone's job, not just the PM's."
- "Misalignments usually come from unstated assumptions — the fix is to make them explicit and documented, not to assign blame."
- "Senior engineers are measured by their team's output, not just their individual output — collaboration is how you scale your impact."
- "I write things down: meeting decisions, technical trade-offs, scope agreements — so there is a record everyone can refer back to."

## Common Mistakes to Avoid

- Assuming other functions understand ML vocabulary — precision, recall, F1, AUC mean nothing to most business stakeholders.
- Waiting for a formal sync to surface a blocker — identify blockers in Slack/chat as soon as they appear.
- Taking on all coordination yourself rather than empowering each function to coordinate within their own work.
- Not documenting decisions made in verbal discussions — they will be remembered differently by different people.
- Conflating "getting alignment" with "everyone agrees with me" — alignment means shared understanding, not unanimous approval of your view.

## Further Reading

- [The Mythical Man-Month (Brooks)](https://www.oreilly.com/library/view/mythical-man-month-the/0201835959/) — the classic on why adding people to complex projects makes them harder, not easier; essential for understanding why coordination matters
- [Accelerate (Forsgren, Humble, Kim)](https://www.oreilly.com/library/view/accelerate/9781457191435/) — research-backed analysis of what distinguishes high-performing engineering teams; cross-team collaboration is a recurring theme
- [Staff Engineer (Larson)](https://staffeng.com/book) — practical guide to senior technical leadership at companies like Google; cross-functional collaboration is central to every archetype described
