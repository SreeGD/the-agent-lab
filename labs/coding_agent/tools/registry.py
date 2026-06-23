"""Tool registry — maps tool names to (function, schema) pairs.

Students add new tools by:
  1. Implementing the function in the appropriate tools/ module
  2. Defining its Anthropic JSON schema here
  3. Calling registry.register(name, fn, schema)

The registry is the single source of truth passed to client.messages.create(tools=...).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any, Callable

from tools.file_tools import edit_file, glob_files, read_file, write_file
from tools.search_tools import grep_codebase
from tools.bash_tool import bash


# ── Schema definitions (Anthropic tool format) ───────────────────────────────

_READ_FILE = {
    "name": "read_file",
    "description": "Read the full contents of a file. Returns the text content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file (relative to cwd)"},
        },
        "required": ["path"],
    },
}

_WRITE_FILE = {
    "name": "write_file",
    "description": "Write content to a file, creating it if it does not exist. Overwrites existing content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path":    {"type": "string", "description": "Path to write"},
            "content": {"type": "string", "description": "Full file content to write"},
        },
        "required": ["path", "content"],
    },
}

_EDIT_FILE = {
    "name": "edit_file",
    "description": (
        "Replace an exact string in a file. The old_string must match exactly "
        "(including whitespace). Use read_file first to get the exact text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path":       {"type": "string", "description": "File to edit"},
            "old_string": {"type": "string", "description": "Exact string to replace"},
            "new_string": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_string", "new_string"],
    },
}

_GLOB_FILES = {
    "name": "glob_files",
    "description": "Find files matching a glob pattern. Returns a list of matching paths.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern e.g. 'src/**/*.py'"},
            "root":    {"type": "string", "description": "Root directory to search (default: cwd)", "default": "."},
        },
        "required": ["pattern"],
    },
}

_GREP_CODEBASE = {
    "name": "grep_codebase",
    "description": "Search file contents for a regex pattern. Returns matching lines with file paths and line numbers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path":    {"type": "string", "description": "File or directory to search (default: cwd)", "default": "."},
            "glob":    {"type": "string", "description": "Filter by file type e.g. '*.py'"},
        },
        "required": ["pattern"],
    },
}

_BASH = {
    "name": "bash",
    "description": (
        "Execute a shell command and return stdout + stderr. "
        "Use for running tests, installing packages, git operations. "
        "NEVER use for destructive operations (rm -rf, DROP TABLE, etc.)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30)", "default": 30},
        },
        "required": ["command"],
    },
}


# ── Registry ──────────────────────────────────────────────────────────────────

@dataclass
class ToolEntry:
    fn: Callable
    schema: dict


class ToolRegistry:
    """Central registry of all agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(self, name: str, fn: Callable, schema: dict) -> None:
        self._tools[name] = ToolEntry(fn=fn, schema=schema)

    def schemas(self) -> list[dict]:
        """Return list of schemas to pass to client.messages.create(tools=...)."""
        return [entry.schema for entry in self._tools.values()]

    def dispatch(self, name: str, tool_input: dict) -> Any:
        """Execute a tool by name. Raises KeyError if tool not registered."""
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name!r}. Available: {list(self._tools)}")
        return self._tools[name].fn(**tool_input)

    def is_registered(self, name: str) -> bool:
        return name in self._tools


def build_registry() -> ToolRegistry:
    """Instantiate and populate the default tool registry."""
    registry = ToolRegistry()
    registry.register("read_file",     read_file,     _READ_FILE)
    registry.register("write_file",    write_file,    _WRITE_FILE)
    registry.register("edit_file",     edit_file,     _EDIT_FILE)
    registry.register("glob_files",    glob_files,    _GLOB_FILES)
    registry.register("grep_codebase", grep_codebase, _GREP_CODEBASE)
    registry.register("bash",          bash,          _BASH)
    # TODO: register additional tools here (web_fetch, find_symbol, etc.)
    return registry


# ── Permission engine ─────────────────────────────────────────────────────────

# Patterns that are ALWAYS blocked — no user prompt offered
DENY_PATTERNS: list[str] = [
    "bash:rm -rf *",
    "bash:*DROP TABLE*",
    "bash:*> /dev/null 2>&1 &&*",
    "bash:sudo *",
    "bash:*shutdown*",
    "bash:*reboot*",
    "write_file:/etc/*",
    "write_file:~/.ssh/*",
]

# Patterns that are auto-approved — no user prompt needed
ALLOW_PATTERNS: list[str] = [
    "read_file:*",
    "glob_files:*",
    "grep_codebase:*",
    "bash:pytest *",
    "bash:python -m pytest *",
    "bash:pip install *",
    "bash:git status",
    "bash:git diff *",
    "bash:git log *",
]


def check_permission(tool_name: str, tool_input: dict) -> str:
    """Return 'allow', 'deny', or 'prompt'.

    TODO (Step 2): implement deny → allow → prompt evaluation order.

    Hint: build a key like "bash:rm -rf ." from tool_name + primary input value,
    then fnmatch against DENY_PATTERNS, then ALLOW_PATTERNS, then return 'prompt'.
    """
    primary_value = str(list(tool_input.values())[0]) if tool_input else ""
    key = f"{tool_name}:{primary_value}"

    # Check deny first
    for pattern in DENY_PATTERNS:
        if fnmatch.fnmatch(key, pattern):
            return "deny"

    # Check allow list
    for pattern in ALLOW_PATTERNS:
        if fnmatch.fnmatch(key, pattern):
            return "allow"

    # Fall through to user prompt
    return "prompt"
