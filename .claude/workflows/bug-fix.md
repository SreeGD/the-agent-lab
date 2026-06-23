# Workflow: Bug Fix

Use when diagnosing and fixing a bug or test failure.

## Steps

### 1. Reproduce
- Get the exact error message and stack trace
- Identify the minimal input that triggers the bug

### 2. Diagnose
- Read the failing code and its direct dependencies
- State the root cause in one sentence before proposing a fix

### 3. Fix
- Change only what is necessary to fix the root cause
- Do not refactor surrounding code in the same commit

### 4. Regression test
- Write a test that would have caught this bug
- Confirm it fails on the unfixed code, passes after the fix

### 5. Commit
- Reference the bug description in the commit message
- Include the regression test in the same commit

### 6. Update memory
- If the bug reveals a systemic issue, add to memory/decisions.md
