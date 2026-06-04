# Conflict Resolution in Technical Teams

## What Is It? (Plain English)

Technical conflict is normal and healthy in engineering teams. When two experienced engineers look at the same problem, they often reach different conclusions about the best approach — and both of them may be right in some respects. The problem is not the disagreement; the problem is how the disagreement is handled. Conflicts that are resolved well produce better decisions than either party would have reached alone. Conflicts that are handled poorly damage trust, slow decision-making, and sometimes result in poor decisions that nobody actually wanted.

The most common technical conflicts fall into a few categories: architectural disagreements ("we should use LangGraph" vs. "we should build a custom state machine"), prioritization disagreements ("we should fix the bug first" vs. "we should ship the feature first"), and standards disagreements ("all SQL should live in db/queries.py" vs. "it's fine to write queries inline for simple cases"). Each type has a different resolution approach, but all of them share a common principle: the goal of the resolution is to reach the best decision for the product and team, not to determine who was right.

Google operates with a principle called **Disagree and Commit**. This means that during the decision-making process, you have the right — and the obligation — to raise objections and argue for your position with full energy. But once a decision is made, everyone on the team commits to executing it wholeheartedly, even if they lost the argument. Publicly undermining a decision you disagreed with after it has been made is a serious cultural violation. Private disagreement with a decision, expressed through continued argument or passive non-compliance, is nearly as harmful.

## How It Works (or: How to Think About This)

The conflict escalation ladder — try each rung before going to the next:

```
CONFLICT ESCALATION LADDER

RUNG 4: MANAGER / TIE-BREAKER
  ├─ Use only when: the decision is genuinely blocking work,
  │   both parties have data, consensus is impossible
  └─ Never use as: a shortcut to avoid a difficult conversation

RUNG 3: WRITTEN RFC / DECISION RECORD
  ├─ Use when: verbal discussion is going in circles
  ├─ Each party writes down their position with evidence
  └─ Async review prevents real-time emotional escalation

RUNG 2: STRUCTURED DISCUSSION
  ├─ Set ground rules: both state positions + evidence
  ├─ Separate "what we disagree on" from "what we agree on"
  └─ Focus on criteria for the decision, not the positions

RUNG 1: DIRECT CONVERSATION (try this first, always)
  ├─ 1:1 without observers
  ├─ "Help me understand your reasoning" not "you're wrong"
  └─ Lead with the problem you share, not your solution
```

STAR story framework for conflict questions:

```
STAR FORMAT FOR CONFLICT QUESTIONS

S — SITUATION
  • What was the technical or organizational context?
  • Who were the key people involved?
  • What was at stake?

T — TASK
  • What was your specific role in the conflict?
  • What outcome were you responsible for?

A — ACTION (this is 70% of the answer)
  • What specific steps did you take?
  • How did you approach the other party?
  • What data or evidence did you bring?
  • How did you handle the emotional component?
  • What compromises or synthesis did you propose?

R — RESULT
  • What decision was made?
  • What was the outcome for the product/team?
  • What did you learn?
```

## Why Google Cares About This

Google explicitly lists "collaboration and influence" as a dimension in its engineering promotion criteria. At L5 and above, you are expected to navigate disagreements effectively — not just avoid them. Google interviewers will often ask directly: "Tell me about a time you disagreed with a technical decision. What did you do?" The answer reveals your communication style, your ego investment in your own ideas, your ability to separate yourself from your positions, and your commitment to the team's success over being right. All of these are signals about whether you will function well in Google's highly collaborative, peer-review-heavy engineering culture.

## Interview Questions & Answers

### Q1: Tell me about a time you had a significant technical disagreement. How did you handle it?

**Answer (STAR):**

**Situation:** During the design phase of ORCA, I had a significant disagreement with a collaborating engineer about the architecture for the HITL (Human-in-the-Loop) mechanism. My position was to use LangGraph's built-in interrupt_before mechanism with MemorySaver checkpointing. The other engineer's position was to implement a custom state machine in plain Python, using a database flag to pause and resume the pipeline. The disagreement had real stakes: this was the core safety mechanism of the system, and getting it wrong would mean either orders being auto-approved when they should have been reviewed, or the pipeline hanging indefinitely.

**Task:** As the lead engineer on the pipeline component, I was responsible for making the final architectural call. But I also knew that if I made the call unilaterally without genuinely engaging with the other position, I would have a disengaged collaborator and a brittle architecture that had not been stress-tested by an alternative perspective.

**Action:** My first step was to spend 30 minutes with the other engineer asking questions, not arguing. "What specific concerns do you have about LangGraph's interrupt mechanism?" They surfaced two legitimate issues: they were not confident about what happened to the MemorySaver state if the API server restarted mid-pause, and they were concerned about the debugging experience when something went wrong in the resume path. Both of these were things I had not fully thought through.

I took their concerns and spent a day doing targeted research: I read the LangGraph interrupt documentation in detail, found a GitHub issue where a user had encountered exactly the restart problem they described, and tested the restart behavior in a local experiment. The test confirmed that MemorySaver does not survive server restarts — the checkpointed state is in memory only. This was a genuine issue their position had surfaced.

My synthesis was: use LangGraph's interrupt mechanism (because building the resume logic from scratch was more error-prone than using a battle-tested library) but store the checkpoint in SQLite rather than MemorySaver (because SqliteSaver survives server restarts). This was a position neither of us had started with, and it addressed both the maintainability concern (LangGraph handles the hard parts of interrupt/resume) and the durability concern (SQLite persists across restarts). I wrote this up as a decision document, got the other engineer's explicit sign-off, and we both committed to the approach.

