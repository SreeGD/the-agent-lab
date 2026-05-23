# 01 — Model Wrapper

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/01_model_wrapper_ollama.py`.

> **The lowest level: send one prompt to an LLM, get one response back.** Everything else in this course is built on top of this single call.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ▶ 01 MODEL WRAPPER  ◄═══════ YOU ARE HERE                ○ 13 system     ○ 16-19 Healthcare
                                                              design       ○ 20-22 Agriculture
  ○ 02 LCEL composition       (02_lcel_chain.py)                   ○ 14 red-team   ○ 23-25 Finance
  ○ 03 agent tool loop        (03_agent_manual.py)                   ○ 15 AI UX      ○ 26-28 Vidya Karana
  ○ 04 prompt caching         (04_prompt_caching.py)                          ○ 29-32 Family AI
  ○ 05 structured output      (05_structured_output.py)
  ○ 06 parallel chains        (06_parallel_chains.py)
  ○ 07 output parsers         (07_output_parsers.py)
  ○ 08 chatbot memory         (08_chatbot_memory.py)
  ○ 09 RAG                    (09_rag.py)
  ○ 10 guardrails             (10_guardrails.py)
  ○ 11 production capstone    (11_production_chatbot.py)
  ○ 12 MCP                    (12_mcp_server.py, 12_mcp_client.py)
```

**Why this lesson first:** every higher-level pattern — chains, agents, RAG, multi-agent systems — is sugar on top of `model.invoke()`. You can't reason about token costs, retries, or streaming until you understand the primitive.

---

## Files involved

| File | Role |
|---|---|
| [`01_model_wrapper_ollama.py`](../ollama/01_model_wrapper_ollama.py) | The minimal example: instantiate `ChatOllama` → invoke → print |

---

## What problem it solves

LLM APIs vary by provider — OpenAI, Ollama, Google, Mistral, Bedrock all have different SDKs, different request shapes, different response objects. Building on top of one ties your code to that vendor.

`ChatOllama` (and its sibling classes `ChatOpenAI`, `ChatGoogleGenerativeAI`, `ChatMistralAI`, etc.) **give you the same `.invoke()` / `.stream()` / `.batch()` interface across every provider**. Swap the import + the constructor and the rest of your code is unchanged.

---

## The analogy

A **database driver**.

You don't write Postgres-specific code in your service layer; you talk to a connection object (`psycopg2.connect`, `asyncpg.create_pool`) that exposes a common interface — `execute`, `fetch`, `commit`. The driver handles wire-protocol differences.

LangChain's model wrappers are LLM drivers. `model.invoke(prompt)` is the equivalent of `cursor.execute(query)` — same call across providers, vendor-specific complexity hidden underneath.

---

## Visual

```
Your code
   │
   │   model.invoke("Say hello")
   ▼
┌──────────────────────────────────────┐
│   ChatOllama (model wrapper)         │  ← uniform interface
│                                      │
│   • No API key needed                │
│   • Formats your prompt to the       │
│     Ollama API shape                 │
│   • Sends HTTP POST                  │
│   • Parses response into AIMessage   │
└──────────────────┬───────────────────┘
                   │ HTTP / JSON
                   ▼
            localhost:11434
                   │
                   ▼
          Llama 3.2 (model)
                   │
                   ▼
         AIMessage with .content,
         .usage_metadata, .tool_calls
```

Same diagram with `ChatOpenAI` → `api.openai.com` → GPT. Wire details differ; your call site doesn't.

---

## The concept

```python
from langchain_ollama import ChatOllama

model = ChatOllama(model="llama3.2")
response = model.invoke("Say hello in one short sentence.")
print(response.content)
```

Three lines:
1. Build a model wrapper bound to a specific Llama 3.2 model (no API key needed — Ollama runs locally)
2. Send a prompt; get back an `AIMessage`
3. Read `.content` for the text

---

## The code

The whole file:

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
# Swap to any model you have pulled, e.g. "llama3.2:3b" for a smaller variant.
model = ChatOllama(model="llama3.2")

response = model.invoke("Say hello in one short sentence.")
print(response.content)
```

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
cd helloworld
source .venv/bin/activate
python ollama/01_model_wrapper_ollama.py
```

Expected output (will vary):

```
Hello! Hope you're having a wonderful day! 😊
```

The actual response varies because the model is non-deterministic by default (`temperature` is the dial — see [lesson 02](../02-lcel-composition.md)).

---

## Walk-through

### 1. `ChatOllama(model="llama3.2")` — pick a model

The constructor binds:
- **Provider** (Ollama, implicit in the class name)
- **Model version** (`llama3.2` here; other variants like `llama3.2:3b` for faster/lighter)
- **Hyperparameters** (`temperature`, `max_tokens`, etc. — defaults are sensible)

The model is local Python state; no network call happens at construction. The first network call is `.invoke()`.

### 2. `.invoke("...")` — the call

