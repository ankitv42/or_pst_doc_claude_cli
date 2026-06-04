# Prompt Versioning and Management

## What Is It? (Plain English)

Prompt versioning is the practice of treating your LLM prompts with the same discipline as application code — tracking every change, who made it, why, and what effect it had on model behavior. When a prompt change breaks production, you need to know what changed, roll it back, and fix it. Without versioning, a prompt is just a string in a Python file or a database cell that can be edited by anyone at any time with no history and no rollback capability.

The analogy to software is precise. A function in your codebase is version-controlled in Git — you can see every change, who made it, and run the tests from any historical version. A prompt that lives as a hardcoded string in your code gets that for free. But as systems mature, prompts often move out of code into databases, configuration files, or prompt registries — and this migration, if not handled carefully, strips away all the version control and change management discipline that engineers rely on.

Think of prompt versioning as configuration management for AI behavior. The model is fixed (you do not control when providers update it), but prompts are the lever you do control. If you cannot track, test, and roll back prompt changes, you have a system whose behavior can change unpredictably at any time — and you have no tools to diagnose or reverse it.

## How It Works

Prompt versioning spans a maturity ladder, from simplest (Git-native) to most sophisticated (dedicated prompt registry):

```
MATURITY LADDER FOR PROMPT VERSIONING
══════════════════════════════════════════════════════════════
Level 1: Prompts in source code (Git-native)
  └── prompts.py → Git history tracks every change
  └── PRO: zero overhead  CON: non-engineers cannot edit

Level 2: Prompts in versioned config files
  └── prompts/v1/agent1_system.txt
  └── prompts/v2/agent1_system.txt
  └── PRO: readable files  CON: manual version management

Level 3: Prompts in database with versions table
  └── prompts table: (id, name, version, content, created_at)
  └── active_prompts table: (name, active_version)
  └── PRO: runtime switching  CON: needs migration tooling

Level 4: Prompt registry (LangSmith Hub, Promptfoo, custom)
  └── Named prompts with semantic versions (agent1-v2.3.1)
  └── Pull prompts at runtime by name+version
  └── A/B testing built in, eval integration
  └── PRO: full lifecycle management  CON: vendor/infra cost
══════════════════════════════════════════════════════════════
```

The key capability that distinguishes mature from naive systems is runtime prompt switching — the ability to change which prompt version is active without deploying new code. This enables A/B testing and instant rollback.

## Why Google Cares About This

Google operates AI systems at massive scale where a single poorly-managed prompt change can affect billions of user interactions. Prompt drift — the gradual degradation of prompt behavior as underlying models are updated by providers — is a real operational risk that has no analogue in traditional software. Google interviewers test prompt management maturity because it reveals whether you think of LLM systems as engineering systems (with proper lifecycle management) or as experimental notebooks. Senior practitioners know that the hard problems in LLM systems are operational, not algorithmic.

## Interview Questions & Answers

### Q1: Why is treating prompts as configuration (not code) a mistake at scale?

**Answer:** The argument for "prompts as config" is appealing: prompts are text, not logic; they should be editable by non-engineers (product managers, domain experts); they should be changeable without code deploys. This reasoning is sound for individual, low-stakes use cases. At scale, it creates several serious operational problems.

First, configuration changes typically bypass the testing and review processes that code changes go through. In most engineering organizations, a config change can be made by anyone with database access and goes live immediately. A code change requires a pull request, automated tests, and peer review before merging. If prompts are config, they inherit the weaker governance model. A product manager who edits a prompt to "sound better" might inadvertently break the JSON schema that downstream agents depend on — and no test ran to catch it.

Second, configuration is typically not version-controlled at the granularity that code is. A config change might be logged in a deployment system, but you cannot easily `git blame` a config entry, run the eval suite as of a specific config version, or bisect between config versions to find what broke. Prompts need code-level version control even when they are stored in a database.

Third, configuration encourages treating prompts as static text, which obscures the fact that prompts are really program logic expressed in natural language. An ORCA prompt that says "If cost exceeds $50,000, set escalate=true" is business logic. Editing it is as consequential as editing the Python function that implements the same rule. It should go through the same review process.

The right model is: prompts are code that happens to be expressed in natural language. Store them in version-controlled files (even if pulled into a database at deploy time), require eval suite passage for every change, and treat prompt reviews with the same rigor as code reviews. Non-engineers can still propose prompt changes — through pull requests, reviewed by engineers with the eval results attached.

