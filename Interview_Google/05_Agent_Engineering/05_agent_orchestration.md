# Agent Orchestration: Coordinating Multiple Agents

## What Is It? (Plain English)

A single AI agent — one LLM with tools — can handle many tasks, but some problems are genuinely too complex, too large, or too multi-domain for one agent to handle well. Just as a large company splits work across specialized teams (finance, engineering, legal) rather than having one person do everything, complex AI workflows benefit from multiple specialized agents that each do one thing well and are coordinated by a higher-level orchestrator.

Agent orchestration is the design of the coordination layer: how does the supervisor agent decide which worker agent to call? How do agents share information? What happens if a worker agent fails? Can multiple agents work in parallel? This is directly analogous to designing a management structure for a team — you need clear roles, clear communication channels, a way to handle disagreements, and a fallback when someone drops the ball.

The two leading frameworks for multi-agent orchestration are LangGraph (which models orchestration as a state machine graph with explicit message passing) and CrewAI (which models it as a "crew" of role-playing agents coordinated by a manager agent). Both work, but they reflect different philosophies: LangGraph gives you explicit, programmatic control over every transition; CrewAI delegates more coordination decisions to the LLM itself.

## How It Works

```
Supervisor / Worker Pattern (most common):

                    ┌─────────────────────────────┐
                    │     SUPERVISOR AGENT         │
                    │ (receives user goal,         │
                    │  decomposes into sub-tasks,  │
                    │  routes to specialists,      │
                    │  aggregates results)         │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
   │  DEMAND AGENT    │ │  SUPPLY AGENT    │ │  FINANCE AGENT   │
   │ (domain: market  │ │ (domain: vendor  │ │ (domain: budget, │
   │  trends, demand  │ │  availability,   │ │  ROI, cash flow) │
   │  forecasting)    │ │  lead times)     │                    │
   └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 │ (results aggregated)
                                 ▼
                    ┌─────────────────────────────┐
                    │     SUPERVISOR AGENT         │
                    │ (synthesizes into final      │
                    │  recommendation)             │
                    └─────────────────────────────┘

Message Passing Format:
{
  "from": "supervisor",
  "to": "supply_agent",
  "task": "Evaluate 3 supplier options for SKU-1042, 500 units",
  "context": {"urgency": "critical", "budget_cap": 50000},
  "expected_output": "ranked supplier list with lead times and costs"
}
```

## Why Google Cares About This

Google deploys multi-agent systems at scale — from DeepMind's research agents to Google Cloud's Vertex AI Agent Builder. The architectural decisions in multi-agent design (when to parallelize, how to prevent deadlocks, how to handle partial failures, when a single agent is actually better) are exactly the kind of system design questions Google asks. Candidates who can discuss tradeoffs between LangGraph and CrewAI, explain the supervisor/worker pattern, and reason about failure modes demonstrate the engineering depth needed for senior AI/ML roles.

## Interview Questions & Answers

### Q1: What is the supervisor/worker pattern and when should you use it instead of a single agent?

**Answer:** The supervisor/worker pattern is a hierarchical multi-agent architecture where a coordinator agent (the supervisor) receives the user's high-level goal, decomposes it into sub-tasks, delegates each sub-task to a specialized worker agent, collects the results, and synthesizes a final response. The supervisor does strategic reasoning; workers do tactical execution in their domains.

Use multi-agent orchestration when you have genuine specialization boundaries that benefit from separate context windows and separate tool sets. A research agent that needs to simultaneously search academic papers, query financial databases, and check regulatory filings would benefit from three specialized workers: a research agent (with Semantic Scholar and arXiv tools), a financial agent (with Bloomberg/SEC Edgar tools), and a legal agent (with regulatory database tools). Each worker's context window is focused on its domain — no cross-contamination of unrelated tool results — and all three can run in parallel.

However, the overhead of multi-agent orchestration is significant: latency (multiple LLM calls), cost (multiple tokens billed), and complexity (more failure modes). A single well-prompted agent with all the necessary tools is almost always faster, cheaper, and more reliable than a multi-agent system. The honest answer to "when to use multi-agent" is: when the task genuinely cannot be completed well by a single context window (too much information, too many competing domains), or when parallelism provides a required latency reduction that a sequential single agent cannot achieve.

