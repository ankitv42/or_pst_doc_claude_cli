# Working with Frontier LLM APIs

## What Is It? (Plain English)

The major frontier LLM providers — OpenAI, Anthropic, and Google (Gemini) — all expose their models through HTTP APIs that follow a similar pattern. You send a request with a list of messages (conversation history), optionally with tools the model can call, and receive a response with the model's generated text plus any tool call decisions. Understanding the exact format of these requests and responses, and the key features each provider offers, is essential for building production AI systems.

The formats are similar but not identical across providers. OpenAI's Chat Completions API established the pattern that others largely follow. Anthropic's Messages API uses the same concepts (system prompt, messages array, assistant response) but with slightly different JSON keys and some unique features like extended thinking. Google's Gemini API follows a similar pattern with `contents` instead of `messages`.

The most practically important advanced feature right now is prompt caching. When you repeatedly send the same long system prompt (thousands of tokens describing your AI's role, tools, and context), you pay full price every time. Prompt caching lets providers cache the prefix of your context window — so if your system prompt plus documents hasn't changed, you only pay a fraction of the usual cost (75-90% discount on cached tokens). For ORCA's agent prompts with long policy context injected on every call, prompt caching could reduce LLM costs by 60-80%.

## How It Works

```
OPENAI CHAT COMPLETIONS FORMAT:
═══════════════════════════════════════════════════════════════════
POST https://api.openai.com/v1/chat/completions
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "You are an inventory analyst..."},
    {"role": "user", "content": "Analyse SKU-001: qty=5, reorder_point=50"},
    {"role": "assistant", "content": "SKU-001 is critically low..."},
    {"role": "user", "content": "What should we order?"}
  ],
  "tools": [                          // optional: tool definitions
    {
      "type": "function",
      "function": {
        "name": "get_supplier_info",
        "description": "Get supplier lead times for a SKU",
        "parameters": {
          "type": "object",
          "properties": {"sku_id": {"type": "string"}},
          "required": ["sku_id"]
        }
      }
    }
  ],
  "temperature": 0.1,
  "max_tokens": 512
}

ANTHROPIC MESSAGES FORMAT (similar concept, different keys):
POST https://api.anthropic.com/v1/messages
{
  "model": "claude-opus-4-5",
  "max_tokens": 512,
  "system": "You are an inventory analyst...",    // separate from messages
  "messages": [
    {"role": "user", "content": "Analyse SKU-001..."},
    {"role": "assistant", "content": "SKU-001 is critically low..."},
    {"role": "user", "content": "What should we order?"}
  ]
}
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google's Gemini API is in direct competition with OpenAI and Anthropic. Senior engineers at Google who work on Gemini-powered products must understand how these APIs compare — what features Gemini offers, where competitors are ahead, and what enterprise customers need from a frontier LLM API. Additionally, many Google Cloud customers build AI applications that use multiple LLM providers, so understanding provider-agnostic patterns (LiteLLM, LangChain's ChatModel abstraction) is valuable. Finally, prompt caching is a cost management skill — at enterprise scale, caching could save millions of dollars annually.

## Interview Questions & Answers

### Q1: Explain the OpenAI Chat Completions message format. What are the roles and how do they structure a conversation?

**Answer:** The OpenAI Chat Completions API structures conversations as an ordered list of messages, each with a `role` and `content`. The roles define who "said" each message and how the model should weight it.

**`system`:** Provides overall context, instructions, and persona for the model. This is the model's briefing — who it is, what it knows, what constraints it operates under. System messages are given high weight and are very hard to override through subsequent messages. Only one system message is typically used, placed first.

**`user`:** Represents input from the human user. This is the question, request, or information the user is providing. Multiple user messages create a multi-turn conversation history.

**`assistant`:** Represents the model's previous responses. When you include assistant messages in the history, you are showing the model what it said previously, enabling coherent multi-turn conversations. You can also manually craft assistant prefills — start an assistant message with a specific opening and the model will continue from there.

**`tool`:** Used to provide the results of tool calls back to the model. After the model returns a `tool_calls` field (requesting to call a tool), you run the tool and add the result as a `tool` role message.

```python
import openai
client = openai.OpenAI()

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "You are ORCA, an inventory management AI. "
                       "Analyse inventory data and recommend reorder actions."
        },
        {
            "role": "user",
            "content": "SKU-001: current_qty=5, reorder_point=50, "
                       "days_of_stock=2, category=electronics"
        }
    ],
    temperature=0.1,     # low temp for consistent, factual analysis
    max_tokens=512,
    response_format={"type": "json_object"}  # force JSON output
)

