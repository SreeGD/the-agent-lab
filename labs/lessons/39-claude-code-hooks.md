# 39 — Claude Code Hooks (Session 39)

> **Make Claude do things deterministically — not via LLM reasoning, but via shell commands that fire on every tool call.** Hooks are the only layer in the Claude Code stack that Claude cannot reason around. They are pure enforcement.

---

## Roadmap — where this lesson sits

```
═══════ TRACK M: CLAUDE CODE MASTERY (optional) ═══════

  ✓ Session 38: CLAUDE.md + Settings
  ▶ Session 39: CLAUDE CODE HOOKS  ◄ HERE
    Session 40: Autonomous Workflows
    Session 41: Codebase Archaeology
    ...
```

---

## Files involved

| File | Role |
|---|---|
| `.claude/hooks/validate-code.sh` | PreToolUse gate — block destructive commands |
| `.claude/hooks/post-edit-format.sh` | PostToolUse formatter — auto-format after every edit |
| `.claude/hooks/block-sensitive-writes.sh` | PreToolUse gate — block writes to sensitive files |
| `.claude/settings.json` | Where hooks are registered (the `"hooks"` key) |

---

## What problem it solves

Claude is an LLM. LLMs can be prompted, convinced, and occasionally reasoned into doing things they shouldn't. A sufficiently clever prompt can get Claude to justify almost any action.

Hooks bypass this entirely. They are shell scripts that run in the OS before or after every tool call — outside Claude's context window, outside its reasoning, outside its ability to influence. Exit 0 = proceed. Exit 2 = blocked. No argument accepted.

---

## The analogy

Think of hooks as **airport security** for Claude's tool calls.

A pilot who wants to bring a restricted item on a plane can argue, explain, and present credentials. Security doesn't care — the scanner doesn't reason, it detects. The rule is enforced at the infrastructure layer, not the reasoning layer.

Hooks work the same way. You don't want Claude to run `rm -rf`? A hook that pattern-matches that string will block it — regardless of how good Claude's reason is.

---

## Visual: hook lifecycle

```
  User prompt
       │
       ▼
  Claude reasons about what to do
       │
       ▼
  Claude decides to call a tool (e.g., Bash("git diff"))
       │
       ▼
  ┌─────────────────────────────┐
  │  PreToolUse hooks fire      │  ← BEFORE the tool runs
  │  validate-code.sh           │
  │  block-sensitive-writes.sh  │
  └──────────┬──────────────────┘
             │ exit 0 = allow / exit 2 = block
             ▼
  Tool executes (or is blocked)
             │
             ▼
  ┌─────────────────────────────┐
  │  PostToolUse hooks fire     │  ← AFTER the tool runs
  │  post-edit-format.sh        │
  └──────────┬──────────────────┘
             │
             ▼
  Result returned to Claude
```

---

## Hook events

| Event | Fires | Use for |
|---|---|---|
| `PreToolUse` | Before any tool call | Block dangerous commands, validate inputs |
| `PostToolUse` | After any tool call completes | Auto-format, log, notify |
| `UserPromptSubmit` | Before user's message is sent | Block PII in prompts, rate limiting |
| `Stop` | When the session ends | Log session summary, cleanup |

---

## Key patterns

### 1. The basic PreToolUse gate

```bash
#!/usr/bin/env bash
# .claude/hooks/validate-code.sh
# Exit 0 = allow. Exit 2 = block.

TOOL="$CLAUDE_TOOL_NAME"
INPUT="$CLAUDE_TOOL_INPUT"

if [[ "$TOOL" == "Bash" ]]; then
    if echo "$INPUT" | grep -qE 'rm -rf|git push --force|git reset --hard|DROP TABLE'; then
        echo "ERROR: Destructive command blocked by hook." >&2
        exit 2
    fi
fi

exit 0
```

**Environment variables available in hooks:**
- `$CLAUDE_TOOL_NAME` — the tool being called (`Bash`, `Read`, `Write`, `Edit`, ...)
- `$CLAUDE_TOOL_INPUT` — the tool's input as a JSON string
- `$CLAUDE_TOOL_RESULT` — the tool's output (PostToolUse only)
- `$CLAUDE_SESSION_ID` — unique ID for the current session

### 2. PostToolUse auto-formatter

```bash
#!/usr/bin/env bash
# .claude/hooks/post-edit-format.sh

if [[ "$CLAUDE_TOOL_NAME" == "Edit" || "$CLAUDE_TOOL_NAME" == "Write" ]]; then
    FILE=$(echo "$CLAUDE_TOOL_RESULT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

    if [[ "$FILE" == *.py && -f "$FILE" ]]; then
        ruff format "$FILE" 2>/dev/null || true
        echo "  [hook] formatted $FILE"
    fi
fi

exit 0  # Never block on formatter — always allow
```

PostToolUse hooks should almost always exit 0. Blocking after the fact is confusing and can leave state inconsistent.

### 3. UserPromptSubmit PII guard

```bash
#!/usr/bin/env bash
# .claude/hooks/block-pii-prompts.sh
# Blocks the prompt before it is sent to the API.

if echo "$CLAUDE_USER_PROMPT" | grep -qE '\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b'; then
    echo "ERROR: Prompt contains an SSN pattern. Remove it and resubmit." >&2
    exit 2
fi

exit 0
```

