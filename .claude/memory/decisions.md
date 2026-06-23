---
name: architectural-decisions
description: Key architectural decisions for AgenticCourse — what we chose and why.
metadata:
  type: project
---

# Architectural Decisions

## 2026-06-23: temperature deprecated for claude-opus-4-7
Anthropic deprecated the `temperature` parameter for Opus 4.x models.
All `ChatAnthropic` calls using Opus must omit `temperature` entirely.
Sonnet and Haiku still accept `temperature=0`.
**Why:** API returned 400 BadRequestError on session 41 demo run.
**How to apply:** Check model name before setting temperature. Opus 4.x = no temperature.

## 2026-06-22: Provider-adapter pattern for all capstone engines
Each major engine exists in three variants (Anthropic, OpenAI, Ollama).
They share identical LangGraph topology and Pydantic state schema.
Only the LLM client and model name differ. UI uses importlib to select at runtime.
**Why:** Course teaches provider-agnostic agentic patterns.
**How to apply:** When adding a new lab that uses LLM calls, add all three variants.

## 2026-05-21: SQLite checkpointer for farm planner
LangGraph SqliteSaver persists state between restarts, keyed by uuid thread_id.
**Why:** Users need to resume interrupted farm plans without re-running all agents.
**How to apply:** Never delete the sqlite file mid-run. Each plan gets its own thread_id.
