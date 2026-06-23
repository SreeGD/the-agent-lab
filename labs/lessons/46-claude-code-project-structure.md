# 46 — Claude Code Project Structure: Full Tutorial (Session 46)

> **Every layer of the Claude Code project structure — built, explained, and exercised.** From `CLAUDE.md` to workflows, this tutorial wires together every concept from Track M into a single working project scaffold.

---

## Roadmap — where this lesson sits

```
═══════ TRACK M: CLAUDE CODE MASTERY (optional) ═══════

  ✓ Session 38: CLAUDE.md + Settings
  ✓ Session 39: Hooks
  ✓ Session 40: Autonomous Workflows
  ✓ Session 41: Codebase Archaeology
  ✓ Session 42: Browser Automation
  ✓ Session 43: Scheduled Routines
  ✓ Session 44: Docs & Slides
  ✓ Session 45: Multi-Agent Code Review
  ▶ Session 46: FULL PROJECT STRUCTURE TUTORIAL  ◄ HERE  (Track M capstone)
```

**Covers the full Claude Code Project Structure infographic** — every file and directory, what it does, and how to build it for your own project.

---

## The structure at a glance

```
your-project/
├── CLAUDE.md                        ← loaded every session
├── CLAUDE.local.md                  ← personal overrides, gitignored
├── AGENTS.md                        ← subagent roster
├── mcp.json                         ← MCP server integrations
└── .claude/
    ├── settings.json                ← permissions, tools, hooks config
    ├── settings.local.json          ← personal permission overrides
    ├── rules/
    │   ├── code-style.md            ← loaded on demand
    │   ├── api-conventions.md
    │   ├── testing-standard.md
    │   └── pr.md
    ├── commands/
    │   ├── review.md                ← /project:review
    │   ├── deploy.md                ← /project:deploy
    │   └── scaffold.md              ← /project:scaffold
    ├── skills/
    │   ├── code-review/SKILL.md     ← auto-triggered by context
    │   ├── testing-patterns/SKILL.md
    │   └── pr-description/SKILL.md
    ├── agents/
    │   ├── security-reviewer.md     ← @security-reviewer
    │   ├── test-writer.md           ← @test-writer
    │   └── research.md              ← @research
    ├── hooks/
    │   ├── validate-code.sh         ← PreToolUse: block bad commands
    │   ├── post-edit-format.sh      ← PostToolUse: auto-format
    │   └── block-sensitive-writes.sh
    ├── memory/
    │   ├── project-context.md       ← persistent facts
    │   ├── decisions.md             ← architectural decisions
    │   └── progress.md              ← current work state
    └── workflows/
        ├── feature-build.md         ← multi-step blueprints
        ├── bug-fix.md
        └── code-review.md
```

---

## Layer 1: `CLAUDE.md` — Loaded every single session

**What it is:** The first file Claude reads at session start. Under 200 lines — every line earns its space. Project overview, tech stack, conventions, hard rules, safety boundaries.

**What belongs here:**
- Project name, purpose, and primary tech stack (2-3 sentences)
- Directory layout (key paths only)
- Non-obvious conventions that Claude would otherwise get wrong
- Hard rules (never do X, always do Y)
- Pointers to rules files for detail

**What does NOT belong here:**
- Long lists of every function or class
- Git history or recent changes
- Debugging notes or temporary reminders

### Exercise 1: Write `CLAUDE.md` for this repo

```markdown
# AgenticCourse

Educational lab monorepo for building agentic AI systems with Claude.

## Tech Stack
- Python 3.9+, LangChain, LangGraph, Streamlit
- Primary AI: Anthropic Claude (claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5)
- Parallel tracks: OpenAI (labs/openai/), Ollama (labs/ollama/)

## Layout
- labs/*.py — numbered lesson scripts (01–46)
- labs/lessons/ — lesson markdown docs
- labs/agritech/ — AgriTech capstone engine + knowledge base
- labs/coding_agent/ — standalone tool-using agent

## Conventions
- Lab files are numbered: NN_descriptive_name.py
- Every lab has a matching lesson: labs/lessons/NN-descriptive-name.md
- Provider variants share the same graph topology — only LLM client differs
- Never use temperature=0 with claude-opus-4-7 (deprecated parameter)

## Hard Rules
- Do not modify labs/farm_plans/checkpoints.sqlite directly
- Keep lesson files under 500 lines — split if larger
- All new sessions must be added to CURRICULUM.csv
```

