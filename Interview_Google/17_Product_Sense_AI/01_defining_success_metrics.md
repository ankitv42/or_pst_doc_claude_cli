# Defining Success Metrics for AI Features

## What Is It? (Plain English)

When you build an AI feature, you need a way to know whether it is working. A "success metric" is simply a number that tells you if the product is doing what it was meant to do. The tricky part with AI is that the obvious numbers are often misleading. For example, if your AI responds to every question in under 200 milliseconds, that sounds great — but if every answer is wrong, speed is irrelevant.

Success metrics for AI products fall into a few categories. A **north star metric** is the single most important number — the one that, if it goes up, you know the product is genuinely delivering value. **Guardrail metrics** are the "do not cross this line" numbers — things like error rate, cost per call, or p99 latency. If a guardrail metric crosses its threshold, you stop and fix it even if the north star looks healthy. **Leading indicators** are metrics that predict future success before you can measure the real outcome (like "days to first order approval" predicts whether a new user will stick around). **Lagging indicators** are downstream outcomes you care about but can only measure weeks later (like "annual inventory holding cost").

Vanity metrics are the enemy. Vanity metrics go up because you are doing more activity, not because you are delivering more value. Examples: total API calls, total pipeline runs, total RAG chunks indexed. These numbers can all increase while the product is getting worse. The discipline of metric definition is asking: if this number went up but nothing else changed, would a real business stakeholder say the product is better?

## How It Works (or: How to Think About This)

Use this framework when defining metrics for any AI feature:

```
STEP 1: Define the JOB TO BE DONE
  "What is the user/system trying to accomplish?"
  ↓
STEP 2: Define the NORTH STAR
  "What single metric proves the job is done well?"
  ↓
STEP 3: Define GUARDRAIL METRICS
  "What must NOT break while we improve the north star?"
  ↓
STEP 4: Separate LEADING from LAGGING indicators
  "What signals appear in days vs. weeks vs. months?"
  ↓
STEP 5: Test for VANITY
  "Could this metric improve while the product gets worse?"
  If YES → discard or demote to monitoring-only
```

For ORCA (the 4-agent inventory pipeline), the metric hierarchy looks like this:

```
NORTH STAR
  └─ Stockout rate reduction (%)
       ← This is the actual business problem ORCA was built to solve

PRIMARY SUCCESS METRICS (health of the pipeline itself)
  ├─ Auto-approval rate (% of runs completing without human intervention)
  ├─ Human approval acceptance rate (when HITL fires, how often does the manager approve?)
  └─ $ value of orders placed vs. baseline rule-based system

GUARDRAIL METRICS (must not degrade)
  ├─ Pipeline failure rate (unhandled exceptions / total runs)
  ├─ Agent 1 CrewAI fallback rate (proxy for LLM call quality)
  ├─ Cost per pipeline run ($)
  └─ Time-to-decision (minutes from trigger to approved order)

LEADING INDICATORS (signal problems early)
  ├─ RAG retrieval pass rate (Layer 1 eval ≥ 70%)
  ├─ Agent 3 capital score distribution (are scores clustering oddly?)
  └─ Interrupt/resume ratio (are too many orders hitting ESCALATE path?)

LAGGING INDICATORS (true business outcomes, weeks away)
  ├─ Inventory carrying cost ($/unit/month)
  ├─ Lost sales due to stockout ($)
  └─ Order error rate (wrong SKU, wrong quantity ordered)
```

## Why Google Cares About This

Google interviews for senior AI/ML Product roles expect you to connect technical decisions to measurable business outcomes. Any candidate can list metrics; a senior candidate explains why a particular metric is the right one, what its failure modes are, and how it fits into a hierarchy of other metrics. Google products at scale have to make tradeoff decisions every day — should we run more experiments, or protect user trust? Should we optimize for latency or accuracy? You cannot answer those questions without a clear metric hierarchy. Showing you can define, defend, and operationalize a metric framework signals that you think at the system level, not just the feature level.

## Interview Questions & Answers

