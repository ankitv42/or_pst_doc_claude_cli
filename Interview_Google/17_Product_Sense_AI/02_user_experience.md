# User Experience for AI Products

## What Is It? (Plain English)

Designing an AI product is fundamentally different from designing a traditional software product because AI is probabilistic — it can be wrong, and users know it. The UX challenge is not just making the interface look clean; it is building an experience that helps users understand what the AI is confident about, what it is unsure about, and why it made a particular decision. When users cannot understand the AI, two bad things happen: they either over-trust it (approving bad recommendations without reading them) or under-trust it (ignoring good recommendations and doing everything manually).

**Trust calibration** is the practice of designing the AI's presentation so that users feel exactly as confident as the AI actually is — not more, not less. An AI that says "I recommend ordering 500 units" sounds authoritative, even if its confidence is only 60%. An AI that says "I recommend ordering 500 units (confidence: medium — demand signal is mixed)" gives the user what they need to apply appropriate skepticism. Getting this right requires deep attention to language, visual design, and information hierarchy.

**Explainability** is the related practice of giving users a traceable path from the AI's conclusion back to its inputs. This is especially critical in enterprise AI where decisions have financial or legal consequences. A human manager approving a $50,000 inventory order needs to know: what data did the AI look at? What policy did it apply? Why did it choose this quantity over a smaller or larger one? Without that trace, the manager cannot take professional responsibility for the decision, and they will rightly refuse to use the system.

## How It Works (or: How to Think About This)

Use this framework for designing trust-aware AI UX:

```
PROGRESSIVE DISCLOSURE LADDER
(Show more detail as user goes deeper)

┌─────────────────────────────────────────────────┐
│  LEVEL 1: Decision Summary (always visible)      │
│  "Recommend: Order 500 units of SKU-4821"        │
│  Confidence: HIGH  │  Action required: None      │
└─────────────────────┬───────────────────────────┘
                      │ user clicks "Why?"
┌─────────────────────▼───────────────────────────┐
│  LEVEL 2: Key Reasoning (one click)              │
│  • Demand forecast: +18% WoW                    │
│  • Current stock covers 4 days (critical)        │
│  • Supplier lead time: 3 days                    │
│  • Budget utilisation: 42% of monthly cap        │
└─────────────────────┬───────────────────────────┘
                      │ user clicks "Show full analysis"
┌─────────────────────▼───────────────────────────┐
│  LEVEL 3: Full AI Trace (two clicks)             │
│  • Agent 1 demand analysis: [raw text]           │
│  • Agent 2 options considered: [table]           │
│  • Agent 3 scoring breakdown: [formula output]   │
│  • Policy docs retrieved: [RAG sources]          │
└─────────────────────────────────────────────────┘
```

For HITL (Human-in-the-Loop) workflows like ORCA's interrupt/resume pattern, the UX must answer three questions on the approval screen:
1. What is the AI recommending?
2. Why is this decision flagged for human review (rather than auto-approved)?
3. What information does the human need to make the override decision confidently?

```
HITL APPROVAL CARD (example wireframe, text representation)

┌───────────────────────────────────────────────────┐
│  ⚠  ESCALATED FOR APPROVAL                         │
│  SKU-4821 — Reorder 500 units — $52,400            │
│                                                     │
│  WHY ESCALATED: Order exceeds $50,000 auto-approve  │
│  threshold. Agent 3 score: 87/100 (High confidence) │
│                                                     │
│  RECOMMENDATION: Standard reorder (Option A)        │
│  vs. Partial fill (Option B): $31,440               │
│  vs. Expedite (Option C): $58,200 (+11%)            │
│                                                     │
│  [View Full Analysis]  [APPROVE]  [REJECT]          │
└───────────────────────────────────────────────────┘
```

## Why Google Cares About This

Google has a long history of thinking about AI UX — from the way Google Maps shows route confidence to the way Google Translate shows alternative translations. At senior levels, Google expects engineers and PMs to think beyond feature correctness to user behavior. A technically correct AI that users do not trust or misuse is a product failure. Interviewers will probe for your understanding of error recovery, edge cases, and the psychological contract between AI and user — because getting this wrong at Google's scale affects hundreds of millions of people.

## Interview Questions & Answers

### Q1: What is trust calibration in AI products and why does it matter?

