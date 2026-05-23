# 07 — Output Parsers

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_openai.ChatOpenAI`, model is `gpt-4o` (or `gpt-4o-mini`), and the API key env var is `OPENAI_API_KEY`. Code file: `labs/openai/07_output_parsers_openai.py`.

> **Convert the LLM's text response into a typed Python value.** `StrOutputParser`, `JsonOutputParser`, `PydanticOutputParser`, custom parsers — and how they differ from the modern `with_structured_output`.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01-04 (foundation)                                      ○ 13 system     ○ 16-19 Healthcare
  ✓ 05 structured output      (05_structured_output.py)                  design       ○ 20-22 Agriculture
  ✓ 06 parallel chains        (06_parallel_chains.py)                ○ 14 red-team   ○ 23-25 Finance
                                                           ○ 15 AI UX      ○ 26-28 Vidya Karana
  ▶ 07 OUTPUT PARSERS  ◄═══════ YOU ARE HERE                                ○ 29-32 Family AI

  ○ 08 chatbot memory         (08_chatbot_memory.py)
  ○ 09 RAG                    (09_rag.py)
  ○ 10 guardrails             (10_guardrails.py)
  ○ 11 production capstone    (11_production_chatbot.py)
  ○ 12 MCP                    (12_mcp_server.py, 12_mcp_client.py)
```

**Why this lesson now:** lesson 05 introduced `with_structured_output` — the modern way to get typed output. Parsers are the *older* generation of the same idea (text-based, not tool-call-based). Knowing both lets you pick the right tool, and parsers shine for streaming + simple types.

---

## Files involved

| File | Role |
|---|---|
| [`07_output_parsers_openai.py`](../../openai/07_output_parsers_openai.py) | Six parsers walked through against one movie review |

---

## What problem it solves

LLMs produce `AIMessage` objects whose `.content` is a string. Downstream code wants `str`, `dict`, `list`, `datetime`, or a Pydantic instance.

Output parsers convert `AIMessage → your target type` and also write the prompt instructions telling the LLM what format to produce. **They do double duty: pre-call (instructions) + post-call (parsing).**

---

## The analogy

A **shape-sorter toy**.

The LLM hands you a fistful of letters (text). You want a *square* (typed value). The parser is the wooden box with shape-cutouts — it only lets the right shape through, and it tells the LLM ("here's the shape I want") *before* the call so the LLM produces something that fits.

`StrOutputParser` = the box that accepts any shape (just unwraps).
`PydanticOutputParser` = the box with a custom-Pydantic-shaped hole.
`OutputFixingParser` = a box that, if the wrong shape arrives, asks a second LLM to reshape it.

---

## Visual

```
                        BEFORE call               AFTER call
                       ──────────────            ──────────────
                                                    
   prompt + format_instructions  →   LLM   →   AIMessage.content (text)
   (parser writes these)                                  │
                                                          ▼
                                                    parser.parse()
                                                          │
                                                          ▼
                                               typed Python value
                                              (str / dict / Pydantic / ...)
```

The parser participates in **both phases**: it writes some of the prompt (so the model produces parseable output) and parses the response (so your code gets typed values).

---

## The catalog

