# LangSmith: Observability for LLM Applications

## What Is It? (Plain English)

LangSmith is Langchain's cloud platform for observing, debugging, and evaluating LLM applications. When your AI pipeline runs, LangSmith captures every LLM call, every tool invocation, every retrieval operation — and shows you a hierarchical trace that lets you see exactly what happened, in what order, with what inputs and outputs, at what latency, and at what token cost.

Think of it as a combination of a request profiler (like New Relic for web apps) and an experiment management platform (like MLflow for ML models). On one side, you instrument your pipeline with a few environment variables, and it automatically captures traces. On the other side, you can define evaluation datasets, run automated evaluations over those datasets, and compare pipeline versions.

Without LangSmith (or a similar observability tool), debugging a multi-agent pipeline is extremely painful. You run the pipeline, it produces a wrong output, and you have no visibility into which of the 4 agents was responsible, what context that agent received, or how the LLM interpreted the prompt. LangSmith makes debugging interactive rather than log-archaeology.

## How It Works

```
LANGSMITH DATA FLOW
═══════════════════════════════════════════════════════════════════
Your AI Pipeline
  │
  │  (automatic instrumentation via environment variables)
  │  LANGCHAIN_TRACING_V2=true
  │  LANGCHAIN_API_KEY=ls-...
  │  LANGCHAIN_PROJECT=orca-production
  │
  ▼
LangSmith (cloud)
  │
  ├── Traces view: hierarchical call tree for each pipeline run
  │     LangGraph run
  │     ├── agent1_node
  │     │     ├── LLM call (ChatGroq)
  │     │     │     ├── Input: {prompt tokens: 1247}
  │     │     │     ├── Output: {completion tokens: 389}
  │     │     │     └── Latency: 1.82s
  │     │     └── Tool calls
  │     ├── agent2_node
  │     ├── agent3_node
  │     └── execute_node (or HITL pause)
  │
  ├── Evaluations view: run test suites against dataset
  │     Dataset: 50 SKU scenarios
  │     Evaluator: correctness, faithfulness, route accuracy
  │     Results: pass rate by metric, by agent, over time
  │
  └── Prompt Hub: versioned prompts with history
        v1.0 → v1.1 (improved urgency classification)
        A/B test: which version performs better?
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google's production AI systems run thousands of pipeline executions per hour. Understanding why a pipeline produced a wrong output requires knowing what every component saw and did. LangSmith (or an equivalent like Langfuse) is the tooling layer that makes LLM systems maintainable rather than black boxes. Senior AI engineers at Google are expected to instrument their systems with observability tooling from day one, not as an afterthought. They also use evaluation datasets and automated testing — which LangSmith facilitates — rather than relying on manual review. Demonstrating that you have set up LangSmith tracing, created evaluation datasets, and used the trace view to debug a pipeline failure shows production engineering maturity.

## Interview Questions & Answers

### Q1: How do you set up LangSmith tracing for a Python AI application? What does automatic instrumentation capture?

**Answer:** LangSmith's automatic instrumentation works through the LangChain callback system. By setting three environment variables, every LangChain and LangGraph operation is automatically captured without modifying application code:

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls-abc123...
export LANGCHAIN_PROJECT=orca-production
```

With these set, every call to a LangChain component (LLM, retriever, tool, chain, LangGraph node) automatically sends a trace event to LangSmith. The trace events form a hierarchical tree called a "run."

What automatic instrumentation captures:
- **LLM calls**: input messages (formatted prompt), output message, model name, token counts (prompt + completion + total), latency, finish reason
- **Chain/LCEL runs**: inputs, outputs, intermediate steps, total latency
- **Retrieval**: query text, retrieved documents with their content and metadata, similarity scores
- **Tool calls**: tool name, input arguments, output, latency
- **LangGraph nodes**: node name, input state, output state delta, total node latency
- **Errors**: which component threw the exception, the exception message and traceback

For ORCA, adding these environment variables to the `.env` file would immediately give visibility into every agent's LLM call, showing exactly what prompt was sent to Groq and what response came back — invaluable for debugging the CrewAI compatibility issue with Agent 1.

For additional context (custom tags, metadata), use `.with_config()`:

```python
# Add custom metadata to a specific LLM call
response = llm.with_config(
    run_name="agent1_demand_analysis",
    tags=["agent1", "demand", f"sku_{sku_id}"],
    metadata={"sku_id": sku_id, "run_id": run_id, "env": "production"}
).invoke(prompt)
```

This makes the LangSmith trace searchable by SKU, run_id, and environment — essential for debugging production issues.

---

### Q2: How do you read a LangSmith trace to debug a broken pipeline? Walk me through a real debugging scenario.

