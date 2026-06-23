"""Codebase Archaeology — Session 41: Architecture Summary Generator.

Reads a repo map produced by 41_repo_map.py, sends it to Claude with a
phase-gated prompt, and writes (or prints) an architecture narrative.

Optionally auto-populates .claude/CLAUDE.md so every future Claude Code
session in the repo starts with the architecture in context.

Usage:
    python 41_architecture_summary.py --map repo_map.json
    python 41_architecture_summary.py --map repo_map.json --output architecture.md
    python 41_architecture_summary.py --map repo_map.json --write-claude-md
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "claude-opus-4-7"
llm = ChatAnthropic(model=MODEL, max_tokens=4096)


SYSTEM_PROMPT = """You are a senior software architect performing a codebase orientation.
You receive a structured JSON map of a repository and produce a clear, concise architecture document.

Be specific: name actual files, classes, and patterns. Avoid generic statements.
Write for a new engineer who will start reading code immediately after this document."""


ARCHITECTURE_PROMPT = """Here is the repository map:

{repo_map_json}

Produce an architecture document with exactly these four sections:

## 1. Architecture Overview
What does this system do? What are its 3-5 major components? What architectural pattern does it follow (MVC, pipeline, event-driven, microservices, etc.)?

## 2. Data Flow
Trace the lifecycle of a single request or record end-to-end, naming the actual files involved at each step.

## 3. File Guide
For each of the top 15 most important files:
- **filename.py** — one sentence on its role, one sentence on what to read first inside it.

## 4. Onboarding Path
List exactly the files a new engineer should read, in order, to build a correct mental model fastest. Include a one-line reason for each.
"""


class FileGuideEntry(BaseModel):
    path: str
    role: str
    read_first: str


class ArchitectureSummary(BaseModel):
    architecture_overview: str = Field(description="High-level description of the system and its components")
    data_flow: str = Field(description="End-to-end trace of a request/record through the system")
    file_guide: list[FileGuideEntry] = Field(description="Key files with roles")
    onboarding_path: list[str] = Field(description="Ordered list of files to read with reasons")
    raw_markdown: str = Field(description="Full architecture document as markdown")


def summarise(repo_map: dict) -> str:
    repo_map_json = json.dumps(repo_map, indent=2)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=ARCHITECTURE_PROMPT.format(repo_map_json=repo_map_json)),
    ]
    response = llm.invoke(messages)
    return response.content


def write_claude_md(summary_markdown: str, repo_root: str):
    claude_dir = Path(repo_root) / ".claude"
    claude_dir.mkdir(exist_ok=True)
    claude_md = claude_dir / "CLAUDE.md"
    claude_md.write_text(f"# Project Architecture\n\n{summary_markdown}\n")
    print(f"CLAUDE.md written to {claude_md}")


def main():
    parser = argparse.ArgumentParser(description="Generate architecture summary from repo map.")
    parser.add_argument("--map", required=True, help="Path to repo_map.json")
    parser.add_argument("--output", default=None, help="Output markdown file (default: stdout)")
    parser.add_argument("--write-claude-md", action="store_true", help="Write to .claude/CLAUDE.md")
    args = parser.parse_args()

    repo_map = json.loads(Path(args.map).read_text())
    repo_root = repo_map.get("repo_root", ".")

    print(f"Generating architecture summary for {repo_root}...")
    summary = summarise(repo_map)

    if args.output:
        Path(args.output).write_text(summary)
        print(f"Architecture summary written to {args.output}")
    else:
        print("\n" + summary)

    if args.write_claude_md:
        write_claude_md(summary, repo_root)


if __name__ == "__main__":
    main()
