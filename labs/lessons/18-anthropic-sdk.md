# 18 — Anthropic SDK / Claude Agent SDK (Session 7)

> **Build the same agent without LangChain — twice.** First with the raw `anthropic` SDK (low-level: `messages.create` + content blocks), then with Anthropic's purpose-built `claude-agent-sdk` (high-level: streams typed messages, uses Claude Code as the runtime). Direct comparison against the LangChain version reveals exactly what the framework wraps — and when dropping it pays off.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: ✓ all 3 sessions
                                                           Track B: ✓ all 3 sessions
                                                           Track C: Alt Architectures
                                                             ▶ Session 7: ANTHROPIC SDK  ◄ HERE
                                                             ○ Session 8: AI Gateway
                                                           Track D: ○ Files & Doc AI
                                                           Track E: ○ Custom Graphs
                                                           Track E.5: ○ RAG Architectures
                                                           Track F: ○ Production
```

**Why this lesson now:** every previous session used LangChain. Real production codebases often skip it (less surface area, fewer dependencies, faster cold start, direct access to provider-specific features). After this session you'll know exactly what LangChain abstracts and when to drop it.

---

## Files involved

| File | Role |
|---|---|
| [`18_direct_anthropic.py`](../18_direct_anthropic.py) | Raw `anthropic` SDK — agent loop using `client.messages.create()` and content blocks (`text`, `tool_use`, `tool_result`) |
| [`18_direct_agent_sdk.py`](../18_direct_agent_sdk.py) | `claude-agent-sdk` — Anthropic's purpose-built agent framework, runs through Claude Code |

---

## What problem it solves

LangChain is excellent for prototyping, composition, and provider portability — but it's not free:
- **Dependency size**: pulls in 100+ transitive packages
- **Cold start**: import time matters in serverless / Lambda
- **Abstraction leakage**: when something breaks, you debug through 2-3 framework layers
- **Vendor-lag**: provider-specific features (extended thinking, cache_control nuances, MCP integration) often land in raw SDKs first, then LangChain wraps them weeks/months later

For **production teams who've picked Anthropic** and don't need provider portability, dropping LangChain trades flexibility for simplicity. The trick is knowing what you're giving up.

---

## The analogy

LangChain is like **a fully-furnished apartment with utilities included** — everything you need to live there comes pre-installed. Easy to move in. Hard to redecorate without fighting the design.

Raw `anthropic` SDK is like **buying an empty studio and furnishing it yourself** — more work upfront, but every decision is yours, and there's nothing you can't change.

`claude-agent-sdk` is like **a serviced apartment in a Claude-themed building** — partially furnished, with the building's amenities (skills, hooks, sub-agents, MCP servers) included by default. Only available in the Claude building, though.

---

## Visual

```
┌─────────────────── same agent task, four implementations ───────────────────┐
│                                                                              │
│   prompt: "What's 47+158 and what time is it?"                               │
│                                                                              │
│   ┌─ 03_agent_manual.py ──────────┐     ┌─ 18_direct_anthropic.py ───────┐  │
│   │  LangChain manual loop        │     │  raw anthropic SDK              │  │
│   │   from langchain_anthropic    │     │   from anthropic import          │  │
│   │   from langchain_core.tools   │     │       Anthropic                  │  │
│   │   @tool decorator             │     │   tool schemas as plain dicts    │  │
│   │   bind_tools(tools)           │     │   client.messages.create(        │  │
│   │   while not msg.tool_calls:   │     │     tools=[...])                 │  │
│   │       ... ToolMessage ...     │     │   content blocks: text /         │  │
│   │   ~50 LOC                     │     │     tool_use / tool_result       │  │
│   └───────────────────────────────┘     │   ~90 LOC                        │  │
│                                          └──────────────────────────────────┘  │
│   ┌─ 03_agent_framework.py ───────┐     ┌─ 18_direct_agent_sdk.py ────────┐  │
│   │  LangChain framework          │     │  Claude Agent SDK                │  │
│   │   from langgraph.prebuilt     │     │   from claude_agent_sdk import   │  │
│   │       import                  │     │       query, tool,               │  │
│   │       create_react_agent      │     │       create_sdk_mcp_server      │  │
│   │   agent = create_react_agent(  │     │   tools = MCP-defined            │  │
│   │     model, tools=[...])       │     │   async for msg in query(        │  │
│   │   ~20 LOC                     │     │     prompt, options)             │  │
│   │                                │     │   uses Claude Code as runtime    │  │
│   └───────────────────────────────┘     │   ~70 LOC                        │  │
│                                          └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## The concept — raw `anthropic` SDK

