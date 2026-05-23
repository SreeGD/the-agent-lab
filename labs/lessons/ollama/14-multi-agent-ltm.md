# 14 — Multi-Agent + Long-term Memory (Session 3)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/14_multi_ollama.py`.

> **Two patterns that take the agent loop to the next level.** Multi-agent: a supervisor orchestrates specialists for different sub-tasks. Long-term memory: facts about the user persist across all conversations, not just within one thread.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: Agentic Patterns
                                                             ✓ Session 1: MCP (lesson 12)
                                                             ✓ Session 2: Reflection + PE (lesson 13)
                                                             ▶ Session 3: MULTI-AGENT + LTM  ◄ HERE
                                                           Track B: Workflow & Skill
                                                             ○ SDD, Vibe, Skills
                                                           Track C-F (alt arch, data, graphs, prod)
                                                           Phase 3: vertical deep dives
```

**Why this lesson now:** Sessions 1+2 covered single-agent patterns at depth. Real production systems use **specialists coordinated by a supervisor** AND **memory that survives across sessions**. Both are essential and pair naturally — by the end of this lesson you have the full agentic AI taxonomy.

---

## Files involved

| File | Role |
|---|---|
| [`14_multi_ollama.py`](../ollama/14_multi_ollama.py) | Supervisor + 3 specialist agents (researcher / writer / reviewer) |
| [`14_long_term_memory.py`](../14_long_term_memory.py) | Agent with conversation memory + vector-stored user facts across sessions |

---

## What problem it solves

### The multi-agent problem

Single-agent ReAct works for simple tasks but struggles when:
- The task has fundamentally different sub-skills (research vs writing vs reviewing)
- You want to use **different models per role** (small + fast for routing; big + smart for execution)
- You want each role to have its own system prompt and tools

Stuffing everything into one system prompt makes the agent confused. **Multi-agent splits the system prompt across specialists**, each tuned for its role.

### The long-term memory problem

`MemorySaver` (lesson 08) gives you **per-thread** memory — the agent remembers *this* conversation. But:
- User starts a new chat tomorrow → memory gone
- User asks across two different topics → each thread is isolated
- Persistent facts about the user ("data scientist", "prefers concise answers") need to live somewhere durable

**Long-term memory is a vector store of facts about the user, separate from thread state.** The agent retrieves relevant facts at the start of each conversation and saves new ones as the user shares them.

---

## The analogy

**Multi-agent = a newsroom.**

The editor (supervisor) doesn't write stories. They route: send the reporter (researcher) to dig up facts, hand the brief to a feature writer (writer), pass the draft to a copy editor (reviewer), then publish. Each role has different skills and gets focused instructions.

**Long-term memory = the doctor's chart.**

Short-term memory is the conversation you have during today's appointment. Long-term memory is the file the doctor reads *before* the appointment — your medical history, allergies, ongoing prescriptions. Different appointment, same chart.

---

## Visual — Multi-agent

```
                  ┌──────────────────────┐
                  │     SUPERVISOR       │  ReAct agent
                  │  (calls specialists  │  - decides who to call
                  │   like tools)        │  - composes their outputs
                  └──────┬───────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌─────────┐ ┌────────┐ ┌──────────┐
        │RESEARCHER│ │ WRITER │ │ REVIEWER │
        │  - tools │ │ no     │ │ no tools │
        │    [RAG] │ │ tools  │ │          │
        └─────────┘ └────────┘ └──────────┘
        
   Each specialist is a normal create_react_agent.
   Each gets wrapped in @tool so the supervisor can call it.
   Same primitive, one level of indirection.
