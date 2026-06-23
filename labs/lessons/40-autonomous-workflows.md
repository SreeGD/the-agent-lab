# 40 — Autonomous Workflows with Claude Code (Session 40)

> **Ship from a single prompt.** Wire CLAUDE.md + Skills + Hooks + MCP + Subagents into a pipeline that plans, builds, tests, and commits — without a human in the loop for each step. This is the capstone of Track M.

---

## Roadmap — where this lesson sits

```
═══════ TRACK M: CLAUDE CODE MASTERY (optional) ═══════

  ✓ Session 38: CLAUDE.md + Settings
  ✓ Session 39: Claude Code Hooks
  ▶ Session 40: AUTONOMOUS WORKFLOWS  ◄ HERE  (Track M capstone)
    Session 41: Codebase Archaeology
    Session 42: Browser Automation
    Session 43: Scheduled Cloud Routines
    Session 44: Document & Slide Generation
    Session 45: Multi-Agent Code Review Pipeline
    Session 46: Full Project Structure Tutorial
```

**Session 40 is the Track M capstone.** It synthesises every session in the track: the goal is to ship a feature from a single natural-language prompt, with Claude handling every step autonomously.

---

## Files involved

| File | Role |
|---|---|
| `autonomous_workflow.md` | Blueprint: the step-by-step autonomous workflow |
| `.claude/workflows/feature-build.md` | Registered workflow Claude follows |
| `.claude/CLAUDE.md` | Project identity + hard rules (Session 38) |
| `.claude/hooks/validate-code.sh` | Enforcement gate (Session 39) |
| `.claude/skills/code-review/SKILL.md` | Auto-loaded review knowledge (Session 17) |
| `mcp.json` | MCP integrations (Session 1) |

---

## What problem it solves

A typical feature request looks like:

```
You → Claude: "Add a keyword-scoring step to the resume tailor"
Claude: "What test framework do you use?"
You: "pytest"
Claude: "Should I add type hints?"
You: "Yes, always"
Claude: "What's the module structure?"
You: [explains for 5 minutes]
Claude: writes code
You: "Run the tests"
Claude: runs tests, finds error
You: "Fix it"
...
```

With an autonomous workflow, all of that except the first message is handled by Claude reading `CLAUDE.md`, the workflow blueprint, the skills, and the hooks. You provide the intent; Claude executes the full cycle.

---

## The analogy

An autonomous workflow is a **standing operating procedure (SOP)** given to a capable contractor:

- SOP defines: understand → plan → build → test → review → commit
- `CLAUDE.md` gives the contractor the project brief
- Skills give domain knowledge at each step
- Hooks enforce safety at the infrastructure level
- MCP gives access to the tools (GitHub, Slack, DB)

You hand the contractor a ticket number. They do the work end-to-end. You review the output.

---

## Visual: autonomous workflow pipeline

```
  Single prompt:
  "Add keyword scoring to 44_resume_tailor.py"
           │
           ▼
  ┌─────────────────────────────────────────────────────┐
  │  Claude reads:                                      │
  │  CLAUDE.md → project brief                         │
  │  AGENTS.md → available specialists                 │
  │  .claude/workflows/feature-build.md → SOP          │
  └──────────────────────┬──────────────────────────────┘
                         │
           ┌─────────────▼──────────────┐
           │  Step 1: Understand        │
           │  Read CURRICULUM.csv,      │
           │  lesson file, related code │
           └─────────────┬──────────────┘
                         │
           ┌─────────────▼──────────────┐
           │  Step 2: Plan              │
           │  Write 5-bullet plan,      │
           │  confirm with user         │
           └─────────────┬──────────────┘
                         │ (only human checkpoint)
           ┌─────────────▼──────────────┐
           │  Step 3: Build             │
           │  Edit file, follow rules   │
           │  hooks enforce style       │
           └─────────────┬──────────────┘
                         │
           ┌─────────────▼──────────────┐
           │  Step 4: Test              │
           │  Write + run pytest        │
           │  Fix failures              │
           └─────────────┬──────────────┘
                         │
           ┌─────────────▼──────────────┐
           │  Step 5: Review            │
           │  /project:review on diff   │
           │  Fix CRITICAL/MAJOR        │
           └─────────────┬──────────────┘
                         │
           ┌─────────────▼──────────────┐
           │  Step 6: Commit            │
           │  Stage, commit, push       │
           │  hooks block force-push    │
           └─────────────────────────────┘
                         │
                         ▼
              Feature shipped. You review the PR.
```

---

## Key patterns

### 1. The workflow blueprint file

```markdown
# .claude/workflows/feature-build.md

# Workflow: Feature Build

Use when building a new feature or lab session.

## Steps

### 1. Understand
- Read the spec or ticket description
- Read relevant existing code (use @research if uncertain about library APIs)
- Identify which files will be created or changed

### 2. Plan
- Write a 3-7 bullet implementation plan
- **Pause here and confirm with the user before writing code**

### 3. Build
- Implement following .claude/rules/code-style.md
- Add type hints to all new public functions
- Keep functions under 50 lines

### 4. Test
- Write tests per .claude/rules/testing-standard.md
- Run: pytest tests/ -x
- Fix all failures before proceeding

### 5. Review
- Run /project:review on the diff
- Fix all CRITICAL and MAJOR findings

### 6. Commit
- Stage only relevant files
- Follow .claude/rules/pr.md commit format
- Update .claude/memory/progress.md
```

### 2. The one human checkpoint

