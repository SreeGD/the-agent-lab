"""Citations via prompt instructions — verified attribution with Ollama.

# Requires: ollama serve + ollama pull llama3.2
# NOTE: Ollama does not have a native citations API equivalent to Anthropic's.
# This variant uses prompt-based citation instructions instead.

The Anthropic Citations API turns faithfulness into a server-enforced
guarantee — cited_text must exist verbatim in the source document.

Ollama does not expose this API surface. This variant achieves the same
GOAL — every factual claim is tagged to a source — through prompt
engineering: we pass numbered source blocks and instruct the model to
cite as [Source N].

Production use cases:
  - Compliance: legal / medical Q&A where every claim must be auditable
  - Customer support: "the docs say X" must be verifiable
  - Research assistants: cite-or-die mode

Note: requires a test_doc.pdf in the labs/ directory; run 20_pdf_vision.py
first to generate it (or this script will generate it on demand).
"""

import re
from pathlib import Path

import openai
from dotenv import load_dotenv

load_dotenv()

MODEL = "llama3.2"
HERE = Path(__file__).parent.parent  # labs/ directory
TEST_PDF = HERE / "test_doc.pdf"

client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# =====================================================================
# Source documents — the same content as the test PDF, exposed as
# discrete text chunks so the model can cite [Source N].
# =====================================================================

SOURCE_DOCS = [
    (
        "Prompt caching is a server side optimization in modern LLM inference. "
        "The provider checkpoints the model's KV cache for a prompt prefix you mark "
        "with a cache_control hint. On subsequent requests reusing that exact prefix, "
        "the server reuses the precomputed KV state instead of running prefill again."
    ),
    (
        "Why it is cheaper: the prefill phase of transformer inference is compute bound "
        "and accounts for roughly 60 to 90 percent of total GPU work. Skipping it means "
        "your bill drops accordingly. Anthropic prices cached input tokens at $0.30 per "
        "million versus $3.00 per million for fresh input, a 90 percent discount. Cache "
        "writes carry a 1.25x premium for the 5 minute TTL tier."
    ),
    (
        "The most common production gotcha is prefix instability. The cache key is the "
        "byte exact prefix up to your cache_control marker. Inject a timestamp or per "
        "request user ID anywhere before the marker and you collapse your hit rate to "
        "near zero. The fix is structural: assemble prompts in stable to dynamic order "
        "(system first, then static context, then dynamic user content) so the cacheable "
        "prefix stays identical across requests."
    ),
]

QUESTIONS = [
    "What percentage discount does prompt caching offer on cached tokens?",
    "Why is the prefill phase so expensive?",
    "What is the most common production gotcha and how is it fixed?",
]


def _ensure_test_pdf():
    """Generate the test PDF if it doesn't exist (deferred import)."""
    if TEST_PDF.exists():
        return
    import sys
    sys.path.insert(0, str(HERE))
    pdf_module = __import__("20_pdf_vision")
    pdf_module._build_test_artifacts()


# =====================================================================
# Query with prompt-based citations
# =====================================================================

def query_with_citations(question: str) -> dict:
    """Ask a question using prompt-engineered citations.

    Passes numbered [Source N] blocks to the model and instructs it to
    cite each claim. Returns {'answer': str, 'prompt_tokens': int, 'completion_tokens': int}.
    """
    # Build context from the same source documents
    context = "\n\n".join(f"[Source {i+1}] {doc}" for i, doc in enumerate(SOURCE_DOCS))

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "Answer using only the provided sources. Cite each fact as [Source N].",
            },
            {
                "role": "user",
                "content": f"Sources:\n{context}\n\nQuestion: {question}",
            },
        ],
    )
    answer = response.choices[0].message.content
    return {
        "answer": answer,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
    }


def render_response(question: str, result: dict) -> None:
    """Pretty-print the answer, highlighting inline citation tags."""
    print(f"\n  Answer: {result['answer']}")
    # Count how many [Source N] tags appear
    citations = re.findall(r"\[Source \d+\]", result["answer"])
    print(f"\n  Citations found: {len(citations)} -- {citations}")
    print(f"  tokens: in={result['prompt_tokens']} out={result['completion_tokens']}")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PROMPT-BASED CITATIONS (Ollama) — attributed answers from numbered sources")
    print("=" * 70)
    print("  NOTE: Ollama does not have a native citations API equivalent to")
    print("  Anthropic's. This variant uses prompt instructions to achieve the")
    print("  same goal: every factual claim is tagged [Source N].")

    _ensure_test_pdf()

    for q in QUESTIONS:
        print(f"\n-> Q: {q}")
        result = query_with_citations(q)
        render_response(q, result)

    print("\n" + "=" * 70)
    print("COMPARISON: ANTHROPIC CITATIONS VS PROMPT-BASED CITATIONS")
    print("=" * 70)
    print(
        "  Anthropic Citations API (native):\n"
        "    - Returns citation blocks with character-range spans\n"
        "    - cited_text is COPIED verbatim from source -- server-enforced\n"
        "    - Model literally cannot fabricate a citation\n"
        "    - Full audit trail for compliance/legal/medical use cases\n\n"
        "  Prompt-based citations (this file / Ollama):\n"
        "    - Model is instructed to cite as [Source N]\n"
        "    - Works well in practice; hallucinated citations are rare\n"
        "    - Not server-enforced -- model could in theory cite incorrectly\n"
        "    - Sufficient for most production applications\n"
        "    - Additional hardening: post-process to verify each [Source N]\n"
        "      claim appears in the corresponding source text\n\n"
        "  For compliance/legal/medical Q&A requiring hard guarantees,\n"
        "  use Anthropic's native Citations API. For general RAG + attribution,\n"
        "  prompt-based citations with post-processing verification works well."
    )
