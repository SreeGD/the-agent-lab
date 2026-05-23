# 08 — Chatbot Memory

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/08_chatbot_memory_ollama.py`.

> **Add one parameter to `create_react_agent` and the agent remembers across calls.** `checkpointer=MemorySaver()` + a `thread_id` is the entire abstraction.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01-07 (foundation)                                      ○ 13 system     ○ 16-19 Healthcare
                                                              design       ○ 20-22 Agriculture
  ▶ 08 CHATBOT MEMORY  ◄═══════ YOU ARE HERE               ○ 14 red-team   ○ 23-25 Finance
                                                           ○ 15 AI UX      ○ 26-28 Vidya Karana
  ○ 09 RAG                    (09_rag.py)                                      ○ 29-32 Family AI
  ○ 10 guardrails             (10_guardrails.py)
  ○ 11 production capstone    (11_production_chatbot.py)
  ○ 12 MCP                    (12_mcp_server.py, 12_mcp_client.py)
```

**Why this lesson now:** every agent you've built so far is **stateless** — each call starts from nothing. Real chatbots remember. This is the one missing piece between *"calculator that talks"* and *"chatbot."*

---

## Files involved

| File | Role |
|---|---|
| [`08_chatbot_memory_ollama.py`](../ollama/08_chatbot_memory_ollama.py) | 3-turn conversation in one thread + isolated second thread |

---

## What problem it solves

Stateless agents are useless for chat:

```
turn 1:  user → "My name is Sree."
         bot  → "Nice to meet you, Sree."
turn 2:  user → "What's my name?"
         bot  → "I don't have access to that information."   ← memory failure
```

Every `.invoke()` starts from a blank slate. The bot has no idea what happened in turn 1.

Memory closes the loop: **the agent stores the message history per `thread_id`** and replays it as context on the next turn. Same agent code, with memory now baked in.

---

## The analogy

A **doctor's chart**.

Without memory: every visit, you sit down with a new doctor who's never seen you. You re-explain your history each time.

With memory: the doctor pulls your chart before the appointment. The whole previous conversation is loaded. You pick up where you left off.

The `thread_id` is the patient ID. The `MemorySaver` is the filing cabinet. The agent automatically pulls the right chart based on the `thread_id` in the config.

---

## Visual

```
        ┌─ thread_id="alice" ──────────────────────────────────────┐
        │                                                          │
turn 1 ─┼─► agent.invoke({"messages": [...]}, config={thread="alice"})
        │   ├── checkpointer LOADS prior state (empty first time)  │
        │   ├── runs the agent                                     │
        │   └── SAVES new state under "alice"                      │
        │                                                          │
turn 2 ─┼─► agent.invoke({"messages": [new_msg]}, config={thread="alice"})
        │   ├── checkpointer LOADS turn 1's state                  │
        │   ├── appends new message                                │
        │   ├── runs with full history                             │
        │   └── SAVES updated state                                │
        └──────────────────────────────────────────────────────────┘

        ┌─ thread_id="bob" — FULLY ISOLATED ──────────────────────┐
        │  agent.invoke({...}, config={thread="bob"})              │
        │  → no idea who alice is                                 │
        └──────────────────────────────────────────────────────────┘
```

---

## The concept

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

agent = create_react_agent(
    model,
    tools=[...],
    checkpointer=MemorySaver(),    # ← ONE keyword
)

config = {"configurable": {"thread_id": "alice"}}
agent.invoke({"messages": [("user", "I'm Sree.")]}, config=config)
agent.invoke({"messages": [("user", "What's my name?")]}, config=config)
# → "Your name is Sree."
```

The `thread_id` is the conversation key. Different `thread_id` = a fresh conversation.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/08_chatbot_memory_ollama.py
```

Expected output (excerpt):

```
[alice turn 1] "Hi Sree! Great to meet you..."
[alice turn 2] "Your name is Sree, and you're a data scientist."
[alice turn 3] "47 + count_letters('Sree') = 47 + 4 = 51"   ← uses name from turn 1

[bob turn 1]   "I don't have access to any personal information..."   ← isolated

Total messages stored for alice: 10
```

Turn 3 is the showpiece: the agent uses a **fact from turn 1** (`name = Sree`) as input to a tool call (`count_letters("Sree")`). Multi-tool reasoning over remembered context.

---

## Walk-through

### What the checkpointer actually stores

After alice's 3-turn conversation:

```
 1. HumanMessage   "Hi! My name is Sree..."
 2. AIMessage      "Hi Sree! Great to meet you..."
 3. HumanMessage   "What's my name and what do I do?"
 4. AIMessage      "Sree, a data scientist."
 5. HumanMessage   "Add 42 and the number of letters in my name."
 6. AIMessage      <tool_calls: count_letters>   ← turn 3 starts a tool loop
 7. ToolMessage    <count_letters → 4>
 8. AIMessage      <tool_calls: add>
 9. ToolMessage    <add → 46>
10. AIMessage      "The result is 46."
```

Notice turn 3 produced **5 messages** (6–10), not 1, because the agent ran a multi-step tool loop. The checkpointer captured the whole loop.

### Token cost grows turn-over-turn

```
alice turn 1:  699 in
alice turn 2: 1477 in    ← carries turn 1 forward
alice turn 3: 1951 in    ← carries turns 1 + 2 forward
bob turn 1:    689 in    ← fresh thread, ~same as alice turn 1
```

