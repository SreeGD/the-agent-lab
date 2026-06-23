# 12b — A2A (Agent-to-Agent Protocol)

> **Agents talking to agents across vendors, services, and clouds.** Where MCP connects an agent to tools, A2A connects an agent to other agents. Build two independent FastAPI services — an orchestrator and a specialist — that discover each other, negotiate capabilities, delegate tasks, and return structured results without sharing a single line of code.

---

## Roadmap — where this lesson sits

```
Phase 1 (Foundation)           Phase 2 (Architect Skills)

  ✓ 01-11 (foundation)           ▶ 12b A2A  ◄═══ YOU ARE HERE
  ✓ 12 MCP                       ○ 13 Reflection / Plan-Execute
                                  ○ 14 Multi-agent + LTM
```

**Why this lesson now:** L12 taught MCP — the standard for agents talking to *tools*. A2A is the next layer: the standard for agents talking to *other agents*. Together, MCP + A2A are the two protocols of the 2026 enterprise AI stack. You will not build a scalable multi-agent system without understanding both.

**A2A was released by Google in April 2025.** It is new, fast-growing, and already supported by 50+ partners including Salesforce, SAP, ServiceNow, and Atlassian.

---

## Files involved

| File | Role |
|---|---|
| [`12b_a2a_orchestrator.py`](../12b_a2a_orchestrator.py) | Orchestrator agent — discovers specialists, delegates tasks |
| [`12b_a2a_specialist.py`](../12b_a2a_specialist.py) | Specialist agent — FastAPI service exposing A2A endpoint |
| [`12b_a2a_demo.py`](../12b_a2a_demo.py) | End-to-end demo — starts both services, runs a delegation |

---

## What problem it solves

Your L14 multi-agent supervisor runs all agents in one Python process. That works for a team you own. It breaks the moment you need to:

- Use a specialist agent built by a different team, in a different codebase
- Call a vendor's pre-built agent (Salesforce's CRM agent, SAP's procurement agent)
- Deploy agents to different clouds (orchestrator on AWS, specialist on GCP)
- Let agents from different LLM providers interoperate (your Claude agent delegates to a GPT-based specialist)

Without a standard protocol, this is O(N×M) glue code — every orchestrator needs custom integration for every specialist. **A2A makes it O(N+M): one protocol, any agent works with any other.**

---

## The analogy

**MCP is USB for tools. A2A is TCP/IP for agents.**

TCP/IP doesn't care whether you're running Linux or Windows, AWS or Azure. It defines how packets flow between machines. Any machine that speaks TCP/IP can talk to any other.

A2A defines how agents negotiate and delegate. Any agent that speaks A2A can talk to any other — regardless of framework (LangGraph, CrewAI, custom), LLM provider (Anthropic, OpenAI, Gemini), or deployment (local, cloud, vendor SaaS).

---

## MCP vs. A2A — the key distinction

```
MCP:  Agent ←─────────────────────► Tool
      (agent is the brain)           (tool is a function it calls)

A2A:  Agent ←─────────────────────► Agent
      (orchestrator delegates)       (specialist is autonomous — it has its OWN loop,
                                      its OWN tools, its OWN model)
```

| Aspect | MCP | A2A |
|---|---|---|
| What connects | Agent ↔ Tool | Agent ↔ Agent |
| The other party | A function | An autonomous agent with its own loop |
| Discovery | `tools/list` | Agent Card (JSON manifest) |
| Invocation | `tools/call` | `tasks/send` |
| Response | Immediate result | Streaming, async, multi-turn |
| Context | Agent owns context | Each agent owns its own context |
| Vendor lock-in | Tool must match agent's SDK | No — protocol is vendor-neutral |

---

## The four-step handshake

```
DISCOVER   ──► Orchestrator fetches Specialist's Agent Card
               GET https://specialist.local/.well-known/agent.json

NEGOTIATE  ──► Orchestrator reads capabilities, picks matching skill
               "company_research" ∈ agent_card.skills → match

DELEGATE   ──► Orchestrator sends task via POST /tasks/send
               {task_id, skill, input: {company, quarter}}

RETURN     ──► Specialist streams back structured result
               {task_id, status: "complete", output: {memo, citations}}
```

