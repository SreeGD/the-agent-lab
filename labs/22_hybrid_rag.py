"""Hybrid RAG — dense + sparse + Reciprocal Rank Fusion.

Same corpus as 09_rag.py (NOTES.md + LEARNINGS.md). Three retrievers run
against three queries. The queries are chosen so each retriever shines on
one but the hybrid catches them all.

Dense  : semantic similarity via sentence-transformers + InMemoryVectorStore.
         Great on paraphrases, weak on rare exact terms (class names, IDs).
Sparse : BM25 keyword search via rank_bm25. Opposite trade-off — wins on
         exact-term queries, loses on semantic paraphrase.
Hybrid : Run both, fuse with Reciprocal Rank Fusion (RRF). No score-normalization
         needed because RRF only uses ranks.
"""

from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

load_dotenv()

HERE = Path(__file__).parent

# =====================================================================
# Index corpus (same as 09_rag.py)
# =====================================================================

print("Loading corpus (NOTES.md + LEARNINGS.md)...")
docs: list[Document] = []
for name in ["NOTES.md", "LEARNINGS.md"]:
    docs.extend(TextLoader(str(HERE / name)).load())

chunks = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=120,
    separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
).split_documents(docs)
print(f"  Indexed {len(chunks)} chunks.")


# =====================================================================
# Dense retriever — sentence-transformers + InMemoryVectorStore
# =====================================================================

print("Building dense index (sentence-transformers/all-MiniLM-L6-v2)...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
dense_store = InMemoryVectorStore.from_documents(chunks, embeddings)


def dense_search(query: str, k: int = 5) -> list[Document]:
    return dense_store.similarity_search(query, k=k)


# =====================================================================
# Sparse retriever — BM25 over tokenized chunk text
# =====================================================================

print("Building BM25 sparse index...")
_tokenized_corpus = [doc.page_content.lower().split() for doc in chunks]
bm25 = BM25Okapi(_tokenized_corpus)


def sparse_search(query: str, k: int = 5) -> list[Document]:
    scores = bm25.get_scores(query.lower().split())
    top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
    return [chunks[i] for i in top_indices]


# =====================================================================
# Hybrid retriever — Reciprocal Rank Fusion
# =====================================================================

def reciprocal_rank_fusion(
    ranked_lists: list[list[Document]],
    k_rrf: int = 60,
    top_k: int = 5,
) -> list[Document]:
    """
    Merge multiple ranked Document lists into one using RRF.

    For each doc in each list: score += 1 / (k_rrf + rank).
    Higher k_rrf = more democratic (top-1 dominance softened).
    Lower k_rrf = top-ranked items in each retriever dominate the merged list.
    k_rrf = 60 is the conventional default (from the original 2009 RRF paper).
    """
    # Track scores by chunk identity (id() of the Document object suffices
    # since both retrievers return references to the SAME chunks list).
    fused: dict[int, float] = {}
    doc_by_id: dict[int, Document] = {}
    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list, start=1):
            key = id(doc)
            fused[key] = fused.get(key, 0.0) + 1.0 / (k_rrf + rank)
            doc_by_id[key] = doc

    top_keys = sorted(fused, key=fused.get, reverse=True)[:top_k]
    return [doc_by_id[k] for k in top_keys]


def hybrid_search(query: str, k: int = 5, retriever_k: int = 10) -> list[Document]:
    """Run dense + sparse with a wider k each, fuse via RRF."""
    dense_hits = dense_search(query, k=retriever_k)
    sparse_hits = sparse_search(query, k=retriever_k)
    return reciprocal_rank_fusion([dense_hits, sparse_hits], top_k=k)


# =====================================================================
# Three demo queries — chosen to exercise each retriever's strengths
# =====================================================================

QUERIES = [
    {
        "query": "how does caching reduce inference cost",
        "expected_winner": "DENSE",
        "rationale": "Semantic paraphrase. 'reduce cost' and 'cheaper' aren't always lexically present.",
    },
    {
        "query": "MemorySaver thread_id",
        "expected_winner": "SPARSE",
        "rationale": "Exact class + parameter names. BM25 should match these strongly.",
    },
    {
        "query": "prompt caching with cache_control marker",
        "expected_winner": "HYBRID",
        "rationale": "Needs the CONCEPT (prompt caching) AND the exact keyword (cache_control).",
    },
]


