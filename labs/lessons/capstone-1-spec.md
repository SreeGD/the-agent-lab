# Project Specification
## Capstone 1 — CLI Coding Agent

**Course:** AgenticCourse — Enterprise AI Architecture
**Phase:** Capstone (after L21 + Framework Comparison module)
**Estimated effort:** 8–10 hours
**Prerequisite:** L03 (Agent tool loop), L12 (MCP), L18 (Anthropic SDK direct), L21 (HITL)

---

## 1. Problem Statement

Claude Code, Cursor, and GitHub Copilot Workspace are the most-used agentic AI products in software engineering. Every developer uses them. Almost no developer understands how they are built. The result: engineers who can prompt these tools but cannot design, extend, or evaluate them.

This project closes that gap. You will build a working CLI coding agent from scratch — the same pattern that underlies all of these products — using the Anthropic SDK directly, without a framework abstraction layer. When you finish, you will understand not just how to use coding agents but how they work.

---

## 2. What You Are Building

A terminal-based coding agent that accepts a natural-language task, reasons about what it needs to do, calls file system and shell tools in a loop, verifies its own work, and reports when it is done — with a tiered permission system, project config injection, extensible hooks, and session memory.

```
$ python main.py "add type hints to all functions in src/utils.py"

[context]  Loaded AGENT.md (312 chars)
[agent]    Starting task: add type hints to all functions in src/utils.py

[tool]     read_file({"path": "src/utils.py"})
           → 1  def parse(x):...  (42 lines)
[tool]     edit_file({"path": "src/utils.py", "old_string": "def parse(x):", ...})
           → OK: edit applied to src/utils.py
[tool]     bash({"command": "python -m pytest tests/ -v"})
           → 9 passed ✓
[agent]    Task complete. 1 file changed, 3 type hints added, all tests passing.

────────────────────────────────────────
Session:   4 iterations  |  8.3s
Tokens:    in=6,200  out=820  cache_hit=4,100
Tools:     read_file ×1  edit_file ×2  bash ×1
────────────────────────────────────────
```

---

## 3. Core Architecture

```
User task
    │
    ▼
Load AGENT.md → inject into system prompt (cache_control)
    │
    ▼
ReAct Loop (max 30 iterations)
    │
    ├── Claude reasons: what do I need to do next?
    │
    ├── Tool call selected
    │       │
    │       ├── check_permission(tool, input)
    │       │     deny   → return DENIED to agent
    │       │     allow  → skip to execute
    │       │     prompt → ask user y/n
    │       │
    │       ├── run pre-tool hook (shell script, exit 2 = block)
    │       ├── execute tool → result
    │       └── run post-tool hook (logging, audit)
    │
    ├── Tool result appended to message history
    │
    ├── stop_reason == "end_turn" → done
    └── stop_reason == "tool_use" → continue loop

Session saved to .agent_session.json after every iteration.
```

---

## 4. Functional Requirements

### 4.1 Tools

| ID | Requirement |
|---|---|
| F-01 | `read_file(path)` returns file content with line numbers. Returns a clear error string (not an exception) if file not found. |
| F-02 | `write_file(path, content)` creates parent directories as needed. Returns lines written on success. |
| F-03 | `edit_file(path, old_string, new_string)` replaces an exact string. Returns an actionable error if `old_string` not found or appears more than once. |
| F-04 | `glob_files(pattern, root)` returns newline-separated matching paths. Returns a clear message if no matches. |
| F-05 | `grep_codebase(pattern, path, glob)` returns matching lines with file:line format. Truncates output at 100 matches. |
| F-06 | `bash(command, timeout)` captures stdout + stderr, enforces timeout, truncates output at 8,000 characters (tail, not head). |

### 4.2 Permission Engine

