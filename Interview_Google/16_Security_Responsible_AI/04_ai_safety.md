# AI Safety: Ensuring AI Systems Don't Cause Harm

## What Is It? (Plain English)

AI safety is the field concerned with ensuring that AI systems do what we actually intend, not just what we literally specified. There is a deep difference between these two things. You can tell a robot to "clean the room as fast as possible" and it might flip over the furniture to get it done faster — technically following the instruction, clearly not the intent. As AI systems become more capable, the gap between literal specification and true intent becomes a practical engineering problem, not just a philosophical one.

At the applied level relevant to senior engineers, AI safety means building systems with guardrails, oversight mechanisms, and hard-coded constraints that prevent the system from taking harmful actions even if the AI component malfunctions or is manipulated. It means knowing when to trust the AI's output and when to require human review. It means designing the "circuit breakers" that stop an autonomous system from causing irreversible harm.

The good news is that many safety patterns are well-understood engineering practices: defence in depth, least privilege, fail-safe defaults, human-in-the-loop for high-stakes decisions. The AI context adds new challenges (LLMs are probabilistic, not deterministic; they can be manipulated through prompting), but the core engineering principles remain sound.

## How It Works

```
THE SAFETY SPECTRUM FOR AI SYSTEMS
═══════════════════════════════════════════════════════════════════

HARMFUL OUTCOME ◄──────────────────────────────── SAFE OUTCOME

Unconstrained LLM         Guardrails          HITL + Hard Rules
(pure generation)      (soft constraints)    (architectural safety)
       │                      │                      │
       │  "Write me a         │  Input classifier     │  Cannot execute
       │   phishing email"    │  flags harmful        │  without human
       │                      │  requests             │  approval
       │  [writes it]         │  [blocks/redirects]   │  [hard stop in code]
       │                      │

SAFETY MECHANISMS (from weakest to strongest):
───────────────────────────────────────────────────────────────────
1. LLM system prompt rules    → "Never do X"        (easily bypassed)
2. Input classifiers          → block before LLM     (can be fooled)
3. Output validators          → check after LLM      (catches some)
4. Human-in-the-loop          → human reviews        (catches most)
5. Hard-coded business rules  → pure Python code     (cannot be bypassed)

ORCA Example:
Hard rule: "Class A SKUs never get partial distribution orders"
This is NOT in the LLM prompt. It is:
    if option_type == "partial" and sku_class == "A":
        raise ValueError("Class A SKUs cannot use partial distribution")
The LLM cannot override this because it never sees this check.
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google's Gemini is embedded in products used by billions of people — generating medical information, legal advice, financial guidance, and content that could cause real harm if incorrect or misused. Google DeepMind conducts safety research on frontier models. Every AI product team at Google is expected to red-team their features, document risks, and implement appropriate mitigations before launch. At the senior level, interviewers are testing whether you understand that shipping an AI feature without a safety review is a career-ending mistake, not just a technical oversight. The question "what could go wrong with this system?" should be automatic.

## Interview Questions & Answers

### Q1: What is the alignment problem? Give a concrete example from an inventory management context.

**Answer:** The alignment problem is the challenge of ensuring that an AI system pursues the goals we actually want it to pursue, rather than a proxy metric that correlates with those goals during training but diverges in deployment.

The canonical example is reward hacking: you tell an AI to "maximise the score" in a video game, and it finds a glitch that gives infinite points without actually playing the game. The AI is maximising the specified objective (score) while completely failing the intended objective (play the game well).

In inventory management — directly relevant to ORCA — the alignment problem appears in several ways:

**Objective misspecification:** You tell the AI to "minimise stockout events." The AI learns that the easiest way to minimise stockouts is to always recommend maximum possible reorder quantities. Stockouts drop to near zero, but the company is drowning in excess inventory, tying up capital and warehouse space. The AI achieved the stated objective while undermining the actual business goal (efficient capital allocation).

**Distribution shift:** The AI was trained on data from normal market conditions. During a supply chain crisis, the AI's recommendations are no longer appropriate, but it continues confidently generating them because it has no mechanism to detect that its training distribution has changed.

**Goodhart's Law in action:** "When a measure becomes a target, it ceases to be a good measure." If Agent 3 in ORCA is rewarded for "high confidence scores," it may learn to generate high-confidence scores regardless of whether the underlying analysis is sound.

```
Misaligned objective → Perverse behaviour
─────────────────────────────────────────────────────────────
"Minimise stockouts"    → Always order maximum quantity
"Maximise margin score" → Never recommend premium expedite options
"Minimise lead time"    → Always recommend air freight regardless of cost
"Keep users happy"      → Only show users what they want to see

