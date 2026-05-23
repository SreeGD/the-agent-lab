# Design: OpenAI + Ollama Lesson Variants

**Date:** 2026-05-23  
**Status:** Approved  

---

## Goal

Add OpenAI (`gpt-4o`) and Ollama (`llama3.2`) variants for every provider-agnostic lesson in the AgenticCourse. Each variant is a fully standalone, runnable alternative — not a diff or wrapper — so learners using any provider can follow the course without referencing Anthropic-specific files.

---

## Scope

### Lessons included (30 of 34)

| # | Lesson | Code file |
|---|---|---|
| 01 | Model Wrapper | `01_model_wrapper.py` |
| 02 | LCEL Composition | `02_lcel_chain.py` |
| 03 | Agent Tool Loop | `03_agent_framework.py` + `03_agent_manual.py` |
| 05 | Structured Output | `05_structured_output.py` |
| 06 | Parallel Chains | `06_parallel_chains.py` |
| 07 | Output Parsers | `07_output_parsers.py` |
| 08 | Chatbot Memory | `08_chatbot_memory.py` |
| 09 | RAG | `09_rag.py` |
| 10 | Guardrails | `10_guardrails.py` |
| 11 | Production Capstone | `11_production_chatbot.py` |
| 12 | MCP | `12_mcp_client.py` + `12_mcp_server.py` |
| 13 | Reflection + Plan-Execute | `13_reflection_agent.py` + `13_plan_execute_agent.py` |
| 14 | Multi-Agent + LTM | `14_multi_agent.py` + `14_long_term_memory.py` |
| 15 | Spec-Driven Development | `15_spec_driven.py` |
| 19 | AI Gateway | `19_ai_gateway.py` |
| 20 | Files & Document AI | `20_citations_demo.py` + `20_pdf_vision.py` |
| 21 | Custom LangGraph + HITL | `21_custom_graph.py` + `21_time_travel.py` |
| 22 | Hybrid RAG | `22_hybrid_rag.py` |
| 23 | GraphRAG | `23_graph_rag.py` |
| 24 | Corrective RAG | `24_corrective_rag.py` |
| 25 | Evaluation | `25_evaluation.py` |
| 26 | Cost Optimization | `26_cost_optimization.py` |
| 27 | Streaming | `27_streaming.py` |
| 28 | Production Deploy | `28_production_app.py` |
| 29 | Memory Architectures | `29_memory_architectures.py` |
| 30 | System Design | `30_system_design_helper.py` |
| 31 | Red Teaming | `31_red_teaming.py` |
| 32 | Governance | `32_governance.py` |
| 33 | UX Patterns | `33_ux_audit_helper.py` |
| 34 | Farm Planner | `34_farm_planner_engine.py` + `34_farm_planner_api.py` + `34_farm_planner_ui.py` |

### Lessons excluded (Anthropic-specific)

| # | Lesson | Reason |
|---|---|---|
| 04 | Prompt Caching | Anthropic-proprietary `cache_control` feature |
| 16 | Vibe Coding | Claude Code runtime-specific |
| 17 | Claude Skills | Claude Code plugin system |
| 18 | Anthropic SDK | Provider-specific by definition |

---

## Directory Structure

```
labs/
├── openai/                              # OpenAI code variants
│   ├── 01_model_wrapper_openai.py
│   ├── 02_lcel_chain_openai.py
│   └── ... (one file per lesson; multi-file lessons get multiple files)
├── ollama/                              # Ollama code variants
│   ├── 01_model_wrapper_ollama.py
│   ├── 02_lcel_chain_ollama.py
│   └── ... (one file per lesson; multi-file lessons get multiple files)
└── lessons/
    ├── openai/                          # OpenAI lesson docs
    │   ├── 01-model-wrapper.md
    │   └── ... (30 files)
    └── ollama/                          # Ollama lesson docs
        ├── 01-model-wrapper.md
        └── ... (30 files)
```

Existing files under `labs/*.py` and `labs/lessons/*.md` are **not modified**.

---

## Code File Convention

### What changes from the Anthropic original

| Element | Anthropic original | OpenAI variant | Ollama variant |
|---|---|---|---|
| Import | `langchain_anthropic` | `langchain_openai` | `langchain_ollama` |
| Model class | `ChatAnthropic` | `ChatOpenAI` | `ChatOllama` |
| Model name | `"claude-sonnet-4-6"` | `"gpt-4o"` | `"llama3.2"` |
| API key env var | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` | _(none — local server)_ |
| File suffix | _(none)_ | `_openai` | `_ollama` |

### What stays identical

- All tool definitions, schemas, and logic
- LangChain LCEL chain compositions
- LangGraph graph structure and nodes
- Prompts, system messages, and examples
- Memory, retrieval, and evaluation patterns

### Ollama prerequisite comment

Every Ollama file includes a top-of-file comment:
```
# Requires: `ollama serve` running locally + `ollama pull llama3.2`
```

---

## Lesson Doc Convention

Each lesson doc in `labs/lessons/openai/` and `labs/lessons/ollama/` is a **full rewrite** of the corresponding Anthropic lesson with:

1. **"Provider variant" callout at top** — a short block (3–5 lines) stating:
   - Which provider this version uses
   - What differs from the Anthropic version
   - What is identical
2. **All model references updated** throughout (class names, model strings, env vars)
3. **All code snippets updated** to use the correct provider
4. **File references updated** to point to `labs/openai/` or `labs/ollama/`
5. **Visual diagrams updated** where provider name appears
6. **Roadmap section preserved** unchanged (the course structure is the same)

---

## Constraints

- Existing Anthropic lesson files and code files are **not touched**
- No shared utility files or factory abstractions — each file is standalone
- Ollama variants do not require an API key; OpenAI variants require `OPENAI_API_KEY` in `.env`
- For lessons with multiple code files (03, 12, 13, 14, 20, 21, 34), only files that directly instantiate a model get variants — server files (`12_mcp_server.py`), UI files (`34_farm_planner_ui.py`), and pure API files (`34_farm_planner_api.py`) are provider-agnostic and are not duplicated

---

## Deliverables

| Deliverable | Count |
|---|---|
| `labs/openai/*.py` | ~35 files (some lessons have 2–3 code files) |
| `labs/ollama/*.py` | ~35 files |
| `labs/lessons/openai/*.md` | 30 files |
| `labs/lessons/ollama/*.md` | 30 files |
| **Total new files** | **~130** |
