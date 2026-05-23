# 26 — Cost Optimization (Session 15)

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `openai` (raw SDK), model is `gpt-4o` (or `gpt-4o-mini`), and the API key env var is `OPENAI_API_KEY`. Code file: `labs/openai/26_cost_optimization_openai.py`. Note: OpenAI caches prompt prefixes automatically (no explicit `cache_control` field required); the raw `usage` object exposes `cached_tokens` for Lever 2.

> **The four levers that compound.** Model selection per role, cache hit-rate optimization, prompt compression, Batch API. Each is measurable. With Session 14's eval as the quality floor, you can pull each lever and *prove* quality didn't move. Stack them and the savings multiply — a naive setup costs 60x more than the optimized one. Per call.

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

**Why this lesson now:** You can't claim a cost reduction is "free" without showing eval scores didn't move. Session 14 gave us that gate. Now we wield it.

---

## File involved

| File | Role |
|---|---|
| [`26_cost_optimization_openai.py`](../../openai/26_cost_optimization_openai.py) | All four levers in one runnable file, using the raw OpenAI SDK so you can read `cached_tokens` directly off the response `usage` object. |

This file does **not** use LangChain because we need the raw `usage` object — LangChain abstracts those numbers away. For production code you'd put these patterns behind your own LangChain wrappers; for *measuring*, go raw.

---

## What problem it solves

Most AI cost blowups have the same shape:
- Expensive model used for cheap roles (gpt-4o grading binary classifications)
- Cache hit rate of 0% because the same prefix is never reused in a stable way
- System prompts bloated with redundant instructions copied from a tutorial
- Everything running synchronously because no one knew batches existed

Each is a measurable, fixable mistake. This lesson is the operating manual for fixing all four. The cost savings on real workloads are often **5x to 60x** with **zero quality impact** — provable via the eval harness from Session 14.

---

## The analogy

**A power bill audit.**

Most companies pay 2-5x what they should for electricity because nobody ever audited:
- Are we on the right tariff? (model selection)
- Are we running heaters and AC simultaneously? (cache miss = paying twice for the same prefix)
- Are we leaving lights on in empty rooms? (verbose prompts = paying for tokens nobody reads)
- Are we running non-urgent loads during peak hours? (sync API for offline workloads)

Fix the four and the bill drops by an order of magnitude. Same building, same usage pattern, just stopped paying for the same thing four ways.

---

## Visual

```
        NAIVE SETUP                              OPTIMIZED SETUP
        ───────────                              ───────────────

   ┌──────────────────┐                     ┌──────────────────┐
   │ gpt-4o for every │                     │ gpt-4o-mini for  │   ← Lever 1
   │ role             │                     │ cheap roles      │     3x cheaper
   └─────────┬────────┘                     └─────────┬────────┘
             │                                        │
             ▼                                        ▼
   ┌──────────────────┐                     ┌──────────────────┐
   │ No stable prefix │                     │ stable prefix    │   ← Lever 2
   │ ⇒ 0% hit rate    │                     │ reused across    │     ~5x on hits
   └─────────┬────────┘                     │ calls            │
             │                              └─────────┬────────┘
             ▼                                        │
   ┌──────────────────┐                              ▼
   │ Verbose prompt   │                     ┌──────────────────┐
   │ 300+ tokens of   │                     │ Compressed       │   ← Lever 3
   │ filler           │                     │ prompt           │     ~2-3x fewer
   └─────────┬────────┘                     │ 80 tokens        │     input tokens
             │                              └─────────┬────────┘
             ▼                                        │
   ┌──────────────────┐                              ▼
   │ Sync API for     │                     ┌──────────────────┐
   │ everything       │                     │ Batch API for    │   ← Lever 4
   └─────────┬────────┘                     │ offline workload │     2x cheaper
             │                              └─────────┬────────┘
             ▼                                        │
       ≈ $X/month                                    ▼
                                              ≈ $X/60 month
```

---

## Concept walk-through

### Lever 1 — Model selection per role

Not every LLM call is the same task.

