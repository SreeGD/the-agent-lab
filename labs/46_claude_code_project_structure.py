"""Claude Code Project Structure — Session 46: Mastery Lab.

This lab builds and exercises all 12 layers of the Claude Code project
structure from scratch, inside this repo. By the end you will have:

  Layer 1  CLAUDE.md         — always-loaded project identity
  Layer 2  CLAUDE.local.md   — personal overrides (gitignored)
  Layer 3  AGENTS.md         — subagent roster
  Layer 4  mcp.json          — MCP server integrations
  Layer 5  settings.json     — permissions + hooks config
  Layer 6  rules/*.md        — modular on-demand rule files
  Layer 7  commands/*.md     — custom slash commands
  Layer 8  skills/*/SKILL.md — context-triggered knowledge bundles
  Layer 9  agents/*.md       — specialist subagents
  Layer 10 hooks/*.sh        — deterministic enforcement scripts
  Layer 11 memory/*.md       — persistent cross-session context
  Layer 12 workflows/*.md    — multi-step task blueprints

Each section scaffolds the files, then DEMONSTRATES the mechanism so
you can observe what Claude is actually doing when it reads each layer.

Five mastery exercises at the end verify you can apply each layer
independently — not just scaffold it.

Run:
    python 46_claude_code_project_structure.py
    python 46_claude_code_project_structure.py --layer 8   # skill demo only
    python 46_claude_code_project_structure.py --verify    # mastery check only
    python 46_claude_code_project_structure.py --clean     # remove scaffold
"""

import argparse
import json
import math
import os
import re
import stat
import textwrap
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel, Field

load_dotenv()

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
CLAUDE_DIR = REPO_ROOT / ".claude"

MODEL = "claude-sonnet-4-6"
llm = ChatAnthropic(model=MODEL, temperature=0, max_tokens=2048)


# =====================================================================
# Scaffold definitions — every file we create
# =====================================================================

CLAUDE_MD = """\
# AgenticCourse

Educational lab monorepo for building agentic AI systems with Claude.

## Tech Stack
- Python 3.9+, LangChain, LangGraph, Streamlit
- Primary AI: Anthropic Claude (claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5)
- Parallel tracks: labs/openai/ (OpenAI) and labs/ollama/ (local Ollama)

## Layout
- labs/*.py       — numbered lesson scripts (01-46)
- labs/lessons/   — lesson markdown docs, one per session
- labs/agritech/  — AgriTech capstone engine + knowledge base
- labs/coding_agent/ — standalone tool-using agent example

## Conventions
- Lab files: NN_descriptive_name.py
- Lesson files: labs/lessons/NN-descriptive-name.md
- New sessions must be added to labs/CURRICULUM.csv
- Provider variants share the same LangGraph topology; only the LLM client differs
- Never use temperature=0 with claude-opus-4-7 (deprecated in Opus 4.x)

## Hard Rules
- Do not modify labs/farm_plans/checkpoints.sqlite directly
- Lesson files must stay under 500 lines — split if larger
- All python files must have a module-level docstring
"""

CLAUDE_LOCAL_MD = """\
# Local Overrides (not committed — gitignored)

## My Environment
- Python: /opt/anaconda3/bin/python
- Projects root: ~/projects/

## Personal Preferences
- Show token counts in every API response
- Prefer async/await patterns over threading for I/O-bound work
- Include runnable examples in every explanation

## Experimental Rules
- Try: suggest a "Try This" follow-up task after every code change
"""

AGENTS_MD = """\
# Agent Roster

Defines every subagent role. Claude reads this before delegating to prevent
overlap and coordinate multi-agent sessions.

## @security-reviewer
**Role:** Security vulnerability specialist
**Focus:** OWASP top 10, injection, auth gaps, SSRF, hardcoded secrets
**Tools:** Read, Bash(grep:*), WebFetch
**Invoke when:** Code touches auth, user input, external APIs, or file paths
**Hands off to:** @test-writer after flagging CRITICAL findings

## @test-writer
**Role:** Test suite author
**Focus:** pytest, edge cases, property-based testing with hypothesis
**Tools:** Read, Write, Bash(pytest:*)
**Invoke when:** New functions or modules are added
**Hands off to:** main session when tests pass

## @research
**Role:** Technical researcher
**Focus:** Web search, documentation lookup, RFC/spec reading
**Tools:** WebSearch, WebFetch
**Invoke when:** Uncertain about library API, external standard, or best practice
**Output format:** Concise summary + sources; no code

## @doc-writer
**Role:** Documentation specialist
**Focus:** Docstrings, lesson markdown, README sections
**Tools:** Read, Write
**Invoke when:** New public functions/classes added or lesson files need updating
**Output format:** Markdown ready to paste; no meta-commentary
"""

MCP_JSON = {
    "mcpServers": {
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem",
                     str(REPO_ROOT)],
        },
    }
}

SETTINGS_JSON = {
    "permissions": {
        "allow": [
            "Bash(python:*)",
            "Bash(git status)",
            "Bash(git diff:*)",
            "Bash(git log:*)",
            "Bash(git add:*)",
            "Bash(git commit:*)",
            "Bash(pytest:*)",
            "Bash(ruff:*)",
            "Read(labs/**)",
            "Write(labs/**)",
            "WebFetch",
            "WebSearch",
        ],
        "deny": [
            "Bash(rm -rf:*)",
            "Bash(git push --force:*)",
            "Bash(git reset --hard:*)",
            "Write(.env)",
            "Write(labs/farm_plans/checkpoints.sqlite)",
        ],
    },
    "hooks": {
        "PreToolUse": [
            {"command": str(CLAUDE_DIR / "hooks" / "validate-code.sh")}
        ],
        "PostToolUse": [
            {"command": str(CLAUDE_DIR / "hooks" / "post-edit-format.sh")}
        ],
    },
}

