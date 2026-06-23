#!/usr/bin/env bash
# PostToolUse hook: auto-format Python files after every Edit or Write.
# Exit 0 always (formatters should not block).

TOOL="$CLAUDE_TOOL_NAME"

if [[ "$TOOL" == "Edit" || "$TOOL" == "Write" ]]; then
    # Extract file_path from tool result JSON
    FILE=$(echo "$CLAUDE_TOOL_RESULT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

    if [[ "$FILE" == *.py && -f "$FILE" ]]; then
        ruff format "$FILE" 2>/dev/null || true
        echo "  [hook] auto-formatted $FILE"
    fi
fi

exit 0
