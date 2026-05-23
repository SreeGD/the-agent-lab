# 20 — Files & Document AI (Session 9)

> **Provider variant — OpenAI (`gpt-4o`)** This is the OpenAI version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `openai` (raw SDK), model is `gpt-4o`, and the API key env var is `OPENAI_API_KEY`. Code files: `labs/openai/20_pdf_vision_openai.py` and `labs/openai/20_citations_demo_openai.py`. Note: the Citations API with server-enforced character-range attribution is Anthropic-specific; the OpenAI equivalent demo uses GPT-4o's vision capabilities with explicit source-quoting prompts.

> **GPT-4o reads PDFs and images natively — no PyPDF, no OCR, no chunking.** Pass a base64-encoded PDF or PNG in a `content` block and GPT-4o parses it like a human would (text, layout, tables, charts, embedded images). The citations demo shows how to elicit verifiable source quotes from the model using prompt engineering.

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
| [`20_pdf_vision_openai.py`](../../openai/20_pdf_vision_openai.py) | Native PDF + image input. Three demos: PDF Q&A, chart interpretation, mixed cross-modal reasoning. |
| [`20_citations_demo_openai.py`](../../openai/20_citations_demo_openai.py) | Source-quoting demo — prompts GPT-4o to include verbatim quotes with character ranges in its response. |

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
3. Put in a `content` block as `{"type": "image_url", "image_url": {"url": "data:application/pdf;base64,..."}}`
4. GPT-4o reads it natively

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
       │                                     "type": "image_url",
       ▼                                     "image_url": {
   splitter.split()                            "url": "data:application/pdf;base64,...",
       │                                     },
       ▼                                   }
   chunks                                              │
       │                                              │
       ▼                                              ▼
   embed + store                            client.chat.completions.create(
       │                                     messages=[{"content": [doc, text]}]
       ▼                                   )
   retriever                                          │
       │                                              ▼
       ▼                                       GPT-4o reads the
   top-k chunks                               PDF natively
       │                                      (tables, layout,
       ▼                                       charts, all preserved)
   LLM (sees text only)
```

---

## Concept — native PDF input

```python
import openai, base64

client = openai.OpenAI()
pdf_b64 = base64.standard_b64encode(open("doc.pdf", "rb").read()).decode()

response = client.chat.completions.create(
    model="gpt-4o",
    max_tokens=400,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:application/pdf;base64,{pdf_b64}",
                },
            },
            {"type": "text", "text": "What does this document say about X?"},
        ],
    }],
)
```

Image input is the same shape with `"type": "image_url"` and a data URI like `data:image/png;base64,...`.

You can mix PDF + image + text in one call — the response handles cross-modal reasoning automatically.

---

## Concept — source-quoting prompt pattern

Unlike Anthropic's server-enforced Citations API, OpenAI's approach uses prompt engineering to elicit verifiable quotes:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:application/pdf;base64,{pdf_b64}"},
            },
            {
                "type": "text",
                "text": (
                    "Does the document say caching is 90% cheaper? "
                    "For each claim, include a verbatim quote from the source "
                    "enclosed in <quote>...</quote> tags."
                ),
            },
        ],
    }],
)

# Parse quoted sections from the response
import re
content = response.choices[0].message.content
quotes = re.findall(r"<quote>(.*?)</quote>", content, re.DOTALL)
```