```

## Visual — Long-term Memory

```
   Two memory layers in one agent:

   SHORT-term (per-thread)              LONG-term (per-user)
   ────────────────────────             ──────────────────────────
   MemorySaver / SqliteSaver            Vector store of "user facts"
   keyed by thread_id                   keyed by user_id, filtered semantically
   conversation history                 facts about the user
   lost when thread changes             persists across all sessions

   thread:session-1                     user_id:sree
     "Hi I'm Sree..."         ─────►    - "User's name is Sree"
     "What's caching?"                  - "User is a data scientist"
                                        - "User prefers concise answers"
                                        - "User is on a LangChain tutorial"

   thread:session-2 (new!)              user_id:sree  (unchanged)
     "What do you know          ◄─────  (agent calls recall_facts_about)
      about me?"
```

The agent has two tools:
- `remember_fact(user_id, fact)` — writes to LTM
- `recall_facts_about(user_id, query)` — reads from LTM (filtered + semantic)

---

## The concept — Multi-agent

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

# Each specialist is a normal create_react_agent
researcher = create_react_agent(model, tools=[retrieve_docs], prompt=SystemMessage("You are a researcher..."))
writer     = create_react_agent(model, tools=[],               prompt=SystemMessage("You are a writer..."))
reviewer   = create_react_agent(model, tools=[],               prompt=SystemMessage("You are a reviewer..."))

# Wrap each as a tool the supervisor can call
@tool
def call_researcher(query: str) -> str:
    """Researcher: gathers facts. Use FIRST."""
    return researcher.invoke({"messages": [("user", query)]})["messages"][-1].content

@tool
def call_writer(brief: str) -> str:
    """Writer: drafts from a brief."""
    return writer.invoke({"messages": [("user", brief)]})["messages"][-1].content

@tool
def call_reviewer(draft_and_task: str) -> str:
    """Reviewer: APPROVED or revised draft."""
    return reviewer.invoke({"messages": [("user", draft_and_task)]})["messages"][-1].content

# Supervisor: ReAct agent over these "tools"
supervisor = create_react_agent(
    model,
    tools=[call_researcher, call_writer, call_reviewer],
    prompt=SystemMessage("You orchestrate the workflow..."),
)
```

**Specialists are agents, wrapped as tools, called by another agent.** Same primitive (`create_react_agent`) at every level. One level of indirection.

## The concept — Long-term Memory

```python
# Vector store of user facts — lives outside MemorySaver
ltm_store = InMemoryVectorStore(embeddings)

@tool
def remember_fact(user_id: str, fact: str) -> str:
    """Save a fact about the user."""
    doc = Document(page_content=fact, metadata={"user_id": user_id, "timestamp": ...})
    ltm_store.add_documents([doc])
    return f"Saved."

@tool
def recall_facts_about(user_id: str, query: str) -> str:
    """Retrieve relevant facts about the user."""
    hits = ltm_store.similarity_search(query, k=5,
        filter=lambda doc: doc.metadata.get("user_id") == user_id)
    return "\n".join(f"- {d.page_content}" for d in hits)

# Agent has BOTH layers: MemorySaver (short-term) + LTM tools (long-term)
agent = create_react_agent(
    model,
    tools=[remember_fact, recall_facts_about],
    checkpointer=MemorySaver(),
    prompt=SystemMessage("Recall facts at start; remember new facts; personalize answers..."),
)
```

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/14_multi_ollama.py
python 14_long_term_memory.py
```

`14_multi_ollama.py` writes a blog post about prompt caching via supervisor routing. You'll see the supervisor's tool calls printed as it routes: `[supervisor → researcher] ... → writer ... → reviewer ...`.

`14_long_term_memory.py` runs 2 sessions for user "sree". Session 1 facts get saved to LTM. Session 2 (new `thread_id`) starts fresh on short-term memory but recalls Sree's facts from LTM.

---

## Walk-through

### Multi-agent: cost shape

```
supervisor call 1: decide → call_researcher                       (1 LLM call)
  researcher: retrieve_docs → respond                             (2 LLM calls)
supervisor call 2: with researcher's output → call_writer          (1 LLM call)
  writer: respond                                                 (1 LLM call)
