---
name: agenticcourse-rag
description: Use when the user asks about Retrieval-Augmented Generation, vector stores, chunking, embeddings, similarity search, or grounding LLM answers in private documents. Provides the canonical 6-stage pipeline, the chunk-embedding link, what the LLM actually sees, and common pitfalls.
---

# RAG — Canonical Pattern + Pitfalls

## The 6-stage pipeline

```
INDEXING (once):
   raw source  →  Loader  →  Splitter  →  Embedder  →  Vector Store
                                              ↑
                                  chunks + vectors stored together

QUERYING (per request):
   question  →  Embedder  →  cosine vs all stored vectors  →  top-k chunks
                                                                    ↓
                                                  prompt + chunks → LLM → answer
```

## What the LLM actually sees

**Plain text. Just two messages.** The LLM does NOT see vectors, the retriever, or any non-retrieved chunks. The chunks get inlined into the human message *before* the API call.

```
SystemMessage: "Answer strictly from the provided context..."
HumanMessage:  "Context:
                [from doc1.md] <chunk 1>
                ---
                [from doc1.md] <chunk 2>
                
                Question: <user query>
                Answer concisely."
```

If you want the model to see metadata (source filenames, dates, authors), **inline it as text**.

## The chunk ↔ embedding link

The embedding is a **deterministic function** of the chunk's text. They live in the same row of the vector store:

| id | text (page_content) | metadata | vector |
|---|---|---|---|
| uuid | "..." | {"source": "..."} | 384 floats |

You don't reference the embedding by an ID; you compute it from the text. Same text → same vector. **Change the embedding model → all stored vectors are wrong → must re-index.**

## Component defaults (good starting points)

- **Splitter**: `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)` for prose
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` for local/free; OpenAI `text-embedding-3-small` for production scale
- **Vector store**: `InMemoryVectorStore` for demos; FAISS / Chroma / pgvector / Pinecone for production
- **k**: 3-5 for small corpora; tune empirically + add re-ranking for large

## The honest truth — the LLM blends context + pre-training

You cannot fully constrain the LLM to "only context." The model uses pre-training for:
- Language understanding
- General world knowledge
- Reasoning across chunks
- Filling small gaps

For high-stakes RAG (compliance, medical, legal), harden with:
- Strict "answer ONLY from context" system instructions
- Inline citation requirements
- A second-LLM faithfulness judge (see agenticcourse-guardrails)
- Refusal training in few-shot examples

100% grounding from prompting alone is **not achievable**. RAG biases the model, not constrains it.

## Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Bad chunking | Retrieved chunks contain irrelevant context | Smaller chunks; chunk on natural boundaries (headers); add overlap |
| Wrong embedding model | Cosine similarity is meaningless on your domain | Try domain-specific models (Voyage Legal/Code/Finance) or fine-tune |
| Too small `k` | Misses relevant content | Increase k; add re-ranking |
| Too large `k` | Dilutes context; costs more tokens | Add a re-ranker (top-N then top-K) |
| Stale index | Doc updates not reflected | Set a re-index cadence; track doc timestamps |
| Forgot to re-embed on model swap | New queries embedded by f₂, stored vectors are from f₁ | Always re-index after embedding-model change |

## Evaluation metrics (4 to track)

- **Faithfulness** — does the answer derive from the chunks? (Most important.)
- **Answer relevance** — does it address the question?
- **Context precision** — are retrieved chunks relevant? (Per-retrieval quality.)
- **Context recall** — did retrieval find ALL relevant chunks? (Per-retrieval coverage.)

Library: `ragas` is the standard for measuring these.

## Variants to consider

- **Hybrid RAG**: combine dense + BM25 sparse; merge with Reciprocal Rank Fusion (15-30% retrieval quality boost)
- **Agentic RAG**: expose `retrieve_docs` as a tool the agent decides when to call (don't retrieve on greetings)
- **GraphRAG**: extract entities + relationships; navigate the graph for multi-hop answers
- **Corrective RAG (CRAG)**: grade the retrieval before trusting it; rewrite query or fall back to web search if bad
- **Multimodal RAG**: unified embedding (CLIP/ColPali) across text + images + tables

## Mental model in one line

> **RAG = "I pick the right text client-side, the LLM reads only that text." Embeddings exist for one purpose: to choose which chunks to put in the prompt. After that, it's just a normal LLM call.**
