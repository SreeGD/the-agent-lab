# 05 — Structured Output

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/05_structured_output_ollama.py`.

> **Get a validated Pydantic object back from the LLM instead of a string.** No regex, no `json.loads`, no `try/except` around malformed JSON. Type checker happy, IDE autocomplete works, production code happy.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01 model wrapper         (01_model_wrapper.py)                    ○ 13 system     ○ 16-19 Healthcare
  ✓ 02 LCEL composition       (02_lcel_chain.py)                       design       ○ 20-22 Agriculture
  ✓ 03 agent tool loop        (03_agent_manual.py, 03_agent_framework.py)      ○ 14 red-team   ○ 23-25 Finance
  ✓ 04 prompt caching         (04_prompt_caching.py)         ○ 15 AI UX      ○ 26-28 Vidya Karana
                                                                            ○ 29-32 Family AI
  ▶ 05 STRUCTURED OUTPUT  ◄═══════ YOU ARE HERE

  ○ 06 parallel chains        (06_parallel_chains.py)
  ○ 07 output parsers         (07_output_parsers.py)
  ○ 08 chatbot memory         (08_chatbot_memory.py)
  ○ 09 RAG                    (09_rag.py)
  ○ 10 guardrails             (10_guardrails.py)
  ○ 11 production capstone    (11_production_chatbot.py)
  ○ 12 MCP                    (12_mcp_server.py, 12_mcp_client.py)
```

**Why this lesson now:** by lesson 5 you have agents that call tools. The next step is making the *answer itself* a typed object — so the LLM's output flows into your code the same way function return values do. Pairs naturally with the agent loop in lesson 3 (tools are functions in; structured output is typed objects out).

---

## Files involved

| File | Role |
|---|---|
| [`05_structured_output_ollama.py`](../ollama/05_structured_output_ollama.py) | The runnable example — email triage as a typed Pydantic model |
| Compares against | [`07_output_parsers.py`](../07_output_parsers.py) — the older `PydanticOutputParser` approach (text-parsing) |

---

## What problem it solves

LLMs produce **strings** by default. Production code needs **typed objects**.

Without structured output, every LLM call returns a blob of prose like:
> *"Sure! Here's my analysis: the priority is urgent, the sentiment is negative, and the action items include rolling back the deploy..."*

You then write **regex, `json.loads`, string parsing, try/except, retry logic** to extract `priority`, `sentiment`, `action_items` — and the LLM can still return malformed JSON, extra prose ("Sure! Here's..."), missing commas, or invented fields that break your code. Every endpoint becomes a parsing project.

**Structured output makes the LLM produce the typed object directly**, with the schema enforced by the provider's tool-calling API. No parsing. No regex. The LLM literally can't return shapes that don't match your Pydantic class.

---

## The analogy

Think of a job application:

| Without structured output | With structured output |
|---|---|
| Candidate writes a **free-form essay** about their qualifications | Candidate fills out a **form with explicit fields**: Name [____], GPA [____], Skills [____] |
| You read the essay and try to extract Name, GPA, References | The form already separates the fields |
| Some essays are missing fields; some include made-up sections | The form rejects submissions that skip required fields |
| 80% of your work is parsing the essay | 80% of your work disappears |

The Pydantic class IS the form. The LLM is the candidate. The form constraint is doing the parsing work for you.

---

## Visual

```
WITHOUT structured output                  WITH structured output
─────────────────────────                  ────────────────────────────

   prompt          →                          prompt + schema    →
   "Triage this                                "Triage this email"
   email"                                     + tools=[EmailTriage schema]
        │                                            │
        ▼                                            ▼
      LLM                                          LLM
        │                                            │
        ▼                                            ▼
  AIMessage with                              AIMessage with
  .content = "Sure! The                       tool_calls=[{
  priority is urgent,                           name: "EmailTriage",
  the sentiment is..."                          args: {
        │                                         priority: "urgent",
        ▼                                         sentiment: "negative",
   regex / json.loads /                           action_items: [...],
   try/except / retry                             ...
        │                                       }
        ▼                                     }]
   ⚠ string that LOOKS                              │
     like JSON, sometimes                           ▼
                                            Pydantic.model_validate(args)
                                                    │
                                                    ▼
                                            ✅ typed instance
                                            ✅ IDE autocomplete
                                            ✅ no parsing code
```

---

## The concept

By default, `model.invoke("...")` returns an `AIMessage` whose `.content` is a string. Useful for chat; awful for code that needs to *act* on the answer. **Structured output makes the LLM produce a typed Pydantic instance instead** — one keyword change, no prompt engineering required.

```python
class EmailTriage(BaseModel):
    summary: str
    priority: Literal["low", "medium", "high", "urgent"]
    sentiment: Literal["positive", "neutral", "negative"]
    requires_response: bool
    action_items: list[str]
    estimated_response_time_minutes: int

extractor = model.with_structured_output(EmailTriage)
result: EmailTriage = extractor.invoke(email_text)

print(result.priority)              # "urgent" — str, validated
print(result.action_items[0])       # str, IDE-autocompletes
```

