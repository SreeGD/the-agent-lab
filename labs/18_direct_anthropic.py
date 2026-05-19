"""Direct Anthropic SDK — same agent as 03_agent_manual.py, no LangChain.

Shows the raw `client.messages.create(tools=[...])` API: content blocks
(text, tool_use, tool_result), stop reasons, and the bare-metal agent loop.

This is what LangChain wraps. Drop down to this level when you want fewer
dependencies, full control, or access to Anthropic-specific features that
the framework hasn't exposed yet.
"""

import os
from datetime import datetime

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Single client instance — auto-picks ANTHROPIC_API_KEY from env
client = anthropic.Anthropic()

MODEL = "claude-sonnet-4-6"
MAX_TURNS = 8


# =====================================================================
# Tools — plain Python functions + JSON Schema declarations
# =====================================================================

def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b


def get_current_time() -> str:
    """Return the current local time as an ISO 8601 string."""
    return datetime.now().isoformat(timespec="seconds")


# Anthropic expects tools as JSON Schemas. No decorator magic; you spell
# the schema out yourself (or wrap a helper to derive it from type hints).
TOOL_SCHEMAS = [
    {
        "name": "add",
        "description": "Add two integers and return the sum.",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "First integer."},
                "b": {"type": "integer", "description": "Second integer."},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Return the current local time as an ISO 8601 string.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

TOOL_REGISTRY = {
    "add": add,
    "get_current_time": get_current_time,
}


# =====================================================================
# The agent loop — same shape as 03_agent_manual.py, raw SDK
# =====================================================================

def run_agent(question: str, max_turns: int = MAX_TURNS) -> dict:
    """Run the propose-execute-feedback loop until the model finishes."""
    messages = [{"role": "user", "content": question}]
    total_in = total_out = 0

    for turn in range(1, max_turns + 1):
        print(f"\n--- turn {turn}: calling model ---")

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        total_in += response.usage.input_tokens
        total_out += response.usage.output_tokens

        # Append the assistant's reply to the conversation history
        messages.append({"role": "assistant", "content": response.content})

        # Check stop reason: 'end_turn' = done, 'tool_use' = needs us to run tools
        if response.stop_reason == "end_turn":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {
                "answer": final_text,
                "turns": turn,
                "input_tokens": total_in,
                "output_tokens": total_out,
            }

        if response.stop_reason != "tool_use":
            print(f"  unexpected stop_reason: {response.stop_reason}")
            return {
                "answer": "",
                "turns": turn,
                "input_tokens": total_in,
                "output_tokens": total_out,
            }

        # Run every tool_use block; collect tool_result blocks
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  tool_call: {block.name}({block.input})")
                fn = TOOL_REGISTRY[block.name]
                result = fn(**block.input)
                print(f"  -> {result}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

        # Feed the results back as a user message containing tool_result blocks
        messages.append({"role": "user", "content": tool_results})

    return {
        "answer": "max turns exhausted",
        "turns": max_turns,
        "input_tokens": total_in,
        "output_tokens": total_out,
    }


# =====================================================================
# Demo + side-by-side comparison with LangChain versions
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("DIRECT ANTHROPIC SDK — agent loop without LangChain")
    print("=" * 70)
    print(f"  model: {MODEL}")
    print(f"  tools: {[s['name'] for s in TOOL_SCHEMAS]}")

    result = run_agent(
        "What's 47 plus 158, and what time is it right now? Tell me both."
    )

    print("\n--- final answer ---")
    print(result["answer"])

    print("\n" + "=" * 70)
    print("METRICS")
    print("=" * 70)
    print(f"  turns         : {result['turns']}")
    print(f"  input tokens  : {result['input_tokens']}")
    print(f"  output tokens : {result['output_tokens']}")
    cost = (result["input_tokens"] * 3 + result["output_tokens"] * 15) / 1_000_000
    print(f"  cost (Sonnet) : ${cost:.6f}")

    print("\n" + "=" * 70)
    print("LINE-COUNT COMPARISON — same agent, three frameworks")
    print("=" * 70)
    print("  03_agent_manual.py       (LangChain manual loop)         ~50 LOC")
    print("  03_agent_framework.py    (LangChain create_react_agent)  ~20 LOC")
    print("  18_direct_anthropic.py   (this — raw anthropic SDK)      ~90 LOC")
    print("")
    print("  The framework version (create_react_agent) is the shortest")
    print("  because it hides the loop. Raw SDK is verbose but shows every")
    print("  step. Same wire format underneath, fewer abstractions.")
    print("")
    print("  When to drop LangChain:")
    print("   - You don't need provider portability (Anthropic-locked is fine)")
    print("   - You want fewer dependencies / faster cold start")
    print("   - You want Anthropic-specific features the framework hasn't wrapped yet")
    print("   - The LangChain abstraction is leaking and you need to debug below it")
