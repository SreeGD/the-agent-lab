# Notes — Table of Contents

The deep content for each topic now lives in [`lessons/`](./lessons/). This file is the **index** — use it to navigate.

For the full 32-session curriculum tracker (Phase 1 + Phase 2 + Phase 3), see [`CURRICULUM.md`](./CURRICULUM.md) and [`CURRICULUM.csv`](./CURRICULUM.csv).

For conceptual deep-dives (prompt caching mechanics, the LLM Client model, lifecycle details), see [`LEARNINGS.md`](./LEARNINGS.md).

---

## Phase 1 — Foundation (12 lessons)

Each lesson is a runnable example + a markdown walkthrough. The markdown follows a consistent template: roadmap visual, **what problem it solves**, **analogy**, **visual**, concept, code, run it, walk-through, production patterns, try this, mental model, **FAQ**, related links.

| # | Lesson | File(s) | What you'll learn |
|---|---|---|---|
| 01 | [Model Wrapper](lessons/01-model-wrapper.md) | `hello.py` | `ChatAnthropic.invoke()` — the primitive every other lesson builds on |
| 02 | [LCEL Composition](lessons/02-lcel-composition.md) | `chain.py` | `prompt \| model \| parser` — the sequential pipe |
| 03 | [Agent Tool Loop](lessons/03-agent-tool-loop.md) | `agent.py`, `agent_lg.py` | Manual + framework versions of propose-execute-feedback |
| 04 | [Prompt Caching](lessons/04-prompt-caching.md) | `agent_lg_cached.py` | 76% cheaper input via `cache_control` |
| 05 | [Structured Output](lessons/05-structured-output.md) | `structured.py` | `model.with_structured_output(PydanticModel)` |
| 06 | [Parallel Chains](lessons/06-parallel-chains.md) | `parallel.py` | `RunnableParallel` — LCEL fan-out |
| 07 | [Output Parsers](lessons/07-output-parsers.md) | `parsers.py` | Six built-in parsers + custom; vs `with_structured_output` |
| 08 | [Chatbot Memory](lessons/08-chatbot-memory.md) | `agent_chatbot.py` | `MemorySaver` + `thread_id` |
| 09 | [RAG](lessons/09-rag.md) | `rag.py` | Load → split → embed → store → retrieve → generate |
| 10 | [Guardrails](lessons/10-guardrails.md) | `safe_rag.py` | Input + output middleware around the LLM |
| 11 | [Production Capstone](lessons/11-production-capstone.md) | `production_chatbot.py` | RAG + memory + caching + guardrails composed |
| 12 | [MCP](lessons/12-mcp.md) | `mcp_server.py`, `mcp_client.py` | Tool sharing over JSON-RPC stdio |

---

## Reference docs (read when relevant)

| Reference | Purpose |
|---|---|
| [Agentic Patterns one-pager](lessons/reference-agentic-patterns.md) | ReAct / Reflection / Plan-and-Execute side-by-side + decision tree |
| [Visual Summary](lessons/visual-summary.md) | Architecture stack, 8 patterns, concept index, mental models |

---

## How to use this

**Linear path (first time through):**
Read lessons 01 → 12 in order. Each takes ~30-60 min of reading + ~30-60 min of running the file. Total: ~12-18 hours.

**Reference path (after first time):**
Land on `lessons/` whenever you're picking a pattern or debugging behavior. The FAQ section of each lesson catches the common confusions.

**Curriculum path (the 32-session plan):**
Foundation (lessons 01-12) = Phase 1 of [`CURRICULUM.md`](./CURRICULUM.md). After Phase 1, the curriculum continues with Phase 2 (advanced patterns: Reflection, Plan-and-Execute, Multi-agent, Spec-Driven Dev, Vibe Coding, Skills, etc.) and Phase 3 (vertical deep dives: Healthcare, Agriculture, Finance, Vidya Karana, Family AI).

---

## File map

```
helloworld/
├── *.py                    ← runnable examples (one per lesson)
├── lessons/                ← lesson markdown (this is what NOTES.md indexes)
│   ├── 01-model-wrapper.md
│   ├── 02-lcel-composition.md
│   ├── ...
│   ├── 12-mcp.md
│   ├── reference-agentic-patterns.md
│   └── visual-summary.md
├── NOTES.md                ← THIS file (the index)
├── LEARNINGS.md            ← deeper conceptual material
├── CURRICULUM.md           ← the 32-session plan
├── CURRICULUM.csv          ← spreadsheet tracker
└── requirements.txt
```
