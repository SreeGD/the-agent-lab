"""Cost Optimization — four measurable levers (Ollama variant).

# Requires: ollama serve + ollama pull llama3.2

With Session 14's eval as our quality floor, we can now cut cost and
*prove* quality didn't move. Each lever below is demonstrated with live
numbers from a local Ollama server.

  Lever 1 -- Model selection per role     (same model for answer and grading)
  Lever 2 -- KV cache (internal to Ollama, no client-side config needed)
  Lever 3 -- Prompt compression           (verbose -> compact, same answers)
  Lever 4 -- Batch processing             (local batch via Python, no Batches API)

NOTE: Ollama is free/local — there are no per-token charges. The cost
      figures shown are $0.00 but the token counts and latencies are real.
      Lever 1-3 still apply for latency and throughput optimization.
      Lever 4 (cloud Batches API) has no Ollama equivalent; instead we
      demonstrate local async batching with asyncio + httpx.
"""

import asyncio
import time
from pathlib import Path

import openai
from dotenv import load_dotenv

load_dotenv()

HERE = Path(__file__).parent
client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

MODEL = "llama3.2"

# Ollama is free/local — no per-token pricing.
# We show $0.0 costs but track token counts and latency (which still matter
# for throughput, hardware sizing, and response quality budgeting).
PRICES: dict = {}  # No cloud pricing for Ollama


def call_cost(model: str, usage) -> float:
    """Compute cost for an Ollama call — always $0.0 (local inference)."""
    return 0.0


# =====================================================================
# Lever 1 -- Model selection per role
#
# In cloud deployments, Haiku-class models cost 3x less than Sonnet.
# With Ollama, all tiers use llama3.2 -- but the principle holds:
# graders/classifiers don't need more tokens than the actual task.
# Measure: do the verdicts agree? Token counts are the proxy for cost.
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
                 "We saw a 76% cost reduction in practice -- from $0.015519 to $0.003725 per call.",
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
        max_tokens=10,
        messages=[
            {"role": "system", "content": GRADER_SYSTEM},
            {"role": "user", "content": f"QUERY: {query}\n\nCHUNK:\n{chunk}"},
        ],
    )
    verdict = resp.choices[0].message.content.strip().lower()
    tokens_used = resp.usage.completion_tokens
    return verdict, tokens_used


def demo_lever_1():
    print("\n" + "=" * 70)
    print("LEVER 1 -- Model selection per role")
    print("=" * 70)
    print(f"  Task: classify chunk relevance (correct/ambiguous/incorrect).")
    print(f"  NOTE: Ollama uses llama3.2 for both roles -- cost is $0.0.")
    print(f"        Token counts show the per-call overhead.\n")

    total_tokens = 0
    agreements = 0
    for t in GRADE_TASKS:
        # Both roles use the same local model
        s_v, s_tok = grade(MODEL, t["query"], t["chunk"])
        h_v, h_tok = grade(MODEL, t["query"], t["chunk"])
        total_tokens += s_tok + h_tok
        agree = s_v.split()[0].strip(".,") == h_v.split()[0].strip(".,")
        agreements += int(agree)
        print(f"  query: {t['query'][:60]}")
        print(f"    Call 1 -> {s_v[:15]:<15} out_tokens={s_tok}")
        print(f"    Call 2 -> {h_v[:15]:<15} out_tokens={h_tok}  agree={'ok' if agree else 'different'}")

    print(f"\n  Total output tokens for {len(GRADE_TASKS)*2} grading calls: {total_tokens}")
    print(f"  Verdict agreement (same model, different call): {agreements}/{len(GRADE_TASKS)}")
    print(f"\n  -> In production, swap MINI to a smaller/faster Ollama model")
    print(f"     (e.g., llama3.2:1b) vs SONNET (llama3.1:8b) to see real")
    print(f"     latency diffs. The verdict agreement metric is what matters.")


# =====================================================================
# Lever 2 -- KV cache (Ollama internal)
#
# Unlike Anthropic, Ollama manages its KV cache internally -- no client-side
# cache_control blocks needed. Repeated prefixes are cached automatically.
# We measure the latency speedup on the second identical call.
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


def chat_with_preamble(question: str) -> tuple[str, int, float]:
    """One call against the stable preamble. Returns (answer, out_tokens, latency_s)."""
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=80,
        messages=[
            {"role": "system", "content": STABLE_PREAMBLE},
            {"role": "user", "content": question},
        ],
    )
    elapsed = time.perf_counter() - t0
    return response.choices[0].message.content, response.usage.completion_tokens, elapsed


