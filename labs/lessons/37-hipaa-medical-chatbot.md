# 37 — Case Study: HIPAA-Compliant Medical Chatbot (Session 24)

> **Build a vertical slice of a medical chatbot that could actually ship.** PII redaction, citation grounding, audit trail, and a reverse-engineering of how Hippocratic AI, Glass Health, K Health, and Abridge approach the problem. The output is running code — not a prototype.

---

## Roadmap — where this lesson sits

```
═══════ TRACK H: HEALTHCARE ═══════

  ✓ Session 22: Healthcare AI Landscape & Compliance
  ✓ Session 23: Reference Arch — Clinical Decision Support
  ▶ Session 24: CASE STUDY — HIPAA MEDICAL CHATBOT  ◄ HERE
```

---

## Files involved

| File | Role |
|---|---|
| `healthcare/medical_chatbot/chatbot.py` | Core chatbot pipeline |
| `healthcare/medical_chatbot/phi_guard.py` | PHI detection + redaction (Presidio) |
| `healthcare/medical_chatbot/citation_engine.py` | Grounded citation generation |
| `healthcare/medical_chatbot/audit.py` | HIPAA-compliant audit trail |
| `healthcare/medical_chatbot/eval.py` | Faithfulness + safety evaluation |

---

## Reverse engineering: what the market leaders do

### Hippocratic AI
- **Approach:** LLM fine-tuned on clinical guidelines + strict RAG grounding
- **Key design:** Nurses-as-validators — human clinical staff review edge cases
- **Safety mechanism:** "I'm not able to answer that" for anything outside scope
- **Business model:** Async patient communication (scheduling, post-discharge follow-up)
- **What to steal:** Explicit scope definition + graceful out-of-scope refusal

### Glass Health
- **Approach:** Differential diagnosis generator for clinicians (not patients)
- **Key design:** Structured output — always produces ranked differential with evidence
- **Safety mechanism:** Clinician-only access; outputs are "starting points not diagnoses"
- **Business model:** Clinical workflow tool (not patient-facing)
- **What to steal:** Structured output schema for clinical recommendations

### K Health
- **Approach:** Symptom checker → triage → async physician consult
- **Key design:** Decision tree for common conditions + LLM for edge cases
- **Safety mechanism:** Always escalates to physician for prescriptions
- **Business model:** Consumer telehealth
- **What to steal:** Hybrid deterministic + LLM (deterministic for common paths)

### Abridge
- **Approach:** Ambient AI scribe — records clinical encounter, generates structured note
- **Key design:** Audio → transcript → structured SOAP note
- **Safety mechanism:** Clinician reviews and edits before signing
- **Business model:** Clinical documentation tool
- **What to steal:** HITL edit + sign workflow; structured note format

---

## The vertical slice: what we build

A patient-facing symptom triage chatbot that:
1. Accepts symptom descriptions in plain English
2. Redacts PHI before any LLM call
3. Retrieves relevant clinical content (grounded answers only)
4. Cites sources and flags uncertainty
5. Escalates to human or advises ER visit for red flags
6. Logs every interaction to a HIPAA audit trail

---

## Core pipeline

```python
from enum import Enum
from pydantic import BaseModel

class TriageLevel(str, Enum):
    SELF_CARE = "self_care"        # manageable at home
    PRIMARY_CARE = "primary_care"  # see GP within days
    URGENT_CARE = "urgent_care"    # same-day care
    EMERGENCY = "emergency"        # go to ER now
    CALL_911 = "call_911"          # life-threatening

class ChatbotResponse(BaseModel):
    answer: str
    triage_level: TriageLevel
    citations: list[str]
    confidence: float
    red_flags_detected: list[str]
    disclaimer: str = (
        "This is health information, not medical advice. "
        "Always consult a qualified healthcare provider."
    )

async def process_query(
    raw_query: str,
    session_id: str,
    patient_pseudonym: str,
) -> ChatbotResponse:
    # Step 1: Detect PHI
    phi_detected = detect_phi(raw_query)

    # Step 2: Redact PHI before LLM
    clean_query = redact_phi(raw_query) if phi_detected else raw_query

    # Step 3: Red flag check (deterministic, pre-LLM)
    red_flags = check_red_flags(clean_query)
    if red_flags:
        response = emergency_response(red_flags)
        log_audit(session_id, patient_pseudonym, raw_query,
                  phi_detected, response, "emergency_path")
        return response

    # Step 4: Retrieve clinical content
    retrieved = await retrieve_clinical_content(clean_query)

    # Step 5: Generate grounded response
    response = await generate_response(clean_query, retrieved)

    # Step 6: Log audit trail
    log_audit(session_id, patient_pseudonym, raw_query,
              phi_detected, response, "normal_path")

    return response
```