content = response.choices[0].message.content
finish_reason = response.choices[0].finish_reason   # "stop", "length", "tool_calls"
usage = response.usage   # prompt_tokens, completion_tokens, total_tokens
```

Tool use extends this pattern: if the model decides to call a tool, the response contains `tool_calls` instead of text content. You run the tool and add a `tool` role message with the result, then call the API again.

---

### Q2: What is the difference between the OpenAI and Anthropic tool calling formats? How do you write provider-agnostic tool calling code?

**Answer:** Both APIs use JSON to describe tools and return JSON tool call requests, but the exact structure differs in keys and nesting.

**OpenAI tool calling format:**

```python
# Tool definition
openai_tool = {
    "type": "function",
    "function": {
        "name": "get_sku_data",
        "description": "Get current inventory data for a SKU",
        "parameters": {
            "type": "object",
            "properties": {
                "sku_id": {"type": "string", "description": "The SKU identifier"}
            },
            "required": ["sku_id"]
        }
    }
}

# Model response when it wants to call a tool:
# response.choices[0].message.tool_calls = [
#   ToolCall(id="call_abc", type="function",
#            function=Function(name="get_sku_data", arguments='{"sku_id": "SKU-001"}'))
# ]
```

**Anthropic tool calling format:**

```python
# Tool definition (similar structure, different key)
anthropic_tool = {
    "name": "get_sku_data",
    "description": "Get current inventory data for a SKU",
    "input_schema": {              # "input_schema" not "parameters"
        "type": "object",
        "properties": {
            "sku_id": {"type": "string", "description": "The SKU identifier"}
        },
        "required": ["sku_id"]
    }
}

# Model response when it wants to call a tool:
# response.content = [
#   ToolUseBlock(type="tool_use", id="toolu_abc",
#                name="get_sku_data", input={"sku_id": "SKU-001"})
# ]
```

**Provider-agnostic approach using LangChain:**

```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq

# Define tool once — works with all providers
@tool
def get_sku_data(sku_id: str) -> dict:
    """Get current inventory data for a SKU."""
    return db_queries.get_sku_by_id(sku_id)

# LangChain handles the format conversion per provider
openai_agent = ChatOpenAI(model="gpt-4o").bind_tools([get_sku_data])
anthropic_agent = ChatAnthropic(model="claude-opus-4-5").bind_tools([get_sku_data])
groq_agent = ChatGroq(model="llama-3.1-8b-instant").bind_tools([get_sku_data])

# All three are called the same way
response = openai_agent.invoke("What is the inventory for SKU-001?")
```

**LiteLLM** is another provider-agnostic option — it provides a unified interface that mirrors OpenAI's format and translates to each provider's native format internally.

---

### Q3: What is prompt caching? How does it work in Anthropic and OpenAI? What is the cost impact?

**Answer:** Prompt caching allows LLM providers to reuse previously processed prompt prefixes rather than recomputing them for every request. Since computing attention over thousands of tokens is the expensive part of inference, caching the key-value attention states for stable prefix content dramatically reduces cost and latency.

**Anthropic's prompt caching** uses the `cache_control` field:

```python
import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are ORCA, an inventory management AI assistant. "
                    "Here are the complete inventory management policies:\n\n"
                    + full_policy_text,   # 50,000 tokens of policy context
            "cache_control": {"type": "ephemeral"}  # mark this for caching
        }
    ],
    messages=[
        {"role": "user", "content": "Analyse SKU-001..."}
    ]
)

