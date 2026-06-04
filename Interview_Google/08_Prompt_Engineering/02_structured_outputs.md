# Structured Outputs

## What Is It? (Plain English)

Structured output means getting an LLM to return data in a specific, machine-readable format — JSON, XML, or a typed object — rather than free-form prose. It is the difference between a model that says "I think you should order about 200 units" and one that returns `{"action": "reorder", "quantity": 200, "confidence": 0.87, "escalate": false}`. The second response can be read by code; the first requires a human or another parsing step.

Think of it like a government form versus a letter. A letter expressing the same information as a tax form might be accurate, but you cannot process it with a computer. Structured output is the discipline of making LLMs fill out the form, not write the letter. In production AI pipelines where one agent's output becomes another agent's input, structured output is not a nice-to-have — it is a hard requirement for the pipeline to function at all.

The challenge is that language models are generative: they produce tokens in sequence, optimizing for plausibility, not for schema compliance. Achieving reliable structured output requires a layered strategy: prompt-level instructions, API-level enforcement, and application-level validation and self-correction.

## How It Works

The layers of structured output enforcement stack from most flexible (prompt-only) to most reliable (schema-constrained generation):

```
┌────────────────────────────────────────────────────────────┐
│              STRUCTURED OUTPUT ENFORCEMENT STACK            │
├────────────────────────────────────────────────────────────┤
│  LAYER 4: Application Validation                            │
│  Pydantic model.parse() → catches type errors, missing      │
│  fields, out-of-range values after the model responds       │
├────────────────────────────────────────────────────────────┤
│  LAYER 3: Self-Correction Loop                              │
│  On parse failure → inject error + raw output into new      │
│  prompt → ask model to fix → retry up to N times           │
├────────────────────────────────────────────────────────────┤
│  LAYER 2: API-Level Enforcement                             │
│  JSON mode: every token must be valid JSON                  │
│  Function calling: output must match function schema        │
│  Structured output (OpenAI/Anthropic): JSON Schema          │
├────────────────────────────────────────────────────────────┤
│  LAYER 1: Prompt-Level Instruction                          │
│  "Respond ONLY with JSON. Schema: {field: type, ...}"       │
│  Include a one-shot example of the target format            │
└────────────────────────────────────────────────────────────┘
                          ▼
              Parsed, Validated Python Object
              (Pydantic BaseModel or dataclass)
```

Each layer catches failures that slip through the layer above. In most production systems, you use all four layers simultaneously.

## Why Google Cares About This

Google builds products at a scale where a 1% structured output failure rate means millions of malformed responses per day. When a model's output feeds into another model, a user interface, a database write, or an action in the world, format violations are not tolerated. Google interviewers test for this because it separates candidates who have built real pipelines (where you learn about format failures painfully) from those who have only used LLMs in demos. Senior engineers at Google are expected to design systems that degrade gracefully under model output failures, not systems that crash.

## Interview Questions & Answers

### Q1: Walk me through how you would implement reliable structured output in a multi-agent pipeline.

**Answer:** Reliable structured output in a multi-agent pipeline requires defense in depth across all four enforcement layers. Start at the prompt level: give the model an explicit schema description and a one-shot example of a correctly formatted response. The example is more important than the schema description alone — models pattern-match to examples more reliably than they follow abstract type specifications.

At the API level, use whatever schema enforcement the provider offers. OpenAI's structured output feature (with `response_format={"type": "json_schema", "json_schema": ...}`) constrains the token sampling process so only tokens that are valid continuations of the target JSON schema are ever generated. This eliminates an entire class of formatting failures that prompt instructions alone cannot prevent. Anthropic's tool use feature and Google Gemini's controlled generation offer comparable enforcement.

At the application level, define a Pydantic model for every agent's output and call `.model_validate()` on the parsed JSON. This catches semantic violations that syntactic JSON enforcement misses: a confidence score of 150 is valid JSON but not a valid probability, and Pydantic validators can reject it. Use validators for range checks, regex validation on IDs, and cross-field consistency (e.g., if escalate=true, then justification must be non-empty).