### Q1: How would you define the north star metric for an AI-powered inventory management system?

**Answer:** I would start by asking what problem the system was actually built to solve at the business level, not the technical level. For an inventory system, the ultimate business pain is either stockout — you run out of product and lose sales — or overstock — you tie up capital in inventory that sits in a warehouse. So the north star is almost certainly a variant of stockout rate, measured as the percentage of SKU-days where a product was at zero stock during business hours.

The reason I would not choose something like "pipeline auto-approval rate" as the north star is that it is internally focused. A system that auto-approves everything, including bad orders, would have a perfect auto-approval rate and a terrible business outcome. The north star must be the outcome the business cares about, not the health of the tool.

The practical challenge with stockout rate as a north star is latency — it is a lagging indicator that takes weeks to observe. This is why you need a leading indicator sitting above it in your monitoring dashboard: something like RAG retrieval quality, or agent decision accuracy on a golden dataset of historical orders, that gives you a signal about pipeline health before you can see the downstream stockout impact.

Finally, every north star needs guardrail metrics. For an inventory AI, the critical guardrails are cost per decision (you cannot spend $50 in LLM calls to approve a $30 order), decision latency (if it takes 4 hours to recommend a reorder, the lead time window closes), and a human-override rate threshold (if the business is overriding AI decisions 80% of the time, the AI is not trusted and needs to be retrained).

### Q2: What is the difference between a leading indicator and a lagging indicator? Give a concrete example.

**Answer:** A lagging indicator measures an outcome that has already happened — it confirms that the system is (or is not) working, but by the time you see it, it is too late to course-correct quickly. Stockout rate is a lagging indicator for an inventory AI: you can only measure it after the stock ran out and a sale was missed. Revenue impact from bad orders is another lagging indicator.

A leading indicator is a signal that predicts the lagging outcome before it materializes. It is observable earlier and usually more actionable. For ORCA, a useful leading indicator is the percentage of Agent 1 runs that fall back to the raw-data demand summary instead of using the CrewAI sub-crew output. If that fallback rate suddenly spikes from 10% to 60%, it is a strong signal that something broke in the LLM integration — and you can act on that signal before any wrong reorder recommendation reaches a human approver.

The skill is in choosing leading indicators that are genuinely predictive, not just technically convenient. It is easy to measure something that is technically observable but does not actually predict the outcome you care about. A good test is: "If this leading indicator improves, will the lagging indicator reliably improve too, eventually?" If you cannot draw that causal chain, the leading indicator is probably a vanity metric in disguise.

### Q3: How do you avoid vanity metrics when your stakeholders keep asking for them?

**Answer:** Vanity metrics are seductive because they always go up and they feel good to report. Total pipeline runs, total API calls, total orders processed — if the system is running, these will trend upward regardless of quality. The challenge is that stakeholders — especially executives — often ask for these because they are easy to understand and easy to visualize.

My approach is to reframe the conversation using the "so what" test in the stakeholder meeting itself. When someone asks for a metric, I ask: "If this number doubled next month, what decision would you make differently?" If the answer is "nothing" — they would not hire more people, they would not change the roadmap, they would not increase the budget — then the metric is not actionable and probably should not be in the executive dashboard.

A complementary technique is to always present vanity metrics alongside a quality denominator. Instead of "we processed 1,000 orders this month," say "we processed 1,000 orders with a 94% human-acceptance rate, up from 87% last month." The denominator transforms the vanity number into a quality signal.

The deeper issue is that stakeholders asking for vanity metrics are often doing it because they do not have access to better metrics. Part of the job of a senior PM or engineer is to build the measurement infrastructure — dashboards, logging, eval pipelines — that makes the right metrics available and trustworthy. ORCA, for example, has a Layer 1 retrieval eval that runs on every push to main. That is the kind of automated quality signal that gives stakeholders a real number to track instead of proxy activity metrics.

### Q4: For ORCA specifically, how would you measure whether the 4-agent pipeline is adding value over a simple rule-based system?