Under the hood, LangChain converts the Pydantic class into a JSON Schema, binds it as a "tool" the LLM must call, parses the tool-call arguments into the Pydantic instance, and validates. **It's tool-calling for data, not for actions.**

---

## The code

```python
from typing import Literal
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama

class EmailTriage(BaseModel):
    """Triage information extracted from an email."""
    summary: str = Field(description="One-sentence summary.")
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        description="How urgently the recipient should respond."
    )
    sentiment: Literal["positive", "neutral", "negative"]
    requires_response: bool
    action_items: list[str] = Field(
        description="Concrete next steps. Empty list if none."
    )
    estimated_response_time_minutes: int

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)
extractor = model.with_structured_output(EmailTriage)

result = extractor.invoke(SOME_EMAIL_TEXT)
```

That's the entire pattern. **Three lines added to a normal chain.**

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
cd helloworld
source .venv/bin/activate
python ollama/05_structured_output_ollama.py
```

Expected output (excerpt — full email response):

```
{
  "summary": "A 30% drop in billed events has been detected since a 14:00 UTC deploy...",
  "priority": "urgent",
  "sentiment": "negative",
  "requires_response": true,
  "action_items": [
    "Roll back the billing-worker service to commit 8a3f12 immediately.",
    "Confirm event counts recover after the rollback.",
    "Post status updates in #incidents every 15 minutes until resolved."
  ],
  "estimated_response_time_minutes": 5
}
```

The `extractor.batch([email_1, email_2])` call in the file then runs two extractions in parallel and returns `list[EmailTriage]`.

---

## Walk-through

### 1. The schema IS the prompt

You never wrote a system prompt. Never said "respond in JSON." Never said "priority must be one of low/medium/high/urgent." Llama 3.2 *read your Pydantic class* to figure all that out:

- Field names → expected dict keys
- Type hints (`Literal[...]`) → allowed values
- `Field(description="...")` → semantic hint for what each field means

**Better descriptions = better outputs.** This is the single most important takeaway. Most beginners miss it.

### 2. Validation is automatic

If the model tried to return `priority: "extremely-urgent"` (not in the `Literal`), Pydantic raises `ValidationError` *before* `result` is bound. The model **cannot** sneak invalid data into your code path.

Same for types: `estimated_response_time_minutes: int` means an integer or `ValidationError`. No "about thirty" slipping through.

### 3. It's tool-calling under the hood

`with_structured_output(EmailTriage)` doesn't use a special API. It:

```
prompt + (tools=[EmailTriage schema])  →  Ollama API
                                            │
                                            ▼
                            AIMessage with tool_calls=[{name: "EmailTriage", args: {...}}]
                                            │
                                            ▼
                            EmailTriage.model_validate(tool_calls[0].args)
                                            │
                                            ▼
                                  typed Pydantic instance
```

Same propose-execute mechanism as `03_agent_manual_ollama.py`'s tool loop — except the "tool" is your data class, not a function.

### 4. LCEL still works

`extractor` is a first-class `Runnable`. You get all the usual methods:

```python
extractor.invoke(email)                     # one
extractor.batch([email_1, email_2])         # parallel
async for chunk in extractor.astream(email):  # streaming (limited — needs full JSON)
    ...
chain = email_fetcher | extractor | priority_router   # composition
```

### 5. Reasoning + answer pattern

A sneaky-powerful trick: add a `reasoning: str` field *first* in the class. Pydantic preserves field order, so the model fills it before the structured fields — getting you chain-of-thought reasoning baked into the structured output, all in one LLM call.

```python
class ReviewAnalysis(BaseModel):
    reasoning: str = Field(description="Walk through your analysis step by step.")  # ← FIRST
    rating: int
    sentiment: Literal["positive", "mixed", "negative"]