RULES = {
    "code-style.md": """\
# Code Style Rules

## Python
- Type hints on all public function signatures
- Descriptive names with auxiliary verbs: is_active, has_permission, should_retry
- No single-letter variables except loop indices (i, j, k)
- Early returns over deep nesting
- Max function length: 50 lines — split if longer
- No commented-out code — delete or commit

## Imports
- stdlib → third-party → local (separated by blank lines)
- Absolute imports only; no relative imports

## Comments
- Write WHY, not WHAT — code explains what, comments explain intent
- No multi-line comment blocks; one short line max
- No docstring novels — one sentence for simple functions

## Formatting
- ruff format is the enforcer; do not argue with it
""",
    "api-conventions.md": """\
# API Conventions

## FastAPI routes
- Path params for resource identity: /users/{user_id}
- Query params for filtering/pagination: ?limit=20&offset=0
- Request bodies via Pydantic models — never raw dicts
- Always return typed response models (not dict)
- HTTP 422 for validation errors (FastAPI default — keep it)
- HTTP 409 for business-logic conflicts (not 400)

## LangChain / LangGraph
- Use with_structured_output() for typed LLM responses
- Prefer ainvoke/astream for all production I/O-bound calls
- State TypedDict over dataclass — LangGraph requires it
- Never mutate state in place — return a new dict slice

## Anthropic SDK (direct)
- claude-opus-4-7: no temperature parameter (deprecated in 4.x)
- claude-sonnet-4-6, claude-haiku-4-5: temperature=0 for determinism
- Always set max_tokens explicitly — never rely on default
""",
    "testing-standard.md": """\
# Testing Standard

## Framework
pytest only. No unittest.

## File layout
- tests/unit/test_<module>.py        — unit tests
- tests/integration/test_<feature>.py — integration tests
- tests/conftest.py                  — shared fixtures

## Naming
test_<function>_<scenario>_<expected>
Example: test_resume_tailor_empty_jd_raises_value_error

## Coverage requirements
- Every new public function: 1 happy-path + 1 edge-case test minimum
- Every bug fix: a regression test that would have caught the bug

## What NOT to test
- Private helpers — test via the public function that calls them
- LLM output content — test structure and schema, not wording
- LangGraph internals — test the graph's input→output contract only
""",
    "pr.md": """\
# PR Conventions

## Title format
type: short description (under 70 chars)
Types: feat | fix | refactor | docs | test | chore

## Body must include
- What changed (2-5 bullets)
- Why it changed (1 sentence)
- How to test it (runnable command)

## Checklist before merge
- [ ] Tests pass: pytest labs/ -x
- [ ] Ruff clean: ruff check labs/
- [ ] CURRICULUM.csv updated if new session added
- [ ] Lesson file created/updated to match lab file

## Branch strategy
- Feature branches off master
- No direct push to master (hook enforced)
- Squash merge preferred for single-session work
""",
}

COMMANDS = {
    "review.md": """\
Review the current diff for correctness, security, and style.

Steps:
1. Run `git diff HEAD` to see all staged and unstaged changes
2. Check for CRITICAL security issues first (injection, hardcoded secrets, missing auth)
3. Check logic correctness (null deref, off-by-one, missing edge cases)
4. Check style against .claude/rules/code-style.md
5. Output findings grouped by severity: CRITICAL → MAJOR → MINOR → LOW

Format each finding as:
`file:line — [SEVERITY] title — one-line fix suggestion`

If $ARGUMENTS contains "fix", apply fixes for MINOR and LOW findings automatically.
""",
    "scaffold.md": """\
Scaffold a new lab session for session number $ARGUMENTS.

Steps:
1. Determine the session title and track from labs/CURRICULUM.csv (row matching session $ARGUMENTS)
2. Create labs/NN_descriptive_name.py with:
   - Module-level docstring explaining the session goal
   - Standard imports (dotenv, langchain_anthropic, pydantic)
   - A main() function and `if __name__ == "__main__":` block
   - A TODO placeholder for the core implementation
3. Create labs/lessons/NN-descriptive-name.md with the lesson template:
   - Title, roadmap, files table, problem statement, analogy, visual, key patterns, run-it, try-this, mental model, related
4. Print the paths of all created files
5. Remind the user to add the session to CURRICULUM.csv if not already there
""",
    "deploy.md": """\
Deploy the current branch to the staging environment.

Steps:
1. Run `git status` — abort if there are uncommitted changes
2. Run `pytest labs/ -x` — abort if any test fails
3. Run `ruff check labs/` — abort if any lint errors
4. Push the current branch: `git push origin HEAD`
5. Report the pushed branch name and last commit hash
6. Remind the user to open a PR if not already open

Never push directly to master. If on master, abort and ask the user to create a branch.
""",
}

