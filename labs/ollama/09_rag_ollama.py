"""RAG (Retrieval-Augmented Generation) demo over the project's own notes.

Pipeline (the canonical 6-stage RAG shape):
  1. LOAD     — TextLoader over NOTES.md + LEARNINGS.md
  2. SPLIT    — RecursiveCharacterTextSplitter (chunk_size=800, overlap=120)
  3. EMBED    — HuggingFaceEmbeddings (all-MiniLM-L6-v2, fully local)
  4. STORE    — InMemoryVectorStore (zero setup; swap for FAISS/Chroma in prod)
  5. RETRIEVE — vectorstore.as_retriever(k=3)
  6. GENERATE — LCEL chain: retriever | prompt | model | parser

On first run, sentence-transformers downloads the ~80MB embedding model.
Subsequent runs are fully offline.
"""
# Requires: ollama serve + ollama pull llama3.2

from pathlib import Path

from langchain_ollama import ChatOllama
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

HERE = Path(__file__).parent.parent


# ============================================================================
# 1. LOAD — turn local files into Document objects
# ============================================================================
print("=" * 70)
print("STAGE 1: LOAD")
print("=" * 70)

sources = ["NOTES.md", "LEARNINGS.md"]
docs: list[Document] = []
for name in sources:
    loader = TextLoader(str(HERE / name))
    docs.extend(loader.load())

print(f"Loaded {len(docs)} Documents from {len(sources)} files.")
for d in docs:
    print(f"  {Path(d.metadata['source']).name:<15} "
          f"page_content: {len(d.page_content):,} chars")


# ============================================================================
# 2. SPLIT — chop into chunks suitable for embedding
# ============================================================================
print("\n" + "=" * 70)
print("STAGE 2: SPLIT")
print("=" * 70)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=120,
    separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
)
chunks: list[Document] = splitter.split_documents(docs)

print(f"Split {len(docs)} Documents into {len(chunks)} chunks.")
print(f"\nExample chunk (chunk #5):")
print(f"  source  : {Path(chunks[5].metadata['source']).name}")
print(f"  length  : {len(chunks[5].page_content)} chars")
print(f"  preview : {chunks[5].page_content[:120].strip()}...")


# ============================================================================
# 3. EMBED — vectorize each chunk
# ============================================================================
print("\n" + "=" * 70)
print("STAGE 3: EMBED")
print("=" * 70)
print("Loading sentence-transformers model (first run downloads ~80MB)...")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
)

# Quick demo: embed one string and report dimensionality
sample_vec = embeddings.embed_query("What is prompt caching?")
print(f"Embedding model ready. Vector dimension: {len(sample_vec)}")
print(f"First 5 values of sample embedding: {[round(v, 4) for v in sample_vec[:5]]}")


# ============================================================================
# 4. STORE — index the chunks
# ============================================================================
print("\n" + "=" * 70)
print("STAGE 4: STORE")
print("=" * 70)

vectorstore = InMemoryVectorStore.from_documents(chunks, embeddings)
print(f"Indexed {len(chunks)} chunks into InMemoryVectorStore.")


# ============================================================================
# DISSECT — what's actually inside InMemoryVectorStore?
# ============================================================================
print("\n" + "=" * 70)
print("DISSECT: peeking inside the vector store")
print("=" * 70)

# InMemoryVectorStore exposes its records as the `store` dict attribute.
# Each record bundles: id, vector, text, metadata — chunk and embedding
# live together in the same row, linked by the same id.
store_dict = vectorstore.store
sample_id = next(iter(store_dict))
sample = store_dict[sample_id]

print(f"\nTotal records: {len(store_dict)}")
print(f"Record container type: {type(store_dict).__name__}")
print(f"One record's fields: {list(sample.keys())}")

print(f"\n--- ONE RECORD (id = {sample_id}) ---")
print(f"  text     : {sample['text'][:90].strip()!r}...")
print(f"  metadata : {sample['metadata']}")
print(f"  vector   : list of {len(sample['vector'])} floats")
print(f"             preview: [{', '.join(f'{v:.4f}' for v in sample['vector'][:5])}, ...]")

# ---- Demo A: determinism — same text always produces the same vector ----
print("\n--- DETERMINISM: same text → same vector ---")
re_embedded = embeddings.embed_query(sample["text"])
all_match = all(abs(a - b) < 1e-6 for a, b in zip(re_embedded, sample["vector"]))
print(f"  Re-embedded the stored text. All {len(re_embedded)} dims match (within 1e-6): {all_match}")
print(f"  → The 'link' is not stored, it's the math: vector = f(text).")

# ---- Demo B: semantic similarity — similar texts → close vectors ----
import math

def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)

print("\n--- SEMANTIC DISTANCE: cosine similarity of three queries ---")
q1 = "What is prompt caching?"
q2 = "How does cache_control reduce input token cost?"
q3 = "What should I have for dinner tonight?"
v1, v2, v3 = embeddings.embed_query(q1), embeddings.embed_query(q2), embeddings.embed_query(q3)