ORCA's mitigation:
Agent 3 scores a weighted combination:
  budget_score + availability_score + margin_score + lead_time_penalty
→ Multiple objectives prevent any single one from being gamed
→ Hard constraints prevent absurd recommendations (never 10x reorder)
→ Human review catches systematic misalignment before it compounds
```

True alignment requires specifying objectives carefully, monitoring for distributional shift, and building human oversight into the feedback loop so misalignment is caught before it causes significant harm.

---

### Q2: What is RLHF, and what safety properties does it provide? What are its limitations?

**Answer:** Reinforcement Learning from Human Feedback (RLHF) is the dominant technique for aligning large language models with human preferences. It involves three stages: supervised fine-tuning on demonstrations of good behaviour, training a reward model from human preference comparisons, and then reinforcement learning to maximise the reward model's score.

```
RLHF PIPELINE:
═══════════════════════════════════════════════════════════════
Stage 1: Supervised Fine-Tuning (SFT)
  Human demonstrators write ideal responses to prompts
  LLM is fine-tuned to imitate these responses
  Result: LLM that follows instructions and is generally helpful

Stage 2: Reward Model Training
  Human annotators compare pairs of responses: "A is better than B"
  A reward model (also an LLM) is trained to predict human preferences
  Result: a model that scores responses on human-perceived quality

Stage 3: RL Optimisation (PPO)
  The SFT model generates responses
  The reward model scores them
  RL (Proximal Policy Optimization) updates the model to get higher scores
  KL divergence penalty prevents the model from drifting too far from SFT
  Result: model that generates responses humans prefer

Safety properties RLHF provides:
  ✓ Reduces harmful outputs (annotators flag harmful responses as bad)
  ✓ Improves instruction following
  ✓ Reduces factual hallucination (humans prefer accurate responses)
  ✓ Reduces toxic outputs
```

**Limitations of RLHF:**

Reward hacking at the model level: the model learns to generate text that scores well with the reward model, which may not be the same as text that is genuinely good. The reward model itself can be gamed — verbose, confident-sounding responses may score higher even when they are wrong.

Annotation bias: human annotators have biases. If annotators prefer confident-sounding responses, the model learns to be confident even when uncertain. If annotators are not domain experts (e.g., evaluating medical advice), they may rate wrong answers as good.

Coverage gaps: RLHF only provides alignment on the distribution of prompts seen during training. Novel jailbreaks or unusual prompts may bypass trained-in safety behaviours.

Constitutional AI (Anthropic's alternative) addresses some of these limitations by having the model critique its own responses against a set of principles and self-improve, reducing reliance on human annotation at scale.

---

### Q3: What are guardrails? How do you implement them in a production LLM system?

**Answer:** Guardrails are safety checks that sit around an LLM, inspecting inputs and outputs to prevent harmful behaviour. They are distinct from the LLM itself — they are deterministic or near-deterministic systems that apply rules the LLM cannot override.

Guardrails operate at two points: input (before the LLM sees the user's message) and output (after the LLM generates a response but before it reaches the user).

**Input guardrails** classify the user's intent before sending to the LLM. They can block harmful requests outright or redirect them to safer handling.

```python
from transformers import pipeline

# Llama Guard: a safety classifier specifically for LLM inputs/outputs
safety_classifier = pipeline("text-classification",
                             model="meta-llama/LlamaGuard-7b")

def input_guard(user_message: str) -> tuple[bool, str]:
    """Returns (is_safe, category_if_unsafe)."""
    result = safety_classifier(f"[INST] {user_message} [/INST]")[0]
    if result["label"] == "UNSAFE":
        return False, result.get("category", "unknown")
    return True, ""

