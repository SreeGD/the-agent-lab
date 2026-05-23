# 02 — LCEL Composition

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/02_lcel_chain_ollama.py`.

> **Compose reusable components with the `|` pipe operator.** `prompt | model | parser` is LangChain's whole composition story. Once you see this, the rest of the framework collapses into variations on this pattern.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01 model wrapper          (01_model_wrapper.py)                   ○ 13 system     ○ 16-19 Healthcare
                                                              design       ○ 20-22 Agriculture
  ▶ 02 LCEL COMPOSITION  ◄═══════ YOU ARE HERE             ○ 14 red-team   ○ 23-25 Finance
                                                           ○ 15 AI UX      ○ 26-28 Vidya Karana
  ○ 03 agent tool loop        (03_agent_manual.py)                                    ○ 29-32 Family AI
  ○ 04 prompt caching         (04_prompt_caching.py)
  ○ 05 structured output      (05_structured_output.py)
  ○ 06 parallel chains        (06_parallel_chains.py)
  ○ 07 output parsers         (07_output_parsers.py)
  ○ 08 chatbot memory         (08_chatbot_memory.py)
  ○ 09 RAG                    (09_rag.py)
  ○ 10 guardrails             (10_guardrails.py)
  ○ 11 production capstone    (11_production_chatbot.py)
  ○ 12 MCP                    (12_mcp_server.py, 12_mcp_client.py)
```

**Why this lesson now:** Lesson 01 was one isolated call. Real systems chain multiple steps — template a prompt, call the model, parse the response. LCEL is the glue that makes that composition possible *and* portable across sync, async, streaming, and batch.

---

## Files involved

| File | Role |
|---|---|
| [`02_lcel_chain_ollama.py`](../ollama/02_lcel_chain_ollama.py) | Three-stage LCEL chain: prompt → model → parser |

---

## What problem it solves

Without LCEL, gluing LLM calls together looks like this:

```python
def explain(topic: str) -> str:
    prompt_text = f"Explain {topic} in 3 bullet points."   # 1. manual format
    response = ollama_client.chat(                          # 2. raw API call
        model="llama3.2",
        messages=[{"role": "user", "content": prompt_text}],
    )
    text = response['message']['content']                   # 3. manual unwrap
    return text
```

Three problems:
1. **Coupling** — prompt, model, output handling are tangled in one function
2. **No reusability** — to add a second step (e.g., translate to JSON), you copy-paste the boilerplate
3. **No reusable surfaces** — sync, async, streaming, batch all need separate implementations

LCEL replaces this with a **composition primitive**: the `|` operator. Each piece is a `Runnable`; pipe them together and you get a chain that supports all execution modes automatically.

---

## The analogy

**Unix pipes.**

```bash
cat log.txt | grep ERROR | awk '{print $4}' | sort -u
```

Each program does one thing, reads stdin, writes stdout. The pipe wires them together. The output of one is the input of the next. You can swap any stage without rewriting the others.

LCEL is Unix pipes for LLMs:

```python
chain = prompt | model | parser
```

Each stage is a `Runnable` (LangChain's "speaks the same I/O protocol"). The pipe wires them. Swap the model, swap the parser, add a stage — the rest of the chain doesn't know.

---

## Visual

```
   input dict                  PromptValue                AIMessage                   str
  {"topic": "X"}                                                                
      │                            │                          │                       │
      ▼                            ▼                          ▼                       ▼
  ┌─────────┐                ┌─────────┐               ┌─────────┐             ┌──────────┐
  │ prompt  │ ───────►       │  model  │ ───────►      │ parser  │ ───────►    │  result  │
  │ template│                │         │               │         │             │   str    │
  └─────────┘                └─────────┘               └─────────┘             └──────────┘

  ChatPromptTemplate          ChatOllama                StrOutputParser              

       │                                                                              │
       └──────────────────────  chain = prompt | model | parser  ─────────────────────┘
       
       chain.invoke({"topic": "X"})              # sync, single
       chain.stream({"topic": "X"})               # stream chunks as model generates
       chain.batch([{...}, {...}, {...}])         # parallel multi-call
       await chain.ainvoke({"topic": "X"})        # async
```

Same chain object. Four execution modes for free.

---

## The concept

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a concise technical explainer."),
    ("human", "Explain {topic} in 3 bullet points."),
])
model = ChatOllama(model="llama3.2", temperature=0)
parser = StrOutputParser()