supervisor call 3: with writer's output → call_reviewer            (1 LLM call)
  reviewer: respond                                               (1 LLM call)
supervisor call 4: final answer                                   (1 LLM call)
─────────────────────────────────────────────────────────────────
TOTAL: ~8 LLM calls for a single blog post
```

Compare to single-agent on the same task: ~3-4 calls.

**The trade-off:** multi-agent is 2-3× more expensive in inference time but produces noticeably better output for tasks with distinct sub-skills. Use it when the task genuinely benefits from specialization.

### LTM vs MemorySaver — the memory hierarchy

| Layer | Scope | Backed by | Use for |
|---|---|---|---|
| **Short-term** | One thread (one conversation) | `MemorySaver` / `SqliteSaver` / `PostgresSaver` | Conversation history within a session |
| **Long-term semantic** | One user, across all threads | Vector store | Facts about the user (name, role, preferences, ongoing context) |
| **Long-term episodic** | Specific past events | Vector store + timestamps | "We discussed X on 2026-03-15" |
| **Shared/global** | All users | Vector store / RAG | Public knowledge (your docs corpus) |

`14_multi_ollama.py` uses none (single-shot task). `14_long_term_memory.py` uses short-term + long-term semantic. Production chatbots use all four.

### Episodic Memory — the third memory type

The LTM in `14_long_term_memory.py` stores **semantic** facts: *"Sree is a data scientist."* These are timeless — they don't have a "when."

**Episodic memory** stores **events**: *"On 2026-03-15 at 14:32, Sree asked about prompt caching. Outcome: satisfied with the answer."* Events have a timestamp, a specific topic, and often an outcome.

#### Why episodic memory matters separately from semantic LTM

| Use case | Semantic LTM | Episodic memory |
|---|---|---|
| "What does the user prefer?" | ✓ "User prefers concise answers" | ✗ |
| "When did we last discuss caching?" | ✗ | ✓ "2026-03-15, you explained KV cache and they were satisfied" |
| "Has the user asked this before?" | ✗ | ✓ Match query against past episodes |
| "What did we promise the user last time?" | ✗ | ✓ Retrieve last conversation's commitments |

The two are complementary. **Semantic = who the user is. Episodic = what we've done together.**

### When to use multi-agent vs single-agent

| Sign that multi-agent helps | Sign that single-agent is enough |
|---|---|
| Task has distinct sub-skills (research vs write vs review) | Task is one coherent skill |
| You want different models per role | One model handles it all |
| Each role needs its own system prompt (very different personas) | One system prompt covers it |
| Output quality jumps with specialization | Single agent already does well |
| Inference time cost is acceptable (2-3× single-agent) | Latency-sensitive |

**Don't reach for multi-agent until you've maxed out single-agent.** Most "multi-agent failures" are actually "complex single-agent that should have been simpler."

---

## Production patterns this unlocks

| Pattern | Real use case |
|---|---|
| Customer support routing | Supervisor → billing-agent / tech-agent / sales-agent |
| Multi-modal research | Supervisor → web-search-agent / pdf-agent / image-analysis-agent |
| Coding workflow | Supervisor → scaffold-agent / implement-agent / test-agent / docs-agent |
| Compliance review | Supervisor → drafter / compliance-checker / legal-reviewer |
| User-facing chatbot with LTM | Conversation memory (thread) + user preferences (LTM) + RAG over your docs |
| Personalization | Track user role/style/projects in LTM; tailor every response |

---

## Try this

1. **Add a 4th specialist** — e.g., a fact-checker who searches the web. Add it as another `@tool` and update the supervisor's system prompt. No other changes needed.
2. **Make the supervisor use different models per specialist** — use `ChatOllama(model="llama3.2:3b")` for the routing supervisor to reduce latency.
3. **Add LTM to `11_production_chatbot_ollama.py`** — the capstone has short-term memory but no LTM. Add the two tools and watch the chatbot remember preferences across sessions.
4. **Inspect the LTM after a long conversation** — print all facts saved: `ltm_store.similarity_search("", k=100, filter=lambda d: d.metadata.get("user_id") == "sree")`. See what the agent decided to remember.
5. **Add LTM fact dedup** — if the agent tries to save a fact that's already in LTM, skip the write. Hint: search first, only save if no high-similarity hit.

---

## Mental model in one line

> **Multi-agent = a supervisor ReAct agent whose tools happen to be other agents. Long-term memory = a vector store of user facts, separate from thread state. Together they cover almost every production agent topology.**

---

## FAQ

**Q: Is multi-agent always better than single-agent?**

A: No. **Multi-agent is 2-3× more expensive in inference time and harder to debug.** Use it only when the task has genuinely distinct sub-skills, or when you want to use different models per role (the latency-optimization angle). For 70% of production agents, well-prompted single-agent is enough.

**Q: How is multi-agent different from Plan-and-Execute?**

A: Plan-and-Execute (lesson 13) decomposes ONE agent's work into ordered steps. Multi-agent uses DIFFERENT agents — each with its own system prompt, tools, and (often) model. PE = decomposition within an agent. Multi-agent = orchestration across agents.

**Q: Why not just put all the system prompts into one big one?**

A: Because the model "spreads its attention" across the whole system prompt. With one big prompt, "you are a researcher AND a writer AND a reviewer" the model often half-does all three. With separate specialists, each call is focused: ONE system prompt at a time. Cleaner, more reliable.

**Q: How does the supervisor know when to stop?**

A: Same as any ReAct agent — when it produces an `AIMessage` with no `tool_calls`, the loop exits. The supervisor's system prompt instructs it: "after the reviewer approves, output the final draft." It decides when its work is done.

**Q: Can specialists call each other directly (swarm pattern)?**

A: Yes. In a **swarm**, specialists can hand off to other specialists without going through the supervisor. Useful when the path between specialists is data-dependent. The supervisor pattern is simpler and more common; swarm is for advanced cases.

**Q: What's the difference between LTM and RAG?**

A: Both use vector stores. The difference is **what's stored and why**:
- **RAG** stores **documents** for answering domain questions. Shared across users.
- **LTM** stores **facts about a specific user** for personalization. Per-user.

You can have both in the same chatbot — `11_production_chatbot_ollama.py` uses RAG; LTM would add per-user personalization on top.

**Q: How do I know when to save a fact to LTM?**

A: Heuristics in the system prompt:
- The user shares biographical info (name, role, location)
- The user states a preference ("I prefer X")
- The user mentions ongoing context ("I'm working on Y")
- The user explicitly asks to be remembered

Avoid saving every utterance — LTM fills up with noise. Save only "facts about the user, not specific to this conversation."

**Q: How do I handle conflicting facts?**

A: Two options:
- **Append + filter** — always add new facts; when retrieving, sort by timestamp and prefer recent
- **Update in place** — search for similar facts first; if found and conflicting, update instead of append

For demo simplicity, `14_long_term_memory.py` does append. Production usually does update-in-place.

**Q: Is LTM safe for sensitive data?**

A: It's a database. Same security concerns: encryption at rest, access control, GDPR compliance, right-to-deletion. **Never store passwords, payment info, or other secrets in LTM.** For PII, encrypt before storing or use a dedicated PII vault.

---

## Related

- **Previous:** [13 — Reflection + Plan-and-Execute](13-reflection-plan-execute.md)
- **Next:** Session 4 — Spec-Driven Development (Track B)
- **Builds on:** [03 — Agent tool loop](03-agent-tool-loop.md), [08 — Chatbot memory](08-chatbot-memory.md), [09 — RAG](09-rag.md)
- **Pattern reference:** [reference-agentic-patterns](../reference-agentic-patterns.md) (Supervisor + Swarm entries)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 3 of 32
