# Multi-Agent Systems

## What Is It? (Plain English)

A multi-agent system is an architecture where multiple AI agents collaborate to solve a problem that would be too complex, too large, or too specialized for a single agent to handle alone. Think of it like a consulting firm: rather than one generalist consultant trying to do market research, financial modeling, and technical due diligence simultaneously, you bring in specialized teams — a strategy team, a finance team, a technical team — who each do their part and then hand off to each other. The engagement manager coordinates everyone and ensures the final deliverable is coherent. In multi-agent AI systems, these roles are played by specialized LLM-powered agents.

The key architectural question in multi-agent design is coordination: who decides what each agent does, and how do agents share information with each other? There are two dominant patterns. In the **orchestrator-worker** pattern, a central "supervisor" agent receives the task, breaks it into subtasks, delegates to specialized worker agents, receives their outputs, and assembles the final result. In the **peer-to-peer** pattern, agents communicate directly with each other, with no central coordinator — more resilient but harder to reason about. Most production systems use the orchestrator-worker pattern because it's more predictable and debuggable.

Why not just use one big, powerful agent? Three reasons. First, a single agent accumulates context across all its steps until it overflows the context window — multiple agents have independent context windows. Second, specialized agents can be smaller, faster, and cheaper than a general-purpose agent — an agent that only writes SQL doesn't need to understand literature or generate images. Third, agents can run in parallel — instead of doing research, then analysis, then writing sequentially, you can do research and data gathering simultaneously, halving the total time. These benefits come at the cost of complexity: you now need to design inter-agent communication, failure handling, and state consistency across multiple agents.

## How It Works

```
═══════════════════════════════════════════════════════════════
            ORCHESTRATOR-WORKER PATTERN
═══════════════════════════════════════════════════════════════

User Task: "Analyze competitor pricing and write a report"
        │
        ▼
┌───────────────────────────────────────────┐
│           ORCHESTRATOR AGENT              │
│  • Receives high-level task               │
│  • Decomposes into subtasks               │
│  • Assigns to appropriate workers         │
│  • Monitors completion                    │
│  • Handles failures / retries             │
│  • Assembles final output                 │
└──────────┬──────────────┬─────────────────┘
           │              │
      ┌────▼────┐    ┌────▼──────┐    ┌─────────────┐
      │Research │    │  Data     │    │  Writing    │
      │ Agent   │    │ Analysis  │    │  Agent      │
      │         │    │  Agent    │    │             │
      │• Web    │    │• Calc.    │    │• Report     │
      │  search │    │• Charts   │    │  drafting   │
      │• Scrape │    │• Stats    │    │• Formatting │
      └────┬────┘    └────┬──────┘    └──────┬──────┘
           │              │                  │
           └──────────────▼──────────────────┘
                    Shared State / Message Bus
                    (LangGraph StateGraph, CrewAI tasks)

═══════════════════════════════════════════════════════════════
            LANGGRAPH STATE MACHINE APPROACH
═══════════════════════════════════════════════════════════════

    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Node A  │───►│  Node B  │───►│  Node C  │
    │(Agent 1) │    │(Agent 2) │    │(Agent 3) │
    └──────────┘    └──────────┘    └──────────┘
         │               │               │
         └───────────────▼───────────────┘
                    Shared State Dict
              {inventory_data, analysis, decision}
                    (passed through graph)

    Conditional edges:
    Node B ──► Node C  (if confidence > 0.8)
    Node B ──► Node A  (if more data needed, loop back)
    Node B ──► HITL    (if human approval required)
```

## Why Google Cares About This

Google's AI products increasingly rely on multi-agent architectures — Gemini's multimodal reasoning, the AI co-scientist announced in 2024, Google's Vertex AI Agent Builder. At scale, any complex AI task benefits from decomposition into specialized, parallelizable agents. Google interviewers probe multi-agent knowledge to test whether candidates can reason about distributed system concerns (state consistency, failure handling, communication patterns) applied to probabilistic AI systems — a genuinely difficult intersection. The candidate who can explain LangGraph vs CrewAI architecturally, describe how to handle inter-agent communication failures, and quantify when multi-agent adds value vs. overhead is demonstrating exactly the kind of production-ready thinking Google values.

## Interview Questions & Answers