---

## Visual

```
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator Agent (12b_a2a_orchestrator.py)               │
│                                                             │
│  User: "Research TataMotors Q4-2025"                        │
│         │                                                   │
│         ▼                                                   │
│  1. GET /.well-known/agent.json  ──► reads Agent Card       │
│         │                                                   │
│         ▼                                                   │
│  2. Match skill: "company_research" found                   │
│         │                                                   │
│         ▼                                                   │
│  3. POST /tasks/send  ──────────────────────────────────┐   │
│         │                                               │   │
│         ▼                                               ▼   │
│  4. Receive stream/result ◄─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                        │ POST /tasks/send
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  Specialist Agent (12b_a2a_specialist.py)                   │
│  FastAPI service — completely independent codebase          │
│                                                             │
│  /.well-known/agent.json  ← Agent Card (discovery)         │
│  POST /tasks/send         ← Accept delegation               │
│  GET  /tasks/{id}         ← Poll status                     │
│                                                             │
│  Internally: has its OWN agent loop, OWN tools, OWN model  │
│  The orchestrator never sees inside this box               │
└─────────────────────────────────────────────────────────────┘
```

---

## The Agent Card

The Agent Card is the A2A discovery mechanism — a JSON manifest every A2A agent serves at `/.well-known/agent.json`. It is the single source of truth about what the agent can do.

```json
{
  "name": "Financial Research Specialist",
  "version": "1.0.0",
  "description": "Researches publicly listed companies and produces investment memos.",
  "url": "https://specialist.local",
  "skills": [
    {
      "id": "company_research",
      "name": "Company Research",
      "description": "Fetches filings, news, and competitor data for a company/quarter.",
      "inputModes":  ["text", "data"],
      "outputModes": ["text", "data"],
      "examples": ["Research TataMotors Q4-2025"]
    },
    {
      "id": "risk_scoring",
      "name": "Risk Scoring",
      "description": "Scores a company on 5 risk dimensions from public data.",
      "inputModes":  ["data"],
      "outputModes": ["data"]
    }
  ],
  "defaultInputMode":  "text",
  "defaultOutputMode": "text",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  }
}
```

The orchestrator reads this card and decides which skill to invoke — without any custom integration code.

---

## The concept

### Specialist side (12b_a2a_specialist.py)

```python
from fastapi import FastAPI
from pydantic import BaseModel
import anthropic, uuid, asyncio

app = FastAPI()
client = anthropic.Anthropic()
tasks: dict = {}   # in-memory task store (use Redis in production)

# ── Agent Card ────────────────────────────────────────────────
@app.get("/.well-known/agent.json")
def agent_card():
    return {
        "name": "Financial Research Specialist",
        "version": "1.0.0",
        "url": "http://localhost:8001",
        "skills": [
            {
                "id": "company_research",
                "name": "Company Research",
                "description": "Research a company and return a structured memo.",
                "inputModes": ["text"],
                "outputModes": ["data"],
            }
        ],
    }

# ── Accept task ───────────────────────────────────────────────
class TaskRequest(BaseModel):
    task_id: str | None = None
    skill_id: str
    message: dict          # {"role": "user", "parts": [{"text": "..."}]}

@app.post("/tasks/send")
async def send_task(req: TaskRequest):
    task_id = req.task_id or str(uuid.uuid4())
    tasks[task_id] = {"status": "working", "result": None}
    # Run agent work in background
    asyncio.create_task(_run_agent(task_id, req.message))
    return {"task_id": task_id, "status": "working"}

# ── Poll status ───────────────────────────────────────────────
@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    return tasks.get(task_id, {"status": "not_found"})

# ── Internal agent loop ───────────────────────────────────────
async def _run_agent(task_id: str, message: dict):
    goal = message["parts"][0]["text"]
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": f"Research this company briefly: {goal}"}],
    )
    tasks[task_id] = {
        "status": "completed",
        "result": {
            "parts": [{"type": "text", "text": response.content[0].text}]
        },
    }
```

### Orchestrator side (12b_a2a_orchestrator.py)

