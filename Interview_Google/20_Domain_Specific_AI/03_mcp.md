# Model Context Protocol (MCP): The Universal AI Tool Interface

## What Is It? (Plain English)

Model Context Protocol (MCP) is an open protocol created by Anthropic that standardises how AI applications connect to external tools, data sources, and services. Before MCP, every AI application had to write custom integration code for every tool it needed — a custom connector to read from a database, another custom connector to call an API, another for the file system. MCP is the USB standard of AI: once you build an MCP server, any MCP-compatible client can use it.

The protocol defines a client-server architecture. The MCP server is a lightweight process that exposes "tools" (functions the AI can call), "resources" (data the AI can read), and "prompts" (reusable prompt templates). The MCP client is the AI application — it connects to one or more MCP servers at startup, discovers what they offer, and makes those capabilities available to the AI. The AI can then decide which tools to call based on the task at hand.

For ORCA, MCP is used to expose 6 inventory management tools (get_sku_data, update_inventory, get_purchase_history, etc.) via a separate server process. The LangGraph pipeline connects to this server at startup and discovers the tools dynamically. The key architectural benefit: adding a new tool to the MCP server requires only adding a `@mcp.tool()` decorated function — no changes needed to the graph or agent code.

## How It Works

```
MCP ARCHITECTURE
═══════════════════════════════════════════════════════════════════

  ┌─────────────────────────────────────────┐
  │          AI Application (Client)        │
  │  ┌──────────────────────────────────┐   │
  │  │ MultiServerMCPClient             │   │
  │  │  connects to MCP servers         │   │
  │  │  discovers tools at startup      │   │
  │  │  exposes tools to LangGraph      │   │
  │  └──────────────────────────────────┘   │
  └──────────────┬──────────────────────────┘
                 │  stdio transport (subprocess)
                 │  or HTTP transport (network)
  ┌──────────────▼──────────────────────────┐
  │          MCP Server Process             │
  │  ┌──────────────────────────────────┐   │
  │  │ FastMCP server                   │   │
  │  │  @mcp.tool() get_sku_data        │   │
  │  │  @mcp.tool() update_inventory    │   │
  │  │  @mcp.tool() get_purchase_history│   │
  │  │  @mcp.tool() check_supplier_avail│   │
  │  │  @mcp.tool() create_order        │   │
  │  │  @mcp.tool() get_policy_context  │   │
  │  └──────────────────────────────────┘   │
  └──────────────────────────────────────────┘
         │
         ▼
  SQLite database, RAG retriever, external APIs

TOOL DISCOVERY SEQUENCE:
──────────────────────────────────────────────
Client starts → connects to server (stdio subprocess)
                → sends list_tools request
                → receives tool schemas (name, description, parameters)
                → makes tools available to LangGraph agents
                → agents decide when to call which tools
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

MCP is becoming the standard protocol for enterprise AI tool integration. Google's Gemini API now supports MCP, and Google Cloud has announced MCP support in Vertex AI. Any senior AI engineer at Google working on agent systems or AI-powered applications will be expected to understand MCP — both how to build MCP servers and how to integrate them as clients. More broadly, MCP represents the "integration layer" problem that Google faces at scale: how do you build AI systems that can safely and reliably connect to thousands of enterprise data sources without writing custom integration code for each one? MCP is the answer the industry is converging on.

## Interview Questions & Answers

### Q1: Why did Anthropic create MCP? What problem does it solve that LangChain tools don't?

**Answer:** MCP solves the integration problem at the ecosystem level, not the application level. LangChain tools are great for a single application — define a `@tool` decorated function, bind it to the LLM, done. But LangChain tools are tightly coupled to the application code. If you have 10 AI applications that all need to access the same database, each one implements its own database connector. When the database schema changes, you update 10 codebases.

MCP decouples the tool implementation from the tool consumer:

```
WITHOUT MCP:
  AI App 1 ─── custom DB connector ──► Database
  AI App 2 ─── custom DB connector ──► Database
  AI App 3 ─── custom DB connector ──► Database
  → 3 codebases to maintain
  → Schema change requires updating 3 apps

WITH MCP:
  AI App 1 ──┐
  AI App 2 ──┤── MCP Client ──► MCP Server (DB connector) ──► Database
  AI App 3 ──┘
  → 1 MCP server to maintain
  → Schema change requires updating 1 server
```

MCP also standardises the security model: the MCP server runs in a separate process with its own permissions. The AI application does not need to have database credentials — only the MCP server does. This is privilege separation at the architectural level.

LangChain tools are also synchronous by default and require the tool code to run in the same process as the agent. MCP tools are async and run in a separate process (or even a separate network service). This matters for security (process isolation), for deployment (the MCP server can be deployed independently), and for resource management (database connection pools live in the server, not every agent instance).

Finally, MCP is designed to be a multi-client standard. Claude Desktop, Cursor, and any other MCP-compatible application can use the same MCP server without modification. This is the network effect that makes MCP strategically important to Anthropic and increasingly to Google.

---

### Q2: Walk me through how ORCA's MCP server is built. What does the stdio transport look like?

**Answer:** ORCA's MCP server uses the `fastmcp` library, which provides a clean `@mcp.tool()` decorator interface. The server is a separate Python process (`mcp_server/server.py`) that the LangGraph graph connects to at startup.

```python
# mcp_server/server.py
from fastmcp import FastMCP
import sys
sys.path.append(".")  # add project root to path for db imports
from db import queries

