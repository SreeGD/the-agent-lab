"""Native PDF + image input — Ollama reads PDFs via rendered PNG pages.

# Requires: ollama serve + ollama pull llava
# Requires: pip install pymupdf

No PyPDF text extraction, no chunking. Each PDF page is rasterized to PNG
at 150 DPI and sent as a vision content block. The llava model parses layout,
tables, and text natively from the image.

NOTE: llama3.2 is text-only. Use llava (or llava-phi3) for vision/image tasks.
      `ollama pull llava` before running this script.

Three demos in one run:
  1. PDF Q&A         -- ask questions about a PDF using rendered page images
  2. Image read       -- interpret a chart from raw bytes
  3. Mixed multimodal -- combine both in one call

The test PDF + chart are generated at runtime (see _build_test_artifacts).
"""

import base64
from pathlib import Path

import openai
from dotenv import load_dotenv
from fpdf import FPDF
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

load_dotenv()

MODEL = "llava"  # llava is the multimodal model in Ollama; text-only uses llama3.2
HERE = Path(__file__).parent.parent  # labs/ directory
TEST_PDF = HERE / "test_doc.pdf"
TEST_PNG = HERE / "test_chart.png"

client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")


# =====================================================================
# Build test artifacts at runtime (kept out of git via .gitignore)
# =====================================================================

PDF_BODY = """\
Prompt Caching: A Technical Primer

Prompt caching is a server side optimization in modern LLM inference. The provider checkpoints the model's KV cache for a prompt prefix you mark with a cache_control hint. On subsequent requests reusing that exact prefix, the server reuses the precomputed KV state instead of running prefill again.

Why it is cheaper: the prefill phase of transformer inference is compute bound and accounts for roughly 60 to 90 percent of total GPU work. Skipping it means your bill drops accordingly. Anthropic prices cached input tokens at $0.30 per million versus $3.00 per million for fresh input, a 90 percent discount. Cache writes carry a 1.25x premium for the 5 minute TTL tier.

The most common production gotcha is prefix instability. The cache key is the byte exact prefix up to your cache_control marker. Inject a timestamp or per request user ID anywhere before the marker and you collapse your hit rate to near zero. The fix is structural: assemble prompts in stable to dynamic order (system first, then static context, then dynamic user content) so the cacheable prefix stays identical across requests.
"""


def _build_test_artifacts() -> None:
    """Create the test PDF and PNG if they don't exist."""
    if not TEST_PDF.exists():
        pdf = FPDF()
        pdf.set_margins(15, 15, 15)
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        body = (PDF_BODY
                .replace("—", "--")
                .replace("‘", "'")
                .replace("’", "'"))
        for paragraph in body.split("\n"):
            if paragraph.strip():
                pdf.multi_cell(w=180, h=6, text=paragraph)
            else:
                pdf.ln(4)
        pdf.output(str(TEST_PDF))
        print(f"  [generated] {TEST_PDF.name} ({TEST_PDF.stat().st_size:,} bytes)")

    if not TEST_PNG.exists():
        models = ["Haiku 4.5", "Sonnet 4.6", "Opus 4.7"]
        costs = [0.000776, 0.002343, 0.007285]
        latencies = [2.94, 6.05, 8.12]

        fig, ax1 = plt.subplots(figsize=(8, 5))
        bars = ax1.bar(models, costs, color="#3a86ff", alpha=0.85)
        ax1.set_ylabel("Cost (USD per call)", color="#3a86ff", fontsize=11)
        ax1.tick_params(axis="y", labelcolor="#3a86ff")
        ax1.set_title("Claude model bake-off: cost vs latency (same prompt)")

        ax2 = ax1.twinx()
        ax2.plot(models, latencies, "o-", color="#ff595e", linewidth=2, markersize=8)
        ax2.set_ylabel("Latency (seconds)", color="#ff595e", fontsize=11)
        ax2.tick_params(axis="y", labelcolor="#ff595e")

        for b, c in zip(bars, costs):
            ax1.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.05,
                     f"${c:.4f}", ha="center", fontsize=9)
        plt.tight_layout()
        plt.savefig(TEST_PNG, dpi=100)
        plt.close()
        print(f"  [generated] {TEST_PNG.name} ({TEST_PNG.stat().st_size:,} bytes)")


def _b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("utf-8")


def pdf_to_base64_images(pdf_path: str) -> list[str]:
    """Render each PDF page as a base64-encoded PNG using PyMuPDF."""
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        images.append(base64.b64encode(pix.tobytes("png")).decode())
    return images


