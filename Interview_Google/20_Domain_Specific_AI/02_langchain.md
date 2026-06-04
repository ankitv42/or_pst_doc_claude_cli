# LangChain: Building Blocks for LLM Applications

## What Is It? (Plain English)

LangChain is a Python framework that provides standardised building blocks for LLM applications — connectors to dozens of LLM providers, document loaders, text splitters, vector store clients, retrievers, output parsers, and tool calling utilities. Its core value is abstraction: instead of writing provider-specific code for OpenAI, then rewriting it for Anthropic, then again for Groq, you write to LangChain's common interface and swap providers by changing one line.

The framework evolved significantly. Early LangChain (before 2023) used a "Chain" abstraction — `LLMChain`, `RetrievalQAChain` — that was monolithic and hard to customise. Modern LangChain uses LCEL (LangChain Expression Language), a pipe-based composition syntax (`prompt | llm | parser`) that is more readable, more composable, and supports streaming and async natively.

LangChain and LangGraph are complementary, not competing. LangGraph uses LangChain's LLM abstractions, output parsers, and tool definitions. Think of LangChain as the components library and LangGraph as the orchestration framework that connects those components in stateful, non-linear workflows.

## How It Works

```
LANGCHAIN COMPONENT MAP
═══════════════════════════════════════════════════════════════════
Input → [LLM] → Output

Each bracket is a LangChain component:

Document Loaders    → read PDFs, web pages, databases
Text Splitters      → chunk documents for embedding
Embeddings          → convert text to vectors
Vector Stores       → store and search vectors (ChromaDB, Pinecone)
Retrievers          → wrap vector stores with retrieval logic
Prompts             → PromptTemplate, ChatPromptTemplate
LLMs                → ChatOpenAI, ChatGroq, ChatAnthropic, ChatVertexAI
Output Parsers      → StrOutputParser, PydanticOutputParser, JsonOutputParser
Tools               → @tool decorator, Tool class

LCEL PIPE SYNTAX:
─────────────────────────────────────────────────────────────────
# Simple chain:
chain = prompt | llm | output_parser

# RAG chain:
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# Invoke:
result = chain.invoke("What is the reorder policy for Class A SKUs?")

# Stream:
for chunk in chain.stream("What is..."):
    print(chunk, end="", flush=True)

# Async:
result = await chain.ainvoke("What is...")
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

LangChain is the most widely used Python framework for LLM application development. Most ML engineers joining Google will encounter existing LangChain code in their first week. Understanding LCEL composition, output parsers, and the tool calling interface is a baseline expectation for anyone doing applied AI engineering. More importantly, LangChain's abstractions directly map to concepts Google cares about: provider-agnosticism (write code that works across Google's LLM portfolio — Gemini, PaLM, custom models), structured output generation, and retrieval-augmented generation.

## Interview Questions & Answers

### Q1: Explain LCEL (LangChain Expression Language). What problems does it solve compared to the old Chain classes?

**Answer:** LCEL is LangChain's pipe-based composition syntax for building LLM workflows. The key concept is `Runnable` — every component in LangChain implements a `Runnable` interface with `.invoke()`, `.stream()`, `.batch()`, and `.ainvoke()`. The pipe operator `|` chains Runnables together, creating a new Runnable.

The old Chain classes (`LLMChain`, `RetrievalQAChain`) were monolithic — they had specific, opinionated ways of handling prompts, memory, and output parsing. Customising them required subclassing and overriding methods. Adding streaming required understanding Chain-specific callback mechanisms.

LCEL solves this by being composable from first principles:

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from pydantic import BaseModel

# Old way (LLMChain — verbose, opinionated, hard to customise)
from langchain.chains import LLMChain
chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run(question="What is...?")

# New way (LCEL — composable, explicit, flexible)
prompt = ChatPromptTemplate.from_template("Answer this: {question}")
llm = ChatGroq(model="llama-3.1-8b-instant")
parser = StrOutputParser()

chain = prompt | llm | parser
result = chain.invoke({"question": "What is...?"})

# Streaming is built in — same chain
for chunk in chain.stream({"question": "What is...?"}):
    print(chunk, end="")

# Async is built in — same chain
result = await chain.ainvoke({"question": "What is...?"})

# Structured output with Pydantic
class DemandAnalysis(BaseModel):
    urgency: str
    trend: str
    narrative: str

parser = PydanticOutputParser(pydantic_object=DemandAnalysis)
chain = prompt | llm | parser
analysis: DemandAnalysis = chain.invoke({"question": "..."})
print(analysis.urgency)   # type-safe
```

LCEL's other advantage: because every component is a Runnable, you can compose them arbitrarily. A retriever is a Runnable. A vector store is a Runnable. A custom function wrapped in `RunnableLambda` is a Runnable. This uniformity makes building complex RAG pipelines much cleaner.

---

