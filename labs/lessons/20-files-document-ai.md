# 20 — Files & Document AI (Session 9)

> **Claude reads PDFs and images natively — no PyPDF, no OCR, no chunking.** Pass a base64-encoded PDF or PNG in a `content` block and Claude parses it like a human would (text, layout, tables, charts, embedded images). Plus the **Citations API** turns the faithfulness story from "I hope the LLM judge caught it" into "the server enforced it."

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Track A: ✓ all 3 done
                                                           Track B: ✓ all 3 done
                                                           Track C: ✓ all 2 done
                                                           Track D: Data & Multi-modal
                                                             ▶ Session 9: FILES & DOC AI  ◄ HERE  (Track D COMPLETE)
                                                           Track E: ○ Custom Graphs
                                                           Track E.5: ○ RAG Architectures
                                                           Track F: ○ Production
```

**Why this lesson now:** Sessions 1-8 covered text-only LLM use. Real-world inputs are PDFs, scanned forms, charts, and screenshots. Track D shows you how to handle them **without losing information** to text-extraction.

---

## Files involved

| File | Role |
|---|---|
| [`20_pdf_vision.py`](../20_pdf_vision.py) | Native PDF + image input. Three demos: PDF Q&A, chart interpretation, mixed cross-modal reasoning. |
| [`20_citations_demo.py`](../20_citations_demo.py) | Citations API — server-enforced character-range attribution. Replaces probabilistic faithfulness judges with structural guarantees. |

Test artifacts (`test_doc.pdf`, `test_chart.png`) generated at runtime and gitignored.

---

## What problem it solves

Old workflow for "ask questions about a PDF":
1. Install `PyPDF2` (or `pdfplumber`, or `unstructured`...)
2. Extract text from PDF — **lose layout, tables, charts, footnotes, math**
3. Chunk extracted text
4. Embed chunks
5. Retrieve relevant chunks
6. Stuff retrieved text into prompt
7. Hope you didn't lose the answer in the extraction step

New workflow:
1. Read PDF as bytes
2. Base64 encode
3. Put in a `content` block as `{"type": "document", "source": {...}}`
4. Claude reads it natively

**Steps 1-7 collapse to 4 lines of code, and you keep the information** that text extraction loses (tables, layout, charts, scanned regions).

For accuracy on tables, charts, layout, handwriting — **native multimodal is the right tool**. Text-extraction-based RAG fundamentally can't match it.

---

## The analogy

**A library researcher who reads the actual book vs. one who only reads transcripts.**

Old workflow = the transcript reader. Someone OCR'd the book and gave them the text. They see what was in the body paragraphs but miss the photo of the diagram, the table that doesn't render, the marginalia.

New workflow = the book reader. Sees what's actually on the page. Tables stay tables. Diagrams stay diagrams. The footnote at the bottom of page 12 is still attached to the right paragraph.

For most documents you can get away with the transcript reader. For research-grade work, the book reader wins.

---

## Visual

```
       OLD WORKFLOW                                NEW WORKFLOW
       ────────────                                ────────────

   PDF on disk                                    PDF on disk
       │                                              │
       ▼                                              │
   PyPDF.extract_text()                              │  (just read bytes)
       │ (loses layout, tables,                       │
       │  charts, math, images,                       │
       │  scanned regions)                            │
       ▼                                              ▼
   plain text                              {
       │                                     "type": "document",
       ▼                                     "source": {
   splitter.split()                            "type": "base64",
       │                                       "media_type": "application/pdf",
       ▼                                       "data": b64encode(pdf_bytes),
   chunks                                    },
       │                                   }
       ▼                                              │
   embed + store                                     │
       │                                              │
       ▼                                              ▼
   retriever                                client.messages.create(
       │                                     messages=[{"content": [doc, text]}]
       ▼                                   )
   top-k chunks                                       │
       │                                              ▼
       ▼                                       Claude reads the
   LLM (sees text only)                       PDF natively
                                              (tables, layout,
                                               charts, all preserved)
```

---

## Concept — native PDF input

```python
import anthropic, base64

client = anthropic.Anthropic()
pdf_b64 = base64.standard_b64encode(open("doc.pdf", "rb").read()).decode()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=400,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_b64,
                },
            },
            {"type": "text", "text": "What does this document say about X?"},
        ],
    }],
)
```

Image input is the same shape with `"type": "image"` and `"media_type": "image/png"` (or `image/jpeg`, etc.).

You can mix PDF + image + text in one call — the response handles cross-modal reasoning automatically.

---

## Concept — Citations API

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                "title": "Prompt Caching Primer",
                "citations": {"enabled": True},    # ← the magic toggle
            },
            {"type": "text", "text": "Does the document say caching is 90% cheaper?"},
        ],
    }],
)

# response.content contains text blocks AND citation blocks
for block in response.content:
    if block.type == "text":
        print(block.text)
        for cite in (block.citations or []):
            print(f"  cited: {cite.cited_text!r}")
            print(f"  range: chars {cite.start_char_index}-{cite.end_char_index}")
```

