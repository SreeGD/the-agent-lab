"""Anthropic Citations API — verified character-range citations.

The Citations API turns the faithfulness story from a probabilistic
LLM-judge check (see safe_rag.py / production_chatbot.py) into a
server-enforced guarantee. When you enable citations on a document, the
model's response contains BOTH text blocks AND citation blocks pointing
to specific character ranges in the source. The model literally cannot
fabricate a citation — every cited_text must exist in the source.

Production use cases:
  - Compliance: legal / medical Q&A where every claim must be auditable
  - Customer support: "the docs say X" must be verifiable
  - Research assistants: cite-or-die mode

Note: requires an existing test_doc.pdf; run 20_pdf_vision.py first to
generate it (or this script will generate it on demand).
"""

import base64
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
HERE = Path(__file__).parent
TEST_PDF = HERE / "test_doc.pdf"

client = anthropic.Anthropic()


def _ensure_test_pdf():
    """Generate the test PDF if it doesn't exist (deferred import)."""
    if TEST_PDF.exists():
        return
    # Import lazily — only needed if PDF is missing
    import sys
    sys.path.insert(0, str(HERE))
    pdf_module = __import__("20_pdf_vision")
    pdf_module._build_test_artifacts()


# =====================================================================
# Send a query with citations enabled
# =====================================================================

def query_with_citations(question: str) -> anthropic.types.Message:
    pdf_b64 = base64.standard_b64encode(TEST_PDF.read_bytes()).decode()

    return client.messages.create(
        model=MODEL,
        max_tokens=600,
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
                    "title": "Prompt Caching: A Technical Primer",
                    "citations": {"enabled": True},   # ← the magic toggle
                },
                {
                    "type": "text",
                    "text": (
                        f"{question}\n\n"
                        "Cite specific passages from the document that support "
                        "your answer."
                    ),
                },
            ],
        }],
    )


def render_response(response) -> None:
    """Pretty-print the response showing text + citation blocks inline."""
    print()
    citation_count = 0
    for block in response.content:
        if block.type == "text":
            # Print the text and any inline citations attached to it
            print(block.text, end="")
            if hasattr(block, "citations") and block.citations:
                for cite in block.citations:
                    citation_count += 1
                    snippet = (cite.cited_text[:100] + "...") if len(cite.cited_text) > 100 else cite.cited_text
                    print(f"\n      [#{citation_count} cited_text: {snippet!r}]", end="")
            print()
    print(f"\n  ── Citations: {citation_count} ──")
    print(f"  tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}")


# =====================================================================
# Demo
# =====================================================================

QUESTIONS = [
    "What percentage discount does prompt caching offer on cached tokens?",
    "Why is the prefill phase so expensive?",
    "What is the most common production gotcha and how is it fixed?",
]


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY missing — add it to .env")

    print("=" * 70)
    print("ANTHROPIC CITATIONS API — verified character-range citations")
    print("=" * 70)

    _ensure_test_pdf()

    for q in QUESTIONS:
        print(f"\n→ Q: {q}")
        response = query_with_citations(q)
        render_response(response)

    print("\n" + "=" * 70)
    print("WHAT MADE THIS DIFFERENT FROM A FAITHFULNESS LLM-JUDGE")
    print("=" * 70)
    print(
        "  In safe_rag.py we wrote a faithfulness judge: a second LLM call\n"
        "  that reads context + answer and decides 'supported'/'unsupported.'\n"
        "  That's probabilistic — the judge can be wrong, miss a hallucination,\n"
        "  or be overly strict on valid paraphrases.\n"
        "\n"
        "  The Citations API is STRUCTURAL: the model returns citation blocks\n"
        "  pointing to specific character ranges. The cited_text is COPIED\n"
        "  verbatim from the source — the model literally cannot put a quote\n"
        "  there that doesn't exist in the document. Server-enforced.\n"
        "\n"
        "  For compliance/legal/medical Q&A, this is the difference between:\n"
        "    'we have an LLM judge'           ← defendable but not perfect\n"
        "    'we have a server-guaranteed audit trail'  ← real provenance\n"
    )
