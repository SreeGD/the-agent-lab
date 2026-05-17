# AgenticCourse

A hands-on curriculum for building agentic AI systems with **LangChain**, **LangGraph**, and **Anthropic Claude** — from a one-line `model.invoke()` to a multi-agent, RAG-grounded, cached, guardrailed, memory-having production chatbot.

Built incrementally as a learning project. Every file in `helloworld/` is a runnable example that adds exactly one concept on top of the previous one.

---

## Where to start

| If you want to... | Go to |
|---|---|
| **See what's been built so far** | [`helloworld/`](helloworld/) — 13 working Python examples |
| **Understand the concepts step by step** | [`helloworld/NOTES.md`](helloworld/NOTES.md) — the foundational walkthrough |
| **Read the conceptual deep dives** | [`helloworld/LEARNINGS.md`](helloworld/LEARNINGS.md) — prompt caching, the LLM Client mental model, token economics |
| **See the full 32-session learning plan** | [`helloworld/CURRICULUM.md`](helloworld/CURRICULUM.md) + [`helloworld/CURRICULUM.csv`](helloworld/CURRICULUM.csv) |
| **Get the project running locally** | [Quick start](#quick-start) below |

---

## What's in `helloworld/`

Each file teaches one concept and runs standalone.

| # | File | Concept |
|---|---|---|
| 1 | `hello.py` | Model wrapper — `ChatAnthropic.invoke()` |
| 2 | `chain.py` | LCEL composition — `prompt \| model \| parser` |
| 3 | `parallel.py` | LCEL fan-out — `RunnableParallel` |
| 4 | `agent.py` | Manual tool-calling loop (hand-written `while not msg.tool_calls`) |
| 5 | `agent_lg.py` | Framework agent — `create_react_agent` from LangGraph |
| 6 | `agent_lg_cached.py` | Prompt caching — 76% cheaper per run with one keyword |
| 7 | `structured.py` | Typed output — `model.with_structured_output(PydanticModel)` |
| 8 | `parsers.py` | The six built-in output parsers + a custom one |
| 9 | `agent_chatbot.py` | Stateful agent — `MemorySaver` + `thread_id` |
| 10 | `rag.py` | Full RAG pipeline — load → split → embed → store → retrieve → generate |
| 11 | `safe_rag.py` | RAG wrapped in input + output guardrails (PII, injection, on-topic, faithfulness) |
| 12 | `production_chatbot.py` | **Capstone** — RAG + memory + caching + guardrails composed in one architecture |
| 13 | `mcp_server.py` + `mcp_client.py` | MCP (Model Context Protocol) — your tools shared via JSON-RPC stdio, usable by Claude Desktop / Cursor / any MCP client |

Plus:
- [`NOTES.md`](helloworld/NOTES.md) — step-by-step walkthrough of every file
- [`LEARNINGS.md`](helloworld/LEARNINGS.md) — conceptual deep dives (LLM Client, caching mechanics, lifecycle)
- [`CURRICULUM.md`](helloworld/CURRICULUM.md) — the 32-session learning plan
- [`CURRICULUM.csv`](helloworld/CURRICULUM.csv) — tracker spreadsheet

---

## The curriculum at a glance

**32 sessions across 12 tracks, ~64 hours, ~11 weeks** at 9 hours/week.

| Phase | Sessions | Tracks |
|---|---|---|
| **Foundation** | 1-13 | Agentic Patterns • Workflow Patterns • Alt Architectures • Data/Multi-modal • Graph Depth • Production |
| **Architect Skills** | 14-16 | System Design Interview • Red-teaming • AI UX |
| **Vertical Deep Dives** | 17-32 | Healthcare • Agriculture • Finance • Vidya Karana (wellness/yoga/Vedic) • Family AI Agent |

See [`helloworld/CURRICULUM.md`](helloworld/CURRICULUM.md) for the full session-by-session plan.

---

## Quick start

```bash
git clone https://github.com/SreeGD/AgenticCourse.git
cd AgenticCourse/helloworld

# Create a Python 3.10+ venv
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Add your Anthropic API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# Run any example
python hello.py                 # send one prompt
python chain.py                 # LCEL chain
python agent_lg.py              # framework agent
python rag.py                   # full RAG pipeline
python production_chatbot.py    # the capstone
python mcp_client.py            # MCP demo (Session 1 of new curriculum)
```

Get an Anthropic API key at https://console.anthropic.com.

---

## Tech stack

- **Models:** Anthropic Claude (Sonnet 4.6, Opus 4.7)
- **Framework:** LangChain (LCEL), LangGraph (agents, state machines)
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (local, free)
- **Vector store:** `InMemoryVectorStore` (swap for FAISS / Chroma / pgvector in production)
- **Tool protocol:** MCP (Model Context Protocol)
- **Python:** 3.11+

See [`helloworld/requirements.txt`](helloworld/requirements.txt) for the full dependency list.

---

## Key mental models

The seven one-liners that compress the curriculum so far:

1. **The LLM never calls anything. The LLM Client does.** *(Tool calling, MCP, agents — all variations of one dance.)*
2. **A prompt is the input. A prompt template is a recipe for building a prompt.**
3. **An output parser adapts text (what the LLM emits) into typed values (what your code wants).**
4. **`prompt \| model \| parser` is sequential. `{"a": chain_a, "b": chain_b}` is parallel.**
5. **Each turn carries the whole conversation. Memory adds state. Caching keeps cost bounded.**
6. **The cache discount is real because the server skips prefill — the most expensive 80% of inference — not because Anthropic is being nice.**
7. **RAG = "I pick the right text client-side, the LLM reads only that text."**

Full discussion in [`helloworld/LEARNINGS.md`](helloworld/LEARNINGS.md).

---

## Status

**Active learning project.** Foundation (Sessions 1-13 of the original 13 + Session 1 of the new 32) is complete and working. The remaining 31 sessions (agentic patterns, workflow patterns, verticals: healthcare / agriculture / finance / vidya karana / family AI) are planned in [`CURRICULUM.md`](helloworld/CURRICULUM.md).

This repo is built and maintained by **Sree** (@SreeGD) — a data scientist learning agentic AI architecture session by session.

---

## License

No license declared yet. Code is provided for learning purposes.
