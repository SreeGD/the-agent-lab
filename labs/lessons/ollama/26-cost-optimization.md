# 26 — Cost Optimization (Session 15)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic and patterns are largely identical to the Anthropic version. What differs: Ollama has no API cost — inference runs locally on your hardware. The levers shift: model selection (different sizes), prompt compression, and parallel batching still apply; cache_control and the Batches API are Anthropic-specific features with no direct Ollama equivalent. Code file: `labs/ollama/26_cost_optimization_ollama.py`.

> **The four levers that compound.** Model selection per role, prompt compression, parallel batching, and local inference efficiency. Each is measurable. With Session 14's eval as the quality floor, you can pull each lever and *prove* quality didn't move.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-14 (foundation + RAG + eval)                        Track F: PRODUCTION
                                                             ✓ Session 14: Evaluation
                                                             ▶ Session 15: COST OPTIMIZATION  ◄ HERE
                                                             ○ Session 16: Streaming
                                                             ○ Session 17: Deploy + Observability
                                                           Track G: ○ Architect Skills
```

**Why this lesson now:** You can't claim an optimization is "free" without showing eval scores didn't move. Session 14 gave us that gate. Now we wield it.

---

## File involved

| File | Role |
|---|---|
| [`26_cost_optimization_ollama.py`](../ollama/26_cost_optimization_ollama.py) | Three levers in one runnable file: model selection per role (llama3.2 vs llama3.2:3b), prompt compression (verbose vs compact), and parallel chain.batch() for local throughput comparison. |

---

## Ollama-specific notes

With Ollama there is **no API cost** — inference time is the metric that matters. The optimization goal shifts:

- **Model selection** — use smaller/faster models for cheap roles (same discipline, measured in latency instead of dollars)
- **Prompt compression** — fewer tokens means shorter prefill and faster inference
- **Batching** — `chain.batch([...])` parallelizes local inference requests
- **Cache_control / Batches API** — these are Anthropic-specific. With Ollama, there is no prompt cache mechanism. Prompt compression (Lever 3) is the best substitute.

---

## What problem it solves

Most AI efficiency problems have the same shape:
- Expensive model used for cheap roles (using full llama3.2 for binary classifications)
- System prompts bloated with redundant instructions
- Everything running sequentially when requests could be parallel

Each is a measurable, fixable issue. The efficiency savings on real workloads are often **2-5x** with **zero quality impact** — provable via the eval harness from Session 14.

---

## The analogy

**A power bill audit.**

Most teams pay 2-5x what they should for GPU time because nobody ever audited:
- Are we on the right model? (model selection — use `llama3.2:3b` for guardrail judges)
- Are we leaving lights on in empty rooms? (verbose prompts = paying for tokens nobody reads)
- Are we running jobs sequentially when they could be parallel? (sequential API calls)

Fix the three and inference time drops by a significant factor. Same workload, just smarter execution.

---

## Visual

```
        NAIVE SETUP                              OPTIMIZED SETUP
        ───────────                              ───────────────

   ┌──────────────────┐                     ┌──────────────────┐
   │ llama3.2 for     │                     │ llama3.2:3b for  │   ← Lever 1
   │ every role       │                     │ cheap roles      │     ~3x faster
   └─────────┬────────┘                     └─────────┬────────┘
             │                                        │
             ▼                                        ▼
   ┌──────────────────┐                     ┌──────────────────┐
   │ Verbose prompt   │                     │ Compressed       │   ← Lever 2
   │ 300+ tokens of   │                     │ prompt           │     ~2-3x fewer
   │ filler           │                     │ 80 tokens        │     input tokens
   └─────────┬────────┘                     └─────────┬────────┘
             │                                        │
             ▼                                        ▼
   ┌──────────────────┐                     ┌──────────────────┐
   │ Sequential calls │                     │ chain.batch()    │   ← Lever 3
   │ for everything   │                     │ for parallel     │     throughput
   └─────────┬────────┘                     └─────────┬────────┘
             │                                        │
             ▼                                        ▼
    slower inference                         faster inference
