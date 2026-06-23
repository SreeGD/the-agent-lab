# 48 — Reference Arch I: Meal Specialist + Family Archivist (Session 35)

> **Two of the three specialist agents that make up the Family Concierge.** The Meal Specialist handles food planning and dietary tracking. The Family Archivist maintains long-term semantic memory of family moments — photos, voice memos, milestones. Both share a common family memory schema and route through a "who's asking" router.

---

## Roadmap — where this lesson sits

```
═══════ TRACK L: FAMILY AI AGENT ═══════

  ✓ Session 34: Landscape — Identity, Privacy, Channels
  ▶ Session 35: REFERENCE ARCH I — MEAL + ARCHIVIST  ◄ HERE
    Session 36: Reference Arch II — Scheduler + Proactive Loop
    Session 37: Case Study + Vertical Slice Build
```

---

## Files involved

| File | Role |
|---|---|
| `family_ai/meal_archivist_arch.md` | Architecture document |

---

## Shared family memory schema

Both specialists read from and write to the same family memory store:

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

MemoryType = Literal["meal", "photo", "voice_memo", "milestone", "preference", "event"]

class FamilyMemory(BaseModel):
    memory_id: str
    family_id: str
    member_id: str | None       # None = whole-family memory
    memory_type: MemoryType
    content: str                # text description or transcription
    embedding: list[float]      # for semantic retrieval
    media_url: str | None       # S3 URL for photo/audio
    tags: list[str]             # ["birthday", "Raju", "paddy harvest"]
    created_at: datetime
    year: int | None            # for "memories from X years ago" queries
    is_private: bool = False    # private to one member

class FamilyMemoryStore:
    """Semantic search over family memories with temporal filtering."""

    def retrieve(
        self,
        query: str,
        family_id: str,
        member_id: str | None = None,
        memory_types: list[MemoryType] | None = None,
        years_ago: int | None = None,
        k: int = 5,
    ) -> list[FamilyMemory]:
        # Build filter
        filter_dict = {"family_id": family_id}
        if member_id:
            filter_dict["member_id"] = member_id
        if memory_types:
            filter_dict["memory_type"] = {"$in": memory_types}
        if years_ago:
            target_year = datetime.now().year - years_ago
            filter_dict["year"] = target_year

        # Semantic search
        return self._vector_db.similarity_search(
            query, k=k, filter=filter_dict
        )
```

---

## Meal Specialist

```
Capabilities:
  • Weekly meal planning (family dietary preferences + availability)
  • Recipe lookup and adaptation (allergies, ingredients on hand)
  • Grocery list generation
  • "What should I cook tonight?" Q&A
  • Dietary tracking (calories, nutrients — if family opts in)
  • Save "family favourites" to memory
```

### Meal planning pipeline

```python
from pydantic import BaseModel

class FamilyDietaryProfile(BaseModel):
    family_id: str
    restrictions: list[str]        # ["vegetarian", "nut allergy (Priya)"]
    preferences: list[str]         # ["South Indian", "low-oil"]
    dislikes: list[str]            # ["bitter gourd", "okra"]
    meal_count_per_day: int
    serving_size: int              # number of people

class MealPlan(BaseModel):
    week_of: str                   # YYYY-MM-DD (Monday)
    days: dict[str, list[str]]     # {"Monday": ["Idli", "Dal rice", "Dosa"]}
    grocery_list: list[str]
    estimated_cook_time_minutes: dict[str, int]

MEAL_SPECIALIST_SYSTEM = """You are a family meal planning assistant.

You know this family's preferences:
{dietary_profile}

Their favourite meals (from family memory):
{favourite_meals}

Rules:
- Never suggest dishes containing the family's allergens
- Vary cuisines across the week (no same dish twice)
- Consider cooking time: weekdays < 30 min, weekends up to 60 min
- Generate a grocery list after the meal plan
- If asked "what do we have?", ask the family to share pantry contents
"""

async def generate_weekly_plan(
    family: FamilyAccount,
    dietary_profile: FamilyDietaryProfile,
    memory_store: FamilyMemoryStore,
) -> MealPlan:
    # Retrieve favourite meals from memory
    favourites = memory_store.retrieve(
        query="family favourite meal delicious loved",
        family_id=family.family_id,
        memory_types=["meal"],
        k=10,
    )
    favourites_text = "\n".join(m.content for m in favourites)

    llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)
    structured = llm.with_structured_output(MealPlan)

    return structured.invoke([
        SystemMessage(content=MEAL_SPECIALIST_SYSTEM.format(
            dietary_profile=dietary_profile.model_dump_json(indent=2),
            favourite_meals=favourites_text,
        )),
        HumanMessage(content="Generate this week's meal plan."),
    ])
