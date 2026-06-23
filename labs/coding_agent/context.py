"""AGENT.md loader — injects project config into the system prompt.

AGENT.md is the equivalent of CLAUDE.md in Claude Code.
It is loaded once at session start and cached (stable prefix → cache hit on subsequent turns).
"""

from __future__ import annotations

from pathlib import Path

_AGENT_MD_FILENAME = "AGENT.md"

_BASE_SYSTEM_PROMPT = """You are an expert software engineering assistant running in a terminal.

You have access to tools that let you read files, write files, edit files, search the codebase, and run shell commands.

## How to approach tasks

1. **Understand before acting** — read relevant files before making changes.
2. **Plan, then execute** — for multi-step tasks, state your plan before calling tools.
3. **Verify your work** — after edits, run tests or check the output.
4. **Be precise with edits** — use read_file to get exact text before calling edit_file.
5. **Stop when done** — do not make unrequested changes.

## Tool discipline

- Prefer read_file + edit_file over write_file for existing files (safer, reviewable).
- Run bash commands only when necessary. Always show the command before running it.
- If a bash command fails, read the error carefully before retrying.
- Never run destructive commands (rm -rf, DROP TABLE, force push to main).

## Output format

- Think step by step but be concise — one clear sentence per reasoning step.
- Show tool results inline. Do not repeat large file contents back to the user.
- When you are done, say so explicitly and summarise what changed.
"""


def build_system_prompt() -> list[dict]:
    """Build the system prompt as a list of Anthropic content blocks.

    The AGENT.md content is marked with cache_control so it is cached
    server-side after the first call — subsequent turns reuse it at no cost.

    TODO (Step 4): parse AGENT.md allow-list section and merge into
    tools.registry.ALLOW_PATTERNS at startup.
    """
    blocks: list[dict] = [
        {
            "type": "text",
            "text": _BASE_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},  # cache the stable base prompt
        }
    ]

    agent_md = _load_agent_md()
    if agent_md:
        blocks.append({
            "type": "text",
            "text": f"## Project configuration (from {_AGENT_MD_FILENAME})\n\n{agent_md}",
            "cache_control": {"type": "ephemeral"},  # cache project config too
        })

    return blocks


def _load_agent_md() -> str | None:
    """Search for AGENT.md in cwd and parent directories (up to 3 levels)."""
    search_dirs = [Path.cwd()] + list(Path.cwd().parents)[:3]
    for d in search_dirs:
        candidate = d / _AGENT_MD_FILENAME
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8")
            print(f"[context]  Loaded {candidate} ({len(content)} chars)")
            return content
    print(f"[context]  No {_AGENT_MD_FILENAME} found — using base system prompt only")
    return None
