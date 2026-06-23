# AGENT.md — Project Configuration

This file is loaded by the coding agent at session start and injected into its system prompt.
Edit this file to shape how the agent behaves in this project.

## Project

Python project. Use pytest for tests. Follow PEP 8.

## Rules

- Always run tests after modifying source files: `pytest tests/ -v`
- Never modify files in `migrations/` directly
- Use type hints on all new functions
- Keep functions under 40 lines — split if longer
- Prefer composition over inheritance

## Allow list

These commands are pre-approved and will not prompt for permission:

```
bash: pytest *
bash: python -m pytest *
bash: pip install *
bash: git status
bash: git diff *
bash: git log *
bash: python *.py
```

## Hooks

pre_tool:
  # Uncomment to block sudo commands via hook script
  # - match: bash
  #   script: hooks/pre_bash.sh

post_tool:
  # Uncomment to enable audit logging
  # - match: "*"
  #   script: hooks/audit_log.sh