With Ollama the model runs locally at no API cost, but token volume still affects latency. Keep threads trimmed for responsive chat.

---

## `thread_id` strategies in production

| Pattern | Example `thread_id` |
|---|---|
| Single-user assistant | `user.id` |
| Multi-conversation chatbot | `f"{user.id}:{conversation.id}"` |
| Topic-scoped agent | `f"{user.id}:topic:{topic_slug}"` |
| Anonymous session | `request.cookies['session_id']` |
| Shared brainstorm room | `room.id` (multiple users converge in one thread) |

---

## `MemorySaver` is dev-only — production swaps

| Checkpointer | When to use |
|---|---|
| `MemorySaver()` | Local dev, tests, single-process scripts. State dies with the process. |
| `SqliteSaver.from_conn_string("chats.db")` | Local persistence, single instance |
| `PostgresSaver(connection_string)` | Multi-instance, concurrent access, durable |
| Custom | Implement `BaseCheckpointSaver` for Redis, DynamoDB, your store |

Same `Checkpointer` interface across all of them — swap is one line.

---

## What memory does NOT do (saved for later)

- **Long-term semantic memory** ("Sree prefers concise answers" across many conversations) — different problem; needs a vector store
- **Cross-thread fact sharing** — by design, threads are isolated. For user-level facts shared across threads, store them outside the checkpointer and inject into the system prompt
- **Automatic summarization** of old turns to keep token cost flat — separate technique ("summary memory" or "buffer-window memory")

---

## Production patterns this unlocks

| Pattern | Example |
|---|---|
| Stateful chatbot | A SaaS support bot — thread per (user, conversation) |
| Onboarding flow | One thread per user; agent remembers progress across sessions |
| Multi-step task agent | "Plan + execute" workflow where each step adds to the thread |
| Pause + resume | User closes app; reopens; thread picks up exactly where it left off |
| Time-travel debugging | Rewind to an earlier checkpoint; replay with different decisions |

---

## Try this

1. **Continue Alice's conversation** — add `turn("alice", "What was the answer again?")`. Watch the model recall `46` without re-running tools.
2. **Compound math across remembered facts** — *"Multiply that by the number of letters in my role."* Three remembered facts + chained tools.
3. **Swap to SQLite** — `SqliteSaver.from_conn_string("chats.db")` replaces `MemorySaver()`. Same code; survives restarts.
4. **Observe latency** — with Ollama, notice how longer threads take more time due to increased context length being processed locally.

---

## Mental model in one line

> **A checkpointer is the storage layer for an agent's conversation. The `thread_id` is the key. Add a checkpointer = the agent remembers. Change the `thread_id` = a fresh conversation. That's the entire abstraction.**

---

## FAQ

**Q: What's the difference between `MemorySaver` and `SqliteSaver`?**

A: `MemorySaver` keeps state in a Python dict — dies when the process exits. `SqliteSaver` writes to a SQLite file, surviving restarts. `PostgresSaver` is for production (multi-instance, concurrent writes). Same interface; pick based on durability needs.

**Q: How do I clear a thread's memory?**

A: Two ways:
- Use a different `thread_id` (starts fresh)
- `agent.update_state(config, {"messages": []})` overwrites — but that's an advanced LangGraph operation

**Q: Can the same agent serve multiple users?**

A: Yes — use a different `thread_id` per user. The agent is stateless; the *checkpointer* holds per-thread state. One agent serves a million users by routing on `thread_id`.

**Q: What happens if turn N succeeds but the next turn fails before saving?**

A: `MemorySaver` saves at the end of each `.invoke()`. If `.invoke()` fails, the state isn't committed (the prior state remains). Real production checkpointers (Postgres) are transactional — partial states don't corrupt the DB.

**Q: How big can a thread get?**

A: Memory-bound until you cap it. Each AIMessage / ToolMessage is small (~hundreds of bytes), but a chatty conversation can hit thousands of messages and tens of thousands of tokens. **With Ollama, longer context means slower inference.** Mitigate with summary memory or sliding window.

**Q: Can I peek at a thread's saved state?**

A: Yes — `agent.get_state(config)` returns a snapshot:
```python
state = agent.get_state({"configurable": {"thread_id": "alice"}})
state.values["messages"]   # the saved message list
```

**Q: What's "time travel" in LangGraph?**

A: Every state save creates a checkpoint with a timestamp. You can `agent.get_state_history(config)` and rewind to any prior checkpoint, then continue from there. Useful for debugging "what if I changed turn 3?" Covered in custom-graph lessons.

**Q: Does memory work with `create_react_agent` only, or also custom graphs?**

A: Both. Custom `StateGraph`s also accept a `checkpointer=` argument with the same semantics. `create_react_agent` is just a prebuilt graph that happens to use it.

**Q: Is there a way to share state across threads but isolate user data?**

A: Not in the checkpointer itself. Put user-level facts (preferences, profile) outside the checkpointer (DB, vector store) and inject them into the system prompt at session start. That gives you the **shared user facts + per-thread conversation** pattern.

---

## Related

- **Previous:** [07 — Output parsers](07-output-parsers.md)
- **Next:** [09 — RAG](09-rag.md)
- **Production composition:** [11 — Production capstone](../11-production-capstone.md)
