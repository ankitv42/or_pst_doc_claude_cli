# Planning and Reasoning in AI Agents

## What Is It? (Plain English)

Most interesting tasks in the real world are not one-step. "Book me a flight to Paris next Tuesday" requires checking your calendar, searching flights, comparing prices, checking passport validity, and confirming payment — a sequence of decisions where each step depends on the results of the previous one. AI agent planning is the ability to decompose a complex goal into a sequence of sub-goals, decide in what order to pursue them, and adapt the plan as new information arrives.

The key insight is that language models are surprisingly capable planners when you ask them to "think aloud" before acting. When you prompt an LLM to write down its reasoning ("First I need to X, then I need to Y") before committing to an action, it makes dramatically better decisions than when asked to jump straight to the answer. This is the foundation of frameworks like ReAct (Reason + Act), which alternates reasoning steps with action steps in a structured way.

Planning fails when the goal is ambiguous, when the agent doesn't know what tools are available, when sub-tasks depend on each other in ways the model doesn't track, or when the model hallucinates a plausible-sounding but impossible plan. Understanding when planning works and when it breaks down is what separates a junior AI engineer from a senior one.

## How It Works

The ReAct framework is the most widely used planning pattern. It structures the agent's thinking as a loop of three phases:

```
ReAct Loop:

┌─────────────────────────────────────────────────────┐
│  Goal: "Find the cheapest flight from NYC to Paris   │
│         leaving next Tuesday, and book it if < $800" │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── THOUGHT ───────────────────────────────┐
│ "I need to know next Tuesday's date first, then    │
│  search for flights. I don't know today's date."   │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── ACTION ────────────────────────────────┐
│  Call tool: get_current_date()                     │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── OBSERVATION ───────────────────────────┐
│  Result: "2026-06-04"                              │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── THOUGHT ───────────────────────────────┐
│ "Next Tuesday is 2026-06-09. Now search flights."  │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── ACTION ────────────────────────────────┐
│  Call tool: search_flights(from="NYC", to="CDG",   │
│                            date="2026-06-09")       │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── OBSERVATION ───────────────────────────┐
│  Result: [{"airline": "Air France", "price": 742}, │
│           {"airline": "Delta", "price": 891}]       │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── THOUGHT ───────────────────────────────┐
│ "Air France at $742 is under $800. Book it."       │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── ACTION ────────────────────────────────┐
│  Call tool: book_flight(flight_id="AF-2091")        │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────── FINAL ANSWER ──────────────────────────┐
│ "Booked Air France flight AF-2091 for $742."       │
└───────────────────────────────────────────────────┘
```

## Why Google Cares About This

Google's production AI systems — from Google Assistant to Bard/Gemini to the agent pipelines in Google Cloud — must handle multi-step tasks reliably. Interviewers want to know whether a candidate understands why naive LLM calls fail for complex tasks, and what architectural patterns solve the problem. Discussing ReAct shows you understand that reasoning and action must be interleaved, not separated. Discussing when planning fails shows engineering maturity — you know the limits of the system you're building.

## Interview Questions & Answers

### Q1: Explain the ReAct framework. Why is it better than just asking the LLM to give you an answer directly?

**Answer:** ReAct stands for Reason + Act, and it was introduced in a 2022 paper by Yao et al. The core idea is dead simple: instead of asking a language model to jump from "user question" to "final answer" in one shot, you structure the interaction as an alternating sequence of thoughts (the model explains its reasoning), actions (the model calls a tool or takes a step), and observations (the result of the action is fed back). This loop continues until the model has enough information to produce a final answer.

The reason this outperforms direct answering is well-documented in the literature and comes down to two effects. First, explicit reasoning serves as a working memory scratchpad. Complex multi-step problems require tracking multiple pieces of state — what have I already discovered, what do I still need to know, what constraints apply. When forced to write this down as "Thought:" text, the model actually maintains this state across steps. When asked to answer directly, the context window fills with raw data and the model loses track. Second, interleaving reasoning with actions allows the plan to be adaptive. A model that writes out its plan in one shot before acting will stick to that plan even when early observations show it won't work. A ReAct agent writes one thought-action-observation at a time and revises its approach based on what it learns.

