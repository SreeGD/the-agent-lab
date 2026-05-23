# 20 — Files & Document AI (Session 9)

> **Provider variant — Ollama (`llama3.2` / `llava`)** This is the Ollama version of this lesson. The logic and patterns are largely identical to the Anthropic version. What differs: vision tasks use `llava` (Ollama's multimodal model), PDF/image input uses LangChain's document loaders rather than the native Anthropic API, and Anthropic-specific features (Citations API, Files API, Batches API) do not have direct Ollama equivalents — see notes in each section. Code file: `labs/ollama/20_pdf_vision_ollama.py`.

> **Read PDFs and images through an LLM.** Pass document content directly and let the model reason over text, tables, charts, and images. Faithfulness can be improved through careful prompting and grounding patterns.

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
| [`20_pdf_vision_ollama.py`](../ollama/20_pdf_vision_ollama.py) | PDF + image input via Ollama. Three demos: PDF Q&A (via text extraction), chart interpretation (via llava), mixed document reasoning. |

Test artifacts (`test_doc.pdf`, `test_chart.png`) generated at runtime and gitignored.

---

## Ollama-specific notes

**Important differences from the Anthropic version:**

1. **Vision model**: Ollama uses `llava` for image/PDF visual understanding. Run `ollama pull llava` before the vision demos.

2. **Native PDF input**: Ollama does not support native PDF content blocks like the Anthropic API. Instead, use `PyPDF2` or `pdfplumber` to extract text, then pass the extracted text to `ChatOllama`. For visual PDF pages (charts, diagrams), render to images and pass to `llava`.

3. **Citations API**: This is an Anthropic-only feature. With Ollama, implement a prompt-based grounding pattern: instruct the model to quote the relevant passage before answering, then verify the quote exists in the source text.

4. **Files API**: Anthropic-only. With Ollama, load documents locally and pass content directly.

5. **Batches API**: Anthropic-only. With Ollama, use `chain.batch([...])` for parallel local inference, or run a cron job with sequential processing.

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

With Ollama + llava for visual pages:
1. Extract text from PDF (for text-heavy pages)
2. Render PDF pages to images (for visual pages)
3. Pass to llava for visual understanding

For accuracy on tables, charts, layout, handwriting — **multimodal is the right tool for visual pages**. Text-extraction-based RAG fundamentally can't match it for layout-heavy content.

---

## The analogy

**A library researcher who reads the actual book vs. one who only reads transcripts.**

Old workflow = the transcript reader. Someone OCR'd the book and gave them the text. They see what was in the body paragraphs but miss the photo of the diagram, the table that doesn't render, the marginalia.

New workflow = the book reader. Sees what's actually on the page. Tables stay tables. Diagrams stay diagrams.

For most documents you can get away with the transcript reader. For layout-heavy work, the book reader wins.

---

## Visual

```
       TEXT-HEAVY PDF                          VISUAL PDF (charts/diagrams)
       ──────────────                          ────────────────────────────

   PDF on disk                                 PDF on disk
       │                                           │
       ▼                                           ▼
   pdfplumber.extract_text()                  pdf2image.convert_from_path()
       │                                           │
       ▼                                           ▼
   plain text                                 page images (PNG)
       │                                           │
       ▼                                           ▼
   ChatOllama(model="llama3.2")               ChatOllama(model="llava")
       │                                           │
       ▼                                           ▼
   text-based Q&A                             visual Q&A (charts, layout)
```

---

## Concept — PDF text extraction + Q&A

```python
import pdfplumber
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

# Extract text from PDF
with pdfplumber.open("doc.pdf") as pdf:
    pdf_text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)

# Ask questions about the extracted text
messages = [
    SystemMessage("Answer strictly from the provided document text. Cite the relevant passage."),
    HumanMessage(f"Document:\n{pdf_text}\n\nQuestion: What does this document say about caching?"),
]
response = model.invoke(messages)
print(response.content)
```

---

## Concept — image/chart understanding with llava

```python
import base64
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

# Use llava for visual content
vision_model = ChatOllama(model="llava", temperature=0)

# Encode image
with open("chart.png", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

# Ask about the visual content
message = HumanMessage(
    content=[
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        {"type": "text", "text": "What does this chart show? Describe the key trends."},
    ]
)
response = vision_model.invoke([message])
print(response.content)
```

---

## Grounding pattern — Ollama alternative to Citations API

Since Ollama doesn't have a native Citations API, use prompt-based grounding:

```python
system_prompt = """Answer the user's question using ONLY information in the provided document.
Before giving your answer, quote the EXACT passage from the document that supports it.
Format:

QUOTE: [exact text from document]
ANSWER: [your answer based on the quote]

If the document does not contain the answer, say "Not found in document."
"""

messages = [
    SystemMessage(system_prompt),
    HumanMessage(f"Document:\n{pdf_text}\n\nQuestion: {question}"),
]
response = model.invoke(messages)

# Post-process: verify the quoted text exists in the source
quote = extract_quote_from_response(response.content)
if quote and quote in pdf_text:
    print("✓ Quote verified in source")
else:
    print("⚠ Quote not found in source — possible hallucination")
```

This is a best-effort alternative. It's not as structurally guaranteed as the Anthropic Citations API, but it significantly reduces hallucination compared to unconstrained prompting.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, `ollama pull llama3.2` and `ollama pull llava` must have been run first.

```bash
python ollama/20_pdf_vision_ollama.py        # PDF + image demos
```

The first creates the test artifacts. The second reuses them.

---

## Production-pattern decision matrix

| Use case | Pick |
|---|---|
| Single PDF, ad-hoc question | Text extraction + ChatOllama (this lesson) |
| Visual PDF page, chart interpretation | llava via ChatOllama (this lesson) |
| 10,000 PDFs, semantic search | Traditional RAG with pdfplumber/unstructured |
| Compliance-grade Q&A on contracts | Prompt-based grounding (Ollama) or Citations API (Anthropic) |
| Customer-facing chatbot citing your docs | Prompt-based grounding + safe_rag-style guardrails |
| Quick chart interpretation | llava (this lesson) |
| Bulk batch processing | `chain.batch([...])` for parallel local inference |

---

## Multimodal RAG — when to reach for CLIP/ColPali

For native multimodal (this lesson), you're extracting/rendering PDFs every time. That doesn't scale to thousands of documents.

For corpus-scale multimodal search, use **unified-embedding RAG**:

- **CLIP** (OpenAI) — embeds images AND text into the same vector space; you can search "show me charts that look like this" by image, or "find diagrams of the architecture" by text
- **ColPali** (newer, 2024) — represents PDF pages as patch grids embedded by a vision-language model; outperforms text-extraction RAG on layout-heavy docs

The pattern is the same as `09_rag_ollama.py`, but the embedder produces image-and-text-aware vectors. Use when:
- Your corpus has 100s+ visual documents
- Text extraction misses essential info (charts, signatures, layout, handwriting)
- You need to search by visual similarity, not just text similarity

---

## Production patterns this unlocks

| Pattern | Real use case |
|---|---|
| **Contract Q&A** | Extract text from contract PDF → ask questions with grounding → verify quotes |
| **Form processing** | Pass a scanned form image to llava → extract structured data via `with_structured_output` |
| **Chart interpretation** | Dashboard screenshots → "what does this chart suggest?" via llava |
| **Research assistant** | Load research papers → ask follow-up questions locally |
| **OCR replacement** | Pass images to llava; it reads handwriting + printed text together |

---

## Try this

1. **Pass a real chart** — replace `test_chart.png` with a screenshot of any dashboard you have. Ask "what does this show?" via llava. Watch the level of detail.
2. **Mix two PDFs** — extract text from two policy documents, pass both in one call, ask "are these compatible?"
3. **Verify grounding** — implement the quote-extraction + verification pattern. Try a question whose answer isn't in the document. Watch how the model handles "Not found."
4. **Bulk processing** — submit 10 small PDF extractions at once via `chain.batch([...])`. See the parallel local inference speedup.
5. **Compare extraction quality** — try `PyPDF2` vs `pdfplumber` vs rendering to image + llava on the same table-heavy PDF. See which preserves the table structure best.

---

## Mental model in one line

> **For text-heavy PDFs, extract text and pass to ChatOllama. For visual pages (charts, tables, diagrams), render to images and pass to llava. For faithfulness, use prompt-based grounding with quote verification. For bulk work, use chain.batch(). The Anthropic Citations/Files/Batches APIs have no direct Ollama equivalents but can be approximated.**

---

## FAQ

**Q: Does Ollama support native PDF input like Anthropic?**

A: No — Ollama's API accepts text and images (via llava), not native PDF content blocks. Use `pdfplumber` for text extraction, or `pdf2image` + llava for visual pages.

**Q: Which Ollama model handles images?**

A: `llava` (LLaVA — Large Language and Vision Assistant). Pull it with `ollama pull llava`. It handles PNG, JPEG, and other common image formats.

**Q: Is there a Citations API equivalent for Ollama?**

A: No native equivalent. Use prompt-based grounding: instruct the model to quote before answering, then programmatically verify the quote exists in the source document. This reduces hallucination significantly but isn't structurally guaranteed.

**Q: What about the Files API and Batches API?**

A: Both are Anthropic-specific. For files, load documents locally. For batching, use `chain.batch([...])` for parallel local inference, or a simple loop for sequential processing. There is no async batch-and-wait pattern with Ollama.

**Q: How accurate is llava compared to Anthropic's native PDF input?**

A: LLaVA is generally less capable than Claude for complex visual reasoning. For simple charts and clear diagrams it performs well. For complex multi-column layouts, tables with many cells, or handwriting, Claude's native PDF input typically produces better results.

**Q: Can I do cross-modal reasoning (PDF text + image in one call) with Ollama?**

A: Not natively in a single request. Process text and image separately, then combine the results in a follow-up prompt. This adds one extra LLM call but achieves similar cross-modal reasoning.

---

## Related

- **Previous:** [19 — AI Gateway](19-ai-gateway.md)
- **Next:** Session 10 — Custom LangGraph + HITL (Track E)
- **Builds on:** [09 — RAG](09-rag.md) (the text-extraction-based RAG pattern this lesson augments) and [10 — Guardrails](10-guardrails.md) (faithfulness judge — grounding pattern is the Ollama alternative)
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 9 of 40 (Track D complete)
