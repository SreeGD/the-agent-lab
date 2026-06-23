# 36 — Reference Arch: Clinical Decision Support (Session 23)

> **Whiteboard a real CDS system.** Clinical Decision Support is the highest-value, highest-risk healthcare AI pattern — it puts AI recommendations in front of clinicians at the point of care. This session designs the architecture that makes that safe: RAG over clinical guidelines, audit-grade logging, doctor-in-the-loop HITL, and faithfulness as the non-negotiable safety floor.

---

## Roadmap — where this lesson sits

```
═══════ TRACK H: HEALTHCARE ═══════

  ✓ Session 22: Healthcare AI Landscape & Compliance
  ▶ Session 23: REFERENCE ARCH — CDS  ◄ HERE
    Session 24: Case Study — HIPAA-Compliant Medical Chatbot
```

---

## Files involved

| File | Role |
|---|---|
| `healthcare/cds_architecture.md` | Architecture document + design decisions |

---

## What is Clinical Decision Support?

CDS is any system that filters clinical knowledge and patient data to provide targeted recommendations at the point of care. Examples:

- Drug-drug interaction alerts (your patient is on warfarin + ibuprofen → alert)
- Dosing guidance based on renal function
- Differential diagnosis suggestions from symptoms + labs
- Protocol reminders ("sepsis bundle due in 2 hours")
- Risk stratification ("this patient's CHADS2 score suggests anticoagulation")

The common pattern: **patient context + clinical knowledge → actionable recommendation + justification**.

---

## Architecture overview

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                   CDS SYSTEM                                    │
  │                                                                 │
  │  Patient Context          Knowledge Base                        │
  │  ┌──────────────┐         ┌──────────────────────────────────┐  │
  │  │ EHR / FHIR   │         │ Clinical guidelines (UpToDate,   │  │
  │  │ • Labs       │         │  NICE, WHO, specialty society)   │  │
  │  │ • Meds       │         │ Drug databases (RxNorm, NDF-RT)  │  │
  │  │ • Diagnoses  │         │ Formulary data                   │  │
  │  │ • Vitals     │         │ Institution protocols            │  │
  │  └──────┬───────┘         └──────────────┬───────────────────┘  │
  │         │                                │                      │
  │         └──────────┬─────────────────────┘                      │
  │                    ▼                                             │
  │         ┌──────────────────────┐                                │
  │         │  PHI Redaction Layer │ ← Presidio before LLM          │
  │         └──────────┬───────────┘                                │
  │                    ▼                                             │
  │         ┌──────────────────────┐                                │
  │         │  Context Assembler   │ ← Session 1c patterns          │
  │         │  (patient + RAG)     │                                │
  │         └──────────┬───────────┘                                │
  │                    ▼                                             │
  │         ┌──────────────────────┐                                │
  │         │  Claude (LLM)        │ ← Faithfulness-enforced        │
  │         │  + Citations API     │                                │
  │         └──────────┬───────────┘                                │
  │                    ▼                                             │
  │         ┌──────────────────────┐                                │
  │         │  HITL Review Layer   │ ← Clinician approves/overrides │
  │         └──────────┬───────────┘                                │
  │                    ▼                                             │
  │         ┌──────────────────────┐                                │
  │         │  Audit Log           │ ← Immutable, HIPAA-compliant  │
  │         └──────────────────────┘                                │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Key design decisions

### 1. FHIR as the patient context interface

FHIR (Fast Healthcare Interoperability Resources) is the standard for EHR data exchange. Structure patient context as FHIR resources:

```python
from pydantic import BaseModel
from datetime import date

class FHIRMedication(BaseModel):
    medication_name: str
    rxnorm_code: str
    dose: str
    frequency: str
    start_date: date

class FHIRLab(BaseModel):
    test_name: str
    loinc_code: str
    value: float
    unit: str
    reference_range: str
    collected_at: str

class PatientContext(BaseModel):
    patient_id: str          # pseudonymised
    age: int
    sex: str
    active_medications: list[FHIRMedication]
    recent_labs: list[FHIRLab]
    active_diagnoses: list[str]  # ICD-10 codes
    allergies: list[str]
```

### 2. RAG over clinical guidelines — chunking strategy

Clinical guidelines are structured documents. Chunk at the section level, not fixed tokens:

```python
def chunk_clinical_guideline(text: str, guideline_id: str) -> list[dict]:
    """
    Splits at section headings (## Recommendation, ## Evidence, etc.)
    Preserves the section title in every chunk for context.
    """
    chunks = []
    current_section = "Introduction"
    current_text = []

    for line in text.splitlines():
        if line.startswith("##"):
            if current_text:
                chunks.append({
                    "guideline_id": guideline_id,
                    "section": current_section,
                    "text": "\n".join(current_text),
                })
            current_section = line.lstrip("#").strip()
            current_text = []
        else:
            current_text.append(line)

    return chunks
```

**Why section-level?** Clinical guidelines have a recommendation section followed by an evidence section. A chunk-size-based split often splits a recommendation from its evidence grade (A/B/C/D). Section-level chunking keeps them together.

### 3. Faithfulness enforcement

Never let the LLM answer from parametric knowledge for clinical questions. Enforce retrieval:

