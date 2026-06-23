# 45 — Reference Arch: Applied-Wisdom Assistant (Session 32)

> **A multi-source RAG system that supports daily yoga and meditation practice** — text retrieval from Sanskrit corpora, voice guidance for asana sequences, vision for pose feedback, and citation back to the source text on every answer.

---

## Roadmap — where this lesson sits

```
═══════ TRACK K: VIDYA KARANA ═══════

  ✓ Session 31: Domain & Content Strategy
  ▶ Session 32: REFERENCE ARCH — APPLIED-WISDOM  ◄ HERE
    Session 33: Case Study — Build Slice of vidya-karana
```

---

## Files involved

| File | Role |
|---|---|
| `vidya_karana/architecture.md` | Architecture document + design decisions |

---

## Architecture overview

```
  User query (text / voice / photo)
         │
         ▼
  ┌─────────────────────────────────────────────────────┐
  │  INPUT ROUTER                                       │
  │  • Text → detect language + audience tier           │
  │  • Voice → Whisper → text → route                  │
  │  • Photo → vision model → pose/mudra identification │
  └──────────────────────┬──────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
  ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐
  │ Text RAG     │ │ Practice     │ │ Vision Feedback  │
  │ (Sanskrit    │ │ Guide        │ │ (pose correction)│
  │  corpus +   │ │ (sequenced   │ │                  │
  │  commentary)│ │  voice TTS)  │ │                  │
  └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘
         └────────────────┼──────────────────┘
                          ▼
              ┌───────────────────────┐
              │  Response Generator   │
              │  • Tier-appropriate   │
              │  • Citation to source │
              │  • Wellness boundary  │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │  Personalisation      │
              │  • Practice history   │
              │  • Constitution type  │
              │  • Progress tracking  │
              └───────────────────────┘
```

---

## Multi-source RAG: Sanskrit corpus

```python
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from pydantic import BaseModel

class TextChunk(BaseModel):
    source_text: str           # original Sanskrit (Devanagari)
    transliteration: str       # IAST
    translation: str           # English (public domain)
    source_ref: str            # "Yoga Sutras 1.2" or "Charaka Samhita Su.1.42"
    tradition: str             # "yoga" | "vedanta" | "ayurveda" | "tantra"
    audience_tier: int         # 1–4 (minimum tier needed to understand)
    is_practice_instruction: bool
    safety_prerequisites: list[str]   # ["basic pranayama", "teacher guidance"]

# Use multilingual embedding (handles Sanskrit, Hindi, English in same space)
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/LaBSE")

def retrieve_wisdom(
    query: str,
    tradition: str | None = None,
    audience_tier: int = 1,
    k: int = 5,
) -> list[TextChunk]:
    db = Chroma(embedding_function=embedder, persist_directory="./vidya_kb")
    filter_dict = {"audience_tier": {"$lte": audience_tier}}
    if tradition:
        filter_dict["tradition"] = tradition

    results = db.similarity_search_with_score(query, k=k, filter=filter_dict)
    return [TextChunk(**doc.metadata, source_text=doc.page_content)
            for doc, _ in results]
```

---

## Citation-to-source-text pattern

Every answer must trace back to a primary source:

```python
WISDOM_SYSTEM = """You are an applied wisdom assistant drawing from Indian philosophical traditions.

Citation rules:
- Every teaching must cite its source: [Source: Yoga Sutras 1.2]
- For practices, cite the tradition and text where the practice originates
- When multiple traditions have different views, present all: 
  "In Patanjali's framework... In the Tantric tradition..."
- Never present your interpretation as the text's meaning without quoting the text
- For safety-sensitive practices (advanced pranayama, kriyas), always state prerequisites

Wellness boundary:
- Use "may support", "traditionally used for", "in Ayurvedic understanding"
- Never: "treats", "cures", "proven to heal"

Retrieved texts:
{retrieved_texts}

Audience tier: {tier} (1=beginner, 4=scholar)
"""

def format_citation_response(chunks: list[TextChunk]) -> str:
    formatted = []
    for chunk in chunks:
        formatted.append(
            f"[{chunk.source_ref}]\n"
            f"Sanskrit: {chunk.source_text}\n"
            f"Translation: {chunk.translation}\n"
        )
    return "\n\n".join(formatted)
```

---

## Voice-guided practice (TTS)

For guided asana and pranayama sessions, voice is the primary output:

