# 41 — Codebase Archaeology with Claude (Session 41)

> **Understand any GitHub repo in under an hour.** Claude reads the file tree, traces dependencies, and produces a complete architecture narrative + guided file-by-file walkthrough — the same work a senior engineer would do over days of onboarding.

---

## Roadmap — where this lesson sits in the journey

```
═══════ TRACK M: CLAUDE CODE MASTERY (optional) ═══════

  ✓ Session 38: CLAUDE.md + Settings
  ✓ Session 39: Claude Code Hooks
  ✓ Session 40: Autonomous Workflows
  ▶ Session 41: CODEBASE ARCHAEOLOGY  ◄ HERE
    Session 42: Browser Automation
    Session 43: Scheduled Cloud Routines
    Session 44: Document & Slide Generation
    Session 45: Multi-Agent Code Review Pipeline
```

**Maps to "12 Insane Claude Features" #04 — Learn Any Codebase in an Hour.**

---

## Files involved

| File | Role |
|---|---|
| [`repo_map.py`](../repo_map.py) | Builds a structured repo map (files, sizes, language, dependency graph) |
| [`architecture_summary.py`](../architecture_summary.py) | Sends the repo map to Claude and receives architecture narrative |

---

## What problem it solves

You drop into a new GitHub repo. Options:

1. **Read every file manually.** 2-3 days. You still miss implicit patterns.
2. **Ask the team.** Takes calendar time; team may not document their own mental model.
3. **Let Claude do it.** Give Claude the file tree + entry points; receive architecture narrative + guided walkthrough in minutes.

The challenge is **not** that Claude can't understand code — it can. The challenge is **how to structure the input** so Claude produces *architecture insight* rather than file summaries.

---

## The analogy

Think of Claude as a **seasoned tech lead on day one**. They don't read every file — they:
1. Look at the directory structure (what's big? what's grouped together?)
2. Find the entry points (`main.py`, `app.py`, `index.ts`)
3. Trace key imports to understand the dependency graph
4. Identify the core data structures
5. Read the README last (as a sanity check)

Your job is to give Claude that same sequence of inputs in a structured prompt.

---

## Visual

```
  GitHub Repo
       │
       ▼
  ┌─────────────────────────────┐
  │  repo_map.py                │
  │  • walk directory tree      │
  │  • collect file sizes       │
  │  • extract top-level imports│
  │  • find entry points        │
  └──────────────┬──────────────┘
                 │ structured JSON
                 ▼
  ┌─────────────────────────────┐
  │  architecture_summary.py    │
  │  Prompt to Claude:          │
  │  "Here is a repo map.       │
  │   Produce:                  │
  │   1. Architecture overview  │
  │   2. Key data flows         │
  │   3. File-by-file guide     │
  │   4. Onboarding path"       │
  └──────────────┬──────────────┘
                 │
                 ▼
        Architecture report
        (narrative + diagrams)
```

---

## Key patterns

### 1. Structured repo map prompt

Don't paste raw file listings. Build a typed map:

```python
repo_map = {
    "entry_points": ["src/main.py", "src/app.py"],
    "top_level_dirs": {
        "src/": {"files": 12, "largest": "pipeline.py (420 lines)"},
        "tests/": {"files": 8},
        "scripts/": {"files": 3},
    },
    "key_files": [
        {"path": "src/pipeline.py", "imports": ["src/models.py", "src/retriever.py"]},
        {"path": "src/models.py", "imports": ["pydantic", "sqlalchemy"]},
    ],
    "dependency_graph": {...}
}
```

Claude extracts *intent* from structure far better than from a flat `ls -R`.

### 2. Phase-gated walkthrough prompt

```
You are a senior engineer onboarding to this codebase.

Phase 1 — Architecture: what does this system do? What are its major components?
Phase 2 — Data flow: trace the lifecycle of a single request/record end-to-end.
Phase 3 — File guide: for each key file, one sentence on its role and one sentence on what to read first inside it.
Phase 4 — Onboarding path: in what order should a new engineer read the files to build a correct mental model fastest?
```

Four explicit phases → Claude produces four clean sections rather than one wall of prose.

### 3. Auto-populate CLAUDE.md

