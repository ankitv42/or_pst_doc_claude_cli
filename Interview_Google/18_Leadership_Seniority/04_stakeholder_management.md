# Stakeholder Management for AI Projects

## What Is It? (Plain English)

Stakeholder management is the practice of keeping the people who care about your project informed, aligned, and appropriately involved — even when the news is not what they want to hear. For AI projects specifically, this is harder than for traditional software because AI has a unique combination of high expectations (from stakeholders who have read the hype), unpredictable timelines (LLM quality is hard to estimate in advance), and outputs that are hard to evaluate (was that recommendation good?). Managing stakeholders well means all of these gaps get communicated proactively, rather than discovered painfully at a critical moment.

Non-technical stakeholders — product managers, business owners, executives — relate to AI projects through the problems they need solved, not through the technology. When a VP asks "when will the AI be ready," they are usually asking "when will the inventory stockout problem be under control?" Answering the first question requires a technical estimate. Answering the real question requires understanding the business timeline, the decision dependencies, and the risk tolerance of the stakeholder.

The most dangerous pattern in AI stakeholder management is over-promising early. AI projects have a characteristic S-curve of progress: very fast at first (you can demo a prototype that looks impressive in week 2), then frustratingly slow in the middle (polishing from "looks impressive in a demo" to "works reliably in production" takes 80% of the total effort), then productive again at the end. Stakeholders who only see the demo and then wait 6 months for production often feel betrayed even when the engineering team did everything right. Managing this expectation — explaining the S-curve explicitly, setting checkpoints that show progress during the messy middle phase — is a core senior engineering responsibility.

## How It Works (or: How to Think About This)

The stakeholder communication framework for AI projects:

```
STAKEHOLDER COMMUNICATION MATRIX

                    HIGH INTEREST        LOW INTEREST
                   ┌─────────────────┬──────────────────┐
HIGH INFLUENCE     │  MANAGE CLOSELY │  KEEP SATISFIED  │
                   │                 │                  │
                   │ VP Ops / CPO    │ Finance (budget) │
                   │ Weekly update   │ Monthly summary  │
                   │ + direct        │                  │
                   │ involvement in  │                  │
                   │ scope decisions │                  │
                   ├─────────────────┼──────────────────┤
LOW INFLUENCE      │  KEEP INFORMED  │  MONITOR         │
                   │                 │                  │
                   │ Inventory       │ IT Security      │
                   │ analysts (users)│ (audit periodic) │
                   │ Demo + feedback │                  │
                   │ cycles          │                  │
                   └─────────────────┴──────────────────┘
```

Translating technical language to business language:

```
TECHNICAL TERM               BUSINESS EQUIVALENT
──────────────────────────────────────────────────────────
LLM hallucination            AI made an error that wasn't 
                             caught before it showed up in 
                             a recommendation

Model latency p99: 8s        In 1% of cases, the AI takes 
                             more than 8 seconds to respond — 
                             fast enough for batch, too slow 
                             for real-time checkout

RAG retrieval quality        How reliably the AI finds the 
                             right policy when making a 
                             recommendation

HITL escalation rate         % of orders that require a 
                             human decision (our "automation 
                             rate" metric)

Pipeline failure rate        How often does the AI system 
                             fail completely and require 
                             manual fallback

Agent 3 capital score        The AI's confidence score on 
                             its recommendation (0-100)
```

Managing uncertainty in timeline communication:

```
WRONG: "We'll be done in 6 weeks."

RIGHT: "Here's how I think about the timeline:
  ├─ 2 weeks to finish core pipeline (high confidence)
  ├─ 2-4 weeks to reach 70% auto-approval rate (medium confidence — 
  │   depends on model quality after seeing real inventory data)
  └─ 2-6 weeks to reach production reliability (low confidence — 
      this is where surprises usually happen in AI projects)
  
  My best estimate is 8 weeks. I'll have a clearer view after the 
  first 2 weeks of pipeline testing. I'll flag if the timeline is 
  slipping by week 3."
```

## Why Google Cares About This

