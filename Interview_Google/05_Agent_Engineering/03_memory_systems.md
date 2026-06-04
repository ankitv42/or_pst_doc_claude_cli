# Memory Systems in AI Agents

## What Is It? (Plain English)

A person's ability to do useful work depends on multiple kinds of memory working together: the handful of things you're holding in mind right now (working memory), the facts and procedures you learned long ago and carry everywhere (long-term memory), the episodic record of what happened in past conversations (episodic memory), and the skill library of how to do things (procedural memory). AI agents have direct analogies to all four, and choosing the right memory architecture for a given use case is one of the most consequential design decisions in agent engineering.

The core constraint that makes memory design non-trivial is the context window. Every LLM can only "see" a fixed amount of text at once — currently between 8,000 and 2 million tokens depending on the model. Everything the agent needs to know in order to act must fit within this window at inference time. But agents that operate over long sessions, handle large documents, or need to remember past users will quickly exhaust any context window. Memory systems are the engineering solution to this fundamental constraint.

Getting memory wrong is expensive. Too little memory and the agent asks users the same questions repeatedly, fails to personalize, and makes decisions without relevant context. Too much memory in context and you waste tokens, increase latency, and can confuse the model with irrelevant information from old sessions. The right answer is always "the minimum memory needed for the current task, retrieved just-in-time."

## How It Works

The four memory types and their technical implementations:

```
┌─────────────────────────────────────────────────────────────────┐
│                   AI AGENT MEMORY TAXONOMY                       │
├──────────────────┬──────────────────────────────────────────────┤
│ Memory Type      │  What It Is / Where It Lives                  │
├──────────────────┼──────────────────────────────────────────────┤
│ 1. In-Context    │  The active conversation history.             │
│   (Short-Term)   │  Lives in the prompt/messages array.          │
│                  │  Capacity: 8K–2M tokens. Forgotten at         │
│                  │  session end.                                  │
├──────────────────┼──────────────────────────────────────────────┤
│ 2. External      │  Facts stored in a vector DB (ChromaDB,       │
│   (Long-Term)    │  Pinecone, Weaviate) or SQL/NoSQL.            │
│                  │  Retrieved via semantic search.               │
│                  │  Capacity: Unlimited. Persists forever.       │
├──────────────────┼──────────────────────────────────────────────┤
│ 3. Episodic      │  Logs of past sessions/interactions.          │
│   (History)      │  What happened, what was decided, what        │
│                  │  worked. Stored in DB, retrieved by           │
│                  │  relevance or recency.                         │
├──────────────────┼──────────────────────────────────────────────┤
│ 4. Procedural    │  The agent's tools, skills, and sub-agents.   │
│   (Skills)       │  Stored as code / tool schemas / system       │
│                  │  prompt instructions.                          │
│                  │  "Knowing how to do things" vs "knowing facts"│
└──────────────────┴──────────────────────────────────────────────┘

Memory Access Flow:
                    ┌───────────────┐
                    │  User Request │
                    └───────┬───────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
  │   Retrieve   │ │   Retrieve   │ │   Load       │
  │   External   │ │   Episodic   │ │   Procedural │
  │   Memory     │ │   Memory     │ │   Skills     │
  │ (vector DB)  │ │  (past logs) │ │  (tools)     │
  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
         │                │                │
         └────────────────┼────────────────┘
                          ▼
               ┌────────────────────┐
               │  Assemble Context  │
               │  (In-Context       │
               │   Memory)          │
               └─────────┬──────────┘
                         │
                         ▼
               ┌────────────────────┐
               │    LLM Call        │
               └────────────────────┘
```

## Why Google Cares About This

Memory architecture is a production engineering challenge that separates toys from systems. Google's AI products (Assistant, Bard/Gemini, Workspace AI) must personalize across sessions, handle documents far larger than any context window, and avoid the "goldfish" problem where the agent forgets context from 10 messages ago. Interviewers test this because candidates who don't understand memory types will over-stuff context windows, under-use vector retrieval, and build agents that degrade in performance as sessions grow. It also connects directly to cost — unnecessary tokens in context are expensive at Google scale.

## Interview Questions & Answers

### Q1: Walk me through the four types of agent memory and give a concrete use case for each.

**Answer:** In-context memory is everything currently in the LLM's prompt — the system message, conversation history, retrieved documents, tool results. It's the agent's working memory: fast, always available, but temporary (lost at session end) and capped by the context window. A concrete use case is a customer service agent that remembers everything said in the current chat session: the customer's complaint, the ticket number, what solutions were tried. All of this fits in context for a single session. When the session ends, in-context memory is gone.