Sends one HTTP request to the local Ollama server. The string is wrapped into a single-message conversation with role `user`. Returns an `AIMessage`.

### 3. The `AIMessage` you get back

```python
response.content              # str — the text response
response.usage_metadata       # {"input_tokens": ..., "output_tokens": ..., "total_tokens": ...}
response.response_metadata    # raw provider metadata
response.id                   # message id
response.tool_calls           # [] (relevant once we add tools — see lesson 03)
```

Most of the time you just want `.content`. But `usage_metadata` is the start of token accounting (see [lesson 04 — caching](../04-prompt-caching.md)).

---

## Production patterns this unlocks

| Pattern | Code shape |
|---|---|
| Provider swap | Change `from langchain_openai import ChatOpenAI; model = ChatOpenAI(model="gpt-4o")` — no other changes |
| Cloud model fallback | `from langchain_openai import ChatOpenAI; model = ChatOpenAI(model="gpt-4o")` |
| Per-request hyperparameters | `model.with_config({"temperature": 0.7}).invoke(...)` |
| Token usage tracking | Sum `response.usage_metadata["total_tokens"]` per call → usage dashboard |
| Retries / fallbacks | `model.with_retry(...)` or `model.with_fallbacks([other_model])` |

---

## Try this

1. **Print the full response object** — `print(response)` instead of `response.content`. See `usage_metadata`, `response_metadata`, `id`.
2. **Change the prompt** — `"Explain LangChain in 2 sentences."` Same code, different answer.
3. **Swap models** — `ChatOllama(model="llama3.2:3b")` for a smaller variant. Note the latency differences.
4. **Set `temperature=0`** — `ChatOllama(..., temperature=0)`. Re-run twice. Output should be nearly identical (see [lesson 02](../02-lcel-composition.md) for the caveats).

---

## Mental model in one line

> **`ChatOllama` is an LLM driver. `.invoke(prompt)` is one round-trip to Llama 3.2. Every higher-level pattern in this course is composition on top of this single call.**

---

## FAQ

**Q: Why use LangChain at all? Why not just call the Ollama API directly?**

A: Two reasons. (1) **Composition** — `.invoke()` is a `Runnable`, which means it composes with `|` into chains, parallels into `RunnableParallel`, etc. The raw API doesn't give you that. (2) **Provider portability** — switching from Llama 3.2 to GPT-4o is one-line change. With the raw API, you rewrite the call sites. For one-off scripts, raw API is fine; for production codebases that may swap providers, the wrapper pays for itself fast.

**Q: What's the difference between `.invoke()`, `.stream()`, and `.batch()`?**

A: All three are part of the `Runnable` interface.
- `.invoke(input)` — one input → one output, synchronously
- `.stream(input)` — one input → yields chunks as the model generates (token streaming)
- `.batch([inputs])` — many inputs → many outputs, parallel under the hood
There are also async versions (`.ainvoke`, `.astream`, `.abatch`) for `await`-based code (see lesson on Streaming + Web UI).

**Q: How do I see what was actually sent over the wire?**

A: Two options:
1. `LANGCHAIN_TRACING_V2=true` + a LangSmith account → captures every call with prompt + response
2. Inspect `response.response_metadata` for echo data the provider returned
3. Run with `LANGCHAIN_VERBOSE=true` env var to print to stderr

**Q: How do I retry on transient failures?**

A: `model.with_retry(stop_after_attempt=3, wait_exponential_jitter=True)` gives you exponential-backoff retries. Or wrap in your own retry logic if you need custom behavior.

**Q: What's the default temperature? Should I always set it?**

A: Defaults vary by provider; Ollama defaults vary by model. **For learning, tests, and structured outputs, set `temperature=0`**. For chat / creative writing, leave it default. For brainstorming, push it to 0.7-1.0. See lesson 02 for the caveats about "deterministic" at temperature=0.

**Q: Where does the model name string come from?**

A: From the Ollama model library. Run `ollama list` to see what you have installed. Common values in this course: `llama3.2` (balanced), `llama3.2:3b` (fastest/smallest). Pull new models with `ollama pull <model>`.

**Q: Ollama is running locally — is there any security concern?**

A: No API key is needed, which is actually simpler. Ollama runs as a local server on `localhost:11434`. As long as you're not exposing that port externally, your data never leaves your machine.

**Q: Can I call multiple models from the same script?**

A: Absolutely. Each `ChatOllama(...)` is a separate object. You can have `fast = ChatOllama("llama3.2:3b")` and `smart = ChatOllama("llama3.2")` in the same file and pick which to invoke. This is the foundation of the "model selection per role" pattern (covered later in Phase 1).

---

## Related

- **Next:** [02 — LCEL composition](../02-lcel-composition.md) — compose `prompt | model | parser` into chains
- **For tokens & costs:** [04 — prompt caching](../04-prompt-caching.md)
- **For multi-provider patterns:** model swap example in [11 — production capstone](../11-production-capstone.md)
