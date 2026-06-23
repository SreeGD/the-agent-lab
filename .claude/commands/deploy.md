Deploy the current branch to the staging environment.

Steps:
1. Run `git status` — abort if there are uncommitted changes
2. Run `pytest labs/ -x` — abort if any test fails
3. Run `ruff check labs/` — abort if any lint errors
4. Push the current branch: `git push origin HEAD`
5. Report the pushed branch name and last commit hash
6. Remind the user to open a PR if not already open

Never push directly to master. If on master, abort and ask the user to create a branch.
