# 22 — Hybrid RAG (Session 11)

> **Dense embeddings + BM25 sparse search + Reciprocal Rank Fusion.** The single highest-ROI upgrade to plain dense-only RAG — typically 15-30% better recall on mixed-query workloads, for ~20 lines of code on top of `09_rag.py`.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Tracks A/B/C/D/E: ✓ all done
                                                           Track E.5: RAG Architectures
                                                             ▶ Session 11: HYBRID RAG  ◄ HERE
                                                             ○ Session 12: GraphRAG
                                                             ○ Session 13: Corrective RAG
                                                           Track F: ○ Production
```

**Why this lesson now:** the basic dense-only RAG you built in `09_rag.py` is fine for clean semantic queries. Real users ask all kinds — paraphrased descriptions AND exact class names AND error codes. Hybrid RAG catches the queries dense alone misses.

---

## File involved

| File | Role |
|---|---|
| [`22_hybrid_rag.py`](../22_hybrid_rag.py) | Indexes the same corpus as `09_rag.py`. Runs three side-by-side retrievers (dense / sparse / hybrid) against three queries — each chosen to highlight a different retriever's strengths. |

---

## What problem it solves

Dense embeddings (`sentence-transformers/all-MiniLM-L6-v2`, OpenAI `text-embedding-3-small`, etc.) are great at **semantic similarity**:

- *"how does caching reduce cost"* → finds chunks about "$0.30/M vs $3/M pricing"
- *"the agent forgot what I told it earlier"* → finds chunks about MemorySaver
- *"this output looks made up"* → finds chunks about hallucination, faithfulness, grounding

They are **bad** at exact keyword matching:

- *"sk-ant-api03"* → won't reliably find the chunk that literally contains that API-key prefix
- *"PCI-DSS"* → embeddings may flatten this to "compliance"
- *"MemorySaver"* (class name) → may rank generic "memory state" chunks above the actual MemorySaver chunk

**BM25** (the canonical sparse-retrieval algorithm, 1990s vintage) is the opposite. Exact term matches dominate; semantic relatedness barely enters.

Real users ask **mixed** queries — *"memory checkpointer in MemorySaver"* needs both signals. Neither retriever alone is best; **hybrid is consistently better than either**.

---

## The analogy

**Two librarians of different skills.**

The *semantic librarian* (dense) knows the books deeply and finds you something on the right topic even if you describe it loosely. *"Got anything on the brain-body connection?"* → "Try Damasio."

The *keyword librarian* (BM25) is methodical with the catalogue. *"I'm looking for ISBN 9780525436126."* → "Here, third shelf, fourth from left."

For most real questions you want both opinions, then merge. Hybrid RAG is asking both librarians the same question, then ranking the books based on how often and how confidently they each recommended them.

---

## Visual

```
   query
     │
     ├──────────────┐
     │              │
     ▼              ▼
  ┌────────┐    ┌────────┐
  │ DENSE  │    │ SPARSE │
  │ embed+ │    │ BM25   │
  │ cosine │    │        │
  └───┬────┘    └───┬────┘
      │              │
   ranked list    ranked list
   [A, B, C, ...]  [B, D, A, X, ...]
      │              │
      └──────┬───────┘
             ▼
    ┌──────────────────────┐
    │ Reciprocal Rank      │
    │ Fusion (RRF):         │
    │ score(d) = Σ 1/(k+r)  │   k=60 conventional
    └──────────┬───────────┘
               ▼
        merged top-K
   (docs corroborated by both
    retrievers float to the top)
```

---

## Concept — the three retrievers

```python
# Dense — same as 09_rag.py
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
dense_store = InMemoryVectorStore.from_documents(chunks, embeddings)

def dense_search(query, k=5):
    return dense_store.similarity_search(query, k=k)


# Sparse — BM25 over tokenized chunks
tokenized = [doc.page_content.lower().split() for doc in chunks]
bm25 = BM25Okapi(tokenized)

def sparse_search(query, k=5):
    scores = bm25.get_scores(query.lower().split())
    top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
    return [chunks[i] for i in top_indices]


# Hybrid — RRF over both
def reciprocal_rank_fusion(ranked_lists, k_rrf=60, top_k=5):
    fused: dict[int, float] = {}
    doc_by_id: dict[int, Document] = {}
    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list, start=1):
            key = id(doc)
            fused[key] = fused.get(key, 0.0) + 1.0 / (k_rrf + rank)
            doc_by_id[key] = doc
    top_keys = sorted(fused, key=fused.get, reverse=True)[:top_k]
    return [doc_by_id[k] for k in top_keys]

def hybrid_search(query, k=5, retriever_k=10):
    return reciprocal_rank_fusion(
        [dense_search(query, k=retriever_k),
         sparse_search(query, k=retriever_k)],
        top_k=k,
    )
