# PR Conventions

## Title format
type: short description (under 70 chars)
Types: feat | fix | refactor | docs | test | chore

## Body must include
- What changed (2-5 bullets)
- Why it changed (1 sentence)
- How to test it (runnable command)

## Checklist before merge
- [ ] Tests pass: pytest labs/ -x
- [ ] Ruff clean: ruff check labs/
- [ ] CURRICULUM.csv updated if new session added
- [ ] Lesson file created/updated to match lab file

## Branch strategy
- Feature branches off master
- No direct push to master (hook enforced)
- Squash merge preferred for single-session work