When validation fails, implement a self-correction loop: catch the `ValidationError`, format the error message and the raw model response into a new prompt — "Your previous response failed validation with error: {error}. Here is your response: {response}. Please correct it and return only valid JSON matching the schema" — and retry. Cap retries at 2-3 to avoid runaway costs. Log all corrections for offline analysis. In ORCA, agent outputs are Pydantic models, and parse failures are logged with the raw LLM response and error message so the eval framework can track format regression rates over time.

### Q2: What is the difference between JSON mode, function calling, and structured output, and when would you use each?

**Answer:** These three mechanisms offer increasing levels of schema enforcement, with different trade-offs in flexibility and reliability.

JSON mode (available in OpenAI, Anthropic, and most providers) constrains the model to only emit tokens that produce valid JSON. It does not enforce any specific schema — the model might return `{"text": "here is my answer"}` when you wanted `{"action": "reorder", "quantity": 200}`. JSON mode eliminates JSON syntax errors (unclosed brackets, unescaped quotes) but not schema violations. Use JSON mode when you want machine-readable output but have a flexible or variable schema, or when you will apply your own post-processing to extract fields.

Function calling (also called tool use) wraps structured output in a higher-level abstraction: the model "calls a function" by emitting JSON arguments that match a function signature you define. The API enforces that the emitted JSON matches the function's parameter schema. This is more reliable than JSON mode alone because the schema is defined by you, not inferred by the model. Use function calling when you want the model to select among multiple possible actions (each represented as a function) in addition to filling in parameters — this is the natural fit for agent tool use.

OpenAI's structured output feature (2024+) and comparable offerings from Anthropic extend function calling to enforce arbitrary JSON Schema constraints, including nested objects, enums, required fields, and format validators. This is the most reliable option for complex schemas and should be the default for production pipelines where schema compliance is critical. The limitation is that very complex schemas can confuse models and degrade response quality — sometimes a simpler schema with application-level validation produces better results than a maximally constrained schema that the model struggles to satisfy.

### Q3: How does Pydantic improve structured output reliability, and what are its limitations?

**Answer:** Pydantic is a Python library that defines data schemas as classes and validates data against them at parse time. For structured LLM output, you define the expected response shape as a Pydantic `BaseModel` subclass and call `MyModel.model_validate(json.loads(llm_response))`. This validates field presence, types, formats, and any custom validators you define, and raises a `ValidationError` with a detailed error message if anything fails.

The reliability improvement comes from four Pydantic features. First, required vs. optional field enforcement: if the model omits a required field, Pydantic raises immediately instead of your code failing with a `KeyError` later in an unrelated function. Second, type coercion with validation: a field typed as `float` will accept the string `"0.87"` from JSON and coerce it, but will reject `"high"`. Third, validators: you can add custom logic like `@validator('confidence') def confidence_must_be_probability(cls, v): assert 0 <= v <= 1; return v`. Fourth, nested models: multi-level structured outputs can be validated hierarchically — each nested object is its own Pydantic model.

The key limitation is that Pydantic validates what the model returned, but cannot recover from what the model did not return. If the model returns `{}`, Pydantic will tell you every required field is missing, but it cannot fill them in. This is why Pydantic is layer 4 of a 4-layer stack, not a complete solution on its own. Another limitation: Pydantic validation errors expose your schema to the model in self-correction loops, which is usually fine but can become a security concern in adversarial settings where users might extract schema information to craft injection attacks.

### Q4: Describe the self-correction loop pattern. How do you implement it without creating infinite retry loops?

**Answer:** The self-correction loop detects structured output failures and asks the model to fix its own mistakes. The loop works because language models are generally good at recognizing formatting errors when shown their output alongside the error — they can apply the same schema knowledge that should have guided the initial generation.

Implementation: (1) Call the model with the original prompt. (2) Attempt to parse and validate the response. (3) If validation passes, return the result. (4) If validation fails, construct a correction prompt: include the original task context, the model's failed response, the specific validation error message, and a clear instruction to produce a corrected response. (5) Call the model with the correction prompt. (6) Attempt validation again. (7) Repeat up to `max_retries` (typically 2-3). (8) If all retries are exhausted, raise a `StructuredOutputFailure` exception with full context for logging.