Fully autonomous loops have one critical failure mode: they can go confidently in the wrong direction for many steps before anyone notices. The solution is a **single plan-confirmation checkpoint** between understanding and building.

```
Understand → Plan → [HUMAN CONFIRMS] → Build → Test → Review → Commit
                         ↑
               Only human touch-point
```

After this point, Claude runs autonomously. The plan confirmation is your chance to redirect before any code is written.

### 3. Wiring everything together

An autonomous workflow draws from every Track M session:

```
CLAUDE.md (Session 38)
    → Claude knows the project without explanation

Settings + deny list (Session 38)
    → Dangerous operations are blocked at the platform level

Hooks (Session 39)
    → validate-code.sh blocks rm -rf, force push
    → post-edit-format.sh auto-formats every file Claude touches

Skills (Session 17 + 46)
    → code-review skill loads when Claude runs /project:review
    → testing-patterns skill loads when Claude writes tests

MCP (Session 1)
    → Claude can push to GitHub, post to Slack, query the DB
    → All via the same tool-call interface

Subagents (Session 46)
    → @security-reviewer invoked during the review step
    → @test-writer invoked during the test step

Memory (Session 46)
    → progress.md updated after each completed workflow
```

### 4. Monitor + iterate

For long-running autonomous sessions, use Claude Code's `/loop` capability to run a workflow on a recurring interval:

```
/loop 30m "Check if any tests are failing and fix them"
```

Or the `/schedule` skill for overnight runs:

```
/schedule "Every morning at 7am, run the test suite and post results to Slack"
```

Claude runs, fails, self-corrects, and reports — you review the morning digest.

### 5. Governance in autonomous mode

The more autonomous Claude is, the more important governance becomes. Three minimum controls for autonomous workflows:

1. **Hooks block irreversible actions** — force push, rm -rf, production DB writes
2. **One plan confirmation** — human in the loop before code is written
3. **Memory records decisions** — `.claude/memory/decisions.md` captures every architectural choice made during the workflow

---

## Run it

```bash
# Start an autonomous feature build from a ticket description
# (Claude will read the workflow blueprint and follow it step by step)

# In Claude Code terminal:
"Build the feature described in this ticket:
Add a keyword confidence score (0-100) to the output of 44_resume_tailor.py.
The score should appear in both the console output and the returned markdown."

# Claude will:
# 1. Read CLAUDE.md, CURRICULUM.csv, 44_resume_tailor.py
# 2. Write a plan and pause for confirmation
# 3. (after confirmation) implement, test, review, commit
```

---

## Walk-through

### What makes a workflow "autonomous" vs. "assisted"

| Assisted (normal) | Autonomous |
|---|---|
| Claude asks about framework | CLAUDE.md tells Claude the framework |
| Claude asks about test style | `.claude/rules/testing-standard.md` answers |
| Human runs tests manually | Claude runs `pytest` and fixes failures |
| Human reviews code | Claude runs `/project:review` and fixes findings |
| Human writes commit | Claude stages, commits per `.claude/rules/pr.md` |
| Human updates docs | Claude updates `memory/progress.md` |

The shift is systematic: every repeated clarification becomes a file that Claude reads automatically.

### Failure modes and mitigations

| Failure mode | Mitigation |
|---|---|
| Claude drifts from the plan | Workflow blueprint is prescriptive; each step is numbered |
| Claude makes irreversible change | Hooks block it; deny list covers the rest |
| Claude commits sensitive data | Pre-commit hook checks for `.env` patterns |
| Autonomous loop runs forever | `/loop` has a time limit; schedule has idempotency check |
| Wrong direction for many steps | Plan confirmation checkpoint (the only human gate) |

---

## Try this

1. **Single-prompt feature** — pick a small, well-scoped task (add one new field to an existing output). Write one sentence describing it. Type it into Claude Code and watch the full workflow execute — observe which steps it does autonomously and where it pauses.

2. **Break the loop** — during an autonomous workflow, introduce a deliberate test failure. Watch Claude find it, diagnose it, and fix it without your intervention.

3. **Hook the workflow** — add a PostToolUse hook that appends to a `workflow-log.txt` every time Claude runs `pytest`. After an autonomous feature build, inspect the log to see how many test runs it took.

4. **Overnight build** — use `/schedule` to run a small workflow every night: "Check if any tests that were passing yesterday are now failing, and open a GitHub issue for each regression." Review the issues in the morning.

5. **Governance audit** — after a full autonomous workflow, open `.claude/memory/decisions.md`. Verify Claude recorded the architectural decisions it made. If it didn't, update the workflow blueprint to explicitly require it.

---

## Mental model in one line

> **An autonomous workflow is a standing operating procedure (blueprint file) combined with all prior Track M layers: CLAUDE.md provides the brief, skills provide domain knowledge, hooks provide enforcement, and memory provides continuity — Claude executes end-to-end, with one human plan-confirmation as the only gate.**

---

## Related

- **Previous:** [39 — Claude Code Hooks](39-claude-code-hooks.md)
- **Next:** [41 — Codebase Archaeology with Claude](41-codebase-archaeology.md)
- **Skills system:** [17 — Claude Skills](17-claude-skills.md)
- **MCP foundation:** [12 — MCP](12-mcp.md)
- **Full structure:** [46 — Claude Code Project Structure](46-claude-code-project-structure.md)
- **Scheduling layer:** [43 — Scheduled Cloud Routines](43-scheduled-cloud-routines.md)
- **Curriculum tracker:** Session 40 of 46 — Track M capstone
