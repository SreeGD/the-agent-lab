# Workflow: Feature Build

Use when building a new lab session or feature from a spec or curriculum entry.

## Steps

### 1. Understand
- Read the CURRICULUM.csv row for the target session
- Read the matching lesson file in labs/lessons/
- Ask clarifying questions if scope is ambiguous

### 2. Plan
- Write a 3-7 bullet implementation plan
- Confirm the plan with the user before writing code

### 3. Build
- Create the lab .py file following code-style.md
- Follow the existing file naming: NN_descriptive_name.py
- Add type hints to all public functions
- Include a module-level docstring and `if __name__ == "__main__":` block

### 4. Test
- Write at least 2 tests per new public function
- Run: pytest tests/ -x (stop on first failure)

### 5. Review
- Run /project:review on the diff
- Fix all CRITICAL and MAJOR findings

### 6. Document
- Update memory/progress.md
- Ensure lesson file matches lab file scope

### 7. Commit
- Stage only relevant files
- Follow PR conventions in .claude/rules/pr.md
