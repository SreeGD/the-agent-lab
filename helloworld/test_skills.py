"""Simulate Claude's skill triggering — given a user query, pick the best-matching skill.

Walks helloworld/skills/, parses each SKILL.md's YAML frontmatter, embeds the
descriptions, then for each test query computes cosine similarity to decide
which skill fires. Same mechanism Claude uses internally to decide which
skills to load on demand.

The triggering signal is the `description` field — that's the entire game.
Good description ↔ good triggering; bad description ↔ skill never fires.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

HERE = Path(__file__).parent
SKILLS_DIR = HERE / "skills"
SIMILARITY_THRESHOLD = 0.30  # below this, "no skill fires"


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


# =====================================================================
# Skill loading — walk skills/ for SKILL.md files, parse frontmatter
# =====================================================================

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_skill_file(path: Path) -> Skill:
    text = path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"No YAML frontmatter in {path}")
    frontmatter = yaml.safe_load(m.group(1))
    return Skill(
        name=frontmatter["name"],
        description=frontmatter["description"],
        body=m.group(2).strip(),
        path=path,
    )


def load_skills(skills_dir: Path) -> list[Skill]:
    return [parse_skill_file(p) for p in sorted(skills_dir.glob("**/SKILL.md"))]


# =====================================================================
# Cosine similarity (pure stdlib; embeddings handle the heavy lifting)
# =====================================================================

def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


# =====================================================================
# Main demo
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CLAUDE SKILLS — triggering by description match")
    print("=" * 70)

    print("\nLoading embedding model (sentence-transformers/all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    print(f"\nDiscovering skills in {SKILLS_DIR.relative_to(HERE)}/...")
    skills = load_skills(SKILLS_DIR)
    print(f"  Found {len(skills)} skill(s):")
    for s in skills:
        print(f"    • {s.name}  ({len(s.body):,} chars body)")
        print(f"        description: {s.description[:80]}...")

    print("\nEmbedding skill descriptions (one-time cost; production caches these)...")
    skill_vecs = [embeddings.embed_query(s.description) for s in skills]

    queries = [
        "How do I chunk and embed docs so the model can answer questions about them?",
        "Why is prompt caching cheaper than full input pricing?",
        "How do I stop my agent from leaking PII or responding to jailbreaks?",
        "What's the weather in Tokyo today?",
    ]

    print("\n" + "=" * 70)
    print("TRIGGERING TEST — 4 queries against 3 skills")
    print("=" * 70)

    for q in queries:
        print(f"\n→ query: {q!r}")
        qvec = embeddings.embed_query(q)

        scored = sorted(
            ((cosine(qvec, sv), s) for sv, s in zip(skill_vecs, skills)),
            key=lambda x: -x[0],
        )

        print("  ranking:")
        for score, s in scored:
            mark = "►" if score == scored[0][0] else " "
            print(f"   {mark} cos={score:.4f}  {s.name}")

        best_score, best_skill = scored[0]
        if best_score < SIMILARITY_THRESHOLD:
            print(f"  → NO SKILL FIRES (best score {best_score:.4f} < threshold {SIMILARITY_THRESHOLD})")
        else:
            print(f"  → FIRES: {best_skill.name}")
            preview = best_skill.body[:180].replace("\n", " ⏎ ")
            print(f"     body preview: {preview}...")

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  - Each SKILL.md has YAML frontmatter with a `description` field.\n"
        "  - We embed the descriptions and the user query into the same vector space.\n"
        "  - The closest description (cosine) is the skill that fires — its body\n"
        "    gets loaded into the LLM's context when relevant.\n"
        "\n"
        "  This is Claude's actual triggering mechanism: skills are NOT always loaded.\n"
        "  They're loaded only when their description semantically matches user intent.\n"
        "  Writing the description is the entire art of skill authoring.\n"
        "\n"
        "  Note the off-topic query ('weather in Tokyo'): all cosines are low,\n"
        "  threshold catches it, no skill fires. That's the right behavior — don't\n"
        "  load context the user isn't asking about."
    )