### Q2: What is prompt drift, and how do you detect and mitigate it?

**Answer:** Prompt drift is the phenomenon where a prompt that worked well at time T produces progressively worse outputs at time T+N, even though the prompt itself has not changed. The cause is that the underlying model has changed — providers update their models continuously (safety fine-tuning, RLHF updates, capability improvements, quantization changes), and these updates can shift model behavior in ways that break existing prompts.

A well-known example: an OpenAI model update in early 2023 made models more reluctant to produce certain structured outputs that previously worked reliably. Prompts that had been running stably for months suddenly needed to be rewritten to elicit the same behavior. This was not announced in advance; teams discovered it through sudden spikes in structured output failure rates.

Detection requires continuous eval monitoring. Run your full prompt eval suite on a regular cadence (daily or weekly), not just at deploy time. Track pass rates over time as a time series. A gradual decline over 2-3 weeks without any prompt changes is the signature of prompt drift — the model is drifting away from the behavior your prompt was designed to elicit. Alert on any eval pass rate drop above a threshold (e.g., >5 percentage points week-over-week).

Mitigation strategies: (1) Pin model versions when the provider supports it (e.g., `gpt-4-0125-preview` instead of `gpt-4`), and control when you upgrade. (2) Run eval suite on the new model version before upgrading in production — treat model upgrades like dependency upgrades. (3) Maintain a prompt regression budget: when upgrading a model, allow N engineering hours to re-calibrate prompts that degrade. (4) For ORCA on Groq: Groq does not currently offer model version pinning, which means LLAMA model updates are outside your control. Running nightly evals and alerting on degradation is especially important in this environment.

### Q3: How would you design an A/B testing system for prompt changes?

**Answer:** Prompt A/B testing compares two prompt versions against real traffic to measure which produces better outcomes. Unlike model A/B testing (which requires infrastructure-level routing), prompt A/B testing can be implemented at the application layer with relatively low overhead.

The design has four components. First, a traffic splitter: a function that deterministically assigns each incoming request to a prompt variant (by hashing the request ID or user ID, so the same user consistently sees the same variant). Deterministic assignment prevents the same user seeing different behavior on repeated requests. Second, a prompt registry: store both variants (control and treatment) with version labels; the traffic splitter looks up the correct variant at runtime. Third, outcome tracking: log the variant ID alongside the request outcome (pipeline success/failure, HITL escalation rate, downstream metric). Fourth, an analysis job: periodically aggregate outcomes by variant and compute significance tests.

The choice of outcome metric is the hard part. For ORCA, a good metric might be "correct routing rate" (does the agent route ESCALATE/AUTO_EXECUTE/SUSPEND correctly as judged by human review of sampled cases), or "time to human decision" (how quickly do escalated items get approved), or simply "structured output failure rate" (does the new prompt produce fewer JSON parse errors). The metric must be measurable automatically or with lightweight human sampling.

A/B testing for prompts has a shorter required experiment duration than, say, a product feature A/B test, because outcomes are observable immediately (no need to wait for user conversion). Typically, 200-500 requests per variant is sufficient to detect a 5-percentage-point difference in a metric with p < 0.05. For ORCA at its current scale, that is achievable within a day of normal traffic. Use a Bayesian A/B testing framework rather than classical frequentist hypothesis testing to get probabilistic estimates rather than binary p-values — this is more useful for deciding when to ship a change.

### Q4: Compare prompt storage strategies: hardcoded in source, YAML files, database, and dedicated registry. When is each appropriate?

**Answer:** Hardcoded in Python source files (as string constants in `prompts.py`) is the right default for small projects. Version history is built into Git. Engineers can see the prompt alongside the code that uses it. Eval suite naturally runs against whatever version is in the codebase. The limitation is that non-engineers cannot edit prompts, and changes require a code deploy. For ORCA, this is the current approach and it is appropriate given the project scale.

YAML or text files in a `prompts/` directory add readability (prompts are often long, making them awkward in Python files) and make it easier to diff changes in pull requests. They are still version-controlled in Git. The limitation is that you need a loading convention (how does the Python code know to read `prompts/v2/agent1.yaml`?) and you can accumulate many files as versions proliferate. Best practice: use a single file per agent and rely on Git history for version tracking, rather than keeping all versions as separate files.

