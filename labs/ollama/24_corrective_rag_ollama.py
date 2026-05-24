# Requires: ollama serve + ollama pull llama3.2
"""Corrective RAG (CRAG) — retrieve, GRADE, then decide.

Classical RAG always trusts its top-k. CRAG inserts a self-correction
loop: each retrieved chunk is graded (correct / ambiguous / incorrect)
by an LLM judge, and the verdict routes the pipeline:

  correct    → answer directly from the retrieved chunks
  ambiguous  → rewrite the query, retrieve again, then answer
  incorrect  → fall back to external knowledge ("web") and answer

Built as a LangGraph StateGraph so the branching is explicit and
inspectable. Same NOTES.md + LEARNINGS.md corpus as 09_rag.py /
22_hybrid_rag.py, so the only new variable is the corrective loop.

Three demo queries exercise each branch:
  1. On-corpus + clear     → CORRECT     → straight answer
  2. On-corpus + vague     → AMBIGUOUS   → rewrite → re-retrieve → answer
  3. Off-corpus question   → INCORRECT   → web fallback → answer
"""

from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

load_dotenv()

HERE = Path(__file__).parent.parent

MODEL = "llama3.2"
model = ChatOllama(model=MODEL, temperature=0)


# =====================================================================
# Index corpus (same as 09_rag.py / 22_hybrid_rag.py)
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

print("Building dense index (sentence-transformers/all-MiniLM-L6-v2)...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vector_store = InMemoryVectorStore.from_documents(chunks, embeddings)


def retrieve(query: str, k: int = 3) -> list[Document]:
    return vector_store.similarity_search(query, k=k)


# =====================================================================
# The retrieval grader — LLM judge with structured output
# =====================================================================

class ChunkGrade(BaseModel):
    """A single chunk's relevance verdict."""
    verdict: Literal["correct", "ambiguous", "incorrect"] = Field(
        description=(
            "'correct' if the chunk directly supports answering the query, "
            "'ambiguous' if it's only tangentially related (might help but "
            "not enough on its own), 'incorrect' if it's off-topic."
        )
    )
    reasoning: str = Field(description="One-sentence justification.")


def grade_chunk(query: str, chunk: Document) -> ChunkGrade:
    grader = model.with_structured_output(ChunkGrade)
    return grader.invoke([
        SystemMessage(
            "You are a strict retrieval grader. Given a user query and a "
            "retrieved chunk, decide if the chunk is correct/ambiguous/"
            "incorrect for answering that specific query. Be honest — "
            "downstream pipelines depend on accurate grading."
        ),
        HumanMessage(f"QUERY: {query}\n\nCHUNK:\n{chunk.page_content}"),
    ])


def aggregate_verdict(grades: list[ChunkGrade]) -> Literal["correct", "ambiguous", "incorrect"]:
    """If any chunk is correct → correct. Else if any ambiguous → ambiguous. Else incorrect."""
    verdicts = [g.verdict for g in grades]
    if "correct" in verdicts:
        return "correct"
    if "ambiguous" in verdicts:
        return "ambiguous"
    return "incorrect"


# =====================================================================
# Query rewriter — used when verdict is "ambiguous"
# =====================================================================

class RewrittenQuery(BaseModel):
    rewritten: str = Field(
        description="A clearer, more retrieval-friendly version of the query: "
                    "expand acronyms, add synonyms, make implicit terms explicit."
    )


def rewrite_query(query: str) -> str:
    rewriter = model.with_structured_output(RewrittenQuery)
    result = rewriter.invoke([
        SystemMessage(
            "Rewrite the user query to be more effective for keyword + semantic "
            "search over technical documentation. Expand abbreviations, add likely "
            "synonyms, and surface implicit concepts. Keep it under 25 words."
        ),
        HumanMessage(query),
    ])
    return result.rewritten


# =====================================================================
# Web fallback — stubbed for repeatability
# =====================================================================

WEB_KNOWLEDGE_BASE = {
    "default": (
        "The author of 'War and Peace' is Leo Tolstoy. It was published serially "
        "between 1865 and 1869. The novel is set against the backdrop of the "
        "Napoleonic invasion of Russia."
    ),
}


def web_search(query: str) -> str:
    """Stand-in for a real web search (DuckDuckGo / Tavily / etc).
    Returns a single 'external knowledge' string so demos are deterministic."""
    print(f"    [web_search stub] would call DuckDuckGo/Tavily for: {query!r}")
    return WEB_KNOWLEDGE_BASE["default"]


# =====================================================================
# LangGraph state + nodes
# =====================================================================

class CRAGState(TypedDict):
    query: str
    original_query: str
    chunks: list[Document]
    grades: list[ChunkGrade]
    verdict: Literal["correct", "ambiguous", "incorrect", ""]
    rewritten: bool
    context: str
    answer: str


def node_retrieve(state: CRAGState) -> dict:
    print(f"  [retrieve] query={state['query']!r}")
    hits = retrieve(state["query"], k=3)
    print(f"  [retrieve] got {len(hits)} chunks")
    return {"chunks": hits}


def node_grade(state: CRAGState) -> dict:
    print(f"  [grade] judging {len(state['chunks'])} chunks...")
    grades = [grade_chunk(state["original_query"], c) for c in state["chunks"]]
    for i, g in enumerate(grades, 1):
        print(f"    chunk {i}: {g.verdict:<10} — {g.reasoning[:80]}")
    verdict = aggregate_verdict(grades)
    print(f"  [grade] aggregate verdict: {verdict.upper()}")
    return {"grades": grades, "verdict": verdict}


def node_rewrite(state: CRAGState) -> dict:
    new_q = rewrite_query(state["original_query"])
    print(f"  [rewrite] {state['original_query']!r}")
    print(f"            → {new_q!r}")
    return {"query": new_q, "rewritten": True}


def node_web_fallback(state: CRAGState) -> dict:
    print(f"  [web_fallback] verdict=incorrect, retrieving external knowledge")
    external = web_search(state["original_query"])
    return {"context": external}


def node_use_chunks(state: CRAGState) -> dict:
    """Pack the correct/ambiguous chunks into context for the answerer."""
    keep = [c.page_content for c, g in zip(state["chunks"], state["grades"]) if g.verdict != "incorrect"]
    return {"context": "\n\n---\n\n".join(keep)}


def node_answer(state: CRAGState) -> dict:
    print(f"  [answer] generating from {len(state['context'])} chars of context")
    response = model.invoke([
        SystemMessage(
            "Answer the user's question using ONLY the provided context. "
            "If the context doesn't contain the answer, say so explicitly. "
            "Be concise — 2-3 sentences."
        ),
        HumanMessage(f"CONTEXT:\n{state['context']}\n\nQUESTION: {state['original_query']}"),
    ])
    return {"answer": response.content}


# =====================================================================
# Conditional edges — the routing brain of CRAG
# =====================================================================

def route_after_grade(state: CRAGState) -> str:
    """correct → use_chunks. ambiguous → rewrite (only once). incorrect → web."""
    if state["verdict"] == "correct":
        return "use_chunks"
    if state["verdict"] == "ambiguous" and not state.get("rewritten"):
        return "rewrite"
    if state["verdict"] == "ambiguous":
        return "use_chunks"
    return "web_fallback"


# =====================================================================
# Build the graph
# =====================================================================

def build_crag_graph():
    g = StateGraph(CRAGState)
    g.add_node("retrieve", node_retrieve)
    g.add_node("grade", node_grade)
    g.add_node("rewrite", node_rewrite)
    g.add_node("use_chunks", node_use_chunks)
    g.add_node("web_fallback", node_web_fallback)
    g.add_node("answer", node_answer)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", route_after_grade, {
        "use_chunks": "use_chunks",
        "rewrite": "rewrite",
        "web_fallback": "web_fallback",
    })
    g.add_edge("rewrite", "retrieve")
    g.add_edge("use_chunks", "answer")
    g.add_edge("web_fallback", "answer")
    g.add_edge("answer", END)

    return g.compile()