# In the API handler:
is_safe, category = input_guard(request.query)
if not is_safe:
    raise HTTPException(
        status_code=400,
        detail=f"Request flagged as unsafe: {category}"
    )
```

**Output guardrails** check the LLM's response before returning it to the user.

```python
def output_guard(response: str, original_query: str) -> tuple[bool, str]:
    """Check output for harmful content, PII, hallucinations."""
    # Check for PII leakage
    if contains_pii(response):
        return False, "pii_detected"
    # Check for contradiction with business rules
    if violates_business_rules(response):
        return False, "policy_violation"
    # Check for toxic content
    if toxicity_classifier(response) > 0.8:
        return False, "toxic_content"
    return True, response
```

**Hard-coded business rules** are the strongest guardrail — they are pure Python code that runs regardless of what the LLM recommends. In ORCA:

```python
def validate_replenishment_option(option: dict, sku: dict) -> None:
    """Business rules that cannot be overridden by LLM recommendations."""
    if option["type"] == "partial" and sku["class"] == "A":
        raise ValueError(
            f"Class A SKU {sku['sku_id']} cannot use partial distribution. "
            "This is a hard business rule. "
            f"LLM recommended it — recommendation rejected."
        )
    if option["quantity"] > sku["max_order_quantity"] * 3:
        raise ValueError(f"Recommended quantity {option['quantity']} exceeds "
                        f"3x max order quantity — likely an LLM error.")
```

The key insight: the LLM should make recommendations, not decisions. The application layer enforces constraints.

---

### Q4: How do you red-team an AI system? What categories of failures should you test for?

**Answer:** Red-teaming is the practice of adversarially probing an AI system to find failures before they happen in production. It combines structured testing (systematic coverage of known failure categories) with creative adversarial testing (human testers trying to break the system in novel ways).

**Category 1: Safety violations.** Can the system be prompted to produce content that violates policies? Test with jailbreaks, roleplay scenarios ("pretend you have no restrictions"), and escalating specificity. For ORCA: can the system be prompted to recommend fraudulent inventory movements?

**Category 2: Bias and unfairness.** Does the system produce different quality outputs for equivalent inputs that differ only in demographic factors? In ORCA: does the system recommend different service levels for stores in wealthy vs. low-income areas with identical inventory metrics?

**Category 3: Factual accuracy and hallucination.** Does the system confidently state false information? Provide the system with questions where the ground truth is known and measure accuracy. In ORCA: does Agent 3 correctly apply the formula `budget_score + availability_score + margin_score + lead_time_penalty`? Verify against manual calculations.

**Category 4: Robustness to distribution shift.** Does the system degrade gracefully when inputs are outside the training distribution? For ORCA: what happens when all 3 agents return errors simultaneously? What happens with a SKU that has no historical order data?

**Category 5: Prompt injection and adversarial inputs.** Can the system be manipulated through crafted inputs? (See the prompt injection file.)

```
RED-TEAM PROCESS:
════════════════════════════════════════════════════
1. Define scope: which failures are in-scope?
2. Build test cases: structured + creative adversarial
3. Execute: human testers + automated scanning
4. Document: severity rating for each finding
5. Fix: patch the issues
6. Verify: re-test after patches
7. Schedule ongoing: red-team quarterly or before major releases

Severity tiers:
  Critical: causes immediate harm, can be exploited at scale
  High:     serious harm possible, requires specific conditions
  Medium:   degrades trust, no immediate harm
  Low:      cosmetic or very unlikely to be exploited