def _preview(doc: Document, length: int = 100) -> str:
    src = Path(doc.metadata["source"]).name
    return f"[{src}] {doc.page_content[:length].strip()}..."


def run_query_demo(query_info: dict) -> None:
    query = query_info["query"]
    print("\n" + "=" * 70)
    print(f"QUERY: {query!r}")
    print(f"  expected winner: {query_info['expected_winner']}")
    print(f"  rationale: {query_info['rationale']}")
    print("=" * 70)

    print("\n  DENSE top-3 (semantic):")
    for i, d in enumerate(dense_search(query, k=3), 1):
        print(f"    [{i}] {_preview(d, 95)}")

    print("\n  SPARSE top-3 (BM25 keyword):")
    for i, d in enumerate(sparse_search(query, k=3), 1):
        print(f"    [{i}] {_preview(d, 95)}")

    print("\n  HYBRID top-3 (RRF fusion):")
    for i, d in enumerate(hybrid_search(query, k=3, retriever_k=10), 1):
        print(f"    [{i}] {_preview(d, 95)}")


# =====================================================================
# Small synthetic RRF illustration (helps build intuition)
# =====================================================================

def show_rrf_math() -> None:
    print("\n" + "=" * 70)
    print("MINI RRF EXAMPLE — synthetic ranks for 4 docs")
    print("=" * 70)
    print(
        "\n  Suppose dense ranked docs as [A, B, C, D] and sparse as [B, D, A, X].\n"
        "  With k_rrf = 60:\n"
        "    score(A) = 1/(60+1)  +  1/(60+3)  ≈ 0.01639 + 0.01587 = 0.03226\n"
        "    score(B) = 1/(60+2)  +  1/(60+1)  ≈ 0.01613 + 0.01639 = 0.03252\n"
        "    score(C) = 1/(60+3)                ≈              0.01587\n"
        "    score(D) = 1/(60+4)  +  1/(60+2)  ≈ 0.01563 + 0.01613 = 0.03176\n"
        "    score(X) =              1/(60+4)  ≈              0.01563\n"
        "\n  Final order: B, A, D, C, X.\n"
        "  → Note: B beats A despite A being rank-1 in dense, because B appears\n"
        "    in BOTH ranked lists at high positions. That's the RRF advantage —\n"
        "    docs corroborated by multiple retrievers float to the top.\n"
    )


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("HYBRID RAG — dense + sparse + Reciprocal Rank Fusion")
    print("=" * 70)
    print(f"  Corpus: {len(chunks)} chunks from NOTES.md + LEARNINGS.md")
    print(f"  Dense:  sentence-transformers/all-MiniLM-L6-v2 (384 dims)")
    print(f"  Sparse: BM25Okapi via rank_bm25")
    print(f"  Fusion: Reciprocal Rank Fusion (k=60)")

    for q_info in QUERIES:
        run_query_demo(q_info)

    show_rrf_math()

    print("\n" + "=" * 70)
    print("PRODUCTION TAKEAWAYS")
    print("=" * 70)
    print(
        "  • Hybrid retrieval consistently outperforms dense-only on real\n"
        "    corpora — typically 15-30% better recall on mixed query workloads.\n"
        "  • The cost is ~20 lines of code + a few MB of memory for the BM25\n"
        "    index. The 'sentence-transformers' install dominates the\n"
        "    dependency cost anyway.\n"
        "  • For production: replace rank_bm25 with Elasticsearch / OpenSearch /\n"
        "    Typesense for a real inverted index. Same RRF logic.\n"
        "  • Add a cross-encoder re-ranker on top of RRF for another 5-10%\n"
        "    quality boost (a follow-up worth its own session).\n"
        "  • RRF requires no score normalization — that's its whole point.\n"
        "    BM25 scores (0-30 typically) and cosine similarities (0-1) live\n"
        "    on different scales; ranks normalize them naturally."
    )