**Answer:** The right experimental design is a parallel holdout study. You run both systems on the same incoming inventory alerts: the rule-based system makes its recommendation, the 4-agent pipeline makes its recommendation, and you track the downstream outcomes for each group over several weeks. The key outcome metrics are stockout rate, average order cost, and the rate at which human reviewers override the recommendation.

The hypothesis being tested is: does the LLM pipeline make better decisions than a deterministic rule engine? "Better" has to be defined before you run the experiment. I would define it as: lower stockout rate AND lower override rate AND cost per good decision below a defined threshold. All three need to be true for the AI to justify its additional complexity and cost.

One complication with this experiment design is that inventory is not independent across SKUs or stores — if you stockout on one SKU, demand for substitute SKUs increases. This means you need to randomize at the store level, not the SKU level, to avoid contamination between the treatment and control groups.

The leading indicator I would watch during the experiment is agent decision confidence scores and the distribution of the ESCALATE / AUTO_EXECUTE / SUSPEND routing from Agent 4. If the pipeline is routing 70% of orders to ESCALATE (human review), it is not delivering on its core promise of automation, even if the decisions themselves are correct. That routing distribution is an early signal about whether the thresholds in the system need recalibration.

### Q5: How do you handle a situation where your north star metric is improving but your guardrail metric is also degrading?

**Answer:** This is one of the most common real-world situations in AI product management and it is exactly what guardrail metrics are designed to catch. The answer is almost always: pause optimization on the north star and fix the guardrail first. This is because guardrail metrics usually represent constraints the business cannot or will not violate — cost ceilings, latency SLAs, safety thresholds, legal compliance requirements.

A concrete ORCA example: suppose the auto-approval rate goes from 40% to 70% over a sprint (north star improving) but cost per pipeline run goes from $0.08 to $0.35 (cost guardrail degrading). The improvement in auto-approval was probably achieved by using a larger, more expensive model for Agent 3's capital scoring. The question is whether the business math holds: if auto-approving 30% more orders saves $X in human reviewer time, and those extra approvals cost $Y more in LLM spend, is X > Y? If it is, you document the tradeoff explicitly and raise the cost guardrail threshold. If it is not, you roll back the model change.

The meta-point here is that the relationship between north star and guardrails requires explicit documentation. In any serious AI system, the tradeoff zone — where improving one metric degrades another — must be written down, agreed to by stakeholders, and revisited on a defined cadence. Ad hoc decisions made in isolation create technical debt that is very hard to unwind later.

## Key Points to Say in the Interview
- Always define the north star as the business outcome, not the AI performance metric
- Guardrail metrics are not secondary — they are constraints the system must not violate
- Leading indicators give you signal weeks before lagging outcomes are observable
- The "so what" test (what decision changes if this metric doubles?) exposes vanity metrics
- Metric hierarchies need to be agreed to by stakeholders before you build the dashboard
- For AI systems, always track model-specific quality metrics (recall, precision, override rate) separately from business metrics
- A metric framework without experimental controls (holdout, A/B) cannot prove causation

## Common Mistakes to Avoid
- Presenting auto-approval rate or pipeline run count as the north star (these are activity metrics, not outcome metrics)
- Defining too many north star metrics — if everything is important, nothing is
- Ignoring the cost dimension; for LLM-based systems, cost per call is always a guardrail
- Conflating model accuracy (evaluated offline on a test set) with business impact (measured in production)
- Proposing metrics you cannot actually measure given the current logging and instrumentation

## Further Reading
- [Reforge: North Star Framework](https://www.reforge.com/blog/north-star-metric) — the canonical product framework for north star metric selection
- [Google's HEART Framework](https://research.google/pubs/measuring-the-user-experience-on-a-large-scale-user-studies-that-inform-product-decisions/) — Google's own rubric for user experience metrics
- [Chip Huyen: Metrics for ML Systems](https://huyenchip.com/2022/02/07/data-distribution-shifts-and-monitoring.html) — grounded treatment of ML-specific metrics and monitoring
