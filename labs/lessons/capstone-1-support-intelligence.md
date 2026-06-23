# Capstone 1 — Enterprise Support Intelligence Platform

> **Product-grade multi-agent system.** Triage + RAG + Research + Escalation agents with guardrails, HITL approval, IAM scoping, multi-provider routing, and full observability — running as a FastAPI service.

---

## Roadmap — where this sits

```
Phase 1 (L01-11)   Phase 2 (L12-21)   Phase 3 (L22-28)   Enterprise Hardening
Foundation          Agentic Patterns    Advanced RAG        IAM + Model Routing

                                                           ▶ CAPSTONE 1  ◄ YOU ARE HERE
                                                           ○ Capstone 2
```

**Why this capstone:** Phase 1-3 taught you the pieces. This capstone assembles them into a product a real company could ship — a support intelligence platform with zero hallucination tolerance, cost controls, and an audit trail.

---

## Scenario

A B2B SaaS company handles 500 support tickets per day. Their current workflow: every ticket goes to a human agent (avg 12 min resolution, ₹800/ticket cost). The goal is to resolve 70% automatically with AI, escalate 30% to humans with a full briefing pre-generated, and audit every decision.

**Your job:** Build the AI system that does this.

---

## Files you will create

| File | Role |
|---|---|
| `capstone1/main.py` | FastAPI service — `/submit-ticket`, `/approve/{ticket_id}`, `/metrics` |
| `capstone1/agents/triage.py` | Triage agent — classify severity + intent |
| `capstone1/agents/rag_agent.py` | RAG agent — retrieve from KB, draft response |
| `capstone1/agents/research.py` | Research agent — web search + KB synthesis |
| `capstone1/agents/escalation.py` | Escalation agent — page human + create Jira ticket |
| `capstone1/agents/orchestrator.py` | Supervisor — routes ticket to right agent chain |
| `capstone1/guardrails.py` | Input + output guardrails (hallucination, PII, on-topic) |
| `capstone1/iam.py` | Per-agent scoping — which agent can call which tool |
| `capstone1/audit.py` | Audit log — every decision recorded |
| `capstone1/router.py` | Model router — haiku for triage, sonnet for research |
| `capstone1/knowledge_base/` | Product docs for RAG (load at startup) |

---

## Architecture

```
POST /submit-ticket
        │
        ▼
   Triage Agent  (claude-haiku — fast, cheap)
        │   classify: severity=[LOW|MED|HIGH], intent=[billing|bug|feature|account]
        │
        ├── LOW ──► RAG Agent ──► retrieve from KB ──► draft response
        │               │
        │               └── Guardrail: faithfulness check vs retrieved chunks
        │                       │ pass ──► POST /send-reply
        │                       │ fail ──► escalate to MED path
        │
        ├── MED ──► Research Agent (claude-sonnet)
        │               │  web_search + KB retrieval + synthesis
        │               ▼
        │           Analyst Agent ──► score confidence (0-10)
        │               │
        │               └── confidence ≥ 7 ──► Human approval gate
        │                       │ approved ──► POST /send-reply
        │                       │ rejected ──► revision loop (max 2)
        │
        └── HIGH ──► Escalation Agent
                        │  page human (Slack webhook)
                        │  create Jira ticket with AI-generated briefing
                        └── Audit log entry (immutable)

Every path writes to audit log.
Every agent call enforced by IAM scope check.
Every response checked by output guardrail.
```

---

## What each lesson shows up as

| In this capstone | From lesson |
|---|---|
| `create_react_agent`, tool-calling loop | L03 |
| `cache_control` on system prompts | L04 |
| `with_structured_output` for triage classification | L05 |
| Parallel KB retrieval across multiple doc sets | L06 |
| `MemorySaver` for conversation context within a ticket | L08 |
| Hybrid RAG for KB (dense + sparse retrieval) | L22 |
| Corrective RAG — re-fetch if retrieval confidence low | L24 |
| Input + output guardrails on every agent | L10 |
| Multi-agent supervisor orchestration | L14 |
| Human-in-the-loop approval gate | L21 |
| LangSmith traces for every ticket end-to-end | L28 |
| Per-agent tool scoping (IAM) | IAM module |
| Haiku for triage, Sonnet for research (model routing) | Model routing module |
| Token budget per ticket (cost optimization) | L26 |

---

## Step-by-step build sequence

### Step 1 — Scaffold and knowledge base
```bash
mkdir -p capstone1/{agents,knowledge_base}
```
- Load 3 product docs (FAQ, pricing, release notes) into hybrid RAG store
- Verify retrieval with 5 test queries before wiring any agents

### Step 2 — Triage agent
- Input: raw ticket text
- Output: `TriageResult(severity, intent, confidence, routing_reason)`
- Use `claude-haiku-4-5` + `with_structured_output`
- Test: 10 sample tickets, verify correct routing for all