External memory is information stored outside the model and retrieved on demand, typically using a vector database like ChromaDB, Pinecone, or Weaviate. You embed documents as vectors (numerical representations of meaning), store them, and at query time embed the user's question and find the most semantically similar documents. A concrete use case is a knowledge base agent for a legal firm: 10,000 contracts are stored as vectors. When a lawyer asks "find all contracts with force majeure clauses," the agent embeds the query, retrieves the 5 most relevant contract sections, and puts them in context. Only the relevant portions — not all 10,000 contracts — enter the LLM's context window.

Episodic memory is a log of what happened in past sessions — what the user asked, what the agent did, what the outcomes were. Unlike external memory (general facts), episodic memory is session-specific history. A concrete use case is a personal AI assistant: you told the assistant last week that you prefer morning meetings and hate PDF reports. Those preferences were stored as episodic memories. When you schedule a meeting today, the assistant retrieves relevant past preferences and applies them without asking again.

Procedural memory is the agent's repertoire of skills — what it knows how to do rather than what it knows about. This is implemented as the tool schemas, sub-agent definitions, and system prompt instructions. A concrete use case is the set of capabilities baked into the agent at build time: "I know how to call the flights API," "I know how to query the expense database," "I know the company's approval workflow." These don't change per user; they're the fixed skills of the agent.

### Q2: How does a vector database work, and why is it used for agent memory rather than a regular SQL database?

**Answer:** A vector database stores data as high-dimensional numerical vectors (typically 384 to 1536 dimensions) rather than rows and columns. When you add a document to the database, you first pass it through an embedding model (like `nomic-embed-text` or `text-embedding-3-small`) which converts the text into a vector — a list of floating-point numbers where the spatial position of the vector encodes the semantic meaning of the text. Documents about similar topics end up as vectors that are geometrically close to each other in this high-dimensional space.

When you want to retrieve relevant memories, you embed your query using the same embedding model, getting a query vector. Then you ask the database: "which stored vectors are nearest to this query vector?" using a distance metric like cosine similarity or dot product. The nearest neighbors are the most semantically relevant documents, regardless of whether they share exact keywords with the query. This is why it's called "semantic search" — it finds meaning-similar documents rather than keyword-matching documents. SQL's `WHERE clause LIKE '%force majeure%'` would only find exact keyword matches and miss synonyms, paraphrases, or related concepts.

For agent memory, the semantic search property is critical because users don't always phrase queries the same way the memory was stored. A user who said "I hate PDF reports" last week might this week trigger retrieval with "what are my reporting preferences?" — no keyword match but high semantic similarity. SQL would miss this; a vector database retrieves it.

The practical tradeoff: vector databases are excellent for unstructured text retrieval but bad for precise structured queries ("show me all orders over $1000 placed in Q3 2025"). For those, SQL is better. Most production agents use both: vector DB for semantic memory retrieval, SQL for structured operational data.

```
SQL Memory:                          Vector Memory:
"Find memories about Paris"          "Find memories about traveling to France"
                                      (returns: Paris trip, Nice vacation, CDG
WHERE text LIKE '%Paris%'             airport layover — because they're
→ Finds exact word "Paris"            semantically similar to "France travel")
→ Misses: "I visited CDG last year"
→ Misses: "My Eiffel Tower photos"
```

### Q3: What is memory compression, and why does every production agent need it?

**Answer:** Memory compression is the process of reducing the size of stored conversation history while preserving the most important information — essentially summarizing as you go rather than keeping a full verbatim transcript. Every production agent needs it because context windows are finite, and long-running agents or users with deep conversation histories will eventually exceed the context limit if you store everything.

The simplest approach is rolling window compression: keep only the last N messages verbatim (e.g., the last 20 messages), and for older messages, run a summarization LLM call to produce a compact summary paragraph. The summary replaces the old messages in context. This is what OpenAI's ChatGPT does internally. The risk is information loss — summaries discard details that might be needed later. A conversation about a customer's exact contract terms might get summarized as "discussed contract" and lose the specific clauses.

A more sophisticated approach is hierarchical compression: recent messages stay verbatim, slightly older messages are compressed into per-topic summaries, and very old content is distilled into user preferences and key facts. Think of it as: "short-term verbatim" → "medium-term summaries" → "long-term extracted facts." This matches how human working memory actually works — you remember exactly what was said in the last 5 minutes, have a general memory of the last hour, and carry only key facts from last year.

For agents that work on discrete tasks (one task = one session), compression is less urgent — each task starts fresh. But for persistent personal assistants, long-running business processes, or agents that learn from every user interaction, compression is not optional. Without it, the agent either breaks (context overflow) or degrades (so much context that relevant information drowns in noise). Implementing compression is a significant engineering investment, but it's what makes agents feel like they have a genuine ongoing relationship with users rather than starting fresh every time.

