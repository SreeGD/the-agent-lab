# 09 — Retrieval-Augmented Generation (RAG)

> **Ground the LLM's answer in your own documents.** Load → split → embed → store → retrieve → generate. The most-used pattern in production AI.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01-08 (foundation)                                      ○ 13 system     ○ 16-19 Healthcare
                                                              design       ○ 20-22 Agriculture
  ▶ 09 RAG  ◄═══════ YOU ARE HERE                          ○ 14 red-team   ○ 23-25 Finance
                                                           ○ 15 AI UX      ○ 26-28 Vidya Karana
  ○ 10 guardrails             (safe_rag.py)                                 ○ 29-32 Family AI
  ○ 11 production capstone    (production_chatbot.py)
  ○ 12 MCP                    (mcp_server.py, mcp_client.py)
```

**Why this lesson now:** the LLM only knows what was in its training. To answer about *your* PDFs, *your* knowledge base, *your* customer data, you need RAG. This is the single most useful pattern in production AI.

---

## Files involved

| File | Role |
|---|---|
| [`rag.py`](../rag.py) | Full 6-stage RAG pipeline over your `NOTES.md` + `LEARNINGS.md` (self-referential demo) |

---

## What problem it solves

LLMs don't know:
- Your company's internal docs
- The latest news (after training cutoff)
- Customer-specific data
- Anything proprietary

If you ask Claude *"What's the API for our internal billing service?"* it has no idea. Worse, it might hallucinate a plausible-sounding-but-wrong answer.

RAG fixes this: **at query time, retrieve the relevant chunks from your private docs, stuff them into the prompt, then let the model answer from that context**. Same model, but it now answers about *your* world.

---

## The analogy

A **librarian with a research desk**.

The user asks a question. The librarian (your code) doesn't know the answer either. But she runs to the stacks, pulls the 3 most relevant books, opens them to the right pages, **places them on the user's desk**, then asks the expert (the LLM) to read those pages and answer.

The LLM is the expert reader. The vector store is the card catalog. The retriever is the librarian. **The expert never accesses the library directly** — only the books the librarian put on the desk.

---

## Visual

```
INDEXING (done once at startup):
   raw docs  ──► Loader ──► Documents
                              │
                              ▼
                          Splitter ──► smaller chunks
                                          │
                                          ▼
                                      Embedder ──► (chunk + vector) stored together
                                                       │
                                                       ▼
                                                 Vector Store
                                              (4-field rows: id, text, metadata, vector)

QUERYING (every request):
   question  ──► Embedder  ──► query vector
                                  │
                                  ▼
                       cosine vs every stored vector
                                  │
                                  ▼
                          top-k chunks (text + metadata)
                                  │
                                  ▼
                        prompt + chunks → LLM → answer
```

The vector is the **search key**. The chunk text is what the LLM actually sees.

---

## The concept

```python
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore

# 1. LOAD + 2. SPLIT
docs = TextLoader("NOTES.md").load() + TextLoader("LEARNINGS.md").load()
chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120).split_documents(docs)

# 3. EMBED + 4. STORE
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = InMemoryVectorStore.from_documents(chunks, embeddings)

# 5. RETRIEVE + 6. GENERATE
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

rag_chain = (
    {
        "context": (lambda x: x["question"]) | retriever | format_context,
        "question": lambda x: x["question"],
    }
    | rag_prompt
    | model
    | parser
)

answer = rag_chain.invoke({"question": "How do I add memory to a LangChain agent?"})
```

---

## Run it

```bash
python rag.py
```

The file walks through each of the 6 stages, dissects what's inside the vector store (id, text, metadata, vector), then runs 3 demo questions over the corpus.

---

## The chunk ↔ embedding link

Critical insight that trips most people up:

> **The embedding is a deterministic function of the chunk's text.** `chunk.page_content → embedding_model.embed() → vector (list[float])`. Same text → same vector, every time.

When you call `InMemoryVectorStore.from_documents(chunks, embeddings)`, each chunk is stored as a 4-field record:

| field | content |
|---|---|
| `id` | UUID |
| `text` | `chunk.page_content` (what the LLM sees) |
| `metadata` | `chunk.metadata` (provenance) |
| `vector` | the embedding (384 floats for MiniLM) |

The "link" between chunk and embedding is **the row itself**. They live together because the vector store stores them together.

---

## What the LLM actually sees

**The most important RAG concept:**

> **The LLM only sees plain text. It never sees vectors, the retriever, or any of the chunks that weren't retrieved.**

For one query, the full HTTP request to Anthropic is just two messages:

```
SystemMessage: "Answer strictly from the provided context. Cite sources..."

HumanMessage:  "Context:
                [from LEARNINGS.md] <chunk 1>
                ---
                [from LEARNINGS.md] <chunk 2>
                ---
                [from LEARNINGS.md] <chunk 3>

                Question: <user question>
                Answer concisely."