Database storage (PostgreSQL table with `(name, version, content, active)` columns) enables runtime prompt switching without code deploys, which is necessary for A/B testing and instant rollback. The engineering cost is a migration, an admin interface (or CLI tool) for managing active versions, and a convention for pulling prompts at runtime. The critical requirement: the database must itself be version-controlled — track schema migrations and never allow arbitrary edits without going through a change management process. For a system at Google scale, this is the minimum viable approach.

Dedicated prompt registries (LangSmith Prompt Hub, Portkey, custom-built) add eval integration, collaboration features, diff views, and automated governance. LangSmith's hub lets you push a prompt, tag it with a semantic version, attach eval results, and pull it at runtime in one line: `hub.pull("orca/agent1:v2.3")`. The overhead is a paid service and a migration. Appropriate when you have multiple teams contributing prompts, high prompt change frequency, or when you need audit trails for compliance.

### Q5: How does a prompt registry integrate with continuous deployment, and what should the rollback process look like?

**Answer:** A prompt registry integrated with CI/CD enables a fully automated prompt lifecycle: propose change → automated eval → human review → deploy → monitor → rollback if needed.

The CI integration: when a developer edits a prompt file and opens a pull request, the CI pipeline automatically runs the full eval suite against the new prompt. The PR review includes the eval results as a comment: "Layer 1 eval: 10/11 cases passing (was 11/11). Case 4 regression: expected ESCALATE, got AUTO_EXECUTE. Review required." The PR cannot merge until the eval passes or the regression is explicitly accepted by a designated reviewer. This prevents silent regressions from shipping.

Deployment: on merge to main, the CI pipeline pushes the new prompt to the registry with a semantic version tag and marks it as the active version. If you are using a database-backed registry, this is a database write; if using LangSmith Hub, it is an API call. The application reads the active version at runtime (not at startup, to enable hot-swaps).

Rollback: when a production issue is detected (eval monitoring alerts, user reports, structured output failure spike), the rollback procedure is: (1) In the registry, mark the previous version as active (one CLI command or a UI click — this takes effect immediately for all new requests). (2) File a post-incident report recording what the new prompt changed, why it caused the regression, and what the new prompt needed to do correctly. (3) Add a test case to the golden dataset covering the regression scenario. (4) Fix the prompt and go through the full PR+eval cycle before redeploying.

For ORCA, this process would mean: agent prompts live in `agents/prompts.py`, a PR modifying any prompt file triggers `evals/run_retrieval_eval.py` and eventually a full pipeline eval, and the result must pass before the PR merges. This is achievable with the existing GitHub Actions workflow (`eval_gate.yaml`) by adding agent prompt eval steps alongside the RAG retrieval eval.

## Key Points to Say in the Interview

- Prompts are code expressed in natural language and should receive code-level version control, review, and testing discipline
- "Prompts as config" is a governance anti-pattern at scale — it bypasses the testing and review that code changes go through
- Prompt drift is a real operational risk: model provider updates can break previously stable prompts without any prompt change on your side
- A/B testing for prompts requires deterministic assignment (same request always gets same variant), outcome tracking, and statistical analysis
- The maturity ladder: hardcoded → files → database → registry — each step adds runtime switching capability at an engineering cost
- Rollback must be instant (database write, not a code deploy) to minimize production impact when a prompt regression is detected

## Common Mistakes to Avoid

- Storing prompts in a database without version history — you need the full audit trail of what was active at each point in time
- Not pinning model versions when the provider supports it, then being surprised by prompt drift after an unannounced model update
- Treating prompt review as less rigorous than code review — a prompt change can change system behavior as fundamentally as a code change
- Running evals only at deploy time rather than continuously — prompt drift cannot be detected without regular monitoring between deploys
- Building a prompt A/B testing system without a clear outcome metric defined in advance — testing without a metric is not testing, it is exploration

## Further Reading

- [LangSmith Prompt Hub Documentation](https://docs.smith.langchain.com/prompt-hub) — reference for the LangChain prompt registry with versioning, eval integration, and runtime pull
- [Martin Fowler: Feature Toggles](https://martinfowler.com/articles/feature-toggles.html) — the foundational article on runtime configuration switching, directly applicable to prompt version switching patterns
- [Promptfoo Configuration and Versioning](https://www.promptfoo.dev/docs/configuration/guide/) — practical guide to YAML-based prompt management with built-in A/B testing and regression tracking