**Answer:** Trust calibration refers to the alignment between how confident the AI presents itself and how confident it actually is. An AI system can be miscalibrated in two directions: overconfident (it presents high certainty when it is actually unsure, leading users to rubber-stamp bad decisions) or underconfident (it hedges everything, making users feel like the AI is useless and prompting them to ignore it entirely).

The reason it matters is that miscalibration changes user behavior in ways that undermine the product's purpose. If an AI inventory system recommends order quantities in authoritative, precise language every time — even when its underlying demand signal is weak — managers will eventually approve an order they should not have. The first time that happens at scale, trust in the system collapses, and you find yourself in a situation where people are using the AI output as a starting point but manually redoing all the calculations anyway. At that point, the AI has added cost without adding value.

The practical implementation of trust calibration is mostly about language and visual design. For high-confidence outputs, use direct, assertive language: "Recommend ordering 500 units." For medium-confidence outputs, flag the uncertainty explicitly: "Model suggests 400-600 units — demand signal is mixed due to recent promotion." For low-confidence outputs, do not present a recommendation at all; instead, present the data and let the human decide.

One important subtlety: confidence in AI outputs is often domain-specific within the same product. An inventory AI might be highly reliable for predicting reorder quantities for steady-state SKUs (commodities with stable demand) but unreliable for new product launches or promotions. The UX should reflect this, even if it means showing different UI treatments for different product categories. Generic "I'm not sure" disclaimers that appear on everything train users to ignore them.

### Q2: How do you design the explainability layer for an HITL approval workflow?

**Answer:** The explainability layer needs to be designed around the decision the human is making, not around the AI's internal architecture. When a manager sits down to approve a $50,000 inventory order, they need to answer one question: "Do I believe this order is the right one to place?" The explainability UI should be structured to help them answer that question, not to give them a technical audit log of which LLM was called when.

For ORCA's HITL approval screen, this means the primary information should be: what SKU, how many units, at what cost, and why is this quantity the right one (not too much, not too little). The secondary layer — visible on request — is the AI's reasoning: what demand trend it detected, what policy it retrieved, how it scored the three options. The tertiary layer — for auditors and engineers, not daily users — is the full pipeline trace, including the raw LLM outputs, the RAG chunks retrieved, and the Agent 3 formula inputs.

The key design principle is **progressive disclosure**: lead with conclusions, offer reasoning on request, and make the full technical trace accessible but not the default view. If you make users read 10 paragraphs of AI reasoning before they can click Approve, they will stop reading after the first day and just click Approve reflexively — the worst possible outcome. The goal is a UI where a careful reviewer can verify the AI's reasoning in under 2 minutes.

One concrete implementation trick: render the Agent 3 scoring formula output as a table rather than as prose. When the approval card shows "Budget score: 34/40, Availability score: 28/30, Margin score: 18/20, Lead-time penalty: -3," a manager can quickly compare the current recommendation against alternative options without having to parse narrative text.

### Q3: How do you handle AI errors gracefully in the UX without destroying user trust?

**Answer:** The first principle of graceful error handling in AI products is to never surprise the user. An unexpected failure — one that produces no output, or produces obviously wrong output without any warning — destroys trust rapidly and permanently. The user's mental model shifts from "this AI is sometimes right and sometimes wrong, and I can tell which" to "this AI is unpredictable and I cannot rely on it."

The design pattern that works is what I call "degrade with dignity." When an AI sub-component fails, the system should fall back to a simpler but reliable output and tell the user clearly that it did so. In ORCA, this is exactly what happens with the Agent 1 CrewAI sub-crew bug: when the CrewAI call fails, Agent 1 falls back to a raw-data demand summary and continues the pipeline. The graceful UX treatment for this is a small badge on the dashboard card: "Demand analysis used simplified mode — CrewAI sub-analysis unavailable." This tells the manager: you have a recommendation, it is based on real data, but the AI had a partial failure and you may want to apply more scrutiny here.

The second principle is that error recovery should always give the user a clear next action. "Something went wrong" is not a useful error message. "The pipeline failed during capital scoring — click here to retry, or click here to review the data manually" gives the user agency and keeps them in control of the process.

