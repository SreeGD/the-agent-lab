"""Memory Architectures — five patterns, one survey lesson.

Brij Kishore Pandey's "Top 5 Agent Memory Architectures" infographic
distinguishes five distinct memory shapes. The curriculum already covers
some of them in pieces (Session 8 = working memory via MemorySaver;
Session 3 = episodic LTM; Session 17 = skills as procedural memory).

This lesson surveys all five in one place with the minimum viable demo
of each — what data structure, what API, when to use, where it breaks.

  Demo 1 — Working memory + FIFO eviction (token-budget truncation)
  Demo 2 — Episodic memory (vector store of past interactions)
  Demo 3 — Semantic memory (entity-attribute fact store, not raw history)
  Demo 4 — Procedural memory + learning loop (skill library that grows)
  Demo 5 — Hierarchical memory (hot/warm/cold, MemGPT-style paging)

Each demo is self-contained and prints clearly what it's doing — the
goal is pattern recognition, not a production implementation of any
single architecture.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import openai
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "gpt-4o"
model = ChatOpenAI(model=MODEL, temperature=0)
client = openai.OpenAI()


# =====================================================================
# Demo 1 — Working memory + FIFO eviction
#
# Session 8 covered MemorySaver, which persists conversation state
# across .invoke() calls. What it does NOT do: cap the total token
# budget. This demo shows the FIFO eviction pattern — drop oldest
# turns when total tokens exceed budget.
# =====================================================================

def count_tokens(messages: list[dict]) -> int:
    """Estimate token count using a simple heuristic (4 chars per token)."""
    if not messages:
        return 0
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars // 4


def demo_1_working_memory_fifo():
    print("\n" + "=" * 70)
    print("DEMO 1 — Working memory + FIFO eviction")
    print("=" * 70)
    print("  Token budget: 100 (intentionally small to trigger eviction quickly).")
    print("  Eviction policy: drop oldest user+assistant pair when over budget.\n")

    BUDGET = 100
    history: list[dict] = []

    # Simulate 5 turns with progressively longer assistant responses
    turns = [
        ("My favorite city is San Francisco.",
         "Got it — San Francisco. Foggy summers and a famously walkable downtown."),
        ("I also love reading science fiction.",
         "Noted — sci-fi reader. Asimov, Le Guin, Ted Chiang are great starting points."),
        ("My job is data science at a fintech.",
         "Data science in fintech — risk models, fraud detection, real-time scoring are typical."),
        ("I have a cat named Pixel.",
         "Pixel the cat — noted. Cats named after pixels suggest tech-adjacent humans."),
        ("What was my favorite city?",
         "<would be answered by the model — but we want to see if history is still there>"),
    ]

    for i, (user_msg, asst_msg) in enumerate(turns, 1):
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": asst_msg})
        size = count_tokens(history)

        evictions = 0
        while size > BUDGET and len(history) > 2:
            # drop the oldest user+assistant pair
            dropped_user = history.pop(0)
            dropped_asst = history.pop(0)
            evictions += 1
            print(f"    [turn {i}] EVICTED oldest: user={dropped_user['content'][:40]!r}...")
            size = count_tokens(history)

        kept_users = [m['content'][:30] for m in history if m['role'] == 'user']
        print(f"  turn {i}: total={size} tokens   evicted={evictions}   "
              f"kept_user_msgs={kept_users}")

    print(f"\n  → By turn 5, the original 'San Francisco' message has been EVICTED.")
    print(f"  → The model can no longer answer 'what was my favorite city?' from working memory.")
    print(f"  → That's the failure mode. Episodic memory (Demo 2) solves it.")


# =====================================================================
# Demo 2 — Episodic memory (vector store of past interactions)
#
# Each completed interaction becomes an "episode" with timestamp +
# outcome rating, embedded into a vector store. On a new query, we
# retrieve the most similar past episodes and feed them as context.
# Session 3 covered this in depth; this is the compact recap.
# =====================================================================

class Episode(BaseModel):
    question: str
    answer: str
    timestamp: str
    outcome: Literal["positive", "neutral", "negative"]


# Seed the episodic store with simulated past interactions
SEED_EPISODES = [
    Episode(question="What's my favorite city?",
            answer="San Francisco — you've mentioned it several times.",
            timestamp="2026-04-12T14:32:00Z", outcome="positive"),
    Episode(question="Recommend a sci-fi book.",
            answer="Try 'Exhalation' by Ted Chiang. Short stories, ideal for sci-fi readers.",
            timestamp="2026-04-15T09:11:00Z", outcome="positive"),
    Episode(question="What's a good fraud-detection model?",
            answer="Start with gradient boosting on labeled fraud history; layer anomaly detection on top.",
            timestamp="2026-04-20T11:45:00Z", outcome="positive"),
]


def demo_2_episodic_memory():
    print("\n" + "=" * 70)
    print("DEMO 2 — Episodic memory (vector store of past interactions)")
    print("=" * 70)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    docs = [
        Document(
            page_content=f"Q: {ep.question}\nA: {ep.answer}",
            metadata={"timestamp": ep.timestamp, "outcome": ep.outcome},
        )
        for ep in SEED_EPISODES
    ]
    store = InMemoryVectorStore.from_documents(docs, embeddings)
    print(f"  Episodic store seeded with {len(docs)} past episodes.")

    new_query = "Remind me — what city did I say I prefer?"
    print(f"\n  New query: {new_query!r}")
    hits = store.similarity_search(new_query, k=2)
    print(f"  Retrieved top-{len(hits)} relevant episodes:")
    for i, doc in enumerate(hits, 1):
        print(f"    [{i}] timestamp={doc.metadata['timestamp']}  outcome={doc.metadata['outcome']}")
        print(f"        {doc.page_content[:100]}")

    print(f"\n  → Even after FIFO evicted the 'San Francisco' working-memory turn,")
    print(f"    episodic recall can resurface it. Working + episodic = robust recall.")


# =====================================================================
# Demo 3 — Semantic memory (entity-attribute fact store)
#
# Distilled facts, NOT raw history. Each turn is processed by an
# extraction LLM that pulls structured (key, value, confidence) triples.
# The store is a flat dict keyed by canonical fact names — lookups are
# O(1), not retrieval. This is what gives agents the "what the user
# said three weeks ago" feel without retrieving the actual prose.
# =====================================================================

class UserFact(BaseModel):
    key: str = Field(description="Canonical fact name in snake_case, e.g. 'favorite_city', 'job_role', 'pet_name'.")
    value: str = Field(description="The fact value, lowercased and minimal.")
    confidence: float = Field(ge=0.0, le=1.0)


class FactExtraction(BaseModel):
    facts: list[UserFact] = Field(default_factory=list,
                                  description="Distinct facts about the user from the turn. Empty if none.")


def extract_facts(turn: str) -> list[UserFact]:
    extractor = model.with_structured_output(FactExtraction)
    result = extractor.invoke([
        SystemMessage(
            "Extract any STABLE facts about the user from the message. "
            "Stable facts: preferences, jobs, names, locations, attributes. "
            "Do NOT extract questions, opinions about external things, or "
            "transient mood. Use canonical snake_case keys (favorite_city, "
            "job_role, pet_name, programming_language). Set confidence based "
            "on how explicit the statement is."
        ),
        HumanMessage(turn),
    ])
    return result.facts


def demo_3_semantic_fact_store():
    print("\n" + "=" * 70)
    print("DEMO 3 — Semantic memory (entity-attribute fact store)")
    print("=" * 70)
    fact_store: dict[str, dict] = {}  # key -> {value, confidence, source}

    turns = [
        "My favorite city is San Francisco.",
        "I'm a data scientist at a fintech company.",
        "I have a cat named Pixel.",
        "Today the weather is rainy.",   # transient — should be filtered
        "What's the weather usually like in Seattle?",  # question — no facts
    ]

    for i, turn in enumerate(turns, 1):
        print(f"\n  turn {i}: {turn!r}")
        facts = extract_facts(turn)
        if not facts:
            print(f"    → no stable facts extracted (correct for questions / weather chatter).")
            continue
        for f in facts:
            existing = fact_store.get(f.key)
            if existing and existing["confidence"] >= f.confidence:
                print(f"    [keep existing] {f.key} = {existing['value']!r}")
                continue
            fact_store[f.key] = {"value": f.value, "confidence": f.confidence, "source": turn}
            verb = "update" if existing else "insert"
            print(f"    [{verb:<6}] {f.key} = {f.value!r}  (confidence={f.confidence:.2f})")

    print(f"\n  Final fact store ({len(fact_store)} facts):")
    print(json.dumps({k: v["value"] for k, v in fact_store.items()}, indent=4))
    print(f"\n  → Lookup is dict.get('favorite_city') → O(1), no embedding cost, no LLM.")
    print(f"  → Use semantic memory for: 'who is this user' — preferences, demographics, traits.")
    print(f"  → Use episodic memory for: 'what have we DONE together' — specific conversations.")


# =====================================================================
# Demo 4 — Procedural memory + learning loop
#
# Start with an empty skill library. After each successful multi-step
# solve, the agent summarizes the workflow into a SkillEntry and
# stores it. Future queries that match a skill description "execute"
# the stored workflow instead of re-deriving it. Session 17 covered
# Claude Skills as the deploy-time mechanism; this demo shows the
# *learning* loop that grows the library at runtime.
# =====================================================================

class SkillEntry(BaseModel):
    name: str = Field(description="Short snake_case skill name.")
    when_to_use: str = Field(description="One-sentence description for matching against new queries.")
    steps: list[str] = Field(description="Ordered steps the agent should follow.")


def summarize_to_skill(query: str, solution_trace: list[str]) -> SkillEntry:
    """After a successful solve, distill the trace into a reusable skill."""
    summarizer = model.with_structured_output(SkillEntry)
    return summarizer.invoke([
        SystemMessage(
            "You are summarizing a successful multi-step solution into a "
            "reusable SKILL for an agent's procedural memory. The 'name' "
            "should be a verb-style snake_case identifier. The 'when_to_use' "
            "is what an agent would match against future queries. The 'steps' "
            "are the generalized procedure (drop query-specific values)."
        ),
        HumanMessage(
            f"Original query: {query}\n\n"
            f"Solution trace:\n" + "\n".join(f"- {s}" for s in solution_trace)
        ),
    ])


def find_skill(library: list[SkillEntry], query: str) -> SkillEntry | None:
    """Pick the best-matching skill by description (a real impl would embed)."""
    if not library:
        return None
    options = "\n".join(f"  {i}. {s.name}: {s.when_to_use}" for i, s in enumerate(library))

    class Choice(BaseModel):
        skill_index: int = Field(description=f"0..{len(library)-1}, or -1 if no skill applies.")

    matcher = model.with_structured_output(Choice)
    result = matcher.invoke([
        SystemMessage("Pick the skill that best applies to the query. Use -1 if none fit."),
        HumanMessage(f"Query: {query}\n\nAvailable skills:\n{options}"),
    ])
    if 0 <= result.skill_index < len(library):
        return library[result.skill_index]
    return None


def demo_4_procedural_skill_library():
    print("\n" + "=" * 70)
    print("DEMO 4 — Procedural memory + learning loop")
    print("=" * 70)
    library: list[SkillEntry] = []

    # Round 1: solve a query from scratch, save the workflow as a skill
    print(f"\n  Round 1 (no skills yet):")
    q1 = "Build a fraud-detection pipeline."
    trace1 = [
        "Collect labeled historical transactions.",
        "Engineer features: amount, merchant category, time-of-day, velocity.",
        "Train a gradient boosting classifier on the labeled set.",
        "Layer an unsupervised anomaly detector on top for novel patterns.",
        "Deploy with a confidence threshold; route high-risk transactions to manual review.",
    ]
    print(f"  query: {q1}")
    print(f"  matched skill: {find_skill(library, q1) and 'yes' or '(none — derive from scratch)'}")
    print(f"  agent derived solution in {len(trace1)} steps. Distilling into a skill...")
    skill1 = summarize_to_skill(q1, trace1)
    library.append(skill1)
    print(f"  [SKILL LEARNED] {skill1.name}: {skill1.when_to_use}")
    print(f"  Library now has {len(library)} skill(s).")

    # Round 2: similar query — should match the stored skill
    print(f"\n  Round 2 (skill library has 1 entry):")
    q2 = "I need a system to catch credit-card fraud in real time."
    matched = find_skill(library, q2)
    if matched:
        print(f"  query: {q2}")
        print(f"  matched skill: {matched.name!r} ({matched.when_to_use})")
        print(f"  agent EXECUTES stored steps instead of re-deriving:")
        for i, step in enumerate(matched.steps[:3], 1):
            print(f"    {i}. {step}")
    else:
        print(f"  no match — would derive from scratch.")

    # Round 3: unrelated query — no skill should match
    print(f"\n  Round 3 (skill library still has 1 entry):")
    q3 = "Help me pick a wedding venue in Hyderabad."
    matched = find_skill(library, q3)
    print(f"  query: {q3}")
    print(f"  matched skill: {matched.name if matched else '(none — correctly rejects unrelated query)'}")

    print(f"\n  → The library GREW from runtime experience: 1 skill after 1 success.")
    print(f"  → Future fraud-detection queries skip the derivation step entirely.")
    print(f"  → In production, gate skill admission on outcome=positive (don't learn bad patterns).")


# =====================================================================
# Demo 5 — Hierarchical memory (MemGPT-style)
#
# Three tiers paged between like an OS:
#   hot     — current context (small, fast, expensive: tokens)
#   warm    — recall buffer (medium, in-RAM, free until used)
#   cold    — archival store (unlimited, on-disk-equivalent, free)
# When hot overflows, evict to warm. When warm overflows, evict to cold.
# When a query references something in warm or cold, "page in" to hot.
# =====================================================================

class HierarchicalMemory:
    def __init__(self, hot_limit: int = 2, warm_limit: int = 4):
        self.hot: list[str] = []
        self.warm: list[str] = []
        self.cold: list[str] = []
        self.hot_limit = hot_limit
        self.warm_limit = warm_limit
        self.events: list[str] = []

    def add_to_hot(self, item: str):
        self.events.append(f"INSERT hot: {item!r}")
        self.hot.append(item)
        self._evict()

    def _evict(self):
        while len(self.hot) > self.hot_limit:
            old = self.hot.pop(0)
            self.warm.append(old)
            self.events.append(f"EVICT hot→warm: {old!r}")
        while len(self.warm) > self.warm_limit:
            old = self.warm.pop(0)
            self.cold.append(old)
            self.events.append(f"EVICT warm→cold: {old!r}")

    def page_in(self, query: str) -> str | None:
        """Search warm + cold for a tier match, page back to hot if found."""
        for tier_name, tier in (("warm", self.warm), ("cold", self.cold)):
            for item in tier:
                if query.lower() in item.lower():
                    tier.remove(item)
                    self.events.append(f"PAGE_IN {tier_name}→hot: {item!r}")
                    self.add_to_hot(item)
                    return item
        return None

    def snapshot(self) -> str:
        return (f"  hot ({len(self.hot)}/{self.hot_limit}):   {self.hot}\n"
                f"  warm ({len(self.warm)}/{self.warm_limit}): {self.warm}\n"
                f"  cold ({len(self.cold)}/∞): {self.cold}")


def demo_5_hierarchical_memgpt():
    print("\n" + "=" * 70)
    print("DEMO 5 — Hierarchical memory (MemGPT-style hot/warm/cold paging)")
    print("=" * 70)
    print("  Limits: hot=2, warm=4, cold=unlimited (intentionally tiny for the demo).")

    mem = HierarchicalMemory(hot_limit=2, warm_limit=4)

    inserts = [
        "user_favorite_city: San Francisco",
        "user_job: data scientist in fintech",
        "user_pet: cat named Pixel",
        "user_book_pref: science fiction",
        "user_timezone: PST",
        "user_dietary: vegetarian",
        "user_languages_spoken: English, Hindi, Telugu",
    ]

    for item in inserts:
        mem.add_to_hot(item)

    print(f"\n  After {len(inserts)} inserts:")
    print(mem.snapshot())

    print(f"\n  Eviction trace:")
    for e in mem.events:
        print(f"    {e}")

    # Now a query references something that's been paged out
    print(f"\n  Query references the user's favorite city (which is now in COLD).")
    paged = mem.page_in("favorite_city")
    print(f"  page_in result: {paged!r}")
    print(f"\n  After paging in:")
    print(mem.snapshot())

    print(f"\n  → Total recall is preserved across paging tiers.")
    print(f"  → Only 'hot' costs tokens at inference time — warm + cold are free.")
    print(f"  → Real MemGPT uses this exact shape, with cold backed by SQLite/Postgres.")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("MEMORY ARCHITECTURES — five patterns, one survey")
    print("=" * 70)

    demo_1_working_memory_fifo()
    demo_2_episodic_memory()
    demo_3_semantic_fact_store()
    demo_4_procedural_skill_library()
    demo_5_hierarchical_memgpt()

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED — choose the right shape per use case")
    print("=" * 70)
    print(
        "  Pattern             Data structure      Lookup        Cost\n"
        "  ─────────           ──────────────      ──────        ────\n"
        "  Working (FIFO)      list[Message]       index         tokens\n"
        "  Episodic            vector store        kNN embedding embed + retrieve\n"
        "  Semantic (facts)    dict[key, value]    O(1) get      free\n"
        "  Procedural (skills) list[SkillEntry]    matcher LLM   1 LLM call\n"
        "  Hierarchical        3 tiers + paging    keyword in cold free until paged in\n\n"
        "  Real agents combine these:\n"
        "    • Working    holds the current turn\n"
        "    • Semantic   holds the user profile (preferences, role, traits)\n"
        "    • Episodic   holds session-scoped past interactions\n"
        "    • Procedural holds learned workflows (skills + how-to)\n"
        "    • Hierarchical is how all the above share a finite token budget\n\n"
        "  The most expensive mistake is using working memory for everything —\n"
        "  context bloats, cost balloons, latency tanks. Pick the shape that\n"
        "  matches the data shape."
    )
