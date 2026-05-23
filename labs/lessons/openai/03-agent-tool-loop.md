# 03 — Agent Tool Loop

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_openai.ChatOpenAI`, model is `gpt-4o` (or `gpt-4o-mini`), and the API key env var is `OPENAI_API_KEY`. Code file: `labs/openai/03_agent_manual_openai.py`.

> **Give the model functions it can call.** When the LLM needs to compute, look up, or act, it emits a structured "tool call" request — and your code runs the function, feeds the result back, and the loop continues until the model produces a final answer.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01 model wrapper          (01_model_wrapper.py)                   ○ 13 system     ○ 16-19 Healthcare
  ✓ 02 LCEL composition       (02_lcel_chain.py)                       design       ○ 20-22 Agriculture
                                                           ○ 14 red-team   ○ 23-25 Finance
  ▶ 03 AGENT TOOL LOOP  ◄═══════ YOU ARE HERE              ○ 15 AI UX      ○ 26-28 Vidya Karana
                                                                            ○ 29-32 Family AI
  ○ 04 prompt caching         (04_prompt_caching.py)
  ○ 05 structured output      (05_structured_output.py)
  ○ 06 parallel chains        (06_parallel_chains.py)
  ○ 07 output parsers         (07_output_parsers.py)
  ○ 08 chatbot memory         (08_chatbot_memory.py)
  ○ 09 RAG                    (09_rag.py)
  ○ 10 guardrails             (10_guardrails.py)
  ○ 11 production capstone    (11_production_chatbot.py)
  ○ 12 MCP                    (12_mcp_server.py, 12_mcp_client.py)
```

**Why this lesson now:** lessons 01 + 02 give you one-shot Q&A. Real apps need the model to *do things* — look up data, check the clock, call APIs. The agent loop is the foundation pattern for every agentic system (ReAct, supervisor, RAG-as-tool, MCP, multi-agent).

---

## Files involved

| File | Role |
|---|---|
| [`03_agent_manual_openai.py`](../../openai/03_agent_manual_openai.py) | The manual tool loop — hand-written `while True` |
| [`03_agent_framework_openai.py`](../../openai/03_agent_framework_openai.py) | Same agent via `create_react_agent` from LangGraph (the framework version) |

---

## What problem it solves

LLMs are pure text functions — they cannot compute, fetch URLs, read files, or call APIs. Yet most useful AI products need exactly those abilities.

The agent loop bridges this gap: **the LLM proposes structured function calls; your code executes them; the results go back to the LLM**. The LLM gets effective access to actions without violating the safety boundary that it can only emit text.

Without it: you'd hand-parse the LLM's prose ("I think you should call `add(47, 158)`"), execute, re-prompt with results. Brittle, error-prone.

---

## The analogy

A **chef and a sous-chef**.

The head chef (LLM) knows the recipe but doesn't touch raw ingredients. When she needs "ribeye, medium-rare, three minutes per side," she writes the order on a ticket and hands it to the sous-chef (your code). The sous-chef runs the actual stove, returns the finished steak. The chef plates and serves.

The chef never operates the kitchen equipment. She just *proposes* actions on tickets. The sous-chef *executes* the actions safely. This is the entire security and reliability story behind tool-calling: **the LLM cannot run code; it can only request that code be run**.

---

## Visual

```
         ┌──────────────────────────────────────────────────┐
         │  Your code (the LLM Client / sous-chef)          │
         │                                                  │
         │   history = [HumanMessage("...")]                │
         │                                                  │
         │   while True:                                    │
         │     msg = model.invoke(history)                  │
         │     history.append(msg)                          │
         │     if not msg.tool_calls:  break       ─────────┼──── final answer
         │     for tc in msg.tool_calls:                    │
         │         result = registry[tc.name](tc.args)      │
         │         history.append(ToolMessage(result))      │
         │                                                  │
         └────────────────────┬─────────────────────────────┘
                              │
                              ▼ HTTP / tools=[schema, ...]
                       ┌─────────────┐
                       │   GPT-4o    │  proposes:
                       │  (the chef) │   tool_calls=[
                       └─────────────┘     {name: "add", args: {a: 47, b: 158}}
                              │           ]
                              ▼
                  AIMessage(tool_calls=[...])
```

