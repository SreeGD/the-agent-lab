# 25 — Evaluation (Session 14)

> **You can't improve what you don't measure.** Before this session, every change to your RAG pipeline was a vibe check. Now you have a golden dataset + four LLM-as-judge metrics + a regression harness that catches quality drops in CI. The first session about *measuring* an AI system rather than building one.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-13 (foundation + RAG architectures)                 Tracks A/B/C/D/E/E.5: ✓ all done
                                                           Track F: PRODUCTION
                                                             ▶ Session 14: EVALUATION  ◄ HERE
                                                             ○ Session 15: Cost Optimization
                                                             ○ Session 16: Streaming
                                                             ○ Session 17: Deploy + Observability
                                                           Track G: ○ Architect Skills
```

**Why this lesson now:** You've shipped 13 sessions of agents and RAG variants — Dense (S9), Hybrid (S11), Graph (S12), Corrective (S13). With no eval, you can't tell which one is actually better, or whether a prompt tweak regressed quality. Production AI without eval is hope-driven engineering.

This kicks off Track F. The next three sessions (Cost, Streaming, Deploy) build on this — you'll *measure* a cost optimization, you'll *measure* streaming latency, etc.

---

## File involved

| File | Role |
|---|---|
| [`eval_dataset.json`](../eval_dataset.json) | 5 golden Q/A pairs over NOTES.md + LEARNINGS.md. Hand-curated so the ground-truth answers are findable in the corpus. The whole eval depends on this dataset being correct. |
| [`25_evaluation.py`](../25_evaluation.py) | 4 metrics (faithfulness, answer relevance, context precision, context recall) as LLM-as-judge calls. Runs 3 RAG variants (dense / hybrid / CRAG) over the golden set, prints a comparison table, then a regression check. |

---

## What problem it solves

Imagine you have three RAG variants — dense, hybrid, CRAG. Which one ships to production?

Without eval, you have:
- **Vibes** — "hybrid felt better on those 4 queries I tested"
- **Anecdotes** — "user X said the answer was wrong"
- **Cherry-picked demos** — "let me find a question where my favorite variant wins"

With eval, you have:
- **Per-metric scores** — `hybrid wins recall (0.74), CRAG wins precision (0.64), dense is cheapest`
- **A reproducible comparison** — same dataset, same metrics, same numbers every run
- **A regression gate** — change anything (prompt, model, k value) → re-run → catch quality drops before users see them

The shift is from "I think it's better" to "the harness says it's better." That's the difference between hobbyist and production.

---

## The analogy

**Unit tests for AI.**

Code without tests works *until it doesn't* — you change something, ship, and a customer finds the regression three days later. Code with tests fails loud and immediately when you break something.

RAG without eval works *until it doesn't* — you swap a prompt, ship, and a customer asks a question whose answer just got worse. RAG with eval fails loud and immediately when a metric drops.

Same discipline, different domain. Once you have eval, you can change things fearlessly — `git checkout -b try-new-prompt`, edit, run eval, ship if metrics hold, revert if they don't.

---

## Visual

```
                          GOLDEN DATASET
                          (5 Q + 5 ground-truth answers)
                                 │
                                 ▼
   ┌───────────────────────────────────────────────────────────┐
   │   For each (Q, GT):                                       │
   │                                                           │
   │   ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │
   │   │  dense_rag   │    │  hybrid_rag  │    │ crag_rag   │  │
   │   │  retrieve+   │    │  +BM25+RRF   │    │ +grade     │  │
   │   │  generate    │    │  +generate   │    │ +filter    │  │
   │   └──────┬───────┘    └──────┬───────┘    └─────┬──────┘  │
   │          │                   │                  │         │
   │          ▼                   ▼                  ▼         │
   │     answer + chunks    answer + chunks    answer+chunks   │
   │          │                   │                  │         │
   │          ├────────────┬──────┴──────┬───────────┤         │
   │          ▼            ▼             ▼           ▼         │
   │     faithfulness  answer_rel.  context_prec. context_rec. │
   │     (LLM judge)   (LLM judge)  (LLM judge)   (LLM judge)  │
   │          │            │             │           │         │
   │          ▼            ▼             ▼           ▼         │
   │       score[0,1]   score[0,1]   score[0,1]   score[0,1]   │
   └───────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                       COMPARISON TABLE
                  (per-metric averages + winner)
