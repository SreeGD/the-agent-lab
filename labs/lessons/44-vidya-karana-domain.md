# 44 — Domain & Content Strategy: Vidya Karana (Session 31)

> **Vedic texts, Yoga Sutras, Ayurvedic shastras — a knowledge base unlike any other.** Before building the AI system, map the domain: what texts, what audience tiers, what languages, and where the line between wellness guidance and medical claims sits. Cultural sensitivity is a technical constraint, not a soft concern.

---

## Roadmap — where this lesson sits

```
═══════ TRACK K: VIDYA KARANA ═══════

  ▶ Session 31: DOMAIN & CONTENT STRATEGY  ◄ HERE
    Session 32: Reference Arch — Applied-Wisdom Assistant
    Session 33: Case Study — Build Slice of vidya-karana

  Prerequisites: Sessions 18–21
  Note: Will refine with the vidya-karana repo.
```

---

## Files involved

| File | Role |
|---|---|
| `vidya_karana/domain_map.md` | Text corpus, audience map, content boundaries |

---

## The domain: what is Vidya Karana?

Vidya Karana (विद्या करण) is the domain of applied ancient Indian wisdom — practical knowledge systems derived from:

| Tradition | Primary texts | Core domain |
|---|---|---|
| Yoga | Yoga Sutras (Patanjali), Hatha Yoga Pradipika, Gheranda Samhita | Asana, pranayama, meditation, samadhi |
| Vedanta | Upanishads, Bhagavad Gita, Brahma Sutras | Philosophy, self-inquiry, non-duality |
| Ayurveda | Charaka Samhita, Sushruta Samhita, Ashtanga Hrdayam | Health, constitution (dosha), food, herbs |
| Tantra | Vigyan Bhairav Tantra, various agamas | Meditation practices, energy work |
| Jyotisha | Brihat Parashara Hora Shastra | Vedic astrology |
| Sanskrit | Panini's Ashtadhyayi | Grammar and language |

The challenge: these are living traditions with multiple lineages, contested interpretations, and a mix of text that is public domain, commentary that is copyrighted, and oral transmission that was never written down.

---

## Audience tiers

A single system cannot serve all audiences equally. Define tiers:

| Tier | Profile | Needs | Content level |
|---|---|---|---|
| **Tier 1: Seeker** | Urban, English-literate, beginning yoga or meditation | Accessible introductions, "what is X?", safety | Plain English, no Sanskrit jargon |
| **Tier 2: Practitioner** | Regular practice (1+ years), some Sanskrit, lineage-aware | Deeper textual references, practice guidance, Q&A | English + transliteration + devanagari |
| **Tier 3: Scholar** | Academic or advanced practitioner | Primary text access, commentary comparison, etymology | Sanskrit primary sources + commentary |
| **Tier 4: Teacher** | Teaching yoga, Ayurveda, or Vedanta | Curriculum design, student FAQ, practice sequencing | All of above + pedagogical framing |

The AI system must detect which tier the user is in and respond appropriately. A Tier 1 question about "pranayama" gets a 100-word English explanation; the same question from a Tier 3 scholar gets a textual comparison of Patanjali vs. Hatha Yoga Pradipika definitions.

---

## Language strategy

```
Text corpus languages:
  Sanskrit (Devanagari script) — primary source texts
  Sanskrit (IAST transliteration) — academic standard
  Hindi — commentaries, modern teachers
  English — translations, contemporary interpretations

User interface languages:
  English — Tier 1, 2, 3, 4 (global)
  Hindi — Indian practitioners, Tier 2–4
  Tamil, Telugu, Kannada — regional practitioners (Tier 2+)

Multilingual strategy:
  • Store texts in original Sanskrit (Devanagari)
  • Index with IAST transliteration for search
  • Retrieve in original; translate/explain in user's language
  • Never auto-translate Sanskrit — human-reviewed translations only
```

Sanskrit transliteration is not optional — searching "pranayama" must find "प्राणायाम" (Devanagari) and "prāṇāyāma" (IAST). Use a multilingual embedding model (LaBSE or mE5) that handles all three representations.

---

## The wellness-vs-medical-claim boundary

This is the most critical content boundary in this domain:

| Statement | Category | Status |
|---|---|---|
| "Pranayama is a breath control practice" | Wellness education | Safe |
| "Daily meditation may support stress management" | Wellness claim | Safe (with "may") |
| "Ashwagandha supports healthy stress response" | Structure/function claim | Safe (US: needs FTC disclaimer) |
| "Ashwagandha treats anxiety disorder" | Medical claim | NOT SAFE — requires clinical evidence |
| "This Ayurvedic protocol will cure your diabetes" | Medical claim | Illegal in most jurisdictions |
| "Triphala cleanses the colon" | Traditional claim | Requires context: "according to Ayurvedic tradition" |

