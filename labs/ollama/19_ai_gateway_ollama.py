"""AI Gateway with LiteLLM — one control plane, many models (Ollama variant).

# Requires: ollama serve + ollama pull llama3.2
# NOTE: Ollama variant — all tiers use llama3.2.
#       Install different models with `ollama pull <model>`.

LiteLLM is the most-used open-source AI gateway: a single Python API that
maps to 100+ providers (Anthropic, OpenAI, Gemini, Bedrock, Mistral, ...).
Same call shape; the model string picks the backend.

This demo runs three patterns against a local Ollama server:
  1. Provider abstraction       — same code, swappable model name
  2. Model bake-off              — llama3.2 vs llama3.2 vs llama3.2 (same)
  3. Fallback chain              — first model fails -> fall through to backup

For real cross-provider routing (Ollama + OpenAI + Anthropic in one call),
add OPENAI_API_KEY / ANTHROPIC_API_KEY to .env — the same code paths work.
"""

import time

from dotenv import load_dotenv

# Silence litellm's chatty default logging
import logging
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

# litellm exposes the unified completion() API
import litellm

load_dotenv()

# Set the Ollama API base for LiteLLM
litellm.api_base = "http://localhost:11434"

PROMPT = (
    "Write a one-paragraph explanation of prompt caching for a senior "
    "backend engineer. Be specific and concise — no filler. Three sentences."
)

# LiteLLM model strings — note the provider prefix is part of the name
# NOTE: Ollama has no separate small/large model tiers by default;
#       all three tiers use llama3.2. Install larger models with `ollama pull <model>`.
MINI = "ollama/llama3.2"
SONNET = "ollama/llama3.2"
OPUS = "ollama/llama3.2"
FALLBACK_CHAIN = ["ollama/llama3.2"]


# =====================================================================
# DEMO 1 — provider abstraction
# Same litellm.completion() call, switchable model string.
# In production: change the model arg to openai/gpt-4o or
# anthropic/claude-sonnet-4-6; rest stays the same.
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
        api_base="http://localhost:11434",
    )
    elapsed = time.perf_counter() - t0

    text = response.choices[0].message.content
    in_tok = response.usage.prompt_tokens
    out_tok = response.usage.completion_tokens
    # Ollama is free/local — cost is always $0.0
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    print(f"\n  model:  {SONNET}")
    print(f"  in/out: {in_tok}/{out_tok}  latency: {elapsed:.2f}s")
    print(f"  cost:   ${cost:.6f}  (Ollama is local — no per-token charge)")
    print(f"\n  output: {text[:200]}...\n")
    print("  -> To swap to GPT-4o: model='openai/gpt-4o' (one-line change).")
    print("     To Anthropic: model='anthropic/claude-sonnet-4-6'. No other code changes.")


# =====================================================================
# DEMO 2 — model bake-off (cost-vs-quality trade-off, made concrete)
# Run the same prompt across three Ollama model aliases; compare metrics.
# NOTE: All tiers map to llama3.2 in this variant. Pull additional models
#       (e.g., `ollama pull llama3.1:8b`) to see real cost/latency diffs.
# =====================================================================

def demo_bake_off():
    print("\n" + "=" * 70)
    print("DEMO 2 — Model bake-off: same prompt, three model aliases")
    print("=" * 70)
    print("  NOTE: All tiers use llama3.2 in this Ollama variant.")
    print("        Pull larger models (e.g., llama3.1:8b) to see real diffs.\n")

    rows = []
    for model in [MINI, SONNET, OPUS]:
        t0 = time.perf_counter()
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": PROMPT}],
                max_tokens=300,
                api_base="http://localhost:11434",
            )
            elapsed = time.perf_counter() - t0
            text = response.choices[0].message.content
            in_tok = response.usage.prompt_tokens
            out_tok = response.usage.completion_tokens
            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception:
                cost = 0.0
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
        if cheapest["cost"] > 0:
            ratio = priciest["cost"] / cheapest["cost"]
            print(f"\n  Cost ratio (priciest/cheapest): {ratio:.1f}x")
        else:
            print("\n  All models are free/local — cost ratio is meaningless here.")
            print("  The latency column shows real hardware differences.")


# =====================================================================
# DEMO 3 — fallback chain
# Try primary first; if it errors (e.g. model not pulled), fall through
# to backup. Production: useful for high-availability across models/providers.
# =====================================================================

def demo_fallback_chain():
    print("\n" + "=" * 70)
    print("DEMO 3 — Fallback chain (try primary -> fallback on failure)")
    print("=" * 70)

    # Deliberately make the primary fail by using a bogus model name,
    # then watch litellm fail over through the chain.
    BOGUS = "ollama/llama3-NONEXISTENT-MODEL"

    print(f"\n  primary:   {BOGUS}  (deliberately bogus to trigger fallback)")
    print(f"  fallback1: {SONNET}")

    t0 = time.perf_counter()
    try:
        response = litellm.completion(
            model=BOGUS,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=200,
            fallbacks=[SONNET],
            api_base="http://localhost:11434",
        )
        elapsed = time.perf_counter() - t0

        served_by = response.model
        in_tok = response.usage.prompt_tokens
        out_tok = response.usage.completion_tokens
        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0

        print(f"\n  -> request succeeded after {elapsed:.2f}s")
        print(f"  -> actually served by: {served_by}")
        print(f"  -> tokens: {in_tok}/{out_tok}  cost: ${cost:.6f}")
        content = response.choices[0].message.content
        print(f"  -> first {min(80, len(content))} chars: {content[:80]}...")
    except Exception as e:
        print(f"\n  -> fallback also failed: {type(e).__name__}: {str(e)[:120]}")
        print(f"  -> In production, the fallback would point to a different provider")
        print(f"     (e.g., openai/gpt-4o) so the chain spans providers.")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    demo_provider_abstraction()
    demo_bake_off()
    demo_fallback_chain()

    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS")
    print("=" * 70)
    print(
        "  * One Python API (litellm.completion) -> any provider.\n"
        "  * Model selection per role becomes a one-line change.\n"
        "  * Fallback chains give you cross-model resilience without\n"
        "    your app code touching the failover logic.\n"
        "  * Cost tracking is automatic (litellm.completion_cost).\n"
        "    For Ollama, cost is $0.0 — but latency is real hardware.\n"
        "  * For centralized ops at scale, run litellm as a self-hosted\n"
        "    proxy (`litellm --port 4000`) and point all apps at it —\n"
        "    one audit log, one credential vault, one rate-limit policy.\n"
        "  * Ollama vs cloud trade-off: no per-token cost, full data\n"
        "    privacy, but you own the hardware/scaling story."
    )
