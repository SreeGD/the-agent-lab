# 46 — Case Study: Build Slice of vidya-karana (Session 33)

> **Build a working daily practice flow** — a functional vertical slice of the vidya-karana system that a practitioner can actually use. Cost engineering for daily use, trust calibration for a domain where unqualified advice causes harm, and alignment with the actual vidya-karana repo.

---

## Roadmap — where this lesson sits

```
═══════ TRACK K: VIDYA KARANA ═══════

  ✓ Session 31: Domain & Content Strategy
  ✓ Session 32: Reference Arch — Applied-Wisdom Assistant
  ▶ Session 33: CASE STUDY — BUILD SLICE  ◄ HERE
```

---

## Files involved

| File | Role |
|---|---|
| `vidya_karana/build_slice/daily_practice.py` | Daily practice flow |
| `vidya_karana/build_slice/cost_tracker.py` | Per-session cost monitoring |
| `vidya_karana/build_slice/trust_calibration.py` | Uncertainty expression for sacred/sensitive content |

---

## The vertical slice: daily practice flow

A practitioner opens the app each morning. The system:
1. Greets them with a relevant verse (personalised to constitution + season)
2. Offers a short guided practice (5–20 minutes, voice-led)
3. Answers one or two questions about the practice
4. Logs the practice for continuity

This is the daily-use loop. Everything else in the system is secondary to getting this right.

```python
from datetime import datetime
from pydantic import BaseModel

class DailySession(BaseModel):
    practitioner_id: str
    date: str                     # YYYY-MM-DD
    opening_verse: str            # Sanskrit + translation + source
    practice_type: str
    practice_duration_minutes: int
    questions_asked: list[str]
    completed: bool
    cost_inr: float

async def run_daily_session(practitioner_id: str) -> DailySession:
    profile = await load_profile(practitioner_id)
    season = get_ayurvedic_season()  # vasanta/grishma/varsha/sharada/hemanta/shishira

    # 1. Personalised opening verse
    verse = await get_morning_verse(
        dosha=profile.primary_dosha,
        season=season,
        tier=profile.audience_tier,
    )

    # 2. Practice recommendation
    practice = recommend_practice(
        dosha=profile.primary_dosha,
        season=season,
        duration=profile.preferred_duration_minutes,
        recent_practices=profile.completed_practices[-7:],
    )

    # 3. Voice guide (generated or cached)
    guide_audio = await get_practice_guide(
        practice_type=practice.type,
        duration=practice.duration_minutes,
        level=profile.experience_level,
    )

    return DailySession(
        practitioner_id=practitioner_id,
        date=datetime.today().isoformat()[:10],
        opening_verse=verse,
        practice_type=practice.type,
        practice_duration_minutes=practice.duration_minutes,
        questions_asked=[],
        completed=False,
        cost_inr=0.0,
    )
```

---

## Cost engineering for daily use

A daily-use app has a different cost profile than an occasional research tool. The user might open it 365 days/year.

```
Cost budget per daily session:
  Opening verse retrieval:   ₹0.01  (cached — same verse per week/season)
  Practice guide (cached):   ₹0.00  (pre-generated for top-20 practices)
  Practice guide (fresh):    ₹0.08  (Haiku, ~1k tokens)
  Question answering (RAG):  ₹0.05  per question (Sonnet + 2k context)
  
  Average session: ₹0.07–0.15
  Annual cost per user: ₹25–55

  At 10,000 users: ₹2.5–5.5 lakh/year for LLM costs alone
```

**Cost reduction strategies:**

```python
PRACTICE_CACHE: dict[str, bytes] = {}  # pre-generated audio guides

async def get_practice_guide(
    practice_type: str,
    duration: int,
    level: str,
) -> bytes:
    cache_key = f"{practice_type}:{duration}:{level}"

    # Cache hit (free)
    if cache_key in PRACTICE_CACHE:
        return PRACTICE_CACHE[cache_key]

    # Cache miss: generate with Haiku (cheapest)
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0, max_tokens=1024)
    guide_text = llm.invoke(f"Guide a {duration}-min {practice_type} for {level} level.").content
    audio = await text_to_speech(guide_text)

    PRACTICE_CACHE[cache_key] = audio
    return audio

# Pre-generate top 20 practice × duration × level combinations at startup
# Covers ~80% of daily sessions with zero LLM cost
```

---

## Trust calibration for sacred content

This domain has a unique trust challenge. The practitioner is often bringing their practice to the AI — it must not undermine the relationship with their teacher or tradition.

