# 39 — Reference Arch: Crop Diagnostic + Advisory (Session 26)

> **A vision-first agent that diagnoses crop disease from a photo, explains it in the farmer's language, and gives actionable treatment advice — offline-tolerant and WhatsApp-native.** This session designs the multi-modal architecture that makes that possible.

---

## Roadmap — where this lesson sits

```
═══════ TRACK I: AGRICULTURE ═══════

  ✓ Session 25: AgriTech AI Landscape
  ▶ Session 26: REFERENCE ARCH — CROP DIAGNOSTIC  ◄ HERE
    Session 27: Case Study — Vernacular Farmer Bot
```

---

## Files involved

| File | Role |
|---|---|
| `agritech/cropdoc_architecture.md` | Architecture document + design decisions |

---

## Architecture overview

```
  Farmer Input
  (photo + voice/text query)
         │
         ▼
  ┌─────────────────────────────────────────────────────┐
  │  INPUT NORMALISER                                   │
  │  • Voice → Whisper ASR → text (local language)     │
  │  • Text → detect language (langdetect)             │
  │  • Photo → validate (is this a plant?)             │
  └──────────────────────┬──────────────────────────────┘
                         │
         ┌───────────────┴──────────────┐
         ▼                              ▼
  ┌──────────────┐              ┌───────────────────┐
  │ Vision Agent │              │ Query Translator   │
  │ (Claude      │              │ local lang → EN   │
  │  vision)     │              └────────┬──────────┘
  │              │                       │
  │ • Identify   │              ┌────────▼──────────┐
  │   crop       │              │ Vernacular RAG     │
  │ • Identify   │              │ (multilingual      │
  │   disease    │              │  embeddings)       │
  │ • Confidence │              └────────┬──────────┘
  └──────┬───────┘                       │
         └───────────────┬───────────────┘
                         ▼
              ┌─────────────────────┐
              │  Advisory Generator  │
              │  (structured output) │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │  Response Localiser  │
              │  EN → local lang    │
              │  TTS for voice out  │
              └──────────┬──────────┘
                         ▼
              WhatsApp / SMS / voice response
```

---

## Key patterns

### 1. Vision-first diagnosis

```python
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
import base64

class CropDiagnosis(BaseModel):
    crop_identified: str
    disease_identified: str | None
    pest_identified: str | None
    confidence: float             # 0.0–1.0
    affected_area_percent: int    # estimate of crop area affected
    severity: str                 # "mild" | "moderate" | "severe"
    is_plant_image: bool
    diagnosis_notes: str

def diagnose_from_image(image_bytes: bytes) -> CropDiagnosis:
    llm = ChatAnthropic(model="claude-opus-4-7", max_tokens=1024)
    structured = llm.with_structured_output(CropDiagnosis)

    image_b64 = base64.standard_b64encode(image_bytes).decode()

    return structured.invoke([
        HumanMessage(content=[
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_b64,
                },
            },
            {
                "type": "text",
                "text": (
                    "Analyse this crop image. Identify: "
                    "1) the crop type, "
                    "2) any disease or pest visible, "
                    "3) severity, "
                    "4) percentage of visible area affected. "
                    "If this is not a plant image, set is_plant_image=false."
                ),
            },
        ])
    ])
```

### 2. Voice input pipeline (ASR)

```python
import whisper
import tempfile

_whisper_model = whisper.load_model("small")  # ~250MB; runs offline

def transcribe_voice(audio_bytes: bytes, hint_language: str = None) -> tuple[str, str]:
    """Returns (transcription, detected_language)"""
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        result = _whisper_model.transcribe(
            f.name,
            language=hint_language,  # None = auto-detect
            task="transcribe",
        )
    return result["text"], result["language"]
```

Whisper "small" model runs on-device (CPU) with ~5-10s latency for a 10-second clip — acceptable for WhatsApp async messages.

### 3. Vernacular RAG with multilingual embeddings

```python
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# LaBSE: Language-agnostic BERT Sentence Embeddings
# Supports 109 languages including all Indian scheduled languages
EMBED_MODEL = "sentence-transformers/LaBSE"

embedder = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

# Index is built from English knowledge base
# LaBSE embeds English and vernacular in same space
# So a Telugu query retrieves the right English chunk

def retrieve_advisory(
    query_english: str,       # translated from vernacular
    crop: str,
    disease: str,
    k: int = 4,
) -> list[dict]:
    db = Chroma(embedding_function=embedder, persist_directory="./agritech_kb")
    results = db.similarity_search_with_score(
        f"{crop} {disease} {query_english}",
        k=k,
        filter={"crop": crop} if crop else None,
    )
    return [{"content": doc.page_content, "score": score, "metadata": doc.metadata}
            for doc, score in results]
```

### 4. Structured advisory output

