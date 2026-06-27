"""Agent tool loop — manual ReAct cycle with LangChain + Claude.

Demonstrates the core agentic pattern: model emits tool_use blocks,
code executes the tools, results feed back into the next model turn,
until the model produces a final answer with no tool calls.
Also shows dispatch_tools_parallel for concurrent multi-tool dispatch.
"""

import asyncio
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool

load_dotenv()


@tool
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b


@tool
def get_current_time() -> str:
    """Return the current local time as an ISO 8601 string."""
    return datetime.now().isoformat(timespec="seconds")


tools = [add, get_current_time]
tools_by_name = {t.name: t for t in tools}


# ── Parallel tool call dispatch ────────────────────────────────────────────────

def dispatch_tools_parallel(tool_use_blocks: list[Any]) -> list[dict[str, Any]]:
    """Dispatch all tool_use blocks concurrently; return tool_result dicts."""

    async def _call(block: Any) -> dict[str, Any]:
        if block.name == "add":
            result = add.invoke(block.input)
        elif block.name == "get_current_time":
            result = get_current_time.invoke(block.input)
        else:
            result = f"Unknown tool: {block.name}"
        return {"type": "tool_result", "tool_use_id": block.id, "content": str(result)}

    async def _run_all() -> list[dict[str, Any]]:
        return await asyncio.gather(
            *[_call(b) for b in tool_use_blocks if b.type == "tool_use"]
        )

    return asyncio.run(_run_all())


if __name__ == "__main__":
    model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0).bind_tools(tools)

    history = [HumanMessage("What's 47 plus 158, and what time is it right now? Tell me both.")]

    turn = 1
    while True:
        print(f"\n--- turn {turn}: calling model ---")
        ai_msg = model.invoke(history)
        history.append(ai_msg)

        if not ai_msg.tool_calls:
            print("\n--- final answer ---")
            print(ai_msg.content)
            break

        for tc in ai_msg.tool_calls:
            print(f"  tool_call: {tc['name']}({tc['args']})")
            result = tools_by_name[tc["name"]].invoke(tc["args"])
            print(f"  -> {result}")
            history.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

        turn += 1