### Q4: How do you decide which information to store in external memory vs keep in the system prompt?

**Answer:** The system prompt contains information that is always relevant for every interaction with this agent — its persona, standing instructions, policies, and capability definitions. External memory contains information that is only sometimes relevant, retrieved when a query matches. The rule of thumb is: if you'd want it in context for 80%+ of queries, put it in the system prompt. If it's only relevant for specific queries, put it in external memory and retrieve it dynamically.

Consider a customer service agent for a software company. The system prompt should contain: the agent's persona ("You are a friendly support agent for Acme Corp"), the general policy ("escalate billing questions to level 2"), and the list of available tools. What should NOT be in the system prompt: the full 500-page product manual, the complete list of known bugs, every customer's account history. These belong in external memory because only a small subset is relevant for any given query.

A common mistake is trying to cram too much into the system prompt for "safety" — "I'll just include everything so the model always has it." This creates two problems. First, very long system prompts reduce the model's attention to any specific part of it (attention dilution). Second, irrelevant information in context actively increases hallucination rates because the model might confusingly blend irrelevant content with its answer. Retrieval-augmented generation (RAG) exists precisely to solve this — you inject only what's needed, when it's needed.

The practical test: write your system prompt, then for each piece of information ask "would this be useful for a simple greeting message?" If no, it probably belongs in external memory. If yes, it belongs in the system prompt.

### Q5: What is the difference between episodic memory and external memory? When would you use each?

**Answer:** The distinction is about the nature of the information. External memory is a knowledge base — documents, facts, policies, reference material that exist independently of any specific user or conversation. A company's product catalog, legal contracts, research papers — this is external memory. It answers questions like "what does our return policy say?" Episodic memory is history — what happened in past sessions, what a specific user did, what decisions were made in past runs. It answers questions like "what did this user ask about last Tuesday?" or "in the last 10 agent runs, which ones ended in escalation?"

Use external memory when you have a corpus of reference material that multiple users or sessions will query, and when the relevant information should be retrieved based on semantic similarity to the current query. A medical chatbot's external memory is the clinical guidelines database. A coding assistant's external memory is the documentation corpus. External memory is static or slowly-changing and shared across users.

Use episodic memory when you need personalization — when the agent's behavior for user A should differ from user B based on their history. A personal finance assistant should remember that User A is saving for a house down payment. A project management agent should remember what decisions were made in previous project meetings. Episodic memory is per-entity (per user, per project, per workflow instance) and is write-heavy — you're constantly adding new episodes as time passes.

In many production systems, you use both: external memory for shared knowledge (product catalog, policies) and episodic memory for user-specific context (preferences, history). The key is to keep them separate so you can manage each appropriately — external memory benefits from periodic bulk re-indexing as documents change; episodic memory benefits from recency-weighted retrieval (more recent episodes are usually more relevant than older ones).

## Key Points to Say in the Interview

- The four memory types are: in-context (current session), external/vector (retrieved knowledge), episodic (session history), procedural (skills/tools)
- Vector databases find semantically similar documents, not just keyword matches — this is why they're used for agent memory
- Memory compression (summarization as you go) is required for long-running agents — context windows are finite
- System prompts hold always-relevant information; external memory holds sometimes-relevant information retrieved on demand
- Episodic memory enables personalization across sessions; external memory enables knowledge grounding
- The goal is minimum memory needed for the current task, retrieved just-in-time — not cramming everything into context

## Common Mistakes to Avoid

- Don't conflate in-context memory with the entire memory system — in-context is just one type, and it's the most temporary
- Don't say "I'll just use RAG for everything" without explaining the retrieval mechanism and when RAG is not the right tool
- Don't ignore memory compression — saying "just extend the context window" is not an answer; very long contexts degrade quality and cost more
- Don't confuse episodic and external memory — they serve different purposes (history vs knowledge)
- Don't forget procedural memory — "what the agent can do" is as important as "what the agent knows"

## Further Reading

- [Lilian Weng: LLM-powered Autonomous Agents (Memory section)](https://lilianweng.github.io/posts/2023-06-23-agent/#memory) — Best technical overview of the four memory types with citations
- [ChromaDB Documentation](https://docs.trychroma.com/) — Hands-on intro to vector databases in Python, the most common tool for agent memory
- [MemGPT: Towards LLMs as Operating Systems (Packer et al., 2023)](https://arxiv.org/abs/2310.08560) — Research paper on virtual memory paging for LLM agents, highly relevant to memory compression