```

---

## Concept walk-through

### 1. The golden dataset

```json
{
  "id": "memorysaver",
  "question": "Which LangGraph component gives an agent memory across .invoke() calls?",
  "ground_truth": "MemorySaver, used as the checkpointer..."
}
```

Five examples is the floor. Real production sets are 50-500 examples, hand-curated, covering the long tail of user questions you actually care about. The set is the contract — every example you add raises the quality bar.

Important: **the ground truth must be findable in your corpus.** If you ask "what's the capital of France?" but your corpus is about LLMs, every variant will fail recall — that tells you nothing about the variants. Eval datasets must be *fair*.

### 2. The four metrics (this is the heart of the lesson)

All four return a single float in `[0.0, 1.0]`, judged by Claude with structured output. Read each prompt — that's where the metric is *defined*.

**Faithfulness** — *"does every claim in the answer appear in the context?"*
```
Penalize claims that go beyond the context, even if true in general.
```
This is the hallucination detector. Goes to **0** if the LLM made things up. Goes to **1** if every word is traceable to a retrieved chunk.

**Answer relevance** — *"does the answer actually address the question?"*
```
Score 1.0 if focused and on-topic, 0.0 if it dodges the question.
Ignore factual correctness — only judge topical fit.
```
This catches the dreaded *"based on the context, I cannot determine..."* dodge. Faithful but unhelpful = high faithfulness, low relevance.

**Context precision** — *"what fraction of retrieved chunks are actually useful?"*
```
1.0 if every chunk could help answer the question, 0.0 if all are off-topic.
```
This measures retrieval *noise*. Even if recall is good, dragging in 5 irrelevant chunks dilutes the answerer's attention. Low precision is the case for CRAG-style filtering.

**Context recall** — *"is the ground-truth answer findable in the retrieved chunks?"*
```
1.0 if every fact in the ground truth is findable in chunks, 0.0 if missing.
```
This measures *whether retrieval found the right material*. Independent of how the LLM used it. Low recall = your retrieval is broken upstream; switching models won't help.

The four metrics break into two pairs:
- **Faithfulness + Answer relevance** judge the *generation* (LLM half)
- **Context precision + Context recall** judge the *retrieval* (search half)

When a number drops, the pair tells you where to look.

### 3. LLM-as-judge with structured output

```python
class _Score(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
```

`Field(ge=0.0, le=1.0)` enforces the range at the API boundary — Pydantic rejects anything outside `[0, 1]`. No clamping in your code. The `reasoning` field is mostly for debugging — when a metric tanks, you read the reasoning to understand *why*.

Why use Claude as judge? Two reasons:
- **Reading comprehension** — the metrics need real language understanding (does this answer "address" the question? does this chunk "support" the claim?). Numeric heuristics can't do this.
- **No training data needed** — classical eval metrics (ROUGE, BLEU) need reference outputs; LLM-as-judge works zero-shot.

The trade-off: LLM judges aren't perfect either. Accuracy is ~85-92% vs. human raters on these tasks. Acceptable for trend detection; not acceptable as the only signal before a major release.

### 4. The comparison table

```
metric                       dense      hybrid        crag    winner
faithfulness                 1.000       1.000       1.000    dense
answer_relevance             1.000       0.900       1.000    dense
context_precision            0.600       0.534       0.640    crag
context_recall               0.660       0.740       0.740    hybrid
OVERALL                      0.815       0.794       0.845    crag
```

This is what production looks like. CRAG wins overall (filtering bad chunks pays off). Hybrid wins recall (BM25 catches exact terms the dense embedding misses — "MiniLM-L6-v2", "MemorySaver"). Faithfulness is 1.0 across the board (none of the variants hallucinate when given good context). Answer relevance is high everywhere except where retrieval failed — `[embeddings-model]` got 0 on context_recall for dense/hybrid because the exact model name wasn't surfaced.

The table doesn't tell you which to ship — that depends on your cost / latency / risk profile. It tells you *what trade-offs you're making*.

### 5. The regression check

The whole point of eval is *catching breaks before users do*. So we deliberately break dense (drop k from 3 to 1) and verify:

```
metric                       k=3        k=1        Δ
answer_relevance             1.000  →  0.520    Δ=-0.480  ❌ REGRESSION
context_precision            0.600  →  0.240    Δ=-0.360  ❌ REGRESSION
context_recall               0.660  →  0.340    Δ=-0.320  ❌ REGRESSION
OVERALL                      0.815  →  0.525    Δ=-0.290  ❌ REGRESSION
```

`Δ < -0.10` on any metric → harness flags it. In CI this would fail the build. That's the whole game — every change goes through the gate.

---

## Run it

```
cd labs
./.venv/bin/python 25_evaluation.py
```

Takes ~3-5 minutes (120-ish LLM calls). Cost ~$0.30-0.50 with Sonnet. If you want it faster + cheaper, switch the judge model to `claude-haiku-4-5-20251001` — almost identical numbers at ~$0.05.

---

## Real output highlights

The full run is in [Concept walk-through 4](#4-the-comparison-table) above. The key takeaways from this run:

1. **Faithfulness is universally high (1.000).** With good prompts ("Answer using ONLY the provided context"), none of the variants make things up. This is *the* baseline you should establish first.
2. **Answer relevance reveals the dodgy answers.** Hybrid lost 0.1 because on `[embeddings-model]` it dodged ("the context doesn't mention...") when dense/CRAG happened to retrieve a chunk with the name.
3. **Context recall is where retrieval lives.** Hybrid + CRAG both win recall over dense because BM25 catches exact terms.
4. **Context precision rewards filtering.** CRAG wins precision because the grader threw out noisy chunks.
5. **The k=1 regression check** shows the harness has teeth — three of four metrics dropped > 30%, flagged loudly.

---

## Production patterns

### Building golden datasets

- **Curate from real traffic.** Pick 50 actual user queries; have a domain expert write the ground-truth answers. This is the closest you get to ground truth on retrieval correctness.
- **Stratify by difficulty.** 1/3 easy, 1/3 medium, 1/3 hard. If you only test easy questions, you'll over-fit to them.
- **Cover the long tail.** Include rare-but-important queries — they're the ones that embarrass you in production.
- **Version it.** `eval_dataset_v1.json`, `eval_dataset_v2.json`. When you add examples, re-baseline. Don't compare new-dataset scores to old-dataset scores.

### Swapping the judge

```python
# from this:
model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)
# to this for 6x cheaper:
model = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
```

For ternary/binary classification (which the metrics essentially are), Haiku is plenty. Sonnet is overkill. Try both and compare scores on your golden set — if they agree within ±0.05, ship the cheap one.

### Swapping in Ragas

[Ragas](https://docs.ragas.io/) wraps the same four metrics with battle-tested prompts. Once you understand what each metric *is* (which is the whole point of this lesson), the swap is:

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
)
```