```python
import httpx, time

SPECIALIST_URL = "http://localhost:8001"

def discover(base_url: str) -> dict:
    """Fetch Agent Card — the only thing needed to discover a specialist."""
    return httpx.get(f"{base_url}/.well-known/agent.json").json()

def match_skill(card: dict, intent: str) -> str | None:
    """Find a skill whose description matches the intent."""
    for skill in card.get("skills", []):
        if intent.lower() in skill["description"].lower():
            return skill["id"]
    return None

def delegate(base_url: str, skill_id: str, goal: str) -> dict:
    """Send task and poll until complete."""
    # Send
    resp = httpx.post(f"{base_url}/tasks/send", json={
        "skill_id": skill_id,
        "message": {"role": "user", "parts": [{"text": goal}]},
    })
    task_id = resp.json()["task_id"]

    # Poll (use webhooks or SSE in production)
    for _ in range(30):
        result = httpx.get(f"{base_url}/tasks/{task_id}").json()
        if result["status"] == "completed":
            return result["result"]
        time.sleep(1)

    raise TimeoutError(f"Task {task_id} did not complete in 30s")

# ── Main orchestration flow ───────────────────────────────────
def run(goal: str):
    print(f"[orchestrator]  Goal: {goal}")

    card = discover(SPECIALIST_URL)
    print(f"[discover]      Found: {card['name']} — {len(card['skills'])} skills")

    skill_id = match_skill(card, "research")
    print(f"[negotiate]     Matched skill: {skill_id!r}")

    result = delegate(SPECIALIST_URL, skill_id, goal)
    print(f"[return]        Result received ({len(result['parts'][0]['text'])} chars)")
    print(f"\n{result['parts'][0]['text']}")
```

---

## Run it

Terminal 1 — start specialist:
```bash
uvicorn 12b_a2a_specialist:app --port 8001
```

Terminal 2 — run orchestrator:
```bash
python 12b_a2a_orchestrator.py
```

Or run the full demo (starts both automatically):
```bash
python 12b_a2a_demo.py
```

Expected output:
```
[specialist]    Agent Card served at http://localhost:8001/.well-known/agent.json
[orchestrator]  Goal: Research TataMotors Q4-2025

[discover]      Found: Financial Research Specialist — 2 skills
[negotiate]     Matched skill: 'company_research'
[delegate]      POST /tasks/send → task_id=abc-123, status=working
[poll]          task abc-123: working... working... completed ✓

[return]        Result received (412 chars)

TataMotors reported strong Q4-2025 results driven by JLR recovery...
[citations: 3 sources]
```

---

## Walk-through

### Why the Agent Card is everything

The Agent Card is the entire discovery mechanism. No registration service, no central directory. The orchestrator only needs to know the base URL — it discovers everything else from the card. This is why A2A scales: adding a new specialist means deploying a service with an Agent Card, not updating any central registry.

### Why agents are opaque to each other

The orchestrator sends `goal: "Research TataMotors Q4-2025"` to the specialist. The specialist could use LangGraph, CrewAI, a direct Claude call, or a GPT-4 call internally. The orchestrator has no idea and no dependency on that choice. **This is the architectural benefit A2A buys: agents are black boxes to each other, coordinated by a common protocol.**

### Task lifecycle and async design

A2A tasks are async by design:
```
POST /tasks/send  → 202 Accepted  + task_id     (immediate)
GET  /tasks/{id}  → {status: "working"}          (poll)
GET  /tasks/{id}  → {status: "completed", result} (done)
```

For long-running research tasks (30s+), this prevents the orchestrator from blocking. In production, replace polling with Server-Sent Events (A2A supports `streaming: true` in the Agent Card) or push notifications.

### Multi-agent with A2A — the enterprise pattern

```
Orchestrator (your Claude agent)
      │
      ├── discover + delegate ──► CRM Specialist    (Salesforce-hosted A2A agent)
      ├── discover + delegate ──► Procurement Agent (SAP-hosted A2A agent)
      ├── discover + delegate ──► Research Specialist (your Python service)
      └── aggregate results   ──► final response
```

The orchestrator doesn't know or care that three of these run in external clouds. It just reads Agent Cards and delegates. **This is how enterprise multi-agent systems work in 2026.**

---

## A2A vs. MCP — when to use which