Rule of thumb: start with a single agent and add worker agents only when you hit a specific, measurable problem — context window overflow, unacceptably slow sequential performance, or poor quality due to domain mixing. Don't use multi-agent because it sounds architecturally sophisticated; use it when it solves a real constraint.

### Q2: How do LangGraph and CrewAI differ in their approach to agent orchestration? When would you choose each?

**Answer:** LangGraph models orchestration as an explicit state machine with typed state objects, deterministic edges (or conditional edges with explicit routing functions), and persistent checkpointing. The developer specifies every possible state and every possible transition in code. The LLM makes decisions within nodes, but the orchestration structure is programmatic. This gives you full control, visibility, and debuggability — you can inspect the exact state at any point, replay from any checkpoint, and guarantee that certain transitions cannot happen. The cost is verbosity: LangGraph requires more code and more explicit design upfront.

CrewAI models orchestration as a conversation between role-playing agents managed by a manager agent. You define each agent's role, backstory, and goals in natural language, define tasks and assign them to agents, and CrewAI's manager agent dynamically decides the execution order, what to delegate, and when to aggregate. The developer writes less code — CrewAI handles the coordination logic. The cost is transparency: because coordination decisions are made by an LLM (the manager), they can be unpredictable, hard to debug, and vulnerable to the manager agent hallucinating a workflow that doesn't match your intent.