---

## PHI guard implementation

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()

# Entities beyond Presidio defaults relevant to healthcare
HEALTHCARE_ENTITIES = [
    "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "DATE_TIME",
    "LOCATION", "US_SSN", "MEDICAL_LICENSE", "US_PASSPORT",
    "US_DRIVER_LICENSE", "CREDIT_CARD", "IBAN_CODE",
]

def detect_phi(text: str) -> bool:
    results = _analyzer.analyze(
        text=text,
        entities=HEALTHCARE_ENTITIES,
        language="en",
    )
    return len(results) > 0

def redact_phi(text: str) -> str:
    results = _analyzer.analyze(
        text=text,
        entities=HEALTHCARE_ENTITIES,
        language="en",
    )
    return _anonymizer.anonymize(text=text, analyzer_results=results).text
```

---

## Red flag detection (deterministic, pre-LLM)

For life-threatening symptoms, never wait for an LLM. Use fast pattern matching:

```python
RED_FLAG_PATTERNS = {
    "chest_pain": [
        r"chest pain", r"chest pressure", r"chest tightness",
        r"pain.*left arm", r"jaw pain",
    ],
    "stroke": [
        r"face drooping", r"arm weakness", r"speech difficulty",
        r"sudden.*headache", r"can't speak",
    ],
    "breathing": [
        r"can't breathe", r"difficulty breathing", r"shortness of breath.*severe",
        r"choking",
    ],
    "overdose": [
        r"took too many", r"overdose", r"swallowed.*pills",
    ],
}

def check_red_flags(text: str) -> list[str]:
    text_lower = text.lower()
    detected = []
    for category, patterns in RED_FLAG_PATTERNS.items():
        if any(re.search(p, text_lower) for p in patterns):
            detected.append(category)
    return detected

def emergency_response(red_flags: list[str]) -> ChatbotResponse:
    return ChatbotResponse(
        answer=f"Based on what you've described ({', '.join(red_flags)}), "
               "please call 911 or go to your nearest emergency room immediately. "
               "Do not drive yourself.",
        triage_level=TriageLevel.CALL_911,
        citations=[],
        confidence=1.0,
        red_flags_detected=red_flags,
    )
```

---

## Citation engine

```python
CITATION_SYSTEM = """You are a medical information assistant.

STRICT RULES:
1. Answer ONLY from the provided clinical content below.
2. Cite every claim: [SOURCE: {source_id}]
3. If the content doesn't address the question: 
   "I don't have specific guidance on this. Please consult your healthcare provider."
4. Always include triage guidance at the end.
5. End every response with the standard disclaimer.

Clinical content:
{clinical_content}
"""

async def generate_response(
    query: str,
    retrieved_docs: list[dict],
) -> ChatbotResponse:
    clinical_content = format_retrieved(retrieved_docs)
    llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)
    structured = llm.with_structured_output(ChatbotResponse)
    return await structured.ainvoke([
        SystemMessage(content=CITATION_SYSTEM.format(
            clinical_content=clinical_content
        )),
        HumanMessage(content=query),
    ])
```

---

## HIPAA audit trail

```python
import hashlib
from datetime import datetime, timezone
from pydantic import BaseModel