**Result:** The implementation used LangGraph with a SQLite-backed checkpointer. The durability requirement was met, the interrupt/resume logic was reliable, and the other engineer became an active contributor to the pipeline component rather than a skeptic. I also added a test that specifically validated the restart scenario, which I would not have thought to write without the conflict.

### Q2: Describe a situation where you disagreed with a decision made by a more senior engineer. What did you do?

**Answer (STAR):**

**Situation:** At a previous role, a senior staff engineer made a decision to cache all LLM responses for 24 hours as a cost-reduction measure. The business case was clear — API costs had grown significantly and caching 70% of repeated queries would cut costs substantially. I disagreed with the decision because the inventory data that fed into our AI recommendations changed continuously, and a 24-hour cache meant that recommendations would be based on inventory snapshots that were up to a day old. For a fast-moving retail inventory system, 24-hour-old data is often dangerously out of date.

**Task:** I was a senior engineer on the team, not the staff engineer's direct report. My role was technical implementation of the caching layer. The decision had been made, but the implementation had not started yet.

**Action:** I did not raise my concern in the team meeting where the decision was announced — I sensed that the staff engineer had already committed to the decision and a public challenge would be interpreted as undermining. Instead, I scheduled a direct 30-minute meeting with them that afternoon.

In the meeting, I opened by acknowledging what I agreed with: the cost reduction goal was legitimate and the caching approach would work for most of our AI features. Then I raised the specific concern with data: I pulled a sample of our last 200 recommendations and identified that 23% of them involved inventory scenarios where the data had changed by more than 20% within 12 hours. For those scenarios, a 24-hour cache would produce recommendations based on inventory levels that no longer existed.

I proposed a modification: cache with a 4-hour TTL for inventory-dependent queries (where the data change rate was high) and a 24-hour TTL for policy-dependent queries (where the data changed rarely). The staff engineer asked me to quantify the cost impact of my modification versus their original proposal. I did the calculation: my approach delivered 55% of the cost savings (vs. 75% for the full 24-hour cache) while eliminating the stale-data risk for the high-volatility category.

**Result:** The staff engineer accepted the modification with 4-hour TTL for inventory-sensitive queries. They also asked me to document the data-change rate analysis as a design artifact so future caching decisions could reference it. We shipped a solution that achieved most of the cost savings without the data quality risk. I learned that raising concerns directly with the decision-maker, with data, and with a specific counter-proposal, is far more effective than either acquiescing silently or arguing in public.

### Q3: Tell me about a time you had to commit to a decision you personally disagreed with. How did you handle it?

**Answer (STAR):**

**Situation:** The team decided to use a commercial managed RAG service instead of building the retrieval pipeline ourselves, despite my recommendation to build it. My reasoning was that our specific use case — policy document retrieval with domain-specific reranking — was unusual enough that a managed service would not give us the customization we needed. The team's reasoning was that we were already operating at capacity, the managed service would be live in a week rather than three months, and we could always migrate later.

**Task:** The decision was made in a team meeting with full attendance, documented in a decision record, and ratified by the engineering manager. My role was to implement the managed service integration.

**Action:** I had raised my concerns during the decision process with full specificity — I had documented the customization requirements that the managed service did not support and estimated a 6-month migration cost if we needed to switch later. The team heard those concerns and made the decision anyway, weighing delivery speed over long-term flexibility.

After the decision, I committed completely. I implemented the managed service integration as cleanly as possible, specifically designing an abstraction layer that would make a future migration easier. I documented the abstraction interface in the codebase so that anyone implementing the migration later would have a clear path. I did not mention my original disagreement again, did not relitigate the decision in subsequent meetings, and did not passively implement a worse version to prove my point.

**Result:** The managed service was live in 10 days. It worked adequately for 80% of our use cases. 4 months later, the customization limits I had predicted became a real constraint and the team decided to migrate to a self-built retrieval pipeline. The migration took 3 weeks rather than the 6 months I had estimated, largely because the abstraction layer I had built anticipated it. I was not the person who said "I told you so" — I was the person who made the migration fast.

## Key Points to Say in the Interview
- Lead with questions, not positions — "help me understand your reasoning" opens the conversation
- Bring data to disagreements, not just opinions — the other party cannot argue with a benchmark result
- Use the escalation ladder: direct conversation first, written RFC if stuck, manager as last resort
- Disagree and commit is a real principle — commit fully once a decision is made, even if you lost the argument
- The best outcome of a conflict is a synthesis neither party had before, not a victory for either position
- Never raise concerns in public forums as a first move — it puts the other party on the defensive

## Common Mistakes to Avoid
- "I was right and they were wrong" framing — focus on what the team learned and what decision improved
- Raising concerns publicly in a group meeting before having a direct conversation
- Committing nominally but implementing passively (doing a worse version to prove a point)
- Escalating to management as a first move rather than last resort
- Stories where you had no genuine doubt about your position — good conflict stories involve learning something from the other side

## Further Reading
- [Google Engineering Practices: Code Review](https://google.github.io/eng-practices/review/) — Google's actual guidance on navigating technical disagreements in code review
- [Crucial Conversations (Patterson et al.)](https://www.vitalsmarts.com/crucial-conversations/) — the standard playbook for high-stakes interpersonal conversations
- [Ray Dalio: Principles](https://www.principles.com/) — the Idea Meritocracy framework, which formalizes how to surface and resolve disagreements constructively
