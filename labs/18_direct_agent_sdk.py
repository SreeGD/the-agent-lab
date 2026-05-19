"""Claude Agent SDK — Anthropic's purpose-built agent framework.

Higher-level than the raw `anthropic` SDK. The SDK uses Claude Code as the
agent runtime under the hood — it spawns a `claude` subprocess that
handles the loop, tool routing, MCP integration, and hooks.

Same agent task as 03_agent_manual.py and 18_direct_anthropic.py:
two tools (add, get_current_time), one compound question, parallel tool use.

REQUIRES: Claude Code (`claude` CLI) installed and authenticated.
"""

import asyncio
from datetime import datetime

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    query,
    tool,
)


# =====================================================================
# Tools — declared as MCP tools via @tool, then registered with an
# in-process MCP server. The SDK exposes them through Claude Code's
# tool-calling mechanism.
# =====================================================================

@tool("add", "Add two integers and return the sum.", {"a": int, "b": int})
async def add(args):
    return {"content": [{"type": "text", "text": str(args["a"] + args["b"])}]}


@tool("get_current_time", "Return the current local time as ISO 8601.", {})
async def get_current_time(args):
    return {
        "content": [{
            "type": "text",
            "text": datetime.now().isoformat(timespec="seconds"),
        }]
    }


# Bundle tools into an in-process MCP server
my_tools_server = create_sdk_mcp_server(
    name="my-tools",
    version="1.0.0",
    tools=[add, get_current_time],
)

# Agent options — restrict to our tools only (and Claude's permission system)
options = ClaudeAgentOptions(
    mcp_servers={"my-tools": my_tools_server},
    allowed_tools=[
        "mcp__my-tools__add",
        "mcp__my-tools__get_current_time",
    ],
    # Skip permission prompts so the demo runs hands-free
    permission_mode="bypassPermissions",
)


# =====================================================================
# Run + stream messages
# =====================================================================

async def main():
    print("=" * 70)
    print("CLAUDE AGENT SDK — agent via the official Anthropic agent framework")
    print("=" * 70)
    print("\n  Uses Claude Code as the runtime. Spawns a separate `claude`")
    print("  subprocess; doesn't share state with this terminal session.\n")

    prompt = (
        "Use the available tools to: (1) compute 47 + 158, "
        "(2) tell me the current time. Then report both results."
    )
    print(f"PROMPT: {prompt}")

    total_in = total_out = 0
    cost_usd = 0.0

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    print(f"\n[assistant]\n{block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"\n[tool_use] {block.name}({block.input})")
        elif isinstance(message, UserMessage):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    text = block.content
                    if isinstance(text, list):
                        text = "".join(c.get("text", "") for c in text if isinstance(c, dict))
                    print(f"[tool_result] {text}")
        elif isinstance(message, ResultMessage):
            if hasattr(message, "usage") and message.usage:
                total_in = message.usage.get("input_tokens", 0)
                total_out = message.usage.get("output_tokens", 0)
            if hasattr(message, "total_cost_usd"):
                cost_usd = message.total_cost_usd or 0.0

    print("\n" + "=" * 70)
    print("METRICS")
    print("=" * 70)
    print(f"  input tokens  : {total_in}")
    print(f"  output tokens : {total_out}")
    print(f"  cost (reported): ${cost_usd:.6f}")

    print("\n" + "=" * 70)
    print("LINE-COUNT vs other approaches (same agent, four frameworks)")
    print("=" * 70)
    print("  03_agent_manual.py       ~50 LOC  LangChain manual loop")
    print("  03_agent_framework.py    ~20 LOC  LangChain create_react_agent")
    print("  18_direct_anthropic.py   ~90 LOC  raw anthropic SDK (full control)")
    print("  18_direct_agent_sdk.py   ~70 LOC  Claude Agent SDK (Anthropic-native)")
    print()
    print("  The Claude Agent SDK is roughly framework-sized but Anthropic-locked:")
    print("  - Tools are MCP tools (in-process or external)")
    print("  - Loop hidden; you stream typed messages")
    print("  - Built-in Claude Code features (hooks, skills, sub-agents, sessions)")
    print("  - Provider swap is OFF the table (Anthropic-only)")
    print()
    print("  Decision matrix:")
    print("  ┌─────────────────────┬──────────────────────────────────┐")
    print("  │ goal                │ pick                             │")
    print("  ├─────────────────────┼──────────────────────────────────┤")
    print("  │ provider portability│ LangChain                        │")
    print("  │ Claude-native power │ Claude Agent SDK                 │")
    print("  │ tightest control    │ raw anthropic SDK                │")
    print("  │ fastest prototyping │ LangChain create_react_agent     │")
    print("  └─────────────────────┴──────────────────────────────────┘")


if __name__ == "__main__":
    asyncio.run(main())
