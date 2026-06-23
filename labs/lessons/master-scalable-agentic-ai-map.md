# Curriculum Map — Master Scalable Agentic AI
## The 2026 Stack: from prompt to production across MCP, A2A, and the agent loop

> Source: Brij Kishore Pandey @brijnpandeyji
> **REMEMBER:** Modular · Interoperable · Observable · Stateful · Evaluatable

---

## Coverage map against AgenticCourse

| # | Concept | What it means | Covered in | Depth |
|---|---|---|---|---|
| 1 | **The Agent Loop** | Perceive → Think → Act → Observe. Core cycle every agent runs until goal is reached. | L03 Agent tool loop, L13 Reflection/Plan-Execute | ✅ Deep |
| 2 | **Context Assembly** | What the model actually sees: System Prompt + Tools + Memory + Retrieved Docs + History. Curate, don't dump. | L04 Caching, L08 Memory, L09 RAG, L11 Production Capstone | ✅ Deep |
| 3 | **MCP** | Model Context Protocol — USB-C of AI. One protocol, any tool, any model. | L12 MCP | ✅ Covered |
| 4 | **Tool Use & Function Calling** | Tool Selection → Argument Generation → Execution → Result. Tool descriptions matter more than prompts. | L03, L18 Anthropic SDK | ✅ Deep |
| 5 | **A2A Protocol** | Agent-to-Agent: Discover → Negotiate → Delegate → Return. Cross-vendor interop for multi-agent systems. | ❌ Not covered | 🔴 Gap |
| 6 | **Memory Architecture** | Three layers: Short-Term (context window), Long-Term (vector/KV store), Episodic (past traces). Don't conflate them. | L08, L14 LTM, L29 Memory Architectures | ✅ Deep |
| 7 | **Planning & Reasoning** | ReAct, Plan-and-Execute, Reflection. Choose pattern by task complexity. | L13 Reflection/Plan-Execute | ✅ Covered |
| 8 | **Multi-Agent Orchestration** | Orchestrator + specialist agents (Research/Code/Review/Data). Teams of small agents beat one big agent. | L14 Multi-agent supervisor | ✅ Covered |
| 9 | **Guardrails & Observability** | Input validation, policy checks, output filters, HITL. Traces, token cost, latency, eval scores. Production-ready means safe and measurable. | L10 Guardrails, L25 Eval, L28 Observability, L32 Governance | ✅ Deep |
| 10 | **Key Takeaways** | Build protocol-first (MCP+A2A). Memory is architecture. Multi-agent beats monolith. Tool descriptions are the new prompts. Observability is non-negotiable. | Woven through curriculum | ✅ Philosophy |

---

## Gap: A2A (Agent-to-Agent Protocol)

A2A is the **only concept not covered** in the current curriculum. It is also the newest — Google released the A2A specification in April 2025. Here is what it covers and why it matters:

### What A2A is

A2A is an open protocol that lets agents from different vendors discover and call each other. Where MCP connects an agent to tools, A2A connects an agent to other agents.

```
Without A2A:
  Your LangGraph agent → (can only call) → tools you wrote

With A2A:
  Your LangGraph agent → discovers → a CrewAI agent (different vendor)
                       → negotiates → what it can do (via Agent Card)
                       → delegates → a subtask
                       → returns   → structured result
```

### The four-step handshake

```
1. DISCOVER   Agent A reads Agent B's "Agent Card" (JSON manifest of capabilities)
2. NEGOTIATE  Agent A sends a task; Agent B confirms it can handle it
3. DELEGATE   Agent A hands off the subtask with context
4. RETURN     Agent B returns structured result back to Agent A
```

### Agent Card (the discovery mechanism)

```json
{
  "name": "FinancialResearchAgent",
  "version": "1.0",
  "capabilities": ["company_research", "risk_scoring", "competitor_analysis"],
  "input_schema": {"company": "string", "quarter": "string"},
  "output_schema": {"memo": "string", "citations": "array"},
  "endpoint": "https://research-agent.example.com/a2a",
  "auth": {"type": "bearer"}
}
```

