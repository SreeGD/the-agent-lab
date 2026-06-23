# Workflow: Code Review

Use when reviewing a PR, branch diff, or set of changed files.

## Steps

### 1. Get the diff
- For a PR: `gh pr diff <number>`
- For a branch: `git diff main...HEAD`
- For specific files: `git diff HEAD -- <file>`

### 2. Fan out to specialists
- Invoke @security-reviewer on the diff
- Invoke @test-writer to assess test coverage gaps
- Run /project:review for style and logic

### 3. Consolidate
- Merge findings from all reviewers
- Deduplicate by file:line
- Sort: CRITICAL → MAJOR → MINOR → LOW

### 4. Report
- Post findings as inline comments if reviewing a GitHub PR
- Summarise in one paragraph: overall quality, top risk, recommended action

### 5. Follow up
- Block merge if any unresolved CRITICAL findings
- Request changes for MAJOR findings
- Leave MINOR/LOW as suggestions at reviewer discretion
