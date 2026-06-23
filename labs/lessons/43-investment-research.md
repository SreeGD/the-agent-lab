# 43 — Case Study: Investment Research Assistant (Session 30)

> **Build a compliance-grade investment research assistant** — financial document RAG with Citations API, batch processing for earnings seasons, and faithfulness scoring that satisfies a securities regulator's disclosure requirements.

---

## Roadmap — where this lesson sits

```
═══════ TRACK J: FINANCE ═══════

  ✓ Session 28: FinTech AI Landscape & Regulation
  ✓ Session 29: Reference Arch — Fraud + Customer Support
  ▶ Session 30: CASE STUDY — INVESTMENT RESEARCH  ◄ HERE
```

---

## Files involved

| File | Role |
|---|---|
| `fintech/investment_research/ingestion.py` | SEC filing + earnings transcript ingestion |
| `fintech/investment_research/research_agent.py` | Research query pipeline with citations |
| `fintech/investment_research/batch_processor.py` | Earnings season batch processing |
| `fintech/investment_research/compliance.py` | MiFID II / SEBI disclosure generation |

---

## What we build

An internal tool for equity research analysts that:
1. Ingests SEC filings (10-K, 10-Q, 8-K) and earnings call transcripts
2. Answers research questions grounded in those documents with citations
3. Processes a full earnings season (hundreds of filings) in batch
4. Produces MiFID II-compliant research notes with AI disclosure

This is an **internal analyst tool**, not retail investment advice — an important compliance distinction.

---

## Financial document ingestion

```python
import httpx
from pathlib import Path
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

async def fetch_sec_filing(ticker: str, form_type: str = "10-K") -> bytes:
    """Fetch latest filing from SEC EDGAR."""
    # EDGAR full-text search API
    search_url = "https://efts.sec.gov/LATEST/search-index?q={ticker}&dateRange=custom&startdt=2024-01-01&forms={form_type}"
    r = await httpx.AsyncClient().get(
        search_url.format(ticker=ticker, form_type=form_type)
    )
    filings = r.json()["hits"]["hits"]
    if not filings:
        raise ValueError(f"No {form_type} found for {ticker}")

    filing_url = filings[0]["_source"]["file_date"]  # simplified
    doc = await httpx.AsyncClient().get(filing_url)
    return doc.content

def extract_financial_sections(filing_bytes: bytes) -> dict[str, str]:
    """Extract key sections from 10-K using Claude's native PDF understanding."""
    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=4096)
    response = llm.invoke([
        HumanMessage(content=[
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf",
                           "data": base64.b64encode(filing_bytes).decode()},
            },
            {
                "type": "text",
                "text": (
                    "Extract these sections as JSON: "
                    "{risk_factors, management_discussion, financial_highlights, "
                    "business_overview, forward_looking_statements}"
                ),
            },
        ])
    ])
    return json.loads(response.content)
```

---

## Research RAG with Citations API

```python
from anthropic import Anthropic

client = Anthropic()

RESEARCH_SYSTEM = """You are an equity research assistant for institutional analysts.

Rules:
- Answer ONLY from the provided financial documents
- Every quantitative claim must cite the specific document and section
- Flag forward-looking statements explicitly
- Distinguish between management statements and verified financials
- Never provide investment recommendations (buy/sell/hold)
- End factual summaries with: "This analysis is based on [document names]. 
  It does not constitute investment advice."
"""

def research_query(
    query: str,
    documents: list[dict],  # [{"title": "AAPL 10-K 2024", "content": "..."}]
) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=RESEARCH_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                # Documents as source blocks for Citations API
                *[{
                    "type": "document",
                    "source": {"type": "text", "media_type": "text/plain",
                               "data": doc["content"]},
                    "title": doc["title"],
                    "citations": {"enabled": True},
                } for doc in documents],
                {"type": "text", "text": query},
            ],
        }],
    )

    # Extract text + citations from response
    answer_text = ""
    citations = []
    for block in response.content:
        if block.type == "text":
            answer_text += block.text
        elif hasattr(block, "citations"):
            citations.extend(block.citations)

    return {"answer": answer_text, "citations": citations}
```

---

## Batch processing for earnings season

Earnings season = 500+ companies report in 3 weeks. Process asynchronously:

```python
import asyncio
from anthropic import AsyncAnthropic

client = AsyncAnthropic()

async def process_earnings_transcript(ticker: str, transcript: str) -> dict:
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",  # cheap for batch extraction
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                f"Extract from this earnings call transcript for {ticker}:\n"
                "1. Revenue guidance (next quarter)\n"
                "2. Key risks mentioned by management\n"
                "3. Notable analyst questions\n"
                "4. Sentiment: bullish/neutral/bearish\n\n"
                f"{transcript[:8000]}"
            ),
        }],
    )
    return {"ticker": ticker, "summary": response.content[0].text}

async def batch_process_earnings(tickers: list[str]) -> list[dict]:
    """Process up to 50 earnings simultaneously."""
    transcripts = {t: await fetch_earnings_transcript(t) for t in tickers}

    # Anthropic Batches API for large volumes (> 100 requests)
    # See Session 9 (Files & Document AI) for Batches API pattern
    tasks = [
        process_earnings_transcript(ticker, transcript)
        for ticker, transcript in transcripts.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]
```

**Cost advantage of batch processing:**
- Anthropic Batches API: 50% discount on input tokens
- Earnings season: 500 transcripts × 8k tokens = 4M tokens
- Cost with Haiku + batch: ~$0.25 (vs. ~$6.00 with Sonnet real-time)

---

## Faithfulness scoring

For regulated research outputs, measure faithfulness automatically:

```python
from ragas.metrics import faithfulness
from ragas import evaluate
from datasets import Dataset

def score_research_faithfulness(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],  # retrieved document chunks per question
) -> float:
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
    })
    result = evaluate(dataset, metrics=[faithfulness])
    return result["faithfulness"]

# Target: > 0.90 for all research outputs
# Block publication if faithfulness < 0.85
```

---

## MiFID II compliance disclosure

EU regulations require disclosure when AI is used in investment research:

```python
MIFID_II_DISCLOSURE = """
IMPORTANT DISCLOSURE

This research note was prepared with the assistance of artificial intelligence 
(Claude, developed by Anthropic). The AI was used to analyse the following 
source documents: {document_list}.

The AI analysis was reviewed and approved by a registered research analyst: 
{analyst_name} (CFA/SEBI Registration: {registration_id}).

This research note constitutes investment research under MiFID II. It has been 
prepared in accordance with legal requirements designed to promote the independence 
of investment research and is not subject to any prohibition on dealing ahead of 
the dissemination of investment research.

Date: {date}
"""

def generate_compliant_note(
    research_content: str,
    documents_used: list[str],
    analyst_name: str,
    registration_id: str,
) -> str:
    disclosure = MIFID_II_DISCLOSURE.format(
        document_list=", ".join(documents_used),
        analyst_name=analyst_name,
        registration_id=registration_id,
        date=date.today().isoformat(),
    )
    return f"{research_content}\n\n---\n{disclosure}"
```

---

## Try this

1. **SEC filing ingestion** — use EDGAR's free API to fetch a real 10-K (e.g., Apple's). Extract the MD&A section using Claude's native PDF understanding. Compare the extraction quality to manual reading.

2. **Citations accuracy** — ask 5 specific factual questions about a financial filing. Run through the Citations API pipeline. Verify every citation points to the correct document and section.

3. **Earnings batch** — collect 10 earnings call transcripts from Seeking Alpha or similar. Batch-process them with Haiku. Build a summary table: revenue guidance, sentiment, key risks. Measure cost per transcript.

4. **Faithfulness scoring** — generate 20 research answers (some well-grounded, some with hallucinated numbers). Run Ragas faithfulness. What score threshold would catch the hallucinated answers?

5. **Compliance note** — take a research analysis you generated. Add the MiFID II disclosure. Review: does it satisfy the key requirements (AI disclosure, human analyst sign-off, document list, date)?

---

## Mental model in one line

> **A compliance-grade investment research assistant is financial document RAG + Citations API (every claim cited to source) + batch processing for earnings season (Haiku + Batches API for cost) + faithfulness scoring (> 0.90 or block publication) + regulatory disclosure (MiFID II / SEBI) — the human analyst reviews and signs off before any note is distributed.**

---

## Related

- **Previous:** [Session 29 — Reference Arch: Fraud + Customer Support](42-fraud-support.md)
- **Next:** [Session 31 — Domain & Content Strategy (Vidya Karana)](44-vidya-karana-domain.md)
- **Citations API:** [Session 9 — Files & Document AI](20-files-document-ai.md)
- **Faithfulness scoring:** [Session 14 — Evaluation](25-evaluation.md)
- **Batch processing:** [Session 15 — Cost Optimization](26-cost-optimization.md)
- **Curriculum tracker:** Session 30 of 46 — Track J capstone