mcp = FastMCP("ORCA Inventory Tools")

@mcp.tool()
def get_sku_data(sku_id: str) -> dict:
    """Get current inventory data for a SKU including quantity,
    reorder point, days of stock, and recent sales history."""
    return queries.get_sku_by_id(sku_id)

@mcp.tool()
def update_inventory(sku_id: str, quantity_delta: int, reason: str) -> dict:
    """Update inventory quantity for a SKU. Use positive delta for restocking,
    negative for adjustments. Always provide a reason for the audit log."""
    return queries.update_inventory(sku_id, quantity_delta, reason)

@mcp.tool()
def get_purchase_history(sku_id: str, days_back: int = 90) -> list[dict]:
    """Get the last N days of purchase orders for a SKU."""
    return queries.get_purchase_history(sku_id, days_back)

# FastMCP runs via stdio by default — reads from stdin, writes to stdout
if __name__ == "__main__":
    mcp.run()
```

The stdio transport works like this: the client starts the server as a subprocess and communicates via JSON-RPC messages over stdin/stdout. The client sends requests (list_tools, call_tool) to the server's stdin; the server writes responses to stdout. This is completely transparent to the application code — you just call `tool.ainvoke(args)` and the MCP client handles the serialisation.

```python
# agents/graph.py — client side
from langchain_mcp_adapters.client import MultiServerMCPClient

async def create_graph_with_mcp_tools():
    async with MultiServerMCPClient(
        {
            "orca_inventory": {
                "command": "python",
                "args": ["mcp_server/server.py"],
                "transport": "stdio",
            }
        }
    ) as client:
        tools = client.get_tools()  # discovered dynamically at runtime
        # tools is a list of LangChain-compatible tool objects
        # bind to LLM and build graph...
        llm_with_tools = llm.bind_tools(tools)
        return build_graph(llm_with_tools)
```

The crucial insight: `client.get_tools()` returns whatever tools the server currently advertises. If you add a new `@mcp.tool()` to server.py and restart, the client discovers it automatically — no changes to graph.py.

---

### Q3: What is the HTTP transport for MCP? When would you use it over stdio?

**Answer:** MCP supports two primary transports: stdio (subprocess communication) and HTTP (SSE — Server-Sent Events).

**stdio transport** is appropriate when the MCP server runs on the same machine as the client and can be managed as a subprocess. It is simple to set up, requires no network configuration, and the subprocess is automatically cleaned up when the parent process exits. ORCA uses stdio because the MCP server runs as a subprocess of the API server.

**HTTP transport (SSE)** is appropriate when the MCP server is a remote service — running on a different machine, container, or deployed as a microservice. The server exposes HTTP endpoints and uses Server-Sent Events for streaming responses.

```python
# HTTP transport example — client connects to a remote MCP server
async with MultiServerMCPClient(
    {
        "orca_inventory": {
            "url": "https://mcp-server.internal.company.com/mcp",
            "transport": "sse",
            "headers": {"Authorization": f"Bearer {api_key}"}
        }
    }
) as client:
    tools = client.get_tools()
```

```
STDIO vs HTTP TRANSPORT:
══════════════════════════════════════════════════════
                STDIO               HTTP (SSE)
─────────────────────────────────────────────────────
Deployment      Same machine        Separate service
Startup         Subprocess          HTTP connection
Lifecycle       Bound to client     Independent
Scaling         Scales with client  Scales independently
Security        Process isolation   Network auth needed
Use case        Local dev, single   Microservices,
                server              multi-client, cloud
