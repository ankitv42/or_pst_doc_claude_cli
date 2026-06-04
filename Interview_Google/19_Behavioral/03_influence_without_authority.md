# Influence Without Authority

## What Is It? (Plain English)

Influence without authority means getting people to change their behaviour, adopt your ideas, or prioritise your project when you have no formal power over them. You cannot order them to do it. You have to convince them. This is one of the most important skills at senior levels in any large organisation, including Google, because almost every meaningful initiative requires cooperation from people in other teams, other functions, or other reporting chains.

The good news is that influence without authority is a learnable skill with identifiable patterns. Data is more persuasive than opinion. Understanding what the other person cares about — and framing your ask in terms of their goals, not yours — is more persuasive than logical arguments from your own perspective. Finding champions (people with authority who believe in your idea) and building coalitions (groups whose collective weight is hard to ignore) are leverage multipliers. And knowing when to "disagree and commit" — to stop arguing and execute once a decision is made — is what distinguishes senior engineers from people who complain but do not deliver.

At Google specifically, the culture values "influence through expertise, not title." Engineers are expected to write design documents, conduct data analysis, and present evidence-based arguments to change decisions — not rely on org chart authority to get things done.

## How It Works

```
INFLUENCE WITHOUT AUTHORITY PLAYBOOK
══════════════════════════════════════════════════════════════
1. UNDERSTAND THEIR GOALS     What does the other team/person care about?
          │                   Frame your ask as helping THEM achieve THEIR goals.
          ▼
2. BUILD THE CASE WITH DATA   Opinions lose to data. Measure the impact.
          │                   "This will reduce API latency by 40%" beats
          │                   "I think this is a better approach."
          ▼
3. FIND CHAMPIONS             Identify who has authority and already agrees.
          │                   Ask them to sponsor your idea.
          ▼
4. BUILD COALITION            Small wins → credibility → more stakeholders on board.
          │                   Document who is aligned and who is not.
          ▼
5. ADDRESS OBJECTIONS         Engage the skeptics. Their concerns are often valid
          │                   and addressing them improves the idea.
          ▼
6. DISAGREE AND COMMIT        If overruled: say you disagree, document your view,
                              then execute fully on the decision made.
══════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google's engineering culture is famously flat and matrix-structured. PMs, data scientists, ML engineers, SREs, and UX researchers all need to align on major features. Nobody in this chain formally reports to another. Decisions are made through persuasion, data, and documented design reviews. Google's Googleyness criteria explicitly include "gets things done" and "works well with cross-functional teams" — both require influence. Interviewers ask about influence situations to assess whether you are someone who grows impact by bringing others along, or someone who works in their own corner and complains when others don't cooperate.

## Interview Questions & Answers

### Q1: Tell me about a time you influenced a cross-team decision without having formal authority over the outcome.

**Answer (STAR):**

**Situation:** I was a data scientist on a demand forecasting team at a retail company. The ML platform team had decided to standardise all model serving infrastructure on a synchronous REST API pattern with a 5-second timeout. My forecasting models sometimes took 8-12 seconds for complex multi-horizon predictions during peak hours. The platform team's decision would force me to either simplify the models (losing accuracy) or route around the platform infrastructure (creating technical debt and security issues).

The platform team had 20 engineers, had been working on this for 6 months, and the initiative was sponsored by the VP of Engineering. I had no authority to change their decision.

**Task:** I needed to get an exception — or better, a genuine change to the platform's design — to support async patterns alongside synchronous ones, without creating an adversarial relationship with a team I would need to work with for years.

**Action:** Instead of going to my manager and asking them to escalate (which would create political tension), I started by understanding the platform team's constraints. I scheduled a 30-minute working session with their tech lead to understand why the 5-second timeout existed. It turned out it was about resource exhaustion protection — they had seen long-running requests cause cascading failures.

I then spent a week doing two things. First, I benchmarked my model's actual latency distribution — the P99 was 11 seconds, but only for multi-horizon predictions during peak. For 80% of requests, latency was under 3 seconds. Second, I researched async patterns in other companies' ML platforms and found examples (Uber, Lyft) where synchronous and async serving coexisted safely.

I wrote a two-page technical memo with the data and three proposed options: (1) accept the restriction and simplify models, (2) an async serving pattern with a callback mechanism, (3) a hybrid — synchronous for simple forecasts, async for complex ones. I shared it with the platform tech lead before the next architecture review, framed as "I have a constraint that doesn't fit the current design — can we figure this out together?"

In the architecture review, the tech lead presented the hybrid option as their own expanded thinking. The async pattern was added to the platform roadmap.

**Result:** The platform added async serving support, my models ran with full accuracy, and I had built a strong working relationship with the platform team's tech lead that continued to pay dividends on later projects. The key was framing the problem as a shared design challenge, not a conflict — and coming with data, not just a complaint.

---

### Q2: Describe a situation where you used data to persuade stakeholders who were skeptical of an AI/ML recommendation.

**Answer (STAR):**

**Situation:** I was working on an automated anomaly detection system for inventory shrinkage (theft and loss) at a distribution centre. My model was flagging 140 locations per week for manual audit. The operations manager had a team of 12 auditors who were currently reviewing 30 locations per week (based on intuition and prior theft history). He was skeptical of expanding to AI-flagged locations — his comment was "the algorithm doesn't understand how the warehouse works."

**Task:** I needed to demonstrate, in terms the operations manager found credible, that the model's flagged locations had a higher yield (actual theft discovered per audit) than the manually selected ones — without dressing it up in ML terminology.

**Action:** I asked for a three-week pilot with a blind comparison structure. I split available audit capacity: half the audits on model-flagged locations, half on the traditional manually selected ones. I did not ask to replace the manual process — I asked to run them side by side.

Three weeks later, I built a one-page report with two numbers: yield rate (% of audited locations where shrinkage was discovered) for model-flagged locations vs. manually selected. Model-flagged locations had 67% yield. Manual locations had 22% yield. Total shrinkage value recovered from model-flagged locations in 3 weeks: $43,000.

I presented this to the operations manager with one slide and three numbers. I also specifically addressed his concerns about the model "not understanding the warehouse" by showing that the top 5 model-flagged features correlated with operational patterns he already knew about (late-shift handover locations, high-SKU-velocity zones, staff rotation weeks).

**Result:** The operations manager championed the expansion of the AI system to 80% of audit capacity, personally presenting the ROI numbers to his director. The system was scaled to 3 additional distribution centres over the next two quarters. The key was running a structured comparison that spoke in his metric (yield rate, dollars recovered), not mine (precision, recall, AUC).

---

### Q3: Tell me about a time you disagreed with a technical decision but ultimately committed to it. What did you do and what was the outcome?

**Answer (STAR):**

**Situation:** I was part of a team building a document processing pipeline for an insurance company. The architecture team had decided to build the system as a monolithic FastAPI service with all ML models loaded in-process. My view was that this created operational risk — a memory leak in the large language model component would bring down the entire API, and deploying model updates would require a full service restart with downtime.

I advocated strongly in the architecture review for a microservices approach with separate model serving containers. The architecture team disagreed — they cited the complexity overhead of service-to-service communication, the team's unfamiliarity with container orchestration at the time, and the shorter delivery timeline. The technical director made the call to proceed with the monolith.

**Task:** My concern was on record. The decision was made. My task now was to (a) support the delivery of the chosen architecture as effectively as possible, (b) mitigate the risks I had flagged within the monolithic design, and (c) remain prepared to revisit if the risks I predicted materialised.

**Action:** I documented my concerns in the architecture review notes: "I disagree with this decision for the following reasons: [specific risks]. I understand the counter-arguments and will fully commit to this approach." This was not passive-aggressive — it was professional record-keeping.

Then I channelled my energy into making the monolith as robust as possible. I implemented graceful model reloading (SIGHUP handler to reload models without restarting the service), memory circuit breakers (auto-restart the model worker if RSS exceeded a threshold), health check endpoints that differentiated between "API degraded but running" and "API down." I also wrote a one-page "migration guide" in the README documenting how to extract the models to separate services when the team was ready.

**Result:** The system launched on time. Six months later, a memory issue with an updated model caused the exact problem I had predicted — but the memory circuit breaker caught it and restarted only the model worker, not the full API. Three months after that, when the team had built more operational experience, they extracted the model serving to a separate FastAPI service using the migration guide I had written. My engineering groundwork made the eventual migration much smoother than it would have been if I had simply sulked after losing the argument.

## Key Points to Say in the Interview

- "I start by understanding what the other person cares about, then frame my ask in terms of their goals."
- "Data is my primary persuasion tool — I will run a controlled experiment before asking for a significant change."
- "I write things down: memos, decision records, documented disagreements. Writing creates shared understanding."
- "I find champions — people who have the authority I lack but share the goal. I help them see the opportunity."
- "Disagree and commit is real: I state my objection clearly, document it, and then execute fully on the decision made."
- "Building influence is a long game — one collaboration that goes well makes the next one easier."
- "I never escalate to the manager layer without first trying to resolve it at the peer level."

## Common Mistakes to Avoid

- Framing your request as "you should change your plans to accommodate mine" rather than "here's how this serves our shared goals."
- Going to your manager to escalate as a first resort — it creates adversarial dynamics that outlast the immediate issue.
- Relying on opinion or seniority rather than data — in an engineering culture, data wins.
- Being a sore loser after a disagreement — undermining a decision after it is made destroys your credibility.
- Failing to document the decision and your reasoning — in a year, nobody will remember why a choice was made.

## Further Reading

- [Influence Without Authority (Cohen & Bradford)](https://www.wiley.com/en-us/Influence+Without+Authority%2C+3rd+Edition-p-9781119816812) — the foundational book on the topic; practical frameworks for non-positional influence
- [Radical Candor (Kim Scott)](https://www.radicalcandor.com/) — Google/Apple veteran on giving honest feedback and building trust across teams
- [How to Win Friends and Influence People (Carnegie)](https://www.simonandschuster.com/books/How-to-Win-Friends-and-Influence-People/Dale-Carnegie/9780671027032) — dated but the core insight about understanding others' interests before stating your own remains accurate