---

## Layer 2: `CLAUDE.local.md` — Personal overrides. Never committed.

**What it is:** Your machine-specific paths, personal preferences, and experimental rules. Gitignored. Stacks on top of `CLAUDE.md` — never replaces it.

**What belongs here:**
- Local paths (`/Users/yourname/projects/...`)
- Personal style preferences ("I prefer verbose explanations")
- Experimental rules you're testing before promoting to `CLAUDE.md`
- API keys or endpoints for your dev environment (never commit these)

```markdown
# Local Overrides (not committed)

## My Environment
- Python: /opt/anaconda3/bin/python
- Projects root: /Users/srmallip/projects/

## Personal Preferences
- Prefer async/await patterns over threading
- Always show token counts in outputs

## Experimental Rules
- Try: suggest test cases after every new function
```

---

## Layer 3: `AGENTS.md` — The team roster. Who does what.

**What it is:** Defines every subagent's role, capabilities, and handoff protocol. Claude reads this before delegating to prevent overlap and keep multi-agent sessions coordinated.

```markdown
# Agent Roster

## @security-reviewer
**Role:** Security vulnerability specialist
**Focus:** OWASP top 10, injection, auth, SSRF
**Invoke when:** Any code touches auth, user input, or external APIs
**Hands off to:** @test-writer after flagging critical issues

## @test-writer
**Role:** Test suite author
**Focus:** pytest, edge cases, property-based testing
**Invoke when:** New functions or modules are added
**Hands off to:** main session when tests are written

## @research
**Role:** Technical researcher
**Focus:** Web search, documentation lookup, RFC/spec reading
**Invoke when:** Uncertain about library API, external standards, or best practices
**Output format:** Concise summary + sources, no code
```

### Exercise 2: Add a `@doc-writer` agent

```markdown
## @doc-writer
**Role:** Documentation specialist
**Focus:** Docstrings, README sections, lesson markdown
**Invoke when:** New public functions/classes added, or lesson files need updating
**Output format:** Markdown, ready to paste
```

---

## Layer 4: `mcp.json` — MCP server integrations. Shared via git.

