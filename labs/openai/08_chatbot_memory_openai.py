"""A stateful chatbot agent — same as agent_lg.py, with memory added.

One new keyword turns the stateless agent into a real chatbot:
  checkpointer=MemorySaver()

State (the full message history) is keyed by thread_id, so multiple
conversations stay isolated.
"""

from datetime import datetime

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

load_dotenv()


@tool
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b


@tool
def get_current_time() -> str:
    """Return the current local time as an ISO 8601 string."""
    return datetime.now().isoformat(timespec="seconds")


@tool
def count_letters(text: str) -> int:
    """Return the number of letters (ignoring spaces/punctuation) in `text`."""
    return sum(1 for ch in text if ch.isalpha())


tools = [add, get_current_time, count_letters]


model = ChatOpenAI(model="gpt-4o", temperature=0)
agent = create_react_agent(
    model,
    tools=tools,
    checkpointer=MemorySaver(),   # <-- the one keyword that adds memory
)


def turn(thread_id: str, user_text: str) -> dict:
    """Run one user message, return the resulting state and usage info."""
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke({"messages": [("user", user_text)]}, config=config)
    last_ai = result["messages"][-1]
    # Sum token usage across all AIMessages produced THIS turn (may be >1 with tools)
    ai_msgs_this_turn = [
        m for m in result["messages"]
        if isinstance(m, AIMessage) and m.usage_metadata
    ]
    in_tok = sum(m.usage_metadata.get("input_tokens", 0) for m in ai_msgs_this_turn[-2:])
    out_tok = sum(m.usage_metadata.get("output_tokens", 0) for m in ai_msgs_this_turn[-2:])
    return {
        "answer": last_ai.content,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "messages_total": len(result["messages"]),
    }


def pretty(label: str, r: dict) -> None:
    print(f"\n[{label}]")
    print(f"  agent: {r['answer']}")
    print(
        f"  (tokens in={r['input_tokens']:>5}  out={r['output_tokens']:>4}  "
        f"total messages in state: {r['messages_total']})"
    )


# ==========================================================================
# Conversation 1 — thread "alice"
# ==========================================================================

print("=" * 68)
print('THREAD "alice" — three turns')
print("=" * 68)

pretty("alice turn 1", turn("alice", "Hi! My name is Sree. I'm a data scientist."))
pretty("alice turn 2", turn("alice", "What's my name and what do I do?"))
pretty(
    "alice turn 3",
    turn("alice", "Cool. Now add 42 and the number of letters in my name."),
)


# ==========================================================================
# Conversation 2 — thread "bob" (fully isolated from alice)
# ==========================================================================

print("\n" + "=" * 68)
print('THREAD "bob" — same questions, different thread → no memory of alice')
print("=" * 68)

pretty("bob turn 1", turn("bob", "What's my name?"))


# ==========================================================================
# Peek at what the checkpointer actually stored
# ==========================================================================

print("\n" + "=" * 68)
print('Inspecting saved state for thread "alice"')
print("=" * 68)

state = agent.get_state({"configurable": {"thread_id": "alice"}})
messages = state.values["messages"]

print(f"\nTotal messages stored: {len(messages)}")
print("Message timeline (type — preview):")
for i, m in enumerate(messages, start=1):
    kind = type(m).__name__
    if isinstance(m, HumanMessage):
        preview = m.content[:60]
    elif isinstance(m, AIMessage):
        if m.tool_calls:
            preview = f"<tool_calls: {[tc['name'] for tc in m.tool_calls]}>"
        else:
            preview = (m.content or "")[:60]
    elif isinstance(m, ToolMessage):
        preview = f"<{m.name} → {str(m.content)[:30]}>"
    else:
        preview = "?"
    print(f"  {i:>2}. {kind:<14} {preview}")

print(
    "\n(This whole list is re-sent to the LLM on every new turn — input cost grows turn-over-turn.\n"
    " Pair memory with prompt caching for production chatbots.)"
)