| ID | Requirement |
|---|---|
| F-07 | Permission check runs before every tool call without exception. |
| F-08 | `deny` verdict: tool call is blocked; agent receives a structured `DENIED` message and continues reasoning. |
| F-09 | `allow` verdict: tool executes without user prompt. `read_file`, `glob_files`, `grep_codebase` are always auto-allowed. |
| F-10 | `prompt` verdict: user sees the tool name and full input, types `y` or `n`. `n` returns `DENIED` to agent. |
| F-11 | Deny patterns are evaluated before allow patterns. Order: deny → allow → prompt. |

### 4.3 AGENT.md Context Injection

| ID | Requirement |
|---|---|
| F-12 | Agent searches for `AGENT.md` in cwd and up to 3 parent directories at session start. |
| F-13 | `AGENT.md` content is injected into the system prompt using `cache_control: ephemeral`. |
| F-14 | On a second invocation with the same `AGENT.md`, cache hit must be confirmed via usage tokens (`cache_read_input_tokens > 0`). |
| F-15 | `AGENT.md` supports an allow-list section that extends the auto-approve patterns without code changes. |

### 4.4 Hook System

| ID | Requirement |
|---|---|
| F-16 | Pre-tool hooks run before tool execution. A hook exiting with code 2 blocks the tool call; agent receives `DENIED`. |
| F-17 | Post-tool hooks run after tool execution. Exit code is ignored (side-effect only). |
| F-18 | Hooks receive `HOOK_TOOL_NAME` and `HOOK_TOOL_INPUT` as environment variables. |
| F-19 | Hook scripts are specified in `AGENT.md`. A missing script logs a warning and does not crash the agent. |

### 4.5 Session Memory

| ID | Requirement |
|---|---|
| F-20 | Full message history is saved to `.agent_session.json` after every iteration. |
| F-21 | `--resume` flag loads prior session. Agent continues from where it left off without re-reading files it already processed. |
| F-22 | `--clear-session` deletes `.agent_session.json` before starting. |

### 4.6 Agent Loop

| ID | Requirement |
|---|---|
| F-23 | Loop terminates on `stop_reason == "end_turn"` (task complete) or `MAX_ITERATIONS` reached (default 30). |
| F-24 | On `MAX_ITERATIONS`, agent prints a clear message explaining how to continue (`--resume` or break task into smaller steps). |
| F-25 | `APIConnectionError` and `RateLimitError` are caught and retried (backoff 5s and 30s respectively) without crashing the session. |
| F-26 | Session cost report is printed at end of every run: iterations, wall time, token counts (in/out/cache_hit), tool call summary. |

---

## 5. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NF-01 | **No framework abstraction.** Use `anthropic.Anthropic().messages.create()` directly. No LangChain, no LangGraph, no agent framework wrappers. |
| NF-02 | **Tool errors never crash the loop.** Every tool function returns a string. Exceptions are caught inside the tool and returned as `ERROR: ...` strings. |
| NF-03 | **Dangerous commands are blocked by default.** `rm -rf`, `sudo`, `DROP TABLE`, force push patterns must be in `DENY_PATTERNS` and must be blocked without a user prompt. |
| NF-04 | **`edit_file` requires exact match.** Fuzzy matching is not acceptable. The tool must surface a useful error message when the string is not found. |
| NF-05 | **Output truncation is tail-biased.** When `bash` output exceeds 8,000 chars, the most recent output is preserved (not the first 8,000 chars). |
| NF-06 | **Single entry point.** `python main.py "<task>"` is the only way to start the agent. No Jupyter notebooks, no `__main__` hacks in non-entrypoint files. |

---

## 6. Technical Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| LLM SDK | `anthropic` (direct) | No LangChain or other framework wrappers |
| Model | `claude-sonnet-4-6` | |
| Serialization | `json` (stdlib) | Session memory stored as plain JSON |
| Hooks | `subprocess` | Shell scripts via bash |
| CLI | `argparse` (stdlib) | `--resume`, `--clear-session`, `--verbose` |

---

## 7. Repository Structure

