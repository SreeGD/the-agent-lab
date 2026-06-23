# 35 — Healthcare AI Landscape & Compliance (Session 22)

> **Healthcare AI is the highest-stakes vertical.** A wrong answer costs a life. A non-compliant system costs a licence. This session maps the stakeholders, the regulatory framework (HIPAA, GDPR, FDA SaMD), and the technical constraints that every clinical AI system must satisfy before a single user query is processed.

---

## Roadmap — where this lesson sits

```
═══════ TRACK H: HEALTHCARE ═══════

  ▶ Session 22: HEALTHCARE AI LANDSCAPE  ◄ HERE
    Session 23: Reference Arch — Clinical Decision Support
    Session 24: Case Study — HIPAA-Compliant Medical Chatbot

  Prerequisites: Sessions 18–21 (System Design, Red-teaming,
                 Governance, UX Patterns)
```

---

## Files involved

| File | Role |
|---|---|
| `healthcare/landscape.md` | Stakeholder map + use case taxonomy |
| `healthcare/regulatory_map.md` | Regulation → technical requirement mapping |

---

## The stakeholder map

Healthcare AI touches more stakeholder types than any other vertical:

```
  ┌─────────────────────────────────────────────────────────┐
  │                   HEALTHCARE AI SYSTEM                   │
  ├──────────────┬──────────────┬──────────────┬────────────┤
  │   Patients   │  Clinicians  │  Payers      │ Regulators │
  │              │              │              │            │
  │  • Autonomy  │  • Liability │  • Coverage  │  • HIPAA   │
  │  • Privacy   │  • Workflow  │  • Fraud     │  • FDA     │
  │  • Consent   │  • Evidence  │  • Codes     │  • GDPR    │
  │  • Trust     │  • Time      │  • Audits    │  • CE Mark │
  └──────────────┴──────────────┴──────────────┴────────────┘
         ↑               ↑
  High vulnerability   Legal exposure
  population           per output
```

**Key insight:** Every stakeholder has veto power. A system patients love but clinicians distrust will fail. A system clinicians use but regulators flag will be shut down.

---

## Regulatory framework

### HIPAA (US)

HIPAA governs Protected Health Information (PHI) — any data that can identify a patient combined with health information.

| Rule | What it requires for AI systems |
|---|---|
| Privacy Rule | Limit PHI use to treatment, payment, operations. AI training on PHI requires patient consent or de-identification. |
| Security Rule | Encrypt PHI at rest and in transit. Access controls for every system touching PHI. |
| Breach Notification | Report breaches within 60 days. AI systems that leak PHI trigger this. |
| Minimum Necessary | Only use the minimum PHI needed. Don't feed full patient records to LLMs when a summary suffices. |

**De-identification** (Safe Harbor method — 18 identifiers to remove):
Names, geographic data below state level, dates (except year), ages >89, phone numbers, fax numbers, email addresses, SSNs, medical record numbers, health plan numbers, account numbers, certificate/licence numbers, vehicle identifiers, device identifiers, URLs, IP addresses, biometric identifiers, full-face photos, unique identifying numbers.

### FDA Software as a Medical Device (SaMD)

If your AI system influences clinical decisions, it may be regulated as a medical device:

```
  Intended use → Clinical significance → Regulatory class
  
  Information only (no clinical action)   → Generally exempt
  Drive clinical decision (low risk)      → Class II (510k)
  Drive clinical decision (high risk)     → Class III (PMA)
  
  Examples:
  • "This patient may have pneumonia" → Class II or III
  • "Here is medical literature" → Generally exempt
  • "Your symptoms suggest X" (consumer) → Grey zone
```

**AI/ML-specific FDA guidance (2021+):** Pre-determined change control plans, performance monitoring, algorithmic transparency, bias testing across demographic subgroups.

### GDPR (EU) — Health Data

Health data is a "special category" under GDPR Article 9. Processing requires:
- Explicit consent, OR
- Vital interests, OR
- Healthcare provision by a professional bound by confidentiality

**Right to explanation:** Patients affected by automated decisions have the right to a meaningful explanation. This constrains black-box models for clinical decisions.

### India — DPDP Act + NHP

The Digital Personal Data Protection Act (2023) treats health data as sensitive. The National Health Policy emphasises AI for rural reach, vernacular access, and ASHA worker augmentation — a different set of constraints than the US/EU focus.

---

## Use case taxonomy

| Category | Examples | Risk level | Regulatory burden |
|---|---|---|---|
| **Administrative** | Scheduling, billing codes, prior auth | Low | Moderate |
| **Clinical documentation** | Ambient scribe, discharge summary | Medium | Moderate–High |
| **Diagnostic support** | Radiology AI, pathology | High | FDA Class II/III |
| **Treatment recommendation** | Drug dosing, protocol selection | Very high | FDA Class II/III |
| **Patient engagement** | Symptom checker, medication reminders | Medium | Grey zone |
| **Population health** | Risk stratification, care gap | Medium | Low–Moderate |
| **Research** | Clinical trial matching, literature synthesis | Low (if no direct patient impact) | IRB |

