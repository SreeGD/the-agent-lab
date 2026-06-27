"""Session 08b — Inference Platforms: cloud comparison + Ollama self-hosting."""
import time
from typing import Any

import litellm
from dotenv import load_dotenv

load_dotenv()

# Three fast-inference cloud providers with OpenAI-compatible APIs via LiteLLM
CLOUD_PROVIDERS: list[dict[str, Any]] = [
    {
        "name": "groq",
        "litellm_model": "groq/llama3-8b-8192",
        "cost_per_1m": 0.05,
    },
    {
        "name": "together",
        "litellm_model": "together_ai/togethercomputer/llama-3-8b",
        "cost_per_1m": 0.20,
    },
    {
        "name": "fireworks",
        "litellm_model": "fireworks_ai/accounts/fireworks/models/llama-v3-8b-instruct",
        "cost_per_1m": 0.20,
    },
]

PROMPT = "Explain the attention mechanism in exactly two sentences."


def cloud_comparison(
    prompt: str,
    providers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Call each cloud provider and record latency, throughput, and cost.

    Returns one result dict per provider with keys: name, litellm_model,
    latency_ms, tokens_per_sec, cost_per_1m, output (and optionally error).
    """
    results: list[dict[str, Any]] = []
    for provider in providers:
        start = time.monotonic()
        try:
            response = litellm.completion(
                model=provider["litellm_model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
            )
            latency_ms = (time.monotonic() - start) * 1000
            output: str = response.choices[0].message.content or ""
            tokens: int = getattr(response.usage, "total_tokens", 0)
            # tokens per second — avoids division by zero on mocked latency
            tps: float = tokens / (latency_ms / 1000) if latency_ms > 0 else 0.0
            results.append(
                {
                    "name": provider["name"],
                    "litellm_model": provider["litellm_model"],
                    "latency_ms": round(latency_ms, 1),
                    "tokens_per_sec": round(tps, 1),
                    "cost_per_1m": provider.get("cost_per_1m", 0.0),
                    "output": output,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "name": provider["name"],
                    "litellm_model": provider.get("litellm_model", ""),
                    "latency_ms": 0.0,
                    "tokens_per_sec": 0.0,
                    "cost_per_1m": provider.get("cost_per_1m", 0.0),
                    "output": "",
                    "error": str(exc),
                }
            )
    return results


def call_ollama(prompt: str, model: str, base_url: str) -> str:
    """Call a locally running Ollama instance via its OpenAI-compatible endpoint.

    Raises litellm.exceptions on connection failure — callers should catch.
    """
    response = litellm.completion(
        model=f"ollama/{model}",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
        api_base=base_url,
    )
    return response.choices[0].message.content or ""


def _print_comparison_table(results: list[dict[str, Any]]) -> None:
    """Print a formatted table of cloud comparison results."""
    print(f"\n{'Provider':<12} {'Latency ms':>12} {'tok/s':>8} {'$/1M':>8}")
    print("-" * 44)
    for result in results:
        if "error" in result:
            print(f"{result['name']:<12} ERROR: {result['error'][:35]}")
        else:
            print(
                f"{result['name']:<12}"
                f" {result['latency_ms']:>12.0f}"
                f" {result['tokens_per_sec']:>8.1f}"
                f" ${result['cost_per_1m']:>7.2f}"
            )


def main() -> None:
    """Run cloud comparison, then demonstrate Ollama self-hosting."""
    print("=" * 64)
    print("PART 1 — CLOUD INFERENCE COMPARISON")
    print("=" * 64)

    results = cloud_comparison(PROMPT, CLOUD_PROVIDERS)
    _print_comparison_table(results)

    print("\n" + "=" * 64)
    print("PART 2 — SELF-HOSTING VIA OLLAMA")
    print("=" * 64)
    print("Start Ollama first:")
    print("  docker compose -f labs/docker/ollama-compose.yml up -d")
    try:
        output = call_ollama(PROMPT, "llama3", "http://localhost:11434/v1")
        print(f"\nOllama llama3 response:\n{output}")
    except Exception as exc:
        print(f"\nOllama not running: {exc}")
        print("Run: docker compose -f labs/docker/ollama-compose.yml up -d")


if __name__ == "__main__":
    main()
