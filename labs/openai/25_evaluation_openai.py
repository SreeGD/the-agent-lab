"""Evaluation — LLM-as-judge for RAG.

Without evaluation, every RAG change is a vibe check. This lab builds a
golden dataset + 4 standard RAG metrics (faithfulness, answer relevance,
context precision, context recall), then scores three RAG variants from
prior sessions:

  1. Dense baseline  (Session 9  — vector search only)
  2. Hybrid          (Session 11 — dense + BM25 + RRF fusion)
  3. CRAG-filter     (Session 13 — retrieve, grade, keep correct chunks)

The variant with the best metric average wins. Then we run a regression
check (dense baseline with k=1) to verify the harness actually catches
quality drops.

All metrics are implemented from scratch as LLM-as-judge calls with
structured output. Ragas wraps the same idea — once you understand what
each metric *is*, swapping to Ragas is a 10-line change.
"""

import json
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

load_dotenv()

HERE = Path(__file__).parent

MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)


# =====================================================================
# Load corpus, build indexes (dense + sparse), load golden dataset
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

print("Building BM25 sparse index...")
_tokenized = [d.page_content.lower().split() for d in chunks]
bm25 = BM25Okapi(_tokenized)

print("Loading golden dataset...")
with open(HERE / "eval_dataset.json") as f:
    GOLDEN = json.load(f)["examples"]
print(f"  {len(GOLDEN)} examples.")


# =====================================================================
# RAG variants (one function each — same signature)
# =====================================================================

def _generate_answer(question: str, retrieved: list[Document]) -> str:
    context = "\n\n---\n\n".join(d.page_content for d in retrieved)
    response = model.invoke([
        SystemMessage(
            "Answer the user's question using ONLY the provided context. "
            "If the context doesn't contain the answer, say so. Be concise — "
            "2-3 sentences."
        ),
        HumanMessage(f"CONTEXT:\n{context}\n\nQUESTION: {question}"),
    ])
    return response.content


def variant_dense(question: str, k: int = 3) -> tuple[str, list[Document]]:
    retrieved = vector_store.similarity_search(question, k=k)
    return _generate_answer(question, retrieved), retrieved


def _rrf(ranked_lists: list[list[Document]], k_rrf: int = 60, top_k: int = 3) -> list[Document]:
    fused: dict[int, float] = {}
    doc_by_id: dict[int, Document] = {}
    for ranked in ranked_lists:
        for rank, d in enumerate(ranked, start=1):
            key = id(d)
            fused[key] = fused.get(key, 0.0) + 1.0 / (k_rrf + rank)
            doc_by_id[key] = d
    top = sorted(fused, key=fused.get, reverse=True)[:top_k]
    return [doc_by_id[k] for k in top]


def variant_hybrid(question: str, k: int = 3) -> tuple[str, list[Document]]:
    dense_hits = vector_store.similarity_search(question, k=8)
    scores = bm25.get_scores(question.lower().split())
    top_idx = sorted(range(len(scores)), key=lambda i: -scores[i])[:8]
    sparse_hits = [chunks[i] for i in top_idx]
    fused = _rrf([dense_hits, sparse_hits], top_k=k)
    return _generate_answer(question, fused), fused


class _Grade(BaseModel):
    verdict: Literal["correct", "ambiguous", "incorrect"]


def variant_crag(question: str, k: int = 3) -> tuple[str, list[Document]]:
    """CRAG-filter: retrieve, grade each chunk, keep only correct ones.

    Simplified vs. Session 13 — no rewrite, no web fallback, so the eval
    is deterministic. The filtering alone is the variant under test.
    """
    retrieved = vector_store.similarity_search(question, k=k)
    grader = model.with_structured_output(_Grade)
    kept: list[Document] = []
    for c in retrieved:
        g = grader.invoke([
            SystemMessage(
                "You are a strict retrieval grader. Decide if the chunk is "
                "correct/ambiguous/incorrect for answering the query."
            ),
            HumanMessage(f"QUERY: {question}\n\nCHUNK:\n{c.page_content}"),
        ])
        if g.verdict == "correct":
            kept.append(c)
    # If nothing graded correct, fall back to all retrieved — otherwise no context.
    if not kept:
        kept = retrieved
    return _generate_answer(question, kept), kept


