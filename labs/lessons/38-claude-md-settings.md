# 38 — CLAUDE.md + Settings Best Practices (Session 38)

> **Capture your project's conventions, rules, and permissions once — Claude reads them on every session start.** `CLAUDE.md` is the highest-leverage file in your Claude Code setup: well-written, it eliminates hundreds of repeated clarifications; poorly written, it wastes tokens on noise that never matters.

---

## Roadmap — where this lesson sits

```
═══════ TRACK M: CLAUDE CODE MASTERY (optional) ═══════

  ▶ Session 38: CLAUDE.md + SETTINGS  ◄ HERE
    Session 39: Claude Code Hooks
    Session 40: Autonomous Workflows
    Session 41: Codebase Archaeology
    Session 42: Browser Automation
    Session 43: Scheduled Cloud Routines
    Session 44: Document & Slide Generation
    Session 45: Multi-Agent Code Review Pipeline
    Session 46: Full Project Structure Tutorial
```

**Track M is optional.** It targets engineers who want to master Claude Code itself as a tool — not just use it to build things, but configure and extend it for maximum leverage.

---

## Files involved

| File | Role |
|---|---|
| `~/.claude/CLAUDE.md` | Global rules loaded in every project |
| `.claude/CLAUDE.md` | Project-level rules (stacks on top of global) |
| `CLAUDE.md` (repo root) | Alternative project root location |
| `.claude/settings.json` | Permissions, tool allow/deny lists |
| `.claude/settings.local.json` | Personal permission overrides (gitignored) |

---

## What problem it solves

Every Claude Code session starts cold. Without `CLAUDE.md`, you spend the first few exchanges re-establishing:
- What this project is
- What conventions to follow
- What Claude should never do
- Where the important files are

With a well-written `CLAUDE.md`, Claude walks in already briefed. The first message can be the actual task.

---

## The analogy

`CLAUDE.md` is a **standing brief to a new contractor**. A good brief covers:
- What the project does (one paragraph)
- The tech stack and key tools
- House conventions ("we use ruff, not black")
- Hard rules ("never modify the production DB directly")
- Where to find things ("tests live in tests/, not alongside the code")

A bad brief either says too much (contractor reads the whole wiki every morning) or too little (contractor keeps asking basic questions). The same trade-off applies to `CLAUDE.md`.

---

## Visual: instruction layering

```
  ~/.claude/CLAUDE.md          ← Global (applies to ALL projects)
         +
  .claude/CLAUDE.md            ← Project (applies to THIS project)
  (or CLAUDE.md at repo root)
         +
  .claude/CLAUDE.local.md      ← Personal overrides (gitignored)
         =
  What Claude sees at session start
```

Rules lower in the stack override rules higher up. Project rules beat global rules. Local overrides beat project rules.

---

## Key patterns

### 1. The 200-line budget

Every line in `CLAUDE.md` is loaded into every session — you pay for it in tokens every single call. The discipline is ruthless curation:

| Include | Exclude |
|---|---|
| Project name + purpose (2-3 sentences) | Detailed architecture docs |
| Key directory layout | Git history or recent changes |
| Non-obvious conventions | Things Claude would guess correctly anyway |
| Hard rules (never do X) | Soft preferences that don't matter |
| Pointers to rules files | The content of those rules files |

If in doubt, leave it out. Rules files (`.claude/rules/*.md`) handle detail — they load on demand, not always.

### 2. Global vs. project vs. local layering

```markdown
# ~/.claude/CLAUDE.md (global — applies everywhere)
## My Defaults
- Always use type hints in Python
- Prefer async/await over threading for I/O
- Never commit .env files
- Commit message format: type: description (under 70 chars)
```

```markdown
# .claude/CLAUDE.md (project — overrides global for this repo)
# AgenticCourse
Educational monorepo for agentic AI. Python 3.9+, LangChain, LangGraph.

## Hard Rules
- Never use temperature=0 with claude-opus-4-7 (deprecated)
- New sessions must be added to labs/CURRICULUM.csv
```

```markdown
# .claude/CLAUDE.local.md (personal — gitignored)
## My Environment
- Python: /opt/anaconda3/bin/python
## Experimental
- Try: suggest a "Try This" follow-up after every code change
```

### 3. settings.json — permissions and tool control

```json
{
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(git diff:*)",
      "Bash(pytest:*)",
      "Read(src/**)",
      "Write(src/**)",
      "WebFetch"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(git push --force:*)",
      "Write(.env)",
      "Write(*.sqlite)"
    ]
  }
}
```

**Allow list** — tools Claude can use without prompting you for permission.
**Deny list** — tools that are always blocked, regardless of context.

Everything not on either list falls through to the permission prompt (Claude asks you first).

### 4. What belongs in CLAUDE.md vs. rules files vs. skills