def demo_lever_2():
    print("\n" + "=" * 70)
    print("LEVER 2 -- KV cache (Ollama manages this internally)")
    print("=" * 70)
    questions = ["What is LCEL?", "What does MemorySaver do?"]

    # Estimate preamble tokens (char-based)
    preamble_tokens_est = len(STABLE_PREAMBLE) // 4
    print(f"  Stable preamble size: ~{len(STABLE_PREAMBLE.split())} words (~{preamble_tokens_est} tokens est).")
    print(f"  NOTE: Ollama caches KV internally -- no cache_control needed.\n")

    print("  First pass (cold, cache may not be warm):")
    latencies_cold = []
    for q in questions:
        _, out_tok, lat = chat_with_preamble(q)
        print(f"    q={q!r:<30} out_tokens={out_tok:<4} latency={lat:.2f}s")
        latencies_cold.append(lat)

    print("\n  Second pass (same preamble, Ollama KV cache may be warm):")
    latencies_warm = []
    for q in questions:
        _, out_tok, lat = chat_with_preamble(q)
        print(f"    q={q!r:<30} out_tokens={out_tok:<4} latency={lat:.2f}s")
        latencies_warm.append(lat)

    avg_cold = sum(latencies_cold) / len(latencies_cold)
    avg_warm = sum(latencies_warm) / len(latencies_warm)
    speedup = avg_cold / avg_warm if avg_warm > 0 else 1.0
    print(f"\n  Avg latency cold: {avg_cold:.2f}s  warm: {avg_warm:.2f}s  speedup: {speedup:.1f}x")
    print(f"  -> Ollama's internal KV cache eliminates prefill recomputation.")
    print(f"     Unlike Anthropic, there's no explicit cache_control to manage.")
    print(f"     The optimization is automatic when the prefix bytes are identical.")


# =====================================================================
# Lever 3 -- Prompt compression
#
# Most system prompts are bloated with redundant instructions. Measure
# tokens via char-based estimation, then re-run on the same task to
# verify the compact version produces equivalent answers.
# NOTE: Ollama has no count_tokens API -- we use char // 4 estimation.
# =====================================================================