```

That's it. No third "retrieval" exchange. The chunks are inlined into the human message *before* the API call. The model treats them as part of one big prompt.

**Implication:** if you want the model to see `metadata`, you must inline it as text. The `[from NOTES.md]` source labels appear *only because* `format_context()` wrote them in.

---

## Does the LLM only use the retrieved context?

**No — it blends context + pre-training.** You can't "uninstall" the model's training. Even with a strict system prompt, the LLM uses pre-training for:
- Language understanding
- General world knowledge
- Reasoning across chunks
- Filling small gaps

For high-stakes RAG (compliance, medical, legal), pair grounding with:
- Strong "answer ONLY from context" instructions
- Inline citation requirements
- A second-LLM faithfulness judge ([lesson 10](10-guardrails.md))
- Refusal training in few-shot examples

100% grounding isn't achievable from prompting alone. Treat RAG as **biasing** the model, not constraining it.

---

## Component choices

| Choice | For this demo | Production alternative |
|---|---|---|
| `TextLoader` | Local files | `PyPDFLoader`, `WebBaseLoader`, `DirectoryLoader`, `S3FileLoader`, 100+ others |
| `RecursiveCharacterTextSplitter` | De facto for prose | `MarkdownHeaderTextSplitter`, `LanguageParser` (code) |
| `HuggingFaceEmbeddings` (MiniLM, free, local) | Tiny model, no API key | OpenAI `text-embedding-3-small`, Voyage AI, Cohere |
| `InMemoryVectorStore` | Zero setup | FAISS, Chroma, pgvector, Pinecone, Weaviate |
| `k=3` retrieval | Tutorial-sized corpus | Tune empirically; production uses k=5-20 + re-ranking |

---

## Production patterns this unlocks

| Pattern | Example |
|---|---|
| Document Q&A | Ask questions over PDFs, Confluence, internal docs |
| Customer support bot | Retrieve from product KB, ground answers in policies |
| Research assistant | Retrieve from a citation database, cite sources |
| Code-aware assistant | Embed your codebase, retrieve relevant files for the LLM |
| Compliance Q&A | Retrieve regulations, answer questions with verified citations |

---

## Try this

1. **Ask a question NOT in the notes** — *"What's the weather today?"* With the strict system prompt, Claude correctly says *"I don't have enough information."*
2. **Crank `k`** — `as_retriever(search_kwargs={"k": 8})`. More chunks → more context tokens → potentially better answers, definitely more cost.
3. **Add metadata filtering** — `{"filter": {"source": ".../LEARNINGS.md"}}` retrieves only from one file.
4. **Swap to FAISS persistence** — `FAISS.from_documents(...).save_local("index/")`. Build once, query forever.
5. **Combine RAG + memory** — wrap in `create_react_agent` with `MemorySaver`. Production RAG chatbot in ~30 lines (see [lesson 11](11-production-capstone.md)).

---

## Mental model in one line

> **RAG is "I pick the right text client-side, the LLM reads only that text." Embeddings + vector stores exist for one purpose: to choose which chunks to put in the prompt. After that, it's just a normal LLM call.**

---

## FAQ

**Q: How is RAG different from giving the LLM a giant prompt with everything in it?**

A: Token cost + relevance. Stuffing all your docs into every prompt is expensive (you pay for every token, every request) and dilutes the model's attention. RAG sends only the **relevant** ~2-5 KB per query, picked by cosine similarity. Same accuracy, fraction of the cost.

**Q: What if my docs change frequently?**

A: Re-embed and re-index when docs change. For low-volume changes, do it nightly. For high-volume, incrementally update the vector store (most production stores support this). Frequent re-indexing is one of the operational costs of RAG.

**Q: How do I pick `chunk_size`?**

A: Trade-off between specificity (smaller chunks = more focused matches but more results) and context (larger chunks = more context per match but less precise). Common defaults: 500-1000 tokens for prose, 200-400 for code. Always test against your domain.

**Q: What's `chunk_overlap` for?**

A: To avoid cutting an important sentence in half between chunks. With overlap, the end of chunk N appears at the start of chunk N+1. Loses no information across boundaries. Common: 10-20% of chunk_size.

**Q: Embedding model — should I use OpenAI, Voyage, or local?**

A: For learning + low-volume: local (MiniLM is free, ~80MB, works offline). For high-volume production: OpenAI's `text-embedding-3-small` is cheap and effective. For specialized domains: Voyage's domain models (legal, code, finance) are state-of-the-art.

**Q: How do I evaluate RAG quality?**

A: Four metrics (see [lesson 10](10-guardrails.md) on guardrails and Track F Session 10 on evaluation):
- **Faithfulness** — does the answer derive from the chunks?
- **Answer relevance** — does it address the question?
- **Context precision** — are the retrieved chunks relevant?
- **Context recall** — did retrieval find ALL the relevant chunks?
Ragas is the standard library for measuring these.

**Q: My retriever returns junk chunks. What do I do?**

A: Three levers in order: (1) improve chunking (smaller, headed by section title), (2) better embeddings (try a different model), (3) add a re-ranker (a second model that scores top-N → picks top-K). Re-ranking is the biggest quality win for medium-large corpora.

**Q: Can I do RAG without LangChain?**

A: Absolutely. The pieces are independent — a loader function, a splitter, an embedding model, a vector DB. LangChain just gives you a uniform interface. For small projects: pgvector + raw OpenAI SDK works fine.

**Q: How do I handle very long context — like a 200-page PDF?**

A: Split into many chunks (50-200), embed all, retrieve top-K relevant per query. For *summarization* of the whole doc, use map-reduce (parallel summarize each chunk → final reducer). For Q&A, retrieval is the right pattern.

**Q: Why "Retrieval-Augmented Generation"? What's the "Generation"?**

A: The LLM generates the final answer. RAG is "retrieval-augmented" generation — adding a retrieval step before generation. As opposed to "vanilla generation" (no retrieval, model answers from training).

---

## Related

- **Previous:** [08 — Chatbot memory](08-chatbot-memory.md)
- **Next:** [10 — Guardrails](10-guardrails.md) (faithfulness checking for RAG answers)
- **Production composition:** [11 — Production capstone](11-production-capstone.md) (RAG + memory + caching + guardrails)
- **RAG-as-a-tool pattern:** [12 — MCP](12-mcp.md) — `retrieve_docs` exposed via MCP
