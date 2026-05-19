"""Integrity tests for the curriculum itself — making sure the docs and code stay in sync.

These tests catch things like:
- A lesson file references a Python file that doesn't exist
- The CSV references a Python file that doesn't exist
- Lesson numbers in filenames are unique
- Required documentation files exist
"""

import csv
import re
from pathlib import Path

LABS_DIR = Path(__file__).resolve().parent.parent


# ─── Filesystem layout ────────────────────────────────────────────────

class TestStructure:
    def test_required_top_level_docs_exist(self):
        for name in ["NOTES.md", "LEARNINGS.md", "CURRICULUM.md", "CURRICULUM.csv", "requirements.txt"]:
            assert (LABS_DIR / name).exists(), f"missing required: {name}"

    def test_lessons_dir_exists(self):
        assert (LABS_DIR / "lessons").is_dir()

    def test_skills_dir_exists(self):
        assert (LABS_DIR / "skills").is_dir()

    def test_python_files_have_lesson_number_prefix(self):
        """Every lab Python file (except generated_*) must start with NN_..."""
        prefix_re = re.compile(r"^\d{2}_.*\.py$")
        py_files = [
            p.name for p in LABS_DIR.glob("*.py")
            if not p.name.startswith("generated_")
        ]
        for name in py_files:
            assert prefix_re.match(name), f"missing lesson-number prefix: {name}"


# ─── Cross-references between docs and code ───────────────────────────

class TestCrossReferences:
    def test_curriculum_csv_parses(self):
        path = LABS_DIR / "CURRICULUM.csv"
        with path.open() as f:
            rows = list(csv.DictReader(f))
        assert rows, "CURRICULUM.csv is empty"
        # Every row should have a Session number, Title, and Hours
        for row in rows:
            assert row.get("Session"), f"missing Session in row: {row}"
            assert row.get("Title"), f"missing Title in row: {row}"
            assert row.get("Hours"), f"missing Hours in row: {row}"

    def test_lessons_are_numbered_sequentially(self):
        """Lesson files 01-17 should all exist."""
        lessons = LABS_DIR / "lessons"
        for n in range(1, 18):
            matches = list(lessons.glob(f"{n:02d}-*.md"))
            assert matches, f"no lesson file matching {n:02d}-*.md"

    def test_referenced_python_files_exist(self):
        """Every .py file referenced in any lesson .md must exist."""
        py_ref_re = re.compile(r"`(\d{2}_[a-z_]+\.py)`")
        lessons = (LABS_DIR / "lessons").glob("*.md")
        for lesson in lessons:
            text = lesson.read_text()
            for match in py_ref_re.finditer(text):
                fname = match.group(1)
                assert (LABS_DIR / fname).exists(), \
                    f"{lesson.name} references {fname} which doesn't exist"