```
capstone1/
├── main.py                  # CLI entrypoint
├── agent_loop.py            # ReAct loop, permission dispatch, session report
├── context.py               # AGENT.md loader, system prompt builder
├── hooks.py                 # Pre/post tool hook runner
├── memory.py                # Session save/resume
├── AGENT.md                 # Sample project config
├── tools/
│   ├── __init__.py
│   ├── registry.py          # ToolRegistry, check_permission, schemas
│   ├── file_tools.py        # read_file, write_file, edit_file, glob_files
│   ├── search_tools.py      # grep_codebase
│   └── bash_tool.py         # bash
├── hooks/
│   ├── pre_bash.sh          # Example: block sudo + rm -rf
│   └── audit_log.sh         # Example: append to audit.log
└── tests/
    ├── test_file_tools.py
    ├── test_permissions.py
    └── test_hooks.py
```

---

## 8. Deliverables

| # | Deliverable | Format |
|---|---|---|
| D-01 | Working agent | `python main.py "list all Python files"` completes successfully |
| D-02 | Multi-step task demo | Agent completes read → edit → test in one session (3+ tool calls) |
| D-03 | Permission demo | Screenshot or log showing: auto-allow, user-prompt, and deny in the same session |
| D-04 | Hook demo | `hooks/pre_bash.sh` blocks a `sudo` command; `hooks/audit_log.sh` writes to `audit.log` |
| D-05 | Session resume demo | `--resume` continues a prior session; agent recalls prior tool results |
| D-06 | Cache hit proof | Second invocation shows `cache_read_input_tokens > 0` in session report |
| D-07 | Architecture Decision Record | 1 page, 4 questions answered |

---

## 9. Grading Rubric

| Area | Points | Pass criteria |
|---|---|---|
| **All 6 tools correct (F-01 to F-06)** | 25 | Each tool handles happy path and error case; edit_file exact-match enforced |
| **Permission engine (F-07 to F-11)** | 20 | Deny blocks without prompt; allow skips prompt; prompt fires for unknown; order correct |
| **ReAct loop (F-23 to F-26)** | 20 | Completes a 3-step coding task; handles max_iterations; retries on API errors |
| **AGENT.md + cache (F-12 to F-15)** | 15 | Injection works; cache hit confirmed on second run; allow-list extends permissions |
| **Hook system (F-16 to F-19)** | 10 | Pre-hook blocks via exit 2; post-hook runs; missing script is a warning not a crash |
| **Session memory (F-20 to F-22)** | 10 | Save/resume round-trip works; clear-session deletes file |

**Total: 100 points. Pass: 75+**

---

## 10. Architecture Decision Record — Required Questions

1. **Client-side permissions:** The permission engine runs in your Python code, not inside Claude. What does this mean for security? Could Claude bypass the permission check if it wanted to?

2. **Message history as memory:** The agent has no database, no embedding store, no special memory module. How does it "remember" that it already read a file three tool calls ago?

3. **Max iterations failure mode:** The agent hits `MAX_ITERATIONS = 30` on a large refactor task. What is the correct failure behavior? What information must be preserved so the user can continue with `--resume`?

4. **Extending to 50-file refactors:** Your agent works well on single-file edits. What breaks when the task requires reading 50 files before making any edits, and how would you redesign the loop to handle it?

---

## 11. Submission Checklist

- [ ] `python main.py "list all Python files in the current directory"` completes in ≤3 iterations
- [ ] `python main.py "add a docstring to the first function in tools/file_tools.py"` produces a correct edit
- [ ] `bash` tool blocks `rm -rf .` without prompting the user
- [ ] `bash: pytest *` is auto-approved (no user prompt)
- [ ] `--resume` loads prior session; agent does not re-read files it already read
- [ ] Second run shows `cache_read_input_tokens > 0` in session report
- [ ] `hooks/pre_bash.sh` blocks a `sudo echo test` command; log shows `DENIED`
- [ ] All tests in `tests/` pass: `python -m pytest tests/ -v`
- [ ] ADR answers all 4 questions with technical specificity

---

*This spec defines the contract between student and evaluator. Implementation choices not specified here are at the student's discretion provided all functional and non-functional requirements are met.*