The practical implication for system design is that you need a loop structure in your orchestration code, not just a single API call. You call the LLM, parse whether its output contains a THOUGHT (continue), an ACTION (execute the tool and loop), or a FINAL ANSWER (return to user). This parser is the core of any ReAct agent implementation.

Where ReAct falls short is on tasks requiring simultaneous consideration of many alternatives. If you need to explore multiple approaches in parallel (try this path and that path, see which works), ReAct's sequential thought-action structure becomes inefficient. This is where Tree-of-Thought comes in as an extension.

### Q2: What is Tree-of-Thought, and when does it outperform chain-of-thought?

**Answer:** Chain-of-Thought (CoT) prompting asks the model to write its reasoning as a linear sequence: "Step 1... Step 2... Therefore the answer is..." It works well when the right path through a problem is relatively obvious once you slow down and think. Tree-of-Thought (ToT), introduced by Yao et al. in 2023, is for problems where you genuinely don't know which approach will work — you need to explore multiple paths simultaneously and prune the dead ends.

The analogy is solving a maze. Chain-of-thought is like walking carefully and thinking aloud as you go, but always committing to the current path. Tree-of-thought is like a bird's-eye view of the maze — you can mentally explore multiple branches, backtrack from dead ends, and choose the path that looks most promising. For most everyday tasks (answering questions, writing code for clear specs), CoT is sufficient and much cheaper. For tasks like game-playing, mathematical proof search, or planning when many sub-tasks have uncertain outcomes, ToT pays off.

In implementation, ToT requires generating multiple "thought branches" at each step — essentially calling the LLM multiple times with slightly different continuations and then using a value function (either another LLM call asking "how promising is this path?" or a programmatic heuristic) to decide which branches to continue and which to prune. This is significantly more expensive in both API calls and complexity.

The honest answer in an interview is: ToT is rarely used in production today because it's expensive and complex to implement reliably. Most production agents use CoT or ReAct. ToT is most valuable as a research paradigm that informs how to think about agent planning, and in very specific high-value use cases where quality dramatically outweighs cost (e.g., drug discovery, legal reasoning, strategic planning).

### Q3: How do you prevent an agent from getting stuck in an infinite planning loop?

**Answer:** Infinite loops in agent planning happen in two main patterns: the agent keeps calling tools and getting back results that don't help it make progress (searching the same query over and over because it can't find what it needs), or the agent gets into a circular dependency where completing step A requires information from step B which requires completing step A first.

The first line of defense is a hard step limit. Every production agent should have a maximum number of thought-action cycles before it gives up and returns a "could not complete" response with its current state. Ten to twenty steps covers nearly all real-world tasks — if you're still not done at step 30, something has gone wrong. This is not a hack; it's responsible system design.

The second defense is action deduplication detection. Keep a log of every (tool, arguments) pair called in the current session. Before executing a new tool call, check if the exact same call has been made before with the same arguments. If yes, that's a signal the agent is looping. Force a "meta-thought" step: inject a message saying "You already called this tool with these arguments and got [result]. Do not call it again. Reconsider your approach."

At the planning level, you can add a planning validation step before execution. Have a separate LLM call (or a rule-based checker) ask: "Does this plan have circular dependencies? Is every step achievable given the available tools?" For high-stakes agentic workflows, this pre-flight check is worth the extra latency.

Finally, consider whether the agent's goal decomposition was too ambitious. An agent asked to "fix all our customer service problems" has no clear termination condition. Good agent design requires goals that are specific, have defined success criteria, and have a finite number of steps. The planner is only as good as the goal it's given.

### Q4: What is the MRKL architecture and how does it relate to modern agent frameworks?

**Answer:** MRKL (pronounced "miracle") stands for Modular Reasoning, Knowledge, and Language, introduced by Karpas et al. at AI21 Labs in 2022. The key insight of MRKL was that a single LLM cannot and should not do everything — instead, you should have a "router" LLM that understands the user's question and decides which specialized module (a calculator, a database, a code interpreter, a knowledge base) should handle each sub-task. The LLM does reasoning and coordination; specialized systems do computation.

