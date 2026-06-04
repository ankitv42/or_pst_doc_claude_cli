# AI Governance and Compliance

## What Is It? (Plain English)

AI governance is the set of policies, processes, and technical mechanisms that ensure an AI system is developed and deployed responsibly — that it is fair, transparent, accountable, and safe. It is the difference between shipping an AI feature because you can and shipping it because you have verified it is ready and appropriate.

Governance frameworks exist at multiple levels. Governments are creating laws (the EU AI Act, the US Executive Order on AI). Standards bodies are publishing frameworks (NIST AI RMF). Companies are publishing voluntary commitments (Google's AI Principles, Anthropic's responsible scaling policy). Engineers are creating technical artefacts (model cards, data sheets, audit trails). All of these are responses to the same core question: when an AI system causes harm, who is responsible, and how do we prevent it?

For a senior AI engineer at Google, governance is not just a legal or policy concern — it is an engineering discipline. Auditability requires that you log what your AI system did and why. Fairness requires that you measure and report bias metrics. Human oversight requires that you design systems where humans can review, override, and stop AI decisions. These are technical choices made at design time, not compliance forms filled at launch.

## How It Works

```
EU AI ACT RISK TIERS (effective 2026):
═══════════════════════════════════════════════════════════════════
UNACCEPTABLE RISK (BANNED):
  • Social scoring by governments
  • Real-time biometric surveillance in public spaces
  • AI that exploits vulnerabilities of specific groups

HIGH RISK (strict requirements before deployment):
  • AI in critical infrastructure (energy, water, transport)
  • Medical devices with AI components
  • AI for credit scoring, insurance risk assessment
  • AI used in hiring and HR decisions
  • AI in law enforcement and border control
  Requirements: conformity assessment, HITL, transparency, accuracy documentation,
               bias testing, post-market monitoring

LIMITED RISK (transparency requirements only):
  • Chatbots (must disclose it's an AI)
  • AI-generated content (deepfakes must be labelled)

MINIMAL RISK (no requirements, but best practice encouraged):
  • Spam filters, AI in games, recommendation systems

WHERE ORCA FALLS:
  Inventory reorder decisions affecting supply chain operations
  → Likely HIGH RISK (critical infrastructure adjacent)
  → Requires: HITL for expensive decisions ✓ (already implemented)
  → Requires: audit trail of decisions ✓ (pipeline_log.py)
  → Requires: ability to explain decisions (partially implemented)
═══════════════════════════════════════════════════════════════════

NIST AI RMF FOUR FUNCTIONS:
─────────────────────────────────────────────────────────────────
GOVERN → establish policies, roles, and culture
MAP    → identify context, risks, and impact
MEASURE → analyse risks quantitatively, test and evaluate
MANAGE  → prioritise and treat risks, monitor continuously
─────────────────────────────────────────────────────────────────
```

## Why Google Cares About This

Google operates in every major regulatory jurisdiction. The EU AI Act directly affects every Google product deployed in Europe. NIST AI RMF is becoming the de facto standard for US federal procurement, affecting Google Cloud contracts. Beyond compliance, Google has made public commitments on responsible AI through its AI Principles (published 2018, updated 2023). Senior engineers at Google are expected to understand these frameworks not just as lawyers' concerns but as engineering requirements: what does "human oversight" mean in code? What does "explainability" require of the system architecture? Demonstrating this understanding signals readiness for senior-level impact.

## Interview Questions & Answers

### Q1: What is the EU AI Act? How would you assess whether a new AI system is high-risk under it?

**Answer:** The EU AI Act (entering into force in stages from 2024-2026) is the world's first comprehensive AI regulatory framework. It classifies AI systems by risk level and imposes proportionate requirements — the higher the risk, the stricter the requirements.

The key assessment question for high-risk classification is: is this AI system being used in one of the eight listed high-risk application areas, or is it a component of a product that falls under existing EU safety legislation?

The eight high-risk areas: (1) critical infrastructure; (2) education and vocational training; (3) employment and workers management; (4) access to essential private and public services (credit scoring, insurance); (5) law enforcement; (6) migration and border control; (7) justice and democratic processes; (8) biometric identification.

