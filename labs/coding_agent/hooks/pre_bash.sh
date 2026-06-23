#!/bin/bash
# Pre-bash hook — block dangerous commands before execution.
# Exit 2 = deny. Exit 0 = allow.
#
# Environment variables provided by the agent:
#   HOOK_TOOL_NAME  — always "bash" for this hook
#   HOOK_TOOL_INPUT — JSON string: {"command": "...", "timeout": 30}

COMMAND=$(echo "$HOOK_TOOL_INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null)

# Block sudo
if echo "$COMMAND" | grep -qE "^sudo "; then
    echo "Blocked: sudo commands are not permitted"
    exit 2
fi

# Block recursive delete
if echo "$COMMAND" | grep -qE "rm\s+-rf"; then
    echo "Blocked: rm -rf is not permitted"
    exit 2
fi

# Allow everything else
exit 0