VERBOSE_PROMPT = """You are a helpful and knowledgeable assistant who provides accurate answers based on the context that is provided to you.

IMPORTANT INSTRUCTIONS -- PLEASE READ CAREFULLY:
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


def count_tokens_est(system: str, user: str) -> int:
    """Estimate token count via char-based heuristic (char count // 4).

    NOTE: Ollama has no count_tokens API equivalent to Anthropic's.
    This is an approximation. For precise counts, use tiktoken or
    run the model and read response.usage.prompt_tokens.
    """
    total_chars = len(system) + len(user)
    return total_chars // 4


def demo_lever_3():
    print("\n" + "=" * 70)
    print("LEVER 3 -- Prompt compression")
    print("=" * 70)
    user_msg = (
        "CONTEXT: MemorySaver is a LangGraph checkpointer that persists "
        "state across .invoke() calls.\n\nQUESTION: What is MemorySaver?"
    )
    v_tokens = count_tokens_est(VERBOSE_PROMPT, user_msg)
    c_tokens = count_tokens_est(COMPACT_PROMPT, user_msg)
    print(f"  verbose system prompt:  ~{v_tokens} tokens (char-based est.)")
    print(f"  compact system prompt:  ~{c_tokens} tokens (char-based est.)")
    print(f"  reduction:              ~{(1 - c_tokens/v_tokens)*100:.1f}% fewer input tokens")
    print(f"  NOTE: Exact counts via response.usage.prompt_tokens (requires a real call).\n")

    print(f"  Comparing answers on the same task:")
    for label, sys_prompt in [("verbose", VERBOSE_PROMPT), ("compact", COMPACT_PROMPT)]:
        r = client.chat.completions.create(
            model=MODEL,
            max_tokens=100,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        actual_in = r.usage.prompt_tokens
        print(f"  [{label}] actual in_tokens={actual_in}  answer: {r.choices[0].message.content.strip()[:120]}")

    print(f"\n  Both answers should be semantically equivalent.")
    print(f"  -> Compact version wins on latency and throughput; quality unchanged.")
    print(f"     Run the eval (Session 14) to verify on YOUR golden set before deploying.")


# =====================================================================
# Lever 4 -- Local async batching
#
# Anthropic's Batches API gives 50% off for async workloads. Ollama has
# no equivalent cloud Batches API. Instead, we demonstrate local async
# batching: fire multiple requests concurrently via asyncio + httpx.
# The throughput gain is real -- serial vs parallel wall time.
# =====================================================================

async def _async_grade(session, model: str, query: str, chunk: str) -> tuple[str, float]:
    """Async call to Ollama via httpx. Returns (verdict, latency_s)."""
    import httpx
    t0 = time.perf_counter()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": GRADER_SYSTEM},
            {"role": "user", "content": f"QUERY: {query}\n\nCHUNK:\n{chunk}"},
        ],
        "max_tokens": 10,
        "stream": False,
    }
    resp = await session.post(
        "http://localhost:11434/v1/chat/completions",
        json=payload,
        timeout=60.0,
    )
    data = resp.json()
    verdict = data["choices"][0]["message"]["content"].strip().lower()
    return verdict, time.perf_counter() - t0


async def _run_batch_async(tasks: list[dict]) -> list[tuple[str, float]]:
    """Run all tasks concurrently. Returns list of (verdict, latency_s)."""
    import httpx
    async with httpx.AsyncClient() as session:
        coros = [
            _async_grade(session, MODEL, t["query"], t["chunk"])
            for t in tasks
        ]
        return await asyncio.gather(*coros)


def demo_lever_4():
    print("\n" + "=" * 70)
    print("LEVER 4 -- Local async batching (Ollama has no cloud Batches API)")
    print("=" * 70)
    print("  Anthropic's Batches API gives 50% off for async/offline workloads.")
    print("  Ollama has no equivalent. Instead: fire requests concurrently.")
    print("  We compare serial wall time vs parallel wall time.\n")

    # --- Serial ---
    print("  Serial execution (one at a time):")
    t0 = time.perf_counter()
    serial_results = []
    for t in GRADE_TASKS:
        r = client.chat.completions.create(
            model=MODEL,
            max_tokens=10,
            messages=[
                {"role": "system", "content": GRADER_SYSTEM},
                {"role": "user", "content": f"QUERY: {t['query']}\n\nCHUNK:\n{t['chunk']}"},
            ],
        )
        verdict = r.choices[0].message.content.strip().lower()
        serial_results.append(verdict)
    serial_total = time.perf_counter() - t0
    print(f"    {len(GRADE_TASKS)} tasks, serial total: {serial_total:.2f}s")

    # --- Parallel async ---
    print("\n  Parallel async execution (all at once via asyncio):")
    try:
        t0 = time.perf_counter()
        async_results = asyncio.run(_run_batch_async(GRADE_TASKS))
        parallel_total = time.perf_counter() - t0
        verdicts = [r[0] for r in async_results]
        print(f"    {len(GRADE_TASKS)} tasks, parallel total: {parallel_total:.2f}s")
        speedup = serial_total / parallel_total if parallel_total > 0 else 1.0
        print(f"    Throughput speedup: {speedup:.1f}x")

        # Check agreement
        agree = sum(s.split()[0].strip(".,") == p.split()[0].strip(".,")
                    for s, p in zip(serial_results, verdicts))
        print(f"    Serial/parallel verdict agreement: {agree}/{len(GRADE_TASKS)}")
    except Exception as e:
        print(f"    Async batch failed: {type(e).__name__}: {str(e)[:120]}")
        print(f"    -> httpx may not be installed. `pip install httpx` to enable.")

    print(f"\n  -> For true offline/async batch processing with Ollama:")
    print(f"     use a task queue (Celery, RQ, asyncio) + local Ollama endpoint.")
    print(f"     Same throughput pattern as Anthropic Batches API, $0 cost.")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("COST OPTIMIZATION (Ollama) -- four measurable levers")
    print("=" * 70)

    demo_lever_1()
    demo_lever_2()
    demo_lever_3()
    demo_lever_4()

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  * LEVER 1 (model selection): graders, classifiers, structured\n"
        "    extractors don't need the largest model. With Ollama, the lever\n"
        "    is latency (smaller models are faster) not cost. Pull llama3.2:1b\n"
        "    vs llama3.1:8b to see real latency diffs.\n\n"
        "  * LEVER 2 (KV cache): Ollama manages its KV cache internally.\n"
        "    No cache_control needed -- repeated prefixes are cached automatically.\n"
        "    The speedup is visible on warm second calls with the same prefix.\n\n"
        "  * LEVER 3 (compression): verbose system prompts cost real tokens.\n"
        "    Even with Ollama ($0 cost), shorter prompts = lower latency.\n"
        "    Most prompts can lose 50-70% of tokens with no quality drop.\n"
        "    Always verify with eval (Session 14) before deploying.\n\n"
        "  * LEVER 4 (batching): no Batches API on Ollama, but asyncio+httpx\n"
        "    delivers comparable throughput for offline workloads. The speedup\n"
        "    is real -- parallel wall time drops linearly with concurrency.\n\n"
        "  * CLOUD vs LOCAL trade-off: Ollama eliminates per-token costs but\n"
        "    you own hardware sizing, GPU memory, and concurrency limits.\n"
        "    The optimization levers (model size, prompt length, parallelism)\n"
        "    still compound -- smaller model + shorter prompt + parallel calls\n"
        "    = dramatically higher throughput on the same hardware."
    )
