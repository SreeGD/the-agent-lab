---
name: project-context
description: Stable facts about AgenticCourse that every session needs.
metadata:
  type: project
---

# Project Context

## What this is
A 46-session educational lab monorepo teaching agentic AI system design.
Sessions are numbered and progressive; each builds on prior sessions.
Track M (Sessions 38-46) covers Claude Code itself as the target skill.

## Primary audience
Engineers building production agentic AI systems; intermediate Python level.

## Key constraints
- Python 3.9+ (some labs use match/case — requires 3.10+)
- Anthropic API key required (ANTHROPIC_API_KEY in .env)
- HuggingFace local embeddings for skill router (no extra API key)
- Ollama track requires local Ollama installation with llama3.2 model

## Repo owner
GitHub: SreeGD/AgenticCourse