This is conceptually the grandparent of modern tool-calling. The difference is that in 2022, MRKL required explicit routing rules and the "modules" were separate trained models or databases. In 2024+, the same architecture is implemented through the tool-calling APIs we discussed — the LLM dynamically decides which tool to route to based on the tool descriptions, rather than following hardcoded routing logic.

Modern frameworks like LangChain, LangGraph, and CrewAI are all MRKL descendants. LangChain's "Agent" abstraction is essentially a MRKL router: LLM picks a tool, tool returns result, LLM picks next tool. LangGraph extends this into a full state machine where you can have conditional routing, loops, and human-in-the-loop pauses. CrewAI implements MRKL at the multi-agent level: multiple specialized "crew member" agents each handling a domain, coordinated by a manager.

The insight to take from MRKL into an interview is the principle of separation of concerns: use LLMs for what they're genuinely good at (language understanding, reasoning, flexible decision-making) and use specialized systems for what they're good at (arithmetic, database queries, real-time data). A good agent architecture is a hybrid system, not an LLM trying to do everything.

### Q5: When does chain-of-thought reasoning actually hurt performance?

**Answer:** Chain-of-thought prompting was a significant breakthrough, but research since 2022 has identified several conditions where it backfires. Understanding these failure modes is important for knowing when to use it and when to skip it.

The most significant case is simple factual lookups. If someone asks "What is the capital of France?", forcing the model to reason step-by-step ("First I should consider what type of question this is... France is a country in Europe... countries have capitals...") actually increases the chance of error and always increases latency. For simple retrieval tasks, CoT adds noise. The model's direct parametric knowledge is more reliable than a reasoned chain.

The second case is tasks where confident but wrong reasoning compounds the error. LLMs can produce very fluent, coherent reasoning chains that lead to the wrong answer — a phenomenon researchers call "confident hallucination." When the model writes out a multi-step argument that sounds completely reasonable but is based on a false premise in step 1, the final answer is wrong and the reasoning chain makes it appear authoritative. Without CoT, the wrong answer is at least clearly a direct claim that can be checked. With CoT, it's wrong AND has a plausible explanation attached, which can mislead users.

Third, CoT doesn't help much for tasks that are fundamentally about pattern recognition rather than reasoning — image classification, sentiment detection in obvious cases, well-formed code generation for common patterns. These tasks benefit more from few-shot examples of the desired output format than from step-by-step reasoning.

The practical rule: use CoT for tasks that genuinely require multi-step reasoning (math, logic puzzles, planning, code debugging), and skip it or use it lightly for lookup, classification, and generation tasks where the answer is more pattern than derivation.

## Key Points to Say in the Interview

- ReAct interleaves reasoning and acting — the thought serves as a working memory scratchpad, not just decoration
- The ReAct loop requires an orchestration layer that parses LLM output and routes to tool execution or final answer
- Tree-of-Thought is the right choice for search/planning with uncertain paths, but is expensive and rarely needed in production
- Always implement a hard step limit — agents that loop forever are a production incident waiting to happen
- MRKL is the conceptual ancestor of modern tool-calling agents — LLM coordinates, specialists execute
- Chain-of-thought can hurt on simple factual tasks and can make confident wrong answers harder to detect

## Common Mistakes to Avoid

- Don't describe planning as "just prompting the LLM to make a list" — that ignores the need for adaptive re-planning based on observations
- Don't say ReAct and chain-of-thought are the same thing — CoT is a single-pass reasoning technique; ReAct is a multi-step loop with tool calls
- Don't claim Tree-of-Thought is widely deployed — be honest that it's mostly a research paradigm
- Don't forget to mention loop termination conditions — infinite loops are a real production failure mode
- Don't ignore failure cases — always discuss when planning breaks down, not just when it works

## Further Reading

- [ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al., 2022)](https://arxiv.org/abs/2210.03629) — The original ReAct paper with benchmark comparisons
- [Tree of Thoughts: Deliberate Problem Solving with LLMs (Yao et al., 2023)](https://arxiv.org/abs/2305.10601) — Full ToT paper with game-of-24 and creative writing experiments
- [Lilian Weng's blog: LLM-powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/) — Comprehensive overview of planning, memory, and tool use in agent systems