### Q1: What are the main architectural patterns for multi-agent systems, and when do you use each?

**Answer:** There are three primary coordination patterns in multi-agent systems, each with distinct tradeoffs in terms of reliability, flexibility, and observability.

**Orchestrator-Worker (Hub and Spoke)**: A central orchestrator agent receives the goal, plans the approach, delegates specific subtasks to specialized worker agents, collects their outputs, and synthesizes the final result. This is the most common production pattern because it's highly predictable — the orchestrator is the single source of truth for task state, making the system easy to monitor, debug, and control. The failure mode is the orchestrator itself becoming a bottleneck or single point of failure; if the orchestrator's LLM call produces a bad plan, all worker outputs may be wasted. LangGraph implements this with a supervisor node that routes to worker subgraphs. CrewAI's "sequential process" is also an orchestrator pattern.

**Peer-to-Peer (Decentralized)**: Agents communicate directly with each other without a central coordinator. Agent A completes its task and directly triggers Agent B, which may trigger Agent C or loop back to Agent A. This is more resilient (no single point of failure), enables more complex non-linear workflows, but is significantly harder to reason about and debug. What's the current system state? Which agent is responsible for error recovery? These questions are harder to answer without a central orchestrator. AutoGPT-style systems lean toward this pattern.

**Hierarchical (Multi-level)**: Combines the above — a top-level orchestrator delegates to mid-level coordinators, each of which manages a team of worker agents. This mirrors large human organizations (VP → Manager → Individual Contributor) and is appropriate for very complex tasks where the decomposition itself is too complex for a single orchestrator. The downside is significant communication overhead and latency at each level.

**When to use each:**
- Simple, linear pipelines (do A, then B, then C): orchestrator-worker
- Complex tasks with many interdependencies: hierarchical
- Tasks where resilience is paramount and the workflow can be expressed as a DAG: peer-to-peer with a message bus
- Real-time, user-facing tasks: orchestrator-worker for predictability

The practical guidance: start with orchestrator-worker. Move to hierarchical only when a single orchestrator's reasoning becomes too complex (> 5-7 concurrent workers). Avoid pure peer-to-peer unless you have a strong reason and robust monitoring.

### Q2: How does LangGraph differ from CrewAI architecturally, and when would you choose one over the other?

**Answer:** LangGraph and CrewAI represent two fundamentally different mental models for multi-agent systems — LangGraph thinks like a distributed systems engineer, CrewAI thinks like a product manager.

**LangGraph** is a state machine framework. You define agents as nodes in a directed graph, define the state (a typed dict) that flows through the graph, and define edges as conditions that determine which node executes next. The framework is explicit and code-first: you write Python to define exactly what happens at each node and under what conditions each edge is traversed. This gives you fine-grained control over execution flow, enables complex conditional routing (e.g., "if confidence < 0.7, loop back to the research node"), and provides built-in support for persistence and resumability via checkpointers. The mental model is: a deterministic state machine where nodes happen to be LLM calls.

**CrewAI** abstracts over the state machine and lets you define agents in terms of their role, goal, and backstory, and tasks in terms of description and expected output. You specify which agent handles which task and how tasks are sequenced. CrewAI then orchestrates the execution automatically. This is faster to prototype — you can define a 3-agent crew in 20 lines of code — but gives you less control over the execution graph. Debugging is harder because the orchestration logic is inside the framework, not in your code.

**Key technical differences:**
- **State management**: LangGraph gives you explicit, typed state; CrewAI manages state internally and passes context between tasks via text.
- **Parallelism**: LangGraph has explicit parallel execution support (fork/join in the graph); CrewAI's async task execution is less controllable.
- **Human-in-the-loop**: LangGraph has first-class support via `interrupt_before` and graph checkpointing; CrewAI has basic callbacks.
- **Debugging**: LangGraph's graph structure is inspectable; you can visualize the graph and replay from any checkpoint. CrewAI's execution is more opaque.

**When to choose:**
- Choose **LangGraph** when: the workflow is complex with non-linear routing; you need HITL; you need resumability from failure; you need fine-grained observability; the system will run in production at scale.
- Choose **CrewAI** when: you're prototyping; the task has a clear sequential/hierarchical structure; you want agents to feel like "teammates" rather than state machine nodes; the team has less engineering depth.