Google is a matrix organization where engineers regularly work with multiple product managers, program managers, business stakeholders, and cross-functional partners. At senior levels, the expectation is that you can navigate this complexity independently — you do not need your manager to relay technical information to stakeholders or to translate business needs back to the team. The ability to communicate uncertainty clearly, push back on unrealistic timelines with specific reasoning, and proactively surface blockers is a key distinguisher between senior and staff-level engineers. Interviewers will often explicitly ask for examples of stakeholder communication challenges, because they know it is a skill that many technically strong engineers have not developed.

## Interview Questions & Answers

### Q1: How do you communicate technical constraints to a non-technical stakeholder without sounding like you are making excuses?

**Answer:** The key is to lead with business impact rather than technical mechanism. "We cannot use a cheaper model because of the inference latency constraints of the BAAI reranker" sounds like an excuse because the stakeholder has no context for what an inference latency constraint is. "If we reduce the model quality here, our auto-approval rate will likely drop from 70% to 50%, which means the inventory team will need to manually review an additional 100 orders per day" connects the technical constraint directly to the business cost.

I use the following pattern: state the constraint as a business tradeoff, not as a technical limitation. Constraints that are framed as tradeoffs keep the stakeholder in the conversation — they now have the information to weigh the tradeoff and make a decision, rather than feeling like they are being told what is not possible. "We can do X or Y, but not both with the current budget" is empowering. "We can't do X because of Z" is not.

When the constraint is genuinely fixed — there is no tradeoff available — I explain the consequence of ignoring it rather than arguing for the constraint itself. "The reason SQLite is a ceiling on concurrent users is that it uses file-level locking for writes, and with 10 concurrent pipelines, we will see write contention errors. I can show you the benchmark output that demonstrates this at 5x current load." The benchmark is hard to argue with, and it is much more persuasive than "trust me, SQLite won't scale."

### Q2: How do you manage expectations when an AI project is running behind schedule?

**Answer:** The first and most important rule is to communicate the slip proactively — do not wait until the stakeholder asks. Stakeholders who discover that a project is behind when they expected it to be finished are much more frustrated than stakeholders who receive a heads-up three weeks early. The latter situation gives them time to adjust their plans; the former situation makes them feel deceived.

When communicating a schedule slip, I always provide three things: the revised timeline, the specific cause of the slip, and what I am doing to prevent further slippage. "The pipeline is running 2 weeks behind because the Groq rate limits are lower than documented and we are hitting them in load testing. The revised estimate is launch on [date]. I have already raised a ticket with Groq support and have identified a batching strategy that will stay within limits — I will have a confirmed fix by [date]." This is very different from "we are behind, we need more time."

For AI projects specifically, I try to set milestone expectations at the project start using the "demo vs. production" framing: I tell stakeholders explicitly that there are two milestones, the demo milestone (AI produces reasonable-looking outputs in a controlled setting, typically achievable in weeks) and the production milestone (AI works reliably on real data at scale, typically takes much longer). I ask which milestone they need and by when, and I set expectations accordingly. This prevents the "but you showed me a working demo in week 2, what took so long?" conversation.

### Q3: A stakeholder is demanding a feature that you believe is technically wrong or will harm the product quality. How do you handle it?

**Answer:** My approach starts by assuming that the stakeholder is rational and is asking for the feature because they have a legitimate business need — they just may not know whether their proposed solution is the right way to meet it. The goal of the conversation is to understand the underlying need, not to win the argument about the specific feature.

I open with questions: "Help me understand the business problem you are trying to solve with this feature. What would success look like?" Very often, the stated feature is one possible solution to the underlying problem, and there is an alternative that achieves the same business outcome without the technical harm. For example: a stakeholder might demand that the AI always show a recommendation even when it is uncertain, because they do not want the UI to show "no recommendation available." The underlying need is that the UI should not confuse users. The right solution might be a fallback recommendation with a clear uncertainty flag, not forcing the AI to fabricate confidence it does not have.

If the underlying need is legitimate and the specific solution is genuinely harmful, I say so directly with data. "If we remove the cost ceiling check and auto-approve all orders, I expect our error rate — orders placed at the wrong quantity or wrong cost — to increase by approximately 15% based on what I see in the Agent 3 score distribution. I want to make sure you have that number before we decide." Then I offer an alternative. "What if we raise the cost ceiling from $50,000 to $75,000, which would auto-approve 85% of current escalations while keeping the safety check for the largest orders?"

