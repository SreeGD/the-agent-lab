# AgenticCourse Curriculum — Full Plan

**36 sessions • ~72 hours • 12 weeks**
Time budget: 1 hour Mon-Fri + 2 hours Sat-Sun = 9 hours/week

The accompanying spreadsheet is `CURRICULUM.csv` — open in Excel / Google Sheets / Numbers.

---

## Phase summary

| Phase | Sessions | Hours | Weeks | Focus |
|---|---|---|---|---|
| **1 — Technical Foundation** | 1-17 | 34 | 1-5 | Every primitive needed for agentic AI |
| **2 — Architect Skills** | 18-20 | 6 | 6 | Judgement, security, product thinking |
| **3 — Vertical Deep Dives** | 21-36 | 32 | 7-12 | Healthcare, Agriculture, Finance, Vidya Karana, Family AI |

---

## Track breakdown

| Track | Sessions | Count | Theme |
|---|---|---|---|
| A — Agentic Patterns | 1, 2, 3 | 3 | MCP, Reflection/PE, Multi-agent, LTM |
| B — Workflow & Skill | 4, 5, 6 | 3 | SDD, Vibe Coding, Claude Skills |
| C — Alt Architectures | 7, 8 | 2 | Anthropic SDK direct, **AI Gateway (NEW)** |
| D — Data & Multi-modal | 9 | 1 | Files, Vision, Citations, Batches, **multimodal RAG** |
| E — Graph Depth | 10 | 1 | Custom LangGraph + HITL |
| **E.5 — RAG Architectures (NEW)** | 11, 12, 13 | 3 | **Hybrid RAG, GraphRAG, Corrective RAG** |
| F — Production | 14, 15, 16, 17 | 4 | Eval, Cost Optimization, Streaming, Deploy + Observability |
| G — Architect Skills | 18, 19, 20 | 3 | System Design Interview, Red-teaming, AI UX |
| H — Healthcare | 21, 22, 23 | 3 | Landscape, CDS Architecture, HIPAA Chatbot |
| I — Agriculture | 24, 25, 26 | 3 | Landscape, Crop Diagnostic, Farmer Bot |
| J — Finance | 27, 28, 29 | 3 | Landscape, Fraud + Support, Investment Research |
| K — Vidya Karana | 30, 31, 32 | 3 | Wellness + Yoga + Applied Vedic Wisdom |
| L — Family AI Agent | 33, 34, 35, 36 | 4 | Multi-generational, multi-channel, multi-specialist |

---

## What's new in this revision

Per gap analysis against Brij Kishore Pandey's "9 AI Concepts" and "Top 5 RAG Architectures" infographics:

**Newly added (4 sessions):**

| New Session | Why added |
|---|---|
| **08 — AI Gateway** | Brij concept #04 (one control plane, many models) — LiteLLM / OpenRouter / Vercel AI Gateway |
| **11 — Hybrid RAG** | Brij RAG #1 — dense + BM25 sparse + Reciprocal Rank Fusion (15-30% retrieval-quality improvement) |
| **12 — GraphRAG** | Brij RAG #2 — entity extraction + knowledge graph + subgraph retrieval |
| **13 — Corrective RAG (CRAG)** | Brij RAG #4 — retrieval-grader + query rewriter + web-search fallback |

**Scope-expanded:**

| Session | What changed |
|---|---|
| **09 — Files & Document AI** | Added CLIP/ColPali unified multimodal embedding for Brij RAG #5 |
| **17 — Production Deployment** | Folded in observability (Brij concept #08) |

Most concepts from both infographics now have explicit curriculum coverage. See coverage matrix in [NOTES.md](./NOTES.md) for the full mapping.

---

## Calendar (12 weeks)

| Week | Sessions | Hours | Theme |
|---|---|---|---|
| 1 | 1, 2, 3 | 6 | Agentic patterns (MCP → Reflection/PE → Multi-agent+LTM) |
| 2 | 4, 5, 6 | 6 | Workflow & skills (SDD → Vibe → Claude Skills) |
| 3 | 7, 8, 9 | 6 | Alt arch (SDK direct + Gateway) + Data/multi-modal |
| 4 | 10, 11, 12, 13 | 8 | Custom Graph + **RAG architectures (Hybrid → GraphRAG → CRAG)** |
| 5 | 14, 15, 16, 17 | 8 | Production (Eval → Cost → Streaming → Deploy+Observability) |
| 6 | 18, 19, 20 | 6 | Architect skills (Interview → Red-team → Product) |
| 7 | 21, 22, 23 | 6 | **Healthcare** deep dive |
| 8 | 24, 25, 26 | 6 | **Agriculture** deep dive |
| 9 | 27, 28, 29 | 6 | **Finance** deep dive |
| 10 | 30, 31, 32 | 6 | **Vidya Karana** (Wellness + Yoga + Vedic) deep dive |
| 11 | 33, 34 | 4 | **Family AI** — landscape + meal/archivist |
| 12 | 35, 36 | 4 | **Family AI** — scheduler/proactive + capstone build |

---

## Coverage vs. external benchmarks

### Brij's "9 AI Concepts That Put You Ahead of 99% in 2026"

| # | Concept | Where |
|---|---|---|
| 01 | Agentic Loops (Plan/Act/Observe/Reflect) | Lessons 03, 13 ✓ |
| 02 | MCP | Lesson 12 ✓ |
| 03 | Subagents & Multi-Agent Systems | Lesson 14 ✓ |
| 04 | **AI Gateway** | **Session 8 (NEW)** |
| 05 | Inference Economics | Lesson 04 ✓ |
| 06 | Evals | Session 14 (planned) |
| 07 | Guardrails | Lesson 10 ✓ |
| 08 | Observability | Session 17 (planned) |
| 09 | The Bitter Lesson | Mindset — research-literacy track |

### Brij's "Top 5 RAG Architectures"

| # | Architecture | Where |
|---|---|---|
| 01 | **Hybrid RAG** | **Session 11 (NEW)** |
| 02 | **GraphRAG** | **Session 12 (NEW)** |
| 03 | Agentic RAG | Lessons 11, 14 ✓ |
| 04 | **Corrective RAG** | **Session 13 (NEW)** |
| 05 | **Multimodal RAG** | **Session 9 (expanded)** |

---

## How to use this

**Linear path (first time through):**
Sessions 1 → 36 in order. ~6 hours / week reading + ~6 hours / week running code. Total: ~72 hours over 12 weeks.

**Reference path (after first time):**
Land on individual lessons whenever you're picking a pattern. Each lesson's FAQ catches common confusions.

**Open-source path:**
- [`NOTES.md`](./NOTES.md) — index into lessons
- [`lessons/`](./lessons/) — per-topic walkthroughs
- [`LEARNINGS.md`](./LEARNINGS.md) — conceptual deep-dives
- [`CURRICULUM.csv`](./CURRICULUM.csv) — your live tracker

---

## File map

```
helloworld/
├── *.py                    ← runnable examples (one per lesson)
├── lessons/                ← per-topic markdown walkthroughs
│   ├── 01-model-wrapper.md
│   ├── ...
│   ├── 15-spec-driven-development.md
│   ├── reference-agentic-patterns.md
│   └── visual-summary.md
├── NOTES.md                ← index into lessons/
├── LEARNINGS.md            ← conceptual deep-dives
├── CURRICULUM.md           ← THIS file
├── CURRICULUM.csv          ← spreadsheet tracker
└── requirements.txt
```
