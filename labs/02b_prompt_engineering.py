"""Session 02b — Prompt Engineering: zero-shot → few-shot → CoT → XML → extended thinking."""
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-8"  # extended thinking requires Opus
MAX_TOKENS = 1024
THINKING_BUDGET = 2000

STRATEGIES: list[str] = [
    "zero_shot",
    "few_shot",
    "cot",
    "xml_structured",
    "extended_thinking",
]

TASK = (
    "A customer writes: 'The product arrived broken and support ignored me for 2 weeks.' "
    "Classify the sentiment (positive/negative/neutral) and urgency (low/medium/high). "
    "Output JSON with keys: sentiment, urgency, one_line_summary."
)

FEW_SHOT_EXAMPLES = """
Example 1:
Input: "Loved the fast shipping and the item works perfectly!"
Output: {"sentiment": "positive", "urgency": "low", "one_line_summary": "Happy customer, fast delivery"}

Example 2:
Input: "Received wrong item, very disappointed."
Output: {"sentiment": "negative", "urgency": "medium", "one_line_summary": "Wrong item delivered"}
"""


def _build_messages(task: str, strategy: str) -> list[dict[str, Any]]:
    """Return the messages list for the given prompting strategy."""
    if strategy == "zero_shot":
        return [{"role": "user", "content": task}]
    if strategy == "few_shot":
        return [{"role": "user", "content": f"{FEW_SHOT_EXAMPLES}\n\nNow classify:\n{task}"}]
    if strategy == "cot":
        return [
            {
                "role": "user",
                "content": (
                    f"{task}\n\nThink step by step: first identify emotional tone, "
                    "then assess urgency from the described situation, then summarize."
                ),
            }
        ]
    if strategy == "xml_structured":
        return [
            {
                "role": "user",
                "content": (
                    f"<task>{task}</task>\n"
                    "<instructions>Analyze the customer message. Output JSON only, no prose.</instructions>"
                ),
            }
        ]
    if strategy == "extended_thinking":
        return [{"role": "user", "content": task}]
    raise ValueError(f"Unknown strategy: {strategy}")


def run_strategy(
    task: str, strategy: str, client: anthropic.Anthropic
) -> dict[str, Any]:
    """Run the task with one prompting strategy; return output + token stats."""
    messages = _build_messages(task, strategy)
    kwargs: dict[str, Any] = {
        "model": OPUS_MODEL if strategy == "extended_thinking" else MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": messages,
    }
    if strategy == "extended_thinking":
        # extended thinking requires betas flag and no temperature (omit for Opus)
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET}
        kwargs["betas"] = ["interleaved-thinking-2025-05-14"]

    response = client.messages.create(**kwargs)
    text = next((b.text for b in response.content if hasattr(b, "text")), "")
    input_tok = response.usage.input_tokens
    output_tok = response.usage.output_tokens
    # Sonnet pricing: $3/M input, $15/M output
    cost = (input_tok * 3.0 + output_tok * 15.0) / 1_000_000

    return {
        "strategy": strategy,
        "output": text,
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "cost_usd": cost,
    }


def score_output(task: str, output: str, client: anthropic.Anthropic) -> int:
    """LLM-judge the output quality on a 1–5 scale."""
    prompt = (
        f"Task: {task}\n\nOutput to grade:\n{output}\n\n"
        "Rate the output quality 1–5 (5=perfect JSON with correct fields). "
        "Reply with a single digit only."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return max(1, min(5, int(response.content[0].text.strip()[0])))
    except (ValueError, IndexError):
        return 3


def main() -> None:
    """Run the prompt engineering workbench — compare all five strategies."""
    client = anthropic.Anthropic()
    print("PROMPT ENGINEERING WORKBENCH")
    print(f"Task: {TASK[:80]}...\n")
    print(f"{'Strategy':<22} {'Score':>5} {'In tok':>7} {'Out tok':>8} {'Cost USD':>10}")
    print("-" * 57)
    for strategy in STRATEGIES:
        result = run_strategy(TASK, strategy, client)
        score = score_output(TASK, result["output"], client)
        print(
            f"{strategy:<22} {score:>5} {result['input_tokens']:>7} "
            f"{result['output_tokens']:>8} ${result['cost_usd']:>9.6f}"
        )


if __name__ == "__main__":
    main()
