from datetime import datetime

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
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

model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(tools)

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