```

---

## Production patterns this unlocks

| Pattern | Code shape |
|---|---|
| **Classification** | `class Result(BaseModel): label: Literal["spam", "promo", "work"]` |
| **Form-filling from unstructured text** | `Optional[str] = None` for fields that may be missing |
| **Multi-output extraction** | `items: list[Item]` — extract a list of typed sub-objects |
| **Confidence scoring** | `confidence: float = Field(ge=0, le=1)` |
| **Reasoning + answer** | Put a `reasoning: str` field *first* in the class |
| **Validated tool args** | Use Pydantic on user input → pass to the model |
| **Multi-modal extraction** | Pass an image as content; same schema works |

---

## Try this

1. **Add a `reasoning: str` field** as the *first* field in `EmailTriage`. Re-run. The answers get noticeably better because the model has to think out loud first.
2. **Make a field `Optional`** — e.g. `assigned_to: Optional[str] = None`. The model fills it when it can identify an assignee; leaves it `None` when it can't.
3. **Add nested models** — `class Sender(BaseModel): name: str; email: str` and `sender: Sender` inside `EmailTriage`. The model handles nesting natively.
4. **Add validators** — `from pydantic import field_validator`; reject malformed combinations server-side.
5. **Run a deliberately ambiguous email** — one where priority could be "low" or "medium". Watch what the model picks. Then tighten the `Field(description=...)` for `priority` to bias it the other way.

---

## Mental model in one line

> **A string is what an LLM produces by default. A *typed Pydantic object* is what your production code wants. `model.with_structured_output(SomeModel)` is the one-line bridge. The Pydantic class is the prompt; the validator is the contract.**

---

## FAQ

**Q: What's the difference between `PydanticOutputParser` and `with_structured_output`?**

A: They produce the same Pydantic objects via fundamentally different mechanisms.
- `PydanticOutputParser` (the old way) injects a JSON Schema into the *prompt text* and parses the model's text response with `json.loads`. Brittle — model may produce malformed JSON.
- `with_structured_output` (modern) puts the schema in the API's `tools` field and the model returns structured data via the tool-calling mechanism. The provider guarantees the shape.

Use `with_structured_output` whenever the LLM provider supports tool-calling (Ollama with llama3.2, OpenAI, Gemini all do). Use `PydanticOutputParser` only when forced to (older models that don't support tool-calling).

**Q: Do I have to use Pydantic, or can I use a TypedDict / dataclass?**

A: Pydantic is the cleanest path (gets you validation for free), but `with_structured_output` also accepts:
- A `TypedDict` (you get typing but no runtime validation)
- A JSON Schema dict (lowest level)
- A Python function — its signature becomes the schema

Pydantic is recommended for production because the `field_validator` decorator and runtime validation catch errors the LLM might sneak past type hints alone.

**Q: Does this work with every LLM provider?**

A: Ollama with llama3.2, OpenAI (GPT-4o+, GPT-4 turbo), Gemini, and Mistral support it. Older local models may need `PydanticOutputParser` instead. Check LangChain's compatibility matrix.

**Q: What happens if the model returns invalid JSON?**

A: With `with_structured_output`, the tool-calling layer enforces schema conformance. What *can* fail is the secondary Pydantic validation (e.g., your custom `field_validator` rejects a combination). In that case Pydantic raises `ValidationError` and you catch and retry, fall back, or surface the error.

**Q: How do I add a confidence score?**

A: Add a `confidence: float = Field(ge=0, le=1, description="Your confidence in the extraction, 0 to 1")` field. The model reports a self-assessed confidence. **Trust this only loosely** — LLM self-confidence is poorly calibrated; treat it as a relative ranking signal across answers, not absolute truth.

**Q: Can I get chain-of-thought reasoning out of this?**

A: Yes — put a `reasoning: str` field *first* in the class. Pydantic preserves field order; the model fills `reasoning` before the answer fields, giving you chain-of-thought in the same call. No extra LLM round-trip needed.

**Q: How does field order affect the output?**

A: Significantly. The model fills fields in the order they appear. So:
- Put `reasoning` or `analysis` fields *before* answer fields → forces thinking-out-loud
- Put `summary` *before* detail fields → forces top-down structure
- Put easy fields before hard fields → reduces variance on the hard ones

This is one of the few real "prompt engineering" levers left when using structured output.

**Q: How is this different from OpenAI's "JSON mode"?**

A: JSON mode just guarantees the response is *valid JSON* — not that it conforms to your schema. You still need a parser and validation. `with_structured_output` is one level higher: it guarantees the response matches *your specific schema*. Ollama uses tool-calling for structured output.

**Q: Can I use enums?**

A: Yes — `Literal[...]` is the recommended approach (cleanest, fewest moving parts). If you have a `enum.Enum`, that works too:

```python
from enum import Enum
class Priority(str, Enum):
    LOW = "low"; MEDIUM = "medium"; HIGH = "high"; URGENT = "urgent"

class Triage(BaseModel):
    priority: Priority
```

`Literal` is preferred unless you need the enum elsewhere in your codebase.

**Q: What about nested models?**

A: Fully supported. Compose Pydantic models like normal:

```python
class Sender(BaseModel):
    name: str
    email: str

class Triage(BaseModel):
    sender: Sender
    priority: Literal["low", "medium", "high"]
```

The model handles nesting natively. Deep nesting (3+ levels) sometimes degrades quality — keep it flat where possible.

**Q: Can I stream a structured output as it's being built?**

A: Partially. `JsonOutputParser` can yield partial dicts as the JSON streams in. `PydanticOutputParser` and `with_structured_output` cannot — they need the full JSON to validate against the schema. If you need progressive UI updates, use `JsonOutputParser` and validate at the end yourself.

---

## Related

- **The lifecycle deep-dive** — see `lessons/07-output-parsers.md` for the side-by-side comparison of what goes over the wire with `PydanticOutputParser` vs `with_structured_output` (schema in prompt text vs schema in `tools` field).
- **Reasoning + answer** — see `lessons/reference-agentic-patterns.md` (CoT pattern entry).
- **Validation in guardrails** — see `lessons/10-guardrails.md` — same Pydantic discipline applies to input validation.
- **The "schema is the prompt" insight** — most beginners miss this; the Field descriptions are doing 80% of the prompt-engineering work for you.
