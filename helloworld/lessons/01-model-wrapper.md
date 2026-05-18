# 01 — Model Wrapper

> **The lowest level: send one prompt to an LLM, get one response back.** Everything else in this course is built on top of this single call.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ▶ 01 MODEL WRAPPER  ◄═══════ YOU ARE HERE                ○ 13 system     ○ 16-19 Healthcare
                                                              design       ○ 20-22 Agriculture
  ○ 02 LCEL composition       (chain.py)                   ○ 14 red-team   ○ 23-25 Finance
  ○ 03 agent tool loop        (agent.py)                   ○ 15 AI UX      ○ 26-28 Vidya Karana
  ○ 04 prompt caching         (agent_lg_cached.py)                          ○ 29-32 Family AI
  ○ 05 structured output      (structured.py)
  ○ 06 parallel chains        (parallel.py)
  ○ 07 output parsers         (parsers.py)
  ○ 08 chatbot memory         (agent_chatbot.py)
  ○ 09 RAG                    (rag.py)
  ○ 10 guardrails             (safe_rag.py)
  ○ 11 production capstone    (production_chatbot.py)
  ○ 12 MCP                    (mcp_server.py, mcp_client.py)
```

**Why this lesson first:** every higher-level pattern — chains, agents, RAG, multi-agent systems — is sugar on top of `model.invoke()`. You can't reason about token costs, retries, or streaming until you understand the primitive.

---

## Files involved

| File | Role |
|---|---|
| [`hello.py`](../hello.py) | The minimal example: load env → instantiate `ChatAnthropic` → invoke → print |

---

## What problem it solves

LLM APIs vary by provider — OpenAI, Anthropic, Google, Mistral, Bedrock all have different SDKs, different request shapes, different response objects. Building on top of one ties your code to that vendor.

`ChatAnthropic` (and its sibling classes `ChatOpenAI`, `ChatGoogleGenerativeAI`, `ChatOllama`, etc.) **give you the same `.invoke()` / `.stream()` / `.batch()` interface across every provider**. Swap the import + the constructor and the rest of your code is unchanged.

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
│   ChatAnthropic (model wrapper)      │  ← uniform interface
│                                      │
│   • Loads ANTHROPIC_API_KEY from env │
│   • Formats your prompt to the       │
│     Anthropic Messages API shape     │
│   • Sends HTTP POST                  │
│   • Parses response into AIMessage   │
└──────────────────┬───────────────────┘
                   │ HTTPS / JSON
                   ▼
            api.anthropic.com
                   │
                   ▼
              Claude (model)
                   │
                   ▼
         AIMessage with .content,
         .usage_metadata, .tool_calls
```

Same diagram with `ChatOpenAI` → `api.openai.com` → GPT. Wire details differ; your call site doesn't.

---

## The concept

```python
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

model = ChatAnthropic(model="claude-sonnet-4-6")
response = model.invoke("Say hello in one short sentence.")
print(response.content)
```

Four lines:
1. Load `.env` (puts `ANTHROPIC_API_KEY` into `os.environ`)
2. Build a model wrapper bound to a specific Claude model
3. Send a prompt; get back an `AIMessage`
4. Read `.content` for the text

---

## The code

The whole file:

```python
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

# Swap to "claude-opus-4-7" for the most capable Claude model.
model = ChatAnthropic(model="claude-sonnet-4-6")

response = model.invoke("Say hello in one short sentence.")
print(response.content)
```

---

## Run it

```bash
cd helloworld
source .venv/bin/activate
python hello.py
```

Expected output (will vary):

```
Hello! Hope you're having a wonderful day! 😊
```

The actual response varies because the model is non-deterministic by default (`temperature` is the dial — see [lesson 02](02-lcel-composition.md)).

---

## Walk-through

### 1. `load_dotenv()` — credentials hygiene

Reads `.env` from the current directory and puts every `KEY=value` into `os.environ`. The Anthropic SDK auto-discovers `ANTHROPIC_API_KEY` from there. Your code never references the secret directly.

### 2. `ChatAnthropic(model="claude-sonnet-4-6")` — pick a model

The constructor binds:
- **Provider** (Anthropic, implicit in the class name)
- **Model version** (Sonnet 4.6 here; Opus 4.7 for the most capable; Haiku 4.5 for the cheapest)
- **Hyperparameters** (`temperature`, `max_tokens`, etc. — defaults are sensible)

The model is local Python state; no network call happens at construction. The first network call is `.invoke()`.

### 3. `.invoke("...")` — the call