### Q2: How does LangChain's tool calling work? What is the @tool decorator and how does it differ from MCP tools?

**Answer:** LangChain provides the `@tool` decorator to define tools that an LLM can be instructed to call. The decorator inspects the function signature and docstring to generate a JSON schema that the LLM receives as part of its context, telling it what tools are available and what arguments they take.

```python
from langchain_core.tools import tool
from typing import Annotated

@tool
def get_inventory_level(
    sku_id: Annotated[str, "The SKU identifier to check inventory for"]
) -> dict:
    """Get the current inventory level, reorder point, and days of stock for a SKU."""
    return db_queries.get_sku_data(sku_id)

@tool
def get_supplier_lead_time(
    sku_id: Annotated[str, "The SKU identifier"],
    order_type: Annotated[str, "standard, partial, or expedite"]
) -> int:
    """Get the lead time in days for a given SKU and order type."""
    return db_queries.get_lead_time(sku_id, order_type)

# Bind tools to an LLM that supports tool calling
llm_with_tools = llm.bind_tools([get_inventory_level, get_supplier_lead_time])

# When the LLM wants to call a tool, it returns a tool call message
response = llm_with_tools.invoke("What is the inventory level for SKU-001?")
# response.tool_calls = [{"name": "get_inventory_level", "args": {"sku_id": "SKU-001"}}]
```

**Key difference between LangChain tools and MCP tools:**

LangChain `@tool` tools are synchronous Python functions called via `.invoke()`. They are defined in the same codebase as the agent. Adding a new tool requires modifying agent code.

MCP tools are async, discovered dynamically at runtime via the Model Context Protocol. The tool definitions live on a separate MCP server process. The agent connects to the server at startup and discovers available tools without any hardcoded definitions. Adding a new tool to the MCP server does not require changing the agent code.

```
LangChain @tool:              MCP tool:
─────────────────────         ──────────────────────
Sync (.invoke())              Async (.ainvoke())
Defined in agent code         Defined on separate server
Hardcoded tool list           Dynamically discovered
Change code to add tool       Add @mcp.tool() to server
Same process as agent         Separate subprocess
```

In ORCA, MCP tools are used because the multi-server discovery pattern allows adding new tools to `mcp_server/server.py` without touching `agents/graph.py`. This is the architecturally correct choice for a system designed to be extensible.

---

### Q3: How do LangChain retrievers work? What is the difference between a VectorStoreRetriever and a MultiQueryRetriever?

**Answer:** A LangChain retriever is a Runnable that takes a string query and returns a list of `Document` objects. It implements the standard Runnable interface, so it can be used in LCEL chains. The simplest retriever wraps a vector store:

```python
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

vectorstore = Chroma(
    collection_name="orca_policies",
    embedding_function=HuggingFaceEmbeddings(model_name="nomic-ai/nomic-embed-text-v1.5"),
    persist_directory="db/chroma"
)

# Basic vector similarity retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Use in a chain
docs = retriever.invoke("What is the reorder policy for Class A SKUs?")
```

**VectorStoreRetriever** performs simple vector similarity search (or MMR — Maximum Marginal Relevance, which balances relevance with diversity to avoid returning 5 near-identical chunks).

**MultiQueryRetriever** addresses a key weakness of pure semantic search: if the user's query uses different vocabulary than the stored documents, the query vector may not match relevant chunks. MultiQueryRetriever generates multiple reformulations of the original query (using an LLM) and retrieves results for all of them, then deduplicates.

```python
from langchain.retrievers.multi_query import MultiQueryRetriever

multi_retriever = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
    llm=llm  # used to generate query variations
)

# User asks: "when should I rush an order?"
# MultiQueryRetriever generates:
#   - "When should I rush an order?"
#   - "What triggers an expedite procurement decision?"
#   - "Under what conditions should I use expedited delivery?"
# Retrieves 3 docs for each → deduplicates → returns best results
docs = multi_retriever.invoke("when should I rush an order?")
```

ORCA uses a custom hybrid approach (BM25 + vector + cross-encoder reranking) that goes beyond what standard LangChain retrievers offer out-of-the-box. The hybrid approach in `docs/rag/retriever.py` first retrieves with both BM25 (keyword matching) and vector similarity, fuses the results with Reciprocal Rank Fusion (RRF), then re-ranks with a cross-encoder — three stages that together significantly outperform any single retrieval method.

---

### Q4: What are output parsers in LangChain? How do you use them for structured output from LLMs?

**Answer:** Output parsers transform the LLM's raw text output into structured Python objects. This is essential for multi-agent pipelines where each agent's output feeds into the next — you need reliable structure, not raw text.

LangChain provides several output parser types:

```python
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# StrOutputParser: just returns the string content
parser = StrOutputParser()

# JsonOutputParser: parses JSON from response
parser = JsonOutputParser()
# chain.invoke() returns a dict

# PydanticOutputParser: parses into a typed Pydantic model
class ReplenishmentAnalysis(BaseModel):
    urgency: str = Field(description="CRITICAL, HIGH, MEDIUM, or LOW")
    trend: str = Field(description="UP, DOWN, or STABLE")
    recommended_action: str
    days_until_stockout: int

parser = PydanticOutputParser(pydantic_object=ReplenishmentAnalysis)

# The parser also generates format instructions for the prompt
format_instructions = parser.get_format_instructions()
# "The output should be formatted as a JSON instance that conforms to the JSON schema below..."

prompt = ChatPromptTemplate.from_template(
    "Analyse this inventory data: {data}\n\n{format_instructions}"
).partial(format_instructions=format_instructions)

chain = prompt | llm | parser
result: ReplenishmentAnalysis = chain.invoke({"data": sku_data})
print(result.urgency)   # type-safe string
print(result.days_until_stockout)   # type-safe int
```

The challenge with output parsers: LLMs do not always produce perfectly formatted JSON, especially smaller models or when the output is complex. The `.with_structured_output()` method on newer LangChain/LLM versions uses the model's native function calling / tool use API to get structured output more reliably than asking the model to format JSON in its response text:

```python
# Preferred for modern LLMs that support tool calling
structured_llm = llm.with_structured_output(ReplenishmentAnalysis)
result = structured_llm.invoke(prompt_text)
```

---

### Q5: When does LangChain add overhead rather than value? What are its limitations?

**Answer:** LangChain is a valuable abstraction, but it has real costs that a senior engineer should understand and communicate honestly.

**Abstraction overhead.** Every LangChain class is a layer over a simpler API. `ChatGroq` wraps the Groq SDK. `Chroma` wraps ChromaDB. When something goes wrong, you debug through two layers of abstraction instead of one. For simple use cases, the overhead is not worth it.

**Dependency weight.** `langchain` has dozens of transitive dependencies. `langchain_community` is enormous. For a slim deployment container (ORCA on Render's 512 MB limit), this matters — one reason ORCA uses `requirements.api.txt` without unnecessary LangChain extensions.

**Rapid API churn.** LangChain's API has changed significantly between versions. Code written for LangChain 0.1 often does not work with 0.3. If you inherit a LangChain codebase, the first task is often compatibility remediation.

**Over-engineering risk.** The `AgentExecutor`, `ConversationalRetrievalChain`, and similar high-level LangChain classes abstract away so much that customising them is harder than building from scratch. Many production teams that started with these have migrated to LCEL or LangGraph.

**When NOT to use LangChain:**
- Single LLM provider (no need for provider abstraction)
- Simple one-shot generation (direct API call is cleaner)
- Performance-critical paths (LangChain's Runnable invocation has overhead)
- When you need maximum control over the HTTP requests to the LLM API

**When LangChain IS worth it:**
- Multi-provider support required (write once, run on Groq/OpenAI/Anthropic)
- RAG pipelines (document loaders, text splitters, vector store integrations)
- Structured output with output parsers
- Integration with LangSmith for tracing
- As the component library for LangGraph

## Key Points to Say in the Interview

- "LCEL's pipe syntax (`prompt | llm | parser`) composes Runnables — every component implements the same interface (invoke, stream, batch, ainvoke)."
- "LangChain's value is provider abstraction and component standardisation — swap from Groq to Gemini by changing one line."
- "LangChain @tool is synchronous, hardcoded in the agent; MCP tools are async, dynamically discovered from a separate server."
- "PydanticOutputParser generates format instructions for the prompt AND validates the output — both in one component."
- "LangChain adds overhead for simple use cases — use it when provider abstraction or RAG component integration is worth the dependency cost."
- "ORCA uses LangChain as the component layer (ChatGroq, ChromaDB integration) and LangGraph as the orchestration layer."
- "`.with_structured_output()` is more reliable than asking the LLM to format JSON in its text — use it when the model supports tool calling."

## Common Mistakes to Avoid

- Using high-level Chain classes (`ConversationalRetrievalChain`) when LCEL would give more control.
- Not pinning LangChain versions — minor version upgrades can break API contracts.
- Assuming LangChain's abstractions are zero-cost — they add latency and dependency weight.
- Conflating LangChain tools and MCP tools — they have different invocation patterns (sync `.invoke()` vs async `.ainvoke()`).
- Not checking if the target deployment has LangChain's transitive dependencies available — slim containers may not.

## Further Reading

- [LangChain LCEL documentation](https://python.langchain.com/docs/expression_language/) — official guide to LCEL composition patterns
- [LangChain tool calling guide](https://python.langchain.com/docs/how_to/tool_calling/) — how to define and use tools with LLMs
- [LangChain retrievers documentation](https://python.langchain.com/docs/how_to/#retrievers) — all retriever types with examples