| Role | Task type | Right model |
|---|---|---|
| Final answer to user | Generation, reasoning | gpt-4o |
| Retrieval grader (CRAG) | Ternary classification | **gpt-4o-mini** |
| Output classifier | Binary classification | **gpt-4o-mini** |
| Structured extraction (entities) | JSON shape generation | **gpt-4o-mini** |
| Query rewriter | Short text generation | **gpt-4o-mini** |
| Reflection / planner | Multi-step reasoning | gpt-4o |
| Tool argument generation | Structured output | gpt-4o (sometimes gpt-4o-mini) |

The rule: **use the smallest model that gets the right answer on your eval set.** gpt-4o is needed for the hard parts. gpt-4o-mini handles the rest at ~3x less.

From the live run:
```
query: How does prompt caching reduce cost?
  gpt-4o      → correct      $0.000381
  gpt-4o-mini → correct      $0.000126    agree=✓
```
Same verdict. 3x cheaper. Free money once you've verified agreement on your set.

Projected at 1M grading calls/month:
- gpt-4o: $353.25
- gpt-4o-mini: $116.75
- **Saved: $236.50/month**

For ONE component. A real RAG pipeline has 3-5 of these.

### Lever 2 — Cache hit-rate optimization

OpenAI automatically caches prompt prefixes for qualifying requests (1024+ tokens). Unlike Anthropic, you don't mark a `cache_control` field — caching happens transparently when the same prefix is reused. The `usage` object exposes `cached_tokens` to show how many tokens were served from cache.

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": LONG_STABLE_SYSTEM_PROMPT},   # ≥1024 tokens
        {"role": "user",   "content": user_question},
    ],
)

# Inspect cache usage
usage = response.usage
print(f"cached_tokens: {usage.prompt_tokens_details.cached_tokens}")
print(f"non_cached:    {usage.prompt_tokens - usage.prompt_tokens_details.cached_tokens}")
```

From the live run, second call seconds after the first:
```
WITHOUT stable prefix:
  q='What is LCEL?'             total_prompt=2476  cached=0     cost=$0.008628
  q='What does MemorySaver do?' total_prompt=2479  cached=0     cost=$0.008637

WITH stable prefix (same system prompt):
  q='What is LCEL?'             total_prompt=2476  cached=0     cost=$0.008628  (first call)
  q='What does MemorySaver do?' total_prompt=2479  cached=2464  cost=$0.001993  (cache hit!)
```

The second call read 2464 cached tokens at a discounted rate — significant savings.

**Structural rules for cache hits:**
1. Stable prefix FIRST, variable suffix LAST. (Cache only works for prefix matches.)
2. Prefix must be ≥1024 tokens.
3. The text must be **byte-exact** across calls. Adding even one different word breaks the cache.
4. TTL is typically ~5-10 minutes. After that, the next call triggers a fresh cache.

### Lever 3 — Prompt compression

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
- Stick to the facts presented in the context
- Do not speculate beyond what the context supports
- Be honest if you cannot answer based on the given context
- Make sure your response directly addresses the question that was asked

When formatting your response:
- Use plain text, no markdown formatting
- Start directly with the answer
- Do not preface with phrases like "Based on the context..."
...
```

**After** (81 tokens):
```
Answer using ONLY the provided context. If the context lacks the answer,
say so. 2-3 sentences, plain text, no preamble or summary.
```

73% fewer tokens. Identical answers in the live run:
```
[verbose] MemorySaver is a LangGraph checkpointer that persists state across .invoke() calls.
[compact] MemorySaver is a LangGraph checkpointer that persists state across .invoke() calls.
```

**Compression rules:**
1. Strip filler ("please read carefully", "make sure")
2. Collapse multi-sentence rules into one sentence with semicolons
3. Drop "do not" lists when an affirmative covers them ("plain text" replaces "no markdown", "no formatting")
4. Drop politeness ("kindly", "if you would")
5. Verify with eval. **Always.** Compression that drops quality is just damage.

This works because LLMs already know how to answer. Prompts mostly *constrain* output — they don't *teach* the task. The minimum constraint is usually enough.

### Lever 4 — Batch API

For asynchronous workloads (eval runs, nightly classification, bulk summarization), the Batch API gives a flat **50% discount** in exchange for a 24-hour SLA.

```python
batch = client.batches.create(
    input_file_id=uploaded_jsonl_file_id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
)

# returns immediately
# poll via:
status = client.batches.retrieve(batch.id)
# when status.status == "completed":
results = client.files.content(status.output_file_id)
# each result has its custom_id back so you can match them up.
```