SKILLS = {
    "code-review": {
        "description": (
            "Use when reviewing code for bugs, security vulnerabilities, style issues, "
            "or correctness problems. Also triggers when asked to review a PR, diff, branch, "
            "or file. Provides the 4-specialist parallel pattern (security, logic, style, docs), "
            "severity classification schema, and confidence filtering."
        ),
        "body": """\
# Code Review Pattern (AgenticCourse)

## Four specialist roles — run in parallel
1. **Security** — OWASP top 10, injection, hardcoded secrets, auth gaps, SSRF
2. **Logic** — null deref, off-by-one, missing edge cases, race conditions, wrong status codes
3. **Style** — naming, complexity, duplication, magic numbers, dead code
4. **Docs** — missing docstrings, outdated comments, TODO/FIXME without tickets

## Severity schema
| Severity | Meaning |
|---|---|
| CRITICAL | Exploitable / data-loss risk — block merge |
| MAJOR | Wrong behavior for common inputs — fix before merge |
| MINOR | Edge-case issue or style — fix at discretion |
| LOW | Best-practice gap — informational |

## Output format
`file.py:line — [SEVERITY] title — concrete fix`

## Confidence threshold
Only report findings with confidence > 0.75.
Low-confidence findings go in a "Needs human review" section, not the main list.
""",
    },
    "testing-patterns": {
        "description": (
            "Use when writing tests, debugging failing tests, designing test suites, "
            "or deciding what to test in Python code. Provides pytest patterns, fixture design, "
            "LLM output testing strategy, and coverage guidance for LangChain/LangGraph code."
        ),
        "body": """\
# Testing Patterns (AgenticCourse)

## LLM output testing — test structure, not wording
```python
def test_resume_tailor_returns_required_sections(jd_fixture, resume_fixture):
    result = tailor_resume(jd_fixture, resume_fixture)
    assert "Experience" in result        # section exists
    assert len(result.split("\\n")) > 10  # non-trivial content
    # Never: assert "Python" in result   — LLM wording is non-deterministic
```

## LangGraph graph testing — test input→output contract
```python
def test_farm_planner_produces_plan(mock_llm):
    state = {"profile": SAMPLE_PROFILE, "plan": None}
    result = graph.invoke(state)
    assert result["plan"] is not None
    assert "crop" in result["plan"]
```

## Fixture patterns
```python
@pytest.fixture
def sample_jd():
    return Path("tests/fixtures/software_engineer_jd.txt").read_text()

@pytest.fixture
def mock_llm(monkeypatch):
    monkeypatch.setattr("labs.module.llm", FakeLLM(response="test output"))
```

## Edge cases that always need a test
- Empty string / empty list input
- None input where not expected
- Single-item list (not just multi-item)
- Maximum length / boundary input
""",
    },
    "pr-description": {
        "description": (
            "Use when writing a pull request title or description, or when asked to "
            "summarise changes for a PR, commit message, or changelog entry. "
            "Provides the repo's PR format, title conventions, and required checklist."
        ),
        "body": """\
# PR Description Template (AgenticCourse)

## Title format
`type: short description (under 70 chars)`
Types: feat | fix | refactor | docs | test | chore

## Body template
```markdown
## What changed
- Bullet 1
- Bullet 2

## Why
One sentence on the motivation.

## How to test
```bash
python labs/NN_file.py
```

## Checklist
- [ ] pytest labs/ -x passes
- [ ] ruff check labs/ clean
- [ ] CURRICULUM.csv updated (if new session)
- [ ] Lesson file matches lab file
```

## Commit message style
Same type prefix as PR title.
Co-Authored-By line at the end when Claude helped write the code.
""",
    },
}

AGENTS = {
    "security-reviewer.md": """\
---
name: security-reviewer
description: Security vulnerability specialist. Invoke with @security-reviewer when
  code touches authentication, user input handling, external API calls, file system
  operations, or any area where injection or data-exposure risk exists.
tools: Read, Bash(grep:*), WebFetch
---

You are a security engineer performing targeted code review.

Focus EXCLUSIVELY on security vulnerabilities. Ignore style, performance, and logic
unless they directly create a security risk.

For each finding return:
- File and line number
- Severity: CRITICAL / MAJOR / MINOR
- One-sentence description of the vulnerability
- One concrete fix

Sort findings by severity (CRITICAL first).
Return as a markdown numbered list.
Do not summarise files that have no findings — silence is the correct output for clean code.
""",
    "test-writer.md": """\
---
name: test-writer
description: Test suite author. Invoke with @test-writer when new functions or modules
  are added, when asked to write tests, or when coverage needs to be improved.
  Writes pytest tests following the project's testing-standard.md conventions.
tools: Read, Write, Bash(pytest:*)
---

You are a senior engineer who writes pytest test suites.

Conventions (from .claude/rules/testing-standard.md):
- One happy-path test + one edge-case test per new public function
- Never test LLM output wording — test schema and structure only
- Name tests: test_<function>_<scenario>_<expected_outcome>
- Put fixtures in tests/conftest.py
- Run the tests after writing them and fix any that fail

After writing tests, run `pytest <test_file> -v` and report results.
""",
    "research.md": """\
---
name: research
description: Technical researcher. Invoke with @research when uncertain about a
  library API, external standard, RFC, or best practice. Returns a concise summary
  with sources — does not write code.
tools: WebSearch, WebFetch
---

You are a technical researcher. Your job is to find accurate, current information.

Rules:
- Search multiple sources before concluding
- Cite every claim with a URL
- Flag information that might be stale (> 1 year old)
- Return a structured summary: finding → evidence → confidence
- Do NOT write code — the main session handles implementation
- Keep the summary under 300 words
""",
}

