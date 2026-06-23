---
name: pr-description
description: Use when writing a pull request title or description, or when asked to summarise changes for a PR, commit message, or changelog entry. Provides the repo's PR format, title conventions, and required checklist.
---

# PR Description Template (AgenticCourse)

## Title format
`type: short description (under 70 chars)`
Types: feat | fix | refactor | docs | test | chore

## Body template
```markdown
## What changed
- Bullet 1
- Bullet 2

## Why
One sentence on the motivation.

## How to test
```bash
python labs/NN_file.py
```

## Checklist
- [ ] pytest labs/ -x passes
- [ ] ruff check labs/ clean
- [ ] CURRICULUM.csv updated (if new session)
- [ ] Lesson file matches lab file
```

## Commit message style
Same type prefix as PR title.
Co-Authored-By line at the end when Claude helped write the code.