chain = prompt | model | parser
chain.invoke({"topic": "LCEL"})
# → "- LCEL is LangChain Expression Language..."
```

Three stages composed with `|`. The input dict flows through; the output is a string.

---

## The code

The whole file:

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Ollama runs locally — no API key needed.
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a concise technical explainer for senior engineers."),
    ("human", "Explain {topic} like I'm a senior backend engineer, in 3 bullet points."),
])

model = ChatOllama(model="llama3.2", temperature=0)
parser = StrOutputParser()

chain = prompt | model | parser

result = chain.invoke({"topic": "LangChain"})
print(result)
```

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
cd helloworld
source .venv/bin/activate
python ollama/02_lcel_chain_ollama.py
```

Expected output (excerpt):

```
- **Composable orchestration framework** for chaining LLM calls...
- **Core abstractions:** Chains, Agents, Retrievers, Memory...
- **The real value is integrations + LCEL** — declaratively compose...
```

---

## Walk-through

### The pipeline, stage by stage

| Stage | Input | Output |
|---|---|---|
| `prompt` | `{"topic": "LangChain"}` | a list of messages with `{topic}` filled in |
| `model` | the messages | an `AIMessage` from Llama 3.2 |
| `parser` | the `AIMessage` | the plain `.content` string |

The `|` operator wires them together. The output of each step becomes the input of the next.

### Why this matters: every `Runnable` is composable

Each LangChain component implements a `Runnable` interface. That means **the same `chain` object** supports:

```python
chain.invoke({"topic": "RAG"})                           # sync, single
chain.batch([{"topic": "RAG"}, {"topic": "MCP"}])         # parallel
async for chunk in chain.astream({"topic": "agents"}):    # streaming
    print(chunk, end="", flush=True)
```

You write the chain once; sync / async / streaming / batch come for free.

### A note on `temperature`

`temperature=0` makes the model produce **the same answer for the same input** — almost. The defaults vary by provider; for tutorials, structured extraction, and tests, set `temperature=0`.

Caveat: even at `temperature=0`, outputs aren't bit-exact across runs. GPU non-determinism and tie-breaking introduce small variation. Treat `temperature=0` as **"strongly deterministic,"** not perfectly deterministic.

---

## Prompt vocabulary (you'll see these everywhere)

| Term | Meaning |
|---|---|
| **Prompt** | The generic input to the model — string or message list |
| **System prompt** | Persona/rules/style instructions, set once at conversation start |
| **Human prompt** | The user's actual question or input |
| **Prompt template** | A reusable string with `{variable}` placeholders |
| **`ChatPromptTemplate`** | Composes multiple role-specific templates into a full chat prompt |

---

## Production patterns this unlocks

| Pattern | Code shape |
|---|---|
| Reusable prompt + swap model | Define `prompt` once; pipe with different models for different routes |
| Parallel inference | `chain.batch([{...}, {...}, {...}])` — N parallel calls, one line |
| Streaming UX | `chain.stream(...)` returns chunks; render to UI as they arrive |
| Mid-pipeline transformations | Insert a `RunnableLambda(some_func)` anywhere in the chain |
| Parameterized chains | Templates with `{var}` placeholders → fill at runtime |

---

## Try this

1. **Change `{topic}` to something different** — same chain, different question. No code change beyond the input dict.
2. **Add a second variable** — `human` message becomes `"Explain {topic} in {n} bullets."`; pass `{"topic": "...", "n": 3}`.
3. **Run in batch** — `chain.batch([{"topic": "RAG"}, {"topic": "MCP"}, {"topic": "agents"}])`. Watch the parallel speedup.
4. **Swap to `temperature=0.8`** — same prompt, multiple runs. See the variance.
5. **Insert a lambda** — `chain = prompt | model | RunnableLambda(lambda m: m.content.upper()) | parser`. The text comes back uppercase.

---

## Mental model in one line

> **`prompt | model | parser` is a sequential pipe. The output of each stage flows into the next. Every LCEL component is a `Runnable`, so the chain supports sync, async, streaming, and batch automatically.**

---

## FAQ

**Q: What does `|` actually do under the hood?**

A: It's operator overloading. `Runnable.__or__(other)` returns a `RunnableSequence` that chains the two. So `prompt | model | parser` is really `RunnableSequence(prompt, RunnableSequence(model, parser))` — but the syntax is way nicer.

**Q: Can I put any Python function in a chain?**

A: Yes — wrap it in `RunnableLambda`:

```python
from langchain_core.runnables import RunnableLambda