---

## Technical constraints every healthcare AI must satisfy

### 1. Faithfulness as a safety floor

Hallucinated clinical information can kill. Faithfulness — answers grounded in retrieved sources — is not a nice-to-have; it is the minimum safety bar.

```
Every clinical AI output must be:
  Grounded    → sourced from retrieved clinical evidence
  Cited       → reference visible to the clinician
  Uncertain   → explicit confidence + "consult a clinician" where uncertain
  Auditable   → the exact sources used are logged
```

### 2. PII/PHI redaction before LLM

Never send raw PHI to a third-party LLM. Redact first:

```python
# Using Microsoft Presidio (open source)
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def redact_phi(text: str) -> str:
    results = analyzer.analyze(text=text, language="en")
    return anonymizer.anonymize(text=text, analyzer_results=results).text

# "John Smith, DOB 1985-03-12, SSN 123-45-6789 has diabetes"
# → "<PERSON>, DOB <DATE_TIME>, SSN <US_SSN> has diabetes"
```

### 3. Doctor-in-the-loop HITL

For clinical decisions, never fully automate. Design for Human-in-the-loop:
- AI produces recommendation + confidence + sources
- Clinician reviews and approves or overrides
- System logs the human decision (not just the AI output)
- Override rate is a key metric — high override = low model trust

### 4. Audit trail (non-negotiable)

Every clinical AI interaction must produce an immutable audit record:
- Patient identifier (de-identified or pseudonymised)
- Timestamp (UTC)
- Query text (or hash if PHI)
- Sources retrieved
- AI output
- Clinician action (accepted / modified / overridden)
- Model version

---

## Regulatory grey zones

| Scenario | Ambiguity | Practical guidance |
|---|---|---|
| Consumer symptom checker | SaMD or not? | Add "not a substitute for medical advice" + escalation path |
| LLM for discharge summaries | Clinical documentation tool or AI writer? | Treat as SaMD; log all outputs |
| RAG over clinical guidelines | Providing information or recommendations? | Keep outputs factual, cited, non-prescriptive |
| LLM for clinical note review | Quality tool or diagnostic aid? | Depends on how the output is used |

**Rule of thumb:** If a clinician would act on the output without independent verification, it's likely SaMD. When in doubt, add HITL and audit logging — it's cheaper than a recall.

---

## US vs. India focus

| Dimension | US focus | India focus |
|---|---|---|
| Primary regulation | HIPAA, FDA SaMD | DPDP Act, NHP guidelines |
| Infrastructure | EHR integration (Epic, Cerner) | ABDM (Ayushman Bharat Digital Mission) |
| Language | English | 22 scheduled languages + dialects |
| Access | Desktop/web | Mobile-first, WhatsApp, voice |
| Connectivity | Assumed high | Offline-tolerant required |
| Key users | Specialists, PCPs | ASHA workers, rural patients |
| Cost constraint | Insurance-funded | ₹-paise unit economics |

---

## Try this

1. **Stakeholder map** — pick one healthcare AI use case (e.g., medication adherence reminder). Draw the stakeholder map. Identify whose interests conflict and where.

2. **PHI identification** — take a sample clinical note (from a public dataset like MIMIC-III). Run Presidio's analyzer on it. Count how many PHI entities it finds. Note which ones it misses.

3. **Regulatory classification** — for five AI healthcare products (e.g., Hippocratic AI, Glass Health, K Health, Abridge, Nabla), determine whether each is likely SaMD Class II, Class III, or exempt. Justify each.

4. **Faithfulness test** — take a clinical question, answer it with a raw LLM (no RAG), then answer it with RAG over clinical guidelines. Compare the faithfulness and citation quality.

5. **HIPAA audit trail design** — design the schema for a HIPAA-compliant audit log for a clinical AI chatbot. What fields are mandatory? What must be encrypted? What retention period applies?

---

## Mental model in one line

> **Healthcare AI compliance is a three-layer constraint: HIPAA requires PHI protection and audit trails, FDA SaMD classification determines pre-market requirements, and clinical safety demands faithfulness + HITL — all three must be satisfied before any clinical AI ships.**

---

## Related

- **Next:** [Session 23 — Reference Arch: Clinical Decision Support](36-clinical-decision-support.md)
- **Governance foundation:** [Session 20 — AI Governance & Audit](32-governance.md)
- **Red-teaming for healthcare:** [Session 19 — Red-teaming & Compliance](31-red-teaming.md)
- **RAG for clinical guidelines:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **Curriculum tracker:** Session 22 of 46 — Track H