Sends one HTTP request. The string is wrapped into a single-message conversation with role `user`. Returns an `AIMessage`.

### 4. The `AIMessage` you get back

```python
response.content              # str — the text response
response.usage_metadata       # {"input_tokens": ..., "output_tokens": ..., "total_tokens": ...}
response.response_metadata    # raw provider metadata
response.id                   # message id
response.tool_calls           # [] (relevant once we add tools — see lesson 03)
```

Most of the time you just want `.content`. But `usage_metadata` is the start of token accounting (see [lesson 04 — caching](04-prompt-caching.md)).

---

## Production patterns this unlocks

| Pattern | Code shape |
|---|---|
| Provider swap | Change `from langchain_openai import ChatOpenAI; model = ChatOpenAI(model="gpt-4o")` — no other changes |
| Local model fallback | `from langchain_ollama import ChatOllama; model = ChatOllama(model="llama3.2")` |
| Per-request hyperparameters | `model.with_config({"temperature": 0.7}).invoke(...)` |
| Token usage tracking | Sum `response.usage_metadata["total_tokens"]` per call → cost dashboard |
| Retries / fallbacks | `model.with_retry(...)` or `model.with_fallbacks([other_model])` |

---

## Try this

1. **Print the full response object** — `print(response)` instead of `response.content`. See `usage_metadata`, `response_metadata`, `id`.
2. **Change the prompt** — `"Explain LangChain in 2 sentences."` Same code, different answer.
3. **Swap models** — `ChatAnthropic(model="claude-opus-4-7")` for the smartest, or `claude-haiku-4-5-20251001` for the cheapest. Note the latency + token-cost differences.
4. **Set `temperature=0`** — `ChatAnthropic(..., temperature=0)`. Re-run twice. Output should be nearly identical (see [lesson 02](02-lcel-composition.md) for the caveats).

---

## Mental model in one line

> **`ChatAnthropic` is an LLM driver. `.invoke(prompt)` is one round-trip to Claude. Every higher-level pattern in this course is composition on top of this single call.**

---

## FAQ

**Q: Why use LangChain at all? Why not just call `anthropic.Anthropic().messages.create(...)`?**

A: Two reasons. (1) **Composition** — `.invoke()` is a `Runnable`, which means it composes with `|` into chains, parallels into `RunnableParallel`, etc. The raw SDK doesn't give you that. (2) **Provider portability** — switching from Claude to GPT-4o is one-line change. With the raw SDK, you rewrite the call sites. For one-off scripts, raw SDK is fine; for production codebases that may swap providers, the wrapper pays for itself fast.

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

**Q: How do I retry on transient failures (rate limits, 5xx)?**

A: `model.with_retry(stop_after_attempt=3, wait_exponential_jitter=True)` gives you exponential-backoff retries. Or wrap in your own retry logic if you need custom behavior.

**Q: What's the default temperature? Should I always set it?**

A: Defaults vary by provider; Anthropic defaults to 1.0 (high creativity). **For learning, tests, and structured outputs, set `temperature=0`**. For chat / creative writing, leave it default. For brainstorming, push it to 0.7-1.0. See lesson 02 for the caveats about "deterministic" at temperature=0.

**Q: Where does the model name string come from?**

A: From the provider's model registry. For Anthropic, see the [models page](https://docs.anthropic.com/en/docs/about-claude/models). Common values in this course: `claude-sonnet-4-6` (balanced), `claude-opus-4-7` (most capable), `claude-haiku-4-5-20251001` (cheapest/fastest).

**Q: My API key is in `.env` — is it safe?**

A: Yes, *if* `.env` is in `.gitignore` (it is in this repo — see [.gitignore](../.gitignore)). The `.env.example` template (no real key, just placeholder) is what gets committed.

**Q: Can I call multiple models from the same script?**

A: Absolutely. Each `ChatAnthropic(...)` is a separate object. You can have `sonnet = ChatAnthropic("claude-sonnet-4-6")` and `opus = ChatAnthropic("claude-opus-4-7")` in the same file and pick which to invoke. This is the foundation of the "model selection per role" pattern in [cost optimization](https://en.wikipedia.org/wiki/Model_selection) (covered later in Phase 1).

---

## Related

- **Next:** [02 — LCEL composition](02-lcel-composition.md) — compose `prompt | model | parser` into chains
- **For tokens & costs:** [04 — prompt caching](04-prompt-caching.md)
- **For multi-provider patterns:** model swap example in [11 — production capstone](11-production-capstone.md)