In production, LangGraph is the more robust choice. CrewAI is better for rapid prototyping and use cases where the simplicity tradeoff is worth it.

### Q3: How do agents share state in a multi-agent system, and what are the consistency challenges?

**Answer:** State sharing is the fundamental engineering challenge of multi-agent systems — it's where most production failures occur. Agents need to read shared information (the current task state, results from other agents, the user's original request) and write their outputs in a way that other agents can reliably consume. There are three patterns.

**Immutable message passing**: Agents don't share mutable state; instead, each agent receives a message, processes it, and emits a new message. The state is implicit in the message chain. This is the cleanest pattern for reasoning about correctness — no agent can corrupt another's state because they don't share state. The downside is that large intermediate results must be passed by value, increasing communication overhead. LangGraph uses a variant of this: each node receives the current state dict and returns a dict of updates, which are merged into the shared state.

**Shared mutable state (blackboard pattern)**: All agents read from and write to a shared state store (Redis, a database, an in-memory dict). This is flexible but requires careful concurrency control. If two agents try to write to the same field simultaneously, you get race conditions. In a synchronous pipeline (Agent 1 finishes before Agent 2 starts), this isn't a problem. In a parallelized pipeline, you need locks or atomic compare-and-swap operations. LangGraph handles this by serializing state updates through the graph execution engine.

**Structured message bus**: Agents communicate through a typed message bus (Kafka, RabbitMQ, or a simple in-process queue). Agents publish events ("research_complete", "analysis_ready") and subscribe to the events they care about. This is the most decoupled pattern — agents don't need to know about each other, only about the messages they produce and consume. It's also the most complex to implement and debug.

**Consistency challenges specific to multi-agent AI:**
- **LLM non-determinism**: Even with the same input, Agent 2's LLM call might produce different output on retry. If Agent 3 already consumed Agent 2's first output, what happens when Agent 2 is retried? You need to decide: does Agent 3 re-run with the new output, or do you keep the original result?
- **Context contamination**: If agents share too much context (e.g., Agent 1's full reasoning trace passed to Agent 2), Agent 2's LLM can be influenced by Agent 1's conclusions rather than reasoning independently. This is sometimes desired (agents should build on each other's work) and sometimes not (independent validation requires isolation).
- **Partial failures**: If Agent 2 of 4 fails, what's the recovery strategy? Re-run only Agent 2 (requires checkpointing from the output of Agent 1); re-run from the beginning (expensive); propagate the failure to the output (user gets a partial result). LangGraph's checkpointing enables the first strategy — retry from the failed node with the state preserved up to that point.

### Q4: When does a multi-agent system make things worse instead of better?

**Answer:** Multi-agent architectures are fashionable and it's easy to over-apply them. There are specific situations where adding multiple agents increases costs, latency, and failure modes without any quality benefit, and being able to articulate this demonstrates engineering maturity.

**When multi-agent makes things worse:**

**The task is simple enough for one agent**: If the task can be accomplished within a single context window without exceeding the model's reasoning capacity, a single agent is strictly better — less latency (fewer LLM calls), less cost (fewer tokens), less failure surface area. A multi-agent RAG system that uses one agent to retrieve and another to generate, when these can be done in one step, just adds overhead.

