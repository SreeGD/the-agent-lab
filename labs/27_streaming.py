"""Streaming — total latency vs perceived latency.

A 4-second answer feels broken if nothing renders for 4 seconds. The
same 4 seconds feels fast if words start landing at 400ms. Streaming
converts total wall time into PERCEIVED latency — same compute, very
different UX.

Four demos, each measurable:

  Demo 1 — Raw SDK streaming + TTFT vs total wall time
  Demo 2 — LangChain .stream() over an LCEL chain
  Demo 3 — LangGraph stream modes (values / updates / messages)
  Demo 4 — The tool-use streaming gotcha (visible pause between passes)
"""

import sys
import time
from typing import TypedDict

import anthropic
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

load_dotenv()

MODEL = "claude-sonnet-4-6"
raw_client = anthropic.Anthropic()
lc_model = ChatAnthropic(model=MODEL, temperature=0)


# =====================================================================
# Demo 1 — Raw SDK streaming, TTFT vs total
# =====================================================================

PROMPT_FOR_TIMING = (
    "Explain prompt caching to a developer in about 60 words. "
    "Cover what gets cached, when it pays off, and the TTL."
)


def demo_1_raw_sdk_stream():
    print("\n" + "=" * 70)
    print("DEMO 1 — Raw SDK streaming: TTFT vs total wall time")
    print("=" * 70)

    # --- Non-streamed (the baseline UX) ---
    print("\n  Non-streamed (single blocking call):")
    t0 = time.perf_counter()
    resp = raw_client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT_FOR_TIMING}],
    )
    total = time.perf_counter() - t0
    print(f"    user sees BLANK SCREEN for {total*1000:.0f} ms, then full text:")
    print(f"    > {resp.content[0].text[:90]}...")
    print(f"    TTFT: {total*1000:.0f} ms     total: {total*1000:.0f} ms")

    # --- Streamed (the actual UX) ---
    print("\n  Streamed (same prompt, .messages.stream()):")
    t0 = time.perf_counter()
    first_token_at = None
    print(f"    > ", end="", flush=True)
    with raw_client.messages.stream(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT_FOR_TIMING}],
    ) as stream:
        for text in stream.text_stream:
            if first_token_at is None:
                first_token_at = time.perf_counter() - t0
            # Cap the inline echo so the terminal doesn't get spammy
            if (time.perf_counter() - t0) < 1.5:
                sys.stdout.write(text)
                sys.stdout.flush()
    total = time.perf_counter() - t0
    print(f"\n    TTFT: {first_token_at*1000:.0f} ms     total: {total*1000:.0f} ms")
    print(f"    → Same total compute. TTFT dropped ~{(1 - first_token_at/total)*100:.0f}% — that's the UX win.")


# =====================================================================
# Demo 2 — LangChain .stream() over LCEL
# =====================================================================

def demo_2_langchain_stream():
    print("\n" + "=" * 70)
    print("DEMO 2 — LangChain .stream() over an LCEL chain")
    print("=" * 70)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a concise technical writer."),
        ("user", "{topic}"),
    ])
    chain = prompt | lc_model | StrOutputParser()

    print("\n  chain.stream({topic: ...}) — chunks arrive as they're generated:\n")
    print(f"    > ", end="", flush=True)
    t0 = time.perf_counter()
    first_token_at = None
    chunk_count = 0
    for chunk in chain.stream({"topic": "Explain LCEL composition in 40 words."}):
        if first_token_at is None:
            first_token_at = time.perf_counter() - t0
        chunk_count += 1
        if (time.perf_counter() - t0) < 1.5:
            sys.stdout.write(chunk)
            sys.stdout.flush()
    total = time.perf_counter() - t0
    print(f"\n    chunks: {chunk_count}    TTFT: {first_token_at*1000:.0f} ms    total: {total*1000:.0f} ms")
    print(f"    → Each chunk is a small string. StrOutputParser passes them through unchanged.")
    print(f"    → JsonOutputParser would buffer until a valid JSON is parseable — partial JSON is invalid.")


# =====================================================================
# Demo 3 — LangGraph stream modes
# =====================================================================

class State(TypedDict):
    question: str
    plan: str
    answer: str


def node_plan(state: State) -> dict:
    resp = lc_model.invoke([
        SystemMessage("Output a one-sentence plan for answering the question. No prose."),
        HumanMessage(state["question"]),
    ])
    return {"plan": resp.content}


def node_answer(state: State) -> dict:
    resp = lc_model.invoke([
        SystemMessage("Answer the question concisely using the plan as guidance."),
        HumanMessage(f"PLAN: {state['plan']}\n\nQUESTION: {state['question']}"),
    ])
    return {"answer": resp.content}


def build_simple_graph():
    g = StateGraph(State)
    g.add_node("plan", node_plan)
    g.add_node("answer", node_answer)
    g.add_edge(START, "plan")
    g.add_edge("plan", "answer")
    g.add_edge("answer", END)
    return g.compile()