```
ASSESSMENT FRAMEWORK FOR NEW AI SYSTEM:
════════════════════════════════════════════════════════════
Step 1: Is it BANNED?
  → Social scoring, exploit vulnerable groups, real-time biometrics?
  → If yes: STOP. Cannot deploy in EU.

Step 2: Is it HIGH RISK?
  → Is it in one of 8 listed application areas?
  → Is it a safety component of a regulated product?
  → If yes: proceed to conformity assessment

Step 3: HIGH RISK compliance checklist:
  □ Risk management system (documented, ongoing)
  □ Data governance (training data quality, bias testing)
  □ Technical documentation (model card equivalent)
  □ Record-keeping (audit log of AI decisions)
  □ Transparency (users know they're interacting with AI)
  □ Human oversight (HITL for consequential decisions)
  □ Accuracy, robustness, and cybersecurity
  □ Conformity assessment (self-assessment or third-party audit)
  □ Registration in EU database before deployment

Step 4: Limited risk?
  → Chatbots, deepfakes: disclose AI nature to users

Step 5: Minimal risk: no requirements, best practices recommended
════════════════════════════════════════════════════════════
```

For ORCA: autonomous inventory reorder decisions affecting supply chain operations for essential goods would likely qualify as high-risk under area (1) critical infrastructure or area (8) if extended to public sector procurement. The existing HITL mechanism (interrupt_before execute_node) and audit logging (pipeline_log.py) already satisfy key high-risk requirements.

---

### Q2: What is a model card? Write a brief model card for ORCA's demand intelligence agent.

**Answer:** A model card (introduced by Google in 2019) is a short document that describes an ML model or AI system's intended use, performance characteristics, limitations, and ethical considerations. It is both a transparency mechanism (users understand what they are getting) and an accountability mechanism (developers are on record about what the system can and cannot do).

A model card typically includes: model details, intended uses, out-of-scope uses, factors affecting performance, evaluation results, and ethical considerations.

Model card for ORCA's Agent 1 (Demand Intelligence):

```
═══════════════════════════════════════════════════════════════
MODEL CARD: ORCA Demand Intelligence Agent (Agent 1)
Version: 1.0  |  Last Updated: 2025-06-04
═══════════════════════════════════════════════════════════════

MODEL DETAILS:
  Type: LLM-based analysis agent (LangGraph node)
  Base model: Llama-3.1-8b-instant via Groq API
  Fine-tuning: None (zero-shot prompting only)
  Input: SKU data (category, current_quantity, reorder_point,
                   days_of_stock, recent_sales, historical_orders)
  Output: Structured analysis: urgency classification (CRITICAL/HIGH/MEDIUM),
          lead-time impact, demand trend (UP/DOWN/STABLE), risk narrative

INTENDED USES:
  ✓ Classifying urgency of inventory reorder requests for retail SKUs
  ✓ Summarising demand trends for human reviewers
  ✓ Providing context for downstream replenishment planning (Agents 2 & 3)
  ✓ Flagging items requiring immediate expedite review

OUT-OF-SCOPE USES:
  ✗ Financial forecasting or revenue projection
  ✗ Decisions affecting safety-critical supply chains (medical, defence)
  ✗ Any use case where the output is acted on without human review
  ✗ Real-time price optimisation

PERFORMANCE:
  Evaluation: qualitative review against known inventory scenarios
  Known limitation: Agent 1's CrewAI sub-crew fails due to Groq
                   cache_breakpoint incompatibility. Falls back to
                   raw data summary (lower analytical depth).
  Hallucination rate: not formally measured; downstream agents
                      and HITL provide correction layers.

ETHICAL CONSIDERATIONS:
  - Output should never be sole basis for major purchasing decisions
  - Recommendations are advisory; human review required for orders
    exceeding HITL_APPROVAL_THRESHOLD
  - No demographic data is processed; no fairness concerns identified
  - System is designed for enterprise B2B use, not consumer-facing

LIMITATIONS:
  - Performance degrades for SKUs with < 30 days historical data
  - Does not account for external market factors (news, supply disruptions)
  - Groq free tier rate limits may cause timeouts under high load
═══════════════════════════════════════════════════════════════
```

Model cards serve the full organisation: product managers understand what the system does, legal understands the scope, operations knows the limitations to monitor for, and future engineers understand intended use.

---

### Q3: What is an audit trail? How do you design an AI system to be auditable?

**Answer:** An audit trail is a chronological record of all system actions, decisions, and the data that drove them, sufficient to reconstruct what happened and why. For AI systems, auditability is both a regulatory requirement (EU AI Act, financial regulations) and a practical debugging necessity.

