# 11 — Production Capstone

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/11_production_chatbot_ollama.py`.

> **Every primitive from the course composed into one architecture.** RAG (via `retrieve_docs` tool) + memory (`MemorySaver`) + guardrails — running in one chatbot, 4-turn demo, per-turn metrics.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01-10 (foundation)                                      ○ 13 system     ○ 16-19 Healthcare
                                                              design       ○ 20-22 Agriculture
  ▶ 11 PRODUCTION CAPSTONE  ◄═══════ YOU ARE HERE          ○ 14 red-team   ○ 23-25 Finance
                                                           ○ 15 AI UX      ○ 26-28 Vidya Karana
  ○ 12 MCP                    (12_mcp_server.py, 12_mcp_client.py)                ○ 29-32 Family AI
```

**Why this lesson now:** the synthesis lesson. Every prior lesson taught one primitive in isolation. This one demonstrates **all of them composed in one app** — the architecture used by 90% of production AI chatbots.

---

## Files involved

| File | Role |
|---|---|
| [`11_production_chatbot_ollama.py`](../ollama/11_production_chatbot_ollama.py) | The capstone. ~350 lines. RAG + memory + guardrails. |

---

## What problem it solves

You've learned the pieces:
- A model wrapper (lesson 01)
- LCEL composition (02)
- Agents with tools (03)
- Structured output (05)
- Parallel chains (06)
- Parsers (07)
- Memory (08)
- RAG (09)
- Guardrails (10)

In isolation, each is interesting. **Combined, they're a shippable product.** The capstone shows you how the pieces fit together into one architecture and why composition is the entire point of LangChain.

The demo answers: *"What does a real, production-grade AI chatbot actually look like?"*

---

## The analogy

A **restaurant kitchen at service**.

Each previous lesson was a station: the grill (LLM), the prep cook (RAG), the waiter (memory), the food safety inspector (guardrails). A station alone is just a station. The full kitchen running at service — with the expediter calling tickets, ingredients flowing between stations, the inspector spot-checking — is the product.

The capstone is service night, all stations active.

---

## Visual

```
                ┌─────────────── 11_production_chatbot_ollama.py ────────────────┐
                │                                                       │
  user input    │  INPUT GUARDS  [PII regex | Injection regex | OnTopic]│
       │        │       │ pass                                          │
       └───────►│       ▼                                               │
                │   create_react_agent                                  │
                │      ├── SystemMessage (long, consistent)            │
                │      ├── checkpointer=MemorySaver()                   │   ← memory
                │      └── tools=[retrieve_docs, ...]                   │   ← RAG-as-tool
                │              │                                        │
                │              ▼ (may loop: model ↔ tool ↔ model)       │
                │            answer                                     │
                │              │                                        │
                │              ▼                                        │
                │  OUTPUT GUARDS [PII output | Faithfulness]            │
                │       │ pass                                          │
                └───────┼───────────────────────────────────────────────┘
                        ▼
                   user sees answer (or polite refusal)

  Behind `retrieve_docs(query)`:
     ┌────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐   ┌──────────┐
     │ Loader │──►│ Splitter │──►│ Embedder │──►│Vector Store│──►│Retriever │
     └────────┘   └──────────┘   └──────────┘   └────────────┘   └──────────┘
     (one-time indexing at startup)              (per-query similarity search)
```

---

## The concept

```python
from langchain_ollama import ChatOllama

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

agent = create_react_agent(
    model,
    tools=[retrieve_docs],         # RAG is exposed as a tool the agent can call
    checkpointer=MemorySaver(),    # memory per thread_id
    prompt=system_message,         # long SystemMessage
)

def safe_chat(user_input, thread_id):
    run_input_guardrails(user_input)        # PII | Injection | OnTopic
    result = agent.invoke(
        {"messages": [("user", user_input)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    answer = result["messages"][-1].content
    run_output_guardrails(retrieved_context, answer)   # PII | Faithfulness
    return answer
```

**No new primitives.** Every piece is something you already built. The lesson is composition.

---

## Key design choices

| Choice | Why |
|---|---|
| **RAG as a tool**, not a hard-coded step | Agent decides when retrieval is needed. Skip it for greetings, use it for substantive questions. Matches how modern production chatbots work. |
| **Consistent system prompt** (~1500 tokens) | Persona + RAG-usage rules + style + constraints. |
| **`MemorySaver` keyed by `thread_id`** | Each conversation isolated. |
| **Guardrails wrap the agent call** | Pre + post middleware, same shape as [lesson 10](10-guardrails.md). |
| **Faithfulness vs `retrieve_docs` ToolMessages** | When the agent retrieved, faithfulness checks against retrieved chunks. When it didn't retrieve (greetings), it's skipped. |

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/11_production_chatbot_ollama.py
```

A 4-turn conversation, one `thread_id`, exercises every layer:

```
turn 1: "Hi! I'm Sree, a data scientist."
        → all guards pass, no retrieval needed (just memory)

turn 2: "How does prompt caching actually work?"
        → all guards pass, agent calls retrieve_docs
        → grounded answer with citations
        → faithfulness check runs (passes)

turn 3: "Cool — could you summarize that for me, as a data scientist?"
        → all guards pass, no retrieval (uses memory + prior context)

turn 4: "My SSN is 123-45-6789, what about RAG?"
        → input PII guard FIRES
        → refused, agent never called (~1 ms, no inference cost)
