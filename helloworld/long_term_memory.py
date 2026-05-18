"""Long-term memory — facts about a user that persist across sessions.

Two memory layers in one agent:
  - SHORT-term (per-thread)   ──► MemorySaver  (lesson 08 — conversation history)
  - LONG-term  (per-user)     ──► Vector store of user facts

The vector store is keyed semantically (the agent retrieves relevant facts
based on the current question, not all facts ever). New facts get written
when the user shares biographical/preference/ongoing-context info.
"""

import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

load_dotenv()


# =====================================================================
# Long-term memory store — a vector store keyed by semantic similarity,
# filtered by user_id at query time. Lives outside the conversation
# (MemorySaver) state, so it survives even when a new thread starts.
# =====================================================================

print("[long_term_memory] Loading embedding model...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
ltm_store = InMemoryVectorStore(embeddings)
print("[long_term_memory] LTM ready.\n")


# =====================================================================
# Two LTM tools the agent can call: remember + recall
# =====================================================================

@tool
def remember_fact(user_id: str, fact: str) -> str:
    """Save a fact about a user to long-term memory.

    Use this when the user shares any of:
      - Biographical info (name, role, location)
      - Preferences (writing style, tone, depth)
      - Ongoing context (current project, ongoing task, what they're learning)

    Keep facts SHORT and SELF-CONTAINED. One sentence per fact.
    Example facts:
      - "User's name is Sree."
      - "User is a data scientist."
      - "User prefers concise answers, no filler."
      - "User is working on a LangChain tutorial."
    """
    doc = Document(
        page_content=fact,
        metadata={"user_id": user_id, "timestamp": datetime.now().isoformat()},
    )
    ltm_store.add_documents([doc])
    print(f"  [LTM ← remember] {user_id}: {fact}")
    return f"Saved fact about {user_id}."


@tool
def recall_facts_about(user_id: str, query: str) -> str:
    """Retrieve relevant facts about a user from long-term memory.

    Use this at the START of any new conversation and any time you need
    context about the user. The query should describe what kind of context
    you're looking for (e.g., "user profile", "user's role", "preferences",
    or the current topic of conversation to find related facts).
    """
    hits = ltm_store.similarity_search(
        query,
        k=5,
        filter=lambda doc: doc.metadata.get("user_id") == user_id,
    )
    if not hits:
        result = f"No facts found about {user_id} matching '{query}'."
    else:
        result = "Known facts about user:\n" + "\n".join(
            f"  - {d.page_content}" for d in hits
        )
    print(f"  [LTM → recall ] {user_id} q='{query}': {len(hits)} hit(s)")
    return result


# =====================================================================
# The agent — short-term memory (MemorySaver) + long-term memory (tools)
# =====================================================================

model = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)

SYSTEM_PROMPT = """You are a personal assistant. The user's id is 'sree'.

Memory rules — follow these for every conversation:

1. At the START of every new conversation, call recall_facts_about(user_id='sree',
   query='user profile') to load context about the user.

2. When the user shares biographical info, preferences, current projects, or
   ongoing context, call remember_fact(user_id='sree', fact=...) to save it.
   Save each distinct fact separately (not one giant blob).

3. Use what you remember to personalize your answers — match the user's stated
   style preferences, reference their role/projects where relevant.

4. Be concise. Don't over-explain unless asked for depth."""


agent = create_react_agent(
    model,
    tools=[remember_fact, recall_facts_about],
    checkpointer=MemorySaver(),
    prompt=SystemMessage(SYSTEM_PROMPT),
)


# =====================================================================
# Demo — two sessions for the same user, different threads
# =====================================================================

def count_tokens(messages: list, since: int = 0) -> tuple[int, int]:
    """Sum (input, output) tokens across AIMessages starting at index `since`."""
    in_tok = out_tok = 0
    for m in messages[since:]:
        if isinstance(m, AIMessage) and m.usage_metadata:
            in_tok += m.usage_metadata.get("input_tokens", 0)
            out_tok += m.usage_metadata.get("output_tokens", 0)
    return in_tok, out_tok


def turn(thread_id: str, user_msg: str) -> str:
    """Run one user message, return the assistant's answer."""
    config = {"configurable": {"thread_id": thread_id}}
    state_before = agent.get_state(config)
    n_before = len(state_before.values.get("messages", [])) if state_before.values else 0

    result = agent.invoke({"messages": [("user", user_msg)]}, config=config)
    answer = result["messages"][-1].content

    in_tok, out_tok = count_tokens(result["messages"], since=n_before)
    print(f"  [tokens] in={in_tok}  out={out_tok}")
    return answer


if __name__ == "__main__":
    print("=" * 70)
    print("LONG-TERM MEMORY agent — facts persist across sessions")
    print("=" * 70)

    # ---------- SESSION 1: user introduces themselves ----------
    print("\n" + "─" * 70)
    print("SESSION 1 (thread: 'session-1')")
    print("─" * 70)

    print("\n→ user: Hi! I'm Sree, a data scientist working on a LangChain tutorial.\n"
          "        I prefer concise answers, no filler.")
    ans = turn("session-1", "Hi! I'm Sree, a data scientist working on a LangChain "
                            "tutorial. I prefer concise answers, no filler.")
    print(f"agent: {ans[:300]}...")

    print("\n→ user: What's prompt caching, briefly?")
    ans = turn("session-1", "What's prompt caching, briefly?")
    print(f"agent: {ans[:300]}...")

    # ---------- SESSION 2: NEW thread — short-term memory is reset, LTM persists ----------
    print("\n" + "─" * 70)
    print("SESSION 2 (thread: 'session-2' — NEW conversation, LTM should still know Sree)")
    print("─" * 70)

    print("\n→ user: What do you know about me?")
    ans = turn("session-2", "What do you know about me?")
    print(f"agent: {ans[:400]}...")

    print("\n→ user: Explain RAG.")
    ans = turn("session-2", "Explain RAG.")
    print(f"agent: {ans[:400]}...")

    # ---------- Summary ----------
    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  Session 1: agent called remember_fact() to save:\n"
        "    - name = Sree\n"
        "    - role = data scientist\n"
        "    - context = working on a LangChain tutorial\n"
        "    - preference = concise answers, no filler\n"
        "\n"
        "  Session 2 (NEW thread, short-term memory empty):\n"
        "    - agent called recall_facts_about() to load Sree's facts from LTM\n"
        "    - cross-session continuity achieved via the vector store, not via\n"
        "      MemorySaver (which is per-thread)\n"
        "\n"
        "  This is the memory HIERARCHY:\n"
        "    short-term (thread)  = MemorySaver — lost when thread changes\n"
        "    long-term  (user)    = vector store — survives across threads/sessions\n"
    )