```

---

## Concept walk-through

### Lever 1 — Model selection per role

Not every LLM call is the same task.

| Role | Task type | Right model |
|---|---|---|
| Final answer to user | Generation, reasoning | `llama3.2` (full) |
| Retrieval grader (CRAG) | Ternary classification | **`llama3.2:3b`** |
| Output classifier | Binary classification | **`llama3.2:3b`** |
| Structured extraction (entities) | JSON shape generation | **`llama3.2:3b`** |
| Query rewriter | Short text generation | **`llama3.2:3b`** |
| Reflection / planner | Multi-step reasoning | `llama3.2` (full) |

The rule: **use the smallest model that gets the right answer on your eval set.** The full model is needed for the hard parts. `llama3.2:3b` handles the rest at ~3x lower latency.

```python
from langchain_ollama import ChatOllama

# Full model for hard roles
main_model = ChatOllama(model="llama3.2", temperature=0)

# Smaller model for cheap roles
judge_model = ChatOllama(model="llama3.2:3b", temperature=0)
```

### Lever 2 — Prompt compression

Most system prompts are bloated tutorial templates. The pattern:

**Before** (302 tokens):
```
You are a helpful and knowledgeable assistant who provides accurate answers...
IMPORTANT INSTRUCTIONS — PLEASE READ CAREFULLY:
- You should ONLY use the provided context to answer questions
- Do not use your background knowledge or training data
- If the context does not contain the answer, you should say so explicitly
- Be concise in your responses, ideally 2-3 sentences
- Use clear and simple language
- Avoid being overly verbose or repeating yourself
...
```

**After** (81 tokens):
```
Answer using ONLY the provided context. If the context lacks the answer,
say so. 2-3 sentences, plain text, no preamble or summary.
```

73% fewer tokens. Identical answers in the live run.

**Compression rules:**
1. Strip filler ("please read carefully", "make sure")
2. Collapse multi-sentence rules into one sentence with semicolons
3. Drop "do not" lists when an affirmative covers them ("plain text" replaces "no markdown", "no formatting")
4. Drop politeness ("kindly", "if you would")
5. Verify with eval. **Always.** Compression that drops quality is just damage.

### Lever 3 — Parallel batching with chain.batch()

For multiple independent requests (eval runs, document classification, bulk summarization), `chain.batch([...])` submits them in parallel to Ollama:

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

model = ChatOllama(model="llama3.2:3b", temperature=0)
prompt = ChatPromptTemplate.from_template("Grade this chunk: {chunk}")
chain = prompt | model

# Sequential (slow):
results = [chain.invoke({"chunk": c}) for c in chunks]

# Parallel (fast):
results = chain.batch([{"chunk": c} for c in chunks])
```

`chain.batch()` submits all requests concurrently; Ollama processes as many as its concurrency allows. For eval runs with 120 judge calls, this is the biggest throughput lever.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` and `ollama pull llama3.2:3b` must have been run first.

```bash
python ollama/26_cost_optimization_ollama.py
```

Takes ~30-60 seconds depending on hardware. No API cost — Ollama runs locally.

---

## Production patterns

### The compound effect

These levers stack multiplicatively:

| Stack | Multiplier on naive |
|---|---|
| Model: llama3.2 → llama3.2:3b for classifiers | ~3x faster |
| Compression: 300-token prompt → 80-token prompt | ~2x fewer tokens |
| Batch: sequential → parallel | ~3-4x throughput (hardware-dependent) |
| **Compound** | **~10-20x** |

A naive grading pipeline that takes 120 seconds becomes ~6-12 seconds. **Same quality.** Verifiable via eval.

### Decision flow for a new workload

```
1. Is this a generation/reasoning task or a classification/extraction?
   GEN   → llama3.2 (full)
   CLASS → llama3.2:3b (verify on eval first)

2. Has your system prompt been reviewed for compression in the last 6 months?
   NO  → review it. Target 50%+ reduction. Verify on eval.

3. Are these requests independent of each other?
   YES → always chain.batch() (significant throughput gain)
   NO  → sequential is fine