The loop runs until GPT-4o stops asking for tools (i.e., produces an `AIMessage` with `.content` and no `tool_calls`).

---

## The concept

Two roles in every turn:

1. **The model** proposes function calls (JSON: name + args)
2. **Your code** executes the proposed functions and returns results

The "agent" is the loop that keeps doing (1) → (2) → (1) → (2) until the model commits to a final answer.

---

## The code

### Manual loop (`03_agent_manual_openai.py`)

```python
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

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

model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(tools)
history = [HumanMessage("What's 47 + 158 and what time is it?")]

while True:
    ai_msg = model.invoke(history)
    history.append(ai_msg)
    if not ai_msg.tool_calls:
        break
    for tc in ai_msg.tool_calls:
        result = tools_by_name[tc["name"]].invoke(tc["args"])
        history.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

print(ai_msg.content)
```

### Framework version (`03_agent_framework_openai.py`)

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(model, tools=[add, get_current_time])
result = agent.invoke({"messages": [("user", "What's 47 + 158 and what time is it?")]})
print(result["messages"][-1].content)
```

Same loop, four lines. The framework wins on production hardening (streaming, checkpointing, parallel execution, recursion limits).

---

## Run it

```bash
# Manual loop:
python openai/03_agent_manual_openai.py

# Framework version (recommended for production):
python openai/03_agent_framework_openai.py
```

Expected output (excerpt):

```
--- turn 1: calling model ---
  tool_call: add({'a': 47, 'b': 158})
  -> 205
  tool_call: get_current_time({})
  -> 2026-05-09T22:07:38

--- turn 2: calling model ---
--- final answer ---
1. **47 + 158 = 205**
2. **The current local time is 10:07 PM on May 9, 2026.**
```

Two turns, two tool calls executed in parallel on turn 1.

---

## Walk-through

### Turn 1: the model proposes tools

```
Input: HumanMessage("What's 47 + 158 and what time is it?")
       + tool schemas (auto-generated from @tool docstrings + type hints)

Output: AIMessage with:
  .content = ""
  .tool_calls = [
    {"name": "add",              "args": {"a": 47, "b": 158}},
    {"name": "get_current_time", "args": {}},
  ]
```

The model decided to call **both** tools in parallel. Your code runs both.

### Turn 2: the model sees the results, produces an answer

```
Input: HumanMessage + AIMessage(tool_calls) + ToolMessage(205) + ToolMessage("2026-05-09...")

Output: AIMessage with:
  .content = "1. **47 + 158 = 205**\n2. **The current local time is..."
  .tool_calls = []   ← no more tool requests; loop exits