| Content | Where it lives | Why |
|---|---|---|
| Project identity, stack, layout | `CLAUDE.md` | Always needed |
| Hard rules ("never do X") | `CLAUDE.md` | Always enforced |
| Detailed coding conventions | `.claude/rules/code-style.md` | Loaded on demand |
| API patterns for this codebase | `.claude/rules/api-conventions.md` | Loaded on demand |
| Domain knowledge for a task | `.claude/skills/<name>/SKILL.md` | Triggered by context |
| Personal machine paths | `CLAUDE.local.md` | Never committed |

### 5. Writing hard rules that stick

Hard rules need three properties to be followed reliably:

1. **Specific** — "Never use `rm -rf`" beats "Be careful with deletions"
2. **Unconditional** — "Never X" beats "Usually avoid X unless..."
3. **Explainable** — Briefly say why, so Claude can apply the rule to edge cases

```markdown
## Hard Rules
- Never modify labs/farm_plans/checkpoints.sqlite directly.
  (LangGraph owns this file; direct writes corrupt the checkpoint index.)
- Never push to master without a PR.
  (Hook enforced — but the rule belongs here too so Claude warns you first.)
- Never use temperature=0 with claude-opus-4-7.
  (Anthropic deprecated this parameter in Opus 4.x; it returns a 400 error.)
```

---

## Run it

```bash
# Check what CLAUDE.md Claude is currently loading
cat ~/.claude/CLAUDE.md        # global
cat .claude/CLAUDE.md          # project (if it exists)
cat CLAUDE.md                  # repo root (if it exists)

# Check effective permissions
cat .claude/settings.json

# Verify gitignore protects local overrides
grep "CLAUDE.local.md" .gitignore
```

After writing your `CLAUDE.md`, open a **new** Claude Code session (not this one) and give it a task related to the project. Observe how much context it already has without you explaining anything.

---

## Walk-through

### Diagnosing a bad CLAUDE.md

Signs your `CLAUDE.md` needs work:

| Symptom | Diagnosis | Fix |
|---|---|---|
| Claude asks "what framework do you use?" | Tech stack not in CLAUDE.md | Add it |
| Claude suggests the wrong test runner | Testing convention missing | Add to CLAUDE.md or rules file |
| Claude tries to edit a file it shouldn't | Missing hard rule | Add "never modify X" |
| Sessions feel sluggish / expensive | CLAUDE.md is too long | Cut ruthlessly; move detail to rules files |
| Claude ignores your conventions | Convention is too vague | Make it specific and unconditional |

### The "would Claude guess this?" test

Before adding a line, ask: *would Claude get this right without being told?*

- "Use Python" — Claude will infer from the `.py` files. Skip it.
- "Use ruff, not black" — Claude cannot know your preference. Add it.
- "Commit messages under 70 chars" — Claude might not follow this. Add it.
- "The main entry point is `labs/34_farm_planner_engine.py`" — Only if Claude would waste time searching. Add it if the repo is large.

---

## Try this

1. **Write your global CLAUDE.md** — open `~/.claude/CLAUDE.md` and write 5-10 lines covering your cross-project defaults (type hints, commit format, never-commit rules). Open a new session on any project and verify Claude follows them without being asked.

2. **Write a project CLAUDE.md** — for a project you're actively working on, write `.claude/CLAUDE.md`. Keep it under 30 lines. Start a new session and give it a task — count how many clarifying questions it asks vs. without the file.

3. **Split a fat CLAUDE.md** — if your CLAUDE.md is over 100 lines, move the detailed coding conventions to `.claude/rules/code-style.md`. Verify the session still works correctly (Claude loads rules files on demand when the task is relevant).

4. **Permissions audit** — run a session and note every time Claude asks permission for a tool call. Each one is a candidate for your `allow` list. Add the ones you always approve; leave anything destructive on the `deny` list.

5. **Layering experiment** — add a rule to `~/.claude/CLAUDE.md` (global) and a conflicting rule to `.claude/CLAUDE.md` (project). Observe which one wins. (Answer: project beats global.)

---

## Mental model in one line

> **`CLAUDE.md` is a standing brief, not a wiki — it should cover only what Claude would get wrong without it, in under 200 lines, with hard rules stated unconditionally. Everything else belongs in rules files, skills, or memory.**

---

## Related

- **Next:** [39 — Claude Code Hooks](39-claude-code-hooks.md)
- **Detail layer:** `.claude/rules/*.md` — loaded on demand (covered in Session 46)
- **Knowledge layer:** `.claude/skills/` — triggered by context (covered in [17 — Claude Skills](17-claude-skills.md) and Session 46)
- **Memory layer:** `.claude/memory/` — persistent facts (covered in Session 46)
- **Full structure:** [46 — Claude Code Project Structure](46-claude-code-project-structure.md)
- **Curriculum tracker:** Session 38 of 46
