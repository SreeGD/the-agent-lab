# Session 21b — Portfolio Generator: Shipping & Building in Public

## Why This Session Exists

Most engineers complete a course, close the repo, and move on.
The ones who compound their learning ship it publicly.
A GitHub portfolio signals taste, depth, and follow-through in a way that a résumé cannot.
This session automates that entire output — scanning the labs you just built, extracting
structured metadata, and asking Claude to write the story.

---

## Why Building in Public Compounds

Shipping work publicly creates a feedback loop that private work never does:

| Action | Private outcome | Public outcome |
|---|---|---|
| Complete 46 labs | You know what you built | Others see what you built |
| Write a portfolio README | Clarifies thinking | Attracts collaborators and employers |
| Post on LinkedIn | Nothing | Recruiter DMs, coffee chats, job offers |
| Open-source capstone | Your laptop | Stars, issues, forks |

The compounding is not automatic — it requires a clear signal.
The portfolio README is that signal.

---

## README Anatomy

A strong project README for an AI engineering portfolio follows this structure:

```
# Project Name
One sentence: what it does and why it matters.

## What I Built
3-5 bullet points of concrete outputs (not learning goals).

## Tech Used
LangGraph / Claude / RAG / MCP / etc.

## How It Works
A 2-paragraph narrative or a simple flow diagram.

## Run It
Copy-paste command that works in 30 seconds.

## What I Learned
Honest reflection — include the thing that surprised you.
```

The `21b_portfolio_generator.py` lab generates this structure automatically for
each numbered lab file in the course.

---

## The Portfolio Pipeline

```
labs/*.py
    │
    ▼  scan_labs()     — AST parses each file; extracts module docstring + patterns
    │
    ▼  generate_project_card()   — Claude writes a 3-4 line markdown card per lab
    │
    ▼  build_portfolio()         — assembles PORTFOLIO.md with a skills matrix
    │
    ▼  draft_linkedin_post()     — Claude writes a 150-200 word LinkedIn post
    │
    ▼  PORTFOLIO.md + PORTFOLIO_linkedin.txt   — ready to publish
```

### AST-Based Lab Scanner

Instead of regex-scraping Python files, the scanner uses the `ast` module to
extract the module docstring reliably regardless of string quoting style:

```python
import ast

tree = ast.parse(source)
docstring = ast.get_docstring(tree)  # None if absent
```

Only files matching `^\d` (i.e., numbered lessons) are processed — helper modules,
config files, and non-lesson scripts are ignored automatically.

### Pattern Detection

`PATTERN_KEYWORDS` maps readable pattern names to source-level keywords:

```python
PATTERN_KEYWORDS = {
    "LangGraph": "langgraph",
    "RAG": "rag",
    "Streaming": "astream",
    "Structured output": "with_structured_output",
    "Prompt caching": "cache_control",
    ...
}
```

This produces a skills matrix in the portfolio that shows which patterns appear
across how many labs — a concrete demonstration of breadth.

### Claude-Generated Project Cards

Each card is generated with a short, focused prompt:

```
Lab file: 09_rag.py
Docstring: Session 09 — Retrieval-Augmented Generation with LangChain and Chroma.
Patterns used: RAG, Streaming

Write a concise markdown project card (3-4 lines): bold filename as header,
one-line description, tech used. No preamble.
```

The `generate_project_card` function calls Claude once per lab.
For a 46-session course this is ~46 API calls — under $0.10 at Sonnet pricing.

---

## Skills Matrix

The `build_portfolio` function aggregates detected patterns across all labs and
renders a Markdown table:

| Pattern | Sessions |
|---|---|
| LangGraph | 13_plan_execute_agent.py, 14_multi_agent.py, ... |
| RAG | 09_rag.py, 11_production_chatbot.py, ... |
| Structured output | 05_structured_output.py, 07_output_parsers.py, ... |

This gives a portfolio reader a quick signal of depth without reading every file.

---

## LinkedIn → Substack → Open Source Pipeline

The `draft_linkedin_post` function feeds the top 10 lab summaries to Claude
and asks for a 150-200 word professional post with at most 3 hashtags.

The natural content progression after the post:

1. **LinkedIn post** (this lab) — broadest reach, 150 words
2. **Technical blog post** — 800-word deep-dive on one capstone (Substack, Dev.to, Hashnode)
3. **Open-source repo** — clean the capstone, add a CONTRIBUTING.md, pin it
4. **Conference / meetup talk** — 20-minute talk distilled from the blog post

Each step builds on the previous signal. The portfolio is step zero.

---

## How to Open-Source a Course Project Cleanly

Before pushing a course project to a public repo:

1. **Strip secrets** — confirm `.env` is in `.gitignore`; run `git log --all -- .env` to verify
2. **Add a LICENSE** — MIT is the default; Apache-2.0 if you want patent protection
3. **Write a CONTRIBUTING.md** — even one paragraph invites collaboration
4. **Tag a release** — `v0.1.0` marks it as intentionally shipped, not accidentally public
5. **Add CI** — a single GitHub Actions workflow that runs `pytest` signals maturity

The `PORTFOLIO.md` generated by this lab is intentionally gitignored — it is a
staging artifact you review and then copy into a dedicated portfolio repo.

---

## Running the Lab

```bash
# Ensure ANTHROPIC_API_KEY is set in .env
python labs/21b_portfolio_generator.py
```

Outputs:
- `PORTFOLIO.md` at the repo root — review, edit, commit to your portfolio repo
- `PORTFOLIO_linkedin.txt` at the repo root — copy-paste into LinkedIn

---

## Key Takeaways

- AST parsing (`ast.get_docstring`) is more reliable than regex for extracting
  Python module metadata — it handles all quote styles and encoding.
- Module-level docstrings in lab files serve double duty: they document the file
  AND provide the seed text for Claude to write richer descriptions.
- A skills matrix built from source-level keyword detection gives concrete,
  verifiable evidence of technical breadth.
- Claude as a writing collaborator (not an author) keeps the portfolio authentic
  while removing the blank-page friction that stops most engineers from shipping.
