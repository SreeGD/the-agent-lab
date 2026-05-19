"""Vibe Coding — improvisational LLM coding loop.

Generate code → run in sandbox → on failure, feed the error back as context
→ regenerate → repeat until success OR iteration budget exhausted.

The opposite of Spec-Driven Development (Session 4 / spec_driven.py):
no spec, no task list, no formal verification — just *vibes*. Fast for
prototypes; fragile for non-trivial work.
"""

import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 5
SANDBOX_TIMEOUT_S = 15
HERE = Path(__file__).parent


# =====================================================================
# Sandbox — subprocess with a hard timeout. NOT a security sandbox;
# the generated code has filesystem + network access. For a real
# security boundary, wrap this in Docker / nsjail / Firecracker.
# =====================================================================

@dataclass
class ExecutionResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    timed_out: bool = False


def execute_in_sandbox(code: str, timeout: int = SANDBOX_TIMEOUT_S) -> ExecutionResult:
    """Write the code to a temp file, run it as a subprocess, capture output."""
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, dir=HERE
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(HERE),  # let the generated code see real files in helloworld/
        )
        return ExecutionResult(
            success=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False, stderr="EXECUTION TIMED OUT", timed_out=True
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# =====================================================================
# Code-block extraction — the LLM wraps code in ```python ... ``` fences
# =====================================================================

CODE_FENCE_RE = re.compile(r"```(?:python)?\n?(.*?)```", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Pull out the first Python code block; fall back to the whole text."""
    m = CODE_FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


# =====================================================================
# Generator — one prompt, accumulates prior error as context on retries
# =====================================================================

generator_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior Python engineer. Given an intent (and possibly a prior "
     "attempt that errored), produce a complete, runnable Python script that "
     "satisfies the intent.\n"
     "\n"
     "Rules:\n"
     "  - Use only the Python standard library unless absolutely necessary\n"
     "  - Script must be runnable with `python script.py` (no required CLI args "
     "    unless the intent demands them)\n"
     "  - Include all necessary imports at the top\n"
     "  - Output ONLY a ```python ... ``` code block. No prose, no explanation."),
    ("human",
     "Intent: {intent}\n\n"
     "Prior attempt (empty on first try):\n{prior_code}\n\n"
     "Error from prior attempt (empty on first try):\n{error}\n\n"
     "Generate the (corrected) Python script now."),
])

model = ChatAnthropic(model=MODEL, temperature=0)
generator_pipe = generator_prompt | model  # → AIMessage (preserves usage_metadata)


# =====================================================================
# The vibe coding loop
# =====================================================================

@dataclass
class VibeRun:
    intent: str
    success: bool = False
    iterations: int = 0
    final_code: str = ""
    final_stdout: str = ""
    total_in_tokens: int = 0
    total_out_tokens: int = 0
    wall_clock: float = 0.0
    errors_history: list[str] = None

    def __post_init__(self):
        if self.errors_history is None:
            self.errors_history = []

    @property
    def cost_usd(self) -> float:
        return (self.total_in_tokens * 3 + self.total_out_tokens * 15) / 1_000_000


def vibe_code(intent: str, max_iterations: int = MAX_ITERATIONS, verbose: bool = True) -> VibeRun:
    """Run the vibe coding loop on an intent. Returns a VibeRun with metrics."""
    run = VibeRun(intent=intent)
    t0 = time.perf_counter()

    code = ""
    error = ""

    for i in range(1, max_iterations + 1):
        if verbose:
            print(f"\n  ── ITERATION {i} ──")

        # GENERATE
        ai_msg = generator_pipe.invoke(
            {"intent": intent, "prior_code": code, "error": error}
        )
        if ai_msg.usage_metadata:
            run.total_in_tokens += ai_msg.usage_metadata.get("input_tokens", 0)
            run.total_out_tokens += ai_msg.usage_metadata.get("output_tokens", 0)
        code = strip_code_fences(ai_msg.content)
        run.iterations = i

        if verbose:
            preview = code[:120].replace("\n", " ⏎ ")
            print(f"  [generated {len(code)} chars]")
            print(f"  preview: {preview}...")

        # EXECUTE
        result = execute_in_sandbox(code)

        if result.success:
            run.success = True
            run.final_code = code
            run.final_stdout = result.stdout
            run.wall_clock = time.perf_counter() - t0
            if verbose:
                stdout_preview = result.stdout[:200].strip()
                print(f"  [executed ✅ ] stdout: {stdout_preview!r}")
            return run

        # FAIL — capture error for next iteration's context
        error = (result.stderr or f"non-zero exit code {result.returncode}").strip()
        run.errors_history.append(error)
        if verbose:
            error_preview = error.split("\n")[-1][:200] if error else "(empty)"
            print(f"  [executed ❌ ] error: {error_preview}")

    run.wall_clock = time.perf_counter() - t0
    run.final_code = code
    return run


# =====================================================================
# Demo
# =====================================================================

DEMO_INTENTS = [
    "Print the SHA-256 hash of the string 'hello world'.",
    "Build a Python script that lists the top 5 largest files in the current "
    "directory (recursively), skipping hidden files and directories (those "
    "starting with '.'). No CLI args needed; default to '.'. Print each as "
    "'<size_bytes> <path>'.",
]


if __name__ == "__main__":
    print("=" * 70)
    print("VIBE CODING — generate → execute → reflect → retry")
    print("=" * 70)
    print(f"  max iterations: {MAX_ITERATIONS}")
    print(f"  sandbox timeout: {SANDBOX_TIMEOUT_S}s per execution")

    runs: list[VibeRun] = []
    for idx, intent in enumerate(DEMO_INTENTS, 1):
        print(f"\n{'#' * 70}")
        print(f"# INTENT {idx}: {intent[:100]}")
        print("#" * 70)
        run = vibe_code(intent)
        runs.append(run)

        if run.success:
            out_path = HERE / f"generated_vibe_{idx}.py"
            out_path.write_text(run.final_code)
            print(f"\n  ✅ SUCCESS in {run.iterations} iteration(s) — saved to {out_path.name}")
        else:
            print(f"\n  ❌ FAILED after {run.iterations} iterations (budget exhausted)")

    # ─── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'intent':<8} {'result':<10} {'iter':>5} {'in':>6} {'out':>5} {'time':>7} {'cost':>10}")
    print("-" * 60)
    for idx, run in enumerate(runs, 1):
        status = "✅ pass" if run.success else "❌ fail"
        print(
            f"{idx:<8} {status:<10} {run.iterations:>5} "
            f"{run.total_in_tokens:>6} {run.total_out_tokens:>5} "
            f"{run.wall_clock:>6.1f}s ${run.cost_usd:>9.6f}"
        )

    total_in = sum(r.total_in_tokens for r in runs)
    total_out = sum(r.total_out_tokens for r in runs)
    total_cost = sum(r.cost_usd for r in runs)
    total_time = sum(r.wall_clock for r in runs)
    total_iter = sum(r.iterations for r in runs)
    print("-" * 60)
    print(
        f"{'TOTAL':<8} {'':<10} {total_iter:>5} "
        f"{total_in:>6} {total_out:>5} {total_time:>6.1f}s ${total_cost:>9.6f}"
    )

    print(
        "\n  Compare to Session 4 (SDD): similar-difficulty task took ~$0.11 / 90s\n"
        "  with full audit trail (spec + tasks + verification report).\n"
        "  Vibe is faster + cheaper but produces no docs — just the final code\n"
        "  and a 'did it run' verdict. Use when speed > rigor."
    )
