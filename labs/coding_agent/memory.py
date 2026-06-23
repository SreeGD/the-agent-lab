"""Session memory — save and resume conversation history.

Saves to .agent_session.json in cwd.
On --resume, the prior message history is loaded and the agent continues from where it left off.

TODO (Step 6): add context compaction — when the session grows large,
summarise older messages with claude-haiku and replace them with the summary.
"""

from __future__ import annotations

import json
from pathlib import Path

SESSION_FILE = Path(".agent_session.json")


def save_session(data: dict) -> None:
    """Persist session data (messages + metadata) to disk."""
    try:
        SESSION_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[memory]   WARNING: could not save session: {e}")


def load_session() -> dict | None:
    """Load prior session from disk. Returns None if no session exists."""
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[memory]   WARNING: could not load session: {e}")
        return None


def clear_session() -> None:
    """Delete the saved session file."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
        print("[memory]   Session cleared.")
