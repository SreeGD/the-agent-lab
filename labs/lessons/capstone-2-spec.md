# Project Specification
## Capstone 2 — Autonomous Financial Research Agent

**Course:** AgenticCourse — Enterprise AI Architecture
**Phase:** Capstone (after L28 + Advanced RAG modules)
**Estimated effort:** 10–14 hours
**Prerequisite:** Capstone 1, L13 (Reflection), L14 (Multi-agent), L21 (HITL), L23 (GraphRAG), L24 (Corrective RAG)

---

## 1. Problem Statement

First-pass investment research — pulling filings, scanning news, benchmarking competitors, scoring risks, and synthesising a memo — takes a skilled analyst 4–6 hours per company. The work is largely mechanical: locate data, extract numbers, compare against benchmarks, flag deviations, structure a narrative. It is exactly the kind of structured, multi-source, multi-step task where autonomous agents can compress hours into minutes.

The challenge is not capability — it is trust. Financial research that cannot cite its sources is worse than useless; it is a liability. Every claim must be traceable. Every number must have a provenance. The output must survive a compliance officer's scrutiny.

This project builds an autonomous research pipeline that meets both requirements: fast enough to be useful, verifiable enough to be trusted.

---

## 2. What You Are Building

A CLI tool that accepts a company name and reporting period, autonomously fans out to four parallel research agents, synthesises their findings through a critic and a writer, requests human approval, and produces a structured investment memo PDF with full source citations and a cost report.

```
$ python main.py "TataMotors" "Q4-2025"

[orchestrator]  launching 4 parallel agents...
[filing]        fetched 142 pages → 847 chunks → GraphRAG index built  (18s)
[news]          12 articles → sentiment=NEUTRAL (score: 0.41)           (6s)
[competitors]   M&M, Maruti, Hyundai India benchmarked                  (9s)
[risk]          8 risk factors extracted, top: EV transition margin drag
[fan-in]        ResearchBundle assembled  (22s total wall time)
[critic]        4 challenges raised, 2 confidence adjustments applied
[writer]        InvestmentMemo drafted — 9 sections, 34 citations

──────────────────────────────────────────────
SUMMARY: TataMotors Q4-2025
Thesis: Revenue +12% YoY on JLR recovery. Domestic CV under pressure.
Risk:   EV capex compressing near-term EBITDA (prob=4, impact=4).
Rec:    HOLD — await Q1 margin trajectory.
──────────────────────────────────────────────
Approve [A] / Revise [R] / Reject [X]: A

[pdf]    saved → output/TataMotors_Q4-2025_yopt_abc123.pdf
[audit]  34 citations logged → audit/TataMotors_Q4-2025.json
[cost]   total ₹36.50 ✓  (budget ₹50)
```

---

## 3. Core Architecture

```
CLI: python main.py "<company>" "<quarter>"
        │
        ▼
   Orchestrator
        │
        ├──────────────── FAN-OUT (parallel, asyncio.gather) ────────────────┐
        │                                                                     │
   Filing Agent      News Agent       Competitor Agent     Risk Agent
   ───────────────  ───────────────  ─────────────────    ────────────────
   fetch PDF        web_search       benchmark 3 peers    extract risk
   chunk + embed    90-day news      on 4 KPIs            factors from
   GraphRAG index   sentiment score  from public data     filing
        │                │                │                    │
        └────────────────┴────────────────┴────────────────────┘
                                    │
                            FAN-IN: ResearchBundle
                                    │
                                    ▼
                            Critic Agent
                            (challenges all claims, adjusts confidence)
                                    │
                                    ▼
                            Writer Agent
                            (9-section InvestmentMemo + citations)
                                    │
                                    ▼
                         Human Review Gate (terminal)
                         A = approve → PDF + audit log
                         R = revise  → writer reruns (max 2 loops)
                         X = reject  → discard, log reason
```

---

## 4. The Six Agents

| Agent | Input | Output | Key constraint |
|---|---|---|---|
| **Filing Agent** | Company name + quarter | GraphRAG index over filing | Must chunk at sentence boundary, not arbitrary length |
| **News Agent** | Company name + quarter | `NewsSummary(articles[], sentiment, themes[])` | Web search only — no hallucinated news |
| **Competitor Agent** | Company name | `CompetitorBenchmark(peers[], metrics[])` | Exactly 3 peers, exactly 4 KPIs, no estimated values without source |
| **Risk Agent** | Company name + quarter | `list[RiskFactor(name, prob, impact, mitigation)]` | Minimum 5 risks; prob and impact scored 1–5 each |
| **Critic Agent** | Full `ResearchBundle` | `CritiqueReport(challenges[], confidence_adjustments[])` | Minimum 3 non-trivial challenges; no generic filler |
| **Writer Agent** | `ResearchBundle` + `CritiqueReport` | `InvestmentMemo(sections[], citations[])` | Every factual claim tagged with source reference |

---

## 5. Functional Requirements

### 5.1 Research Agents

