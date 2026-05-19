"""Unit tests for vibe coding — the sandbox + code-fence stripping helpers."""

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


# Replicate the helpers from 16_vibe_coding.py for isolated testing.
# (Importing the lab file would also bring in ChatAnthropic at module load.)

@dataclass
class ExecutionResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    timed_out: bool = False


CODE_FENCE_RE = re.compile(r"```(?:python)?\n?(.*?)```", re.DOTALL)


def strip_code_fences(text: str) -> str:
    m = CODE_FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


def execute_in_sandbox(code: str, timeout: int = 5) -> ExecutionResult:
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        tmp_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=timeout,
        )
        return ExecutionResult(
            success=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(success=False, stderr="EXECUTION TIMED OUT", timed_out=True)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─── strip_code_fences ────────────────────────────────────────────────

class TestStripCodeFences:
    def test_python_fence(self):
        text = "```python\nprint('hi')\n```"
        assert strip_code_fences(text) == "print('hi')"

    def test_generic_fence(self):
        text = "```\nprint('hi')\n```"
        assert strip_code_fences(text) == "print('hi')"

    def test_no_fence_returns_stripped_text(self):
        assert strip_code_fences("  print('hi')  ") == "print('hi')"

    def test_extracts_first_block(self):
        # If the model produced multiple blocks, we take the first
        text = "```python\nA = 1\n```\nsome prose\n```python\nB = 2\n```"
        assert strip_code_fences(text) == "A = 1"

    def test_multiline_code(self):
        text = "```python\nimport sys\nprint('multi')\nprint('line')\n```"
        result = strip_code_fences(text)
        assert "import sys" in result
        assert "print('multi')" in result
        assert "print('line')" in result


# ─── execute_in_sandbox ───────────────────────────────────────────────

class TestExecuteInSandbox:
    def test_simple_success(self):
        r = execute_in_sandbox("print('hello')")
        assert r.success
        assert r.stdout.strip() == "hello"
        assert r.returncode == 0
        assert not r.timed_out

    def test_syntax_error(self):
        r = execute_in_sandbox("this is not valid python")
        assert not r.success
        assert "SyntaxError" in r.stderr
        assert r.returncode != 0

    def test_runtime_exception(self):
        r = execute_in_sandbox("raise ValueError('boom')")
        assert not r.success
        assert "ValueError" in r.stderr
        assert "boom" in r.stderr

    def test_timeout(self):
        r = execute_in_sandbox("import time; time.sleep(60)", timeout=2)
        assert not r.success
        assert r.timed_out
        assert "TIMED OUT" in r.stderr

    def test_nonzero_exit(self):
        r = execute_in_sandbox("import sys; sys.exit(7)")
        assert not r.success
        assert r.returncode == 7

    def test_stdout_and_stderr_separated(self):
        code = "import sys; print('to stdout'); sys.stderr.write('to stderr')"
        r = execute_in_sandbox(code)
        assert r.success
        assert "to stdout" in r.stdout
        assert "to stderr" in r.stderr