# Check cache performance in response:
print(response.usage.cache_creation_input_tokens)  # first call: tokens processed
print(response.usage.cache_read_input_tokens)       # subsequent calls: tokens read from cache
```

**Cache economics:**
- First call: pay 25% more than normal (cache write cost)
- Subsequent calls within 5 minutes (ephemeral): pay 10% of normal (90% discount)
- For ORCA: 4 agents each making 1 LLM call per pipeline run, each with ~5,000 token system prompt
  - Without caching: 4 × 5,000 = 20,000 tokens × $15/M = $0.30 per pipeline run
  - With caching (if runs cluster): cache write first run, then ~$0.03/run (90% cheaper)

**OpenAI's automatic prompt caching** (no explicit marking needed):

```python
# OpenAI caches automatically when the same prefix is detected
# Works for system prompts and multi-turn conversation history
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...long stable system prompt + changing user message...]
)
# response.usage.prompt_tokens_details.cached_tokens = N
```

OpenAI's caching is automatic and applies to the longest matching prefix. Anthropic's requires explicit `cache_control` markers but gives you more control over what gets cached.

**Practical impact for ORCA:** ORCA's agents use policy context from the RAG system in their prompts. If this context were marked with `cache_control`, the expensive vector search and large context injection would be cached for subsequent calls, significantly reducing both latency and cost.

---

### Q4: How do you implement streaming LLM responses? When would you use it in an AI system?

**Answer:** Streaming returns tokens as they are generated rather than waiting for the full response. This dramatically improves perceived latency — for a 500-token response at 100 tokens/second, streaming shows first token in ~0.1 seconds; non-streaming shows first token after ~5 seconds.

```python
# OpenAI streaming
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    stream=True  # enable streaming
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="", flush=True)

