"""Cost Optimization — four measurable levers (OpenAI variant).

With Session 14's eval as our quality floor, we can now cut cost and
*prove* quality didn't move. Each lever below is demonstrated with live
numbers from the OpenAI API.

  Lever 1 — Model selection per role     (gpt-4o for answer; gpt-4o-mini for grading)
  Lever 2 — Prompt caching               (automatic for prompts >1024 tokens)
  Lever 3 — Prompt compression           (verbose → compact, same answers)
  Lever 4 — Batch API                    (50% off for async workloads, 24h SLA)

This file uses the raw OpenAI SDK (not LangChain) so we can read the
real cached_tokens field on the response usage — that's where the proof lives.
"""

import json
import os
from pathlib import Path

import openai
from dotenv import load_dotenv

load_dotenv()

HERE = Path(__file__).parent.parent  # labs/ directory
client = openai.OpenAI()

# OpenAI pricing reference (gpt-4o), May 2026
PRICES = {
    "gpt-4o":       {"in": 2.50, "out": 10.00},
    "gpt-4o-mini":  {"in": 0.15, "out": 0.60},
}


def call_cost(model: str, usage) -> float:
    p = PRICES[model]
    return (usage.prompt_tokens * p["in"] + usage.completion_tokens * p["out"]) / 1_000_000


# =====================================================================
# Lever 1 — Model selection per role
#
# CRAG (Session 13) grades each retrieved chunk with an LLM judge — a
# small classification task. gpt-4o works fine. gpt-4o-mini works just
# as well and costs much less. The question: do the verdicts agree?
# =====================================================================

GRADER_SYSTEM = (
    "You are a strict retrieval grader. Decide if the chunk is "
    "correct/ambiguous/incorrect for answering the query. "
    "Reply with a single word: correct, ambiguous, or incorrect."
)

GRADE_TASKS = [
    {
        "query": "How does prompt caching reduce cost?",
        "chunk": "Prompt caching saves the KV cache tensor from prefill. "
                 "We saw a 76% cost reduction in practice — from $0.015519 to $0.003725 per call.",
    },
    {
        "query": "How does prompt caching reduce cost?",
        "chunk": "Recipe for pasta carbonara: cook spaghetti, fry pancetta, "
                 "mix with eggs and pecorino, season with black pepper.",
    },
    {
        "query": "What checkpointer gives a LangGraph agent memory across calls?",
        "chunk": "MemorySaver() is the LangGraph checkpointer that persists state "
                 "across .invoke() calls, giving agents conversation memory.",
    },
    {
        "query": "What checkpointer gives a LangGraph agent memory across calls?",
        "chunk": "The | operator in LCEL pipes runnables: prompt | model | parser.",
    },
]


def grade(model: str, query: str, chunk: str):
    resp = client.chat.completions.create(
        model=model,
        max_completion_tokens=10,
        messages=[
            {"role": "system", "content": GRADER_SYSTEM},
            {"role": "user", "content": f"QUERY: {query}\n\nCHUNK:\n{chunk}"},
        ],
    )
    return resp.choices[0].message.content.strip().lower(), call_cost(model, resp.usage)


def demo_lever_1():
    print("\n" + "=" * 70)
    print("LEVER 1 — Model selection per role")
    print("=" * 70)
    print(f"  Task: classify chunk relevance (correct/ambiguous/incorrect).")
    print(f"  Comparing gpt-4o vs gpt-4o-mini.\n")

    big_total = 0.0
    mini_total = 0.0
    agreements = 0
    for t in GRADE_TASKS:
        b_v, b_c = grade("gpt-4o", t["query"], t["chunk"])
        m_v, m_c = grade("gpt-4o-mini", t["query"], t["chunk"])
        big_total += b_c
        mini_total += m_c
        agree = b_v.split()[0].strip(".,") == m_v.split()[0].strip(".,")
        agreements += int(agree)
        print(f"  query: {t['query'][:60]}")
        print(f"    gpt-4o      → {b_v[:15]:<15} ${b_c:.6f}")
        print(f"    gpt-4o-mini → {m_v[:15]:<15} ${m_c:.6f}    agree={'yes' if agree else 'no'}")

    print(f"\n  gpt-4o total cost:      ${big_total:.6f}")
    print(f"  gpt-4o-mini total cost: ${mini_total:.6f}")
    print(f"  Savings:                {(1 - mini_total/big_total)*100:.1f}%")
    print(f"  Verdict agreement: {agreements}/{len(GRADE_TASKS)}")
    print(f"\n  Projected at 1M grading calls/month:")
    per_call_big = big_total / len(GRADE_TASKS)
    per_call_mini = mini_total / len(GRADE_TASKS)
    print(f"    gpt-4o:      ${per_call_big * 1_000_000:,.2f}/month")
    print(f"    gpt-4o-mini: ${per_call_mini * 1_000_000:,.2f}/month")
    print(f"    Saved:       ${(per_call_big - per_call_mini) * 1_000_000:,.2f}/month")