VARIANTS = {
    "dense": variant_dense,
    "hybrid": variant_hybrid,
    "crag":   variant_crag,
}


# =====================================================================
# The 4 metrics — LLM-as-judge, all return 0.0-1.0
# =====================================================================

class _Score(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="Score between 0.0 and 1.0.")
    reasoning: str = Field(description="One-sentence justification.")


def _score(system: str, user: str) -> _Score:
    return model.with_structured_output(_Score).invoke([
        SystemMessage(system),
        HumanMessage(user),
    ])


def faithfulness(answer: str, retrieved: list[Document]) -> _Score:
    """Is every claim in the answer supported by the retrieved context?
    Returns 1.0 = fully grounded, 0.0 = fully hallucinated."""
    context = "\n---\n".join(d.page_content for d in retrieved)
    return _score(
        system=(
            "You judge FAITHFULNESS: does every factual claim in the answer "
            "appear in the provided context? Score 1.0 if all claims are "
            "grounded, 0.0 if the answer is largely fabricated. Penalize "
            "claims that go beyond the context, even if true in general."
        ),
        user=f"CONTEXT:\n{context}\n\nANSWER:\n{answer}",
    )


def answer_relevance(question: str, answer: str) -> _Score:
    """Does the answer actually address the question?
    Returns 1.0 = direct & on-topic, 0.0 = irrelevant or evasive."""
    return _score(
        system=(
            "You judge ANSWER RELEVANCE: does the answer directly address "
            "the user's question? Score 1.0 if focused and on-topic, 0.0 if "
            "it dodges the question or rambles. Ignore whether the answer "
            "is factually correct — only judge topical fit."
        ),
        user=f"QUESTION:\n{question}\n\nANSWER:\n{answer}",
    )


def context_precision(question: str, retrieved: list[Document]) -> _Score:
    """What fraction of retrieved chunks are actually relevant to the question?
    Returns 1.0 = all chunks useful, 0.0 = all chunks off-topic noise."""
    listed = "\n\n".join(f"[CHUNK {i+1}]\n{d.page_content}" for i, d in enumerate(retrieved))
    return _score(
        system=(
            "You judge CONTEXT PRECISION: of the retrieved chunks below, "
            "what fraction are actually relevant to the question? Score 1.0 "
            "if every chunk could help answer the question, 0.0 if all are "
            "off-topic. This measures retrieval noise, not retrieval recall."
        ),
        user=f"QUESTION:\n{question}\n\nRETRIEVED CHUNKS:\n{listed}",
    )


def context_recall(retrieved: list[Document], ground_truth: str) -> _Score:
    """Is the ground-truth answer findable in the retrieved chunks?
    Returns 1.0 = fully supported, 0.0 = ground truth missing entirely."""
    context = "\n---\n".join(d.page_content for d in retrieved)
    return _score(
        system=(
            "You judge CONTEXT RECALL: given the ground-truth answer, what "
            "fraction of its key facts are supported by the retrieved "
            "chunks? Score 1.0 if every fact is findable, 0.0 if the chunks "
            "miss the answer entirely. This measures whether retrieval "
            "found the right material — not whether the LLM used it well."
        ),
        user=f"GROUND TRUTH:\n{ground_truth}\n\nRETRIEVED CHUNKS:\n{context}",
    )


METRICS = {
    "faithfulness":      faithfulness,
    "answer_relevance":  answer_relevance,
    "context_precision": context_precision,
    "context_recall":    context_recall,
}


# =====================================================================
# Eval runner
# =====================================================================

def evaluate_variant(name: str, variant_fn) -> dict:
    """Run a variant over all golden examples; return per-metric averages."""
    print(f"\n  Running variant: {name}")
    per_metric: dict[str, list[float]] = {m: [] for m in METRICS}
    per_example: list[dict] = []

    for ex in GOLDEN:
        q = ex["question"]
        gt = ex["ground_truth"]
        print(f"    [{ex['id']}] {q[:60]}...")
        answer, retrieved = variant_fn(q)

        scores = {
            "faithfulness":      faithfulness(answer, retrieved).score,
            "answer_relevance":  answer_relevance(q, answer).score,
            "context_precision": context_precision(q, retrieved).score,
            "context_recall":    context_recall(retrieved, gt).score,
        }
        for m, s in scores.items():
            per_metric[m].append(s)
        per_example.append({
            "id": ex["id"], "answer": answer, "scores": scores,
        })
        print(f"        scores: " + "  ".join(f"{m[:4]}={s:.2f}" for m, s in scores.items()))

    averages = {m: sum(v) / len(v) for m, v in per_metric.items()}
    averages["OVERALL"] = sum(averages.values()) / len(averages)
    return {"name": name, "averages": averages, "per_example": per_example}


