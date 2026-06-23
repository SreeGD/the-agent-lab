Review the current diff for correctness, security, and style.

Steps:
1. Run `git diff HEAD` to see all staged and unstaged changes
2. Check for CRITICAL security issues first (injection, hardcoded secrets, missing auth)
3. Check logic correctness (null deref, off-by-one, missing edge cases)
4. Check style against .claude/rules/code-style.md
5. Output findings grouped by severity: CRITICAL → MAJOR → MINOR → LOW

Format each finding as:
`file:line — [SEVERITY] title — one-line fix suggestion`

If $ARGUMENTS contains "fix", apply fixes for MINOR and LOW findings automatically.
