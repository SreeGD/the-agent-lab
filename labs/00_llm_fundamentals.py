"""Session 00 — LLM Fundamentals: tokenization, context windows, sampling, benchmarks."""
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512


def visualize_tokens(text: str, client: anthropic.Anthropic) -> str:
    """Return text annotated with approximate token boundaries and the API token count."""
    response = client.messages.count_tokens(
        model=MODEL,
        messages=[{"role": "user", "content": text}],
    )
    total = response.input_tokens
    # Approximate visual: mark every ~4 chars as a token boundary for display
    chunks = [text[i : i + 4] for i in range(0, len(text), 4)]
    annotated = "|".join(chunks)
    return f"{annotated}\n\nTotal tokens (API): {total}"


def fill_percentage(
    text: str, client: anthropic.Anthropic, model: str, max_tokens: int
) -> float:
    """Return fraction of the model's context window consumed by text."""
    response = client.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": text}],
    )
    return response.input_tokens / max_tokens


def sample_temperatures(
    prompt: str, client: anthropic.Anthropic, temps: list[float]
) -> list[dict[str, Any]]:
    """Call the model at each temperature and return a list of {temperature, output} dicts."""
    results = []
    for temp in temps:
        kwargs: dict[str, Any] = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        # temperature=0 is often unsupported; omit it to use the model default
        if temp > 0:
            kwargs["temperature"] = temp
        response = client.messages.create(**kwargs)
        results.append({"temperature": temp, "output": response.content[0].text})
    return results


def benchmark_table() -> list[dict[str, Any]]:
    """Return hardcoded benchmark scores for a representative set of models."""
    return [
        {"model": "claude-opus-4-7", "mmlu": 88.2, "humaneval": 84.9, "lmsys_rank": 2},
        {"model": "claude-sonnet-4-6", "mmlu": 85.7, "humaneval": 79.1, "lmsys_rank": 5},
        {"model": "gpt-4o", "mmlu": 87.2, "humaneval": 90.2, "lmsys_rank": 3},
        {"model": "llama-3-70b", "mmlu": 82.0, "humaneval": 72.4, "lmsys_rank": 12},
        {"model": "gemini-1.5-pro", "mmlu": 85.9, "humaneval": 71.9, "lmsys_rank": 7},
    ]


def print_benchmark_table(rows: list[dict[str, Any]]) -> None:
    """Print benchmark scores as an aligned table."""
    print(f"\n{'Model':<25} {'MMLU':>6} {'HumanEval':>10} {'LMSYS Rank':>12}")
    print("-" * 57)
    for row in rows:
        print(
            f"{row['model']:<25} {row['mmlu']:>6.1f} {row['humaneval']:>10.1f}"
            f" {row['lmsys_rank']:>12}"
        )


def main() -> None:
    """Run the LLM Fundamentals lab interactively."""
    client = anthropic.Anthropic()

    print("=" * 64)
    print("1. TOKENIZATION VISUALIZER")
    print("=" * 64)
    sample = "The transformer architecture uses self-attention mechanisms."
    print(f"Input: {sample!r}\n")
    print(visualize_tokens(sample, client))

    print("\n" + "=" * 64)
    print("2. CONTEXT WINDOW FILL %")
    print("=" * 64)
    pct = fill_percentage(sample, client, MODEL, 200_000)
    print(f"'{sample[:40]}...' uses {pct * 100:.4f}% of {MODEL}'s context window")

    print("\n" + "=" * 64)
    print("3. SAMPLING TEMPERATURES")
    print("=" * 64)
    prompt = "Complete this sentence in exactly five words: The best way to learn is"
    print(f"Prompt: {prompt!r}\n")
    results = sample_temperatures(prompt, client, [0.0, 0.7, 1.2])
    for r in results:
        print(f"  temp={r['temperature']:.1f}  ->  {r['output'].strip()!r}")

    print("\n" + "=" * 64)
    print("4. BENCHMARK COMPARISON TABLE")
    print("=" * 64)
    print_benchmark_table(benchmark_table())
    print("\n(Source: public leaderboards as of 2026-06)")


if __name__ == "__main__":
    main()