# Anthropic streaming
with client.messages.stream(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[...]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

# LangChain streaming (provider-agnostic)
for chunk in llm.stream(prompt):
    print(chunk.content, end="", flush=True)

# FastAPI streaming response endpoint
from fastapi.responses import StreamingResponse

@app.post("/pipeline/stream")
async def stream_pipeline(request: PipelineRequest):
    async def generate():
        async for chunk in llm.astream(build_prompt(request)):
            yield f"data: {chunk.content}\n\n"  # Server-Sent Events format
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**When to use streaming in an AI system:**

Use streaming for: chat interfaces (users see responses appear as they're generated), long-form content generation (blog posts, reports), anything where first-token latency matters for UX.

Do NOT use streaming for: agent pipelines where the full response must be parsed before proceeding (Agent 3's JSON output must be complete before Agent 4 can route), batch processing where throughput matters more than latency, or when the response must pass through output validators before being shown to the user.

For ORCA: streaming is not appropriate for the pipeline agents (they need complete JSON responses for parsing). It would be appropriate for a conversational interface built on top of ORCA where a human analyst asks follow-up questions about a pending approval.

---

### Q5: How does ORCA use Groq via LangChain's ChatGroq? What is Groq, and what are its trade-offs vs OpenAI/Anthropic?

**Answer:** Groq is an LLM inference provider that uses a custom hardware chip (the LPU — Language Processing Unit) designed specifically for the memory-bandwidth-intensive operations of transformer inference. The result is inference speeds of 200-500 tokens/second — approximately 10x faster than GPU-based inference for the same model.

ORCA uses Groq's free tier with `llama-3.1-8b-instant`:

```python
from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama-3.1-8b-instant",  # or llama-3.3-70b-versatile for higher quality
    groq_api_key=os.environ["GROQ_API_KEY"],
    temperature=0.1,
    max_tokens=512,
)

# LangChain handles Groq's API format transparently
response = llm.invoke("Analyse this inventory data: ...")
```

**Groq vs OpenAI/Anthropic:**

```
TRADE-OFF TABLE:
══════════════════════════════════════════════════════════════════
                  Groq             OpenAI GPT-4o    Anthropic Claude
──────────────────────────────────────────────────────────────────
Speed             Very fast        Moderate         Moderate
                  200-500 tok/s    50-100 tok/s     50-80 tok/s
Cost              Free tier        ~$15/M tokens    ~$15/M tokens
                  then low         input            input
Model quality     Open models      GPT-4o best      Claude best
                  (Llama, Mixtral) in class         in class
Max context       128k tokens      128k tokens      200k tokens
Tool calling      Yes              Yes              Yes
Prompt caching    No               Yes (auto)       Yes (explicit)
Context window    Standard         Standard         Best (200k)
Streaming         Yes              Yes              Yes
Rate limits       Free tier limited Flexible        Flexible
ORCA usage        Production       Not used         Not used
══════════════════════════════════════════════════════════════════
```

ORCA chose Groq for two reasons: (1) free tier access makes it deployable without API costs for a portfolio project, and (2) the high inference speed reduces pipeline latency (each agent call takes 1-2 seconds on Groq vs 3-5 seconds on GPT-4o for the same prompt).

The trade-offs: Groq's open-source models (Llama 3.1 8B instant) are lower quality than GPT-4o or Claude Opus for complex reasoning tasks. The CrewAI compatibility issue (ORCA's Known Issue #1) is a Groq-specific problem — Groq rejects certain request fields that other providers ignore. And Groq's free tier rate limits (30 requests/minute) can cause timeouts under load.

For a production enterprise deployment, the LLM choice would likely shift to `gpt-4o-mini` (OpenAI) or `claude-haiku-3-5` (Anthropic) for cost-effectiveness at scale, with prompt caching to manage costs.

## Key Points to Say in the Interview

- "OpenAI uses `messages` with role=system/user/assistant/tool; Anthropic uses `system` separately and `messages` with user/assistant."
- "Tool calling: model returns a tool_calls field instead of text content; you run the tool and add the result as a `tool` role message."
- "Prompt caching: Anthropic uses explicit `cache_control` markers, OpenAI caches automatically — both give ~90% cost reduction on cached tokens."
- "Streaming: use for chat interfaces where first-token latency matters; don't use in agent pipelines where full JSON must be parsed first."
- "LangChain's ChatModel abstraction makes provider-agnostic code possible — swap `ChatGroq` for `ChatOpenAI` with one line change."
- "Groq provides 10x faster inference than GPU providers for the same model — at the cost of lower-quality open-source models."
- "ORCA uses ChatGroq with llama-3.1-8b-instant — fast, free, but lower quality than frontier models."

## Common Mistakes to Avoid

- Hardcoding provider-specific formats in application code — use LangChain or LiteLLM abstraction for portability.
- Not handling `finish_reason = "length"` — if the model's output was cut off, the JSON will be incomplete and parsing will fail.
- Using streaming in agent pipelines — the pipeline needs the complete structured output before routing.
- Not implementing retry logic for API calls — transient rate limit errors (429) and server errors (500) are common at scale.
- Confusing prompt caching with response caching — prompt caching saves on the input processing; response caching saves on the entire API call.

## Further Reading

- [OpenAI API documentation](https://platform.openai.com/docs/api-reference/chat) — complete Chat Completions API reference including tool calling and streaming
- [Anthropic Messages API documentation](https://docs.anthropic.com/en/api/messages) — Claude API reference including prompt caching and extended thinking
- [LiteLLM documentation](https://docs.litellm.ai/) — unified LLM API library supporting 100+ providers with OpenAI-compatible interface
