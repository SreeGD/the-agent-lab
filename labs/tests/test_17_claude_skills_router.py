"""Unit tests for the Claude Skills router — frontmatter parsing + cosine."""

import math
import re
from pathlib import Path

import pytest
import yaml


# Replicate the helpers — keeps tests fast (no embeddings model load).

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_skill_text(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("No YAML frontmatter")
    return {
        "frontmatter": yaml.safe_load(m.group(1)),
        "body": m.group(2).strip(),
    }


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na * nb > 0 else 0.0


SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


# ─── Frontmatter parsing ──────────────────────────────────────────────

class TestParseSkill:
    def test_well_formed_skill(self):
        text = (
            "---\n"
            "name: my-skill\n"
            "description: Use when the user asks about X.\n"
            "---\n"
            "# Body\n"
            "Some content here.\n"
        )
        result = parse_skill_text(text)
        assert result["frontmatter"]["name"] == "my-skill"
        assert "user asks about X" in result["frontmatter"]["description"]
        assert "Some content here" in result["body"]

    def test_missing_frontmatter_raises(self):
        text = "Just a body, no frontmatter."
        with pytest.raises(ValueError):
            parse_skill_text(text)

    def test_multiline_description(self):
        text = (
            "---\n"
            "name: test\n"
            "description: A description\n"
            "  that wraps across lines.\n"
            "---\n"
            "body\n"
        )
        result = parse_skill_text(text)
        assert "wraps across lines" in result["frontmatter"]["description"]


# ─── Cosine similarity ────────────────────────────────────────────────

class TestCosine:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 1.0, 0.5]
        assert cosine(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        # Defensive: don't crash on zero vector
        assert cosine([0, 0, 0], [1, 1, 1]) == 0.0


# ─── Real skill files in the repo ─────────────────────────────────────

class TestActualSkills:
    """Verify the actual SKILL.md files in skills/ all parse cleanly."""

    def test_all_skills_parse(self):
        skill_files = list(SKILLS_DIR.glob("**/SKILL.md"))
        assert skill_files, "no SKILL.md files found in skills/"

        for path in skill_files:
            text = path.read_text()
            parsed = parse_skill_text(text)

            # Every skill must have name + description
            assert "name" in parsed["frontmatter"], f"{path}: missing 'name'"
            assert "description" in parsed["frontmatter"], f"{path}: missing 'description'"

            # Body must be non-empty
            assert len(parsed["body"]) > 100, f"{path}: body too short ({len(parsed['body'])} chars)"

    def test_skill_names_are_unique(self):
        skill_files = list(SKILLS_DIR.glob("**/SKILL.md"))
        names = []
        for path in skill_files:
            parsed = parse_skill_text(path.read_text())
            names.append(parsed["frontmatter"]["name"])
        assert len(names) == len(set(names)), f"duplicate skill names: {names}"

    def test_descriptions_are_substantial(self):
        # Descriptions are the entire triggering signal — they should be 30+ chars
        skill_files = list(SKILLS_DIR.glob("**/SKILL.md"))
        for path in skill_files:
            parsed = parse_skill_text(path.read_text())
            desc = parsed["frontmatter"]["description"]
            assert len(desc) >= 30, f"{path}: description too short ({len(desc)} chars): {desc!r}"