The architecture summary is the seed for `CLAUDE.md`:

```python
with open(".claude/CLAUDE.md", "w") as f:
    f.write("# Project Architecture\n\n")
    f.write(summary["architecture_overview"])
    f.write("\n\n## Key Files\n\n")
    for entry in summary["file_guide"]:
        f.write(f"- **{entry['path']}**: {entry['role']}\n")
```

Every future Claude Code session in this repo now starts with the architecture in context.

---

## Run it

```bash
# Map a local repo
python repo_map.py --path /path/to/repo --output repo_map.json

# Generate architecture summary
python architecture_summary.py --map repo_map.json --output architecture.md

# Auto-populate CLAUDE.md
python architecture_summary.py --map repo_map.json --write-claude-md
```

Expected output (`architecture.md`):

```markdown
## Architecture Overview

This is a RAG pipeline that ingests PDFs, chunks them, embeds with OpenAI,
stores in Chroma, and answers questions via a LangChain RetrievalQA chain.

## Data Flow

PDF → `ingest.py` → chunk (512 tokens, 50 overlap) → embed → Chroma
Query → `query.py` → embed → similarity search → top-4 chunks → Claude → answer

## File Guide

- **src/ingest.py** — entry point for ingestion; start here to understand chunking config
- **src/query.py** — entry point for Q&A; read after ingest.py
- **src/models.py** — Pydantic schemas; read first if touching data shapes
...

## Onboarding Path

1. README.md (context)
2. src/models.py (data shapes)
3. src/ingest.py (how data enters)
4. src/query.py (how data is used)
5. tests/test_pipeline.py (intended behavior)
```

---

## Walk-through

### What makes a good repo map

The map should be **structured, not exhaustive**. Claude doesn't need to see every file — it needs to understand *relationships*. Include:

- Entry points (what runs first)
- File sizes (large files = important logic)
- Import graph (what depends on what)
- Directory groupings (what belongs together)

Skip: test fixtures, auto-generated files, lock files.

### The architecture narrative vs. file summaries distinction

| Bad prompt | Good prompt |
|---|---|
| "Summarize each file" | "Describe the system's purpose and main components" |
| "What does models.py do?" | "What are the key data structures and how do they flow through the system?" |
| "List all the functions" | "What would I need to understand to modify the ingestion pipeline?" |

Ask Claude to think like an architect, not a documentation generator.

### Handling large repos

For repos with >200 files, filter before sending:

```python
IGNORE = {".git", "__pycache__", "node_modules", ".venv", "dist", "build"}

def is_key_file(path: str, size: int) -> bool:
    return size > 100 and not any(ignored in path for ignored in IGNORE)
```

Send Claude the top 50 files by size + all files in the root. That's usually enough.

---

## Try this

1. **Clone a repo you've never seen** — run `repo_map.py` on it, generate the summary, check whether Claude's architecture description is accurate.
2. **CLAUDE.md auto-generation** — run `--write-claude-md`, then open a new Claude Code session in that repo. Notice how quickly you can orient.
3. **Dependency graph extraction** — extend `repo_map.py` to emit a Mermaid diagram of the import graph. Ask Claude to annotate each edge with "why does A depend on B?"
4. **Onboarding quiz** — after Claude generates the onboarding path, manually read the files in that order and see if you understand the codebase. Compare to your usual approach.
5. **Cross-repo archaeology** — run on two repos that serve the same domain (e.g., two RAG implementations). Ask Claude: "What architectural trade-offs differ between these two repos?"

---

## Mental model in one line

> **Codebase archaeology is a structured prompt problem: build a typed repo map, ask Claude to think in phases (architecture → data flow → file guide → onboarding path), and auto-write the result to CLAUDE.md so every future session benefits.**

---

## Related

- **Previous:** [40 — Autonomous Workflows with Claude Code](40-autonomous-workflows.md)
- **Next:** [42 — Browser Automation & Computer Use](42-browser-automation.md)
- **CLAUDE.md output feeds:** [38 — CLAUDE.md + Settings Best Practices](38-claude-md-settings.md)
- **Maps to image feature:** #04 — Learn Any Codebase in an Hour
- **Curriculum tracker:** Session 41 of 45