# =====================================================================
# Lever 2 — Prompt caching
#
# gpt-4o supports automatic prompt caching for prompts >1024 tokens.
# No cache_control needed — OpenAI caches automatically.
# Check `usage.prompt_tokens_details.cached_tokens` to see cache hits.
# =====================================================================

STABLE_PREAMBLE = """You are an expert technical assistant for the AgenticCourse curriculum.
You help users understand topics in LangChain, LangGraph, MCP, Anthropic SDK, and RAG architectures.

When answering, follow these rules:
- Be concise but technically precise
- Cite specific session numbers when relevant
- Distinguish concepts from implementations
- Acknowledge limitations honestly
- Never fabricate API names or model identifiers
- Prefer 'why does this exist' over 'how do I call it'

Available topics include but are not limited to:
- LCEL composition (Session 02)
- Prompt caching mechanics and the KV cache (Session 04)
- Structured output via Pydantic (Session 05)
- Output parsers and JSON schemas (Session 07)
- Memory in LangGraph via MemorySaver (Session 08)
- Classical RAG with InMemoryVectorStore (Session 09)
- Hybrid RAG with BM25 + Reciprocal Rank Fusion (Session 11)
- GraphRAG with NetworkX and entity extraction (Session 12)
- Corrective RAG with retrieval grading (Session 13)
- Evaluation via LLM-as-judge over a golden dataset (Session 14)

Reference material to ground your answers:
"""
STABLE_PREAMBLE += "\n".join(
    f"- Fact #{i:03d}: AgenticCourse is an open-source curriculum maintained by "
    f"Sree Mallipeddi covering session {i % 14 + 1} concepts in depth."
    for i in range(60)
)

QUERY = "What is LCEL?"
LONG_SYSTEM = STABLE_PREAMBLE