```python
import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "name": "add",
        "description": "Add two integers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        },
    },
    # ... get_current_time similarly
]

tool_registry = {"add": lambda a, b: a + b, ...}

messages = [{"role": "user", "content": "What's 47 + 158?"}]

while True:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        tools=tools,
        messages=messages,
    )
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason == "end_turn":
        break

    # Run every tool_use; build tool_result blocks
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result = tool_registry[block.name](**block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            })

    messages.append({"role": "user", "content": tool_results})
```

**Key vocabulary shift:** content blocks (`text`, `tool_use`, `tool_result`) replace LangChain's `AIMessage` / `ToolMessage`. Same wire format underneath — LangChain literally serializes to these blocks before calling the API.

---

## The concept — Claude Agent SDK

```python
from claude_agent_sdk import (
    query, tool, create_sdk_mcp_server, ClaudeAgentOptions,
    AssistantMessage, ToolUseBlock, TextBlock,
)

@tool("add", "Add two integers.", {"a": int, "b": int})
async def add(args):
    return {"content": [{"type": "text", "text": str(args["a"] + args["b"])}]}

# Wrap tools in an in-process MCP server
my_tools_server = create_sdk_mcp_server(
    name="my-tools", version="1.0.0", tools=[add, get_current_time]
)

options = ClaudeAgentOptions(
    mcp_servers={"my-tools": my_tools_server},
    allowed_tools=["mcp__my-tools__add", "mcp__my-tools__get_current_time"],
    permission_mode="bypassPermissions",
)

async for message in query(prompt="What's 47+158 and the time?", options=options):
    # message is AssistantMessage / UserMessage / ResultMessage / ...
    ...
```

**Key shifts from LangChain:**
- Tools are **MCP tools** (registered with an in-process MCP server, then exposed by ID)
- Loop is **hidden** — you stream typed messages instead of running the loop
- Uses **Claude Code as the runtime** — spawns a `claude` subprocess that handles execution
- All Claude Code features (skills, hooks, sub-agents, sessions) available natively

---

## Run them

```bash
python 18_direct_anthropic.py
python 18_direct_agent_sdk.py
```

(The second requires Claude Code installed.)

---

## Real numbers from clean runs

| | 03_agent_manual.py | 03_agent_framework.py | 18_direct_anthropic.py | 18_direct_agent_sdk.py |
|---|---|---|---|---|
| Lines of code | ~50 | ~20 | ~90 | ~70 |
| Turns | 2 | 2 | 2 | 2 |
| Input tokens | 1,458 | ~1,500 | 1,484 | 13 (reported) |
| Output tokens | 163 | ~150 | 147 | 437 |
| Cost (USD) | $0.007 | $0.007 | **$0.007** | **$0.405** |
| Cold start | medium | medium | fast | slow (spawns subprocess) |

The cost difference between raw SDK and Agent SDK is **dramatic** — $0.007 vs $0.405. That's because the Claude Agent SDK uses Claude Code as the runtime, which loads its own system prompt + 50+ skills + permission system by default. Even a trivial task pays that overhead.

**Translation:** the Claude Agent SDK is for tasks that *benefit from* Claude Code's full power. For simple agent loops, raw SDK is dramatically cheaper.

---

## Walk-through

### What LangChain actually wraps

When you write `model.invoke(messages)` in LangChain, the framework does:

1. Serialize each `Message` object → Anthropic's wire format
2. Add tool schemas from `bind_tools(...)` calls
3. Set `model`, `max_tokens`, other params
4. Call `client.messages.create(...)` via the `anthropic` SDK
5. Deserialize the response's content blocks → `AIMessage` with `.tool_calls`, `.content`, etc.

**Steps 1-4 are exactly what `18_direct_anthropic.py` does manually.** The wrapping is real (less code in app), but it's also real overhead (extra deserialization, extra abstractions to debug through).

### The decision matrix

```
   ┌────────────────────────────────────────────────────────────────────┐
   │ Do you need provider portability (Claude OR GPT OR Gemini OR ...)? │
   │                                                                    │
   │   YES → LangChain                                                  │
   │         (you'll change one line to swap providers)                 │
   │                                                                    │
   │   NO  → Are you using Claude Code's features (skills, hooks, etc)? │
   │                                                                    │
   │         YES → Claude Agent SDK                                     │
   │               (gives you the full Claude Code platform)            │
   │                                                                    │
   │         NO  → Is your team large enough to maintain framework code?│
   │                                                                    │
   │               YES → LangChain (the team will benefit from the      │
   │                     bigger ecosystem and parameter conventions)    │
   │                                                                    │
   │               NO  → raw anthropic SDK                              │
   │                     (smallest dependency footprint, fastest        │
   │                      cold start, direct access to features)        │
   └────────────────────────────────────────────────────────────────────┘
```

### When the SDK choice changes your architecture

Each option has architectural implications:

| | LangChain | raw anthropic | Claude Agent SDK |
|---|---|---|---|
| Cold start | ~1-2s (lots of imports) | <0.5s | ~2-5s (spawn subprocess) |
| Memory footprint | ~200MB (LangChain + deps) | ~30MB | ~50MB + Claude Code |
| Async support | sync + async via wrappers | sync + async native | async-only (streams) |
| Multi-provider | first-class | rewrite per provider | Anthropic-only |
| Caching control | via `cache_control` blocks | direct `cache_control` blocks | direct + Claude Code's session caching |
| Tool definition | `@tool` decorator (auto schemas) | manual JSON Schema | `@tool` + MCP server |
| Built-in tools | none | none | Claude Code's full toolkit (file ops, web search, ...) |
| State / memory | LangGraph `MemorySaver` | manual | Claude Code sessions |

For a high-throughput stateless API → **raw `anthropic` SDK**.
For a coding agent that needs file editing + shell access → **Claude Agent SDK**.
For a multi-provider chatbot with fallback → **LangChain**.

---

## Production patterns this unlocks