```python
from pathlib import Path
import anthropic

def generate_practice_guide(
    practice_type: str,   # "sun_salutation" | "nadi_shodhana" | "yoga_nidra"
    duration_minutes: int,
    level: str,           # "beginner" | "intermediate" | "advanced"
) -> str:
    """Generate a spoken-word practice guide."""
    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=(
            "You are a yoga teacher guiding a live practice session. "
            "Write in second person, present tense. "
            "Include breath cues, timing, and safety reminders. "
            "Pace the instructions for spoken delivery (one instruction per breath). "
            "No markdown — this will be converted to speech."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Guide a {duration_minutes}-minute {practice_type} session "
                f"for a {level} practitioner."
            ),
        }],
    )
    return response.content[0].text

# Convert to audio using TTS (e.g., ElevenLabs, Google TTS, or Kokoro open-source)
def text_to_speech(text: str, voice: str = "calm_female_en") -> bytes:
    # Implementation depends on TTS provider
    pass
```

---

## Vision for pose feedback

```python
def analyse_yoga_pose(image_bytes: bytes) -> dict:
    """Identify pose and provide alignment feedback."""
    client = anthropic.Anthropic()
    import base64

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.standard_b64encode(image_bytes).decode(),
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Identify the yoga pose in this image. "
                        "Provide: 1) pose name (Sanskrit + English), "
                        "2) 2-3 alignment observations, "
                        "3) one primary adjustment suggestion. "
                        "Be encouraging but specific. "
                        "If you cannot identify a yoga pose, say so."
                    ),
                },
            ],
        }],
    )
    return {"feedback": response.content[0].text}
```

---

## Personalisation: practice history + constitution

```python
from pydantic import BaseModel
from typing import Literal

AyurvedicDosha = Literal["vata", "pitta", "kapha", "vata-pitta", "pitta-kapha", "vata-kapha", "tridoshic"]

class PractitionerProfile(BaseModel):
    practitioner_id: str
    primary_dosha: AyurvedicDosha | None
    experience_years: int
    practice_goals: list[str]           # ["flexibility", "stress", "meditation depth"]
    completed_practices: list[str]      # ["sun_salutation", "nadi_shodhana"]
    contraindications: list[str]        # ["lower back injury", "hypertension"]
    preferred_language: str             # "en" | "hi" | "te"
    audience_tier: int                  # auto-detected from interaction history

def personalise_recommendation(
    profile: PractitionerProfile,
    base_recommendation: str,
) -> str:
    """Adapt recommendation to practitioner's constitution and history."""
    if profile.primary_dosha == "vata":
        modifier = "Ground and slow down: vata types benefit from slower, held poses."
    elif profile.primary_dosha == "pitta":
        modifier = "Cool and surrender: pitta types benefit from cooling, non-competitive practice."
    elif profile.primary_dosha == "kapha":
        modifier = "Energise and lift: kapha types benefit from dynamic, warming practice."
    else:
        modifier = ""

    if any(c in base_recommendation.lower() for c in profile.contraindications):
        modifier += " Note: adapt or skip poses that affect your contraindicated areas."

    return f"{base_recommendation}\n\n{modifier}".strip()
```

---

## Try this

1. **Sanskrit RAG** — index 20 Yoga Sutra verses (public domain translation by Charles Johnston). Ask 5 questions at different audience tiers. Verify the retrieved chunks match the tier filter.

2. **Voice guide generation** — generate a 5-minute guided pranayama session (nadi shodhana). Read it aloud with a timer. Does the pacing work? Are the instructions clear without visual aids?

3. **Pose feedback** — take 5 yoga pose photos (your own or from a public dataset). Run the vision analysis. Evaluate: is the pose identified correctly? Is the alignment feedback accurate and safe?

4. **Citation accuracy** — generate 10 answers to yoga questions. For each citation [Source: X.Y], verify the reference is real and the attribution is correct. Any false citation is a hallucination.

5. **Constitution personalisation** — create practitioner profiles for all three primary doshas. Ask the same question (e.g., "What pranayama should I practice in the morning?") for each. Verify the personalisation changes the recommendation meaningfully.

---

## Mental model in one line

> **The applied-wisdom assistant is multi-source Sanskrit RAG (LaBSE for multilingual retrieval) + citation-to-source-text (every claim cites chapter/verse) + voice-guided practice (TTS output) + vision pose feedback (Claude vision) + dosha-based personalisation — with wellness boundary enforcement at every output layer.**

---

## Related

- **Previous:** [Session 31 — Domain & Content Strategy](44-vidya-karana-domain.md)
- **Next:** [Session 33 — Case Study: Build Slice of vidya-karana](46-vidya-karana-case-study.md)
- **Multi-modal foundation:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **Voice pipeline:** [Session 27 — Case Study: Vernacular Farmer Bot](40-farmer-bot.md)
- **Curriculum tracker:** Session 32 of 46 — Track K
