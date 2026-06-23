"""File system tools — read, write, edit, glob.

All paths are resolved relative to cwd unless absolute.
These tools are always auto-approved (read-only variants) or require confirmation (write variants).
"""

from __future__ import annotations

import glob as _glob
from pathlib import Path


def read_file(path: str) -> str:
    """Return file content as a string, prefixed with line numbers."""
    p = Path(path)
    if not p.exists():
        return f"ERROR: File not found: {path}"
    if not p.is_file():
        return f"ERROR: Path is not a file: {path}"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        numbered = "\n".join(f"{i+1:4d}  {line}" for i, line in enumerate(lines))
        return f"// {path} ({len(lines)} lines)\n{numbered}"
    except Exception as e:
        return f"ERROR reading {path}: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to path, creating parent directories as needed."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        lines = content.count("\n") + 1
        return f"OK: wrote {lines} lines to {path}"
    except Exception as e:
        return f"ERROR writing {path}: {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Replace old_string with new_string in file. old_string must match exactly."""
    p = Path(path)
    if not p.exists():
        return f"ERROR: File not found: {path}"
    try:
        original = p.read_text(encoding="utf-8")
        if old_string not in original:
            # Give the agent a useful hint
            return (
                f"ERROR: old_string not found in {path}.\n"
                f"Use read_file first to get the exact text including whitespace."
            )
        count = original.count(old_string)
        if count > 1:
            return (
                f"ERROR: old_string appears {count} times in {path}. "
                f"Provide more surrounding context to make it unique."
            )
        updated = original.replace(old_string, new_string, 1)
        p.write_text(updated, encoding="utf-8")
        return f"OK: edit applied to {path}"
    except Exception as e:
        return f"ERROR editing {path}: {e}"


def glob_files(pattern: str, root: str = ".") -> str:
    """Return newline-separated list of paths matching the glob pattern."""
    try:
        matches = sorted(_glob.glob(pattern, root_dir=root, recursive=True))
        if not matches:
            return f"No files matched pattern: {pattern}"
        return "\n".join(matches)
    except Exception as e:
        return f"ERROR in glob: {e}"
