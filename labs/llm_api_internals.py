"""LLM API Internals — hands-on observation lab.

This lab makes the 7-layer API journey visible and measurable.
Run each exercise independently or run all with: python llm_api_internals.py

Exercises:
  1. Token counting before sending
  2. Time-to-first-token vs. total time
  3. Streaming vs. non-streaming latency comparison
  4. Prompt caching: cache write vs. cache read cost
  5. Output length effect on latency
  6. Cost estimation function
"""

from __future__ import annotations

import time
from typing import Iterator

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

PRICE = {
    # Claude Sonnet 4.6 pricing (USD per million tokens)
    "input":          3.00,
    "output":        15.00,
    "cache_write":    3.75,
    "cache_read":     0.30,
}


def usd(tokens: int, tier: str) -> str:
    cost = tokens * PRICE[tier] / 1_000_000
    return f"${cost:.6f}"


def divider(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print('═' * 60)


# ─────────────────────────────────────────────────────────────────────────────
# Exercise 1 — Token counting before sending
# ─────────────────────────────────────────────────────────────────────────────

def exercise_1_token_counting():
    divider("Exercise 1 — Token counting before sending")

    prompts = [
        ("Short English",    "What is the capital of France?"),
        ("Long English",     "Explain the entire history of the Roman Empire from its founding to its fall, covering political, military, economic, and cultural dimensions in exhaustive detail." * 3),
        ("Code",             "def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)\n\nprint([fibonacci(i) for i in range(20)])"),
        ("Hindi text",       "भारत एक विविधताओं से भरा देश है जहाँ अनेक भाषाएँ, संस्कृतियाँ और परंपराएँ एक साथ फलती-फूलती हैं।"),
    ]

    print(f"\n{'Prompt':<20} {'Chars':>8} {'Tokens':>8} {'Chars/Token':>12} {'Cost (input)':>14}")
    print("-" * 66)

    for label, text in prompts:
        response = client.messages.count_tokens(
            model=MODEL,
            messages=[{"role": "user", "content": text}],
        )
        tokens = response.input_tokens
        chars = len(text)
        ratio = chars / tokens if tokens else 0
        print(f"{label:<20} {chars:>8,} {tokens:>8,} {ratio:>12.1f} {usd(tokens, 'input'):>14}")

    print("""
Observations:
  • English prose: ~4 chars/token
  • Code: ~2-3 chars/token (special chars, spaces tokenize inefficiently)
  • Hindi: ~1-2 chars/token (non-Latin scripts encode poorly in BPE)
  → Implication: non-English agents cost 2-4× more per character than English ones
""")


# ─────────────────────────────────────────────────────────────────────────────
# Exercise 2 — Time-to-first-token vs. total time
# ─────────────────────────────────────────────────────────────────────────────

def exercise_2_ttft():
    divider("Exercise 2 — Time-to-first-token vs. total time")

    prompt = "Write a detailed 500-word essay on the importance of clean water access globally."

    print(f"\nStreaming a ~500-word response...\n")

    t_start = time.perf_counter()
    t_first_token = None
    total_output_tokens = 0
    char_count = 0

    with client.messages.stream(
        model=MODEL,
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            if t_first_token is None:
                t_first_token = time.perf_counter()
                print(f"[t={t_first_token - t_start:.3f}s]  First token: {text!r}")
            char_count += len(text)

        usage = stream.get_final_message().usage

    t_end = time.perf_counter()
    total_output_tokens = usage.output_tokens

    ttft = t_first_token - t_start
    total = t_end - t_start
    decode_time = total - ttft
    ms_per_token = (decode_time / total_output_tokens) * 1000 if total_output_tokens else 0

    print(f"""
Results:
  Time-to-first-token (TTFT):  {ttft:.3f}s   ← prefill + network
  Total time:                  {total:.3f}s
  Decode time:                 {decode_time:.3f}s  ← {total_output_tokens} tokens × {ms_per_token:.1f}ms each
  Characters generated:        {char_count:,}
  Output tokens:               {total_output_tokens:,}

Mental model:
  TTFT = API gateway + load balancer + tokenization + prefill
  Decode = output_tokens × ~{ms_per_token:.0f}ms each (autoregressive, sequential)
  → Streaming shows you the decode is happening token-by-token
""")


# ─────────────────────────────────────────────────────────────────────────────
# Exercise 3 — Streaming vs. non-streaming latency
# ─────────────────────────────────────────────────────────────────────────────

def exercise_3_streaming_vs_sync():
    divider("Exercise 3 — Streaming vs. non-streaming latency comparison")

    prompt = "List 10 interesting facts about the Amazon rainforest. Be concise."

    # Non-streaming
    t0 = time.perf_counter()
    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    t_sync = time.perf_counter() - t0
    tokens_out = response.usage.output_tokens

    # Streaming (measure time-to-first-token)
    t0 = time.perf_counter()
    t_first = None
    with client.messages.stream(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for _ in stream.text_stream:
            if t_first is None:
                t_first = time.perf_counter() - t0
            # consume stream
        t_stream_total = time.perf_counter() - t0

    print(f"""
Results (same prompt, same model, ~{tokens_out} output tokens):

  Non-streaming:
    User perceives: {t_sync:.3f}s wait → all {tokens_out} tokens at once

  Streaming:
    User perceives: {t_first:.3f}s → first token  (TTFT)
    Total compute:  {t_stream_total:.3f}s → last token

  Perceived speedup: {t_sync / t_first:.1f}×  faster first response with streaming

Key insight:
  Same GPU compute. Same total time. Different DELIVERY.
  Streaming doesn't make the model faster — it makes waiting bearable.
  For agentic apps: always stream responses shown to users.
""")


# ─────────────────────────────────────────────────────────────────────────────
# Exercise 4 — Prompt caching: write vs. read
# ─────────────────────────────────────────────────────────────────────────────

LARGE_SYSTEM_PROMPT = """You are an expert agricultural advisor for Indian farmers.

""" + ("You have deep knowledge of soil science, crop management, irrigation, pest control, fertilizer selection, seed varieties, weather patterns, and market prices across Telangana, Andhra Pradesh, Karnataka, Maharashtra, and Tamil Nadu. " * 60) + """

Always provide practical, actionable advice grounded in local conditions.
Answer questions about crops, soil, water, fertilizers, and pest management.
"""


def exercise_4_prompt_caching():
    divider("Exercise 4 — Prompt caching: cache write vs. cache read")

    messages = [{"role": "user", "content": "What is the best fertilizer for paddy in black cotton soil?"}]
    system = [
        {
            "type": "text",
            "text": LARGE_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    print(f"System prompt size: {len(LARGE_SYSTEM_PROMPT):,} chars")
    print(f"Making 3 identical calls with prompt caching enabled...\n")

    results = []
    for i in range(3):
        t0 = time.perf_counter()
        response = client.messages.create(
            model=MODEL,
            max_tokens=100,
            system=system,
            messages=messages,
        )
        elapsed = time.perf_counter() - t0
        u = response.usage
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
        regular_in = u.input_tokens

        cost = (
            regular_in   * PRICE["input"]       / 1_000_000 +
            cache_write  * PRICE["cache_write"]  / 1_000_000 +
            cache_read   * PRICE["cache_read"]   / 1_000_000 +
            u.output_tokens * PRICE["output"]    / 1_000_000
        )
        results.append((i+1, regular_in, cache_write, cache_read, u.output_tokens, cost, elapsed))
        time.sleep(1)  # ensure cache is registered

    print(f"{'Call':>4} {'Regular in':>10} {'Cache write':>12} {'Cache read':>12} {'Out':>6} {'Cost':>10} {'Time':>7}")
    print("-" * 65)
    for call, reg, cw, cr, out, cost, t in results:
        print(f"{call:>4} {reg:>10,} {cw:>12,} {cr:>12,} {out:>6,}  ${cost:.6f} {t:>6.2f}s")

    if results[0][3] == 0 and results[1][3] > 0:
        cost_without = results[0][5] * 3
        cost_with = sum(r[5] for r in results)
        savings_pct = (1 - cost_with / cost_without) * 100
        print(f"""
Without caching (3 calls):  ${cost_without:.6f}
With caching    (3 calls):  ${cost_with:.6f}
Savings:                    {savings_pct:.0f}%

At scale: 10,000 calls/day × this system prompt = ${cost_without/3 * 10000:.2f}/day uncached
                                                  = ${cost_with/3 * 10000:.2f}/day cached
""")
    else:
        print("\nNote: cache_creation may show on call 1. cache_read on calls 2+.")
        print("Check usage.cache_read_input_tokens in results above.")


# ─────────────────────────────────────────────────────────────────────────────
# Exercise 5 — Output length effect on latency
# ─────────────────────────────────────────────────────────────────────────────

def exercise_5_output_length_latency():
    divider("Exercise 5 — Output length effect on latency")

    tests = [
        ("1 word",    50,  "Respond in exactly one word: What is 2+2?"),
        ("1 sentence", 80, "In one sentence only: What is the capital of France?"),
        ("1 paragraph", 200, "In one paragraph only: What is machine learning?"),
        ("5 paragraphs", 600, "Write exactly 5 paragraphs explaining how neural networks work."),
    ]

    print(f"\n{'Length':>12} {'Max tokens':>12} {'Actual out':>12} {'Total time':>12} {'ms/token':>10}")
    print("-" * 62)

    for label, max_tok, prompt in tests:
        t0 = time.perf_counter()
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tok,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.perf_counter() - t0
        out_tokens = response.usage.output_tokens
        ms_per = (elapsed / out_tokens * 1000) if out_tokens else 0
        print(f"{label:>12} {max_tok:>12,} {out_tokens:>12,} {elapsed:>11.2f}s {ms_per:>9.1f}")

    print("""
Observations:
  • Short outputs: TTFT dominates total time (prefill + network overhead is fixed)
  • Long outputs: decode time scales ~linearly with output tokens
  • ms/token converges to ~40-70ms (varies by GPU load)
  → Implication: for agents that need speed, constrain max_tokens aggressively
""")


# ─────────────────────────────────────────────────────────────────────────────
# Exercise 6 — Cost estimation function
# ─────────────────────────────────────────────────────────────────────────────

def exercise_6_cost_estimator():
    divider("Exercise 6 — Cost estimation function")

    def estimate_cost(
        system_prompt: str,
        user_messages: list[str],
        expected_output_tokens: int,
        calls_per_day: int,
        use_caching: bool = True,
    ) -> dict:
        # Count tokens
        system_tokens = client.messages.count_tokens(
            model=MODEL,
            system=system_prompt,
            messages=[{"role": "user", "content": "x"}],
        ).input_tokens

        avg_user_tokens = sum(
            client.messages.count_tokens(
                model=MODEL,
                messages=[{"role": "user", "content": m}],
            ).input_tokens
            for m in user_messages
        ) // len(user_messages)

        if use_caching:
            # First call: pay cache_write for system; subsequent: pay cache_read
            daily_system_cost = (
                system_tokens * PRICE["cache_write"] / 1_000_000 +           # 1 write/day
                (calls_per_day - 1) * system_tokens * PRICE["cache_read"] / 1_000_000  # rest reads
            )
        else:
            daily_system_cost = calls_per_day * system_tokens * PRICE["input"] / 1_000_000

        daily_user_cost   = calls_per_day * avg_user_tokens * PRICE["input"] / 1_000_000
        daily_output_cost = calls_per_day * expected_output_tokens * PRICE["output"] / 1_000_000
        daily_total = daily_system_cost + daily_user_cost + daily_output_cost

        return {
            "system_tokens":         system_tokens,
            "avg_user_tokens":       avg_user_tokens,
            "daily_system_cost_usd": daily_system_cost,
            "daily_user_cost_usd":   daily_user_cost,
            "daily_output_cost_usd": daily_output_cost,
            "daily_total_usd":       daily_total,
            "monthly_total_usd":     daily_total * 30,
        }

    # Example: customer support agent
    system = "You are a helpful customer support agent for AgroMart, India's leading agri-supplies marketplace. " * 30
    messages = [
        "I placed an order 3 days ago but it hasn't shipped yet. Order #AM-12345.",
        "What fertilizers do you stock for paddy cultivation?",
        "How do I return a defective sprayer pump?",
    ]

    for caching in [False, True]:
        est = estimate_cost(
            system_prompt=system,
            user_messages=messages,
            expected_output_tokens=150,
            calls_per_day=1000,
            use_caching=caching,
        )
        label = "With caching" if caching else "Without caching"
        print(f"\n{label} (1,000 calls/day):")
        print(f"  System prompt:   {est['system_tokens']:,} tokens")
        print(f"  Avg user msg:    {est['avg_user_tokens']:,} tokens")
        print(f"  Daily system:   ${est['daily_system_cost_usd']:.4f}")
        print(f"  Daily user:     ${est['daily_user_cost_usd']:.4f}")
        print(f"  Daily output:   ${est['daily_output_cost_usd']:.4f}")
        print(f"  Daily total:    ${est['daily_total_usd']:.4f}")
        print(f"  Monthly total:  ${est['monthly_total_usd']:.2f}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

EXERCISES = {
    "1": ("Token counting before sending",          exercise_1_token_counting),
    "2": ("Time-to-first-token vs. total time",     exercise_2_ttft),
    "3": ("Streaming vs. non-streaming latency",    exercise_3_streaming_vs_sync),
    "4": ("Prompt caching: write vs. read cost",    exercise_4_prompt_caching),
    "5": ("Output length effect on latency",        exercise_5_output_length_latency),
    "6": ("Cost estimation function",               exercise_6_cost_estimator),
}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        key = sys.argv[1]
        if key in EXERCISES:
            EXERCISES[key][1]()
        else:
            print(f"Unknown exercise: {key}. Choose from: {list(EXERCISES)}")
    else:
        print("LLM API Internals — Observation Lab")
        print("=====================================")
        print("Available exercises:")
        for k, (name, _) in EXERCISES.items():
            print(f"  {k}. {name}")
        print("\nRun all:      python llm_api_internals.py all")
        print("Run one:      python llm_api_internals.py 1")

        if len(sys.argv) > 1 and sys.argv[1] == "all":
            for k, (name, fn) in EXERCISES.items():
                fn()