The model **literally cannot fabricate** a citation. The `cited_text` is copied verbatim from the source document — server-enforced.

---

## Run them

```bash
python 20_pdf_vision.py        # PDF + image + mixed
python 20_citations_demo.py    # verified character-range citations
```

The first creates the test artifacts. The second reuses them.

---

## Real output from a clean run

### Mixed PDF + image reasoning (cross-modal!)

```
Q: The PDF claims prompt caching makes input ~90% cheaper. The chart
   shows costs per model for an uncached call. If a caching customer
   was using Sonnet 4.6 for this kind of call, roughly what would they
   pay per cached request? Show your reasoning briefly.

A: ## Reasoning

   Uncached cost for Sonnet 4.6: $0.0023 per call (from chart)
   PDF claim: Prompt caching makes input ~90% cheaper
   Calculation: $0.0023 × (1 - 0.90) = $0.0023 × 0.10 = ~$0.00023 per cached request

   ## Caveat
   This is approximate — in practice, only the cached portion of the
   prompt gets the discount (the new/uncached tokens are still billed at
   full rate). So the real saving depends on what fraction of the prompt
   is a stable prefix.
```

Claude read the chart (visual), pulled the cost from it, read the PDF (text), pulled the caching claim, did the arithmetic, AND volunteered an honest caveat about partial caching. **No text extraction library could give you this.**

### Citations API — server-enforced attribution

```
Q: What is the most common production gotcha and how is it fixed?

A: ## Most Common Production Gotcha: Prefix Instability

   The most common production gotcha is **prefix instability**. The
   cache key is the byte-exact prefix up to your cache_control marker.
   Injecting a timestamp or per-request user ID anywhere before the
   marker will collapse your hit rate to near zero.
   [cited_text: "The most common production gotcha is prefix instability.
    The cache key is the byte exact prefix up to..."]

   The fix is structural: assemble prompts in stable-to-dynamic order...
   [cited_text: "The fix is structural: assemble prompts in stable to
    dynamic order (system first, then static content..."]
```

Each claim ties back to a **specific character range** in the source. The model can't hallucinate a citation — the cited_text has to exist verbatim in the document.

---

## Production-pattern decision matrix

| Use case | Pick |
|---|---|
| Single PDF, ad-hoc question | Native multimodal (this lesson) |
| 10,000 PDFs, semantic search | Traditional RAG with PyPDF/unstructured |
| Compliance-grade Q&A on contracts | **Citations API** (this lesson) |
| Customer-facing chatbot citing your docs | **Citations API** + safe_rag-style guardrails |
| Quick chart interpretation | Native vision (this lesson) |
| Cross-modal reasoning (PDF + chart together) | Native multimodal (this lesson) |
| OCR over thousands of scanned forms | Files API + Batches API (see below) |

---

## The Files API — upload once, reference many times

If you'll ask many questions of the same PDF, uploading it once is more efficient than base64-ing it into every request:

```python
# Upload once
with open("contract.pdf", "rb") as f:
    file = client.beta.files.upload(file=f)

# Reference by file_id thereafter
for question in many_questions:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "file", "file_id": file.id}},
                {"type": "text", "text": question},
            ],
        }],
    )
```

Saves bandwidth. Important for large PDFs in repeat-query workflows.

---

## The Batches API — 50% off for async work

For non-interactive workloads (overnight extractions, eval runs, bulk classification), use the Batches API:

```python
batch = client.messages.batches.create(
    requests=[
        {
            "custom_id": f"doc-{i}",
            "params": {
                "model": "claude-sonnet-4-6",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompts[i]}],
            },
        }
        for i in range(1000)
    ],
)

# Returns within 24 hours (often minutes). 50% pricing on all calls.
# Poll: client.messages.batches.retrieve(batch.id)
```

Half the cost. Trade-off: no real-time response. Perfect for nightly cron jobs, weekly eval suites, bulk migration projects.

---

## Multimodal RAG — when to reach for CLIP/ColPali

For native multimodal (this lesson), you're passing PDFs/images directly to Claude every time. That doesn't scale to thousands of documents.

For corpus-scale multimodal search, use **unified-embedding RAG**:

- **CLIP** (OpenAI) — embeds images AND text into the same vector space; you can search "show me charts that look like this" by image, or "find diagrams of the architecture" by text
- **ColPali** (newer, 2024) — represents PDF pages as patch grids embedded by a vision-language model; outperforms text-extraction RAG on layout-heavy docs

The pattern is the same as `09_rag.py`, but the embedder produces image-and-text-aware vectors. **This is its own session** (worth a future lesson 20b) — heavy install (vision-LM model weights), heavier ops. Use when:
- Your corpus has 100s+ visual documents
- Text extraction misses essential info (charts, signatures, layout, handwriting)
- You need to search by visual similarity, not just text similarity