| Pattern | Pick |
|---|---|
| Lambda function calling Claude on each request | raw `anthropic` SDK (cold-start sensitive) |
| Coding assistant (Cursor-style) | Claude Agent SDK (uses Claude Code's editor primitives) |
| Multi-tenant chatbot with Claude/GPT failover | LangChain (provider portability) |
| Background batch processor | raw `anthropic` SDK + Batches API |
| Research agent with web + filesystem | Claude Agent SDK (Claude Code's built-in tools) |
| Provider-agnostic library you're shipping | LangChain (consumers pick their provider) |

---

## Try this

1. **Diff `18_direct_anthropic.py` against `03_agent_manual.py`** — see where the same logic lives in raw SDK vs LangChain. Notice what each abstraction is "for".
2. **Add a third tool** to the raw SDK version — you have to write the JSON Schema by hand. Compare to LangChain's `@tool` which derives it from type hints.
3. **Profile cold-start times** — `time python 03_agent_framework.py` vs `time python 18_direct_anthropic.py`. The raw SDK wins by seconds.
4. **Add prompt caching directly** — in `18_direct_anthropic.py`, add `"cache_control": {"type": "ephemeral"}` to a message's content block. Watch the cache hit appear in `response.usage.cache_read_input_tokens`.
5. **Use the Claude Agent SDK with a real skill** — copy one of your `labs/skills/*/SKILL.md` to `~/.claude/skills/`, then ask the SDK agent a question that should trigger it. Watch the SDK auto-load the skill.

---

## Mental model in one line

> **LangChain wraps the raw `anthropic` SDK with composition (`|`), provider portability, and an ecosystem. The Claude Agent SDK wraps Claude Code with first-class skill/hook/MCP integration. The raw SDK is what's underneath both. Pick the layer that gives you what you need without paying for what you don't.**

---

## FAQ

**Q: If raw SDK is cheaper, why use LangChain at all?**

A: Three reasons people pick LangChain in production: (1) **provider portability** — one config flip changes the model; (2) **composition primitives** (`prompt | model | parser`, `RunnableParallel`, structured output) that give you sync + async + streaming + batch for free; (3) **ecosystem** — every vector store, parser, tool integration is already wrapped. For a small team that wants to ship a chatbot and not write infrastructure, LangChain pays for itself.

**Q: Can I mix? Use raw SDK for hot paths and LangChain for prototyping?**

A: Yes — they share the same underlying API. You can prototype in LangChain, then drop down to the raw SDK for the production hot path. LangChain's `AIMessage.usage_metadata` even maps 1:1 to the raw SDK's `response.usage`.

**Q: Does the Claude Agent SDK work without Claude Code installed?**

A: No. The SDK spawns `claude` as a subprocess; Claude Code must be installed and authenticated. Without it, you'd get a `ProcessError` at runtime.

**Q: Why does the Claude Agent SDK cost so much more in the demo?**

A: It loads Claude Code's full default context — system prompt, all installed skills, permission system, MCP server descriptions. Even for a trivial task, you pay for all that overhead (the `total_cost_usd` reported includes everything, not just your tool calls). Translation: the SDK is for tasks that *benefit* from that context. For simple tool calls, raw SDK is dramatically cheaper.

**Q: Can I get streaming with the raw `anthropic` SDK?**

A: Yes — `with client.messages.stream(...) as stream:`. The streaming API yields events as the model generates. Same shape as LangChain's `.stream()` / `.astream()` but without the wrapper.

**Q: What about extended thinking?**

A: Both SDKs support it. In raw `anthropic`: `extended_thinking={"type": "enabled", "budget_tokens": 10000}`. In Claude Agent SDK: `ClaudeAgentOptions(thinking_config=ThinkingConfigEnabled(...))`. LangChain wraps it but sometimes lags new model capabilities by weeks.

**Q: How do I do MCP with raw SDK?**

A: The raw `anthropic` SDK doesn't have first-class MCP integration. You'd run the MCP client separately, list tools, pass them as schemas to `messages.create(tools=[...])`, and route `tool_use` calls back to your MCP client. The Claude Agent SDK has MCP integration built in.

**Q: Can I run async with raw SDK?**

A: Yes — `anthropic.AsyncAnthropic()` is the async version. Same API, `await`-friendly.

**Q: Is `claude-agent-sdk` Anthropic's official SDK?**

A: Yes — published by Anthropic. It's intended for building agents on Claude Code's runtime, including the full set of Claude Code features (skills, hooks, sub-agents, session management). For agents that don't need Claude Code's tools (file editing, shell, web search, etc.), the raw `anthropic` SDK is simpler.

**Q: Where does the line count actually matter?**

A: For one-off scripts, line count doesn't matter. For a codebase your team maintains, **fewer lines of code = less to read, less to test, less to update when SDKs change**. LangChain's 20 LOC vs raw SDK's 90 LOC is real maintenance debt — but provider portability is also real value. The trade is yours.

---

## Related

- **Previous:** [17 — Claude Skills](17-claude-skills.md)
- **Next:** Session 8 — AI Gateway (LiteLLM / OpenRouter / Vercel AI Gateway)
- **Builds on:** [03 — Agent tool loop](03-agent-tool-loop.md) (the LangChain version of the same agent)
- **Pattern reference:** [reference-agentic-patterns](reference-agentic-patterns.md)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 7 of 40 (Track C 1/2)