Their prompts are better-tested than ours. Use them in production. But you'll only trust them if you understand what they're measuring — and now you do.

### Wiring into CI

```yaml
# .github/workflows/eval.yml
- run: python labs/25_evaluation.py --threshold OVERALL=0.75
- run: if [[ $? -ne 0 ]]; then echo "Eval failed" && exit 1; fi
```

Run on every PR. Fail the build on regression. Optionally: post the comparison table as a PR comment.

### LangSmith integration

```python
from langsmith import Client
client = Client()
client.upload_dataset("rag-eval-v1", examples=GOLDEN)
# then runs are auto-traced and dashboards show metric trends over time.
```

The value of LangSmith over a homegrown harness: persistent dashboards, comparison across model versions, drill-down to per-example traces. Worth the $39/mo when you have a team and a long-lived eval set.

### What this lab DOESN'T cover

- **A/B testing in production.** Eval is offline measurement against a fixed set. A/B testing is online measurement against real users. Both matter. Eval first, A/B second.
- **Latency and cost metrics.** Quality is one axis; cost and p50/p95 latency are the others. Add them in Session 15.
- **Multi-turn conversation eval.** Single-turn Q/A is easier to measure. Multi-turn needs persona simulation. Worth its own session.

---

## Try this

1. **Add 3 more golden examples**, including one whose answer is *not* in the corpus. Watch CRAG win precision (its grader filters out the bad chunks) and watch the answer become *"the context doesn't contain the answer"* (which is the correct behavior!).
2. **Switch the judge to Haiku.** Time the run, compare scores. Are any metric averages > 0.05 apart? If not, ship the cheap one.
3. **Break dense intentionally** in a different way — change the prompt to *"answer in haiku form."* Watch answer_relevance plummet, faithfulness probably stay high.
4. **Add a 5th metric: `answer_correctness`** — compare the generated answer to the ground truth. Score how factually similar they are. Now you can detect cases where retrieval was fine but the LLM still got the answer wrong.
5. **Plot scores over time.** Run the eval after every commit, append results to a JSON file. After 10 commits you have a quality time-series — you can spot the commit where things broke.

---

## Mental model

> **Eval is the contract between you and your future self.** It's the assertion that *"this system at least does X."*

You set the contract by curating the golden set + picking the metrics. After that, every change to the system has to honor the contract — or you're knowingly degrading something. The harness makes "knowingly" mandatory.

Three numbers tell you everything you need:
1. **Faithfulness** — does it lie?
2. **Recall** — does retrieval find the right stuff?
3. **Overall** — net quality direction.

The other metrics diagnose *why* when one of these moves.

---

## FAQ

**Q: Why these four metrics and not others?**
They're the four that come from the original RAG paper and are now standard across Ragas / RAGAS / DeepEval / etc. They cover the two halves of RAG (retrieval, generation) with two metrics each. You can add more — answer correctness, semantic similarity, latency, cost — but start here.