| ID | Requirement |
|---|---|
| F-01 | All four research agents (Filing, News, Competitor, Risk) must run in parallel using `asyncio.gather`. Total fan-out wall time must be less than the sum of sequential times. |
| F-02 | Filing Agent uses GraphRAG: entities (company, product line, executive, KPI) are extracted and indexed as a graph. Entity-aware queries must outperform dense-only retrieval on 3 held-out queries. |
| F-03 | Filing Agent implements Corrective RAG: if retrieval confidence < 0.6, it re-fetches with a rewritten query before returning results. |
| F-04 | News Agent uses `web_search` tool only. It must not fabricate article headlines or dates. Source URL must be included for every article. |
| F-05 | Competitor Agent populates all cells in the comparison table (3 peers × 4 KPIs). If a value cannot be found, it must explicitly state `"not available"` — not leave the cell empty or guess. |
| F-06 | Risk Agent extracts a minimum of 5 risk factors from the filing. Each risk must include `probability` (1–5) and `impact` (1–5) as integers, not text descriptions. |

### 5.2 Critic Agent

| ID | Requirement |
|---|---|
| F-07 | Critic receives the full `ResearchBundle` and returns a minimum of 3 specific, non-trivial challenges. A challenge is trivial if it would apply to any company in any quarter (e.g., "macroeconomic uncertainty"). |
| F-08 | Critic may adjust confidence on specific claims in the ResearchBundle. Adjustments must reference the specific claim being modified. |
| F-09 | Writer must incorporate Critic's challenges — the final memo must acknowledge the bear case, not ignore it. |

### 5.3 Writer Agent and Memo Structure

| ID | Requirement |
|---|---|
| F-10 | Writer produces all 9 memo sections: Executive Summary, Company Overview, Q-period Highlights, News & Sentiment, Competitor Benchmarking, Risk Register, Devil's Advocate, Investment Thesis, Source Citations. |
| F-11 | Every factual claim carries an inline citation tag in format `[Filing §3.2]` or `[News: ET 2025-04-12]`. |
| F-12 | Source Citations section lists every source referenced in the memo with URL or document section identifier. |
| F-13 | Executive Summary is exactly 3 bullet points: thesis, key risk, recommendation. No more, no less. |

### 5.4 Human Review Gate

| ID | Requirement |
|---|---|
| F-14 | Before PDF is saved, the terminal displays: 3-sentence summary, top 2 risks (name + prob × impact score). |
| F-15 | User inputs `A` (approve), `R` (revise), or `X` (reject). Any other input re-prompts. |
| F-16 | On `R`: Writer reruns incorporating terminal feedback typed by user. Maximum 2 revision loops. |
| F-17 | On `X`: PDF is not saved. Rejection reason (user-typed) is logged to audit file. |

### 5.5 Output and Audit

| ID | Requirement |
|---|---|
| F-18 | Approved memo is saved as PDF to `output/<company>_<quarter>_<id>.pdf`. |
| F-19 | Citation audit log is saved as JSON to `audit/<company>_<quarter>.json`. Format: `[{claim, source, url, confidence}]`. |
| F-20 | Cost report is printed at session end: token spend per agent, total, vs. ₹50 budget. |
| F-21 | Total run cost must not exceed ₹50. If budget is exceeded during execution, the pipeline aborts with a clear message. |

---

## 6. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NF-01 | **Fan-out is genuinely parallel.** Filing, News, Competitor, Risk agents must run concurrently. Sequential execution that happens to call four functions in order does not satisfy this requirement. |
| NF-02 | **No hallucinated citations.** Every source in the citation log must be a real URL or a real document section. Manual spot-check of 5 random citations must all resolve. |
| NF-03 | **GraphRAG outperforms dense-only.** On 3 entity-specific queries (e.g., "What did the CEO say about EV strategy?"), GraphRAG must return more relevant results than a standard vector similarity search. Demonstrate with side-by-side output. |
| NF-04 | **Cost hard cap enforced.** The pipeline must abort if cumulative token spend exceeds ₹50. The check must run between agents, not only at the end. |
| NF-05 | **Revision loop is bounded.** Writer revision loops are capped at 2. A third revision request returns an error, not an infinite loop. |
| NF-06 | **PDF opens cleanly.** No broken fonts, no missing sections, no overflow text outside page margins. |

---

## 7. Technical Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Concurrency | `asyncio` + `asyncio.gather` | Fan-out parallelism |
| LLM | Anthropic Claude | claude-haiku-4-5 for cheap agents; claude-sonnet-4-6 for Critic + Writer |
| RAG | Custom (sentence-transformers + in-memory) | GraphRAG over filing entities |
| Web search | `web_search` tool (Anthropic) or `tavily-python` | News Agent only |
| PDF generation | `fpdf2` | Reuse patterns from agritech yield optimizer |
| Data validation | `pydantic` | All agent outputs are typed Pydantic models |

---

## 8. Data Models

