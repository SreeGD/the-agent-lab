"""Bash tool — execute shell commands with timeout and output capture."""

from __future__ import annotations

import subprocess


MAX_OUTPUT_CHARS = 8_000  # truncate very large outputs before feeding back to context


def bash(command: str, timeout: int = 30) -> str:
    """Execute a shell command. Returns combined stdout + stderr.

    The permission engine checks this before execution — never call directly.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        if not output.strip():
            output = f"(exit code {result.returncode}, no output)"

        # Truncate very long output — agent gets the tail (most recent output is most useful)
        if len(output) > MAX_OUTPUT_CHARS:
            output = f"... (truncated, showing last {MAX_OUTPUT_CHARS} chars)\n" + output[-MAX_OUTPUT_CHARS:]

        return output.rstrip()

    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s: {command!r}"
    except Exception as e:
        return f"ERROR executing command: {e}"
