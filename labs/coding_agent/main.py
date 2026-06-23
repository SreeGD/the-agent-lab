#!/usr/bin/env python3
"""CLI Coding Agent — entrypoint.

Usage:
    python main.py "add type hints to all functions in src/utils.py"
    python main.py --resume
    python main.py --clear-session "start fresh"
    python main.py --verbose "refactor auth module"

Keyboard shortcuts during a session:
    Ctrl+C  — interrupt the agent after the current tool call completes
"""

from __future__ import annotations

import argparse
import sys

from agent_loop import run_agent
from memory import clear_session
from tools.registry import build_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CLI Coding Agent — an autonomous coding assistant powered by Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "add input validation to all FastAPI route handlers"
  python main.py --resume
  python main.py --verbose "write unit tests for src/utils/parser.py"
  python main.py --clear-session "start fresh task"
        """,
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task description for the agent",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume prior session from .agent_session.json",
    )
    parser.add_argument(
        "--clear-session",
        action="store_true",
        dest="clear_session",
        help="Clear saved session before starting",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full tool outputs (not just preview)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.clear_session:
        clear_session()

    if not args.task and not args.resume:
        print("Error: provide a task or use --resume to continue a prior session.")
        print("       python main.py \"<your task here>\"")
        sys.exit(1)

    task = args.task or ""

    # Build the tool registry (register all tools + schemas)
    registry = build_registry()

    try:
        run_agent(task=task, registry=registry, resume=args.resume)
    except KeyboardInterrupt:
        print("\n\n[agent]    Interrupted by user. Session saved.")
        sys.exit(0)


if __name__ == "__main__":
    main()
