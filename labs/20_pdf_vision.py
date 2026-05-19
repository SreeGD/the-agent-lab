"""Native PDF + image input — Claude reads both via content blocks.

No PyPDF, no text extraction, no chunking. The PDF goes directly into the
message as a base64-encoded document block; Claude parses pages, layout,
tables, and embedded text natively. Images go in as image content blocks.

Three demos in one run:
  1. PDF Q&A         — ask questions about a PDF Claude has never seen
  2. Image read       — interpret a chart from raw bytes
  3. Mixed multimodal — combine both in one call

The test PDF + chart are generated at runtime (see _build_test_artifacts).
"""

import base64
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fpdf import FPDF
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

load_dotenv()

MODEL = "claude-sonnet-4-6"
HERE = Path(__file__).parent
TEST_PDF = HERE / "test_doc.pdf"
TEST_PNG = HERE / "test_chart.png"

client = anthropic.Anthropic()


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
        # Replace Unicode chars FPDF's default font can't render
        body = (PDF_BODY
                .replace("\u2014", "--")
                .replace("\u2018", "'")
                .replace("\u2019", "'"))
        for paragraph in body.split("\n"):
            if paragraph.strip():
                pdf.multi_cell(w=180, h=6, text=paragraph)
            else:
                pdf.ln(4)
        pdf.output(str(TEST_PDF))
        print(f"  [generated] {TEST_PDF.name} ({TEST_PDF.stat().st_size:,} bytes)")

    if not TEST_PNG.exists():
        # Re-create the cost bake-off chart from Session 8 (numbers approximated)
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


# =====================================================================
# DEMO 1 — PDF Q&A
# =====================================================================

def demo_pdf_qa():
    print("\n" + "=" * 70)
    print("DEMO 1 — PDF Q&A (Claude reads the PDF natively)")
    print("=" * 70)

    pdf_b64 = _b64(TEST_PDF)
    print(f"  PDF base64 payload: {len(pdf_b64):,} chars")

    questions = [
        "What is the prefill phase and why does it dominate inference cost?",
        "What's the cost-per-million for cached vs fresh input tokens?",
    ]

    for q in questions:
        print(f"\n  → Q: {q}")
        response = client.messages.create(
            model=MODEL,
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
                    {"type": "text", "text": q},
                ],
            }],
        )
        answer = "".join(b.text for b in response.content if b.type == "text")
        print(f"    A: {answer[:300]}{'...' if len(answer) > 300 else ''}")
        print(f"    tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}")


# =====================================================================
# DEMO 2 — Image read
# =====================================================================

def demo_image_read():
    print("\n" + "=" * 70)
    print("DEMO 2 — Image read (Claude interprets a chart)")
    print("=" * 70)

    png_b64 = _b64(TEST_PNG)
    print(f"  PNG base64 payload: {len(png_b64):,} chars")

    question = (
        "What does this chart show? Identify the axes, the metrics, and "
        "the trend across models. Note any cost-vs-latency trade-off."
    )

    print(f"\n  → Q: {question}")
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": png_b64,
                    },
                },
                {"type": "text", "text": question},
            ],
        }],
    )
    answer = "".join(b.text for b in response.content if b.type == "text")
    print(f"    A: {answer[:500]}{'...' if len(answer) > 500 else ''}")
    print(f"    tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}")


# =====================================================================
# DEMO 3 — Mixed PDF + image (cross-modal reasoning)
# =====================================================================

def demo_mixed():
    print("\n" + "=" * 70)
    print("DEMO 3 — Mixed: PDF + image (cross-modal reasoning)")
    print("=" * 70)

    pdf_b64 = _b64(TEST_PDF)
    png_b64 = _b64(TEST_PNG)

    question = (
        "The PDF claims prompt caching makes input ~90% cheaper. The chart "
        "shows costs per model for an uncached call. If a caching customer "
        "was using Sonnet 4.6 for this kind of call, roughly what would they "
        "pay per cached request? Show your reasoning briefly."
    )

    print(f"  → Q: {question[:120]}...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
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
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": png_b64,
                    },
                },
                {"type": "text", "text": question},
            ],
        }],
    )
    answer = "".join(b.text for b in response.content if b.type == "text")
    print(f"\n    A: {answer}")
    print(f"\n    tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY missing — add it to .env")

    print("=" * 70)
    print("PDF + VISION — native multimodal input to Claude")
    print("=" * 70)
    print("  Generating test artifacts if needed...")
    _build_test_artifacts()

    demo_pdf_qa()
    demo_image_read()
    demo_mixed()

    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS")
    print("=" * 70)
    print(
        "  • PDF input is NATIVE — no PyPDF, no chunking, no embeddings.\n"
        "    Just base64 the file and put it in a 'document' content block.\n"
        "  • Image input is also native — same shape, different media_type.\n"
        "  • Mixed content (PDF + image + text) in one call enables cross-modal\n"
        "    reasoning that text-extraction-based RAG fundamentally can't match.\n"
        "  • For repeated access to the same file, use the Files API: upload\n"
        "    once with client.files.upload(), reference by file_id in many\n"
        "    requests. Saves bytes on the wire.\n"
        "  • Native multimodal is the right tool when accuracy on tables,\n"
        "    layout, charts, or handwriting matters. Text-extraction loses\n"
        "    information that the model could otherwise see."
    )