```

### Saving a meal to memory

```python
async def save_meal_memory(
    family_id: str,
    member_id: str,
    meal_description: str,
    photo_bytes: bytes | None,
    memory_store: FamilyMemoryStore,
):
    """Called when a family member says 'save this recipe' or 'we loved this'."""
    photo_url = await upload_to_s3(photo_bytes) if photo_bytes else None

    memory = FamilyMemory(
        memory_id=str(uuid4()),
        family_id=family_id,
        member_id=member_id,
        memory_type="meal",
        content=meal_description,
        embedding=embedder.embed_query(meal_description),
        media_url=photo_url,
        tags=extract_tags(meal_description),  # ["biryani", "Eid", "celebration"]
        created_at=datetime.utcnow(),
        year=datetime.now().year,
    )
    await memory_store.save(memory)
    return f"Saved '{meal_description[:50]}' to your family favourites."
```

---

## Family Archivist

```
Capabilities:
  • Store photos + voice memos with semantic descriptions
  • Answer "remember when...?" queries
  • Surface "on this day" memories (temporal retrieval)
  • Create milestone summaries ("Priya's first year")
  • Share memories to WhatsApp ("send that birthday photo")
```

### Photo ingestion with vision description

```python
async def archive_photo(
    photo_bytes: bytes,
    caption: str | None,
    member_id: str,
    family_id: str,
    memory_store: FamilyMemoryStore,
) -> FamilyMemory:
    # Step 1: Generate semantic description via vision
    llm = ChatAnthropic(model="claude-opus-4-7", max_tokens=256)
    description = llm.invoke([
        HumanMessage(content=[
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(photo_bytes).decode(),
                },
            },
            {
                "type": "text",
                "text": (
                    "Describe this family photo in 2-3 sentences for a memory archive. "
                    "Include: who appears (if recognisable), what they're doing, "
                    "the occasion if visible, the mood. "
                    f"Caption provided: {caption or 'none'}"
                ),
            },
        ])
    ]).content

    # Step 2: Store with embedding
    photo_url = await upload_to_s3(photo_bytes)
    memory = FamilyMemory(
        memory_id=str(uuid4()),
        family_id=family_id,
        member_id=member_id,
        memory_type="photo",
        content=description,
        embedding=embedder.embed_query(description),
        media_url=photo_url,
        tags=extract_tags(description),
        created_at=datetime.utcnow(),
        year=datetime.now().year,
    )
    await memory_store.save(memory)
    return memory
```

### "On this day" retrieval

```python
async def on_this_day(
    family_id: str,
    memory_store: FamilyMemoryStore,
    years_back: int = 5,
) -> list[FamilyMemory]:
    today_month_day = datetime.now().strftime("%m-%d")
    memories = []

    for years_ago in range(1, years_back + 1):
        target_year = datetime.now().year - years_ago
        year_memories = memory_store.retrieve(
            query=f"family moment {today_month_day}",
            family_id=family_id,
            years_ago=years_ago,
            k=2,
        )
        memories.extend(year_memories)

    return memories

async def format_on_this_day_message(memories: list[FamilyMemory]) -> str:
    if not memories:
        return None
    lines = ["🗓 *On this day...*\n"]
    for m in memories:
        years_ago = datetime.now().year - m.year
        lines.append(
            f"*{years_ago} year{'s' if years_ago > 1 else ''} ago:* {m.content[:120]}"
        )
        if m.media_url:
            lines.append(f"[📷 View photo]({m.media_url})")
    return "\n".join(lines)
```

---

## Try this

1. **Meal plan generation** — create a sample FamilyDietaryProfile (vegetarian, 4 people, South Indian preference). Generate a weekly meal plan. Verify it respects restrictions and varies across the week.

2. **Grocery list extraction** — take the meal plan and generate a grocery list. Group by category (vegetables, grains, dairy). Remove duplicates. Estimate quantities.

3. **Photo archival** — take 5 family-style photos (or use stock photos). Run the vision description pipeline. Evaluate: are the descriptions semantically rich enough to retrieve later by query?

4. **"On this day" retrieval** — seed the memory store with 20 memories across 5 years. Query "on this day". Verify temporal filtering works correctly. Test edge case: no memories for a particular date.

5. **WhatsApp message format** — take the "on this day" result and format it as a WhatsApp message under 800 characters. Include the photo URL as a link. Test with a photo from the archive.

---

## Mental model in one line

> **Meal Specialist + Family Archivist share a FamilyMemoryStore (semantic vector search with temporal + member filtering) — the Meal Specialist reads meal preferences and writes favourites, the Archivist writes photo descriptions (vision-generated) and voice memo transcriptions and surfaces temporal memories ("on this day") — all through the same memory schema.**

---

## Related

- **Previous:** [Session 34 — Family AI Landscape](47-family-ai-landscape.md)
- **Next:** [Session 36 — Reference Arch II: Scheduler + Proactive Loop](49-scheduler-proactive.md)
- **Long-term memory patterns:** [Session 3 — Multi-agent + LTM](14-multi-agent-ltm.md)
- **Vision (photo description):** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **Curriculum tracker:** Session 35 of 46 — Track L