```python
class RiskFactor(BaseModel):
    name: str
    description: str
    probability: int          # 1-5
    impact: int               # 1-5
    mitigation: str

class NewsSummary(BaseModel):
    articles: list[NewsArticle]
    overall_sentiment: float  # -1.0 to 1.0
    key_themes: list[str]

class ResearchBundle(BaseModel):
    filing_summary: str
    news: NewsSummary
    competitor_benchmark: CompetitorBenchmark
    risk_factors: list[RiskFactor]

class CritiqueReport(BaseModel):
    challenges: list[str]           # min 3, non-trivial
    confidence_adjustments: list[ConfidenceAdjustment]

class InvestmentMemo(BaseModel):
    sections: dict[str, str]        # section_name → content
    citations: list[Citation]       # all sources cited

class Citation(BaseModel):
    claim: str
    source: str
    url: str | None
    document_section: str | None
    confidence: float
```

---

## 9. Repository Structure

```
capstone2/
├── main.py                  # CLI entrypoint
├── orchestrator.py          # Fan-out coordinator
├── agents/
│   ├── filing_agent.py      # GraphRAG + Corrective RAG
│   ├── news_agent.py        # Web search + sentiment
│   ├── competitor_agent.py  # Peer benchmarking
│   ├── risk_agent.py        # Risk factor extraction
│   ├── critic_agent.py      # Devil's advocate
│   └── writer_agent.py      # Memo synthesis
├── rag/
│   ├── graph_rag.py         # Entity extraction + graph index
│   └── corrective.py        # Re-fetch on low confidence
├── models.py                # Pydantic data models
├── hitl.py                  # Human review gate
├── pdf_report.py            # FPDF2 memo renderer
├── audit.py                 # Citation log persistence
├── cost_tracker.py          # Per-agent token + cost tracking
└── tests/
    ├── test_agents.py
    ├── test_graph_rag.py
    └── test_citations.py
```

---

## 10. Deliverables

| # | Deliverable | Format |
|---|---|---|
| D-01 | Working CLI | `python main.py "TataMotors" "Q4-2025"` runs end-to-end |
| D-02 | Investment memo PDF | All 9 sections present, citations tagged inline |
| D-03 | Citation audit log | JSON file with ≥10 entries, all sources real |
| D-04 | GraphRAG comparison | Side-by-side output: same 3 queries on GraphRAG vs. dense-only |
| D-05 | Cost report | Printed at session end; total ≤ ₹50 |
| D-06 | Parallelism proof | Log timestamps showing fan-out agents overlapping (not sequential) |
| D-07 | Architecture Decision Record | 1 page, 4 questions answered |

---

## 11. Grading Rubric

| Area | Points | Pass criteria |
|---|---|---|
| **Fan-out parallelism (F-01, NF-01)** | 15 | Agents genuinely concurrent; timestamp proof provided |
| **GraphRAG quality (F-02, NF-03)** | 15 | Entity-aware retrieval; outperforms dense-only on 3 queries |
| **Memo completeness (F-10 to F-13)** | 20 | All 9 sections; executive summary exactly 3 bullets; inline citation tags |
| **Citation integrity (F-11, F-12, NF-02)** | 15 | No hallucinated sources; 5 random citations spot-checked and valid |
| **Critic challenges (F-07 to F-09)** | 10 | ≥3 non-trivial challenges; bear case present in final memo |
| **HITL flow (F-14 to F-17)** | 10 | Terminal prompt shows summary + risks; A/R/X all work; revision capped at 2 |
| **Cost control (F-20, F-21, NF-04)** | 10 | Per-agent cost logged; hard cap enforced mid-run |
| **PDF output (NF-06)** | 5 | Opens cleanly; no broken layout |

**Total: 100 points. Pass: 75+**

---

## 12. Architecture Decision Record — Required Questions

1. **Fan-out vs. sequential:** You run four research agents in parallel. What is the failure mode if the News Agent times out after 30 seconds while the other three complete in 10 seconds? How would you handle partial results gracefully?

2. **Critic placement:** The Critic runs after the fan-in, not as a fifth parallel agent during fan-out. What would break if the Critic ran in parallel with the research agents?

3. **Reproducibility:** A compliance officer asks: *"If I run this pipeline twice on the same company and quarter, will I get the same memo?"* What is your honest answer, and what would you need to change to make the output deterministic?

4. **Citation hallucination prevention:** Your Researcher returns citations with confidence scores. What technical mechanism prevents a citation from being included in the final memo if its source URL does not actually exist or does not contain the claimed information?

---

## 13. Submission Checklist

- [ ] `python main.py "TataMotors" "Q4-2025"` (or another public company) completes end-to-end
- [ ] PDF opens and contains all 9 sections with inline citation tags
- [ ] Citation audit JSON has ≥10 entries; manually verify 5 are real
- [ ] Fan-out log shows overlapping timestamps (filing, news, competitors, risk running concurrently)
- [ ] GraphRAG comparison document shows entity-aware retrieval outperforming dense-only
- [ ] Cost report shows per-agent breakdown; total ≤ ₹50
- [ ] Revision loop works: type `R` at HITL prompt, provide feedback, see revised memo
- [ ] Rejection works: type `X`, PDF not saved, rejection reason in audit log
- [ ] ADR answers all 4 questions with specific technical reasoning

---

*This spec defines the contract between student and evaluator. Implementation choices not specified here are at the student's discretion provided all functional and non-functional requirements are met.*
