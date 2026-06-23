---
name: code-review
description: Use when reviewing code for bugs, security vulnerabilities, style issues, or correctness problems. Also triggers when asked to review a PR, diff, branch, or file. Provides the 4-specialist parallel pattern (security, logic, style, docs), severity classification schema, and confidence filtering.
---

# Code Review Pattern (AgenticCourse)

## Four specialist roles — run in parallel
1. **Security** — OWASP top 10, injection, hardcoded secrets, auth gaps, SSRF
2. **Logic** — null deref, off-by-one, missing edge cases, race conditions, wrong status codes
3. **Style** — naming, complexity, duplication, magic numbers, dead code
4. **Docs** — missing docstrings, outdated comments, TODO/FIXME without tickets

## Severity schema
| Severity | Meaning |
|---|---|
| CRITICAL | Exploitable / data-loss risk — block merge |
| MAJOR | Wrong behavior for common inputs — fix before merge |
| MINOR | Edge-case issue or style — fix at discretion |
| LOW | Best-practice gap — informational |

## Output format
`file.py:line — [SEVERITY] title — concrete fix`

## Confidence threshold
Only report findings with confidence > 0.75.
Low-confidence findings go in a "Needs human review" section, not the main list.