### Step 3 — RAG agent (LOW path)
- Retrieve top-5 chunks from KB
- Draft response grounded strictly in retrieved content
- Faithfulness guardrail: refuse to send if score < 7
- Test: 5 billing + 5 bug tickets against KB

### Step 4 — Research agent (MED path)
- web_search tool + KB retrieval in parallel
- Synthesise into `ResearchSummary(answer, sources, confidence)`
- Analyst scores confidence; if < 7, trigger one revision loop
- Test: 5 tickets that require web context not in KB

### Step 5 — Escalation agent (HIGH path)
- Generate structured briefing: summary, impact, suggested owner, SLA risk
- Send Slack webhook notification (mock endpoint)
- Create Jira-style ticket record in SQLite (mock CRM)
- Test: 3 critical tickets, verify briefing quality

### Step 6 — IAM scoping
```python
AGENT_SCOPES = {
    "triage":     ["classify"],
    "rag":        ["retrieve_kb", "send_reply"],
    "research":   ["retrieve_kb", "web_search"],
    "escalation": ["send_slack", "create_jira", "send_reply"],
}
```
- Middleware intercepts every tool call, checks agent scope
- Returns structured `PermissionDeniedError` if out of scope
- Test: triage agent attempting `web_search` — must be denied

### Step 7 — Orchestrator + FastAPI service
- Wire all agents under supervisor
- `POST /submit-ticket` → returns `ticket_id`
- `GET /ticket/{ticket_id}` → status + audit trail
- `POST /approve/{ticket_id}` → human approval for MED path
- `GET /metrics` → resolution rate, avg cost, avg latency, cache hit rate

### Step 8 — Observability
- LangSmith trace tag per ticket: `ticket_id`, `severity`, `intent`
- Cost per ticket logged: input tokens × price + output tokens × price
- Alert if any ticket exceeds ₹50 token budget

---

## Run it

```bash
cd capstone1
uvicorn main:app --reload

# Submit a ticket
curl -X POST /submit-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id": "T001", "text": "I was charged twice for my subscription this month."}'

# Check status
curl /ticket/T001

# Approve (if MED severity)
curl -X POST /approve/T001
```

Expected output per ticket:
```
[triage]     severity=LOW  intent=billing  routing=rag_agent  (0.4s, haiku, $0.0003)
[rag]        retrieved=4 chunks  confidence=8.2  faithfulness=PASS
[guardrail]  output PII=CLEAR  hallucination=CLEAR
[send]       reply drafted (182 tokens)  total_cost=$0.0021  latency=3.1s
[audit]      T001 logged — agent=rag, verdict=resolved, timestamp=...
```

---

## Grading rubric

| Area | Points | Criteria |
|---|---|---|
| **Triage accuracy** | 20 | ≥ 85% correct routing on 20 held-out tickets |
| **RAG faithfulness** | 15 | No hallucinated facts in any LOW-path response (manual spot-check 10) |
| **Guardrails** | 15 | PII in input → refused; hallucinated output → blocked; on-topic → enforced |
| **IAM scoping** | 10 | Each agent restricted to declared tools; out-of-scope call returns error |
| **HITL flow** | 10 | MED path requires approval before sending; rejection triggers revision |
| **Audit trail** | 10 | Every ticket has complete log: agent, tool calls, decision, cost, timestamp |
| **Observability** | 10 | LangSmith trace visible for 3 submitted tickets; cost per ticket logged |
| **API correctness** | 5 | All 4 endpoints return correct status codes and response shapes |
| **Cost control** | 5 | Token budget enforced; haiku used for triage (not sonnet); cache hit > 40% |

**Total: 100 points. Pass: 75+**

---

## Architecture Decision Record (deliverable)

Write a 1-page ADR answering:
1. Why did you choose this agent topology (supervisor vs pipeline vs event-driven)?
2. What is the failure mode if the RAG agent returns low confidence and the escalation agent is unavailable?
3. How would you scale this to 10,000 tickets/day without changing the agent logic?
4. What would you add to make this SOC-2 compliant?

---

## Extension challenges

| Challenge | What you learn |
|---|---|
| Swap `MemorySaver` → `PostgresSaver` | Durable state across restarts |
| Add WhatsApp webhook as input channel | Multi-channel agent |
| Add A/B test: compare Haiku vs Sonnet for RAG quality | Evaluation + cost tradeoff |
| Add GraphRAG over product docs | Richer entity-aware retrieval |
| Replace mock Jira with real Jira API via MCP server | Enterprise integration |

---

## Mental model in one line

> **A production support agent is not a chatbot — it's a pipeline with routing logic, trust boundaries, cost controls, and an audit trail. Every design decision is a tradeoff between accuracy, speed, and cost.**

---

## Related

- **Previous:** L28 — Production deployment + Observability
- **Next:** Capstone 2 — Autonomous Financial Research Agent
- **Reference:** IAM module, Model Routing module, L14 Multi-agent supervisor