```python
def call_with_correction(prompt, schema_cls, max_retries=2):
    response = call_llm(prompt)
    for attempt in range(max_retries + 1):
        try:
            return schema_cls.model_validate(json.loads(response))
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt == max_retries:
                raise StructuredOutputFailure(response, e)
            correction_prompt = build_correction_prompt(
                original=prompt, failed_output=response, error=str(e)
            )
            response = call_llm(correction_prompt)
```

Preventing infinite loops requires hard retry caps. Do not retry indefinitely — a model that fails three times on the same schema is unlikely to succeed on a fourth attempt without a different approach. Also implement exponential backoff between retries (100ms, 200ms, 400ms) to avoid hammering your rate limit. For monitoring, log each correction attempt with the error type and whether it eventually succeeded — a high correction rate for a specific agent is a signal that the prompt or schema needs redesign, not just more retries.

### Q5: How does ORCA's multi-agent pipeline depend on structured outputs, and what happens when they fail?

**Answer:** ORCA's 4-agent LangGraph pipeline uses structured outputs as the inter-agent communication protocol. Agent 1 returns a demand analysis object with fields like `urgency_score`, `demand_trend`, and `lead_time_days`. Agent 2 reads these fields to build its three reorder options. Agent 3 reads Agent 2's options to apply the capital allocation scoring formula. Agent 4 reads Agent 3's scoring output to make the routing decision. Each agent's output is the next agent's input — this is a strict data dependency chain.

If Agent 1 returns malformed JSON, the entire pipeline fails at the point where Agent 2 tries to read `urgency_score`. In the current implementation, LangGraph propagates this as a Python exception, the pipeline logs a FAILED status, and the dashboard shows an error state to the user. This is acceptable for a prototype but would be insufficient for production: a production system would need graceful degradation, where a structured output failure triggers a fallback to a simpler prompt, a cached result, or a default value with a human review flag.

The known issue with ORCA's Agent 1 CrewAI sub-crew (where Groq rejects the `cache_breakpoint` field) is actually a structured output failure at a different level — the request payload rather than the response. The fix pattern is the same: validate the structure of what you are sending to the model, not just what comes back. A comprehensive structured-output discipline covers both directions: outbound prompt construction and inbound response parsing. Both can fail in production, and both need validation and error handling.

## Key Points to Say in the Interview

- Structured output is mandatory in multi-agent pipelines where one agent's output is another's input — free-form prose breaks the pipeline
- Use all four enforcement layers: prompt instruction, API-level schema enforcement, application-level Pydantic validation, and self-correction loop
- JSON mode prevents syntax errors; function calling and structured output prevent schema violations — they solve different problems
- Pydantic validators catch semantic violations that JSON Schema cannot express, such as out-of-range floats or cross-field consistency rules
- Self-correction loops should have hard retry caps (2-3) and log all failures for offline analysis and eval suite improvement
- Schema simplicity improves reliability — a model following a 5-field schema is more reliable than one following a 20-field schema

## Common Mistakes to Avoid

- Using only prompt-level format instructions without API-level or application-level enforcement — this works in demos but fails under load
- Treating JSON parse success as validation success — valid JSON with wrong fields or wrong value ranges is still a schema violation
- Not logging structured output failures — without this data you cannot tell whether your correction loop is working or whether a model upgrade broke your schemas
- Designing schemas that are too complex, with deeply nested objects and many required fields — complexity increases failure rate; prefer flatter schemas with optional fields where possible
- Forgetting to validate the model response when using API-level structured output, assuming the API guarantee is absolute — even enforced structured output can produce valid-schema but semantically wrong values

## Further Reading

- [OpenAI Structured Outputs Documentation](https://platform.openai.com/docs/guides/structured-outputs) — covers JSON Schema enforcement and function calling with detailed examples
- [Pydantic Documentation](https://docs.pydantic.dev/latest/) — comprehensive reference for validation, custom validators, and Pydantic v2 features
- [Instructor Library](https://python.useinstructor.com/) — open-source library for structured LLM output with built-in retry and correction loops across multiple providers