### Why it matters for enterprise

| Without A2A | With A2A |
|---|---|
| Multi-agent = all agents in same codebase | Agents can live in different services, vendors, clouds |
| Adding a new specialist = code change | Adding a new specialist = register Agent Card |
| Vendor lock-in | Swap agent implementations without changing orchestrator |
| One team owns all agents | Different teams own different agents |

### Proposed new lesson: A2A Protocol

**Position:** After L12 (MCP) — A2A is the natural next step after MCP.

**Lab:** Build two agents as separate FastAPI services. Agent A (orchestrator) discovers Agent B (specialist) via Agent Card, delegates a subtask, receives structured result — all without sharing code.

```python
# Agent A — orchestrator
agent_card = a2a_client.discover("https://specialist.local/a2a/card")
if "company_research" in agent_card.capabilities:
    result = a2a_client.delegate(
        endpoint=agent_card.endpoint,
        task={"company": "TataMotors", "quarter": "Q4-2025"},
    )

# Agent B — specialist (separate service)
@app.post("/a2a/execute")
async def execute(task: A2ATask):
    result = await research_agent.run(task.input)
    return A2AResult(output=result, status="complete")
```

---

## Full curriculum coverage by REMEMBER principle

| Principle | Meaning | Where in curriculum |
|---|---|---|
| **Modular** | Each agent does one thing; swap without breaking others | L14 Multi-agent, Capstone 3 five-agent architecture |
| **Interoperable** | Works with any tool, any model, any vendor | L12 MCP, L19 AI Gateway, **A2A (gap)** |
| **Observable** | Every decision is visible and traceable | L28 Observability, L32 Governance, Capstone 3 Jaeger |
| **Stateful** | Agents remember across turns and sessions | L08 Memory, L14 LTM, L29 Memory Architectures |
| **Evaluatable** | You can measure quality, cost, and correctness | L25 Evaluation, L26 Cost Optimization, Capstone 3 ROI report |

---

## Recommended curriculum additions based on this map

| Priority | Addition | Rationale |
|---|---|---|
| 🔴 High | **L12b — A2A Protocol** (new session) | Only uncovered concept; growing enterprise adoption |
| 🟡 Medium | Add A2A to **Capstone 1** (CLI Coding Agent) | Agent discovery via Agent Card is a natural coding-agent extension |
| 🟡 Medium | Add A2A delegation to **Capstone 3** (Production Context Engine) | Specialist agents as external A2A services = true enterprise architecture |
| 🟢 Low | Explicit "Context Assembly" micro-lesson | Covered across L04/L08/L09/L11 but never framed as "what the model sees" |

---

## Visual curriculum arc against the 2026 stack

```
The 2026 Stack                    AgenticCourse lesson
──────────────────────────────────────────────────────────────
Agent Loop                  ──►   L03 Agent tool loop
Context Assembly            ──►   L04 + L08 + L09 + L11
MCP                         ──►   L12 MCP
Tool Use                    ──►   L03 + L18 Anthropic SDK
A2A Protocol                ──►   ❌ NEW: L12b
Memory Architecture         ──►   L08 + L14 + L29
Planning & Reasoning        ──►   L13 Reflection / Plan-Execute
Multi-Agent Orchestration   ──►   L14 Multi-agent supervisor
Guardrails & Observability  ──►   L10 + L25 + L28 + L32
                                  + Capstone 3 (full stack)
──────────────────────────────────────────────────────────────
Build protocol-first        ──►   MCP (L12) + A2A (L12b)
Memory is architecture      ──►   L29 Memory Architectures
Multi-agent beats monolith  ──►   L14 + Capstone 2 fan-out
Tool descriptions = prompts ──►   L03 + L18 tool schema design
Observability non-negotiable──►   Capstone 3 Phase B
```

---

## One-line verdict

> The AgenticCourse covers 9 of 10 concepts from the 2026 Scalable Agentic AI stack at intermediate-to-deep depth. The single gap is **A2A** — add one session after L12 and the curriculum matches the full stack.