print(f"  cos(q1, q2) = {cosine(v1, v2):.4f}  (similar topic)")
print(f"    q1: {q1!r}")
print(f"    q2: {q2!r}")
print(f"  cos(q1, q3) = {cosine(v1, v3):.4f}  (unrelated topic)")
print(f"    q3: {q3!r}")
print("  → higher cosine = semantically closer = retrieved first.")


# ============================================================================
# 5. RETRIEVE — turn the store into a Runnable that returns top-k chunks
# ============================================================================
print("\n" + "=" * 70)
print("STAGE 5: RETRIEVE")
print("=" * 70)

retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# Sanity check: retrieve for one question
probe = "What is prompt caching and why is it cheaper?"
hits = retriever.invoke(probe)
print(f"Query: {probe!r}")
print(f"Retrieved {len(hits)} chunks:")
for i, h in enumerate(hits, 1):
    print(f"  [{i}] {Path(h.metadata['source']).name}  | "
          f"{h.page_content[:80].strip()}...")


# ============================================================================
# 6. GENERATE — LCEL chain ties it all together
# ============================================================================
print("\n" + "=" * 70)
print("STAGE 6: GENERATE (the RAG chain)")
print("=" * 70)

model = ChatOllama(model="llama3.2", temperature=0)
parser = StrOutputParser()

rag_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You answer questions strictly from the provided context. "
     "If the context does not contain the answer, say so. "
     "Cite sources inline like (NOTES.md) or (LEARNINGS.md) where relevant."),
    ("human",
     "Context:\n{context}\n\nQuestion: {question}\n\nAnswer concisely."),
])


def format_context(chunks: list[Document]) -> str:
    """Join retrieved chunks into a single prompt-friendly context string."""
    return "\n\n---\n\n".join(
        f"[from {Path(c.metadata['source']).name}]\n{c.page_content}"
        for c in chunks
    )


# The full chain:
#   input = {"question": "..."}
#   |--> retrieve hits, format into context
#   |--> build prompt with context + question
#   |--> call model
#   |--> parse to string
rag_chain = (
    {
        "context": (lambda x: x["question"]) | retriever | format_context,
        "question": lambda x: x["question"],
    }
    | rag_prompt
    | model
    | parser
)

# Sub-chain WITHOUT the model — produces the rendered prompt instead of an
# answer. We use this to peek at exactly what would go over the wire.
prompt_only_chain = (
    {
        "context": (lambda x: x["question"]) | retriever | format_context,
        "question": lambda x: x["question"],
    }
    | rag_prompt
)


# ============================================================================
# WHAT THE LLM SEES — render the prompt without calling the model
# ============================================================================
print("\n" + "=" * 70)
print("WHAT THE LLM SEES (rendered prompt, model NOT called)")
print("=" * 70)

peek_question = "Why does prompt caching cost 90% less than normal input?"
prompt_value = prompt_only_chain.invoke({"question": peek_question})
messages = prompt_value.to_messages()

print(f"\nFor the question: {peek_question!r}\n")
print(f"The chain produced {len(messages)} message(s) — this is exactly")
print("what gets sent to the local Ollama server:\n")

for i, m in enumerate(messages, 1):
    role = type(m).__name__
    print("┌" + "─" * 68 + "┐")
    print(f"│ MESSAGE {i}: {role:<55} │")
    print("├" + "─" * 68 + "┤")
    # Indent the content for readability
    for line in m.content.splitlines():
        line = line[:66]
        print(f"│ {line:<66} │")
    print("└" + "─" * 68 + "┘")
    print()

print("Notice: the LLM sees ONLY this text. It does not see:")
print("  - the embedding vectors (lived client-side, already discarded)")
print("  - the retriever or vector store")
print("  - the 152 chunks that were NOT retrieved")
print("  - the cosine similarity scores")
print("  - the chunk UUIDs, the splitter config, anything else")
print("\nFrom the LLM's perspective, this is a normal prompt. RAG happened")
print("entirely on your side of the wire before the API call.")


# ============================================================================
# Demo: ask three questions over the tutorial corpus
# ============================================================================
questions = [
    "Why does prompt caching cost 90% less than normal input?",
    "How do I make a LangChain agent remember things across calls?",
    "What's the difference between PydanticOutputParser and with_structured_output?",
]

for q in questions:
    print("\n" + "=" * 70)
    print(f"QUESTION: {q}")
    print("=" * 70)

    # Show the retrieved chunks so you can see what the model is "reading"
    hits = retriever.invoke(q)
    print(f"\nRetrieved {len(hits)} chunks:")
    for i, h in enumerate(hits, 1):
        print(f"  [{i}] {Path(h.metadata['source']).name}  | "
              f"{h.page_content[:90].strip()}...")

    # Then the answer
    answer = rag_chain.invoke({"question": q})
    print(f"\nANSWER:\n{answer}")