```python
class TreatmentOption(BaseModel):
    treatment: str
    active_ingredient: str | None
    dose: str
    timing: str
    cost_inr_per_acre: int | None
    availability: str             # "widely available" | "district level" | "online only"

class CropAdvisory(BaseModel):
    disease_explanation: str      # in plain language, no jargon
    immediate_action: str         # what to do TODAY
    treatment_options: list[TreatmentOption]
    prevention_next_season: str
    when_to_seek_help: str        # escalation trigger
    confidence: float
    sources: list[str]

ADVISORY_SYSTEM = """You are an agricultural extension officer.
Speak simply. Use the farmer's perspective, not a scientist's.
Give ONE clear immediate action first.
List treatments by cost (cheapest first) and local availability.
Answer ONLY from the provided knowledge base. Cite sources.
If you don't know, say "consult your nearest KVK (Krishi Vigyan Kendra)."

Knowledge base:
{knowledge_base}
"""
```

### 5. Offline-tolerant architecture

```python
class OfflineFallback:
    """
    When connectivity is unavailable, serve cached common-case advice.
    Cache is pre-built for top-50 crop × disease combinations per region.
    """
    def __init__(self, cache_path: str = "./offline_cache.json"):
        with open(cache_path) as f:
            self._cache = json.load(f)

    def lookup(self, crop: str, disease: str) -> CropAdvisory | None:
        key = f"{crop.lower()}:{disease.lower()}"
        cached = self._cache.get(key)
        if cached:
            return CropAdvisory(**cached)
        return None

async def diagnose_and_advise(
    image_bytes: bytes | None,
    voice_bytes: bytes | None,
    text_query: str | None,
    language: str = "te",  # Telugu default
    online: bool = True,
) -> CropAdvisory:
    # Step 1: Get diagnosis (vision if available)
    diagnosis = diagnose_from_image(image_bytes) if image_bytes else None

    # Step 2: Try offline cache first
    if diagnosis and not online:
        cached = OfflineFallback().lookup(
            diagnosis.crop_identified,
            diagnosis.disease_identified or ""
        )
        if cached:
            return cached

    # Step 3: Online path
    query_en = await translate_to_english(text_query or "", source_lang=language)
    retrieved = retrieve_advisory(
        query_english=query_en,
        crop=diagnosis.crop_identified if diagnosis else "",
        disease=diagnosis.disease_identified if diagnosis else "",
    )
    advisory = await generate_advisory(diagnosis, query_en, retrieved)

    # Step 4: Translate response back to farmer's language
    return await localise_advisory(advisory, target_lang=language)
```

---

## WhatsApp output format

WhatsApp messages must be under 1,000 characters for high readability. Structure the advisory:

```
🌾 *Crop:* Paddy
🔴 *Problem:* Blast disease (severe — 60% affected)

⚡ *Do now:* Stop irrigation for 2 days

💊 *Treatment:*
1. Tricyclazole 75% WP — ₹180/acre (available at input shops)
2. Isoprothiolane 40% EC — ₹250/acre (district level)

📅 *Spray:* Morning or evening, not midday

⚠️ *See KVK if:* New leaves also affected in 3 days

Source: ICAR Rice Knowledge Management Portal
```

Plain text, numbered lists, emoji for scannability, ₹ for price, no markdown headers.

---

## Try this

1. **Vision diagnosis test** — collect 10 crop disease images (public datasets: PlantVillage, iNaturalist). Run the vision diagnosis pipeline. Measure accuracy vs. ground truth labels.

2. **Vernacular retrieval** — build a small agritech knowledge base (10 documents about paddy diseases). Translate 5 queries to Telugu. Use LaBSE to retrieve. Compare retrieval quality to English-only queries.

3. **Offline cache builder** — generate pre-built advisories for the top 20 crop × disease combinations in a target region. Serialize to JSON. Measure cache hit rate on a sample of real farmer queries.

4. **WhatsApp formatter** — take a full CropAdvisory object and format it as a WhatsApp message under 800 characters. Build the formatter function. Test it on 5 different advisory outputs.

5. **End-to-end latency test** — measure the latency of: voice → Whisper → translate → retrieve → generate → translate back. Target: < 10 seconds for WhatsApp async response.

---

## Mental model in one line

> **The crop diagnostic agent is vision-first (photo → disease ID) + voice-in (Whisper ASR) + vernacular RAG (LaBSE multilingual embeddings) + structured advisory (cheapest treatment first) + offline fallback (cached top-50 combinations) — all output in < 800 chars for WhatsApp.**

---

## Related

- **Previous:** [Session 25 — AgriTech AI Landscape](38-agritech-landscape.md)
- **Next:** [Session 27 — Case Study: Vernacular Farmer Bot](40-farmer-bot.md)
- **Vision + multi-modal:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **AgriTech capstone:** [Session 34 — Farm Planner](34-farm-planner.md)
- **Curriculum tracker:** Session 26 of 46 — Track I