---

## Production patterns this unlocks

| Pattern | Real use case |
|---|---|
| **Contract Q&A** | Upload contract PDF → ask questions with Citations API → audit trail of every cited clause |
| **Form processing** | Pass a scanned form image → extract structured data via `with_structured_output` |
| **Chart interpretation** | Dashboard screenshots → "what does this chart suggest?" |
| **Compliance review** | Multi-document policy + claim → verified citations across both |
| **Research assistant** | Upload research papers via Files API → ask follow-up questions cheaply |
| **OCR replacement** | Pass scanned PDFs directly; Claude reads handwriting + printed text together |

---

## Try this

1. **Pass a real chart** — replace `test_chart.png` with a screenshot of any dashboard you have. Ask "what does this show?" Watch the level of detail.
2. **Mix two PDFs** — pass two policy documents in one call, ask "are these compatible?"
3. **Citations on a complex doc** — upload a longer document (10+ pages). Ask a question whose answer spans multiple sections. Watch how citations pinpoint each.
4. **Use the Files API** — upload `test_doc.pdf` once, then re-run all 3 questions referencing `file_id` instead of base64. Compare bandwidth on the wire.
5. **Bulk via Batches** — submit 10 small requests at half price. See the 50% cost saving in action.

---

## Mental model in one line

> **Native multimodal lifts the text-extraction tax. Citations turn faithfulness into a structural guarantee. Files + Batches turn one-call patterns into cost-efficient batch patterns. Use the right combination for your workload — interactive vs bulk, single-doc vs corpus, compliance vs convenience.**

---

## FAQ

**Q: What PDF formats does Claude support?**

A: Standard PDF 1.4 through 2.0. Encrypted PDFs need to be decrypted first. Scanned PDFs (image-only) work — Claude OCRs them internally. PDFs with forms, annotations, embedded fonts, and complex layouts all work.

**Q: How big can the PDF be?**

A: Per-request limit is 32MB. For larger files, use the Files API which supports up to 100MB and persists across requests.

**Q: Does it cost more than text input?**

A: PDFs and images consume input tokens proportional to their visual complexity — typically more than the same content as plain text. For a text-heavy PDF, ~1.5-2× the token count of extracting the text. Worth it for accuracy on tables/charts; not worth it for plain prose where text extraction is fine.

**Q: Can I cache a PDF?**

A: Yes — add `cache_control: {"type": "ephemeral"}` to the document content block. Same cache_control rules as text. Useful when the same PDF is queried repeatedly within 5 minutes.

**Q: How accurate are the citations?**

A: The `cited_text` is **copied verbatim** from the source. The model literally cannot fabricate it. What CAN be wrong: the model's interpretation of which passage answers the question (it might cite a related-but-not-quite-right passage). The citation itself is structurally correct; the relevance is still LLM judgment.

**Q: Can citations span multiple documents?**

A: Yes — pass multiple document content blocks in the same `content` array. Each gets indexed; citations include a `document_index` field telling you which one.

**Q: What's the difference between citations and just asking the model to quote?**

A: Asking the model to quote ("include the exact quote in your answer") is best-effort — the model may paraphrase or hallucinate quotes. The Citations API is **server-enforced** — Anthropic's backend verifies the cited_text exists in the source before returning it.

**Q: How does this compare to LangChain document loaders?**

A: LangChain's `PyPDFLoader`, `UnstructuredLoader`, etc., do text extraction and produce LangChain `Document` objects you can chunk + embed. They're good for corpus-scale RAG. Native multimodal is better for accuracy on individual PDFs where extraction would lose information. Use both — LangChain loaders for the corpus path, native multimodal for the precision path.

**Q: Are image and PDF inputs supported by all Claude models?**

A: Claude 3.5 onwards. Sonnet 4.6, Opus 4.7, Haiku 4.5 all support PDF and image input. Older models (Claude 2.x) don't.

**Q: Can I use the Batches API for non-Anthropic models?**

A: No — the Batches API is Anthropic-specific. For batching across multiple providers, use an AI Gateway like LiteLLM (Session 8) which has its own batching abstraction.

**Q: What if my PDF has handwriting?**

A: Claude handles handwriting via internal OCR. Quality varies with handwriting clarity. For mission-critical handwriting recognition (medical scripts, legal signatures), pair with a specialized OCR + human review.

---

## Related

- **Previous:** [19 — AI Gateway](19-ai-gateway.md)
- **Next:** Session 10 — Custom LangGraph + HITL (Track E)
- **Builds on:** [09 — RAG](09-rag.md) (the text-extraction-based RAG pattern this lesson augments) and [10 — Guardrails](10-guardrails.md) (faithfulness judge — Citations API is the structural alternative)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 9 of 40 (Track D complete)