```

The model has everything it needs and produces a natural-language answer.

---

## The most important mental model in this lesson

> **The LLM never calls anything. The LLM Client (your code) does.**

The LLM is a pure text function — it cannot run code, hit the clock, or open a network connection. It can only **emit structured JSON saying "I'd like `add(47, 158)` called."** Your code decides whether to honor that, executes the function, and feeds the result back as text.

This is why agents are safe by design: every action is your Python code, fully under your control. The LLM never operates the kitchen equipment.

---

## Production patterns this unlocks

| Pattern | Example |
|---|---|
| Calculator agent | `@tool def calc(expression: str)` |
| RAG-as-a-tool | `@tool def retrieve_docs(query: str) -> str` |
| Database query agent | `@tool def query_db(sql: str) -> list[dict]` |
| Multi-tool reasoning | `add` then `multiply` chained automatically |
| Cross-process tools | MCP — see [lesson 12](12-mcp.md) |
| Multi-agent handoffs | Specialist agents as tools — see Session 3 |

---

## Try this

1. **Break a tool intentionally** — `raise ValueError("nope")` in `add`. Watch GPT-4o get the error as a `ToolMessage` and recover.
2. **Unanswerable question** — *"What's the weather in Tokyo?"* with no weather tool. GPT-4o refuses instead of hallucinating.
3. **Sequential dependency** — add a `multiply(a, b)` tool, ask *"What is (47+158) × 3?"*. Watch a 3-turn loop: model calls `add`, waits for the result, then calls `multiply(a=205, b=3)`.
4. **Compare manual vs framework** — diff `03_agent_manual_openai.py` against `03_agent_framework_openai.py`. Notice how much the loop logic shrinks.

---

## Mental model in one line

> **An agent is a loop that lets the LLM call functions until it decides it's done. The LLM proposes (emits structured JSON); your code disposes (executes the function and feeds the result back). The LLM never executes anything itself.**

---

## FAQ

**Q: Why does the manual `03_agent_manual_openai.py` exist if `03_agent_framework_openai.py` does the same thing in 5 lines?**

A: Pedagogy. Writing the loop by hand once teaches you exactly what `create_react_agent` does inside. After that, when something breaks in production (model in an infinite loop, weird parallel-tool-call interaction, custom retry needed), you know how to debug it.

**Q: How does the model know about my tools' schemas?**

A: `@tool` is a decorator that introspects your function's type hints and docstring. It builds a JSON Schema like `{"name": "add", "description": "Add two integers and return the sum.", "parameters": {"a": {"type": "integer"}, "b": {"type": "integer"}}}`. `bind_tools([add, get_current_time])` attaches those schemas to every model call.

**Q: What if the model calls a tool that doesn't exist?**

A: It can't — the schemas it sees are exactly the tools you bound. The model will only emit tool names from that list. If you remove a tool but reference it in conversation history, the model might re-request it; defensive code should validate `tc["name"] in tools_by_name`.

**Q: What if a tool raises an exception?**

A: Append a `ToolMessage` with the error text as content. The model will see it on the next turn and adapt. In the framework version, `create_react_agent` handles this for you.

**Q: Are tool calls always parallel like in turn 1 here?**

A: Sometimes parallel (when the model identifies independent tools), sometimes sequential (when one tool depends on another's output). The model decides per turn.

**Q: What's the difference between `@tool` (LangChain) and an MCP tool?**

A: `@tool` defines an in-process Python function. MCP defines the same shape but **over JSON-RPC** so any client can use the tool. Same `tool_use`/`tool_result` mechanism on the model side. See [lesson 12](12-mcp.md).

**Q: Can I have the agent ask follow-up questions before calling tools?**

A: Yes — by default GPT-4o will ask for clarification when a tool's args aren't clear. You can also engineer prompts ("Ask me for missing info before calling tools") to bias this behavior.

**Q: How many turns can a loop run?**

A: Until the model stops requesting tools — but you should always set a recursion limit:
- Manual loop: `for turn in range(MAX_TURNS):`
- Framework: `agent.invoke(..., {"recursion_limit": 10})`
Without a limit, a bug can run up your OpenAI bill.

**Q: How is this related to ReAct?**

A: This *is* ReAct — Reason + Act. The model reasons (decides to call a tool), acts (the call gets executed), observes (sees the result), repeats. `create_react_agent` is literally the framework version of this loop.

---

## Related

- **Previous:** [02 — LCEL composition](02-lcel-composition.md)
- **Next:** [04 — Prompt caching](04-prompt-caching.md)
- **Productionized loop:** `03_agent_framework_openai.py` and its caching variant in [04](04-prompt-caching.md)
- **MCP version:** [12 — MCP](12-mcp.md)
- **All agent patterns side-by-side:** [reference-agentic-patterns](reference-agentic-patterns.md)
