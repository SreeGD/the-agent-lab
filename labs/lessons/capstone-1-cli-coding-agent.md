# Capstone 1 — Build Your Own CLI Coding Agent

> **Build a working Claude Code equivalent from scratch.** A terminal-based coding agent with a ReAct tool-use loop, file system tools, bash execution with permission gates, context injection via a project config file, pre/post tool hooks, and session memory — all wired to Claude via the Anthropic SDK.

---

## Roadmap — where this sits

```
Phase 1 (L01-11)   Phase 2 (L12-21)   Phase 3 (L22-28)   Enterprise Hardening
Foundation          Agentic Patterns    Advanced RAG        IAM + Model Routing

                                                           ▶ CAPSTONE 1  ◄ YOU ARE HERE
                                                           ○ Capstone 2
```

**Why this capstone:** Claude Code, Cursor, and GitHub Copilot Workspace are the most-used agentic AI products in the world. Building one from scratch teaches you every agentic pattern simultaneously — tool-use loops, permission systems, context management, hooks, and HITL — in a domain every developer understands. When you finish, you understand not just how to use these tools but how they are built.

---

## What you are building

```
$ python agent.py "refactor the auth module to use JWT instead of sessions"

[agent]  Reading AGENT.md for project context...
[agent]  Tool call: read_file("src/auth/session.py")
[agent]  Tool call: glob("src/auth/**/*.py")
[agent]  Tool call: read_file("src/auth/middleware.py")
[agent]  Plan: replace session store → JWT encode/decode, update middleware, add refresh token logic
[tool]   bash("pip install pyjwt") → Permission required. Allow? [y/n]: y
[agent]  Tool call: write_file("src/auth/jwt_handler.py", ...)
[agent]  Tool call: edit_file("src/auth/middleware.py", old="session.get(...)", new="jwt.decode(...)")
[agent]  Tool call: bash("python -m pytest tests/test_auth.py -v")
[tool]   Tests: 8 passed, 1 failed → test_session_expiry
[agent]  Tool call: read_file("tests/test_auth.py")
[agent]  Tool call: edit_file("tests/test_auth.py", ...)
[agent]  Tool call: bash("python -m pytest tests/test_auth.py -v")
[tool]   Tests: 9 passed ✓
[agent]  Done. 3 files changed, 1 file created, all tests passing.
```

---

## Core architecture

```
User prompt
    │
    ▼
 Load AGENT.md  (project config — inject into system prompt)
    │
    ▼
 Agent Loop (ReAct — Reason → Act → Observe → repeat)
    │
    ├── Claude reasons: what do I need to know / do next?
    │
    ├── Tool call decision
    │       │
    │       ├── Permission check
    │       │     READ tools  → auto-allow
    │       │     WRITE tools → check allow-list; prompt if not listed
    │       │     BASH tools  → always prompt unless pattern in allow-list
    │       │
    │       ├── Pre-tool hook  (shell script, exit 0=allow / exit 2=deny)
    │       │
    │       ├── Execute tool
    │       │
    │       └── Post-tool hook (logging, audit, side effects)
    │
    ├── Tool result → back into context as next observation
    │
    ├── Claude decides: done? or next tool call?
    │
    └── Loop until: task complete OR max_iterations OR user interrupt (Ctrl+C)

Session memory: conversation saved to .agent_session.json
Context compaction: auto-summarise when context > 80% full
```

---

## Files you will create

| File | Role |
|---|---|
| `coding_agent/main.py` | CLI entrypoint — `python agent.py "<task>"` |
| `coding_agent/agent_loop.py` | Core ReAct loop — tool dispatch, observation feeding, stop detection |
| `coding_agent/tools/file_tools.py` | `read_file`, `write_file`, `edit_file`, `glob_files` |
| `coding_agent/tools/search_tools.py` | `grep_codebase`, `find_symbol` |
| `coding_agent/tools/bash_tool.py` | `bash` — execute shell command, capture stdout/stderr |
| `coding_agent/tools/registry.py` | Tool registry — maps tool names to functions + schemas |
| `coding_agent/permissions.py` | Permission engine — allow/deny/prompt per tool + pattern |
| `coding_agent/hooks.py` | Hook runner — pre/post tool, shell script execution |
| `coding_agent/context.py` | AGENT.md loader + context injection |
| `coding_agent/memory.py` | Session memory — save/resume conversation |
| `coding_agent/compactor.py` | Context compaction — summarise when window fills |
| `AGENT.md` | Project config file (what CLAUDE.md is to Claude Code) |