HOOKS = {
    "validate-code.sh": """\
#!/usr/bin/env bash
# PreToolUse hook: block destructive commands before Claude executes them.
# Exit 2 = block the tool call. Exit 0 = allow.

TOOL="$CLAUDE_TOOL_NAME"
INPUT="$CLAUDE_TOOL_INPUT"

if [[ "$TOOL" == "Bash" ]]; then
    # Block destructive patterns
    if echo "$INPUT" | grep -qE 'rm -rf|git push --force|git reset --hard|DROP TABLE|truncate'; then
        echo "ERROR: Destructive command blocked by validate-code.sh hook" >&2
        exit 2
    fi
    # Block direct push to master/main
    if echo "$INPUT" | grep -qE 'git push.*(master|main)($| )'; then
        echo "ERROR: Direct push to master blocked. Use a feature branch and PR." >&2
        exit 2
    fi
fi

exit 0
""",
    "post-edit-format.sh": """\
#!/usr/bin/env bash
# PostToolUse hook: auto-format Python files after every Edit or Write.
# Exit 0 always (formatters should not block).

TOOL="$CLAUDE_TOOL_NAME"

if [[ "$TOOL" == "Edit" || "$TOOL" == "Write" ]]; then
    # Extract file_path from tool result JSON
    FILE=$(echo "$CLAUDE_TOOL_RESULT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

    if [[ "$FILE" == *.py && -f "$FILE" ]]; then
        ruff format "$FILE" 2>/dev/null || true
        echo "  [hook] auto-formatted $FILE"
    fi
fi

exit 0
""",
    "block-sensitive-writes.sh": """\
#!/usr/bin/env bash
# PreToolUse hook: block writes to sensitive files.
# Exit 2 = block. Exit 0 = allow.

TOOL="$CLAUDE_TOOL_NAME"
INPUT="$CLAUDE_TOOL_INPUT"

if [[ "$TOOL" == "Write" || "$TOOL" == "Edit" ]]; then
    FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

    # Block writes to sensitive files
    if echo "$FILE" | grep -qE '\\.env$|\\.sqlite$|secrets\\.|credentials\\.'; then
        echo "ERROR: Write to sensitive file '$FILE' blocked by hook." >&2
        exit 2
    fi
fi

exit 0
""",
}

MEMORY = {
    "decisions.md": """\
---
name: architectural-decisions
description: Key architectural decisions for AgenticCourse — what we chose and why.
metadata:
  type: project
---

# Architectural Decisions

## 2026-06-23: temperature deprecated for claude-opus-4-7
Anthropic deprecated the `temperature` parameter for Opus 4.x models.
All `ChatAnthropic` calls using Opus must omit `temperature` entirely.
Sonnet and Haiku still accept `temperature=0`.
**Why:** API returned 400 BadRequestError on session 41 demo run.
**How to apply:** Check model name before setting temperature. Opus 4.x = no temperature.

## 2026-06-22: Provider-adapter pattern for all capstone engines
Each major engine exists in three variants (Anthropic, OpenAI, Ollama).
They share identical LangGraph topology and Pydantic state schema.
Only the LLM client and model name differ. UI uses importlib to select at runtime.
**Why:** Course teaches provider-agnostic agentic patterns.
**How to apply:** When adding a new lab that uses LLM calls, add all three variants.

## 2026-05-21: SQLite checkpointer for farm planner
LangGraph SqliteSaver persists state between restarts, keyed by uuid thread_id.
**Why:** Users need to resume interrupted farm plans without re-running all agents.
**How to apply:** Never delete the sqlite file mid-run. Each plan gets its own thread_id.
""",
    "progress.md": """\
---
name: session-progress
description: Current work state for AgenticCourse — what's done, active, and next.
metadata:
  type: project
---

# Current Progress

## Completed
- Track M Sessions 38-46: all lesson files and lab py files created
- AgriTech capstone (Session 34): engine + UI + Telangana knowledge base
- Yield optimizer engine: built, lesson pending

## Active
- Session 46 scaffold: .claude/ directory structure built in this session

## Next
- Run mastery exercises from Session 46
- Add tests for Sessions 41-46 lab files
- Consider Ollama/OpenAI variants for Sessions 41-43
""",
    "project-context.md": """\
---
name: project-context
description: Stable facts about AgenticCourse that every session needs.
metadata:
  type: project
---

# Project Context

## What this is
A 46-session educational lab monorepo teaching agentic AI system design.
Sessions are numbered and progressive; each builds on prior sessions.
Track M (Sessions 38-46) covers Claude Code itself as the target skill.

## Primary audience
Engineers building production agentic AI systems; intermediate Python level.

## Key constraints
- Python 3.9+ (some labs use match/case — requires 3.10+)
- Anthropic API key required (ANTHROPIC_API_KEY in .env)
- HuggingFace local embeddings for skill router (no extra API key)
- Ollama track requires local Ollama installation with llama3.2 model

## Repo owner
GitHub: SreeGD/AgenticCourse
""",
}

WORKFLOWS = {
    "feature-build.md": """\
# Workflow: Feature Build

Use when building a new lab session or feature from a spec or curriculum entry.

## Steps

### 1. Understand
- Read the CURRICULUM.csv row for the target session
- Read the matching lesson file in labs/lessons/
- Ask clarifying questions if scope is ambiguous

### 2. Plan
- Write a 3-7 bullet implementation plan
- Confirm the plan with the user before writing code

### 3. Build
- Create the lab .py file following code-style.md
- Follow the existing file naming: NN_descriptive_name.py
- Add type hints to all public functions
- Include a module-level docstring and `if __name__ == "__main__":` block

### 4. Test
- Write at least 2 tests per new public function
- Run: pytest tests/ -x (stop on first failure)

### 5. Review
- Run /project:review on the diff
- Fix all CRITICAL and MAJOR findings

### 6. Document
- Update memory/progress.md
- Ensure lesson file matches lab file scope

### 7. Commit
- Stage only relevant files
- Follow PR conventions in .claude/rules/pr.md
""",
    "bug-fix.md": """\
# Workflow: Bug Fix

Use when diagnosing and fixing a bug or test failure.

## Steps

### 1. Reproduce
- Get the exact error message and stack trace
- Identify the minimal input that triggers the bug

### 2. Diagnose
- Read the failing code and its direct dependencies
- State the root cause in one sentence before proposing a fix

### 3. Fix
- Change only what is necessary to fix the root cause
- Do not refactor surrounding code in the same commit

### 4. Regression test
- Write a test that would have caught this bug
- Confirm it fails on the unfixed code, passes after the fix

### 5. Commit
- Reference the bug description in the commit message
- Include the regression test in the same commit

### 6. Update memory
- If the bug reveals a systemic issue, add to memory/decisions.md
""",
    "code-review.md": """\
# Workflow: Code Review

Use when reviewing a PR, branch diff, or set of changed files.

## Steps

### 1. Get the diff
- For a PR: `gh pr diff <number>`
- For a branch: `git diff main...HEAD`
- For specific files: `git diff HEAD -- <file>`

### 2. Fan out to specialists
- Invoke @security-reviewer on the diff
- Invoke @test-writer to assess test coverage gaps
- Run /project:review for style and logic

### 3. Consolidate
- Merge findings from all reviewers
- Deduplicate by file:line
- Sort: CRITICAL → MAJOR → MINOR → LOW

### 4. Report
- Post findings as inline comments if reviewing a GitHub PR
- Summarise in one paragraph: overall quality, top risk, recommended action

### 5. Follow up
- Block merge if any unresolved CRITICAL findings
- Request changes for MAJOR findings
- Leave MINOR/LOW as suggestions at reviewer discretion
""",
}


