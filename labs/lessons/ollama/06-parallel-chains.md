# 06 — Parallel Chains (LCEL fan-out)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/06_parallel_chains_ollama.py`.

> **Run several chains *at the same time* against the same input, collect their results into one dict.** `RunnableParallel` is the second LCEL primitive (after the `|` pipe) and the foundation of map-reduce, multi-aspect analysis, and multi-model ensembling.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01 model wrapper          (01_model_wrapper.py)                   ○ 13 system     ○ 16-19 Healthcare
  ✓ 02 LCEL composition       (02_lcel_chain.py)                       design       ○ 20-22 Agriculture
  ✓ 03 agent tool loop        (03_agent_manual.py, 03_agent_framework.py)      ○ 14 red-team   ○ 23-25 Finance
  ✓ 04 prompt caching         (04_prompt_caching.py)         ○ 15 AI UX      ○ 26-28 Vidya Karana
  ✓ 05 structured output      (05_structured_output.py)                               ○ 29-32 Family AI

  ▶ 06 PARALLEL CHAINS  ◄═══════ YOU ARE HERE

  ○ 07 output parsers         (07_output_parsers.py)
  ○ 08 chatbot memory         (08_chatbot_memory.py)
  ○ 09 RAG                    (09_rag.py)
  ○ 10 guardrails             (10_guardrails.py)
  ○ 11 production capstone    (11_production_chatbot.py)
  ○ 12 MCP                    (12_mcp_server.py, 12_mcp_client.py)
```

**Why this lesson now:** by lesson 5 you can build sophisticated linear chains. Real systems often need to fan *out* — run multiple analyses on the same input concurrently. This lesson adds the parallel primitive.

---

## Files involved

| File | Role |
|---|---|
| [`06_parallel_chains_ollama.py`](../ollama/06_parallel_chains_ollama.py) | Three parallel chains explaining the same topic for different audiences — with timing showing the speedup |

---

## What problem it solves

Many real tasks need **the same input processed multiple ways**:
- Classify a document AND summarize it AND extract entities
- Translate one text into 5 languages
- Query 3 different vector stores in parallel, merge results
- Get answers from 3 different models, take majority vote

Without parallel composition: you call each chain in sequence, total time = sum of all individual times.

With `RunnableParallel`: each chain runs in its own thread/coroutine, total time ≈ slowest chain.

For 3 chains taking 2-6 seconds each: **wall clock drops from ~12 s to ~6 s** — same code, one primitive.

---

## The analogy

A **kitchen with multiple burners**.

Sequential cook: you boil pasta, then make sauce, then sear chicken — 30 min total. The chicken sits cold while sauce simmers.

Parallel cook: all three start at once on different burners. Done in 12 min (= time of the slowest item, which is the chicken).

LCEL's `|` is the cutting-board step ordering (one task → next task). `RunnableParallel` is the multi-burner step (run independent tasks concurrently). Real production chains use both.

---

## Visual

```
                    ┌──► eli5_chain  ── "Explain like I'm 5"
input = {topic:"X"} ─┼──► senior_chain ── "Explain to a senior engineer"
                    └──► haiku_chain  ── "Write a haiku"
                                              │
                                              ▼
                  {"eli5": "...", "senior": "...", "haiku": "..."}
                  
                  Wall-clock = max(branches), not sum
```

Each branch runs in parallel (thread pool for sync, asyncio.gather for async). Result is a merged dict.

---

## The concept

```python
from langchain_core.runnables import RunnableParallel

eli5_chain   = prompt_eli5   | model | parser
senior_chain = prompt_senior | model | parser
haiku_chain  = prompt_haiku  | model | parser

parallel = RunnableParallel(
    eli5=eli5_chain,
    senior=senior_chain,
    haiku=haiku_chain,
)

result = parallel.invoke({"topic": "prompt caching"})
# → {"eli5": "...", "senior": "...", "haiku": "..."}
```

Or the **dict-literal shorthand** (idiomatic in production):

```python
parallel = {"eli5": eli5_chain, "senior": senior_chain, "haiku": haiku_chain}
# LCEL auto-promotes a dict to RunnableParallel when it's piped into the next stage
chain = parallel | combiner
```

---

## The code

The whole `06_parallel_chains_ollama.py`:

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

def make_chain(template: str):
    prompt = ChatPromptTemplate.from_messages([("human", template)])
    return prompt | model | StrOutputParser()

eli5_chain   = make_chain("Explain {topic} like I'm 5...")
senior_chain = make_chain("Explain {topic} to a senior backend engineer...")
haiku_chain  = make_chain("Write a haiku about {topic}...")

parallel = RunnableParallel(eli5=eli5_chain, senior=senior_chain, haiku=haiku_chain)

# Sequential baseline
for chain in [eli5_chain, senior_chain, haiku_chain]:
    chain.invoke({"topic": "prompt caching"})   # times sum up

# Parallel run — same chains, fan out
result = parallel.invoke({"topic": "prompt caching"})  # ≈ max time
```

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/06_parallel_chains_ollama.py
```

Expected output (real numbers from a clean run):

```
=== SEQUENTIAL ===
  eli5:    3.94s
  senior:  6.40s
  haiku:   1.29s
  TOTAL: 11.63s  (sum)