---

## What each lesson shows up as

| In this capstone | From lesson |
|---|---|
| Anthropic SDK direct — `messages.create()` with tools | L18 |
| Tool definitions as JSON schema | L03, L18 |
| Structured output for tool call parsing | L05 |
| ReAct loop (reason → act → observe) | L03, L13 |
| Plan-execute pattern for multi-step tasks | L13 |
| MCP protocol — tool registry design | L12 |
| Human-in-the-loop permission prompts | L21 |
| Session memory (save/resume) | L08, L29 |
| Guardrails — dangerous command detection | L10 |
| Streaming output token-by-token | L27 |
| Cost tracking per session | L26 |
| Prompt caching on system prompt + AGENT.md | L04 |

---

## Step-by-step build sequence

### Step 1 — Tool definitions
Define 6 core tools as Anthropic tool schemas:
```python
READ_FILE = {
    "name": "read_file",
    "description": "Read the contents of a file at the given path.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative or absolute file path"}
        },
        "required": ["path"]
    }
}
```
Tools to implement: `read_file`, `write_file`, `edit_file`, `glob_files`, `grep_codebase`, `bash`

Test: call each tool directly with a Python unit test before wiring the agent.

### Step 2 — Permission engine
```python
class PermissionEngine:
    # Tiered rules evaluated in order: deny → allow → prompt
    DENY_PATTERNS  = ["rm -rf", "DROP TABLE", "> /dev/null 2>&1 &&"]
    ALLOW_PATTERNS = ["read_file:*", "glob_files:*", "grep_codebase:*",
                      "bash:pytest *", "bash:pip install *"]

    def check(self, tool_name: str, tool_input: dict) -> Literal["allow", "deny", "prompt"]:
        ...
```
- Deny: immediately block + return error to agent
- Allow: execute without user prompt
- Prompt: show user the tool call, wait for y/n

Test: 10 tool calls (mix of safe, dangerous, ambiguous) — verify correct verdict for each.

### Step 3 — Hook system
```python
# AGENT.md hook config
hooks:
  pre_tool:
    - match: "bash"
      script: "hooks/pre_bash.sh"   # exit 2 to deny, exit 0 to allow
  post_tool:
    - match: "*"
      script: "hooks/audit_log.sh"  # log every tool call
```
- Pre-hook: run shell script before tool execution; exit 2 = deny
- Post-hook: run shell script after tool result; useful for audit logging
- Hook scripts receive tool name + input as env vars

Test: pre-hook that blocks any `bash` call containing `sudo`; post-hook that appends to `audit.log`.

### Step 4 — AGENT.md context injection
```markdown
# AGENT.md
## Project
Python FastAPI service. PostgreSQL. Pytest for tests.

## Rules
- Never modify migration files
- Always run tests after editing src/
- Use type hints on all new functions

## Allow list
bash: pytest *
bash: pip install *
bash: alembic *
```
- Parse AGENT.md at session start
- Inject into system prompt with `cache_control` (stable prefix → cache hit)
- Rules section shapes agent behaviour; allow-list pre-approves safe commands

Test: verify AGENT.md content appears in system prompt; verify cache hit on second invocation.

### Step 5 — ReAct agent loop
```python
def run_agent(task: str, max_iterations: int = 30):
    messages = [{"role": "user", "content": task}]

    for i in range(max_iterations):
        response = client.messages.create(
            model=ANSWER_MODEL,
            system=build_system_prompt(),   # AGENT.md + tool instructions
            tools=TOOL_REGISTRY,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            print(response.content[-1].text)
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = dispatch_tool(block.name, block.input)  # permission → hook → execute
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
```

Test: `"list all Python files in src/"` → agent calls `glob_files` → returns list → stops. Verify in ≤ 2 iterations.