**Answer:** A LangSmith trace is a tree. The root is the top-level pipeline run. Each node in the tree is a component that ran. Expanding a node shows its inputs, outputs, and timing. The colour indicates status: green = success, red = error, yellow = slow.

**Debugging scenario:** ORCA's pipeline is occasionally routing to AUTO_EXECUTE for orders that should be ESCALATE (cost > threshold). The symptom: a $25,000 order was approved without human review.

```
LangSmith trace for run_id: run_broken_789
══════════════════════════════════════════════
[LangGraph] orca_pipeline           4.2s   ✓
  [Node] agent1_node                1.1s   ✓
    [LLM] ChatGroq demand analysis  1.1s   ✓
       tokens: 1102 in / 287 out
  [Node] agent2_node                1.8s   ✓
    [LLM] ChatGroq replenishment    1.8s   ✓
       tokens: 1847 in / 512 out
  [Node] agent3_node                1.2s   ✓
    [LLM] ChatGroq capital alloc    1.2s   ✓
       tokens: 2104 in / 398 out
       ← CLICK HERE TO EXPAND ←
  [Node] route_node                 0.0s   ✓
    route: AUTO_EXECUTE             ← WRONG
══════════════════════════════════════════════
```

Expanding the Agent 3 LLM call:

**Input (prompt):** I can see exactly what context Agent 3 received. Looking at the `total_cost` field in the input: `"total_cost": 25000`.

**Output:** The LLM responded with: `"route": "AUTO_EXECUTE", "total_cost": 25000.0`. 

**Root cause found:** The LLM correctly identified the cost as $25,000. But the route_node is checking `state["capital_decision"]["total_cost"] > HITL_APPROVAL_THRESHOLD`. Looking at the route_node code, the threshold is loaded from an environment variable `HITL_THRESHOLD` which defaults to `None` when not set. `25000 > None` raises a `TypeError` that is silently caught and defaults to AUTO_EXECUTE.

**Fix:** Add a validation check at startup that `HITL_THRESHOLD` is set and numeric. Without LangSmith, this bug would have required adding print statements, redeploying, and reproducing the exact scenario — possibly taking hours.

---

### Q3: What are LangSmith evaluation datasets? How do you use them for regression testing?

**Answer:** A LangSmith evaluation dataset is a collection of test cases — input/output pairs — that you run your pipeline against to measure quality. It is the LLM equivalent of a unit test suite.

```python
from langsmith import Client
from langsmith.evaluation import evaluate

client = Client()

# Create a dataset once
dataset = client.create_dataset("orca_demand_scenarios")
client.create_examples(
    inputs=[
        {"sku_id": "SKU-001", "quantity": 5, "reorder_point": 50, "days_of_stock": 2},
        {"sku_id": "SKU-002", "quantity": 100, "reorder_point": 50, "days_of_stock": 15},
        # ... 50 test cases
    ],
    outputs=[
        {"expected_urgency": "CRITICAL", "expected_route": "ESCALATE"},
        {"expected_urgency": "LOW",      "expected_route": "AUTO_EXECUTE"},
    ],
    dataset_id=dataset.id
)

# Define an evaluator
def route_accuracy(run, example):
    actual_route = run.outputs["route"]
    expected_route = example.outputs["expected_route"]
    return {"score": int(actual_route == expected_route), "key": "route_accuracy"}

# Run evaluation
results = evaluate(
    lambda inputs: orca_pipeline.invoke(inputs),
    data=dataset.name,
    evaluators=[route_accuracy],
    experiment_prefix="orca-pipeline-v2"
)
print(results.aggregate_feedback)
# {'route_accuracy': {'mean': 0.88, 'std': 0.12, 'n': 50}}
```

The power of LangSmith datasets is regression testing: every time you change the prompts or logic, run the dataset and compare to the previous run. If route_accuracy drops from 0.88 to 0.72, something broke.

