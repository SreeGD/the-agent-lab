# 38 — AgriTech AI Landscape (Session 25)

> **Agriculture is the largest employer on Earth, yet one of the least digitised.** AI in AgriTech must work on 2G, in 12 languages, for farmers who may be illiterate, on a ₹50-per-acre margin. This session maps the landscape, constraints, and use cases — with India as the primary focus.

---

## Roadmap — where this lesson sits

```
═══════ TRACK I: AGRICULTURE ═══════

  ▶ Session 25: AGRITECH AI LANDSCAPE  ◄ HERE
    Session 26: Reference Arch — Crop Diagnostic + Advisory
    Session 27: Case Study — Vernacular Farmer Bot

  Prerequisites: Sessions 18–21
```

---

## Files involved

| File | Role |
|---|---|
| `agritech/landscape.md` | Use case taxonomy + constraint map |

---

## The scale of the problem

- **India:** 146M farm households; average holding 1.08 hectares; 58% of rural workforce
- **Crop loss:** 15-25% post-harvest; 30-40% from pest/disease in-field
- **Information gap:** Extension officer to farmer ratio: 1:1,000 (target: 1:800; reality: 1:1,500+)
- **Language:** 22 scheduled languages; 1,600+ dialects; most farmers read their regional language, not Hindi or English
- **Connectivity:** 500M rural Indians with smartphones; but 2G is the baseline; offline periods common

An AI system that requires 4G, English, and a smartphone with a modern browser serves the top 5% of farmers. The other 95% need something different.

---

## Smallholder vs. commercial agriculture

| Dimension | Smallholder (India focus) | Commercial (US/EU) |
|---|---|---|
| Farm size | < 2 hectares | > 100 hectares |
| Connectivity | 2G baseline, offline expected | High-speed broadband |
| Device | Basic Android, WhatsApp | Desktop, precision ag hardware |
| Language | Vernacular (Telugu, Tamil, ...) | English |
| Literacy | Variable; voice preferred | High |
| Budget | ₹-paise sensitive | Dollar-denominated ROI |
| Data | Sparse, unstructured | Dense, structured (sensors) |
| Crops | Diverse, rain-fed | Monoculture, irrigated |
| Advisory | Extension officers, KVKs | Agronomists, precision ag vendors |

AI systems designed for commercial agriculture (John Deere, Trimble, Granular) fail for smallholders on every dimension except crop science.

---

## Use case taxonomy

| Category | Examples | Key AI components |
|---|---|---|
| **Crop diagnostics** | Disease/pest ID from photo | Vision (leaf image), RAG over crop knowledge base |
| **Advisory** | Fertiliser dose, irrigation timing | Structured output, agronomic knowledge base |
| **Market information** | Mandi prices, buyer connections | RAG over price feeds, NLP for voice queries |
| **Weather** | Hyper-local forecast, alert | API integration, proactive notification |
| **Financial** | Loan eligibility, insurance claim | Document AI, structured extraction |
| **Supply chain** | Input procurement, logistics | Agent with tool calls to vendor APIs |
| **Compliance** | Subsidy applications, PM-KISAN | Form filling, document generation |

---

## Multi-modal as a requirement (not an option)

For smallholder farmers, multi-modal input is not a feature — it is the baseline:

```
Input modalities required:
  📷 Photo     — leaf with disease, pest, soil
  🎙 Voice     — query in local language (Whisper ASR)
  📝 Text      — WhatsApp message in regional script
  📍 Location  — GPS for hyper-local soil/weather data

Output modalities required:
  🎙 Voice     — TTS response in local language
  📷 Annotated — photo with disease marked
  📝 Text      — WhatsApp-friendly (< 200 chars, no markdown)
  📊 Simple    — single recommendation, not a paragraph
```

A purely text-based chatbot serves farmers who can type. That is not most of them.

---

## The offline-tolerant design constraint

Unlike healthcare or finance, AgriTech AI often runs in low/no connectivity:

```
Design for offline-tolerant:
  ✓ Cache the knowledge base locally on the device
  ✓ Queue queries when offline; sync when connected
  ✓ Prefer on-device models (Ollama) for basic diagnostics
  ✓ Degrade gracefully: offline → cached advice → "sync later for personalised answer"
  ✓ SMS fallback: if internet fails, send structured SMS with mandi price
```

Progressive enhancement: the system works on SMS, better on WhatsApp, best on a smartphone with camera.

---

## Vernacular RAG

The knowledge base must work in the farmer's language:

```
English knowledge base → multilingual embeddings → query in Telugu

Options:
  1. Translate KB to all target languages (expensive, maintenance burden)
  2. Multilingual embedding model (e.g., LaBSE, mE5) — 
     embeds English KB and Telugu query in same vector space
  3. Translate query to English → retrieve → translate response back
     (adds latency; works for async WhatsApp)

For real-time voice: Option 3 (ASR → translate → retrieve → generate → TTS)
For WhatsApp async: Option 3 or 2
For on-device: Option 2 with a small multilingual model
```

---

## Unit economics: ₹-paise sensitivity

```
Farmer's willingness to pay: ₹0–500/month (₹0–6/day)
Cost of one LLM query (Claude Sonnet): ~₹0.05–0.10

At scale (1M farmers, 3 queries/day):
  LLM cost: 3M queries × ₹0.08 = ₹240,000/day = ₹87M/year
  Revenue needed: ₹87/farmer/year minimum just for LLM costs

Strategies:
  • Route simple queries to a smaller/cheaper model (Haiku)
  • Cache common queries (80% of crop disease queries repeat)
  • On-device model for basic diagnostics (zero API cost)
  • Batch non-urgent queries (Batches API, Session 15)
  • Freemium: basic advice free, premium personalised advice paid
```

---

## Key players to study

| Company | Country | Approach | What to learn |
|---|---|---|---|
| Plantix (Bayer) | Germany/India | Vision-based disease ID | Multi-modal input UX |
| DeHaat | India | Full-stack agri-advisory | End-to-end farmer journey |
| Fasal | India | Sensor + AI crop advisory | IoT + AI integration |
| CropIn | India | Data platform for agri | Enterprise vs. farmer product |
| Wadhwani AI | India | Pest management (cotton) | On-device ML for offline |
| Gramophone | India | Input marketplace + advisory | Commerce + advisory flywheel |

---

## Try this

1. **Constraint mapping** — pick one use case (e.g., disease diagnosis). List the constraints: connectivity, language, device, literacy, cost. For each constraint, describe what it eliminates from your tech stack.

2. **Multilingual embedding test** — take 10 crop disease descriptions in English. Translate 5 to Telugu (Google Translate). Use LaBSE embeddings to find the Telugu query's nearest English neighbours. Measure retrieval accuracy.

3. **Voice query pipeline** — record a 10-second voice query in Hindi or Telugu (or use a text-to-speech tool). Run it through Whisper. Translate to English. Retrieve from an English knowledge base. Evaluate end-to-end quality.

4. **Unit economics spreadsheet** — build a spreadsheet: farmers served × queries/day × cost/query. At what scale does Claude Sonnet become unaffordable? What model switch or caching rate makes it viable?

5. **Reverse-engineer Plantix** — install Plantix. Submit 5 disease photos. Map its response to the architecture components. Is it vision + RAG? Vision + lookup table? How does it handle uncertain diagnosis?

---

## Mental model in one line

> **AgriTech AI for smallholder farmers is a multi-modal, offline-tolerant, vernacular-first system — voice in, photo in, WhatsApp out — with ₹-paise unit economics enforced through model routing, caching, and on-device inference.**

---

## Related

- **Next:** [Session 26 — Reference Arch: Crop Diagnostic + Advisory](39-crop-diagnostic.md)
- **Multi-modal foundation:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **AgriTech capstone:** [Session 34 — Farm Planner](34-farm-planner.md)
- **Cost engineering:** [Session 15 — Cost Optimization](26-cost-optimization.md)
- **Curriculum tracker:** Session 25 of 46 — Track I