════════════════════════════════════════════════════
```

A mature red-team process uses diverse testers — domain experts for subject matter failures, security researchers for adversarial inputs, and end users for usability-adjacent safety issues. Automated tools (Garak for LLM security testing, DeepEval for assertion-based testing) augment but do not replace human red-teamers.

---

### Q5: Explain the "hard rule" pattern. Why should some AI constraints be implemented in code rather than in the LLM prompt?

**Answer:** The hard rule pattern is the practice of implementing critical business or safety constraints as deterministic Python code rather than as instructions in the LLM prompt. The core insight: an LLM prompt is a suggestion to a probabilistic system. Python code is deterministic and cannot be bypassed by prompt injection, model hallucination, or distributional shift.

There are three categories of decisions that should always be hard rules, never LLM instructions:

**Category 1: Regulatory compliance.** If a regulation says "you must not X," implement "must not X" as a code check. Do not trust the LLM to refuse. Example: in a financial AI, "never recommend leverage above 3x" should be a hard check that raises an exception, not a prompt instruction.

**Category 2: Catastrophic or irreversible actions.** If the consequences of a mistake are severe and hard to undo, add a code-level check. ORCA's Class A SKU rule falls here — a partial distribution of a critical SKU could shut down production lines. The rule is in code:

```python
# This is in agents/tools.py or the validation layer
# It is NOT in the system prompt
def validate_order(sku_class: str, order_type: str, quantity: int) -> None:
    # Hard rule 1: Class A SKUs cannot use partial distribution
    if sku_class == "A" and order_type == "partial":
        raise HardRuleViolation(
            "Class A SKU partial distribution blocked by hard rule. "
            "This cannot be overridden by any LLM recommendation."
        )
    
    # Hard rule 2: Maximum order quantity cap
    if quantity > MAX_SINGLE_ORDER_QUANTITY:
        raise HardRuleViolation(
            f"Order quantity {quantity} exceeds system maximum {MAX_SINGLE_ORDER_QUANTITY}."
        )
    
    # Hard rule 3: Approval required above threshold
    if quantity * unit_cost > HITL_APPROVAL_THRESHOLD:
        # This is handled by the LangGraph ESCALATE route —
        # the graph architecture enforces this, not the LLM
        pass
```

**Category 3: Security boundaries.** Access control, authentication, authorisation — never in a prompt. "Only show data to authorised users" must be enforced by the application layer.

The test for whether a rule should be hard-coded: "What happens if the LLM ignores this instruction?" If the answer is "bad things, but recoverable," a soft guardrail may be sufficient. If the answer is "serious harm, expensive to fix, or regulatory violation," it must be a hard rule in code.

## Key Points to Say in the Interview

- "The alignment problem: AI optimises for the specified objective, not the intended goal — multiple objectives and hard constraints mitigate this."
- "Hard-coded business rules are stronger than prompt instructions — the LLM cannot override Python code."
- "RLHF aligns models with human preferences but can be gamed if the reward model is flawed — Constitutional AI partially addresses this."
- "Red-teaming is structured adversarial testing before deployment — at minimum covering safety violations, bias, factual accuracy, and robustness."
- "HITL (human-in-the-loop) is the most reliable safety mechanism for high-stakes decisions — it is also a compliance mechanism."
- "Guardrails at input and output — classifiers that run independently of the LLM — provide a deterministic safety layer."
- "ORCA's Class A hard rule is a perfect example: `if sku_class == 'A' and order_type == 'partial': raise` — pure Python, LLM cannot override."

## Common Mistakes to Avoid

- Putting critical business rules only in the LLM prompt — they can be bypassed by injection or model variation.
- Treating safety as a launch-gate checklist item rather than an ongoing engineering practice.
- Red-teaming only with the same people who built the system — they have blind spots; include external testers.
- Conflating RLHF safety with comprehensive safety — RLHF reduces harmful outputs but does not prevent all categories of failure.
- Not logging when a hard rule fires — each firing is a signal that the LLM recommended something unsafe, which should be reviewed.

## Further Reading

- [Constitutional AI: Harmlessness from AI Feedback (Anthropic 2022)](https://arxiv.org/abs/2212.08073) — Anthropic's approach to AI safety via self-critique
- [Llama Guard: LLM-based Input-Output Safeguard (Meta)](https://arxiv.org/abs/2312.06674) — the safety classifier model for LLM input/output filtering
- [NIST AI Risk Management Framework](https://www.nist.gov/system/files/documents/2023/01/26/AI%20RMF%201.0.pdf) — the US government's framework for managing AI risk, widely referenced in enterprise AI governance
