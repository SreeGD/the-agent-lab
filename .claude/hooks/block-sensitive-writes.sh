#!/usr/bin/env bash
# PreToolUse hook: block writes to sensitive files.
# Exit 2 = block. Exit 0 = allow.

TOOL="$CLAUDE_TOOL_NAME"
INPUT="$CLAUDE_TOOL_INPUT"

if [[ "$TOOL" == "Write" || "$TOOL" == "Edit" ]]; then
    FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

    # Block writes to sensitive files
    if echo "$FILE" | grep -qE '\.env$|\.sqlite$|secrets\.|credentials\.'; then
        echo "ERROR: Write to sensitive file '$FILE' blocked by hook." >&2
        exit 2
    fi
fi

exit 0
