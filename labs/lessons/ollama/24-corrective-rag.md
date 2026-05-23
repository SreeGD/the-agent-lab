# 24 — Corrective RAG (Session 13)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/24_corrective_rag_ollama.py`.

> **Don't trust your retrieval — grade it.** Classical RAG always feeds the top-k chunks to the answerer. Corrective RAG (CRAG) inserts a self-correction loop: a grader judges each retrieved chunk, and the verdict routes the pipeline — use the chunks, rewrite the query and try again, or fall back to external knowledge.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Tracks A/B/C/D/E: ✓ all done
                                                           Track E.5: RAG Architectures
                                                             ✓ Session 11: Hybrid RAG
                                                             ✓ Session 12: GraphRAG
                                                             ▶ Session 13: CORRECTIVE RAG  ◄ HERE
                                                           Track F: ○ Production
```

**Why this lesson now:** Sessions 9 / 11 / 12 covered retrieval **mechanics** — dense, sparse, hybrid, graph. They all assume retrieval is good. CRAG is the first session to question that assumption — and act on the answer.

This completes Track E.5. After this, all RAG patterns from Brij Kishore Pandey's "Top 5 RAG Architectures" are in the curriculum.

---

## File involved

| File | Role |
|---|---|
| [`24_corrective_rag_ollama.py`](../ollama/24_corrective_rag_ollama.py) | A LangGraph `StateGraph` implementing the full CRAG pipeline: retrieve → grade → {use_chunks \| rewrite \| web_fallback} → answer. Three demo queries, one per branch. |

---

## What problem it solves

Classical RAG (and Hybrid RAG, and GraphRAG) all share the same trust assumption: **whatever the retriever returns, feed it to the LLM.** That works most of the time. But when retrieval fails — rare term, ambiguous phrasing, query is off-corpus entirely — the LLM does one of two bad things:

- **Hallucinates** an answer that *sounds* grounded in the chunks but isn't actually supported
- **Confidently cites the wrong chunk**, because the LLM can't tell from inside the prompt that the chunk is off-topic

CRAG turns retrieval from a one-shot operation into a **judged pipeline**. The grader sits between retrieve and answer, and routes:

- **correct** — chunks support the answer, generate normally
- **ambiguous** — chunks are tangentially related, rewrite the query and try again
- **incorrect** — chunks are off-topic, fall back to web / external knowledge

The end result is a system that **knows when it doesn't know**, instead of confabulating.

---

## The analogy

**A research assistant who reads what they pull before handing it to you.**

Classical RAG is an intern who runs to the library, grabs the top 3 books off the recommended shelf, and slides them across the desk without opening them. If the right book wasn't on the shelf, you find out only after wasting an hour reading the wrong one.

CRAG is an intern who *skims each book first* and tells you: *"book 1 nails it, book 2 is sort of related, book 3 is wrong shelf entirely. Want me to search the catalog with different keywords?"*

The cost is more of the intern's time. The benefit is you never read garbage.

---

## Visual

```
                        ┌──────────────────┐
   user query  ────────► │     retrieve     │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │      grade       │   ← LLM judge,
                        │  (per chunk)     │     Literal[
                        └────────┬─────────┘       "correct",
                                 │                 "ambiguous",
                   ┌─────────────┼─────────────┐   "incorrect"]
                   │             │             │
              correct        ambiguous      incorrect
                   │             │             │
                   │             ▼             │
                   │      ┌────────────┐       │
                   │      │  rewrite   │       │
                   │      │   query    │       │
                   │      └─────┬──────┘       │
                   │            │              │
                   │            ▼ (loop once)  │
                   │      ┌────────────┐       │
                   │      │ retrieve   │       │
                   │      │  again     │       │
                   │      └─────┬──────┘       │
                   │            │              │
                   ▼            ▼              ▼
              ┌──────────────┐         ┌─────────────────┐
              │  use_chunks  │         │  web_fallback   │
              └──────┬───────┘         └────────┬────────┘
                     │                          │
                     └──────────┬───────────────┘
                                ▼
                        ┌───────────────┐
                        │    answer     │
                        └───────────────┘
```

---

## Concept walk-through

### 1. The retrieval grader

The grader is a small LLM call per chunk with structured output:

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

class ChunkGrade(BaseModel):
    verdict: Literal["correct", "ambiguous", "incorrect"]
    reasoning: str
```