def print_comparison_table(results: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("COMPARISON — per-metric averages across all golden examples")
    print("=" * 70)
    metrics = list(METRICS.keys()) + ["OVERALL"]
    header = f"{'metric':<22}" + "".join(f"{r['name']:>12}" for r in results) + "    winner"
    print(header)
    print("-" * len(header))
    for m in metrics:
        scores = [r["averages"][m] for r in results]
        winner_idx = scores.index(max(scores))
        winner = results[winner_idx]["name"]
        row = f"{m:<22}" + "".join(f"{s:>12.3f}" for s in scores) + f"    {winner}"
        print(row)


def regression_check(baseline: dict) -> None:
    """Re-run the dense variant with k=1 — should regress on context_recall.
    Demonstrates the harness can detect quality drops."""
    print("\n" + "=" * 70)
    print("REGRESSION CHECK — dense with k=1 (deliberately weakened retrieval)")
    print("=" * 70)
    weakened = evaluate_variant("dense_k1", lambda q: variant_dense(q, k=1))

    print("\n  delta vs. baseline 'dense' (k=3):")
    failed: list[str] = []
    for m in list(METRICS.keys()) + ["OVERALL"]:
        before = baseline["averages"][m]
        after = weakened["averages"][m]
        delta = after - before
        flag = ""
        if delta < -0.10:
            flag = "  ❌ REGRESSION (>10% drop)"
            failed.append(m)
        elif delta < -0.05:
            flag = "  ⚠️  drop"
        print(f"    {m:<22} {before:.3f}  →  {after:.3f}    Δ={delta:+.3f}{flag}")

    if failed:
        print(f"\n  ✓ Harness caught {len(failed)} regression(s): {failed}")
        print(f"  In CI this would FAIL the build — exactly what we want.")
    else:
        print(f"\n  No regressions caught (this would be a surprise for k=1).")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("EVALUATION — LLM-as-judge over a golden dataset")
    print("=" * 70)
    print(f"  Corpus:  {len(chunks)} chunks from NOTES.md + LEARNINGS.md")
    print(f"  Golden:  {len(GOLDEN)} Q/A pairs from eval_dataset.json")
    print(f"  Variants: {list(VARIANTS.keys())}")
    print(f"  Metrics:  {list(METRICS.keys())}")

    results = [evaluate_variant(name, fn) for name, fn in VARIANTS.items()]
    print_comparison_table(results)

    # Use the dense baseline as the reference for regression
    dense_baseline = next(r for r in results if r["name"] == "dense")
    regression_check(dense_baseline)

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  • 5 questions × 3 RAG variants × 4 metrics = 60 LLM-as-judge calls\n"
        "    (plus the 15 RAG generations and the CRAG grading calls). Total\n"
        "    ~120 calls, ~$0.50-0.90 with gpt-4o.\n"
        "  • Each metric is a single LLM call returning a structured score\n"
        "    in [0,1]. The Pydantic `Field(ge=0.0, le=1.0)` enforces the range\n"
        "    at the API boundary — no post-hoc clamping needed.\n"
        "  • The comparison table tells you which retrieval variant wins on\n"
        "    each metric. Hybrid often wins recall; CRAG often wins precision\n"
        "    and faithfulness. Dense is the cheap baseline.\n"
        "  • The regression check artificially weakens dense to k=1 and\n"
        "    verifies the harness notices. In real CI this guards against\n"
        "    silent quality drops from prompt edits, model swaps, etc.\n"
        "  • Production swaps: replace the judge prompts with Ragas (same\n"
        "    metrics, more battle-tested). Wire the runner into LangSmith for\n"
        "    persistent dashboards. Both are 10-20 line drop-ins once you\n"
        "    understand what each metric *is*."
    )