```python
CDS_SYSTEM_PROMPT = """You are a clinical decision support assistant.

CRITICAL RULES:
1. Answer ONLY from the retrieved guidelines provided below. 
   Never use your training knowledge for clinical recommendations.
2. If the retrieved guidelines do not address the question, say:
   "The available guidelines do not cover this specific scenario. 
    Please consult a specialist."
3. Every recommendation must cite the specific guideline section 
   it comes from using [SOURCE: guideline_id, section].
4. Include the evidence grade (A/B/C/D or Level 1-4) where present.
5. Always end with: "This is decision support only. 
    Final clinical decisions rest with the treating clinician."

Retrieved guidelines:
{retrieved_guidelines}
"""
```

### 4. Doctor-in-the-loop HITL

Structure every CDS output for HITL review:

```python
class CDSRecommendation(BaseModel):
    recommendation: str
    evidence_grade: str          # A, B, C, D, or "Consensus"
    sources: list[str]           # guideline sections cited
    confidence: float            # 0.0–1.0
    caveats: list[str]           # "assumes normal renal function", etc.
    requires_clinician_review: bool = True

class CDSHITLRecord(BaseModel):
    recommendation: CDSRecommendation
    clinician_id: str            # de-identified
    decision: str                # "accepted" | "modified" | "rejected"
    clinician_note: str | None
    decided_at: str              # UTC ISO timestamp
    time_to_decision_seconds: int
```

Track `time_to_decision_seconds` — very fast decisions (< 3s) suggest alert fatigue; very slow decisions (> 120s) suggest the recommendation wasn't clear.

### 5. Audit-grade logging

```python
class ClinicalAuditEntry(BaseModel):
    # Identity
    audit_id: str                # uuid
    session_id: str
    patient_pseudonym: str       # NOT the real patient ID
    clinician_pseudonym: str

    # Request
    timestamp_utc: str
    query_hash: str              # SHA-256 of query; not raw text
    query_category: str          # "drug interaction" | "dosing" | "differential" | ...

    # Retrieval
    guidelines_retrieved: list[str]   # guideline IDs
    retrieval_scores: list[float]

    # LLM
    model: str
    model_version: str
    tokens_input: int
    tokens_output: int

    # Output
    recommendation_hash: str     # SHA-256 of recommendation text
    citations_count: int
    confidence: float

    # HITL
    clinician_decision: str
    override_reason: str | None

    # Compliance
    phi_detected_in_query: bool
    phi_redacted: bool
```

---

## Faithfulness as safety floor

The key metric for any clinical RAG system is **faithfulness** — does every claim in the response trace back to a retrieved source?

```
Faithfulness = (claims with source) / (total claims)

Target: > 0.95 for clinical recommendations
Alert: < 0.90 triggers human review of the session
Block: any response where faithfulness cannot be computed
       (e.g., no sources retrieved) → "guidelines not available"
```

Use Ragas (Session 14) to measure faithfulness automatically on a golden evaluation set. Run it on every model version before deployment.

---

## Alert fatigue — the CDS killer

CDS systems fail not because they're inaccurate but because clinicians learn to ignore them. Alert fatigue is the #1 clinical AI adoption failure mode.

Design principles to fight it:
- **Actionable only** — every alert must have a clear action (not "patient may be at risk")
- **Specific** — "warfarin + ibuprofen → bleeding risk" beats "drug interaction detected"
- **Right timing** — surface at prescribing, not after the fact
- **Right person** — route to the prescribing clinician, not all nurses
- **Override tracking** — high override rate → alert is not useful → remove or refine
- **Quiet by default** — require high confidence threshold (>0.85) before surfacing

---

## Try this

1. **Whiteboard the architecture** — draw the CDS system from scratch on paper. Identify every data flow that touches PHI. Mark which ones need encryption.

2. **Chunk clinical guidelines** — download a public clinical guideline (e.g., ACC/AHA hypertension guidelines). Run the section-level chunker. Embed the chunks. Ask three clinical questions and evaluate retrieval quality.

3. **Faithfulness measurement** — build a 10-question golden set for a clinical domain. Run RAG answers through Ragas faithfulness scorer. Find the threshold below which you'd block the response.

4. **HITL simulation** — build the HITL review interface (even a simple CLI). Log override rate over 20 synthetic scenarios. Which recommendation types get overridden most?

5. **Alert fatigue audit** — take a list of 20 CDS alerts from the literature. Classify each: actionable vs. informational, specific vs. vague, right timing vs. after-the-fact. Count how many would survive an alert fatigue audit.

---

## Mental model in one line

> **Clinical Decision Support architecture is RAG over guidelines (section-level chunks) + PHI redaction + faithfulness enforcement (cite sources or say nothing) + HITL (clinician approves every recommendation) + immutable audit log — all four layers are non-negotiable.**

---

## Related

- **Previous:** [Session 22 — Healthcare AI Landscape](35-healthcare-landscape.md)
- **Next:** [Session 24 — Case Study: HIPAA-Compliant Medical Chatbot](37-hipaa-medical-chatbot.md)
- **RAG foundation:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **Faithfulness scoring:** [Session 14 — Evaluation](25-evaluation.md)
- **HITL patterns:** [Session 10 — Custom LangGraph + HITL](21-custom-langgraph.md)
- **Governance + audit:** [Session 20 — AI Governance & Audit](32-governance.md)
- **Curriculum tracker:** Session 23 of 46 — Track H