Choose LangGraph when: the workflow has well-defined states and transitions, you need guaranteed execution order, you need human-in-the-loop pauses at specific points, or you need audit trails for compliance. Choose CrewAI when: the coordination logic is complex and hard to specify programmatically, the tasks are exploratory (you're not sure exactly what steps are needed upfront), and you prioritize rapid development over guaranteed determinism.

In practice, for production systems handling financial decisions, medical recommendations, or any compliance-sensitive domain, LangGraph's determinism is usually required. CrewAI is excellent for research, prototyping, and tasks where flexibility matters more than guarantees.

### Q3: How do agents pass information to each other? What are the design patterns?

**Answer:** There are three main patterns for inter-agent communication: shared state, message passing, and blackboard (shared memory). Each has different tradeoffs.

Shared state is LangGraph's approach: there is a single typed state object (usually a Python TypedDict or Pydantic model) that all nodes read from and write to. Agent 1 writes its output to `state["demand_analysis"]`; Agent 2 reads from it. The state object is passed through the graph and is available to any node. This is simple, debuggable, and maintains a complete record of all intermediate outputs. The downside is that all agents share the same state schema — you need to define upfront what every agent will produce, which can create coupling.

Message passing is more loosely coupled: agents send discrete messages to each other through a queue or channel, and each agent processes only the messages addressed to it. This is closer to how microservices communicate. It's better for dynamically-composed workflows where you don't know upfront which agents will communicate. The downside is that debugging requires tracing the full message flow, and there's no single "state of the world" object you can inspect.

The blackboard pattern is a hybrid: there's a shared knowledge base (the "blackboard") that any agent can read from or write to, but agents post atomic facts rather than structured state objects. Each agent monitors the blackboard for facts that trigger its activation, adds its results, and goes idle. This is the most flexible but also the most complex to implement reliably, as you need conflict resolution when two agents write conflicting facts.

For most production systems, shared state (LangGraph's approach) is the right starting point — it's explicit, debuggable, and sufficient for 80% of multi-agent use cases. Switch to message passing only when you need loose coupling between agents that evolve independently.

### Q4: How do you avoid deadlock in a multi-agent system?

**Answer:** Deadlock occurs when two or more agents are each waiting for the other to complete before proceeding. Agent A is waiting for Agent B to return supplier data; Agent B is waiting for Agent A to return demand data first. Neither can proceed, and the system stalls forever. This is the classic circular dependency problem from concurrent programming, appearing in agent systems.

Prevention is far better than detection. The primary prevention technique is ensuring a clear dependency ordering: draw out the dependency graph of which agents need results from which other agents. If this graph has any cycles, you have a potential deadlock. Resolve cycles by restructuring the workflow: identify which direction the dependency should flow, add an intermediate step that breaks the cycle (e.g., a preliminary pass with estimated values), or collapse the two agents into one.

At the implementation level, every blocking wait must have a timeout. An agent waiting for another agent should not block indefinitely — it should have a maximum wait time (e.g., 30 seconds) after which it either proceeds with partial information, uses a cached/default value, or marks itself as failed. Timeouts convert infinite deadlocks into recoverable failures.

For dynamic multi-agent systems where you can't guarantee a cycle-free dependency graph at design time, implement a deadlock detector that periodically checks the state of all running agents. If any set of agents has been in a "waiting" state for more than N seconds with no progress, trigger an intervention: either abort and restart the stalled agents, inject a default value to break the wait, or escalate to a human operator. The key insight is that no multi-step distributed system can guarantee deadlock-freedom without timeouts — add them everywhere.

### Q5: When is a single agent better than multiple agents?

**Answer:** The honest answer is: almost always, a single agent is better, and you should only add agents when you've hit a specific, measurable wall. Multi-agent systems are architecturally elegant but practically expensive — every additional agent means additional latency (another LLM call), additional cost (more tokens), additional failure modes (more things that can go wrong), and additional debugging complexity (more state to inspect when something goes wrong).

A single agent with a well-designed system prompt and the right tool set can handle most real-world tasks. Even tasks that seem inherently multi-domain (analyze demand AND supply AND finance) can often be handled by one agent calling different tools in sequence, with a good system prompt providing the relevant expertise framing. The context window of modern models (up to 2 million tokens for Gemini 1.5 Pro) is large enough to hold the full context of most business tasks.

The cases where multi-agent genuinely wins are: parallelism requirements (you need to simultaneously query 5 different data sources and the latency of doing this sequentially is unacceptable), context window overflow (the inputs to the task literally cannot fit in one context window), domain isolation (you have 3 different LLMs fine-tuned for specific domains and want to route tasks to the right specialist), or organizational structure (different teams own different agents and they should evolve independently). If none of these specific conditions apply, use a single agent.

This is an important thing to say in an interview: showing you understand when NOT to use an advanced architecture is a strong signal. It demonstrates that you optimize for reliability and simplicity, not just technical sophistication.

## Key Points to Say in the Interview

- Supervisor/worker is the most common multi-agent pattern: coordinator decomposes goals, specialists execute, coordinator synthesizes
- LangGraph gives explicit, programmatic control over orchestration; CrewAI delegates coordination to an LLM manager — choose based on whether determinism matters
- Agents pass information via shared state (LangGraph), message passing (loosely coupled), or blackboard (shared knowledge base)
- Deadlock prevention: ensure no cycles in dependency graph AND add timeouts to every blocking wait
- Single agents are almost always simpler, faster, and cheaper — use multi-agent only when you've hit a specific measurable constraint
- When describing multi-agent, always mention the failure modes: partial failures, deadlocks, state explosion, debugging complexity

## Common Mistakes to Avoid

- Don't recommend multi-agent by default — this suggests you're optimizing for complexity over practicality
- Don't forget to mention communication patterns between agents — saying "they just talk to each other" shows shallow understanding
- Don't confuse LangGraph (state machine, programmatic) with CrewAI (role-playing, LLM-driven) — they're architecturally different
- Don't ignore deadlock prevention — treating it as "handled automatically" by the framework is incorrect
- Don't claim multi-agent always improves quality — poor orchestration actively degrades quality compared to a well-designed single agent

## Further Reading

- [LangGraph Multi-Agent Documentation](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/) — Official tutorial for supervisor/worker pattern in LangGraph
- [CrewAI Documentation](https://docs.crewai.com/concepts/crews) — How CrewAI models agents as a crew with roles and tasks
- [AutoGen: Enabling Next-Gen LLM Applications (Microsoft)](https://arxiv.org/abs/2308.08155) — Research paper on conversational multi-agent frameworks, good academic grounding