The challenge with AI audit trails is that the "why" is hard to capture. A traditional system's audit trail logs: `UPDATE inventory SET quantity=50 WHERE sku_id='SKU-001' BY user='alice' AT 2025-06-04T14:32:00Z`. An AI system's decision was influenced by a 100k-token context window, a probabilistic model, and intermediate reasoning that may not be exposed. Full auditability requires capturing not just the decision but the inputs, context, and intermediate states.

ORCA's audit design (via `db/pipeline_log.py`):

```python
# What to log for each pipeline run:
audit_record = {
    "run_id": run_id,                           # unique identifier
    "timestamp_start": iso_timestamp(),
    "timestamp_end": iso_timestamp(),
    "trigger": {
        "sku_id": sku_id,
        "trigger_type": "CRITICAL_STOCK",       # why it was triggered
        "sku_data_snapshot": sku_data_at_trigger # exact data used
    },
    "agent_outputs": {
        "agent1_demand": agent1_output,          # what each agent said
        "agent2_options": agent2_output,
        "agent3_decision": agent3_output,
        "route": route_decision                  # ESCALATE/AUTO/SUSPEND
    },
    "llm_calls": [
        {
            "agent": "agent1",
            "model": "llama-3.1-8b-instant",
            "prompt_tokens": 1247,
            "completion_tokens": 389,
            "latency_ms": 1823
        }
        # ... one record per LLM call
    ],
    "outcome": {
        "status": "APPROVED",                    # what actually happened
        "approver_id": "user_abc",
        "approval_timestamp": iso_timestamp(),
        "executed_order": {
            "option_type": "standard",
            "quantity": 500,
            "total_cost": 12500.00
        }
    },
    "hard_rules_triggered": []                   # any hard rule violations
}
```

An auditable AI system must also support queries: "Show me all decisions made by Agent 3 in the last 30 days where the route was ESCALATE but the human rejected the recommendation." This requires structured logging with queryable fields, not just log file appending.

For the EU AI Act, high-risk AI systems must keep logs for the lifetime of the system or at least 10 years for certain applications. Log storage architecture (retention policies, archiving to cold storage) must be part of the system design.

---

### Q4: What are the FATE principles in responsible AI? How do you operationalise fairness in a production AI system?

**Answer:** FATE stands for Fairness, Accountability, Transparency, and Explainability. These are the four pillars of responsible AI, widely used at Microsoft, Google, and in academic literature.

**Fairness** means the system produces equitable outcomes across demographic groups and use cases. It does not produce better recommendations for some stores than others based on factors unrelated to inventory needs.

**Accountability** means there is a clear chain of responsibility when the AI causes harm. Who reviewed the model before deployment? Who approved the deployment? Who is responsible for monitoring? These are organisational questions, but they require technical support: audit logs, model cards, approval workflows.

**Transparency** means stakeholders can understand what the AI does and how. Users are told they are interacting with AI. Customers can request explanations of decisions that affect them.

**Explainability** means the system can, for a specific decision, provide a human-understandable rationale.

Operationalising fairness in a production system:

```python
# Step 1: Define fairness metrics for your context
# For ORCA: are orders recommended at similar rates for all store types?
def compute_fairness_metrics(pipeline_logs: list[dict]) -> dict:
    decisions_by_store_type = defaultdict(list)
    for log in pipeline_logs:
        store_type = log["sku_data"]["store_type"]  # e.g., urban/rural
        decisions_by_store_type[store_type].append(log["route"])
    
    return {
        store_type: {
            "escalation_rate": sum(1 for r in routes if r == "ESCALATE") / len(routes),
            "auto_execute_rate": sum(1 for r in routes if r == "AUTO_EXECUTE") / len(routes),
            "suspension_rate": sum(1 for r in routes if r == "SUSPEND") / len(routes),
        }
        for store_type, routes in decisions_by_store_type.items()
    }

# Step 2: Monitor metrics over time
# Step 3: Alert when disparity exceeds threshold
# Step 4: Investigate and remediate root cause
```

Types of AI fairness:
- **Individual fairness:** similar individuals should receive similar predictions
- **Group fairness (demographic parity):** similar outcomes across demographic groups
- **Equalised odds:** similar error rates (false positive rate, false negative rate) across groups
- **Counterfactual fairness:** the prediction should not change if only the protected attribute changes

These definitions conflict with each other in many real scenarios. A system cannot simultaneously satisfy all fairness definitions. Engineers must choose which definition is most appropriate for their context and document that choice.

---

