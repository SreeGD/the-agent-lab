"""AI Gateway with LiteLLM — one control plane, many models (OpenAI variant).

LiteLLM is the most-used open-source AI gateway: a single Python API that
maps to 100+ providers (OpenAI, Anthropic, Gemini, Bedrock, Mistral, ...).
Same call shape; the model string picks the backend.

This demo runs three patterns against your existing OPENAI_API_KEY:
  1. Provider abstraction       — same code, swappable model name
  2. Model bake-off              — Mini vs Sonnet (gpt-4o) vs o1 on the same prompt
  3. Fallback chain              — first model fails → fall through to backup

For real cross-provider routing (OpenAI + Anthropic + Gemini in one call),
add ANTHROPIC_API_KEY / GEMINI_API_KEY to .env — the same code paths work.
"""

import os
import time

from dotenv import load_dotenv

# Silence litellm's chatty default logging
import logging
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

# litellm exposes the unified completion() API
import litellm

load_dotenv()

PROMPT = (
    "Write a one-paragraph explanation of prompt caching for a senior "
    "backend engineer. Be specific and concise — no filler. Three sentences."
)

# LiteLLM model strings for OpenAI — note the provider prefix is part of the name
MINI = "openai/gpt-4o-mini"
SONNET = "openai/gpt-4o"
OPUS = "openai/o1"

FALLBACK_CHAIN = ["openai/gpt-4o", "openai/gpt-4o-mini"]


# =====================================================================
# DEMO 1 — provider abstraction
# Same litellm.completion() call, switchable model string.
# In production: change the model arg to anthropic/claude-sonnet-4-6 or
# gemini/gemini-1.5-pro; the rest stays the same.
# =====================================================================

def demo_provider_abstraction():
    print("=" * 70)
    print("DEMO 1 — Provider abstraction (same API for any LLM provider)")
    print("=" * 70)

    t0 = time.perf_counter()
    response = litellm.completion(
        model=SONNET,
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=300,
    )
    elapsed = time.perf_counter() - t0

    text = response.choices[0].message.content
    in_tok = response.usage.prompt_tokens
    out_tok = response.usage.completion_tokens
    cost = litellm.completion_cost(completion_response=response)

    print(f"\n  model:  {SONNET}")
    print(f"  in/out: {in_tok}/{out_tok}  latency: {elapsed:.2f}s")
    print(f"  cost:   ${cost:.6f}")
    print(f"\n  output: {text[:200]}...\n")
    print("  → To swap to Anthropic: model='anthropic/claude-sonnet-4-6' (one-line change).")
    print("    To Gemini: model='gemini/gemini-1.5-pro'. No other code changes.")


# =====================================================================
# DEMO 2 — model bake-off (cost-vs-quality trade-off, made concrete)
# Run the same prompt across three OpenAI tiers; compare metrics.
# =====================================================================

def demo_bake_off():
    print("\n" + "=" * 70)
    print("DEMO 2 — Model bake-off: same prompt, three OpenAI tiers")
    print("=" * 70)

    rows = []
    for model in [MINI, SONNET, OPUS]:
        t0 = time.perf_counter()
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": PROMPT}],
                max_tokens=300,
            )
            elapsed = time.perf_counter() - t0
            text = response.choices[0].message.content
            in_tok = response.usage.prompt_tokens
            out_tok = response.usage.completion_tokens
            cost = litellm.completion_cost(completion_response=response)
            rows.append({
                "model": model.split("/")[-1],
                "in": in_tok, "out": out_tok,
                "latency": elapsed, "cost": cost,
                "preview": text[:80],
            })
        except Exception as e:
            print(f"  [FAILED] {model}: {type(e).__name__}: {str(e)[:120]}")

    print(f"\n  {'model':<35} {'in':>4} {'out':>4} {'lat':>6} {'cost':>10}")
    print("  " + "-" * 67)
    for r in rows:
        print(
            f"  {r['model']:<35} {r['in']:>4} {r['out']:>4} "
            f"{r['latency']:>5.2f}s ${r['cost']:>9.6f}"
        )

    if len(rows) >= 2:
        cheapest = min(rows, key=lambda r: r["cost"])
        priciest = max(rows, key=lambda r: r["cost"])
        ratio = priciest["cost"] / cheapest["cost"] if cheapest["cost"] else 0
        print(
            f"\n  Cost ratio (priciest/cheapest): {ratio:.1f}x — "
            f"the cost lever in 'model selection per role'."
        )


# =====================================================================
# DEMO 3 — fallback chain
# Try o1 first; if it errors (e.g. rate limit), fall through to gpt-4o,
# then gpt-4o-mini. Production: useful for high-availability across
# models and providers.
# =====================================================================

def demo_fallback_chain():
    print("\n" + "=" * 70)
    print("DEMO 3 — Fallback chain (try o1 → gpt-4o → gpt-4o-mini on failure)")
    print("=" * 70)

    # We'll DELIBERATELY make the primary fail by using a bogus model name,
    # then watch litellm fail over through the chain.
    BOGUS = "openai/gpt-NONEXISTENT-MODEL"

    print(f"\n  primary:   {BOGUS}  (deliberately bogus to trigger fallback)")
    for i, fb in enumerate(FALLBACK_CHAIN, 1):
        print(f"  fallback{i}: {fb}")

    t0 = time.perf_counter()
    response = litellm.completion(
        model=BOGUS,
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=200,
        fallbacks=FALLBACK_CHAIN,
    )
    elapsed = time.perf_counter() - t0

    served_by = response.model
    in_tok = response.usage.prompt_tokens
    out_tok = response.usage.completion_tokens
    cost = litellm.completion_cost(completion_response=response)

    print(f"\n  → request succeeded after {elapsed:.2f}s")
    print(f"  → actually served by: {served_by}")
    print(f"  → tokens: {in_tok}/{out_tok}  cost: ${cost:.6f}")
    print(f"  → first {len(response.choices[0].message.content[:80])} chars: "
          f"{response.choices[0].message.content[:80]}...")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY missing — add it to .env")

    demo_provider_abstraction()
    demo_bake_off()
    demo_fallback_chain()

    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS")
    print("=" * 70)
    print(
        "  • One Python API (litellm.completion) → any provider.\n"
        "  • Model selection per role becomes a one-line change.\n"
        "  • Fallback chains give you cross-model resilience without\n"
        "    your app code touching the failover logic.\n"
        "  • Cost tracking is automatic (litellm.completion_cost).\n"
        "  • For centralized ops at scale, run litellm as a self-hosted\n"
        "    proxy (`litellm --port 4000`) and point all apps at it —\n"
        "    one audit log, one credential vault, one rate-limit policy."
    )
