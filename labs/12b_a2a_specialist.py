"""A2A Specialist Agent — Financial Research Service.

An autonomous agent exposing the Agent-to-Agent (A2A) protocol.
Run with: uvicorn 12b_a2a_specialist:app --port 8001

Endpoints:
  GET  /.well-known/agent.json   → Agent Card (discovery)
  POST /tasks/send               → Accept a delegated task
  GET  /tasks/{task_id}          → Poll task status
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Financial Research Specialist", version="1.0.0")
client = anthropic.Anthropic()

# In-memory task store — use Redis in production
tasks: dict[str, dict] = {}


# ── Agent Card ────────────────────────────────────────────────────────────────

AGENT_CARD = {
    "name": "Financial Research Specialist",
    "version": "1.0.0",
    "description": "Researches publicly listed companies and produces structured investment summaries.",
    "url": "http://localhost:8001",
    "documentationUrl": "http://localhost:8001/docs",
    "skills": [
        {
            "id": "company_research",
            "name": "Company Research",
            "description": "Research a company for a given quarter and return a structured summary with key metrics and risks.",
            "inputModes":  ["text"],
            "outputModes": ["data"],
            "examples": [
                "Research TataMotors Q4-2025",
                "What are the key risks for Infosys in Q3-2025?",
            ],
        },
        {
            "id": "risk_scoring",
            "name": "Risk Scoring",
            "description": "Score a company on 5 risk dimensions: market, operational, financial, regulatory, and ESG.",
            "inputModes":  ["data"],
            "outputModes": ["data"],
            "examples": [
                "Score TataMotors on risk dimensions",
            ],
        },
    ],
    "defaultInputMode":  "text",
    "defaultOutputMode": "data",
    "capabilities": {
        "streaming":             False,
        "pushNotifications":     False,
        "stateTransitionHistory": True,
    },
    "authentication": {
        "schemes": ["none"]    # Add "Bearer" for production auth
    },
}


@app.get("/.well-known/agent.json")
def get_agent_card():
    """Discovery endpoint — orchestrators read this to learn what we can do."""
    print("[specialist]  Agent Card requested", file=sys.stderr)
    return JSONResponse(content=AGENT_CARD)


# ── Task schemas ──────────────────────────────────────────────────────────────

class MessagePart(BaseModel):
    type: str = "text"
    text: str


class Message(BaseModel):
    role: str = "user"
    parts: list[MessagePart]


class TaskRequest(BaseModel):
    task_id: str | None = None
    skill_id: str
    message: Message
    metadata: dict | None = None


# ── Accept task ───────────────────────────────────────────────────────────────

@app.post("/tasks/send", status_code=202)
async def send_task(req: TaskRequest):
    """Accept a delegated task. Returns task_id immediately; work happens in background."""
    if req.skill_id not in {s["id"] for s in AGENT_CARD["skills"]}:
        raise HTTPException(status_code=400, detail=f"Unknown skill: {req.skill_id!r}")

    task_id = req.task_id or str(uuid.uuid4())
    tasks[task_id] = {
        "task_id": task_id,
        "skill_id": req.skill_id,
        "status": "working",
        "result": None,
        "history": [
            {"timestamp": datetime.utcnow().isoformat(), "status": "working", "note": "Task accepted"}
        ],
        "error": None,
    }

    # Run agent work asynchronously — orchestrator polls for result
    goal = req.message.parts[0].text
    asyncio.create_task(_execute_skill(task_id, req.skill_id, goal))

    print(f"[specialist]  Task {task_id[:8]}... accepted — skill={req.skill_id!r}", file=sys.stderr)
    return {"task_id": task_id, "status": "working"}


# ── Poll status ───────────────────────────────────────────────────────────────

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    """Poll task status. Check status field: working | completed | failed."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    return tasks[task_id]


# ── Internal skill execution ──────────────────────────────────────────────────

async def _execute_skill(task_id: str, skill_id: str, goal: str) -> None:
    """Run the actual agent work. Each skill has its own logic."""
    try:
        if skill_id == "company_research":
            result = await _company_research(goal)
        elif skill_id == "risk_scoring":
            result = await _risk_scoring(goal)
        else:
            raise ValueError(f"Unhandled skill: {skill_id}")

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result"] = {"parts": [{"type": "data", "data": result}]}
        tasks[task_id]["history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed",
            "note": f"Skill {skill_id!r} completed successfully",
        })
        print(f"[specialist]  Task {task_id[:8]}... completed ✓", file=sys.stderr)

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        tasks[task_id]["history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "status": "failed",
            "note": str(e),
        })
        print(f"[specialist]  Task {task_id[:8]}... FAILED: {e}", file=sys.stderr)


async def _company_research(goal: str) -> dict:
    """Specialist's internal agent logic — orchestrator never sees inside here."""
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=(
                "You are a concise financial research analyst. "
                "Return a structured JSON object with keys: "
                "summary (str), key_metrics (list of str), risks (list of str), "
                "recommendation (str), confidence (float 0-1)."
            ),
            messages=[{"role": "user", "content": f"Research request: {goal}"}],
        ),
    )
    import json
    text = response.content[0].text
    try:
        # Try to parse structured output
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end]) if start >= 0 else {"summary": text}
    except json.JSONDecodeError:
        return {"summary": text}


async def _risk_scoring(goal: str) -> dict:
    """Return risk scores across 5 dimensions (1-5 scale)."""
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=(
                "You are a risk analyst. Return a JSON object with keys: "
                "market_risk (int 1-5), operational_risk (int 1-5), "
                "financial_risk (int 1-5), regulatory_risk (int 1-5), "
                "esg_risk (int 1-5), overall_risk (float), rationale (str)."
            ),
            messages=[{"role": "user", "content": f"Risk score request: {goal}"}],
        ),
    )
    import json
    text = response.content[0].text
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end]) if start >= 0 else {"rationale": text}
    except json.JSONDecodeError:
        return {"rationale": text}


if __name__ == "__main__":
    import uvicorn
    print("[specialist]  Starting Financial Research Specialist on port 8001", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")