```python
TRUST_LEVELS = {
    "textual_reference": (0.90, 1.00,
        "According to {source}: {content}"),

    "traditional_consensus": (0.75, 0.90,
        "Across most traditional lineages, {content} "
        "[Source: {sources}]"),

    "interpretive": (0.60, 0.75,
        "One interpretation is {content}. "
        "Different teachers may understand this differently. "
        "Your teacher's guidance takes precedence."),

    "uncertain": (0.0, 0.60,
        "I don't have a reliable answer to this from the traditional texts. "
        "This is a good question for your teacher or a qualified acharya."),
}

ALWAYS_DEFER = [
    "Should I do this practice?",          # personal practice guidance
    "Is this right for my condition?",      # health-related
    "What is my dosha?",                    # requires in-person assessment
    "Am I ready for advanced practice?",    # requires teacher's observation
]

def calibrate_response(query: str, confidence: float, content: str, sources: list[str]) -> str:
    # Always defer certain question types to a teacher
    if any(pattern in query.lower() for pattern in ALWAYS_DEFER):
        return (
            "This is exactly the kind of question that benefits from a "
            "teacher who knows you and can observe your practice directly. "
            "I can share what the texts say generally, but your teacher's "
            "guidance is more valuable here."
        )

    for level, (low, high, template) in TRUST_LEVELS.items():
        if low <= confidence < high:
            return template.format(
                content=content,
                source=sources[0] if sources else "traditional teaching",
                sources=", ".join(sources[:3]),
            )
```

---

## Progress continuity

The daily practice feels different if the system remembers you:

```python
class PracticeHistory(BaseModel):
    practitioner_id: str
    total_sessions: int
    current_streak_days: int
    longest_streak_days: int
    practices_completed: dict[str, int]  # {"sun_salutation": 45, "nadi_shodhana": 23}
    milestones: list[str]               # ["7-day streak", "first pranayama", ...]

def generate_progress_note(history: PracticeHistory) -> str:
    if history.current_streak_days == 7:
        return "Seven days of continuous practice — the texts call this the beginning of a real habit."
    if history.current_streak_days == 30:
        return "Thirty days. Patanjali says abhyasa (steady practice) over a long time becomes firmly established."
    if history.total_sessions == 100:
        return "One hundred sessions. You have built something real."
    return f"Day {history.current_streak_days} of your current practice."
```

Quote the texts to mark milestones — it connects the practitioner's personal progress to the tradition.

---

## Integration with vidya-karana repo

This session aligns to the user's actual vidya-karana repository. Before building:

1. **Read the existing README** — understand what's already built
2. **Check the corpus** — what texts are already indexed?
3. **Review the UI** — what does the existing daily practice flow look like?
4. **Identify the gap** — which component needs the AI layer?

The build slice should enhance what exists, not duplicate it. The most common gap: the corpus is built but the conversational Q&A layer (RAG + citation) is missing.

---

## Try this

1. **Daily flow end-to-end** — run `daily_practice.py` for 7 consecutive days. Does the system vary the opening verse? Does it track your streak? Does it recall your last session?

2. **Cost audit** — instrument every LLM call. After 30 simulated sessions, calculate the cost breakdown (verse retrieval, practice guide, Q&A). What's the biggest cost driver? What caching reduces it most?

3. **Trust calibration test** — ask 10 questions at different confidence levels (some well-supported by texts, some ambiguous). Verify the calibrated response matches the actual uncertainty. Ask "Should I do advanced pranayama?" — verify it defers to a teacher.

4. **Progress milestones** — write 10 milestone messages that quote relevant texts. Verify each quote is accurate (check against the source text). Replace any inaccurate quote.

5. **Vidya-karana integration** — open the vidya-karana repo. Identify one specific component where this session's code can be integrated. Write the integration plan (which file, which function, what changes).

---

## Mental model in one line

> **The vidya-karana vertical slice is a daily practice loop: personalised verse (cached) + voice-guided practice (pre-generated for cost) + Q&A (RAG + citation) + progress continuity (streak + milestones with text quotes) — trust calibration always defers to the teacher for personal guidance, and cost engineering keeps the daily session under ₹0.15.**

---

## Related

- **Previous:** [Session 32 — Reference Arch: Applied-Wisdom Assistant](45-applied-wisdom-arch.md)
- **Next:** [Session 34 — Family AI Agent Landscape](47-family-ai-landscape.md)
- **Cost optimization:** [Session 15 — Cost Optimization](26-cost-optimization.md)
- **Voice pipeline (Whisper + TTS):** [Session 26 — Crop Diagnostic](39-crop-diagnostic.md)
- **Curriculum tracker:** Session 33 of 46 — Track K capstone
