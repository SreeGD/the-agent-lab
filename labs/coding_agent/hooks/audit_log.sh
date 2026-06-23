#!/bin/bash
# Post-tool audit hook — append every tool call to audit.log.
# Exit code is ignored by the agent.

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="audit.log"

echo "$TIMESTAMP  tool=$HOOK_TOOL_NAME  input=$HOOK_TOOL_INPUT" >> "$LOG_FILE"
