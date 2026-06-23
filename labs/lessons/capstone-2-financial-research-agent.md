# Capstone 2 — Autonomous Financial Research Agent

> **Product-grade autonomous research pipeline.** Six specialized agents fan out in parallel — filing retrieval, news analysis, competitor benchmarking, risk extraction, devil's advocate critique, and report writing — producing an auditable investment memo PDF with full source citations and a reproducible cost report.

---

## Roadmap — where this sits

```
Phase 1 (L01-11)   Phase 2 (L12-21)   Phase 3 (L22-28)   Enterprise Hardening
Foundation          Agentic Patterns    Advanced RAG        IAM + Model Routing

                                                           ○ Capstone 1
                                                           ▶ CAPSTONE 2  ◄ YOU ARE HERE
```

**Why this capstone:** Capstone 1 was reactive (ticket arrives → system responds). Capstone 2 is autonomous — a single prompt triggers a multi-agent research pipeline that runs for minutes, coordinates parallel workstreams, critiques its own output, and produces a structured deliverable. This is the hardest agentic pattern to get right.

---

## Scenario

An investment analyst wants a first-pass research memo on any listed company in under 5 minutes — pulling from regulatory filings, news, and competitor data — that a human can review, annotate, and approve before distribution. The memo must cite every claim, flag every risk, and cost less than ₹50 per run.

**Your job:** Build `research <company> <quarter>` → investment memo PDF.

---

## Files you will create

| File | Role |
|---|---|
| `capstone2/main.py` | CLI entrypoint — `research <company> <quarter>` |
| `capstone2/orchestrator.py` | Fan-out coordinator — launches 4 parallel agents, collects results |
| `capstone2/agents/filing_agent.py` | Fetch + chunk + embed annual report / 10-K equivalent |
| `capstone2/agents/news_agent.py` | Web search last 90 days, sentiment scoring |
| `capstone2/agents/competitor_agent.py` | Benchmark 3 peers on KPIs from public data |
| `capstone2/agents/risk_agent.py` | Extract risk factors, score probability + impact |
| `capstone2/agents/critic_agent.py` | Devil's advocate — challenge all findings |
| `capstone2/agents/writer_agent.py` | Synthesise into structured memo, produce PDF |
| `capstone2/rag/graph_rag.py` | GraphRAG over filing entities (company, product, exec, metric) |
| `capstone2/rag/corrective.py` | Corrective RAG — re-fetch if retrieval confidence < threshold |
| `capstone2/audit.py` | Source citation log + agent decision trace |
| `capstone2/cost_tracker.py` | Token spend per agent per run |
| `capstone2/pdf_report.py` | FPDF2 report renderer |
| `capstone2/hitl.py` | Human review gate — CLI prompt before final PDF save |

---

## Architecture

```
CLI: research "TataMotors" "Q4-2025"
        │
        ▼
   Orchestrator
        │
        ├─────────────────────────────────────────────────┐
        │                    FAN-OUT (parallel)           │
        ▼                ▼              ▼             ▼   │
  Filing Agent    News Agent    Competitor Agent  Risk Agent
  ─────────────  ──────────    ───────────────   ──────────
  fetch filing   web_search    benchmark 3       extract
  chunk + embed  90-day news   peers on KPIs     risk factors
  GraphRAG idx   sentiment     from public data  score prob+impact
        │                ▼              ▼             ▼
        │           FAN-IN: Orchestrator merges ResearchBundle
        │
        ▼
   Critic Agent  (devil's advocate — challenges every claim)
        │   returns CritiqueReport(challenges[], confidence_adjustments[])
        ▼
   Writer Agent  (claude-sonnet — highest quality needed here)
        │   synthesises bundle + critique → InvestmentMemo(sections[], citations[])
        ▼
   Human Review Gate
        │   show summary + key risks in terminal
        │   analyst: [A]pprove / [R]evise / [R]eject
        │
        ├── Approve ──► render PDF ──► save + open
        ├── Revise  ──► writer_agent reruns with feedback (max 2 loops)
        └── Reject  ──► discard, log reason

Audit log: every source URL, every chunk used, every agent decision.
Cost report: token spend per agent, total per run.
```

---

## What each lesson shows up as