# =====================================================================
# Builder — writes all scaffold files
# =====================================================================

def scaffold(dry_run: bool = False) -> list[str]:
    created = []

    def write(path: Path, content: str, executable: bool = False):
        if dry_run:
            created.append(f"[dry-run] {path.relative_to(REPO_ROOT)}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content)
            if executable:
                path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            created.append(str(path.relative_to(REPO_ROOT)))

    # Layer 1: CLAUDE.md
    write(REPO_ROOT / "CLAUDE.md", CLAUDE_MD)

    # Layer 2: CLAUDE.local.md (ensure gitignored)
    write(REPO_ROOT / "CLAUDE.local.md", CLAUDE_LOCAL_MD)
    gitignore = REPO_ROOT / ".gitignore"
    if gitignore.exists() and "CLAUDE.local.md" not in gitignore.read_text():
        with open(gitignore, "a") as f:
            f.write("\nCLAUDE.local.md\n")
        created.append("  (added CLAUDE.local.md to .gitignore)")

    # Layer 3: AGENTS.md
    write(REPO_ROOT / "AGENTS.md", AGENTS_MD)

    # Layer 4: mcp.json
    write(REPO_ROOT / "mcp.json", json.dumps(MCP_JSON, indent=2))

    # Layer 5: settings.json
    write(CLAUDE_DIR / "settings.json", json.dumps(SETTINGS_JSON, indent=2))

    # Layer 6: rules/
    for fname, content in RULES.items():
        write(CLAUDE_DIR / "rules" / fname, content)

    # Layer 7: commands/
    for fname, content in COMMANDS.items():
        write(CLAUDE_DIR / "commands" / fname, content)

    # Layer 8: skills/
    for skill_name, skill in SKILLS.items():
        skill_md = f"---\nname: {skill_name}\ndescription: {skill['description']}\n---\n\n{skill['body']}\n"
        write(CLAUDE_DIR / "skills" / skill_name / "SKILL.md", skill_md)

    # Layer 9: agents/
    for fname, content in AGENTS.items():
        write(CLAUDE_DIR / "agents" / fname, content)

    # Layer 10: hooks/
    for fname, content in HOOKS.items():
        write(CLAUDE_DIR / "hooks" / fname, content, executable=True)

    # Layer 11: memory/
    for fname, content in MEMORY.items():
        write(CLAUDE_DIR / "memory" / fname, content)

    # Layer 12: workflows/
    for fname, content in WORKFLOWS.items():
        write(CLAUDE_DIR / "workflows" / fname, content)

    return created


def clean():
    import shutil
    removed = []
    for path in [
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "CLAUDE.local.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "mcp.json",
        CLAUDE_DIR / "settings.json",
        CLAUDE_DIR / "rules",
        CLAUDE_DIR / "commands",
        CLAUDE_DIR / "skills",
        CLAUDE_DIR / "agents",
        CLAUDE_DIR / "hooks",
        CLAUDE_DIR / "memory",
        CLAUDE_DIR / "workflows",
    ]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(str(path.relative_to(REPO_ROOT)))
    return removed


# =====================================================================
# Demo helpers
# =====================================================================

def section(title: str, width: int = 70):
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def subsection(title: str):
    print(f"\n── {title} ──")


# =====================================================================
# DEMO 1: CLAUDE.md — show what Claude sees on session start
# =====================================================================

def demo_layer1_claude_md():
    section("LAYER 1 — CLAUDE.md (loaded every session)")
    content = (REPO_ROOT / "CLAUDE.md").read_text()
    print(f"\nFile: CLAUDE.md ({len(content.splitlines())} lines)")
    print("\nWhat Claude reads at the start of every session:")
    print("─" * 50)
    for line in content.splitlines()[:20]:
        print(f"  {line}")
    print("  ...")
    print(f"\n→ Every session starts with this context pre-loaded, zero tokens wasted re-explaining.")
    print(f"  Critical: keep it under 200 lines. Every line is paid for on every call.")


# =====================================================================
# DEMO 2: settings.json — show allow/deny enforcement
# =====================================================================

def demo_layer5_settings():
    section("LAYER 5 — settings.json (permissions + hooks config)")
    settings = json.loads((CLAUDE_DIR / "settings.json").read_text())

    print("\nAllow list (Claude CAN run these):")
    for item in settings["permissions"]["allow"]:
        print(f"  ✓ {item}")

    print("\nDeny list (Claude CANNOT run these — hook blocks at PreToolUse):")
    for item in settings["permissions"]["deny"]:
        print(f"  ✗ {item}")

    print("\nHooks wired:")
    for event, hooks in settings["hooks"].items():
        for h in hooks:
            print(f"  {event}: {h['command']}")

    print("\n→ Permissions are enforced by the Claude Code runtime — Claude cannot override them.")
    print("  Hooks fire before/after every tool call via shell scripts (Layer 10).")


# =====================================================================
# DEMO 3: hooks — simulate PreToolUse enforcement
# =====================================================================

def demo_layer10_hooks():
    section("LAYER 10 — hooks (deterministic enforcement)")

    test_cases = [
        ("Bash", "git diff HEAD", True),
        ("Bash", "rm -rf /tmp/test", False),
        ("Bash", "git push --force origin master", False),
        ("Bash", "git push origin feature/my-branch", True),
        ("Bash", "pytest labs/ -x", True),
        ("Write", '{"file_path": ".env"}', False),
        ("Write", '{"file_path": "labs/46_demo.py"}', True),
    ]

    # Simplified hook logic mirroring the shell scripts
    BLOCK_PATTERNS = [
        re.compile(r"rm -rf", re.I),
        re.compile(r"git push --force", re.I),
        re.compile(r"git reset --hard", re.I),
        re.compile(r"DROP TABLE", re.I),
        re.compile(r"git push.*(master|main)($|\s)", re.I),
    ]
    SENSITIVE_FILES = re.compile(r"\.(env|sqlite)$|secrets\.|credentials\.")

    def simulate_hook(tool: str, inp: str) -> tuple[bool, str]:
        if tool == "Bash":
            for pattern in BLOCK_PATTERNS:
                if pattern.search(inp):
                    return False, f"blocked: matched '{pattern.pattern}'"
            return True, "allowed"
        elif tool in ("Write", "Edit"):
            try:
                file_path = json.loads(inp).get("file_path", "")
                if SENSITIVE_FILES.search(file_path):
                    return False, f"blocked: sensitive file '{file_path}'"
            except Exception:
                pass
            return True, "allowed"
        return True, "allowed"

    print(f"\n{'TOOL':<8} {'INPUT':<45} {'RESULT'}")
    print("─" * 70)
    all_correct = True
    for tool, inp, expected_allow in test_cases:
        allowed, reason = simulate_hook(tool, inp)
        status = "✓ ALLOW" if allowed else "✗ BLOCK"
        flag = "" if allowed == expected_allow else " ← UNEXPECTED"
        if allowed != expected_allow:
            all_correct = False
        display_inp = inp[:42] + "..." if len(inp) > 42 else inp
        print(f"  {tool:<8} {display_inp:<45} {status}  {reason}{flag}")

    print(f"\n→ {'All 7 hook decisions correct.' if all_correct else 'Some decisions unexpected — review hook logic.'}")
    print("  Hooks are shell scripts: deterministic, fast, no LLM involved.")
    print("  This is the only layer that CANNOT be reasoned around.")


# =====================================================================
# DEMO 4: skills — show triggering by cosine similarity
# =====================================================================

def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def demo_layer8_skills():
    section("LAYER 8 — skills (context-triggered knowledge bundles)")

    skills_dir = CLAUDE_DIR / "skills"
    skill_files = list(skills_dir.glob("**/SKILL.md"))
    if not skill_files:
        print("  No skill files found — scaffold first.")
        return

    FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
    skills_data = []
    for path in sorted(skill_files):
        text = path.read_text()
        m = FRONTMATTER_RE.match(text.strip())
        if m:
            fm = yaml.safe_load(m.group(1))
            skills_data.append({"name": fm["name"], "description": fm["description"]})

    print(f"\nLoaded {len(skills_data)} skills:")
    for s in skills_data:
        desc_preview = s["description"][:70] + "..." if len(s["description"]) > 70 else s["description"]
        print(f"  [{s['name']}] {desc_preview}")

    print("\nEmbedding skill descriptions (HuggingFace all-MiniLM-L6-v2)...")
    embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    skill_vectors = embedder.embed_documents([s["description"] for s in skills_data])

    test_queries = [
        "Can you review this PR for security issues?",
        "Write pytest tests for my new function",
        "Help me write the PR description for this branch",
        "What's the weather in Tokyo today?",
        "How do I deploy to production?",
    ]

    THRESHOLD = 0.30
    print(f"\n{'QUERY':<50} {'FIRES'}")
    print("─" * 70)
    for query in test_queries:
        q_vec = embedder.embed_query(query)
        scores = [(s["name"], cosine(q_vec, v)) for s, v in zip(skills_data, skill_vectors)]
        best_name, best_score = max(scores, key=lambda x: x[1])
        fires = best_name if best_score >= THRESHOLD else "(no skill fires)"
        icon = "►" if best_score >= THRESHOLD else " "
        display_q = query[:48] + ".." if len(query) > 48 else query
        print(f"  {icon} {display_q:<50} {fires}  ({best_score:.3f})")

    print(f"\n→ Threshold: {THRESHOLD}. Below it, no skill loads — context stays lean.")
    print("  The description IS the trigger. Bad description = skill never fires.")


# =====================================================================
# DEMO 5: memory — show cross-session persistence in action
# =====================================================================

def demo_layer11_memory():
    section("LAYER 11 — memory (persistent cross-session context)")
    memory_dir = CLAUDE_DIR / "memory"
    files = list(memory_dir.glob("*.md"))
    print(f"\n{len(files)} memory files:")
    for f in sorted(files):
        lines = f.read_text().splitlines()
        # Find first non-frontmatter, non-empty heading
        heading = next((l for l in lines if l.startswith("#") and not l.startswith("---")), f.name)
        print(f"  {f.name:<30} → {heading}")

    subsection("Simulating a session that updates memory")
    # Ask Claude to identify one new decision from this session to write to memory
    decisions_path = memory_dir / "decisions.md"
    current = decisions_path.read_text()

    response = llm.invoke([
        SystemMessage(
            "You are a memory manager for a Claude Code project. "
            "You receive the current memory/decisions.md and a session summary. "
            "If there is a new architectural decision worth recording, append it. "
            "Return ONLY the new entry to append (not the whole file), in the same format. "
            "If nothing new to add, return the string 'NO_UPDATE'."
        ),
        HumanMessage(
            f"Current memory/decisions.md:\n{current}\n\n"
            "Session summary: We ran the repo map tool (41_repo_map.py) on AgenticCourse "
            "and discovered 299 files. The architecture summary revealed that the farm planner "
            "engine is the single most important file. We scaffolded the full .claude/ directory "
            "using the Session 46 lab script. We confirmed the temperature deprecation workaround "
            "for claude-opus-4-7 by removing the temperature parameter."
        ),
    ])

    new_entry = response.content.strip()
    if new_entry != "NO_UPDATE":
        print(f"\n  Claude identified a new memory entry:")
        print(textwrap.indent(new_entry[:300], "    "))
        decisions_path.write_text(current.rstrip() + "\n\n" + new_entry + "\n")
        print(f"\n  → Appended to memory/decisions.md")
    else:
        print("\n  → No new decisions to record (memory already up to date)")

    print("\n→ Memory files are committed to git — the whole team benefits from shared context.")
    print("  They compensate for context loss between sessions in long-running projects.")


# =====================================================================
# DEMO 6: full layer interaction walkthrough
# =====================================================================

def demo_full_session():
    section("FULL SESSION WALKTHROUGH — all layers interacting")
    print("""
  Scenario: Developer types "@security-reviewer review the auth changes"

  ① Claude reads CLAUDE.md                   [Layer 1] → knows repo layout + hard rules
  ② Claude reads AGENTS.md                   [Layer 3] → finds @security-reviewer definition
  ③ Claude reads settings.json               [Layer 5] → confirms tools @security-reviewer can use
  ④ hooks/validate-code.sh fires (PreToolUse)[Layer 10]→ checks every tool call before exec
  ⑤ skills/code-review/SKILL.md loads        [Layer 8] → cosine match on "review auth changes"
  ⑥ @security-reviewer agent spawned         [Layer 9] → isolated context, own system prompt
  ⑦ Agent reads .claude/rules/api-conventions[Layer 6] → knows what "correct auth" means here
  ⑧ Agent completes, hands back to main session
  ⑨ Claude updates memory/progress.md        [Layer 11]→ records "reviewed PR #47 auth changes"
  ⑩ Workflow: code-review.md resumes         [Layer 12]→ next step: "Consolidate findings"

  Every layer has ONE job. No layer does another layer's job.
  The result: 10 layers coordinated without a single line of routing code.
    """)


# =====================================================================
# Mastery check — verify the scaffold is complete and correct
# =====================================================================

REQUIRED_FILES = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "CLAUDE.local.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "mcp.json",
    CLAUDE_DIR / "settings.json",
    CLAUDE_DIR / "rules" / "code-style.md",
    CLAUDE_DIR / "rules" / "api-conventions.md",
    CLAUDE_DIR / "rules" / "testing-standard.md",
    CLAUDE_DIR / "rules" / "pr.md",
    CLAUDE_DIR / "commands" / "review.md",
    CLAUDE_DIR / "commands" / "scaffold.md",
    CLAUDE_DIR / "commands" / "deploy.md",
    CLAUDE_DIR / "skills" / "code-review" / "SKILL.md",
    CLAUDE_DIR / "skills" / "testing-patterns" / "SKILL.md",
    CLAUDE_DIR / "skills" / "pr-description" / "SKILL.md",
    CLAUDE_DIR / "agents" / "security-reviewer.md",
    CLAUDE_DIR / "agents" / "test-writer.md",
    CLAUDE_DIR / "agents" / "research.md",
    CLAUDE_DIR / "hooks" / "validate-code.sh",
    CLAUDE_DIR / "hooks" / "post-edit-format.sh",
    CLAUDE_DIR / "hooks" / "block-sensitive-writes.sh",
    CLAUDE_DIR / "memory" / "decisions.md",
    CLAUDE_DIR / "memory" / "progress.md",
    CLAUDE_DIR / "memory" / "project-context.md",
    CLAUDE_DIR / "workflows" / "feature-build.md",
    CLAUDE_DIR / "workflows" / "bug-fix.md",
    CLAUDE_DIR / "workflows" / "code-review.md",
]


