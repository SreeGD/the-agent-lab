#!/usr/bin/env bash
# PreToolUse hook: block destructive commands before Claude executes them.
# Exit 2 = block the tool call. Exit 0 = allow.

TOOL="$CLAUDE_TOOL_NAME"
INPUT="$CLAUDE_TOOL_INPUT"

if [[ "$TOOL" == "Bash" ]]; then
    # Block destructive patterns
    if echo "$INPUT" | grep -qE 'rm -rf|git push --force|git reset --hard|DROP TABLE|truncate'; then
        echo "ERROR: Destructive command blocked by validate-code.sh hook" >&2
        exit 2
    fi
    # Block direct push to master/main
    if echo "$INPUT" | grep -qE 'git push.*(master|main)($| )'; then
        echo "ERROR: Direct push to master blocked. Use a feature branch and PR." >&2
        exit 2
    fi
fi

exit 0