LangSmith also enables online evaluation — annotating production traces with feedback (thumbs up/down from the human approvers in ORCA's HITL flow) and using those annotations to expand the dataset with real-world cases.

---

### Q4: How does ORCA use LangSmith's `.with_config()` pattern? What metadata is worth tracking?

**Answer:** ORCA instruments every LLM call with `.with_config(run_name=..., tags=[...], metadata={...})`. This enriches the LangSmith trace with searchable context, making it possible to filter traces by SKU, by pipeline run, by agent, and by environment.

```python
# From agents/graph.py — typical instrumentation pattern
class Agent1Node:
    def __call__(self, state: AgentState) -> dict:
        sku_id = state["sku_id"]
        run_id = state["run_id"]

        analysis_prompt = build_demand_prompt(state)

        response = self.llm.with_config(
            run_name="demand_intelligence_llm",
            tags=[
                "agent1",
                "demand_analysis",
                f"sku:{sku_id}",
                "production" if IS_PRODUCTION else "development"
            ],
            metadata={
                "sku_id": sku_id,
                "run_id": run_id,
                "sku_class": state["sku_data"].get("sku_class"),
                "days_of_stock": state["sku_data"].get("days_of_stock"),
                "prompt_version": "1.2"   # track which prompt version was used
            }
        ).invoke(analysis_prompt)

        return {"demand_analysis": parse_response(response)}
```

Most valuable metadata to track:
- `sku_id`: filter all traces for a specific SKU to understand its history
- `run_id`: correlate the LangSmith trace with the ORCA pipeline log in the database
- `prompt_version`: know which version of the prompt was in use when an error occurred
- `sku_class`: filter by class A/B/C to detect if the model behaves differently by class
- `environment`: separate production and development traces

In LangSmith's UI, these tags and metadata fields become filterable — you can search "all ESCALATE decisions for Class A SKUs in the last 7 days" and find every relevant trace without reading logs.

---

### Q5: What is the LangSmith Prompt Hub? How does prompt versioning work in production?

**Answer:** The LangSmith Prompt Hub is a versioned registry for LLM prompts. Instead of hardcoding prompt strings in your code, you store them in the Hub and pull them by name and version at runtime. This enables:

1. **Non-code prompt updates:** PMs or domain experts can improve prompts without a code deploy.
2. **A/B testing:** compare two prompt versions against each other on live traffic.
3. **Rollback:** if a prompt change degrades performance, revert without a code change.
4. **Attribution:** know exactly which prompt version was used for every trace.

```python
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate

client = Client()

# Pull prompt from hub (always gets latest by default)
prompt = client.pull_prompt("orca/demand-intelligence-v2")

# Pull specific version for reproducibility
prompt = client.pull_prompt("orca/demand-intelligence-v2:abc123")

# In LangGraph node:
class Agent1Node:
    def __init__(self):
        # Load prompt at node instantiation (happens at graph compile time)
        self.prompt = client.pull_prompt("orca/demand-intelligence", include_model=True)

    def __call__(self, state: AgentState) -> dict:
        chain = self.prompt | StrOutputParser()
        response = chain.invoke({"sku_data": state["sku_data"]})
        return {"demand_analysis": parse_response(response)}
```

Prompt versioning best practice: store prompts with a commit-like versioning scheme. Tag stable versions (v1, v2) separately from development versions. In production, always reference a specific version tag — never pull `latest` in production.

For ORCA's 4 agent prompts, the current approach (hardcoded in `agents/prompts.py`) is appropriate for a portfolio project. In a team environment, moving these to LangSmith Prompt Hub would allow the business stakeholders who understand inventory policy to iterate on prompts without touching Python code.

## Key Points to Say in the Interview

- "Three environment variables instrument your entire LangChain/LangGraph application: LANGCHAIN_TRACING_V2=true, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT."
- "A LangSmith trace is a hierarchical tree — expand any node to see exact inputs, outputs, tokens, and latency."
- "Evaluation datasets are your regression test suite — run against them after every prompt or code change to detect degradation."
- "`.with_config(run_name=..., tags=[...], metadata={...})` makes traces searchable and debuggable — instrument every LLM call."
- "Prompt Hub enables non-code prompt updates, A/B testing, and rollback — essential for team AI development."
- "Online evaluation: annotate production traces with feedback, use them to grow your evaluation dataset with real-world cases."
- "For ORCA: `run_id` in trace metadata correlates the LangSmith trace with the pipeline log in the SQLite database."

## Common Mistakes to Avoid

- Not instrumenting at all and debugging by adding print statements — LangSmith changes debugging from hours to minutes.
- Using `LANGCHAIN_PROJECT=development` in production — use a separate project for each environment.
- Not tagging traces with `run_id` — makes it impossible to correlate a LangSmith trace with a user-reported issue.
- Pulling `latest` prompt from Prompt Hub in production — always pin to a specific version for reproducibility.
- Treating evaluation datasets as a one-time setup — they should grow with every bug found and every new edge case encountered.

## Further Reading

- [LangSmith documentation](https://docs.smith.langchain.com/) — official comprehensive guide including tracing, evaluation, and prompt hub
- [LangSmith evaluation guide](https://docs.smith.langchain.com/evaluation) — how to define evaluators, create datasets, and run experiments
- [LangSmith Prompt Hub](https://docs.smith.langchain.com/prompt-hub) — prompt versioning and management in production
