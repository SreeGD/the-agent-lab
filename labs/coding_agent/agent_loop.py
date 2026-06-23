"""Core ReAct agent loop.

Pattern: Reason → Act (tool call) → Observe (result) → repeat until done.

Each iteration:
  1. Call Claude with current message history + tools
  2. If stop_reason == "end_turn" → agent is done, print final message
  3. If stop_reason == "tool_use" → for each tool call:
       a. Check permission (allow / deny / prompt user)
       b. Run pre-tool hooks
       c. Execute tool
       d. Run post-tool hooks
       e. Append tool result to messages
  4. Loop
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Iterator

import anthropic

from context import build_system_prompt
from hooks import run_hooks
from memory import load_session, save_session
from tools.registry import ToolRegistry, check_permission

ANSWER_MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 30
CONTEXT_WINDOW = 200_000   # claude-sonnet-4-6 context window
COMPACT_THRESHOLD = 0.80   # compaction when messages use > 80% of window


# ── Session state ─────────────────────────────────────────────────────────────

class SessionState:
    def __init__(self, task: str, resume: bool = False) -> None:
        self.task = task
        self.messages: list[dict] = []
        self.iteration = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_read_tokens = 0
        self.tool_calls: list[str] = []
        self.start_time = time.time()

        if resume:
            saved = load_session()
            if saved:
                self.messages = saved["messages"]
                print(f"[session]  Resumed — {len(self.messages)} prior messages loaded")
            else:
                print("[session]  No prior session found, starting fresh")


# ── Display helpers ───────────────────────────────────────────────────────────

def _print_tool_call(name: str, tool_input: dict) -> None:
    args_preview = json.dumps(tool_input)
    if len(args_preview) > 120:
        args_preview = args_preview[:120] + "..."
    print(f"\n[tool]     {name}({args_preview})", flush=True)


def _print_tool_result(result: str) -> None:
    preview = result.strip().replace("\n", " ")
    if len(preview) > 160:
        preview = preview[:160] + "..."
    print(f"           → {preview}", flush=True)


def _print_cost_report(state: SessionState) -> None:
    elapsed = time.time() - state.start_time
    tool_summary = {}
    for t in state.tool_calls:
        tool_summary[t] = tool_summary.get(t, 0) + 1

    print("\n" + "─" * 60)
    print(f"Session:   {state.iteration} iterations  |  {elapsed:.1f}s")
    print(f"Tokens:    in={state.total_input_tokens:,}  out={state.total_output_tokens:,}  "
          f"cache_hit={state.total_cache_read_tokens:,}")
    if tool_summary:
        tools_str = "  ".join(f"{k} ×{v}" for k, v in sorted(tool_summary.items()))
        print(f"Tools:     {tools_str}")
    print("─" * 60)


# ── Permission + dispatch ─────────────────────────────────────────────────────

def _request_permission(tool_name: str, tool_input: dict) -> bool:
    """Prompt the user to allow or deny a tool call. Returns True = allow."""
    args_str = json.dumps(tool_input, indent=2)
    print(f"\n[permission]  {tool_name} wants to run:")
    print(f"              {args_str}")
    while True:
        answer = input("              Allow? [y/n]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


def _execute_tool(
    tool_name: str,
    tool_input: dict,
    tool_use_id: str,
    registry: ToolRegistry,
    state: SessionState,
) -> dict:
    """Permission check → pre-hook → execute → post-hook → return tool_result block."""
    _print_tool_call(tool_name, tool_input)
    state.tool_calls.append(tool_name)

    # 1. Permission check
    verdict = check_permission(tool_name, tool_input)
    if verdict == "deny":
        result = f"DENIED: this operation is not permitted by the agent's security policy."
        print(f"           → DENIED (auto-block)", flush=True)
    elif verdict == "prompt":
        allowed = _request_permission(tool_name, tool_input)
        if not allowed:
            result = "DENIED: user declined this tool call."
        else:
            # 2. Pre-tool hook
            hook_result = run_hooks("pre_tool", tool_name, tool_input)
            if hook_result == "deny":
                result = "DENIED: pre-tool hook blocked this operation."
            else:
                # 3. Execute
                result = str(registry.dispatch(tool_name, tool_input))
                # 4. Post-tool hook
                run_hooks("post_tool", tool_name, {"input": tool_input, "result": result[:500]})
    else:  # allow
        run_hooks("pre_tool", tool_name, tool_input)
        result = str(registry.dispatch(tool_name, tool_input))
        run_hooks("post_tool", tool_name, {"input": tool_input, "result": result[:500]})

    _print_tool_result(result)

    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": result,
    }


# ── Context compaction ────────────────────────────────────────────────────────

def _maybe_compact(client: anthropic.Anthropic, state: SessionState) -> None:
    """Summarise conversation history if context window is filling up.

    TODO (Step 6): implement compaction.
    Hint:
      1. Estimate current token count from state.total_input_tokens
      2. If > COMPACT_THRESHOLD * CONTEXT_WINDOW, call claude-haiku with a
         summarisation prompt over state.messages
      3. Replace state.messages with a single summary message
      4. Print [compact] notice so user knows it happened
    """
    estimated_used = state.total_input_tokens
    if estimated_used > COMPACT_THRESHOLD * CONTEXT_WINDOW:
        print("[compact]  Context window filling — summarising session history...")
        # TODO: call haiku to summarise, replace messages
        pass


# ── Streaming helpers ─────────────────────────────────────────────────────────

def _stream_response(
    client: anthropic.Anthropic,
    system: str,
    messages: list[dict],
    tools: list[dict],
    state: SessionState,
) -> anthropic.types.Message:
    """Stream Claude's response token-by-token, return the complete Message.

    TODO (Step 7): implement streaming.
    Hint: use client.messages.stream(...) context manager.
    For now, falls back to non-streaming (still correct, just less interactive).
    """
    # Non-streaming fallback — replace with streaming in Step 7
    response = client.messages.create(
        model=ANSWER_MODEL,
        max_tokens=8096,
        system=system,
        tools=tools,
        messages=messages,
    )

    # Print text blocks as they arrive
    for block in response.content:
        if hasattr(block, "text") and block.text:
            print(f"\n[agent]    {block.text}", flush=True)

    # Track token usage
    if response.usage:
        state.total_input_tokens  += response.usage.input_tokens
        state.total_output_tokens += response.usage.output_tokens
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        state.total_cache_read_tokens += cache_read

    return response


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_agent(task: str, registry: ToolRegistry, resume: bool = False) -> None:
    """Entry point — run the ReAct loop until task complete or max iterations."""
    client = anthropic.Anthropic()
    system_prompt = build_system_prompt()
    state = SessionState(task, resume=resume)

    # Seed the conversation with the user's task
    if not state.messages:
        state.messages.append({"role": "user", "content": task})

    print(f"\n[agent]    Starting task: {task}")
    print(f"[agent]    Model: {ANSWER_MODEL}  |  Max iterations: {MAX_ITERATIONS}\n")

    for iteration in range(1, MAX_ITERATIONS + 1):
        state.iteration = iteration

        # ── Check / compact context ───────────────────────────────────────────
        _maybe_compact(client, state)

        # ── Call Claude ───────────────────────────────────────────────────────
        try:
            response = _stream_response(
                client,
                system=system_prompt,
                messages=state.messages,
                tools=registry.schemas(),
                state=state,
            )
        except anthropic.APIConnectionError as e:
            print(f"\n[error]    API connection error: {e}")
            print("[error]    Retrying in 5s...")
            time.sleep(5)
            continue
        except anthropic.RateLimitError:
            print("\n[error]    Rate limited — backing off 30s...")
            time.sleep(30)
            continue

        # ── Append assistant response to history ──────────────────────────────
        state.messages.append({"role": "assistant", "content": response.content})

        # ── Handle stop conditions ────────────────────────────────────────────
        if response.stop_reason == "end_turn":
            print("\n[agent]    Task complete.")
            break

        if response.stop_reason == "max_tokens":
            print("\n[agent]    Max tokens reached — increase max_tokens or compact context.")
            break

        # ── Handle tool calls ─────────────────────────────────────────────────
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_block = _execute_tool(
                        tool_name=block.name,
                        tool_input=block.input,
                        tool_use_id=block.id,
                        registry=registry,
                        state=state,
                    )
                    tool_results.append(result_block)

            state.messages.append({"role": "user", "content": tool_results})

        # ── Persist session after each iteration ──────────────────────────────
        save_session({"messages": state.messages, "task": task})

    else:
        print(f"\n[agent]    Reached max iterations ({MAX_ITERATIONS}). Stopping.")
        print("[agent]    Tip: increase MAX_ITERATIONS or break the task into smaller steps.")

    _print_cost_report(state)