| Parser | Output | Use when |
|---|---|---|
| `StrOutputParser` | `str` | Just want `.content`; trivial |
| `JsonOutputParser` | `dict` | Want JSON — supports **streaming partial dicts** |
| `PydanticOutputParser(pydantic_object=M)` | `M` (Pydantic instance) | Older sibling of `with_structured_output` |
| `CommaSeparatedListOutputParser` | `list[str]` | Quick lists |
| `XMLOutputParser` | `dict` | XML-shaped responses |
| `DatetimeOutputParser` | `datetime` | When the LLM returns a date |
| `BooleanOutputParser` | `bool` | YES/NO classifiers |
| `EnumOutputParser(enum=E)` | enum member | Constrained vocabulary |
| `OutputFixingParser` | (wrapped parser's type) | **Error recovery via 2nd LLM call** |
| Custom (subclass `BaseOutputParser`) | any | Build your own format (YAML, etc.) |

---

## The format-instructions pattern (the killer idiom)

The parser writes part of the prompt — keeping the prompt + parser in sync automatically:

```python
parser = PydanticOutputParser(pydantic_object=Recipe)

prompt = PromptTemplate(
    template="Tell me about {dish}.\n{format_instructions}",
    input_variables=["dish"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

chain = prompt | model | parser
recipe: Recipe = chain.invoke({"dish": "carbonara"})
```

The parser's `get_format_instructions()` returns a chunk of text describing the JSON schema. That gets baked into the prompt. **Change the parser, the instructions update automatically.**

---

## Run it

```bash
python openai/07_output_parsers_openai.py
```

The file walks through 6 parsers on one movie review (Blade Runner 2049). Each section shows the format instructions (where applicable), the LLM call, and the parsed result.

---

## Streaming JSON — the underrated superpower

`JsonOutputParser` yields partial dicts as the model streams:

```python
async for chunk in chain.astream({"topic": "..."}):
    print(chunk)
```

Each yielded chunk is the JSON-so-far parsed into a (possibly partial) dict:

```
{}
{'rating': 9}
{'rating': 9, 'pros': []}
{'rating': 9, 'pros': ['Stunning cinematography...', 'Mes']}    ← mid-token!
{'rating': 9, 'pros': [...], 'cons': ['Length...']}             ← complete
```

Build a UI that fills in fields as the model generates. The parser handles partial JSON gracefully.

---

## Output parsers vs `with_structured_output`

| Aspect | `PydanticOutputParser` (older) | `with_structured_output` (modern) |
|---|---|---|
| How it works | Format instructions in prompt text; parse text response | Schema in `tools` API field; read tool-call args |
| Reliability | Brittle — model may emit malformed JSON, extra prose | High — provider-side enforcement |
| Provider support | Any LLM (works via prompting) | Requires tool-calling (Anthropic, OpenAI, Gemini) |
| Streaming | Limited (needs full JSON to validate) | Same limitation |
| Token efficiency | Slightly worse (instructions in prompt) | Slightly better (schema in `tools` field) |

**Rule of thumb:**
- Typed Pydantic objects? → **`with_structured_output(MyModel)`** ([lesson 05](05-structured-output.md))
- `str` / `list` / `dict` / `datetime`? → **output parser**
- Provider without tool-calling? → **output parser** is your only option
- Streaming partial JSON? → **`JsonOutputParser`**

---

## The lifecycle — what's sent and parsed where

```
        ┌───── BEFORE the call ─────┐      ┌──── AFTER the call ────┐
                                    │      │
prompt construction ───► HTTP ──►   │ LLM  │  ───► HTTP ───► parsing
(may include parser's                │      │                 (response
 format_instructions text)            │      │                  text or
                                    │      │                  tool_call)
                                    └──────┘
```

**The LLM only speaks text. Parsing is ALWAYS client-side. The LLM has no idea your parser exists.**

| Parser | What goes IN the prompt | What model produces | Parsing AFTER |
|---|---|---|---|
| `StrOutputParser` | (nothing extra) | text | `.content` access |
| `JsonOutputParser` | "respond with valid JSON" | JSON-as-text | `json.loads` |
| `PydanticOutputParser` | full JSON Schema (~1000+ tokens!) | JSON-as-text | `json.loads` + Pydantic |
| Custom YAML | "respond in YAML" | YAML-as-text | `yaml.safe_load` |
| `OutputFixingParser` | (wrapped parser's instructions) | Same | Wrapped parser, plus a fixup LLM call on failure |
| **`with_structured_output`** | **nothing in prompt (schema in `tools` field)** | **`tool_call` with structured dict** | **Pydantic validates dict** |

The last row eliminates `json.loads` entirely — that's the point of failure parsers have to fight.

---

## Custom parsers — the escape hatch

Subclass `BaseOutputParser`:

```python
from langchain_core.output_parsers import BaseOutputParser
import yaml

class YamlOutputParser(BaseOutputParser):
    def parse(self, text: str) -> dict:
        return yaml.safe_load(text)

    def get_format_instructions(self) -> str:
        return "Respond in valid YAML. Use 2-space indentation."
```

That's the entire required interface: `parse` and `get_format_instructions`. Now it pipes into chains like any built-in parser.

---

## Try this

1. **Replace `StrOutputParser` with `JsonOutputParser`** in `02_lcel_chain_openai.py` — the chain now returns a dict if the prompt asks for JSON.
2. **Build a custom YAML parser** — 10 lines; verify it pipes into a chain.
3. **Wrap a parser with `OutputFixingParser`** — feed it deliberately malformed JSON and watch the second LLM call repair it.
4. **Compare `PydanticOutputParser` vs `with_structured_output`** on the same task — see the token-efficiency difference in the prompt.

---

## Mental model in one line

> **An output parser is the adapter between text (what the LLM emits) and types (what your code wants). Like Pydantic for unstructured text — except it also teaches the LLM how to produce text the parser can read.**

---

## FAQ

**Q: I'm always going to want Pydantic. Should I just always use `with_structured_output`?**

A: For Pydantic targets, yes. Output parsers exist for: (a) simpler types where Pydantic is overkill (lists, datetimes, bools), (b) providers without tool-calling, (c) streaming partial output, (d) custom formats your domain needs (YAML, XML, your own).

**Q: How does `get_format_instructions()` know what to say?**

A: Each parser hardcodes its instructions. `PydanticOutputParser` introspects the Pydantic class and emits its JSON Schema as the instruction. `CommaSeparatedListOutputParser` returns a fixed string about commas. You can read each parser's source to see exactly what gets injected.

**Q: Can I write a parser that doesn't need format instructions?**

A: Yes — return an empty string from `get_format_instructions()`. `StrOutputParser` does this. Use when the LLM's default output already matches what you want.

**Q: Why does `JsonOutputParser` support streaming but `PydanticOutputParser` doesn't?**

A: JSON parsing can handle partial input (a valid prefix of a JSON object is still parseable). Pydantic needs the *complete* object to validate against the schema. Stream JSON for UI; validate at the end if Pydantic typing matters.

**Q: What's `OutputFixingParser`'s cost?**

A: One *extra* LLM call when the wrapped parser fails. Use sparingly — for the long tail of weird outputs. If you're seeing >5% failure rates, **fix the prompt** instead.

**Q: How does `with_structured_output` not need a parser at all?**

A: It uses the provider's tool-calling API. The model returns a structured dict in the response's `tool_calls` field — already validated server-side. LangChain just runs `Pydantic.model_validate(args)`. There's no text-parsing step.

**Q: What's `RetryOutputParser` vs `OutputFixingParser`?**

A: Both retry on failure.
- `OutputFixingParser` sends the broken output to a second LLM call asking it to **fix** the output.
- `RetryOutputParser` re-sends the **original prompt** with the parse error appended.
`OutputFixingParser` is usually preferred — it understands the output it's repairing.

**Q: Where do parsers fit in LangSmith / observability?**

A: They're `Runnable`s, so every parse shows up as a node in LangSmith traces. The instruction text appears in the prompt; the parsing step shows the AIMessage in → typed value out.

---

## Related

- **Previous:** [06 — Parallel chains](06-parallel-chains.md)
- **Next:** [08 — Chatbot memory](08-chatbot-memory.md)
- **Modern alternative for typed output:** [05 — Structured output](05-structured-output.md)
- **Where parsers shine in production:** chains with simple-type returns; streaming UIs
