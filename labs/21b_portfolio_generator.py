"""Session 21b — Portfolio Generator: scan course labs and publish a GitHub-ready portfolio."""

import ast
import os
import re
from pathlib import Path
from typing import List, TypedDict

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512

PATTERN_KEYWORDS: dict = {
    "LangGraph": "langgraph",
    "MCP": "mcp",
    "RAG": "rag",
    "Streaming": "astream",
    "Structured output": "with_structured_output",
    "Prompt caching": "cache_control",
    "Multi-agent": "supervisor",
    "Tool use": "tool",
}


class LabEntry(TypedDict):
    """A single parsed lab file with its metadata."""

    filename: str
    docstring: str
    patterns: List[str]


def _extract_docstring(source: str) -> str:
    """Return the module-level docstring from Python source, or empty string."""
    try:
        tree = ast.parse(source)
        return ast.get_docstring(tree) or ""
    except SyntaxError:
        return ""


def _detect_patterns(source: str) -> List[str]:
    """Return pattern names whose keywords appear in source (case-insensitive)."""
    lowered = source.lower()
    return [name for name, kw in PATTERN_KEYWORDS.items() if kw in lowered]


def scan_labs(labs_dir: str) -> List[LabEntry]:
    """Scan labs_dir for digit-prefixed *.py files that have module docstrings."""
    entries: List[LabEntry] = []
    for path in sorted(Path(labs_dir).glob("*.py")):
        if not re.match(r"^\d", path.name):
            continue
        source = path.read_text(encoding="utf-8")
        docstring = _extract_docstring(source)
        if not docstring:
            continue
        entries.append(
            LabEntry(
                filename=path.name,
                docstring=docstring,
                patterns=_detect_patterns(source),
            )
        )
    return entries


def generate_project_card(entry: LabEntry, client: anthropic.Anthropic) -> str:
    """Generate a short markdown project card for one lab via Claude."""
    patterns_text = ", ".join(entry["patterns"]) or "none"
    prompt = (
        f"Lab file: {entry['filename']}\n"
        f"Docstring: {entry['docstring']}\n"
        f"Patterns used: {patterns_text}\n\n"
        "Write a concise markdown project card (3-4 lines): bold filename as header, "
        "one-line description, tech used. No preamble."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def build_portfolio(entries: List[LabEntry], cards: List[str]) -> str:
    """Assemble PORTFOLIO.md content from lab entries and generated cards."""
    all_patterns: set = set()
    for entry in entries:
        all_patterns.update(entry["patterns"])

    lines = [
        "# AgenticCourse Portfolio",
        "",
        "Built through the AgenticCourse curriculum — 46 sessions on agentic AI systems.",
        "",
        "## Skills Matrix",
        "",
        "| Pattern | Sessions |",
        "|---|---|",
    ]

    for pattern in sorted(all_patterns):
        sessions = [e["filename"] for e in entries if pattern in e["patterns"]]
        suffix = "..." if len(sessions) > 3 else ""
        lines.append(f"| {pattern} | {', '.join(sessions[:3])}{suffix} |")

    lines += ["", "## Project Cards", ""]
    lines += cards
    return "\n".join(lines)


def draft_linkedin_post(entries: List[LabEntry], client: anthropic.Anthropic) -> str:
    """Draft a LinkedIn post summarising the course arc via Claude."""
    summary = "\n".join(
        f"- {e['filename']}: {e['docstring'][:60]}" for e in entries[:10]
    )
    prompt = (
        f"I completed an AI engineering course covering {len(entries)} labs. "
        f"Top sessions:\n{summary}\n\n"
        "Write a LinkedIn post (150-200 words) about what I built and learned. "
        "Professional but enthusiastic. No hashtag spam (max 3 tags)."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def main() -> None:
    """Scan labs, generate portfolio, write PORTFOLIO.md and PORTFOLIO_linkedin.txt."""
    labs_dir = os.path.dirname(__file__)
    client = anthropic.Anthropic()

    print("Scanning labs...")
    entries = scan_labs(labs_dir)
    print(f"Found {len(entries)} labs with docstrings.\n")

    print("Generating project cards...")
    cards = [generate_project_card(e, client) for e in entries]

    portfolio_md = build_portfolio(entries, cards)
    out = Path(labs_dir).parent / "PORTFOLIO.md"
    out.write_text(portfolio_md, encoding="utf-8")
    print(f"Written: {out}")

    print("Drafting LinkedIn post...")
    post = draft_linkedin_post(entries, client)
    post_out = Path(labs_dir).parent / "PORTFOLIO_linkedin.txt"
    post_out.write_text(post, encoding="utf-8")
    print(f"Written: {post_out}")


if __name__ == "__main__":
    main()