class HITPAuditEntry(BaseModel):
    audit_id: str
    session_id: str
    patient_pseudonym: str           # NOT real patient ID
    timestamp_utc: str
    query_hash: str                  # SHA-256; never store raw query if PHI present
    phi_detected: bool
    phi_redacted: bool
    path_taken: str                  # "emergency_path" | "normal_path"
    triage_level: str
    red_flags: list[str]
    citations_count: int
    confidence: float
    model: str = "claude-sonnet-4-6"
    retention_years: int = 6         # HIPAA minimum

def log_audit(
    session_id: str,
    patient_pseudonym: str,
    raw_query: str,
    phi_detected: bool,
    response: ChatbotResponse,
    path: str,
) -> HITPAuditEntry:
    entry = HITPAuditEntry(
        audit_id=str(uuid4()),
        session_id=session_id,
        patient_pseudonym=patient_pseudonym,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        query_hash=hashlib.sha256(raw_query.encode()).hexdigest(),
        phi_detected=phi_detected,
        phi_redacted=phi_detected,  # always redact if detected
        path_taken=path,
        triage_level=response.triage_level.value,
        red_flags=response.red_flags_detected,
        citations_count=len(response.citations),
        confidence=response.confidence,
    )
    # Write to append-only audit store (e.g., S3 + CloudTrail, or Postgres with RLS)
    persist_audit_entry(entry)
    return entry
```

---

## Evaluation suite

```python
# Safety: never miss a red flag
def test_red_flag_recall():
    red_flag_cases = load_red_flag_test_set()
    results = [check_red_flags(case["query"]) for case in red_flag_cases]
    recall = sum(1 for r, c in zip(results, red_flag_cases)
                 if c["expected_flag"] in r) / len(red_flag_cases)
    assert recall == 1.0, f"Red flag recall {recall:.2%} — must be 100%"

# Faithfulness: all clinical claims are cited
def test_faithfulness(golden_set, threshold=0.95):
    scores = [score_faithfulness(q, a) for q, a in golden_set]
    assert sum(scores) / len(scores) >= threshold

# PHI: redaction never leaks
def test_phi_not_in_llm_input():
    queries_with_phi = load_phi_test_set()
    for q in queries_with_phi:
        redacted = redact_phi(q)
        assert not detect_phi(redacted), f"PHI leaked in: {redacted}"
```

---

## Try this

1. **Build the PHI guard** — take 20 synthetic clinical queries (some with PHI, some without). Run Presidio. Measure precision (no false blocks) and recall (no PHI leaks). Target: 100% recall, >90% precision.

2. **Red flag test** — build a test set of 20 symptom descriptions — 10 that are emergencies, 10 that aren't. Run `check_red_flags()`. Any missed emergency is a P0 bug.

3. **Faithfulness vs. raw LLM** — ask 5 clinical questions (a) with RAG + citation enforcement, (b) with raw LLM. Score faithfulness on both. The gap is your safety argument.

4. **Reverse engineer one product** — sign up for K Health's free tier. Ask 10 symptom questions. Map its behaviour to the architecture components: where does it use deterministic rules? Where LLM? Where does it escalate?

5. **Audit trail completeness** — after 10 test interactions, query the audit log. Answer: which queries contained PHI? Which triggered emergency path? What was the average confidence? Can you answer a HIPAA audit from the log alone?

---

## Mental model in one line

> **A HIPAA-compliant medical chatbot is a six-layer pipeline: red flag detection (deterministic, pre-LLM) → PHI redaction → RAG retrieval → citation-enforced generation → HITL escalation path → immutable audit trail — every layer is independently testable and non-negotiable.**

---

## Related

- **Previous:** [Session 23 — Reference Arch: Clinical Decision Support](36-clinical-decision-support.md)
- **Next:** [Session 25 — AgriTech AI Landscape](38-agritech-landscape.md)
- **PHI redaction tool:** [Presidio](https://microsoft.github.io/presidio/)
- **Citations API:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **Faithfulness scoring:** [Session 14 — Evaluation](25-evaluation.md)
- **Curriculum tracker:** Session 24 of 46 — Track H capstone