This is the only place where you can intercept a user's prompt before it reaches the model. Use it for data-loss-prevention (DLP) at the CLI level.

### 4. Registering hooks in settings.json

```json
{
  "hooks": {
    "PreToolUse": [
      { "command": ".claude/hooks/validate-code.sh" },
      { "command": ".claude/hooks/block-sensitive-writes.sh" }
    ],
    "PostToolUse": [
      { "command": ".claude/hooks/post-edit-format.sh" }
    ],
    "UserPromptSubmit": [
      { "command": ".claude/hooks/block-pii-prompts.sh" }
    ]
  }
}
```

Multiple hooks per event run in order. If any PreToolUse hook exits 2, the chain stops and the tool is blocked — subsequent hooks do not run.

### 5. Observability hook (Stop event)

```bash
#!/usr/bin/env bash
# .claude/hooks/session-summary.sh
# Fires when the Claude Code session ends.

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Session $CLAUDE_SESSION_ID ended" \
    >> ~/.claude/session-log.txt
```

Use the `Stop` event to log session activity, send Slack notifications, or trigger downstream automation when a Claude Code session completes.

---

## Run it

```bash
# Make hooks executable (required)
chmod +x .claude/hooks/*.sh

# Test a hook manually
CLAUDE_TOOL_NAME=Bash CLAUDE_TOOL_INPUT='rm -rf /tmp' .claude/hooks/validate-code.sh
echo "Exit code: $?"   # Should be 2 (blocked)

CLAUDE_TOOL_NAME=Bash CLAUDE_TOOL_INPUT='git diff HEAD' .claude/hooks/validate-code.sh
echo "Exit code: $?"   # Should be 0 (allowed)
```

---

## Walk-through

### Exit codes matter

| Exit code | Meaning |
|---|---|
| `0` | Allow / success |
| `1` | Error in the hook script itself (treated as allow with a warning) |
| `2` | **Block** — tool call is cancelled |

Exit 2 is the block signal. Exit 1 is reserved for hook crashes — don't use it for intentional blocks, or you'll get cryptic error messages instead of clean "blocked" feedback.

### Hooks vs. settings deny list

Both can block tool calls. The difference:

| | settings.json deny list | PreToolUse hook |
|---|---|---|
| Pattern matching | Exact tool + prefix matching | Full regex on tool input |
| Logic | None — static list | Arbitrary shell logic |
| Feedback | Generic "permission denied" | Custom error message |
| Update method | Edit JSON, restart | Edit shell script, instant |
| Best for | Broad tool-level blocks | Nuanced input-level blocks |

Use the deny list for "Claude can never use `rm -rf` at all." Use hooks for "Claude can use Bash, but not with this specific pattern."

### Writing robust hooks

Rules for hooks that don't cause grief:

1. **Fast** — hooks run on every tool call. Keep them under 100ms. No web requests, no LLM calls.
2. **Idempotent** — hooks may run multiple times. Writes should be safe to repeat.
3. **Explicit error messages** — write to stderr with a clear explanation. The user sees this when blocked.
4. **Never fail silently** — if your hook crashes, exit 1 (not 0). A crashed hook that exits 0 is invisible.
5. **PostToolUse always exits 0** — blocking after a tool has already run is confusing. Use PostToolUse for side-effects only.

---

## Try this

1. **Block test** — add `.claude/hooks/validate-code.sh`, register it in `settings.json`, then ask Claude to run `ls -la && rm -rf /tmp/test`. Verify it blocks on `rm -rf` but allows `ls`.

2. **Auto-formatter** — add the `post-edit-format.sh` hook. Ask Claude to write a poorly-formatted Python function. Verify `ruff format` runs automatically on save.

3. **PII guard** — add the `block-pii-prompts.sh` hook. Type a prompt containing `123-45-6789` and verify it's blocked before reaching the API.

4. **Observability** — add a `Stop` hook that appends a line to `~/.claude/session-log.txt` every time a session ends. Start and end a few sessions. Inspect the log.

5. **Hook chain** — register two PreToolUse hooks. Make the first one block a pattern. Verify the second one never fires when the first blocks. Then swap the order and verify the chain behaviour changes.

---

## Mental model in one line

> **Hooks are shell scripts that fire on every Claude Code event — PreToolUse blocks before, PostToolUse reacts after, and UserPromptSubmit intercepts before the API is called. They are the only layer Claude cannot reason around: exit 2 = blocked, unconditionally.**

---

## Related

- **Previous:** [38 — CLAUDE.md + Settings Best Practices](38-claude-md-settings.md)
- **Next:** [40 — Autonomous Workflows with Claude Code](40-autonomous-workflows.md)
- **Enforcement demonstrated live:** [46 — Claude Code Project Structure](46-claude-code-project-structure.md) (Layer 10 demo)
- **Settings deny list (simpler alternative):** [38 — CLAUDE.md + Settings](38-claude-md-settings.md)
- **Curriculum tracker:** Session 39 of 46