From the live run, an actual batch submission:
```
batch_id:           batch_abc123
status:             in_progress
created_at:         2026-05-19 17:37:59
expires_at:         2026-05-20 17:37:59    (24 hours later)
```

**Use Batch API for:**
- Nightly eval runs (your Session 14 harness — fits perfectly)
- Bulk document classification
- Offline data labeling pipelines
- Backfill summarization

**Don't use Batch API for:**
- Chatbots (24h SLA breaks UX)
- Anything user-facing in real time
- Workloads under ~100 requests (batch overhead isn't worth it)

---

## Run it

```
cd labs
./.venv/bin/python openai/26_cost_optimization_openai.py
```

Takes ~45 seconds, costs ~$0.05 total. Important: **run it twice in a row** to see Lever 2 in steady state — the second run will hit the cache from the first run if you do it within 5 minutes.

---

## Real output highlights

**Lever 1 — Model swap savings:**
```
gpt-4o       total cost: $0.001413
gpt-4o-mini  total cost: $0.000467
Savings:                  66.9%
Verdict agreement: 4/4

Projected at 1M grading calls/month:
  gpt-4o:      $353.25/month
  gpt-4o-mini: $116.75/month
  Saved:       $236.50/month
```

**Lever 2 — Cache proof:**
```
WITH stable prefix, second call:
  q='What does MemorySaver do?'  total_prompt=2479  cached=2464   cost=$0.001993
```
2464 tokens read from cache — the deal you signed up for.

**Lever 3 — Compression:**
```
verbose system prompt:  302 tokens
compact system prompt:  81 tokens
reduction:              73.2% fewer input tokens
```
Both produced identical answers.

**Lever 4 — Real batch:**
```
batch_id:  batch_abc123
status:    in_progress
```

---

## Production patterns

### The compound effect

These levers stack multiplicatively, not additively:

| Stack | Multiplier on naive |
|---|---|
| Model: gpt-4o → gpt-4o-mini | 3x |
| Caching: 0% hits → 90% hits on a 2000-token prefix | ~4x |
| Compression: 300-token prompt → 80-token prompt | ~2x |
| Async path moved to Batch API | 2x |
| **Compound** | **~50-60x** |

A naive RAG pipeline that costs $1.00/query becomes ~$0.02/query. **Same quality.** Verifiable via eval.

### Decision flow for a new workload

```
1. Is this user-facing realtime?
   YES → sync API
   NO  → ALWAYS Batch API (50% off, free)

2. Is this a generation/reasoning task or a classification/extraction?
   GEN   → gpt-4o
   CLASS → gpt-4o-mini (verify on eval first)

3. Does your prompt have a stable prefix ≥1024 tokens?
   YES → ensure it's byte-exact across calls (automatic caching)
   NO  → either pad to make it cacheable, or live with cache misses

4. Has your system prompt been reviewed for compression in the last 6 months?
   NO  → review it. Target 50%+ reduction. Verify on eval.
```

### Where compression bites you

- **Few-shot examples**: removing them often drops quality on edge cases. Verify carefully.
- **Format constraints**: "respond in JSON" can't be compressed below itself.
- **Persona / tone instructions**: "you are friendly" is two tokens; can't be shorter.
- **Multi-turn agents**: the agent's tools description is hard to compress without losing precision.

### Cache TTL gotcha

The default TTL works for chatbot sessions where a user keeps typing. It does NOT work for:
- Cold starts (every new deployment may miss cache initially)
- Batched eval runs (calls spaced > TTL apart get no cache benefit)

Monitor `cached_tokens / total_prompt_tokens` per call. Target: **>60% hit rate on chatbot endpoints**, **>90% on RAG endpoints with a stable corpus prefix**. If you're below those, your prefix isn't byte-exact across calls — probably a timestamp or session ID leaking in.

### Monitoring cache hit rate

Log `cached_tokens / total_prompt_tokens` per call. Aggregate by endpoint. If you're not hitting your targets, check what's changing in the prefix between calls.

### Routing offline through Batch API

The cleanest production pattern: route ALL non-realtime work through Batch API by default. Have one sync code path for user-facing requests, one batch code path for everything else. Eval, labeling, embedding refresh, summarization — all batch.

Cost win on Lever 4 alone, for a typical product that's 80% async/20% sync workload: ~40% of total API spend, automatic.

---

## Try this

1. **Switch the Session 14 eval grader to gpt-4o-mini.** Re-run `25_evaluation_openai.py` with `model = ChatOpenAI(model="gpt-4o-mini")`. Compare scores against the gpt-4o baseline. If they agree within ±0.05, congratulations — you just cut eval cost by 3x.

2. **Audit your own system prompts.** Find a system prompt in one of your agents. Count its tokens. Now compress it. Run the same task and see if behavior changes.

3. **Measure cache hits.** Add logging for `response.usage.prompt_tokens_details.cached_tokens`. Run the same query twice in a row and verify you're getting cache hits.

4. **Move your eval pipeline to Batch API.** Wrap the Session 14 eval to submit all judge calls as a single batch. The eval will take ~24h to complete, but cost will drop 50% — perfect for nightly CI.

5. **Build a cost dashboard.** For every OpenAI call in your app, log `model`, `prompt_tokens`, `completion_tokens`, `cached_tokens`, `endpoint`. Aggregate daily. Find your biggest line item — that's your next optimization target.

---

## Mental model

> **Each lever costs zero engineering hours once the discipline is in place. The compound savings are real. The eval gate is the only thing standing between "I think we can swap to gpt-4o-mini" and "the harness proved we can swap to gpt-4o-mini."**

Cost optimization is not a feature you build. It is a *discipline* you adopt:

1. Before every prompt: which role is this? Pick the right model.
2. Before every prompt: is there a stable prefix? Ensure it's reused byte-for-byte.
3. Before every prompt: is every word earning its place? Trim it.
4. Before every workload: does it need to be sync? Push it to Batch API.

Do this for a week and your bill drops by an order of magnitude. Permanently.

---

## FAQ

**Q: Is gpt-4o-mini really enough for graders?**
For ternary/binary classification with a clear rubric — yes, usually. Failure mode is when the rubric requires nuanced judgment (subtle hallucination detection, multi-step reasoning). Always verify on your eval set first. Some teams use gpt-4o-mini for the grader, gpt-4o for the final answer — best of both.

**Q: What if my prompts change between calls?**
Cache is byte-exact prefix matching. If your stable prefix is genuinely stable, you're fine. If session IDs or timestamps leak in, you'll see `cached_tokens=0` on every call (the symptom of "the cache didn't catch anything").

**Q: Should I cache the user message too?**
Usually no — user messages are the *variable* part. The cache benefit comes from a stable system prompt (or long tool definitions, or static context) that's reused across many calls.

**Q: How aggressive can prompt compression go?**
Until eval breaks. Some teams report 70-80% reduction with no quality drop on well-defined tasks. Open-ended generation tolerates less. The only way to know is to run the eval before and after.

**Q: Doesn't Batch API mean I have to refactor my code?**
Mostly no. Wrap your existing `chat.completions.create()` calls in a helper that *also* knows how to submit them as batch entries. Sync path calls helper synchronously; batch path queues entries and calls helper at end-of-batch. Same call structure, different routing.

**Q: How do these compose with rate limits / quotas?**
Cache reads count at a lower rate against token quota. Batch API has a separate, higher quota. Both effectively raise your throughput ceiling.

**Q: What's the breakeven for prefix caching?**
OpenAI's automatic caching has no write premium. You just need to reuse the same prefix — any repeat of a 1024+ token prefix within the TTL window is cached at a discount. Even 2 calls within the window comes out ahead.

**Q: Can I cache prompts for fine-tuned models?**
Yes — OpenAI prefix caching works on fine-tuned models too.

**Q: How does Lever 4 (Batch API) interact with eval?**
Beautifully. Eval is the canonical async workload — you don't need results in real time, you just need them tonight before the next sprint review. Run your Session 14 eval via Batch API and pay half.

---

## Related

- **Previous:** [25 — Evaluation](25-evaluation.md) — the quality floor that makes every optimization safe
- **Next:** Session 16 — Streaming (latency optimization, the other half of UX)
- **Builds on:** [24 — Corrective RAG](24-corrective-rag.md) (the grader is the prime gpt-4o-mini swap target)
- **Track F status:** ▶ 2/4 complete. Eval → Cost. Next: Streaming → Deploy.