Why `Literal[...]`? Because it forces the model to **commit** to one of three discrete buckets. No "well, kind of correct" — that would defeat the whole point. The `reasoning` field is one-sentence justification, mostly for the developer (you'll read these in logs).

### 2. Aggregation

Per-chunk grades become a single verdict:

```python
if "correct" in verdicts:    return "correct"
if "ambiguous" in verdicts:  return "ambiguous"
return "incorrect"
```

"Any one chunk is correct → trust the bundle" is a generous rule. A stricter shop might require *majority* correct. Both are valid — tune to your false-positive tolerance.

### 3. The query rewriter

Fires only on `ambiguous`. The job: expand acronyms, add likely synonyms, surface implicit terms.

```python
class RewrittenQuery(BaseModel):
    rewritten: str
```

Important detail: we rewrite **once**, controlled by `state["rewritten"] = True`. Without that guard, an ambiguous-then-still-ambiguous query becomes an infinite loop. In production, replace the boolean with a counter and a hard cap (typically 2-3 rewrites).

### 4. The web fallback

Stubbed for this demo (returns a hardcoded string). In production, swap in:

- **DuckDuckGo Search** (no API key, polite ToS)
- **Tavily** (purpose-built for LLM grounding, API key)
- **Your own search service** (Elasticsearch / OpenSearch / Algolia / etc.)

The interface is just `(query: str) -> str` — return a single string of "external knowledge" to feed the answerer. Easy swap.

### 5. The LangGraph wiring

`StateGraph` with conditional edges makes the routing visible and inspectable:

```python
g.add_conditional_edges("grade", route_after_grade, {
    "use_chunks": "use_chunks",
    "rewrite": "rewrite",
    "web_fallback": "web_fallback",
})
g.add_edge("rewrite", "retrieve")   # loop back!
```

`rewrite → retrieve` is the loop. The state carries `rewritten: bool`, so on the second grade pass even if the verdict is still ambiguous, the router falls through to `use_chunks` instead of rewriting again.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/24_corrective_rag_ollama.py
```

You'll see, for each of the three demo queries: the retrieve step, three per-chunk grades, the aggregate verdict, the routing decision, and the final answer.

---

## Walk-through — the three branches

### Branch 1 — CORRECT (on-corpus, clear query)

The grader finds at least one chunk that directly supports the query. The pipeline uses the chunks as-is and generates a grounded answer.

### Branch 2 — AMBIGUOUS → rewrite → re-retrieve

The grader finds only tangentially related chunks. The query rewriter expands the query, retrieves fresh chunks. If still ambiguous after one rewrite, falls through to `use_chunks` (the `rewritten=True` guard kicks in).

The rewriter can go **too wide** — that's a real failure mode. In production, constrain it harder ("rewrite for **this specific corpus** about LLMs and agents", not just "rewrite generically").

### Branch 3 — INCORRECT → web fallback

The grader correctly identifies that none of the chunks are on-topic. Without CRAG, classical RAG would have fed those off-topic chunks to the answerer. CRAG routes to the web fallback stub instead.

---

## Production patterns

### When to use CRAG

- **Customer-facing chatbots** — wrong answers are reputation damage. Worth the 3-5x cost.
- **RAG of record** — compliance, legal, medical. The "I don't know" answer is required when retrieval misses.
- **Mixed-corpus / mixed-domain** — when your retrieval has highly variable quality across topics.
- **Open-domain Q&A** with a corpus + web fallback — the web fallback is the whole point.

### When to skip CRAG

- **Tightly-scoped internal tools** — if your corpus is exactly aligned with your queries, classical RAG is fine.
- **Cost-sensitive paths** — chatbot greeting handlers, autocomplete, status endpoints.
- **You don't have a good fallback** — if "incorrect" routes to nothing, CRAG just adds latency without adding value.

### Tuning the grader

- **Stricter aggregation** — require *majority* correct, not just *any* correct. Cuts false positives.
- **Confidence threshold** — extend the schema with `confidence: float` and only trust grades above some threshold.
- **Per-chunk filtering** — instead of an all-or-nothing verdict, keep only the chunks graded "correct" and drop the rest. Drastically improves answer quality on borderline queries.
- **Cheaper grader model** — for Ollama, `llama3.2:3b` is faster for binary/ternary classification. Don't pay full Llama3.2 inference time for a yes/no judgment.

### Composing with other patterns

CRAG is **orthogonal** to the retrieval substrate:

```python
# Classical RAG + CRAG
chunks = vector_store.similarity_search(query, k=5)

# Hybrid RAG + CRAG
chunks = reciprocal_rank_fusion([dense_hits, sparse_hits])

# GraphRAG + CRAG
chunks = extract_subgraph_context(graph, seed_entities)
```

Whatever retrieval you use, **grade the output and route accordingly**. The grader doesn't care how the chunks were retrieved.

---

## Try this

1. **Tighten the rewriter** — change the system prompt to "rewrite for a corpus about AI agents, LangChain, and LLMs". Re-run the "memory thing" query — does the rewrite stay on-topic now?
2. **Switch the grader to a smaller model** — use `ChatOllama(model="llama3.2:3b")` *just for the grader*. Time the run. Same verdicts? (Spoiler: usually yes.)
3. **Add per-chunk filtering** — modify `node_use_chunks` to keep only chunks graded `correct`. Re-run Demo 1 — does the answer get cleaner?
4. **Wire in a real web search** — `pip install duckduckgo-search`, replace `web_search()` with a real call. Try queries about current events (the corpus has zero coverage of news).
5. **Add a max-retry counter** — replace the `rewritten: bool` with `rewrite_count: int`, allow up to 3 rewrites before falling back to web. Test with a query that's truly hard to retrieve.

---

## Mental model

> **Retrieve, then judge what you retrieved, then route.**

That's the entire CRAG idea. Everything else — the rewriter, the web fallback, the LangGraph wiring, the verdict aggregation — is implementation detail around that one shift.

The shift is small. The behavior change is large. You move from a system that *always* tries to answer (and sometimes fabricates) to a system that *knows when retrieval failed* and *does something about it*.

---

## FAQ

**Q: Why three verdicts instead of a binary correct/incorrect?**
The middle bucket — "ambiguous" — is what makes the rewrite branch worth having. Binary classification forces every borderline case into one of two extremes; ternary lets you say "this is close but the query needs work" and trigger a fix.

**Q: Won't the grader sometimes be wrong?**
Yes. Grader accuracy is ~85-92% in practice. But the failure modes are mostly **conservative**: graders tend to mark things ambiguous when they should be correct, which triggers a rewrite (mild cost, no quality loss). False positives in the other direction are rarer because the grader prompt explicitly asks for strictness.

**Q: How is CRAG different from "Self-RAG"?**
Self-RAG is similar in spirit but more integrated — the answerer model itself generates reflection tokens inline during generation. CRAG is more modular: separate grader, separate rewriter, separate answerer. Easier to debug, easier to swap parts. Both are legitimate designs.

**Q: How is CRAG different from RAG-Fusion?**
RAG-Fusion fans out queries (generate 3-5 variants, retrieve for each, fuse the results). CRAG is reactive — only rewrites *if* the grader says ambiguous. They compose well: use RAG-Fusion as your retriever, then grade with CRAG.

**Q: Doesn't grading every chunk get expensive on long contexts?**
Yes. Two mitigations: (1) use the smallest model that can do the judgment — `llama3.2:3b` is usually fine, (2) batch the grading into a single call ("here are 5 chunks, give me 5 verdicts") instead of one call per chunk. The latter cuts cost ~4x with minimal accuracy loss.

**Q: Why LangGraph instead of plain Python `if/else`?**
For a 3-branch pipeline, either works. LangGraph wins when:
- you want to visualize the graph (`graph.get_graph().draw_mermaid_png()`)
- you want to add checkpointing / time-travel later
- you want to compose this with the LangGraph patterns from Session 10
- the team standardizes on it for all stateful workflows

For this demo, the LangGraph version is ~30 lines longer than plain Python but the routing is much clearer to read.

---

## Related

- **Previous:** [23 — GraphRAG](23-graph-rag.md)
- **Next:** Session 14 — Evaluation (Ragas + LangSmith — start of Track F: Production)
- **Builds on:** [09 — RAG](09-rag.md) (the baseline pipeline), [05 — Structured output](05-structured-output.md) (the grader/rewriter use it), [21 — Custom LangGraph](21-custom-langgraph.md) (the routing pattern)
- **Skill it lives under:** [`labs/skills/agenticcourse-rag/SKILL.md`](../skills/agenticcourse-rag/SKILL.md) — CRAG is listed there; this lesson is the deep dive
- **Track E.5 status:** ✓ **COMPLETE** — Hybrid (11), Graph (12), Corrective (13). All five Brij RAG architectures now in the curriculum (multimodal was covered in Session 9).