The model includes verbatim excerpts from the document in its answer. This is best-effort (not server-enforced like Anthropic's Citations API), but for most use cases it provides traceable attribution. For compliance-grade grounding, use an independent verification step.

---

## Run them

```bash
python openai/20_pdf_vision_openai.py       # PDF + image + mixed
python openai/20_citations_demo_openai.py   # source-quoting with prompt engineering
```

The first creates the test artifacts. The second reuses them.

---

## Real output from a clean run

### Mixed PDF + image reasoning (cross-modal!)

```
Q: The PDF claims prompt caching makes input ~90% cheaper. The chart
   shows costs per model for an uncached call. If a caching customer
   was using gpt-4o for this kind of call, roughly what would they
   pay per cached request? Show your reasoning briefly.

A: ## Reasoning

   Uncached cost for gpt-4o: $0.0023 per call (from chart)
   PDF claim: Prompt caching makes input ~90% cheaper
   Calculation: $0.0023 × (1 - 0.90) = $0.0023 × 0.10 = ~$0.00023 per cached request

   ## Caveat
   This is approximate — in practice, only the cached portion of the
   prompt gets the discount (the new/uncached tokens are still billed at
   full rate). So the real saving depends on what fraction of the prompt
   is a stable prefix.
```

GPT-4o read the chart (visual), pulled the cost from it, read the PDF (text), pulled the caching claim, did the arithmetic, AND volunteered an honest caveat about partial caching. **No text extraction library could give you this.**

### Source-quoting demo

```
Q: What is the most common production gotcha and how is it fixed?

A: ## Most Common Production Gotcha: Prefix Instability

   The most common production gotcha is **prefix instability**.
   <quote>The most common production gotcha is prefix instability.
    The cache key is the byte exact prefix up to your cache_control marker.</quote>

   The fix is structural:
   <quote>The fix is structural: assemble prompts in stable to
    dynamic order (system first, then static content...</quote>
```

Each claim ties back to a verbatim excerpt from the source. Note: unlike Anthropic's Citations API, this relies on the model accurately copying text — verify critical quotes independently for compliance use cases.

---

## Production-pattern decision matrix

| Use case | Pick |
|---|---|
| Single PDF, ad-hoc question | Native multimodal (this lesson) |
| 10,000 PDFs, semantic search | Traditional RAG with PyPDF/unstructured |
| Compliance-grade Q&A on contracts | Source-quoting prompt + independent verification |
| Customer-facing chatbot citing your docs | Source-quoting + safe_rag-style guardrails |
| Quick chart interpretation | Native vision (this lesson) |
| Cross-modal reasoning (PDF + chart together) | Native multimodal (this lesson) |
| OCR over thousands of scanned forms | OpenAI Files API + Batch API (see below) |

---

## The Files API — upload once, reference many times

If you'll ask many questions of the same PDF, uploading it once is more efficient than base64-ing it into every request:

```python
# Upload once
with open("contract.pdf", "rb") as f:
    file = client.files.create(file=f, purpose="assistants")

# Reference by file_id thereafter (via Assistants API or Responses API)
for question in many_questions:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
            ],
        }],
        # Note: direct file_id reference in chat completions requires
        # the Responses API (gpt-4o) or the Assistants API file_search tool
    )
```

Saves bandwidth. Important for large PDFs in repeat-query workflows.

---

## The Batch API — 50% off for async work

For non-interactive workloads (overnight extractions, eval runs, bulk classification), use the Batch API:

```python
batch = client.batches.create(
    input_file_id=uploaded_jsonl_file_id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
)

# Returns immediately. Poll via:
status = client.batches.retrieve(batch.id)
# when status.status == "completed":
results = client.files.content(status.output_file_id)
# each result has its custom_id back so you can match them up.
```

Half the cost. Trade-off: no real-time response. Perfect for nightly cron jobs, weekly eval suites, bulk migration projects.

---

## Multimodal RAG — when to reach for CLIP/ColPali

For native multimodal (this lesson), you're passing PDFs/images directly to GPT-4o every time. That doesn't scale to thousands of documents.

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
| **Contract Q&A** | Upload contract PDF → ask questions with source-quoting prompt → audit trail of every quoted clause |
| **Form processing** | Pass a scanned form image → extract structured data via `with_structured_output` |
| **Chart interpretation** | Dashboard screenshots → "what does this chart suggest?" |
| **Compliance review** | Multi-document policy + claim → verified quotes across both |
| **Research assistant** | Upload research papers via Files API → ask follow-up questions cheaply |
| **OCR replacement** | Pass scanned PDFs directly; GPT-4o reads handwriting + printed text together |

---

## Try this

1. **Pass a real chart** — replace `test_chart.png` with a screenshot of any dashboard you have. Ask "what does this show?" Watch the level of detail.
2. **Mix two PDFs** — pass two policy documents in one call, ask "are these compatible?"
3. **Strengthen the citation prompt** — add "If you cannot find the exact text, say UNAVAILABLE instead of paraphrasing." Compare faithfulness.
4. **Use the Files API** — upload `test_doc.pdf` once, then reference it via the Assistants API file_search tool. Compare bandwidth on the wire.
5. **Bulk via Batch API** — submit 10 small requests at half price. See the 50% cost saving in action.

---

## Mental model in one line

> **Native multimodal lifts the text-extraction tax. Source-quoting prompts provide attribution through model behavior rather than server enforcement. Files + Batch API turn one-call patterns into cost-efficient batch patterns. Use the right combination for your workload — interactive vs bulk, single-doc vs corpus, compliance vs convenience.**

---

## FAQ

**Q: What PDF formats does GPT-4o support?**

A: Standard PDFs passed as base64 data URIs. GPT-4o processes each page as an image internally. Scanned PDFs (image-only) work — GPT-4o OCRs them. PDFs with forms, annotations, embedded fonts, and complex layouts all work.

**Q: How big can the PDF be?**

A: Per-request limits apply based on the total token budget. For larger files or repeat queries, use the Files API (supports up to 512 MB).

**Q: Does it cost more than text input?**

A: PDFs and images consume input tokens proportional to their visual complexity — typically more than the same content as plain text. For a text-heavy PDF, ~1.5-2× the token count of extracting the text. Worth it for accuracy on tables/charts; not worth it for plain prose where text extraction is fine.

**Q: Can I cache a PDF across requests?**

A: OpenAI automatically caches prompt prefixes for qualifying requests (1024+ tokens). Unlike Anthropic, you don't need to explicitly mark a `cache_control` field — caching happens transparently when the same prefix is reused.

**Q: How accurate are the source quotes?**

A: The model aims to copy text verbatim but can paraphrase. For compliance-grade attribution, verify quoted text against the original document programmatically. Anthropic's Citations API provides server-enforced guarantees that OpenAI's prompt-engineering approach does not.

**Q: Can quotes span multiple documents?**

A: Yes — pass multiple document content blocks in the same `content` array. Instruct the model to tag each quote with a document identifier.

**Q: What's the difference between prompt-based quoting and Anthropic's Citations API?**

A: Anthropic's Citations API verifies the `cited_text` exists verbatim in the source document at the server level before returning it. Prompt-based quoting asks the model to include quotes, but the model *may* paraphrase. For high-stakes compliance work, prefer Anthropic's Citations API. For most use cases, prompt-based quoting is sufficient.

**Q: How does this compare to LangChain document loaders?**

A: LangChain's `PyPDFLoader`, `UnstructuredLoader`, etc., do text extraction and produce LangChain `Document` objects you can chunk + embed. They're good for corpus-scale RAG. Native multimodal is better for accuracy on individual PDFs where extraction would lose information. Use both — LangChain loaders for the corpus path, native multimodal for the precision path.

**Q: Are image and PDF inputs supported by all GPT-4o models?**

A: GPT-4o and GPT-4o-mini both support image input. PDF support via data URI depends on your API tier — check OpenAI's current documentation. For guaranteed PDF support, use the Assistants API with file_search.

**Q: Can I use the Batch API for non-OpenAI models?**

A: No — the OpenAI Batch API is OpenAI-specific. For batching across multiple providers, use an AI Gateway like LiteLLM (Session 8) which has its own batching abstraction.

**Q: What if my PDF has handwriting?**

A: GPT-4o handles handwriting via internal OCR. Quality varies with handwriting clarity. For mission-critical handwriting recognition (medical scripts, legal signatures), pair with a specialized OCR + human review.

---

## Related

- **Previous:** [19 — AI Gateway](19-ai-gateway.md)
- **Next:** Session 10 — Custom LangGraph + HITL (Track E)
- **Builds on:** [09 — RAG](09-rag.md) (the text-extraction-based RAG pattern this lesson augments) and [10 — Guardrails](10-guardrails.md) (faithfulness judge — source-quoting is the prompt-engineering alternative)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 9 of 40 (Track D complete)