**What it is:** Wires Claude to external tools via the Model Context Protocol — GitHub, Notion, Slack, PostgreSQL, and 200+ others.

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": { "DATABASE_URL": "${DATABASE_URL}" }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/srmallip/projects"]
    }
  }
}
```

**Rule:** `mcp.json` is committed. It defines which MCP servers the team shares. Auth tokens stay in env vars or `settings.local.json` — never in `mcp.json`.

---

## Layer 5: `settings.json` — Permissions, tools, and hooks config.

**What it is:** Defines what Claude can read, write, and execute. Committed. Personal overrides go in `settings.local.json`.

```json
{
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(git:*)",
      "Bash(pytest:*)",
      "Read(labs/**)",
      "Write(labs/**)",
      "WebFetch"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(git push --force:*)",
      "Write(.env)",
      "Write(*.sqlite)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "command": ".claude/hooks/validate-code.sh" }
    ],
    "PostToolUse": [
      { "command": ".claude/hooks/post-edit-format.sh" }
    ]
  }
}
```

---

## Layer 6: `rules/*.md` — Modular rule files. Loaded on demand.

**What it is:** Each `.md` is a focused rule module. Keeps `CLAUDE.md` lean by externalising detail that only loads when relevant.

**Example — `.claude/rules/testing-standard.md`:**

```markdown
# Testing Standard

## Framework
Use pytest exclusively. No unittest.

## Structure
- Unit tests: tests/unit/test_<module>.py
- Integration tests: tests/integration/test_<feature>.py
- Fixtures in tests/conftest.py

## Coverage requirements
- New functions: >= 1 happy-path test + >= 1 edge-case test
- Bug fixes: regression test that would have caught the bug

## Naming
- test_<function>_<scenario>_<expected_outcome>
- Example: test_resume_tailor_empty_jd_raises_value_error

## What NOT to test
- Private helper functions (test via the public function)
- LLM output content (test structure, not wording)
```

### Exercise 3: Write three rule files

Create `.claude/rules/code-style.md`, `.claude/rules/api-conventions.md`, and `.claude/rules/pr.md`. Each should be under 50 lines.

---

## Layer 7: `commands/*.md` — Custom slash commands for your project.

**What it is:** Each `.md` becomes a `/project:command-name` slash command. Supports `$ARGUMENTS`. Type `/` in chat to see all commands.

**Example — `.claude/commands/review.md`:**

```markdown
Review the current diff for correctness, security, and style.

Steps:
1. Run `git diff HEAD` to see changes
2. Check for security issues first (injection, hardcoded secrets, missing auth)
3. Check logic correctness (null deref, off-by-one, edge cases)
4. Check style (naming, complexity, duplication)
5. Output findings grouped by severity: CRITICAL → MAJOR → MINOR → LOW
6. If $ARGUMENTS contains "fix", apply fixes for MINOR and LOW findings automatically

Keep findings concise: file:line — severity — one-line description — fix.
```

**Example — `.claude/commands/scaffold.md`:**

```markdown
Scaffold a new lab session for session number $ARGUMENTS.

Steps:
1. Create labs/NN_descriptive_name.py with the standard module docstring
2. Create labs/lessons/NN-descriptive-name.md with the standard lesson template
3. Add the session row to labs/CURRICULUM.csv
4. Print the paths of created files
```

### Exercise 4: Build and use `/project:scaffold`

1. Create `.claude/commands/scaffold.md` as above.
2. In Claude Code, type `/project:scaffold 47`.
3. Watch it create the stub files automatically.

---

## Layer 8: `skills/<name>/SKILL.md` — Auto-triggered by task context.

**What it is:** Not a single file — a directory per skill. The `description` field is the routing rule. Loads only when Claude recognises the task. One job per skill.

**Example — `.claude/skills/code-review/SKILL.md`:**

```markdown
---
name: code-review
description: Use when reviewing code for bugs, security issues, style problems,
  or when asked to review a PR, diff, or file. Provides the 4-specialist parallel
  review pattern (security, logic, style, docs) and severity classification schema.
---

# Code Review Pattern

## Specialist roles
1. Security — OWASP, injection, auth, SSRF
2. Logic — null deref, off-by-one, edge cases, race conditions
3. Style — naming, complexity, duplication, magic numbers
4. Docs — missing docstrings, outdated comments, TODO/FIXME

## Severity schema
- CRITICAL: exploitable or data-loss risk
- MAJOR: incorrect behavior for common inputs
- MINOR: edge case or style issue
- LOW: informational / best practice

## Output format
File:line — [SEVERITY] — Title — Suggestion

## Confidence threshold
Only report findings with confidence > 0.75.
```

**The description IS the trigger.** A query about "reviewing my PR" → this skill fires. A query about "scheduling a cron job" → it doesn't.

---

## Layer 9: `agents/*.md` — Specialist subagents with isolated context.

**What it is:** Each `.md` defines a specialist subagent with its own system prompt, tools, and permissions. Runs in a separate context window — research without polluting the main session. Invoke with `@agent-name`.

**Example — `.claude/agents/security-reviewer.md`:**

```markdown
---
name: security-reviewer
description: Security vulnerability specialist. Invoke with @security-reviewer when
  code touches authentication, user input, external APIs, or file system operations.
tools: Read, Bash(grep:*), WebFetch
---

You are a security engineer performing code review.

Focus exclusively on security vulnerabilities. For each finding:
1. State the file and line number
2. Classify: CRITICAL / MAJOR / MINOR
3. Describe the vulnerability in one sentence
4. Provide a concrete fix

Do not comment on style, performance, or logic unless they create a security issue.
Return findings as a markdown list, sorted by severity.
```

**Key difference from skills:** Agents have their own context window (they can't see your current conversation). Skills load content into YOUR context. Use agents when the task is large enough to need its own thread.

---

## Layer 10: `hooks/*.sh` — Event-driven scripts. 100% enforcement.

**What it is:** Shell commands that execute in response to Claude Code events. Make sure Claude does something deterministically via shell commands — not LLM interpretation. Exit 0 = allow. Exit 2 = block.

**Hook events:**
- `PreToolUse` — runs before any tool call; non-zero exit blocks the call
- `PostToolUse` — runs after a tool call completes; non-zero exit flags a warning
- `UserPromptSubmit` — runs before the user's message is sent
- `Stop` — runs when a Claude Code session ends

**Example — `.claude/hooks/validate-code.sh`:**

```bash
#!/usr/bin/env bash
# Block destructive git commands
TOOL="$CLAUDE_TOOL_NAME"
INPUT="$CLAUDE_TOOL_INPUT"

if [[ "$TOOL" == "Bash" ]]; then
  if echo "$INPUT" | grep -qE 'rm -rf|git push --force|DROP TABLE|DELETE FROM.*WHERE 1'; then
    echo "ERROR: Destructive command blocked by hook" >&2
    exit 2
  fi
fi
exit 0
```

**Example — `.claude/hooks/post-edit-format.sh`:**

```bash
#!/usr/bin/env bash
# Auto-format Python files after every edit
if [[ "$CLAUDE_TOOL_NAME" == "Edit" || "$CLAUDE_TOOL_NAME" == "Write" ]]; then
  FILE=$(echo "$CLAUDE_TOOL_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)
  if [[ "$FILE" == *.py ]]; then
    ruff format "$FILE" 2>/dev/null || true
  fi
fi
exit 0
```

### Exercise 5: Wire a hook that blocks commits to main

```bash
#!/usr/bin/env bash
# .claude/hooks/block-main-push.sh
if [[ "$CLAUDE_TOOL_NAME" == "Bash" ]]; then
  if echo "$CLAUDE_TOOL_INPUT" | grep -q "git push.*main\|git push.*master"; then
    echo "ERROR: Direct push to main blocked. Use a PR." >&2
    exit 2
  fi
fi
exit 0
```

Register in `settings.json`:
```json
"hooks": {
  "PreToolUse": [{ "command": ".claude/hooks/block-main-push.sh" }]
}
```

---

## Layer 11: `memory/*.md` — Persistent memory across all sessions.

**What it is:** Project context, architectural decisions, and progress logs Claude reads between sessions. Compensates for context loss. Commit it — the whole team benefits.

**`memory/decisions.md`:**

```markdown
# Architectural Decisions

## 2026-06-22: Remove temperature=0 from claude-opus-4-7 calls
Parameter is deprecated for Opus 4.7. All LangChain ChatAnthropic calls
for Opus must omit temperature entirely.

## 2026-05-21: Provider-adapter pattern for all capstone engines
Each major engine exists in three variants (Anthropic, OpenAI, Ollama).
They share the same LangGraph topology and state schema.
Only the LLM client and model name differ.
The UI uses importlib to select at runtime.

## 2026-04-10: SQLite checkpointer for farm planner
LangGraph's SqliteSaver persists state between restarts.
Key: uuid thread_id per farm plan. Never delete the sqlite file mid-run.
```

**`memory/progress.md`:**

```markdown
# Current Progress

## Active work
- Track M: Sessions 41-46 lesson files complete, lab files complete
- Yield optimizer: engine built, lesson doc pending

## Last session summary
- Fixed temperature deprecation bug in 41_architecture_summary.py
- Added Session 46 to CURRICULUM.csv

## Next up
- Run 41_repo_map.py on this repo as a demo
- Write lab py files for Session 46
```

---

## Layer 12: `workflows/*.md` — Multi-step task blueprints.

**What it is:** Each `.md` defines a repeatable workflow — feature build, bug fix, code review. Claude follows the blueprint step by step, combining Skills, Subagents, and Hooks in sequence.

**Example — `.claude/workflows/feature-build.md`:**

```markdown
# Workflow: Feature Build

Use this workflow when building a new feature from a spec or issue.

## Steps

### 1. Understand
- Read the spec or issue description
- Ask clarifying questions if scope is ambiguous
- Identify files that will be touched (use @research if uncertain)

### 2. Plan
- Write a brief implementation plan (3-7 bullet points)
- Confirm approach with user before writing code

### 3. Build
- Implement in small, reviewable commits
- Follow .claude/rules/code-style.md conventions
- Add type hints to all new public functions

### 4. Test
- Write tests per .claude/rules/testing-standard.md
- Run: pytest tests/ -x (stop on first failure)
- All tests must pass before proceeding

### 5. Review
- Run /project:review on the diff
- Fix CRITICAL and MAJOR findings before committing
- MINOR and LOW are at developer discretion

### 6. Document
- Update docstrings for all new public functions
- Update memory/progress.md with what was built

### 7. Commit
- Commit with a clear message following repo conventions
- Reference the issue number if applicable
```

---

## Putting it all together: the interaction model

```
User types: "@security-reviewer review the auth changes in PR #47"
                │
                ▼
  Claude reads AGENTS.md → finds @security-reviewer definition
                │
                ▼
  Spawns security-reviewer agent with its own context
  (reads: .claude/agents/security-reviewer.md system prompt)
                │
                ▼
  Agent uses tools: Read, grep, WebFetch
  Agent may trigger: .claude/hooks/validate-code.sh (PreToolUse)
  Agent may load: .claude/skills/code-review/SKILL.md (context match)
                │
                ▼
  Agent returns findings to main session
                │
                ▼
  Claude formats and presents findings
  Claude updates: .claude/memory/decisions.md if arch decision found
```

Every layer has a specific job. No layer does another layer's job.

---

## Anti-patterns to avoid

| Anti-pattern | What goes wrong | Fix |
|---|---|---|
| Everything in CLAUDE.md | Context bloat; Claude "spreads attention" | Move detail to rules/, skills/, memory/ |
| Skills that always load | Defeats the purpose — become system prompt | Write specific descriptions that don't match general queries |
| Hooks that interpret LLM output | Non-deterministic; LLM might say different things | Hooks must grep for patterns, not interpret meaning |
| Memory files with code | Code belongs in source, not memory | Memory = facts and decisions, not implementation |
| CLAUDE.local.md committed | Exposes personal paths, experimental rules | Ensure it's in .gitignore |
| One giant workflow | Can't reuse parts | One workflow per task type; compose from skills |

---

## Exercise 6: Scaffold the full structure for this repo

Run this sequence in Claude Code:

```bash
mkdir -p .claude/{rules,commands,skills/code-review,skills/testing-patterns,agents,hooks,memory,workflows}

# Then ask Claude:
# "Using the Claude Code project structure from Session 46,
#  scaffold the full .claude/ directory for AgenticCourse.
#  Pull context from the architecture summary in /tmp/repo_map.json."
```

Claude will populate each layer using the architecture it already understands from Session 41.

---

## Mental model in one line

> **The Claude Code project structure is layered context management: CLAUDE.md is always-on identity, rules/skills are on-demand expertise, agents are isolated specialists, hooks are deterministic enforcement, memory is cross-session persistence, and workflows are repeatable task blueprints — each layer has one job.**

---

## Related

- **Previous:** [45 — Multi-Agent Code Review Pipeline](45-multi-agent-code-review.md)
- **Foundation:** [38 — CLAUDE.md + Settings Best Practices](38-claude-md-settings.md)
- **Enforcement layer:** [39 — Claude Code Hooks](39-claude-code-hooks.md)
- **Skills system:** [17 — Claude Skills](17-claude-skills.md)
- **Archaeology feeds CLAUDE.md:** [41 — Codebase Archaeology](41-codebase-archaeology.md)
- **Curriculum tracker:** Session 46 of 46 — Track M capstone