### Q4: How do you explain model uncertainty to a business stakeholder who expects deterministic outputs?

**Answer:** The framing I use is the weather forecast analogy. A weather forecast does not say "it will rain at 2:47pm" — it says "70% chance of rain in the afternoon." We consider this useful information and act on it (bring an umbrella) without expecting the forecast to be deterministic. An AI recommendation is the same: it is probabilistic information that helps you make better decisions, not a certainty that replaces your judgment.

For inventory decisions specifically, I explain uncertainty through the consequence lens. "When the AI says 'order 500 units' with a 90% confidence score, it means: in 9 out of 10 similar situations historically, the right answer was in the 450-550 unit range. When it says 'order 400-600 units' with a 60% confidence score, it means the demand signal is mixed — maybe there was a recent promotion that clouded the trend. In both cases, the AI is giving you its honest assessment; the difference is in how much additional scrutiny you should apply."

The key stakeholder concern is usually: "Can I be held accountable for a decision made by the AI?" The answer needs to acknowledge this concern directly. "The AI provides a recommendation with supporting evidence. You review the recommendation and decide to approve or modify it. The AI's recommendation is an input to your decision, not a replacement for it. You retain professional accountability for all approved orders." This framing — AI as a high-quality analyst who researches and recommends, human as the decision-maker — is one that most non-technical stakeholders find comfortable.

### Q5: How do you push back on an unrealistic timeline from leadership without damaging the relationship?

**Answer:** The starting point is to replace the emotional reaction ("that's impossible") with a factual analysis ("here is what that timeline requires"). When a leader sets an unrealistic timeline, they usually have real reasons for that timeline — a board commitment, a competitive launch, a contract deadline. Dismissing the timeline as impossible does not help them solve their underlying problem.

My approach is the "yes, and" framing: "Yes, I want to help you hit [date], and here is the tradeoff analysis that will determine whether we can." I then work through specifically what it would take to hit the date — scope reductions, team additions, quality reductions — and quantify the cost of each option. "We can hit [date] with a 60% auto-approval rate by cutting the RAG component and hardcoding the policy constraints. We can hit [date + 3 weeks] with an 80% auto-approval rate with the full RAG pipeline. Which do you prefer?"

The key to preserving the relationship is to make it clear that you are genuinely trying to find a way to meet the business need, not protecting your own schedule. Coming with options, not just a "no," is the difference between being seen as a blocker and being seen as a partner. If leadership explicitly accepts a scope reduction or quality reduction to hit the date, that acceptance must be documented in writing — not to create blame, but to ensure shared understanding of what was traded away and why, so there is no surprise when the reduced-scope version ships.

## Key Points to Say in the Interview
- Lead with business impact, not technical mechanism — translate constraints into consequence language
- Communicate schedule slips proactively, with cause and mitigation plan — never wait to be asked
- Use the "demo vs. production" framing upfront to prevent the "why did it take so long?" conversation
- Separate underlying business need from proposed solution — often a better alternative exists
- Model uncertainty = weather forecast framing; business accountability stays with the human approver
- Push back with options and tradeoffs, not "no" — you are solving the business problem, not protecting your schedule

## Common Mistakes to Avoid
- Using technical jargon when translating constraints instead of business consequence language
- Waiting for stakeholders to discover a problem rather than surfacing it proactively
- Treating stakeholder requests as demands to comply with rather than business needs to understand
- Agreeing to an unrealistic timeline under pressure and then delivering late with no prior warning
- Not documenting scope or quality reductions that were traded away to hit a deadline

## Further Reading
- [Lara Hogan: Resilient Management](https://larahogan.me/resilient-management/) — practical frameworks for communication with non-technical stakeholders
- [Google's Technical Writing Courses](https://developers.google.com/tech-writing) — free Google course on communicating technical content clearly
- [Influence Without Authority (Cohen & Bradford)](https://www.influencewithoutauthority.com/) — foundational text on stakeholder alignment and persuasion