### Step 6 — Session memory + context compaction
- Save full message history to `.agent_session.json` after each turn
- `python agent.py --resume` loads prior session
- When `total_tokens > 0.8 × context_window`: call a summarisation step
  ```python
  summary = client.messages.create(
      model="claude-haiku-4-5",
      messages=[{"role": "user", "content": f"Summarise this coding session:\n{history}"}]
  )
  messages = [{"role": "user", "content": f"[Session summary]\n{summary}\n\n[New task continues]"}]
  ```

Test: run a 10-turn session, save, resume, verify agent recalls prior file edits.

### Step 7 — Streaming output
- Stream tokens to terminal as Claude reasons
- Show tool calls as they are dispatched: `[tool] read_file("src/auth.py") → 142 lines`
- Show permission prompt inline, not after full response

Test: verify tokens stream character-by-character; verify tool call display appears before result.

### Step 8 — Cost + session report
At session end, print:
```
────────────────────────────────────────────
Session: 14 iterations | 3 files changed
Tokens:  in=24,800  out=3,200  cache_hit=18,400
Cost:    ₹18.40  (cache saved ₹12.20)
Tools:   read_file ×6  edit_file ×3  bash ×4  glob ×1
────────────────────────────────────────────
```

---

## Run it

```bash
# New session
python agent.py "add input validation to all FastAPI route handlers in src/routes/"

# Resume prior session
python agent.py --resume

# With verbose tool logging
python agent.py --verbose "write unit tests for src/utils/parser.py"
```

---

## Grading rubric

| Area | Points | Criteria |
|---|---|---|
| **Tool correctness** | 20 | All 6 tools work correctly; edit_file applies diffs without corrupting files |
| **ReAct loop** | 20 | Agent completes a 3-step coding task (read → edit → test) without human guidance |
| **Permission engine** | 15 | Deny patterns block correctly; allow-list auto-approves; prompt fires for ambiguous |
| **Hook system** | 10 | Pre-hook can block a tool call; post-hook logs to file; AGENT.md drives config |
| **AGENT.md injection** | 10 | Project rules shape agent behaviour; cache hit on second run confirmed |
| **Session memory** | 10 | Session saves and resumes correctly; compaction fires when context > 80% |
| **Streaming** | 5 | Tokens stream live; tool dispatch visible before result |
| **Cost report** | 5 | Accurate token count + cost at session end |
| **Safety** | 5 | Dangerous commands (rm -rf, DROP TABLE) blocked by deny patterns |

**Total: 100 points. Pass: 75+**

---

## Architecture Decision Record (deliverable)

Write a 1-page ADR answering:
1. Why is the permission engine client-side rather than enforced by the model? What does this mean for security?
2. What is the failure mode when the agent hits `max_iterations`? How should it fail gracefully?
3. How would you extend this agent to support multi-file refactors that span 50+ files without hitting context limits?
4. What would you need to add to make this agent safe to run in a shared cloud environment (multi-tenant)?

---

## Extension challenges

| Challenge | What you learn |
|---|---|
| Add `web_fetch` tool — agent can read documentation URLs | Tool expansion |
| Add MCP server support — agent discovers tools from external MCP server | L12 MCP protocol |
| Add sub-agent spawning — agent delegates sub-tasks to a cheaper model | L14 Multi-agent |
| Add git-aware context — agent reads `git diff` and `git log` before planning | Tool composition |
| Add a TUI (Textual) frontend replacing the plain CLI | Production UX |
| Port one tool to TypeScript + AI SDK (Vercel) | Multi-language agentic patterns |

---

## Mental model in one line

> **A CLI coding agent is a tool-use loop with a permission system and a memory — Claude Code, Cursor, and Devin are all variations of this same pattern. Once you build one, you understand all of them.**

---

## Related

- **Next:** Capstone 2 — Autonomous Financial Research Agent
- **Core dependencies:** L03 Agent tool loop, L12 MCP, L13 Reflection, L18 Anthropic SDK direct, L21 HITL, L27 Streaming
- **Reference:** Claude Code docs — hooks, permissions, CLAUDE.md mechanism