def shout(text: str) -> str:
    return text.upper()

chain = prompt | model | StrOutputParser() | RunnableLambda(shout)
```

Now `shout()` participates in the chain like any other component.

**Q: What's the difference between `ChatPromptTemplate` and `PromptTemplate`?**

A: `ChatPromptTemplate` produces a **list of messages** (system + human + ...); `PromptTemplate` produces a **single string**. For chat-style models like Llama 3.2, use `ChatPromptTemplate`. For completion-style models, use `PromptTemplate`.

**Q: How do I see the rendered prompt before it's sent?**

A: Pipe only up to the prompt:

```python
rendered = prompt.invoke({"topic": "LangChain"})
print(rendered.to_messages())
# → [SystemMessage(...), HumanMessage(...)]
```

`prompt` is itself a `Runnable` — you can invoke it standalone.

**Q: Why do I need a parser? Can't I just use `chain.invoke()` and read `.content`?**

A: Yes, but only if you don't have a parser stage. With `prompt | model | parser`, the final result is whatever the parser returns. Without one, you get the raw `AIMessage` and have to call `.content` manually. The parser is sugar; pick one that returns the type you want (`str`, `dict`, Pydantic, etc.).

**Q: What if temperature=0 gives slightly different results on different machines?**

A: That's expected. GPU non-determinism + model-side tie-breaking = bit-different outputs across runs/machines even at temp=0. The variation is usually within a few output tokens. For *byte-exact* reproducibility, you need to cache responses (or use a deterministic local model).

**Q: How do I add error handling mid-chain?**

A: Use `chain.with_fallbacks([other_chain])` for fallback paths, or wrap individual stages with `RunnableLambda` that catch exceptions and route accordingly.

**Q: Is LCEL just for LLMs or can I chain other things?**

A: Anything that's a `Runnable`. Document loaders aren't Runnables (they're legacy), but retrievers, embeddings, vector stores, parsers, tool functions, and your own custom logic via `RunnableLambda` all are. Real RAG chains pipe retriever → prompt → model → parser.

**Q: What's the difference between `.invoke()` and `.invoke({...})` with a dict?**

A: The shape of the input depends on the first component in the chain. `ChatPromptTemplate.from_messages([...])` expects a dict (mapping variable names to values). `model.invoke("...")` accepts a raw string. The chain's input contract is whatever its *first* stage requires.

---

## Related

- **Previous:** [01 — Model wrapper](01-model-wrapper.md)
- **Next:** [03 — Agent tool loop](03-agent-tool-loop.md)
- **The parsers stage in detail:** [07 — Output parsers](../07-output-parsers.md)
- **Parallel composition:** [06 — Parallel chains](../06-parallel-chains.md)