def demo_3_langgraph_stream_modes():
    print("\n" + "=" * 70)
    print("DEMO 3 — LangGraph stream modes")
    print("=" * 70)
    graph = build_simple_graph()
    inputs = {"question": "What is structured output in LangChain?"}

    print("\n  stream_mode='values' — emits the FULL state after each node:")
    for state in graph.stream(inputs, stream_mode="values"):
        keys_present = {k: bool(v) for k, v in state.items()}
        print(f"    state: {keys_present}")

    print("\n  stream_mode='updates' — emits only what each node CHANGED:")
    for update in graph.stream(inputs, stream_mode="updates"):
        for node_name, changes in update.items():
            keys = list(changes.keys())
            preview = next(iter(changes.values()), "")[:60] if keys else ""
            print(f"    [{node_name}] changed {keys}    preview: {preview!r}")

    print("\n  stream_mode='messages' — emits per-token deltas from LLM calls in the graph:")
    print(f"    > ", end="", flush=True)
    t0 = time.perf_counter()
    seen_node = None
    for msg, meta in graph.stream(inputs, stream_mode="messages"):
        node = meta.get("langgraph_node", "?")
        if node != seen_node:
            sys.stdout.write(f"\n    [{node}] ")
            seen_node = node
        if (time.perf_counter() - t0) < 2.0:
            sys.stdout.write(msg.content if isinstance(msg.content, str) else "")
            sys.stdout.flush()
    print(f"\n    → 'messages' mode is what production chat UIs use to stream tokens to the browser.")
    print(f"    → 'updates' mode powers the 'planning…' / 'searching…' status indicator.")


# =====================================================================
# Demo 4 — Tool-use streaming gotcha
# =====================================================================

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city. Returns a one-sentence summary."""
    return f"It is 18°C and partly cloudy in {city}."


def demo_4_tool_streaming_gotcha():
    print("\n" + "=" * 70)
    print("DEMO 4 — Tool-use streaming gotcha: the visible pause")
    print("=" * 70)
    print("  When the agent decides to call a tool, the LLM stream produces a")
    print("  tool_use block, then STOPS. Tool runs (locally). Then a SECOND")
    print("  LLM call streams the final answer. The pause between passes is")
    print("  what users see as 'thinking…' in production UIs.\n")

    agent = create_react_agent(lc_model, [get_weather])

    print("  Streaming agent execution with mode='values':\n")
    t0 = time.perf_counter()
    step_counter = 0
    last_msg_count = 0
    for state in agent.stream(
        {"messages": [HumanMessage("What's the weather in Hyderabad?")]},
        stream_mode="values",
    ):
        step_counter += 1
        msgs = state.get("messages", [])
        new_msgs = msgs[last_msg_count:]
        last_msg_count = len(msgs)
        elapsed = time.perf_counter() - t0
        for m in new_msgs:
            kind = type(m).__name__
            # Detect tool calls vs plain text
            has_tool_calls = bool(getattr(m, "tool_calls", None))
            if has_tool_calls:
                tc = m.tool_calls[0]
                print(f"    [t={elapsed*1000:>5.0f}ms] step={step_counter} {kind:<14} → tool_call: {tc['name']}({tc['args']})")
            elif kind == "ToolMessage":
                content_preview = (m.content[:60] + "...") if len(m.content) > 60 else m.content
                print(f"    [t={elapsed*1000:>5.0f}ms] step={step_counter} {kind:<14} ← tool result: {content_preview!r}")
            elif kind == "AIMessage":
                preview = (m.content[:70] + "...") if len(m.content) > 70 else m.content
                print(f"    [t={elapsed*1000:>5.0f}ms] step={step_counter} {kind:<14}   answer: {preview!r}")
            else:
                pass  # HumanMessage echo from the input — skip

    total = time.perf_counter() - t0
    print(f"\n    total: {total*1000:.0f} ms")
    print(f"    → Two LLM round-trips: one to decide the tool call, one to compose the answer.")
    print(f"    → In production, render the tool_call event as 'searching weather…',")
    print(f"      then resume streaming once the tool result comes back.")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("STREAMING — total latency vs perceived latency")
    print("=" * 70)

    demo_1_raw_sdk_stream()
    demo_2_langchain_stream()
    demo_3_langgraph_stream_modes()
    demo_4_tool_streaming_gotcha()

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  • DEMO 1 (raw SDK): same total wall time, but TTFT dropped from\n"
        "    seconds to hundreds of milliseconds. That is the entire UX win.\n"
        "    Total compute is identical; perception is transformed.\n\n"
        "  • DEMO 2 (LangChain): chain.stream() yields string chunks for an\n"
        "    LCEL chain. Works seamlessly with StrOutputParser. JsonOutputParser\n"
        "    has to buffer (partial JSON is invalid) — different streaming\n"
        "    contract.\n\n"
        "  • DEMO 3 (LangGraph): three stream modes for three jobs:\n"
        "      values   — full state after each node (debugging, persistence)\n"
        "      updates  — what each node changed (sidebar status indicators)\n"
        "      messages — token-by-token deltas (the live chat UI token feed)\n"
        "    Production chat UIs typically stream 'messages' to the browser\n"
        "    over SSE/WebSocket and 'updates' to the agent activity log.\n\n"
        "  • DEMO 4 (tool gotcha): agents stream in PASSES. The first stream\n"
        "    ends at the tool_use block. The second stream produces the\n"
        "    final answer. The pause between is where you render a\n"
        "    'thinking…' / 'calling get_weather…' indicator — otherwise the\n"
        "    user thinks the app froze.\n\n"
        "  • Production wiring: FastAPI endpoint returns StreamingResponse;\n"
        "    each yielded chunk is an SSE 'data:' line; browser EventSource\n"
        "    appends each delta to a <div> as it arrives. ~30 lines of code\n"
        "    on top of the patterns above."
    )