══════════════════════════════════════════════════════
```

For enterprise deployments, HTTP transport enables a shared MCP server: one central MCP server providing access to the inventory database, shared by multiple AI applications (the ORCA pipeline, a separate analytics AI, a customer-facing recommendation AI). All clients see the same tool definitions and benefit from centralised access control and auditing.

---

### Q4: How does ORCA's dynamic tool discovery pattern work? Why is it architecturally superior to hardcoding tool definitions?

**Answer:** The dynamic discovery pattern works because MCP is a protocol, not a library — the client asks the server what it offers, rather than the client assuming it knows.

When ORCA's `MultiServerMCPClient` connects to the MCP server, it sends a `tools/list` request. The server responds with a JSON array of tool schemas — name, description, parameter types. The client turns these into LangChain-compatible `Tool` objects and passes them to the LLM via `.bind_tools()`. The LLM sees the tool schemas and can decide which ones to call.

```
Discovery sequence (at startup):
  1. MCP client starts server subprocess (python mcp_server/server.py)
  2. Client sends: {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
  3. Server responds: {"result": {"tools": [
       {"name": "get_sku_data", "description": "Get current inventory...",
        "inputSchema": {"type": "object", "properties": {"sku_id": {"type": "string"}}}},
       {"name": "update_inventory", ...},
       ...6 tools total...
     ]}}
  4. Client wraps each tool as a LangChain Tool object
  5. LLM receives all 6 tool schemas in its context
```

The architectural benefit of this pattern:

**Without dynamic discovery (hardcoded):**
```python
# agents/tools.py — defines tools in agent code
GET_SKU_DATA_TOOL = Tool(name="get_sku_data", func=get_sku_data, description="...")
UPDATE_INVENTORY_TOOL = Tool(name="update_inventory", func=update_inventory, description="...")

# agents/graph.py — imports from tools.py
from agents.tools import GET_SKU_DATA_TOOL, UPDATE_INVENTORY_TOOL
llm.bind_tools([GET_SKU_DATA_TOOL, UPDATE_INVENTORY_TOOL])
# Adding a new tool requires editing BOTH tools.py AND graph.py
```

**With dynamic discovery:**
```python
# agents/graph.py — discovers tools at runtime
tools = client.get_tools()   # discovers whatever the server advertises
llm.bind_tools(tools)
# Adding a new tool to server.py: ZERO changes to graph.py
```

The second pattern reduces the blast radius of tool additions, makes the tool server independently deployable, and correctly implements the MCP philosophy: the server owns the tool definitions, the client discovers them.

---

### Q5: What is the future of MCP for enterprise AI? How might it change how AI systems are built?

**Answer:** MCP is significant because it solves the integration problem that has historically been the largest obstacle to enterprise AI adoption. Enterprises have hundreds of internal systems — ERP, CRM, HR, financial, operational — and connecting AI to all of them has required bespoke integration work for each system and each AI application.

MCP creates the possibility of a marketplace of enterprise AI tools: an ERP vendor (SAP, Oracle) publishes an official MCP server for their product. An AI application connects to it via the standard protocol and immediately gains access to inventory data, purchase orders, financial records, and supplier information — without any custom integration code.

```
ENTERPRISE MCP ECOSYSTEM (emerging):
═══════════════════════════════════════════════════════════════════
                     AI Application
                    (Claude, Gemini, custom)
                           │
                           │ MCP Protocol
                  ┌────────┼────────┐
                  ▼        ▼        ▼
             SAP MCP   Salesforce  GitHub
             Server    MCP Server  MCP Server
                │          │          │
             SAP DB    CRM Data   Code repos

Each vendor builds their MCP server once.
Every AI application benefits immediately.
═══════════════════════════════════════════════════════════════════
```

Current adoption (as of 2025): Claude Desktop has a large MCP server marketplace. Cursor (AI IDE) uses MCP for tool integration. Google's Gemini API supports MCP. Major enterprise software vendors are building official MCP servers.

The architectural implication: AI systems of the future will be assembled from a catalogue of MCP servers rather than written from scratch. The skill shifts from "write custom integration code" to "design which MCP servers to connect, how to compose their capabilities, and how to implement appropriate access controls between the AI and the enterprise systems." This is the direction ORCA is pointing at, even though it only has one MCP server today.

Security considerations become critical at scale: if the AI can call any tool the MCP server exposes, you need fine-grained access control at the MCP layer — not every agent should have access to `update_inventory`, even if they can call `get_sku_data`.

## Key Points to Say in the Interview

- "MCP decouples tool implementation from tool consumption — one MCP server, many AI clients, no custom integration code per client."
- "ORCA's dynamic discovery pattern: `client.get_tools()` at runtime — adding a tool to server.py requires zero changes to graph.py."
- "stdio transport for co-located services, HTTP/SSE transport for microservices and multi-client deployments."
- "MCP tools are async (`.ainvoke()`); LangChain @tool is synchronous (`.invoke()`) — important for performance in async pipelines."
- "The MCP server owns the tool definitions; the client discovers them — this is the correct ownership model."
- "Process isolation is a security benefit of MCP: the database credentials live in the server process, not in the agent."
- "Enterprise future: MCP server marketplaces (SAP, Salesforce, GitHub publishing official MCP servers) enable AI applications to be assembled from components."

## Common Mistakes to Avoid

- Confusing MCP tools with LangChain tools — they use different invocation patterns and have different architectural properties.
- Using stdio transport when the MCP server needs to be independently scaled or shared across multiple client instances.
- Not handling async context properly when using `MultiServerMCPClient` — it requires `async with` context manager to manage the subprocess lifecycle.
- Giving all agents access to all MCP tools — follow least privilege: agents should only bind the tools they actually need.
- Not versioning the MCP server separately from the application — they should be independently deployable.

## Further Reading

- [Model Context Protocol specification](https://spec.modelcontextprotocol.io/) — the official protocol specification and architecture documentation
- [MCP Python SDK (Anthropic)](https://github.com/modelcontextprotocol/python-sdk) — the reference Python implementation with examples
- [FastMCP library](https://github.com/jlowin/fastmcp) — the high-level Python framework for building MCP servers used by ORCA