def demo_lever_2():
    print("\n" + "=" * 70)
    print("LEVER 2 — Prompt caching")
    print("=" * 70)
    # =====================================================================
    # Lever 2 — Prompt caching
    #
    # gpt-4o supports automatic prompt caching for prompts >1024 tokens.
    # No cache_control needed — OpenAI caches automatically.
    # Check `usage.prompt_tokens_details.cached_tokens` to see cache hits.
    # =====================================================================
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": QUERY}],
    )
    cached = getattr(getattr(response.usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
    print(f"  Stable preamble size: ~{len(STABLE_PREAMBLE.split())} words")
    print(f"  prompt_tokens: {response.usage.prompt_tokens}  cached_tokens: {cached}")
    print(f"  Cache hits: {cached} tokens  (gpt-4o caches automatically after first use)")
    print(f"\n  → Run the script TWICE in a row to see steady-state caching savings.")
    print(f"  → gpt-4o caches prompts >1024 tokens automatically — no setup needed.")
    print(f"  → Unlike Anthropic, there is no explicit cache_control marker to add.")
    print(f"  → Cached tokens are billed at a 50% discount on gpt-4o.")


# =====================================================================
# Lever 3 — Prompt compression
#
# Most system prompts are bloated with redundant instructions. Measure
# tokens via a simple heuristic, then re-run on the same task to verify
# the compact version produces equivalent answers.
# =====================================================================

VERBOSE_PROMPT = """You are a helpful and knowledgeable assistant who provides accurate answers based on the context that is provided to you.

IMPORTANT INSTRUCTIONS — PLEASE READ CAREFULLY:
- You should ONLY use the provided context to answer questions
- Do not use your background knowledge or training data
- If the context does not contain the answer, you should say so explicitly
- Be concise in your responses, ideally 2-3 sentences
- Use clear and simple language
- Avoid being overly verbose or repeating yourself
- Stick to the facts presented in the context
- Do not speculate beyond what the context supports
- Be honest if you cannot answer based on the given context
- Make sure your response directly addresses the question that was asked

When formatting your response:
- Use plain text, no markdown formatting
- Start directly with the answer
- Do not preface with phrases like "Based on the context..." or "According to the provided information..."
- Do not end with summaries like "In summary..." or "To conclude..."
- Avoid filler phrases

Quality expectations:
- Accuracy is paramount
- Concision is valued
- Honesty when uncertain is required
"""

COMPACT_PROMPT = (
    "Answer using ONLY the provided context. If the context lacks the answer, "
    "say so. 2-3 sentences, plain text, no preamble or summary."
)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def demo_lever_3():
    print("\n" + "=" * 70)
    print("LEVER 3 — Prompt compression")
    print("=" * 70)
    user_msg = (
        "CONTEXT: MemorySaver is a LangGraph checkpointer that persists "
        "state across .invoke() calls.\n\nQUESTION: What is MemorySaver?"
    )
    v_tokens = estimate_tokens(VERBOSE_PROMPT + user_msg)
    c_tokens = estimate_tokens(COMPACT_PROMPT + user_msg)
    print(f"  verbose system prompt:  ~{v_tokens} tokens (estimated)")
    print(f"  compact system prompt:  ~{c_tokens} tokens (estimated)")
    print(f"  reduction:              {(1 - c_tokens/v_tokens)*100:.1f}% fewer input tokens")

    print(f"\n  Comparing answers on the same task:")
    for label, sys_prompt in [("verbose", VERBOSE_PROMPT), ("compact", COMPACT_PROMPT)]:
        r = client.chat.completions.create(
            model="gpt-4o",
            max_completion_tokens=100,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        print(f"  [{label}] {r.choices[0].message.content.strip()}")

    print(f"\n  Both answers should be semantically equivalent.")
    print(f"  → Compact version wins on cost; quality unchanged. Run the eval (Session 14)")
    print(f"    to verify on YOUR golden set before deploying.")


# =====================================================================
# Lever 4 — Batch API
#
# OpenAI Batch API: 50% discount, 24-hour SLA.
# Same semantics as Anthropic Message Batches.
# =====================================================================

QUERIES = [
    "What is LangChain LCEL? One sentence.",
    "What is LangGraph? One sentence.",
]


def demo_lever_4():
    print("\n" + "=" * 70)
    print("LEVER 4 — Batch API (50% off, 24h SLA)")
    print("=" * 70)
    # =====================================================================
    # Lever 4 — Batch API
    #
    # OpenAI Batch API: 50% discount, 24-hour SLA.
    # Same semantics as Anthropic Message Batches.
    # =====================================================================
    batch_input = [
        {"custom_id": f"req-{i}", "method": "POST", "url": "/v1/chat/completions",
         "body": {"model": "gpt-4o", "messages": [{"role": "user", "content": q}]}}
        for i, q in enumerate(QUERIES)
    ]
    print(f"  Submitting batch of {len(batch_input)} requests...")
    try:
        input_file = client.files.create(
            file=("\n".join(json.dumps(r) for r in batch_input)).encode(),
            purpose="batch",
        )
        batch = client.batches.create(
            input_file_id=input_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )
        print(f"  batch_id:  {batch.id}")
        print(f"  status:    {batch.status}")
        print(f"  created:   {batch.created_at}")
        print(f"Batch {batch.id} created — status: {batch.status}")
        print("(50% discount applied; results available within 24 hours)")
    except Exception as e:
        print(f"  ! Batch API call failed: {e}")
        print(f"  → Demonstrating the shape below as static reference.")
        print(f"\n  OpenAI Batch API shape:")
        print(f"    1. Build JSONL requests (one per line, custom_id + method + url + body)")
        print(f"    2. client.files.create(file=jsonl_bytes, purpose='batch')")
        print(f"    3. client.batches.create(input_file_id=..., endpoint='/v1/chat/completions')")
        print(f"    4. Poll: client.batches.retrieve(batch_id)")
        print(f"    5. Results: client.files.content(output_file_id)")

    print(f"\n  Next steps in production:")
    print(f"    1. Poll status:  client.batches.retrieve('<batch_id>')")
    print(f"    2. When done:    client.files.content(batch.output_file_id)")
    print(f"    3. Each result has a custom_id mapping back to your request.")
    print(f"\n  Pricing: 50% off the per-token cost of the same model.")
    print(f"  Typical use: nightly eval runs, document labeling, offline summarization.")
    print(f"  NOT for: real-time chat, interactive UIs (24h SLA is the trade-off).")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("COST OPTIMIZATION — four measurable levers (OpenAI)")
    print("=" * 70)

    demo_lever_1()
    demo_lever_2()
    demo_lever_3()
    demo_lever_4()

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  • LEVER 1 (model selection): graders, classifiers, structured\n"
        "    extractors don't need gpt-4o. gpt-4o-mini gets the same verdicts\n"
        "    at a fraction of the cost. The trade is: check verdict agreement on your\n"
        "    eval set before swapping. Free money if they agree.\n\n"
        "  • LEVER 2 (caching): gpt-4o caches prompts >1024 tokens automatically.\n"
        "    No setup required — no cache_control markers to add. Cached tokens\n"
        "    are billed at 50% discount. Check prompt_tokens_details.cached_tokens\n"
        "    to confirm cache hits in production.\n\n"
        "  • LEVER 3 (compression): verbose system prompts cost real money.\n"
        "    Most prompts can lose 50-70% of their tokens with no quality\n"
        "    drop. Always verify with eval (Session 14) before deploying.\n\n"
        "  • LEVER 4 (batches): for async workloads — eval runs, nightly\n"
        "    classification, bulk labeling — Batch API is a flat 50% off.\n"
        "    Production move: route everything offline through batches by\n"
        "    default, only call the sync API for user-facing requests.\n\n"
        "  • The four levers COMPOUND. Use gpt-4o-mini in a batch with a\n"
        "    compressed prompt → model savings × batch × compression\n"
        "    × auto-cache = dramatically cheaper than the naive version.\n"
        "    At scale, this is the difference between a sustainable product\n"
        "    and one you have to shut off."
    )
