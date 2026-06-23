"""Search tools — grep codebase by regex pattern."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def grep_codebase(pattern: str, path: str = ".", glob: str | None = None) -> str:
    """Search for a regex pattern across files. Returns matching lines with locations."""
    # TODO (Step 1 extension): add find_symbol() using ast.parse for Python symbol lookup
    args = ["grep", "-rn", "--color=never"]
    if glob:
        args += ["--include", glob]
    args += [pattern, path]

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        if not output:
            return f"No matches for pattern: {pattern!r}"
        lines = output.splitlines()
        if len(lines) > 100:
            return "\n".join(lines[:100]) + f"\n... ({len(lines) - 100} more lines truncated)"
        return output
    except subprocess.TimeoutExpired:
        return "ERROR: grep timed out (>10s)"
    except FileNotFoundError:
        return _pure_python_grep(pattern, path, glob)


def _pure_python_grep(pattern: str, path: str, glob_pat: str | None) -> str:
    """Fallback grep using Python (slower but no subprocess dependency)."""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"ERROR: invalid regex pattern: {e}"

    results = []
    root = Path(path)
    files = root.rglob(glob_pat or "*") if root.is_dir() else [root]

    for fp in files:
        if not fp.is_file():
            continue
        try:
            for i, line in enumerate(fp.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if regex.search(line):
                    results.append(f"{fp}:{i}: {line}")
                    if len(results) >= 100:
                        results.append("... (truncated at 100 matches)")
                        return "\n".join(results)
        except Exception:
            continue

    return "\n".join(results) if results else f"No matches for pattern: {pattern!r}"
