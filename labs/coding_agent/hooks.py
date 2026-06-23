"""Hook runner — pre/post tool shell scripts.

Hooks are configured in AGENT.md under a `hooks:` section (YAML-style).
Each hook specifies:
  - match: tool name pattern (supports * wildcard)
  - script: path to a shell script

Pre-tool hooks:
  - Receive tool name + JSON input via environment variables:
      HOOK_TOOL_NAME, HOOK_TOOL_INPUT
  - Exit 0 = allow the tool call to proceed
  - Exit 2 = deny the tool call (agent receives a DENIED message)

Post-tool hooks:
  - Receive tool name + JSON result summary via env vars
  - Exit code ignored (side effects only — logging, audit)

Example AGENT.md hooks section:
  ## Hooks
  pre_tool:
    - match: bash
      script: hooks/pre_bash.sh
  post_tool:
    - match: "*"
      script: hooks/audit_log.sh

TODO (Step 3): parse hooks config from AGENT.md and load into HOOK_CONFIG.
For now, HOOK_CONFIG is hardcoded as an example.
"""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
from pathlib import Path

# Example hook config — replace with AGENT.md parser in Step 3
HOOK_CONFIG: dict[str, list[dict]] = {
    "pre_tool": [
        # {"match": "bash", "script": "hooks/pre_bash.sh"},
    ],
    "post_tool": [
        # {"match": "*", "script": "hooks/audit_log.sh"},
    ],
}


def run_hooks(event: str, tool_name: str, tool_data: dict) -> str:
    """Run all hooks matching (event, tool_name). Returns 'deny' if any pre-hook blocks.

    Args:
        event:     'pre_tool' or 'post_tool'
        tool_name: name of the tool being called
        tool_data: tool input dict (pre) or {input, result} dict (post)

    Returns:
        'deny' if a pre_tool hook exited with code 2, else 'allow'
    """
    hooks = HOOK_CONFIG.get(event, [])
    for hook in hooks:
        pattern = hook.get("match", "*")
        script  = hook.get("script", "")
        if not fnmatch.fnmatch(tool_name, pattern):
            continue
        if not script:
            continue

        result = _run_hook_script(script, tool_name, tool_data)
        if event == "pre_tool" and result == 2:
            print(f"[hook]     pre_tool hook '{script}' blocked {tool_name}")
            return "deny"
        if result != 0 and event == "pre_tool":
            print(f"[hook]     pre_tool hook '{script}' exited {result} (non-zero treated as allow)")

    return "allow"


def _run_hook_script(script: str, tool_name: str, tool_data: dict) -> int:
    """Execute a hook shell script. Returns exit code."""
    script_path = Path(script)
    if not script_path.exists():
        print(f"[hook]     WARNING: hook script not found: {script}")
        return 0

    env = {
        **os.environ,
        "HOOK_TOOL_NAME":  tool_name,
        "HOOK_TOOL_INPUT": json.dumps(tool_data),
    }

    try:
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout:
            print(f"[hook]     {script}: {result.stdout.strip()}")
        if result.returncode == 2:
            if result.stdout:
                print(f"[hook]     Denial reason: {result.stdout.strip()}")
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"[hook]     WARNING: hook script timed out: {script}")
        return 0
    except Exception as e:
        print(f"[hook]     WARNING: hook script error: {e}")
        return 0