def verify():
    section("MASTERY CHECK — verifying all 12 layers are complete")
    layers = {
        "Layer 1  CLAUDE.md":           [REPO_ROOT / "CLAUDE.md"],
        "Layer 2  CLAUDE.local.md":     [REPO_ROOT / "CLAUDE.local.md"],
        "Layer 3  AGENTS.md":           [REPO_ROOT / "AGENTS.md"],
        "Layer 4  mcp.json":            [REPO_ROOT / "mcp.json"],
        "Layer 5  settings.json":       [CLAUDE_DIR / "settings.json"],
        "Layer 6  rules/*.md (4)":      [CLAUDE_DIR / "rules" / f for f in RULES],
        "Layer 7  commands/*.md (3)":   [CLAUDE_DIR / "commands" / f for f in COMMANDS],
        "Layer 8  skills (3 dirs)":     [CLAUDE_DIR / "skills" / n / "SKILL.md" for n in SKILLS],
        "Layer 9  agents/*.md (3)":     [CLAUDE_DIR / "agents" / f for f in AGENTS],
        "Layer 10 hooks/*.sh (3)":      [CLAUDE_DIR / "hooks" / f for f in HOOKS],
        "Layer 11 memory/*.md (3)":     [CLAUDE_DIR / "memory" / f for f in MEMORY],
        "Layer 12 workflows/*.md (3)":  [CLAUDE_DIR / "workflows" / f for f in WORKFLOWS],
    }

    all_pass = True
    for layer_label, paths in layers.items():
        missing = [p for p in paths if not p.exists()]
        if missing:
            status = f"✗ MISSING: {[str(p.relative_to(REPO_ROOT)) for p in missing]}"
            all_pass = False
        else:
            status = f"✓ ({len(paths)} file{'s' if len(paths) > 1 else ''})"
        print(f"  {layer_label:<35} {status}")

    # Settings sanity check
    try:
        settings = json.loads((CLAUDE_DIR / "settings.json").read_text())
        has_allow = len(settings.get("permissions", {}).get("allow", [])) > 0
        has_deny = len(settings.get("permissions", {}).get("deny", [])) > 0
        has_hooks = len(settings.get("hooks", {})) > 0
        settings_ok = has_allow and has_deny and has_hooks
    except Exception:
        settings_ok = False

    print(f"\n  settings.json has allow+deny+hooks: {'✓' if settings_ok else '✗'}")

    # Hook executable check
    for fname in HOOKS:
        hook_path = CLAUDE_DIR / "hooks" / fname
        if hook_path.exists():
            is_exec = os.access(hook_path, os.X_OK)
            print(f"  {fname} is executable: {'✓' if is_exec else '✗ (run: chmod +x)'}")

    # Skill description quality check (length)
    for skill_name, skill in SKILLS.items():
        desc_words = len(skill["description"].split())
        quality = "✓ good" if 20 <= desc_words <= 80 else f"✗ {desc_words} words (target: 20-80)"
        print(f"  Skill '{skill_name}' description ({desc_words} words): {quality}")

    print()
    if all_pass and settings_ok:
        print("  ✓ ALL 12 LAYERS COMPLETE — structure is ready for Claude Code.")
        print("\n  Open a new Claude Code session in this repo and observe:")
        print("  - CLAUDE.md loads automatically")
        print("  - Type / to see commands/review, commands/scaffold, commands/deploy")
        print("  - Type a query about code review — skills/code-review fires")
        print("  - Type @security-reviewer — the specialist agent spawns")
    else:
        print("  ✗ Some layers incomplete. Run without --verify to scaffold them.")
    return all_pass