| In this capstone | From lesson |
|---|---|
| Fan-out parallel execution of 4 agents | L06 Parallel chains |
| `create_react_agent` with tools per agent | L03 |
| `cache_control` on shared system context (company profile) | L04 |
| `with_structured_output` for memo sections | L05 |
| GraphRAG over filing entities and relationships | L23 |
| Corrective RAG — re-fetch filing sections on low confidence | L24 |
| Reflection + critique loop (Critic Agent) | L13 |
| Multi-agent supervisor orchestrating fan-out/fan-in | L14 |
| Human-in-the-loop review before PDF save | L21 |
| FPDF2 PDF generation with citations | L20 + agritech engine |
| LangSmith trace for entire pipeline per run | L28 |
| Token budget per run (hard cap ₹50) | L26 |
| Evaluation harness — compare memo quality across companies | L25 |
| Source citation audit log | IAM module |

---

## The memo structure (Writer Agent output)

```
1. Executive Summary        (3 bullets — thesis, key risk, recommendation)
2. Company Overview         (from filing — revenue, segments, geography)
3. Q4 Financial Highlights  (from filing — revenue, EBITDA, PAT vs PY)
4. News & Sentiment         (from news agent — major events, sentiment score)
5. Competitor Benchmarking  (from competitor agent — table: 4 metrics × 4 companies)
6. Risk Register            (from risk agent — probability × impact matrix)
7. Devil's Advocate         (from critic agent — 3 strongest counter-arguments)
8. Investment Thesis        (writer synthesis — bull case, bear case, base case)
9. Source Citations         (every claim linked to source URL or filing section)
```

---

## Step-by-step build sequence

### Step 1 — Data layer
- Filing Agent: fetch a public annual report PDF (e.g., TataMotors FY25 from NSE)
- Chunk + embed using sentence-transformers
- Build GraphRAG index: extract entities (company, product lines, exec names, KPI values)
- Test: 10 queries against the graph — verify entity-aware retrieval beats dense-only

### Step 2 — News Agent
- `web_search` tool: `"{company} Q4 2025 news"` → top 10 results
- Per-article: extract headline, date, sentiment (positive/negative/neutral), relevance score
- Aggregate into `NewsSummary(articles[], overall_sentiment, key_themes[])`
- Test: verify sentiment scores correlate with article content (spot-check 5)

### Step 3 — Competitor Agent
- Identify 3 peers (hardcoded for now — e.g., M&M, Maruti, Hyundai India)
- For each peer: `web_search` latest revenue, EBITDA margin, market cap, EV/EBITDA
- Build comparison table as `CompetitorBenchmark(peers[], metrics[])`
- Test: verify all 4 companies × 4 metrics populated; no hallucinated numbers

### Step 4 — Risk Agent
- Use GraphRAG to extract all risk-factor sections from the filing
- For each risk: `RiskFactor(name, description, probability, impact, mitigation)`
- Score probability (1-5) and impact (1-5) using structured output
- Test: verify ≥ 5 risks extracted; probability × impact scores are defensible

### Step 5 — Critic Agent
- Input: full `ResearchBundle` from steps 1-4
- Output: `CritiqueReport(challenges[], confidence_adjustments[], missing_context[])`
- Prompt: *"You are a skeptical analyst. Challenge every major claim. Identify what data is missing."*
- Test: critic must identify ≥ 3 non-trivial challenges for any real company

### Step 6 — Writer Agent + PDF
- Input: `ResearchBundle` + `CritiqueReport`
- Output: `InvestmentMemo` with all 9 sections + citations list
- Render to PDF using FPDF2 (reuse patterns from agritech yield optimizer engine)
- Every factual claim tagged with source: `[Filing §3.2]` or `[News: ET 2025-04-12]`
- Test: PDF opens cleanly, all citations resolve, no section is empty

### Step 7 — Orchestrator + fan-out
```python
async def run_research(company: str, quarter: str) -> ResearchBundle:
    filing, news, competitors, risks = await asyncio.gather(
        filing_agent.run(company, quarter),
        news_agent.run(company, quarter),
        competitor_agent.run(company),
        risk_agent.run(company, quarter),
    )
    return ResearchBundle(filing=filing, news=news, competitors=competitors, risks=risks)
```
- Test: all 4 agents complete; total wall time < 60s for real run