=== PARALLEL ===
  TOTAL:   6.59s  (≈ max)
  Speedup: 1.77×
```

---

## Walk-through

### Why the speedup is 1.77× and not 3×

Three reasons in order of impact:

1. **Unequal branch durations** — parallel time = `max(branches)`. The haiku branch finished in 1.3s and sat idle waiting for `senior` (6.4s) to finish.
2. **Coordination overhead** — `RunnableParallel` wraps each branch in a thread (sync mode) or task (async mode). Small fixed cost.
3. **Local inference variance** — three concurrent requests to the local Ollama server compete for GPU resources; under load they may serialize.

To get closer to 3×: make the branches **similar in size**, run them **async**, use a model with consistent latency.

### The async path is faster

LLM calls are I/O-bound, not CPU-bound. For I/O-bound parallelism, **async beats threads**:

```python
result = await parallel.ainvoke({"topic": "prompt caching"})
```

No thread-pool overhead, just `asyncio.gather()`. If you're inside FastAPI or any async runtime, always use `.ainvoke()`.

---

## Production patterns this unlocks

| Pattern | Branches |
|---|---|
| **Multi-aspect analysis** | Classify + summarize + extract entities + score sentiment, all on the same input |
| **Multi-language translation** | One branch per target language, single source |
| **Retrieval ensembles** | Query 3 vector stores or retrievers, merge results |
| **Map-reduce summarization** | Summarize each chunk in parallel, then a final reducer |
| **A/B prompt testing** | Same input, two prompts, compare outputs |
| **Multi-model voting** | Same prompt to Llama 3.2 + GPT + Gemini, take majority |

The last one is especially powerful with LangChain's model abstraction — swap the model in each branch and you've got cross-provider ensembling in 5 lines.

---

## Try this

1. **Add a 4th branch** — e.g. `tweet_chain` ("write a 280-char tweet about {topic}"). Watch parallel time stay roughly the same; sequential time grows.
2. **Swap to async** — change `.invoke()` to `await .ainvoke()` (wrap in `asyncio.run`). Compare wall-clock to the sync version.
3. **Add a synthesizer step** — pipe the merged dict into a final chain that combines the three perspectives:
   ```python
   chain = parallel | synthesizer
   ```
   This is the classic **map-reduce** shape: parallel branches (map) → single combiner (reduce).
4. **Multi-model voting** — three branches with the same prompt against three different models. Compare answers.

---

## Mental model in one line

> **`prompt | model | parser` is a sequential pipe (one stage feeds the next). `{"a": chain_a, "b": chain_b}` is a parallel fan-out (one input, many simultaneous chains, merged output). Together they cover almost every LCEL pattern.**

---

## FAQ

**Q: What's the difference between `RunnableParallel(...)` and `{"k1": chain1}`?**

A: They produce the same thing. LCEL auto-promotes a plain dict into a `RunnableParallel` when it's piped into the next stage. The explicit form is more discoverable; the dict form is more idiomatic in production code. Pick whichever reads more clearly to you.

**Q: What if I need shared state between branches?**

A: Don't use `RunnableParallel` — that pattern is sequential by nature. Either chain them with `|` so the output of one feeds the next, or use LangGraph's `StateGraph` for richer state flows (covered in custom-graph lessons).

**Q: Does parallel work with `chain.batch()`?**

A: Different concept. `RunnableParallel` runs **different chains in parallel** on the same input. `.batch([inputs])` runs **the same chain in parallel** on different inputs. You can combine them.

**Q: How many branches can I have?**

A: No hard limit, but many concurrent branches will compete for local GPU resources with Ollama. For very large fan-outs, consider running branches sequentially or using a remote model provider.

**Q: What happens if one branch fails?**

A: By default, the whole `.invoke()` raises. To make individual failures tolerable, wrap each branch with `chain.with_fallbacks([...])` or `chain.with_retry(...)`.

**Q: Can I have different output types per branch?**

A: Yes. Each branch can output anything (str, dict, Pydantic). The result is a dict keyed by branch name with each value's type.

**Q: Does parallel help with non-LLM work too?**

A: Yes, anywhere you have multiple `Runnable`s that can run independently. Combine an embedding step + a retrieval step + a metadata lookup — all `Runnable`s, all parallel.

**Q: Is parallel always cheaper?**

A: With Ollama there are no API costs — parallel and sequential both run locally for free. Parallel saves *time*, though local GPU contention may reduce the speedup compared to a cloud provider.

---

## Related

- **Previous:** [05 — Structured output](05-structured-output.md)
- **Next:** [07 — Output parsers](../07-output-parsers.md)
- **Map-reduce extension:** see "Try this" #3 above
- **Used in:** [09 — RAG](../09-rag.md) (parallel retrieval), [11 — Production capstone](../11-production-capstone.md)