```

### Where compression bites you

- **Few-shot examples**: removing them often drops quality on edge cases. Verify carefully.
- **Format constraints**: "respond in JSON" can't be compressed below itself.
- **Persona / tone instructions**: "you are friendly" is two tokens; can't be shorter.
- **Multi-turn agents**: the agent's tools description is hard to compress without losing precision.

### Monitoring inference time

Log per-call:
- `model` name
- `input_tokens` (use `ollama.count_tokens` or estimate from text)
- `output_tokens`
- `latency_ms`

Aggregate by endpoint. Target: **p95 latency on guardrail/grader calls < 500ms** (use `llama3.2:3b`). p95 on final answer calls < 3000ms (use `llama3.2` full).

---

## Try this

1. **Switch the Session 14 eval grader to `llama3.2:3b`.** Re-run `25_evaluation_ollama.py` with `model = ChatOllama(model="llama3.2:3b")`. Compare scores against the full model baseline. If they agree within ±0.05, congratulations — you just cut eval time by 3x.

2. **Measure batch throughput.** Compare sequential vs `chain.batch()` on 20 grading calls. Print wall-clock time for each. The speedup is your "free" parallelism win.

3. **Audit your own agent system prompts.** Look at the system prompts in previous sessions' code. Count their tokens. Now compress. Run the same task and see if behavior changes.

4. **Profile model sizes.** Pull `llama3.2:3b` and `llama3.2` (full). Run the same simple classification task on both. Record latency and output quality. Build your own "role → model" recommendation table.

5. **Build a latency dashboard.** For every Ollama call in your app, log `model`, `input_tokens`, `output_tokens`, `latency_ms`, `endpoint`. Aggregate. Find your biggest bottleneck — that's your next optimization target.

---

## Mental model

> **Each lever costs zero engineering hours once the discipline is in place. The eval gate is the only thing standing between "I think we can swap to llama3.2:3b" and "the harness proved we can swap to llama3.2:3b."**

Optimization is not a feature you build. It is a *discipline* you adopt:

1. Before every prompt: which role is this? Pick the right model size.
2. Before every prompt: is every word earning its place? Trim it.
3. Before every batch: can these run in parallel? Use `chain.batch()`.

Do this for a week and your inference time drops significantly. Permanently.

---

## FAQ

**Q: Is `llama3.2:3b` really enough for graders?**
For ternary/binary classification with a clear rubric — yes, usually. Failure mode is when the rubric requires nuanced judgment. Always verify on your eval set first.

**Q: What's the Ollama equivalent of Anthropic's prompt caching?**
There is no direct equivalent. Prompt compression (Lever 2) is the best substitute — fewer tokens in means less prefill time. Ollama doesn't expose a server-side KV cache mechanism that persists across requests.

**Q: What's the Ollama equivalent of Anthropic's Batches API?**
Use `chain.batch([...])` from LangChain, or use `asyncio` to submit concurrent requests. The 50% cost discount that Anthropic's Batches API provides has no equivalent in Ollama (there is no API cost to discount), but the throughput benefit of parallelism is real.

**Q: How aggressive can prompt compression go?**
Until eval breaks. Some teams report 70-80% reduction with no quality drop on well-defined tasks. Open-ended generation tolerates less. The only way to know is to run the eval before and after.

**Q: Does `chain.batch()` work with all LangChain chains?**
Yes — any LCEL chain supports `.batch([...])`. The number of concurrent requests is limited by Ollama's concurrency setting (configured in Ollama's environment variables).

---

## Related

- **Previous:** [25 — Evaluation](25-evaluation.md) — the quality floor that makes every optimization safe
- **Next:** Session 16 — Streaming (latency optimization, the other half of UX)
- **Builds on:** [24 — Corrective RAG](24-corrective-rag.md) (the grader is the prime small-model target), [19 — AI Gateway](19-ai-gateway.md) (model selection + latency bake-off covered there)
- **Track F status:** ▶ 2/4 complete. Eval → Cost. Next: Streaming → Deploy.