**Latency is critical and the task is sequential**: Multi-agent systems add coordination overhead — each agent handoff requires a message, often an LLM call by the orchestrator to route and synthesize. If tasks must be done sequentially (Agent 2 can't start until Agent 1 finishes), the total latency is the sum of all agent latencies plus coordination overhead. For real-time user-facing applications, this overhead may be unacceptable.

**The inter-agent communication bandwidth is high**: If Agent 1 produces a 50,000-word document that Agent 2 needs in its entirety to do its job, passing this between agents is expensive and may exceed context windows. Sometimes a single long-context model is better than a pipeline of smaller models.

**The task requires tight coupling between steps**: Some tasks have tight feedback loops where the decision in step N depends on tentative results from step N+1. Multi-agent systems create synchronization barriers that make tight coupling expensive. Single-agent ReAct loops handle this naturally.

**You can't debug or monitor it**: Multi-agent systems with opaque inter-agent communication are a debugging nightmare. If you don't have the tooling to trace a request through multiple agents, capture each agent's inputs and outputs, and replay from any point, you will not be able to improve the system or diagnose production failures. Don't build multi-agent systems you can't observe.

The test: "Would a thoughtful single-agent with access to all the same tools solve this problem well?" If yes, use a single agent. Use multi-agent only for tasks that are demonstrably too large (context overflow), too complex (beyond single-agent reasoning), or too slow without parallelism.

### Q5: How do you handle failures in a multi-agent pipeline?

**Answer:** Failure handling in multi-agent systems is substantially harder than in traditional software because failures can be partial (some agents succeed, some fail), non-deterministic (the same input might fail 20% of the time), and subtle (the agent completes but produces incorrect output). A robust failure handling strategy has to address all three categories.

**Categorical retry logic**: Not all failures are equal. LLM API rate limit errors (HTTP 429) should be retried with exponential backoff — the LLM service is temporarily overloaded. LLM context window exceeded errors (HTTP 400) should not be retried — retrying with the same input will fail again; you need to reduce the input size. LLM content policy violations should not be retried — the input itself is the problem. Agent logic errors (the agent produced malformed output) require a different retry strategy — retry with a more constrained prompt or route to a fallback agent. Encode these distinctions in your retry logic rather than blindly retrying all failures.

**Checkpoint-based recovery**: Using LangGraph's checkpointing, every agent's output is persisted to the checkpoint store before the next agent runs. If Agent 3 fails, you can resume from the output of Agent 2, skipping Agents 1 and 2 on the retry. This is the correct strategy for expensive, long-running pipelines where re-running from the beginning is costly. The checkpoint store must be durable (written to disk or a database, not just in-memory) to survive process restarts.

**Graceful degradation**: Design the pipeline to produce useful partial results when one agent fails. In ORCA's pipeline, if Agent 1's CrewAI sub-crew fails (which it does regularly due to the Groq `cache_breakpoint` bug), Agent 1 falls back to a raw-data summary. The pipeline continues with a degraded but functional Agent 1 output rather than failing entirely. This requires defining a "minimum viable output" for each agent and implementing fallback logic.

**Failure isolation**: An agent that fails catastrophically (throws an unhandled exception, consumes all available memory) should not bring down the entire pipeline. Run agents in separate threads or processes with timeouts and resource limits. In distributed deployments, run agents as separate microservices with circuit breakers between them.

**Alerting and observability**: Every agent failure should emit a structured log event with the agent ID, input state, error type, and stack trace. Set up alerts on agent failure rates — if Agent 2 fails > 5% of the time, that's a signal of a systematic problem (model instability, input distribution shift) that needs investigation. Don't just retry silently; log every retry attempt and the eventual outcome.

## Key Points to Say in the Interview

- Name the **three coordination patterns**: orchestrator-worker, peer-to-peer, hierarchical — and match them to use cases
- Know **LangGraph vs CrewAI** architecturally: LangGraph is explicit state machine, CrewAI is role-based abstraction
- Explain **why multi-agent sometimes makes things worse**: latency overhead, debugging difficulty, cost
- Know the **three state-sharing patterns**: immutable messages, shared mutable state, message bus
- Mention **consistency challenges** specific to LLMs: non-determinism on retry, context contamination
- Advocate for **checkpoint-based recovery** for long-running pipelines
- Say "principle of least privilege" for agent permissions — agents should only have access to what they need

## Common Mistakes to Avoid

- Saying multi-agent is always better than single-agent — demonstrate you understand the **cost-benefit tradeoff**
- Confusing **LangGraph and LangChain** — LangGraph is the graph/agent framework; LangChain is the broader toolkit
- Not mentioning **observability** — multi-agent systems without tracing are unmaintainable
- Treating all agent failures the same — distinguish **retryable vs non-retryable** failures
- Forgetting that **agents run LLM calls** — each agent is not free; cost compounds with every agent added

## Further Reading

- [LangGraph: Building Stateful Multi-Actor Applications](https://langchain-ai.github.io/langgraph/) — Official LangGraph documentation with multi-agent patterns
- [CrewAI Documentation](https://docs.crewai.com/) — Official CrewAI docs explaining the role/task/crew paradigm
- [Lilian Weng — LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/) — Deep dive on multi-agent architectures, planning, and memory