```

Expected per-turn output includes the guard verdicts, tool calls, answer preview, and timing. A final summary shows total tokens processed and time taken.

---

## Walk-through

### Token economics with Ollama

Unlike cloud providers, Ollama has no per-token cost — it runs locally. However, longer contexts require more local compute. Keeping your system prompt stable and your context windows lean still matters for latency:

```
turn 1:  1966 tokens in   →  fast (short context)
turn 2:  7913 tokens in   →  slower (chunks added to context)
turn 3:  3625 tokens in   →  medium (prior summary, no new chunks)
turn 4:     0 tokens sent →  refused at guardrail, no inference
```

At scale: with many concurrent users and a local GPU, context length directly impacts throughput. Design your system prompts for conciseness.

### Where each lesson shows up

| In the capstone | From lesson |
|---|---|
| `ChatOllama(...)` | 01 |
| `prompt | model | parser` (in guard chains) | 02 |
| Tools, `@tool`, `create_react_agent` | 03 |
| `with_structured_output` (in guard judges) | 05 |
| `parallel.batch` patterns (RAG retrieval) | 06 |
| `StrOutputParser` | 07 |
| `MemorySaver`, `thread_id` | 08 |
| Loader → splitter → embedder → vector store → retriever | 09 |
| Input + output guardrail wrappers | 10 |

**10 of the previous lessons live in this one file.** That's the synthesis.

---

## Production patterns this unlocks

The capstone IS the pattern. Other variants:

| Variant | What changes |
|---|---|
| Multi-tenant SaaS chatbot | `thread_id = f"{tenant_id}:{user_id}:{conversation_id}"` |
| Persistent across restarts | Swap `MemorySaver` → `PostgresSaver` |
| Real vector DB | Swap `InMemoryVectorStore` → FAISS / Chroma / pgvector / Pinecone |
| Multi-channel | Add WhatsApp / Slack / web frontends, all calling `safe_chat()` |
| Multi-domain | Add specialist agents (multi-agent), router supervisor |

---

## Try this

1. **Open `CURRICULUM.csv`, mark Status = "Done" for Sessions 1-12** — you've completed Phase 1.
2. **Try a turn 5** — *"What's my name?"* in the same thread. Watch the agent recall from memory.
3. **Add a faithfulness threshold** — change the binary judge to a 0-10 score; refuse below 7.
4. **Swap guard model** — use `ChatOllama(model="llama3.2:3b")` for guards and `ChatOllama(model="llama3.2")` for the main agent. Watch latency drop for guardrail checks.
5. **Add WhatsApp** — wrap `safe_chat()` in a WhatsApp webhook handler. See the Family AI Agent track (Phase 3) for the pattern.

---

## Mental model in one line

> **Production AI architectures aren't novel primitives — they're disciplined combinations of well-understood patterns. The capstone is RAG + memory + guardrails composed. Every layer was lesson; their integration is the product.**

---

## FAQ

**Q: Why is RAG a *tool* here instead of hardcoded into every turn?**

A: Because not every turn needs retrieval. Greetings, follow-ups, simple math don't. **The agent decides** when to call `retrieve_docs` — much like a human assistant decides when to check the knowledge base vs. answer from memory. Hardcoded retrieval would waste inference time.

**Q: How do I keep latency consistent across turns?**

A: Three rules for local Ollama:
- **Consistent system prompt length** — the system prompt is processed fresh each turn
- **Cap context window growth** — implement sliding window or summarization for long conversations
- **Avoid huge chunks in context** — prefer smaller, more targeted retrieval results

**Q: How is the on-topic LLM-judge cost?**

A: With Ollama there are no API costs. Local inference time is ~600ms for a small check. For guardrail efficiency, use a smaller model (`llama3.2:3b`) for classification tasks.

**Q: What's the recursion limit for the agent?**

A: `create_react_agent` defaults to 25. Override with `agent.invoke(..., {"recursion_limit": 10})`. **Always set a limit** in production — a bug can cause an infinite loop consuming local resources.

**Q: How would I scale to 100k users?**

A: Three changes:
- **`MemorySaver` → `PostgresSaver`** for durable, concurrent-write memory
- **`InMemoryVectorStore` → FAISS-on-disk or pgvector** so multiple instances share the index
- **Scale Ollama instances** — run multiple Ollama processes or use a remote inference provider

**Q: How do I A/B test prompt changes?**

A: Two ways:
- **Online** — feature flag, route 10% of traffic to the new prompt, compare CSAT/faithfulness scores
- **Offline** — versioned prompts + golden dataset; run Ragas against both, compare scores

**Q: What's the latency profile?**

A: Per turn (local Ollama):
- Input guards: ~600ms (one LLM-judge call)
- Agent: 2-5s (1-3 LLM calls, depending on tool use)
- Output guards: ~600ms (one faithfulness check, if retrieval ran)
- **Total: ~3-7s per turn.** Acceptable for chat; tightenable by using a smaller model for guards.

---

## Related

- **Previous:** [10 — Guardrails](10-guardrails.md)
- **Next:** [12 — MCP](12-mcp.md) (Phase 2 starts)
- **Reference for picking which agent topology:** [reference-agentic-patterns](../reference-agentic-patterns.md)
- **For the visual map of the whole course:** [visual-summary](../visual-summary.md)