# =====================================================================
# Main
# =====================================================================

LAYER_DEMOS = {
    1: demo_layer1_claude_md,
    5: demo_layer5_settings,
    8: demo_layer8_skills,
    10: demo_layer10_hooks,
    11: demo_layer11_memory,
}


def main():
    parser = argparse.ArgumentParser(description="Session 46 — Claude Code Project Structure lab.")
    parser.add_argument("--layer", type=int, default=None,
                        help="Run demo for a single layer only (1, 5, 8, 10, or 11)")
    parser.add_argument("--verify", action="store_true",
                        help="Run mastery check only (no scaffold, no demos)")
    parser.add_argument("--clean", action="store_true",
                        help="Remove all scaffolded files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be created without writing files")
    args = parser.parse_args()

    print("=" * 70)
    print("  SESSION 46 — CLAUDE CODE PROJECT STRUCTURE")
    print("  Mastery Lab: build + demonstrate all 12 layers")
    print("=" * 70)

    if args.clean:
        removed = clean()
        print(f"\nRemoved {len(removed)} files/dirs:")
        for r in removed:
            print(f"  - {r}")
        return

    if args.verify:
        verify()
        return

    if args.layer:
        # Always scaffold for real when running a demo (demos read the files)
        created = scaffold(dry_run=False)
        if created:
            print(f"\nScaffolded {len(created)} files.")
        demo_fn = LAYER_DEMOS.get(args.layer)
        if demo_fn:
            demo_fn()
        else:
            print(f"No specific demo for layer {args.layer}. Available: {list(LAYER_DEMOS.keys())}")
        return

    # Full run: scaffold → all demos → verify
    section("STEP 1 — SCAFFOLD all 12 layers")
    created = scaffold(dry_run=args.dry_run)
    if created:
        print(f"\nCreated {len(created)} files:")
        for c in created:
            print(f"  + {c}")
    else:
        print("\nAll files already exist (scaffold is idempotent — skipped existing files).")

    # Run all demos
    demo_layer1_claude_md()
    demo_layer5_settings()
    demo_layer10_hooks()
    demo_layer8_skills()
    demo_layer11_memory()
    demo_full_session()

    # Final mastery check
    verify()

    print("\n" + "=" * 70)
    print("  WHAT JUST HAPPENED")
    print("=" * 70)
    print("""
  You built all 12 layers of the Claude Code project structure and
  observed each layer's mechanism directly:

  Layer 1  CLAUDE.md         — always-loaded identity (< 200 lines)
  Layer 2  CLAUDE.local.md   — personal overrides, never committed
  Layer 3  AGENTS.md         — subagent roles, capabilities, handoffs
  Layer 4  mcp.json          — MCP integrations committed to git
  Layer 5  settings.json     — permissions + hook wiring
  Layer 6  rules/*.md        — on-demand rule modules (keep CLAUDE.md lean)
  Layer 7  commands/*.md     — /project:command slash commands
  Layer 8  skills/*/SKILL.md — description-triggered knowledge bundles
  Layer 9  agents/*.md       — isolated specialists with own context
  Layer 10 hooks/*.sh        — deterministic enforcement (the only layer
                               Claude CANNOT reason around)
  Layer 11 memory/*.md       — persistent facts across sessions
  Layer 12 workflows/*.md    — repeatable multi-step task blueprints

  Key insight: each layer has ONE job. No layer does another's job.
  CLAUDE.md = identity. Skills = knowledge. Hooks = enforcement.
  Memory = continuity. Workflows = procedures. Agents = delegation.

  Mastery test: close this session and open a new one.
  - CLAUDE.md loads → Claude knows the repo immediately
  - /project:review is available → run it on your next diff
  - @security-reviewer is available → invoke before any merge
  - memory/decisions.md persists → Claude remembers architecture choices
  - hooks block destructive commands → no accidental rm -rf
  """)


if __name__ == "__main__":
    main()