### Q5: How do you design a human-in-the-loop mechanism that satisfies both governance requirements and user experience needs?

**Answer:** The tension in HITL design is real: regulators want maximum human oversight, but too much oversight makes systems unusable. The resolution is risk-proportionate oversight — escalate to humans only when the stakes are high enough to justify the cost of human attention.

Governance requirements typically specify: (1) humans must be able to understand what they are reviewing, (2) humans must be able to meaningfully override the AI, and (3) humans must have enough time to make a considered decision (no rubber-stamping under time pressure).

Designing HITL for these requirements:

```
RISK-PROPORTIONATE HITL DESIGN:
════════════════════════════════════════════════════════════
Risk level   │ Route        │ Human involvement
─────────────┼──────────────┼────────────────────────────────
LOW          │ AUTO_EXECUTE │ None. Logged for audit.
MEDIUM       │ AUTO_EXECUTE │ Notification sent, can override
             │              │ within review window (4 hours)
HIGH         │ ESCALATE     │ Explicit approval required before
             │              │ any action taken
CRITICAL     │ ESCALATE     │ Approval + secondary review
             │              │ required (4-eyes principle)
════════════════════════════════════════════════════════════

ORCA's implementation:
  Threshold: total_cost > HITL_APPROVAL_THRESHOLD → ESCALATE
  HITL pause: LangGraph interrupt_before=["execute_node"]
  Presentation: dashboard shows all 3 options with scores and rationale
  Time: no forced timeout — human takes as long as they need
  Override: can reject (with reason) or approve
  Audit: approval decision logged with approver ID and timestamp
```

Making HITL meaningful rather than rubber-stamping:

1. **Present the AI's reasoning.** Do not just show the recommendation — show why. Agent 3's score breakdown (budget_score: 0.8, availability_score: 0.7, lead_time_penalty: -0.1) gives the human something to evaluate.

2. **Present alternatives.** Show all 3 options (standard, partial, expedite) with their scores. The human should be able to choose a different option, not just approve or reject.

3. **Highlight anomalies.** If this recommendation is very different from historical recommendations for this SKU, flag it: "Note: this is 3x the typical order quantity for this SKU."

4. **Design the rejection path to collect signal.** When a human rejects a recommendation, ask why (structured categories + free text). This data feeds back into model improvement.

5. **Set review time standards.** For the EU AI Act high-risk category, "meaningful human oversight" means the human has sufficient time, context, and ability to override. Design the UX to support this, not to rush approvals.

## Key Points to Say in the Interview

- "EU AI Act classifies AI by risk level — inventory decisions affecting critical supply chains likely fall in the high-risk tier."
- "Model cards are the technical artefact that makes AI systems transparent — they document intended use, limitations, and evaluation results."
- "Audit trails must capture not just decisions but the inputs, context, and intermediate states — otherwise you cannot explain a past decision."
- "FATE: Fairness, Accountability, Transparency, Explainability — the four pillars of responsible AI, each with specific engineering requirements."
- "HITL is a governance mechanism, not just a UX feature — it provides the human oversight required by law for high-risk AI decisions."
- "Risk-proportionate oversight: auto-execute low-stakes decisions, escalate high-stakes ones — ORCA's ESCALATE route is a correct implementation."
- "Fairness definitions conflict — demographic parity and equalised odds cannot both be satisfied in many real-world scenarios. Choose and document."

## Common Mistakes to Avoid

- Treating governance as a post-launch compliance exercise — it must be designed in from the start (GDPR Article 25: privacy by design).
- Building HITL as a rubber-stamp mechanism where the human always approves under time pressure — this satisfies neither regulation nor safety.
- Not logging when hard rules fire — every hard rule trigger is evidence of a misalignment between LLM recommendations and business constraints.
- Using demographic parity as the only fairness metric — different fairness definitions are appropriate for different business contexts.
- Confusing model explainability with transparency — explainability is "why did it decide X for this case"; transparency is "what does this system do in general."

## Further Reading

- [EU AI Act (full text)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689) — the regulation itself; Annex III lists the high-risk AI use cases
- [NIST AI Risk Management Framework](https://www.nist.gov/system/files/documents/2023/01/26/AI%20RMF%201.0.pdf) — the US government's framework for managing AI risk; widely used in enterprise governance
- [Model Cards for Model Reporting (Mitchell et al. 2019)](https://arxiv.org/abs/1810.03993) — the original Google paper proposing model cards as a transparency mechanism
