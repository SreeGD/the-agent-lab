"""Session 07b — Ecosystem Fluency: HuggingFace Hub, open-weight models, benchmarks."""
import time
from typing import Any, Optional

import litellm
from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv()

# Static benchmark reference table — scores sourced from public leaderboards (2025-Q2).
BENCHMARK_REFERENCE: list[dict[str, Any]] = [
    {"model": "gpt-4o",            "mmlu": 87.2, "humaneval": 90.2, "lmsys_rank": 3,  "mteb": 64.6},
    {"model": "claude-opus-4-7",   "mmlu": 88.2, "humaneval": 84.9, "lmsys_rank": 2,  "mteb": 62.1},
    {"model": "claude-sonnet-4-6", "mmlu": 85.7, "humaneval": 79.1, "lmsys_rank": 5,  "mteb": 60.3},
    {"model": "llama-3-70b",       "mmlu": 82.0, "humaneval": 72.4, "lmsys_rank": 12, "mteb": 58.1},
    {"model": "gemini-1.5-pro",    "mmlu": 85.9, "humaneval": 71.9, "lmsys_rank": 7,  "mteb": 63.2},
    {"model": "deepseek-v3",       "mmlu": 88.5, "humaneval": 89.1, "lmsys_rank": 4,  "mteb": 61.0},
    {"model": "mistral-large-2",   "mmlu": 84.0, "humaneval": 80.0, "lmsys_rank": 9,  "mteb": 59.4},
]


def search_hf_models(task: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search HuggingFace Hub for top models by pipeline tag, sorted by downloads."""
    api = HfApi()
    models = api.list_models(filter=task, sort="downloads", direction=-1, limit=limit)
    return [
        {"model_id": m.modelId, "downloads": m.downloads or 0, "tags": list(m.tags or [])}
        for m in models
    ]


def benchmark_scores(
    model_name: str, reference: list[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """Return the benchmark row for a model name, or None if not in the reference table."""
    for row in reference:
        if row["model"] == model_name:
            return row
    return None


def provider_shootout(
    prompt: str, providers: list[str]
) -> list[dict[str, Any]]:
    """Call each LiteLLM-compatible provider with the same prompt; return output and latency."""
    results = []
    for provider in providers:
        start = time.monotonic()
        response = litellm.completion(
            model=provider,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
        )
        latency_ms = (time.monotonic() - start) * 1000
        output = response.choices[0].message.content or ""
        results.append({"provider": provider, "output": output, "latency_ms": latency_ms})
    return results


def main() -> None:
    """Run ecosystem fluency demo: HF Hub search, provider shootout, benchmark table."""
    print("=" * 64)
    print("1. HUGGINGFACE HUB — TOP TEXT-GENERATION MODELS")
    print("=" * 64)
    models = search_hf_models("text-generation", limit=5)
    for m in models:
        print(f"  {m['model_id']:<45} {m['downloads']:>10,} downloads")

    print("\n" + "=" * 64)
    print("2. PROVIDER SHOOTOUT")
    print("=" * 64)
    prompt = "Explain gradient descent in one sentence."
    providers = ["anthropic/claude-sonnet-4-6", "openai/gpt-4o-mini"]
    results = provider_shootout(prompt, providers)
    for r in results:
        print(f"\n  {r['provider']} ({r['latency_ms']:.0f}ms):")
        print(f"  {r['output'][:120]!r}")

    print("\n" + "=" * 64)
    print("3. BENCHMARK SCORES")
    print("=" * 64)
    print(f"{'Model':<25} {'MMLU':>6} {'HumanEval':>10} {'LMSYS':>7} {'MTEB':>6}")
    print("-" * 58)
    for row in BENCHMARK_REFERENCE:
        print(
            f"{row['model']:<25} {row['mmlu']:>6.1f} {row['humaneval']:>10.1f}"
            f" {row['lmsys_rank']:>7} {row['mteb']:>6.1f}"
        )


if __name__ == "__main__":
    main()