| I need to... | Use |
|---|---|
| Give my agent access to a database, API, or file system | **MCP** |
| Let my agent call a Python function | **MCP** |
| Delegate a complex subtask to a specialist agent | **A2A** |
| Use an agent built by a different vendor | **A2A** |
| Connect two agents across different clouds | **A2A** |
| Both: agent needs tools AND to delegate to agents | **MCP + A2A** |

The patterns compose naturally:
```
Your orchestrator (A2A client)
    └── delegates to → Your specialist (A2A server)
                            └── uses tools via → MCP server
```

---

## Key design choices

| Choice | Why |
|---|---|
| Agent Card at `/.well-known/agent.json` | Standard path — orchestrators know where to look without configuration |
| 202 Accepted + poll pattern | Agents tasks are long-running; blocking HTTP would time out |
| `skill_id` not `tool_name` | Skills are higher-level intentions, not low-level functions — matches how agents think |
| Opaque internal implementation | Each agent owns its own loop, tools, and model — no coupling |

---

## Production extensions

| Extension | What it enables |
|---|---|
| Add OAuth to Agent Card | Only authorized orchestrators can delegate |
| Replace polling with SSE | Real-time streaming of agent reasoning to orchestrator |
| Add `stateTransitionHistory: true` | Orchestrator can audit every step the specialist took |
| Register Agent Cards in a service directory | Orchestrators discover agents by capability, not URL |
| Add task cancellation: `DELETE /tasks/{id}` | Orchestrator can abort a long-running specialist |

---

## Try this

1. **Add a second skill** to the specialist (`risk_scoring`). Restart it. Watch the orchestrator discover it automatically with no orchestrator code changes.
2. **Change the specialist's model** from `claude-haiku` to `claude-sonnet`. The orchestrator never notices. This is the power of opacity.
3. **Build a second specialist** (e.g., a news summariser on port 8002). Have the orchestrator discover both, delegate to each, and merge results.
4. **Break the specialist mid-task** (kill it). Handle the timeout gracefully in the orchestrator.

---

## Mental model in one line

> **MCP lets agents use tools. A2A lets agents use other agents. Together they are the complete 2026 protocol stack: MCP for the leaf nodes, A2A for the coordination layer. Any enterprise multi-agent system that needs to cross team or vendor boundaries needs A2A.**

---

## FAQ

**Q: How is A2A different from just calling a REST API?**

A: Convention and discovery. A REST API requires custom client code per endpoint. A2A means: any orchestrator that speaks the protocol can discover any specialist via its Agent Card and invoke it with the same four lines of code. It's the difference between HTTP (any server) and a custom protocol (one server).

**Q: Is A2A an open standard?**

A: Yes. Released by Google in April 2025, now hosted at [google.github.io/A2A](https://google.github.io/A2A) under an open governance model. Anthropic, Microsoft, Amazon, Salesforce, SAP, and 50+ others have committed to compatibility.

**Q: Does MCP replace A2A or vice versa?**

A: Neither. They solve different problems and compose. MCP is how an agent accesses a tool (file, DB, API). A2A is how an agent accesses another agent (which internally might use MCP to access its own tools).

**Q: How do agents authenticate each other?**

A: The Agent Card's `authentication` field specifies the method. Most commonly OAuth 2.0 client credentials or API keys. The orchestrator obtains a token before calling `/tasks/send`.

**Q: What happens if the specialist is down when I try to discover it?**

A: `GET /.well-known/agent.json` fails with a connection error. The orchestrator should treat this as a routing failure and either try a fallback specialist or return a graceful error.

**Q: Can a specialist also be an orchestrator?**

A: Yes — and this is common in hierarchical multi-agent systems. A specialist might delegate to sub-specialists, creating a tree. A2A's protocol is symmetric: any agent can be both client and server.

---

## Related

- **Previous:** [12 — MCP](12-mcp.md)
- **Next:** [13 — Reflection & Plan-Execute](13-reflection-plan-execute.md)
- **Builds toward:** [14 — Multi-agent + LTM](14-multi-agent-ltm.md), Capstone 3 (Production Context Engine)
- **A2A specification:** https://google.github.io/A2A
- **Infographic:** Brij Kishore Pandey — Master Scalable Agentic AI (concept 5)