The third principle is to track error recovery patterns as a product quality metric. If users are retrying pipelines frequently, or if the "simplified mode" fallback is triggering more than 5% of the time, those are signals that the underlying AI component needs to be fixed, not that the error handling is working. Error handling buys you time to fix the root cause — it is not a permanent solution.

### Q4: When should you show the AI's reasoning versus just showing the answer?

**Answer:** Show the reasoning when the user needs to take professional or financial responsibility for the outcome, when the stakes of a wrong decision are high, or when the domain is unfamiliar enough that the user cannot independently validate the conclusion. In all three of these cases, the answer alone is not enough — the user needs to understand how the AI got there to exercise genuine judgment.

In ORCA's case, any order that triggers the ESCALATE path (cost above the auto-approve threshold) requires the manager to see the reasoning, because they are signing off on a decision that has a real financial consequence. The reasoning display is not optional UX polish; it is a product requirement that enables the human to do their job.

Conversely, for routine auto-executed orders (below the cost threshold, high Agent 3 score), you should show the reasoning only on request. Bombarding users with AI reasoning for every low-stakes decision trains them to ignore it. The default view for AUTO_EXECUTE runs should be a clean status card: "Order placed: 200 units of SKU-1142 — $8,400." The reasoning is available in the audit log but does not require the user's attention.

A useful heuristic is the "would you trust a colleague to make this call" test. For decisions where you would trust a capable colleague to act without explaining themselves, the AI does not need to show reasoning by default. For decisions where you would ask a colleague "walk me through your thinking before I approve this," the AI needs to show the reasoning up front.

### Q5: How would you improve the ORCA dashboard UX based on product thinking principles?

**Answer:** The most important improvement I would make is adding a visual trust signal to each pipeline run card on the dashboard. Currently, all output looks the same regardless of whether Agent 1 used the full CrewAI sub-crew or fell back to the simplified demand summary, and regardless of the Agent 3 confidence score. A manager cannot look at the dashboard and quickly identify which recommendations deserve more scrutiny and which can be rubber-stamped. I would add a color-coded confidence badge (High / Medium / Low) derived from the Agent 3 score and the fallback status, and I would put it in the top-right corner of every recommendation card.

The second improvement is the approval UX for HITL escalations. Right now, a manager clicking "Approve" or "Reject" gets no confirmation prompt and no field to record their reasoning. This is a problem for two reasons: accidental approvals are irreversible, and there is no feedback loop to improve the AI. I would add a one-sentence "reason for decision" field that is required for rejections (to enable Agent 3 retraining) and optional for approvals. This also creates an audit trail that protects the manager legally.

The third improvement is a trend view. The current dashboard shows individual pipeline runs, but it does not show whether the stockout rate is trending up or down, or whether the auto-approval rate has changed over the last 30 days. For a Data Science Manager reviewing the system monthly, these trend charts are more useful than a list of recent runs. I would add a metrics panel at the top of the dashboard with the four key KPIs from the metric hierarchy.

## Key Points to Say in the Interview
- Trust calibration is the alignment between AI confidence presentation and actual model confidence
- Progressive disclosure: lead with conclusions, offer reasoning on request, technical trace available but not default
- HITL UX must answer: what is recommended, why escalated, and what does the approver need to decide
- Graceful degradation means falling back to simpler outputs with clear labeling — never silent failure
- Show reasoning by default only when the user must take professional responsibility for the outcome
- Error recovery should always give the user a clear next action
- Track user override rate as a proxy for AI trust calibration quality

## Common Mistakes to Avoid
- Showing full AI trace by default — this trains users to ignore it through alert fatigue
- Using only one visual treatment for all confidence levels (high, medium, low all look the same)
- Designing the explainability layer for engineers rather than for the decision-maker who actually uses it
- Forgetting that "approve" and "reject" without reasoning collection destroys the feedback loop for model improvement
- Assuming users will read the documentation — the UI must be self-explanatory at every level

## Further Reading
- [Google PAIR Guidebook](https://pair.withgoogle.com/guidebook/) — Google's own AI UX design patterns and anti-patterns
- [Nielsen Norman Group: Explainability in AI](https://www.nngroup.com/articles/ai-explainability/) — practical UX research on how users interact with AI explanations
- [Anthropic: HHH Framework](https://www.anthropic.com/research/core-views-on-ai-safety) — Helpful, Harmless, Honest as a framework for AI product design values