# =====================================================================
# DEMO 1 -- PDF Q&A
# =====================================================================

QUESTION_PDF = "What is the prefill phase and why does it dominate inference cost?"
QUESTION_PDF_2 = "What's the cost-per-million for cached vs fresh input tokens?"


def demo_pdf_qa():
    print("\n" + "=" * 70)
    print("DEMO 1 -- PDF Q&A (llava reads rendered PDF pages as images)")
    print("=" * 70)

    images = pdf_to_base64_images(str(TEST_PDF))
    print(f"  PDF rendered to {len(images)} page image(s) at 150 DPI")

    questions = [QUESTION_PDF, QUESTION_PDF_2]

    for q in questions:
        print(f"\n  -> Q: {q}")
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": q},
                    *[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
                      for img in images],
                ],
            }],
        )
        answer = response.choices[0].message.content
        print(f"    A: {answer[:300]}{'...' if len(answer) > 300 else ''}")
        print(f"    tokens: in={response.usage.prompt_tokens} out={response.usage.completion_tokens}")


# =====================================================================
# DEMO 2 -- Image read
# =====================================================================

def demo_image_read():
    print("\n" + "=" * 70)
    print("DEMO 2 -- Image read (llava interprets a chart)")
    print("=" * 70)

    png_b64 = _b64(TEST_PNG)
    print(f"  PNG base64 payload: {len(png_b64):,} chars")

    question = (
        "What does this chart show? Identify the axes, the metrics, and "
        "the trend across models. Note any cost-vs-latency trade-off."
    )

    print(f"\n  -> Q: {question}")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{png_b64}",
                    },
                },
                {"type": "text", "text": question},
            ],
        }],
    )
    answer = response.choices[0].message.content
    print(f"    A: {answer[:500]}{'...' if len(answer) > 500 else ''}")
    print(f"    tokens: in={response.usage.prompt_tokens} out={response.usage.completion_tokens}")


# =====================================================================
# DEMO 3 -- Mixed PDF + image (cross-modal reasoning)
# =====================================================================

def demo_mixed():
    print("\n" + "=" * 70)
    print("DEMO 3 -- Mixed: PDF (as images) + chart (cross-modal reasoning)")
    print("=" * 70)

    pdf_images = pdf_to_base64_images(str(TEST_PDF))
    png_b64 = _b64(TEST_PNG)

    question = (
        "The PDF claims prompt caching makes input ~90% cheaper. The chart "
        "shows costs per model for an uncached call. If a caching customer "
        "was using Sonnet 4.6 for this kind of call, roughly what would they "
        "pay per cached request? Show your reasoning briefly."
    )

    print(f"  -> Q: {question[:120]}...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                *[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
                  for img in pdf_images],
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{png_b64}",
                    },
                },
            ],
        }],
    )
    answer = response.choices[0].message.content
    print(f"\n    A: {answer}")
    print(f"\n    tokens: in={response.usage.prompt_tokens} out={response.usage.completion_tokens}")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PDF + VISION (Ollama/llava) -- PyMuPDF renders pages, llava reads images")
    print("=" * 70)
    print("  NOTE: Requires `ollama pull llava` (llama3.2 is text-only).")
    print("  Generating test artifacts if needed...")
    _build_test_artifacts()

    demo_pdf_qa()
    demo_image_read()
    demo_mixed()

    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS")
    print("=" * 70)
    print(
        "  * Ollama does not accept PDF document blocks natively like Anthropic.\n"
        "    Instead, we rasterize each page to PNG (PyMuPDF, 150 DPI) and send\n"
        "    the images in content blocks -- llava reads them via vision.\n\n"
        "  * PyMuPDF (fitz) renders faithfully including tables, layout, fonts.\n"
        "    Quality is comparable to native PDF parsing for typical documents.\n\n"
        "  * Image input uses the same image_url content block format as the\n"
        "    OpenAI-compatible API -- base64 data URI with data:image/png prefix.\n\n"
        "  * llava is the recommended vision model for Ollama. Use llava-phi3\n"
        "    for a smaller/faster variant. llama3.2 is text-only.\n\n"
        "  * Mixed content (PDF pages + images + text) in one call enables\n"
        "    cross-modal reasoning -- same capability as cloud vision APIs,\n"
        "    with full data privacy and no per-token cost.\n\n"
        "  * For repeated access to the same PDF, render the pages once and\n"
        "    cache the base64 strings -- avoids re-rasterizing on each request.\n\n"
        "  * For very large PDFs (100+ pages), chunk by page range and make\n"
        "    multiple calls rather than sending all pages at once."
    )