**Q: What about ROUGE / BLEU / BERTScore?**
Classical NLP metrics. They compare token overlap or embedding similarity between generated and reference answers. Three problems: (1) they need a fixed reference (golden answer); (2) they reward verbatim matches over correctness; (3) they don't measure faithfulness at all. LLM-as-judge sidesteps all three. Use ROUGE/BLEU only if you have a strict-format generation task (translation, summarization with specific style).

**Q: How big should the golden dataset be?**
Floor: 5. Reasonable: 30-50. Production: 200-500. Quality > quantity — 30 carefully chosen examples beat 300 random ones. Cover edge cases (rare terms, off-topic questions, multi-hop) explicitly.

**Q: How reliable are LLM judges?**
Roughly 85-92% agreement with humans on these tasks. Failure modes: (1) sycophancy (rates everything generously); (2) self-bias (model rates its own outputs higher); (3) misses subtle hallucinations. Mitigations: (1) use a *different* model as judge than the one generating; (2) for high-stakes decisions, add human review on a sample; (3) explicitly prompt for strictness.

**Q: Can I just check exact-match against ground truth?**
For factoid questions, sort of. *"Who wrote War and Peace?"* → match "Tolstoy" exactly. But almost no real questions are factoid. *"How does prompt caching reduce cost?"* has 50 valid phrasings. LLM-as-judge handles paraphrase naturally.

**Q: Should I run eval on every commit?**
At 120 LLM calls per run, no — too expensive. Strategies: (1) run a smoke eval (5-10 examples) on every PR, full eval on merge to main; (2) cache eval results when nothing related changed; (3) run on a schedule (daily) regardless of commits.

**Q: How do I know if my eval is good?**
Easy check: artificially break something (the regression test in this lab does this). If the eval doesn't catch it, the eval is broken. Harder check: when a *real* regression slips into production, did your eval catch it? If not, add an example covering that case to the golden set. The eval grows from its mistakes.

**Q: What's the relationship between eval and guardrails?**
Guardrails (Session 10) catch problems at inference time — they prevent bad outputs from reaching the user. Eval catches problems at development time — it prevents bad systems from shipping in the first place. You want both. Guardrails are last-mile; eval is the actual quality bar.

**Q: How does this connect to the next sessions?**
Session 15 (Cost Optimization) — you can't claim a cost reduction is "free" without showing eval scores didn't move. Session 16 (Streaming) — you can't claim faster latency is acceptable without showing quality didn't degrade. Session 17 (Deploy) — you can't deploy with confidence without a quality gate in CI. Every Track F session uses eval as its foundation.

---

## Langfuse — Open-Source Alternative to LangSmith

### Self-hostable vs managed comparison

| Feature | LangSmith (managed) | Langfuse (self-hosted) | Langfuse Cloud |
|---|---|---|---|
| Hosting | SaaS only | Docker / K8s on your infra | SaaS |
| Data residency | US/EU LangChain servers | Your servers — full control | EU servers |
| Cost | Paid tiers above free quota | Infra cost only (open-source) | Free tier + paid |
| GDPR / HIPAA | Contractual | You own the data entirely | Contractual |
| LangChain integration | Native callbacks | Callback handler | Callback handler |
| Metrics | Traces, latency, cost | Traces, latency, scores, cost | Same |

### Tracing a Q&A pair

```python
from typing import Any

def trace_with_langfuse(
    question: str, answer: str, langfuse_client: Any
) -> str:
    """Log a Q&A pair to Langfuse; return the trace ID."""
    trace = langfuse_client.trace(
        name="rag-eval",
        input={"question": question},
        output={"answer": answer},
    )
    return trace.id
```

Usage:

```python
# pip install langfuse; set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY
from langfuse import Langfuse

lf = Langfuse()
trace_id = trace_with_langfuse(question, answer, lf)
print(f"Langfuse trace: https://cloud.langfuse.com/trace/{trace_id}")
```

### What to look for in the Langfuse dashboard

After running the eval harness with tracing enabled, open the Langfuse UI:
- **Traces view**: each RAG call is one trace; expand to see individual LLM spans
- **Latency histogram**: spot the slow calls (usually the judge chain, not retrieval)
- **Score tab**: attach metric scores to traces so you can filter by quality bucket
- **Cost tab**: per-model token spend; useful for confirming Haiku is cheaper than Sonnet for judge calls
- **Sessions**: group multiple traces from a single eval run into one session for comparison

---

## Related

- **Previous:** [24 — Corrective RAG](24-corrective-rag.md)
- **Next:** Session 15 — Cost Optimization (use this eval as the quality floor while we cut costs)
- **Builds on:** [09 — RAG](09-rag.md), [22 — Hybrid RAG](22-hybrid-rag.md), [24 — Corrective RAG](24-corrective-rag.md) (the three variants under test), [05 — Structured output](05-structured-output.md) (the judge uses it for scores)
- **Track F status:** ▶ 1/4 complete. Eval is the foundation for everything else in this track.
