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


def sdlc_analogy_demo(client: anthropic.Anthropic) -> dict[str, Any]:
    """Show the same task solved two ways: traditional rule-based vs LLM.

    Helps SDLC engineers see where LLMs replace brittle if/else chains.
    """
    text = "This product exceeded all my expectations! Absolutely love it."

    # Traditional approach: keyword matching
    positive_words = {"love", "great", "excellent", "amazing", "exceeded", "fantastic"}
    negative_words = {"hate", "terrible", "awful", "broken", "waste", "horrible"}
    words = set(text.lower().split())
    if words & positive_words:
        traditional_result = "positive"
    elif words & negative_words:
        traditional_result = "negative"
    else:
        traditional_result = "unknown"

    # LLM approach: natural language instruction
    response = client.messages.create(
        model=MODEL,
        max_tokens=20,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Classify the sentiment as exactly one word: "
                    f"positive, negative, or neutral.\n\nText: {text}"
                ),
            }
        ],
    )
    llm_result = response.content[0].text.strip().lower()

    return {
        "input": text,
        "traditional_keyword_match": traditional_result,
        "llm_classification": llm_result,
        "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
    }


def token_cost_estimator(texts: list[str], client: anthropic.Anthropic) -> list[dict[str, Any]]:
    """Estimate token counts for a list of texts — like a query cost estimator for your LLM calls.

    Shows SDLC engineers how to think about token budgets the same way they
    think about DB query costs or API call quotas.
    """
    results = []
    for text in texts:
        response = client.messages.count_tokens(
            model=MODEL,
            messages=[{"role": "user", "content": text}],
        )
        tokens = response.input_tokens
        # Approximate cost: Sonnet 4.6 input = ~$3 per 1M tokens
        cost_usd = (tokens / 1_000_000) * 3.0
        results.append({
            "preview": text[:60] + ("..." if len(text) > 60 else ""),
            "tokens": tokens,
            "cost_usd": round(cost_usd, 6),
            "chars_per_token": round(len(text) / tokens, 2) if tokens else 0,
        })
    return results


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

    print("\n" + "=" * 64)
    print("5. SDLC ANALOGY — TRADITIONAL vs LLM CLASSIFICATION")
    print("=" * 64)
    demo = sdlc_analogy_demo(client)
    print(f"Input:                   {demo['input'][:55]}...")
    print(f"Traditional (keywords):  {demo['traditional_keyword_match']}")
    print(f"LLM (natural language):  {demo['llm_classification']}")
    print(f"Tokens consumed:         {demo['tokens_used']}")
    print("\nKey insight: the LLM handles 'exceeded', 'love', and edge cases")
    print("the keyword list doesn't know about — without code changes.")

    print("\n" + "=" * 64)
    print("6. TOKEN COST ESTIMATOR (like query cost for DB engineers)")
    print("=" * 64)
    sample_texts = [
        "What is the weather today?",
        "Explain the transformer architecture in detail, covering attention heads, "
        "residual streams, and how depth relates to reasoning capability.",
        "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
    ]
    estimates = token_cost_estimator(sample_texts, client)
    print(f"\n{'Text preview':<45} {'Tokens':>7} {'Cost (USD)':>12} {'Chars/tok':>10}")
    print("-" * 78)
    for est in estimates:
        print(
            f"{est['preview']:<45} {est['tokens']:>7} "
            f"${est['cost_usd']:>11.6f} {est['chars_per_token']:>10.2f}"
        )
    print("\nRule of thumb: ~4 chars/token for English prose; code costs 2-3x more.")


if __name__ == "__main__":
    main()
