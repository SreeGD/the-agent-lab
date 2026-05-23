from datetime import datetime

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
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


def print_usage(messages):
    """Print per-call and total token usage for every AIMessage in `messages`."""
    print("\n=== token usage ===")
    total_in = total_out = total_cache_read = 0
    call = 0
    for m in messages:
        if not isinstance(m, AIMessage) or not m.usage_metadata:
            continue
        call += 1
        u = m.usage_metadata
        in_tok = u.get("input_tokens", 0)
        out_tok = u.get("output_tokens", 0)
        details = u.get("input_token_details", {}) or {}
        cache_read = details.get("cache_read", 0)
        total_in += in_tok
        total_out += out_tok
        total_cache_read += cache_read
        line = f"call {call}: {in_tok:>5} in + {out_tok:>4} out = {in_tok + out_tok:>5} total"
        if cache_read:
            line += f"   (cache read={cache_read})"
        print(line)
    print(f"{'-' * 48}")
    print(f"total:  {total_in:>5} in + {total_out:>4} out = {total_in + total_out:>5} total")
    if total_cache_read:
        print(f"        cache read={total_cache_read}")


# Pass the plain model — create_react_agent calls .bind_tools() internally.
model = ChatOpenAI(model="gpt-4o", temperature=0)
agent = create_react_agent(model, tools=[add, get_current_time])

question = "What's 47 plus 158, and what time is it right now? Tell me both."

print("=== invoke (single result) ===")
result = agent.invoke({"messages": [("user", question)]})
print(result["messages"][-1].content)
print_usage(result["messages"])

print("\n=== stream (every step) ===")
final_state = None
for event in agent.stream(
    {"messages": [("user", question)]},
    stream_mode="values",
):
    event["messages"][-1].pretty_print()
    final_state = event
print_usage(final_state["messages"])
