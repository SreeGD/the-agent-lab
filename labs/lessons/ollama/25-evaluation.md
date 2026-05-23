# 25 — Evaluation (Session 14)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/25_evaluation_ollama.py`.

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

## Files involved

| File | Role |
|---|---|
| [`eval_dataset.json`](../eval_dataset.json) | 5 golden Q/A pairs over NOTES.md + LEARNINGS.md. Hand-curated so the ground-truth answers are findable in the corpus. The whole eval depends on this dataset being correct. |
| [`25_evaluation_ollama.py`](../ollama/25_evaluation_ollama.py) | 4 metrics (faithfulness, answer relevance, context precision, context recall) as LLM-as-judge calls. Runs 3 RAG variants (dense / hybrid / CRAG) over the golden set, prints a comparison table, then a regression check. |

---

## What problem it solves

Imagine you have three RAG variants — dense, hybrid, CRAG. Which one ships to production?

Without eval, you have:
- **Vibes** — "hybrid felt better on those 4 queries I tested"
- **Anecdotes** — "user X said the answer was wrong"
- **Cherry-picked demos** — "let me find a question where my favorite variant wins"

With eval, you have:
- **Per-metric scores** — `hybrid wins recall (0.74), CRAG wins precision (0.64), dense is fastest`
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

All four return a single float in `[0.0, 1.0]`, judged by Llama 3.2 with structured output. Read each prompt — that's where the metric is *defined*.

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
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

class _Score(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
```

`Field(ge=0.0, le=1.0)` enforces the range at the API boundary — Pydantic rejects anything outside `[0, 1]`. No clamping in your code. The `reasoning` field is mostly for debugging — when a metric tanks, you read the reasoning to understand *why*.

Why use an LLM as judge? Two reasons:
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

This is what production looks like. CRAG wins overall (filtering bad chunks pays off). Hybrid wins recall (BM25 catches exact terms the dense embedding misses). Faithfulness is 1.0 across the board (none of the variants hallucinate when given good context).

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

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/25_evaluation_ollama.py
```

Takes ~3-5 minutes (120-ish LLM calls, all running locally via Ollama). No API cost — Ollama runs locally.

If you want it faster, switch the judge model to `llama3.2:3b` in the code — smaller model, faster inference.

---

## Production patterns

### Building golden datasets

- **Curate from real traffic.** Pick 50 actual user queries; have a domain expert write the ground-truth answers.
- **Stratify by difficulty.** 1/3 easy, 1/3 medium, 1/3 hard. If you only test easy questions, you'll over-fit to them.
- **Cover the long tail.** Include rare-but-important queries — they're the ones that embarrass you in production.
- **Version it.** `eval_dataset_v1.json`, `eval_dataset_v2.json`. When you add examples, re-baseline.

### Swapping the judge

```python
# from this:
model = ChatOllama(model="llama3.2", temperature=0)
# to this for faster inference:
model = ChatOllama(model="llama3.2:3b", temperature=0)
```

For ternary/binary classification (which the metrics essentially are), `llama3.2:3b` is usually adequate. Try both and compare scores on your golden set — if they agree within ±0.05, use the smaller one.

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
- run: python labs/ollama/25_evaluation_ollama.py --threshold OVERALL=0.75
- run: if [[ $? -ne 0 ]]; then echo "Eval failed" && exit 1; fi
```

Run on every PR. Fail the build on regression.

---

## Try this

1. **Add 3 more golden examples**, including one whose answer is *not* in the corpus. Watch CRAG win precision (its grader filters out the bad chunks) and watch the answer become *"the context doesn't contain the answer"* (which is the correct behavior!).
2. **Switch the judge to `llama3.2:3b`.** Time the run, compare scores. Are any metric averages > 0.05 apart? If not, use the smaller model.
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
They're the four that come from the original RAG paper and are now standard across Ragas / RAGAS / DeepEval / etc. They cover the two halves of RAG (retrieval, generation) with two metrics each.

**Q: What about ROUGE / BLEU / BERTScore?**
Classical NLP metrics. They compare token overlap or embedding similarity between generated and reference answers. Three problems: (1) they need a fixed reference (golden answer); (2) they reward verbatim matches over correctness; (3) they don't measure faithfulness at all. LLM-as-judge sidesteps all three.

**Q: How big should the golden dataset be?**
Floor: 5. Reasonable: 30-50. Production: 200-500. Quality > quantity — 30 carefully chosen examples beat 300 random ones.

**Q: How reliable are LLM judges?**
Roughly 85-92% agreement with humans on these tasks. Failure modes: (1) sycophancy; (2) self-bias; (3) misses subtle hallucinations. Mitigations: (1) use a *different* model as judge than the one generating; (2) for high-stakes decisions, add human review on a sample.

**Q: Should I run eval on every commit?**
At 120 LLM calls per run, consider running a smoke eval (5-10 examples) on every PR, full eval on merge to main; or run on a schedule (daily) regardless of commits.

**Q: How do I know if my eval is good?**
Easy check: artificially break something (the regression test in this lab does this). If the eval doesn't catch it, the eval is broken. Harder check: when a *real* regression slips into production, did your eval catch it? If not, add an example covering that case to the golden set.

**Q: What's the relationship between eval and guardrails?**
Guardrails (Session 10) catch problems at inference time — they prevent bad outputs from reaching the user. Eval catches problems at development time — it prevents bad systems from shipping in the first place. You want both.

---

## Related

- **Previous:** [24 — Corrective RAG](24-corrective-rag.md)
- **Next:** Session 15 — Cost Optimization (use this eval as the quality floor while we cut costs)
- **Builds on:** [09 — RAG](09-rag.md), [22 — Hybrid RAG](22-hybrid-rag.md), [24 — Corrective RAG](24-corrective-rag.md) (the three variants under test), [05 — Structured output](05-structured-output.md) (the judge uses it for scores)
- **Track F status:** ▶ 1/4 complete. Eval is the foundation for everything else in this track.