```

That's the whole thing. **No score normalization** — RRF only uses ranks.

---

## RRF in one paragraph

For each document seen across all retrievers' ranked lists:

```
score(doc) = Σ over retrievers: 1 / (k + rank_in_that_retriever)
```

`k` is a constant — conventionally **60** (from the original 2009 RRF paper by Cormack et al.).

A document at rank 1 contributes `1/61 ≈ 0.0164`. At rank 10, `1/70 ≈ 0.0143`. At rank 100, `1/160 ≈ 0.0063`. The score falls off slowly — that's by design. **A doc that appears at rank 5 in both retrievers usually beats a doc that appears at rank 1 in only one** — corroboration wins.

Why no normalization? BM25 scores are typically 0-30; cosine similarities are 0-1. Different scales. RRF sidesteps this entirely by working only with ranks.

---

## Run it

```bash
python 22_hybrid_rag.py
```

Three queries, three retrievers, side-by-side top-3 for each. Plus a synthetic RRF math illustration at the end.

---

## Real results from a clean run

### Query 3 (the interesting one)

> *"prompt caching with cache_control marker"*

Needs both the *concept* (prompt caching) AND the *exact keyword* (`cache_control`).

**DENSE top-3** (semantic only):
1. `[LEARNINGS.md] The wire reality... cache_control is just a hint...`
2. `[LEARNINGS.md] Three rules that bite — Caches are byte-exact...`
3. `[LEARNINGS.md] Critical rule: the cache key is the entire prefix...`

**SPARSE top-3** (BM25 keyword):
1. `[LEARNINGS.md] Real numbers from 04_prompt_caching.py...`
2. `[LEARNINGS.md] Files added in this part... 03_agent_framework.py...`
3. `[LEARNINGS.md] LangChain — Part 2: Frameworks, Token Economics...`

**HYBRID top-3** (RRF-fused):
1. `[LEARNINGS.md] The wire reality... cache_control is just a hint...` *(dense rank 1)*
2. `[LEARNINGS.md] Real numbers from 04_prompt_caching.py...` *(sparse rank 1)*
3. `[LEARNINGS.md] Three rules that bite...` *(dense rank 2)*

Hybrid pulls the strongest from each. Dense alone misses the "real numbers" chunk that sparse found via exact-term matching. Sparse alone surfaces meta/TOC chunks that don't really answer the question. The fusion gets the best of both.

---

## Walk-through — when each retriever wins

### Dense wins when

- Query is a **paraphrase** of what's in the corpus
- Query uses synonyms or descriptions
- The exact words may not be in the chunks
- Example: *"why are LLM bills high"* → finds chunks about input/output token pricing

### Sparse (BM25) wins when

- Query has **rare exact terms** (proper names, IDs, error codes, class names)
- Query is short / keyword-style
- Embeddings flatten domain-specific jargon
- Example: *"PostgresSaver"* → finds the one chunk with that exact class name

### Hybrid wins when

- **The query mixes both** — concept + keyword
- You don't know what kind of query your user will type (real production case)
- The corpus has a mix of prose and structured content (code, tables, error messages)

**In practice, hybrid is almost always the right default for any corpus where users ask mixed-style questions.** That covers most production RAG.

---

## Production patterns this unlocks

| Pattern | Real use case |
|---|---|
| **Hybrid by default** | Any user-facing search where queries aren't predictable in style |
| **Re-ranking on top of RRF** | Add a cross-encoder reranker for another 5-10% quality at modest cost |
| **Multi-modal RRF** | Combine text-RAG + image-RAG ranks via RRF (for visual corpora) |
| **A/B testing the fusion** | Try `k_rrf=10` vs `k_rrf=60` vs `k_rrf=200`; measure on golden dataset |
| **Cascading retrieval** | First-stage hybrid for recall (top-100), second-stage cross-encoder for precision (top-5) |

---

## Try this

1. **Change `k_rrf`** from 60 to 10 vs 200. With `k=10`, top-ranked items dominate strongly. With `k=200`, results are very democratic. Pick what works for your corpus.
2. **Add a re-ranker** — pip install `sentence-transformers/cross-encoder/ms-marco-MiniLM-L-6-v2`, score the top-10 hybrid candidates, return top-3 by cross-encoder score. Often the single biggest quality lift.
3. **Test with edge-case queries** — search for an exact class name from your corpus (`PostgresSaver`, `MemorySaver`, etc.). Watch sparse dominate. Then search for a paraphrase. Watch dense dominate.
4. **Plug hybrid into `11_production_chatbot.py`** — replace the `retrieve_docs` tool's dense-only retriever with `hybrid_search`. Same agent loop; better retrieval quality.
5. **Profile cost** — measure cost per query for dense-only vs hybrid. Hybrid is *cheaper* on the retrieval side (BM25 is free) but you still pay for the embedding. The win is quality, not cost.

---

## Mental model in one line

> **Hybrid RAG = ask two different librarians the same question, then trust the docs that BOTH put near the top. Reciprocal Rank Fusion is the merge math; it works because ranks normalize across scoring scales. 15-30% retrieval quality boost for 20 lines of code is the highest-ROI RAG upgrade you can make.**

---

## FAQ

**Q: Do I need a separate index for BM25?**

A: Yes — BM25 needs tokenized text. `rank_bm25` is the easy in-memory option (works for ~1M chunks). For larger corpora, use Elasticsearch / OpenSearch / Typesense — they have BM25 built in and offer persistence + concurrency.

**Q: Does the embedding model matter for hybrid?**

A: Less than for dense-only. Hybrid is more robust to mediocre embeddings because BM25 catches the keyword-precision failures. You can use a cheap local model and still get good hybrid quality.

**Q: What about TF-IDF instead of BM25?**

A: BM25 is TF-IDF with length normalization (longer docs don't get unfair advantage from raw term-frequency counts). Always pick BM25 over plain TF-IDF — it's strictly better for the same compute.

**Q: How does this compare to using a generative model for re-ranking?**

A: Different layer. Hybrid retrieval = first-stage recall (get the top-50 candidates). Generative reranking = second-stage precision (use an LLM-judge or cross-encoder to pick the top-3 from the 50). Production stacks usually do both.

**Q: Why k=60 in RRF?**

A: The original paper (Cormack 2009) settled on `k=60` empirically. It's the conventional default. Real production RAG occasionally tunes it (small `k` for high-precision needs; large `k` for democratic recall), but `k=60` is rarely wrong.

**Q: Is hybrid always better than dense-only?**

A: For corpora with prose-only content and clean semantic queries, dense-only is fine. For corpora with code / IDs / error messages / class names / proper nouns, hybrid is significantly better. For unknown query styles (i.e., most production), hybrid is the safer default.

**Q: Can I have THREE retrievers (dense + sparse + something else)?**

A: Yes — RRF generalizes to N ranked lists. Just sum the contributions from each retriever. Common third source: a metadata-filtered retrieval (e.g., "only docs from the last 30 days"), or a knowledge-graph traversal score.

**Q: How does this compare to GraphRAG?**

A: Orthogonal. GraphRAG (Session 12 in this curriculum) augments retrieval with a knowledge graph for multi-hop questions. You can combine them: dense + BM25 + graph-traversal, all fused via RRF.

**Q: Does this work with re-ranking?**

A: Yes — and it's the typical production pattern. Hybrid retrieval gives you a high-recall top-50; a cross-encoder re-ranker (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) re-scores those 50 and returns top-3. Three layers in total: hybrid (recall) + RRF (fusion) + cross-encoder (precision).

**Q: What's the LangChain-native way?**

A: `langchain.retrievers.EnsembleRetriever` with `weights` parameter — but that uses **weighted score normalization**, not RRF. It works but requires you to pick weights (an extra hyperparameter). RRF is simpler and usually competitive. For pure-LangChain installs, `EnsembleRetriever` is fine; we wrote RRF by hand here for clarity.

---

## HyDE — Hypothetical Document Embeddings

### The problem

Query embeddings and document embeddings live in different semantic spaces.
A short user question like "photosynthesis?" has a very different embedding
than a long document passage that explains photosynthesis in detail.
Dense retrieval underperforms when questions are short but corpus documents are long.

### Solution

```
query → Claude generates hypothetical answer → embed the answer → search with that vector
```

Instead of embedding the sparse query, you embed a *hypothetical document* that would
answer the query. That hypothetical answer lives in the same semantic space as real
document chunks — closing the query-document gap.

### When to use HyDE

- Knowledge-dense corpora where user questions are short telegraphic phrases
- Technical docs where questions are brief but matching passages are several paragraphs
- When dense-only retrieval recall is measurably below hybrid (check with eval harness)

### Code

```python
import anthropic
from typing import Any

def hyde_retrieve(
    query: str, vectorstore: Any, client: anthropic.Anthropic, k: int = 4
) -> list[Any]:
    """HyDE: generate a hypothetical answer, embed it, use as the query vector."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": f"Write a short, factual answer to: {query}",
        }],
    )
    hypothetical_answer = response.content[0].text
    return vectorstore.similarity_search(hypothetical_answer, k=k)
```

### Cost trade-off

HyDE adds one extra LLM call per query (generating the hypothetical answer).
That call returns ~100-300 tokens at Haiku pricing (~$0.0001). Against the
background of a full RAG answer call, HyDE's overhead is marginal — but measure
it with `time.perf_counter` before enabling in high-volume paths.

---

## Related

- **Previous:** [21 — Custom LangGraph + HITL](21-custom-langgraph.md)
- **Next:** Session 12 — GraphRAG (Track E.5 continues)
- **Builds on:** [09 — RAG](09-rag.md) (the dense-only baseline)
- **Skill it goes into:** [`labs/skills/agenticcourse-rag/SKILL.md`](../skills/agenticcourse-rag/SKILL.md) — Hybrid is listed as a variant; this lesson is the deep dive
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 11 of 40 (Track E.5 1/3)