**Technical enforcement:**

```python
MEDICAL_CLAIM_PATTERNS = [
    r"\b(treats|cures|heals|eliminates|reverses)\b.*\b(disease|disorder|condition)\b",
    r"\b(clinical|proven|scientifically proven|evidence-based)\b",
    r"\b(diagnose|prescribe|medication|drug)\b",
]

WELLNESS_QUALIFIERS = [
    "may support", "according to tradition", "traditionally used for",
    "in Ayurvedic practice", "some practitioners believe", "consult a qualified practitioner"
]

def check_medical_claim(text: str) -> bool:
    return any(re.search(p, text, re.I) for p in MEDICAL_CLAIM_PATTERNS)
```

When a medical claim pattern is detected, either rephrase as a traditional/wellness claim or block with: "For health concerns, please consult a qualified Ayurvedic practitioner or medical doctor."

---

## Cultural sensitivity as a technical constraint

This domain requires cultural sensitivity that goes beyond content moderation:

**1. Lineage attribution:** Different teachers interpret the same text differently. The AI must not present one interpretation as "the correct" Yoga Sutras interpretation without attributing it to a lineage.

```
Wrong: "Samadhi means X"
Right: "In the Iyengar tradition, samadhi is understood as X. 
        In the Krishnamacharya lineage, the emphasis is on Y."
```

**2. Sacred text handling:** Some texts are considered sacred. The system should not combine sacred text quotes with commercial or irreverent content.

**3. Context collapse:** Taking a practice out of its traditional context can be harmful (e.g., advanced pranayama without proper grounding). The AI must surface prerequisite context.

**4. Living tradition:** This is not a dead language. Teachers and lineages are still active. The AI must not present their teachings without attribution.

```python
ATTRIBUTION_SYSTEM = """
When referencing specific practices or interpretations:
- Name the source text with chapter/verse where applicable
- Name the lineage or teacher if interpreting beyond the text
- Use "according to [source]" not "X is Y"
- For contested interpretations, present multiple views
- For practices with safety prerequisites, state them first
"""
```

---

## Content corpus strategy

```
Public domain (pre-1928):
  ✓ Primary Sanskrit texts (Yoga Sutras, Charaka Samhita, etc.)
  ✓ 19th century translations (Max Müller Sacred Books of the East)
  ✓ Early 20th century translations (Swami Vivekananda's works)

Modern translations (copyrighted):
  ✗ Georg Feuerstein, B.K.S. Iyengar, etc. (must license or exclude)
  ✗ Contemporary teachers' commentaries

Synthetically generated:
  ✓ Explanations derived from public domain texts
  ✓ Practice guides sourced from public domain

Oral tradition:
  ✗ Cannot index; acknowledge gaps explicitly
```

---

## Try this

1. **Audience tier detection** — take 10 questions about yoga or Ayurveda. Classify each into Tier 1–4 based on vocabulary and specificity. Write the system prompt that would do this classification automatically.

2. **Medical claim audit** — take 20 statements from wellness websites about yoga and Ayurveda. Run the medical claim checker. How many false positives (safe statements flagged)? How many false negatives (actual medical claims missed)?

3. **Multilingual Sanskrit search** — index 10 passages from the Yoga Sutras in Devanagari. Query in English ("breath control"), IAST ("prāṇāyāma"), and Hindi ("प्राणायाम"). Measure retrieval quality across all three query forms.

4. **Attribution template** — pick one contested concept (e.g., "What is dharana?"). Write three responses: one without attribution, one with single-lineage attribution, one with multi-lineage comparison. Which is most accurate for this domain?

5. **Copyright boundary** — research the copyright status of five major Yoga/Ayurveda translations. Which are public domain? Which require licensing? How does this constrain the knowledge base?

---

## Mental model in one line

> **Vidya Karana domain strategy is four decisions: which texts (public domain corpus), which audience tier (detected from query vocabulary), which language (Sanskrit/Hindi/English per tier), and where the wellness-vs-medical-claim line is (enforced by pattern matching + content policy) — cultural sensitivity is not optional; it's a product requirement.**

---

## Related

- **Next:** [Session 32 — Reference Arch: Applied-Wisdom Assistant](45-applied-wisdom-arch.md)
- **RAG for Sanskrit/multilingual corpus:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **Content moderation/guardrails:** [Session 10 — Guardrails](10-guardrails.md)
- **Curriculum tracker:** Session 31 of 46 — Track K
