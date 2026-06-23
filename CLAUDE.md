# AgenticCourse

Educational lab monorepo for building agentic AI systems with Claude.

## Tech Stack
- Python 3.9+, LangChain, LangGraph, Streamlit
- Primary AI: Anthropic Claude (claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5)
- Parallel tracks: labs/openai/ (OpenAI) and labs/ollama/ (local Ollama)

## Layout
- labs/*.py       — numbered lesson scripts (01-46)
- labs/lessons/   — lesson markdown docs, one per session
- labs/agritech/  — AgriTech capstone engine + knowledge base
- labs/coding_agent/ — standalone tool-using agent example

## Conventions
- Lab files: NN_descriptive_name.py
- Lesson files: labs/lessons/NN-descriptive-name.md
- New sessions must be added to labs/CURRICULUM.csv
- Provider variants share the same LangGraph topology; only the LLM client differs
- Never use temperature=0 with claude-opus-4-7 (deprecated in Opus 4.x)

## Hard Rules
- Do not modify labs/farm_plans/checkpoints.sqlite directly
- Lesson files must stay under 500 lines — split if larger
- All python files must have a module-level docstring