### Step 8 — HITL + cost report
- After writer produces memo: print 3-sentence summary + top 2 risks to terminal
- Analyst types A / R / X (approve / revise / reject)
- On approve: save PDF + print cost report
- Cost report format:
  ```
  Agent             Tokens in   Tokens out   Cost (₹)
  ─────────────────────────────────────────────────
  filing_agent      12,400      820          ₹8.20
  news_agent         3,100      440          ₹2.60
  competitor_agent   2,800      390          ₹2.40
  risk_agent         4,200      610          ₹3.80
  critic_agent       8,900      720          ₹6.10
  writer_agent      14,200     2,100         ₹13.40
  ─────────────────────────────────────────────────
  TOTAL             45,600     5,080         ₹36.50  ✓ under ₹50 budget
  ```

---

## Run it

```bash
cd capstone2
python main.py "TataMotors" "Q4-2025"
```

Expected terminal output:
```
[orchestrator]  launching 4 parallel agents...
[filing]        fetched 142 pages → 847 chunks → GraphRAG index built (18s)
[news]          12 articles found → sentiment=NEUTRAL (score: 0.41) (6s)
[competitors]   M&M, Maruti, Hyundai India benchmarked (9s)
[risk]          8 risk factors extracted → top risk: EV transition margin compression
[fan-in]        ResearchBundle assembled (22s total wall time)
[critic]        4 challenges raised → confidence adjusted on 2 claims
[writer]        InvestmentMemo drafted → 9 sections, 34 citations
─────────────────────────────────────────────────────────────────
SUMMARY: TataMotors Q4-2025

Thesis: Revenue grew 12% YoY driven by JLR recovery. Domestic CV segment under pressure.
Risk: EV investment cycle compressing near-term EBITDA (prob=4, impact=4).
Recommendation: HOLD — await Q1 margin trajectory before adding.

Top risks: [1] EV capex drag  [2] JLR supply chain exposure

Approve [A] / Revise [R] / Reject [X]: A

[pdf]    saved → capstone2/output/TataMotors_Q4-2025_yopt_abc123.pdf
[audit]  34 citations logged → capstone2/audit/TataMotors_Q4-2025.json
[cost]   total ₹36.50 ✓ (budget ₹50)
```

---

## Grading rubric

| Area | Points | Criteria |
|---|---|---|
| **Fan-out correctness** | 15 | All 4 agents run in parallel; fan-in merges correctly; no data loss |
| **GraphRAG quality** | 15 | Entity-aware retrieval beats dense-only on 5 held-out queries |
| **Memo completeness** | 20 | All 9 sections present; no section is a placeholder or empty |
| **Citation integrity** | 15 | Every factual claim has a traceable source; spot-check 10 claims manually |
| **Critic challenge quality** | 10 | ≥ 3 non-trivial challenges per run; not generic filler |
| **HITL flow** | 10 | Revision loop works; reject discards PDF; approve saves with cost report |
| **Cost control** | 10 | Total run cost under ₹50; model routing correct (haiku for cheap tasks) |
| **PDF output** | 5 | Opens cleanly; readable formatting; citation list at end |

**Total: 100 points. Pass: 75+**

---

## Architecture Decision Record (deliverable)

Write a 1-page ADR answering:
1. Why fan-out for the 4 research agents rather than sequential? What is the failure mode if one agent times out?
2. Why does the Critic Agent run after fan-in rather than as a 5th parallel agent?
3. How would you make this pipeline reproducible — same inputs always produce the same memo?
4. What additional data source would most improve memo quality and how would you integrate it?

---

## Extension challenges

| Challenge | What you learn |
|---|---|
| Add a `FactCheck Agent` that verifies numbers against a live market data API | Tool use + external API integration |
| Store all memos in a vector DB; add `compare <company1> <company2>` command | Long-term memory + multi-doc RAG |
| Add email delivery via Gmail MCP server | MCP server integration |
| Build evaluation harness: run 5 companies, score memos with LLM-as-judge | L25 Evaluation at scale |
| Add streaming progress updates via SSE | L27 Streaming |

---

## Mental model in one line

> **Autonomous research agents are not about replacing analysts — they are about compressing the 4-hour first-pass research cycle to 5 minutes so analysts can spend their time on judgment, not data gathering.**

---

## Related

- **Previous:** Capstone 1 — Enterprise Support Intelligence Platform
- **Core dependencies:** L13 Reflection, L14 Multi-agent, L21 HITL, L23 GraphRAG, L24 Corrective RAG, L28 Observability
- **Reference:** agritech/yield_optimizer_engine.py — PDF generation patterns
