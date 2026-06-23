Scaffold a new lab session for session number $ARGUMENTS.

Steps:
1. Determine the session title and track from labs/CURRICULUM.csv (row matching session $ARGUMENTS)
2. Create labs/NN_descriptive_name.py with:
   - Module-level docstring explaining the session goal
   - Standard imports (dotenv, langchain_anthropic, pydantic)
   - A main() function and `if __name__ == "__main__":` block
   - A TODO placeholder for the core implementation
3. Create labs/lessons/NN-descriptive-name.md with the lesson template:
   - Title, roadmap, files table, problem statement, analogy, visual, key patterns, run-it, try-this, mental model, related
4. Print the paths of all created files
5. Remind the user to add the session to CURRICULUM.csv if not already there