# =====================================================================
# Demo queries — one per branch
# =====================================================================

QUERIES = [
    {
        "query": "How does prompt caching reduce cost?",
        "expected_branch": "CORRECT",
        "rationale": "On-corpus, clearly phrased — grader should accept the chunks directly.",
    },
    {
        "query": "Tell me about the memory thing",
        "expected_branch": "AMBIGUOUS → rewrite",
        "rationale": "On-corpus (we cover MemorySaver) but the phrasing is too vague — grader marks ambiguous, rewrite makes it retrievable.",
    },
    {
        "query": "Who wrote War and Peace?",
        "expected_branch": "INCORRECT → web fallback",
        "rationale": "Completely off-corpus — grader marks incorrect, pipeline falls back to web knowledge.",
    },
]


def run_query(graph, query: str) -> None:
    print("\n" + "=" * 70)
    print(f"QUERY: {query!r}")
    print("=" * 70)
    initial: CRAGState = {
        "query": query,
        "original_query": query,
        "chunks": [],
        "grades": [],
        "verdict": "",
        "rewritten": False,
        "context": "",
        "answer": "",
    }
    final = graph.invoke(initial)
    print(f"\n  FINAL ANSWER:\n    {final['answer']}")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CORRECTIVE RAG — retrieve, grade, then decide")
    print("=" * 70)
    print(f"  Corpus: {len(chunks)} chunks from NOTES.md + LEARNINGS.md")
    print(f"  Grader/Rewriter/Answerer: {MODEL}")

    graph = build_crag_graph()
    print(f"  Compiled LangGraph: {len(graph.get_graph().nodes)} nodes")

    for q_info in QUERIES:
        print(f"\n>>> branch this query should hit: {q_info['expected_branch']}")
        print(f">>> rationale: {q_info['rationale']}")
        run_query(graph, q_info["query"])

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  • Each query went through retrieve → grade → {use|rewrite|web}.\n"
        "  • The grader is a structured-output LLM call — Literal[correct,\n"
        "    ambiguous, incorrect] forces the model to commit to one verdict.\n"
        "  • Rewriting is gated by `rewritten=True` to prevent infinite loops:\n"
        "    we only rewrite once. In production add a max-retry counter.\n"
        "  • The web fallback is stubbed for repeatable demos. Swap in\n"
        "    DuckDuckGo / Tavily / your own search index for the real thing.\n"
        "  • Cost: 3-5x classical RAG (one LLM call per chunk to grade, plus\n"
        "    sometimes a rewrite + re-retrieve). Use CRAG when retrieval\n"
        "    quality genuinely matters — RAG-of-record, compliance answers,\n"
        "    customer-facing chatbots.\n"
        "  • CRAG composes naturally with Hybrid RAG (Session 11) and GraphRAG\n"
        "    (Session 12): grade the union of retrievers' top-k. Self-correction\n"
        "    is orthogonal to the retrieval substrate."
    )
