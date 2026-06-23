"""A2A Orchestrator Agent — delegates tasks to specialist agents.

Implements the four-step A2A handshake:
  1. DISCOVER  — fetch Agent Card from specialist
  2. NEGOTIATE — match a skill to the goal
  3. DELEGATE  — send task, receive task_id
  4. RETURN    — poll until complete, retrieve result

Usage:
  # Start specialist first: uvicorn 12b_a2a_specialist:app --port 8001
  python 12b_a2a_orchestrator.py
"""

from __future__ import annotations

import json
import sys
import time

import httpx

SPECIALIST_URL = "http://localhost:8001"
POLL_INTERVAL_S = 1.0
POLL_TIMEOUT_S  = 60.0


# ── Step 1: DISCOVER ──────────────────────────────────────────────────────────

def discover(base_url: str) -> dict:
    """Fetch the Agent Card from a specialist's well-known endpoint."""
    url = f"{base_url}/.well-known/agent.json"
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        card = response.json()
        print(f"[discover]    {card['name']} v{card['version']}")
        print(f"              Skills: {[s['id'] for s in card.get('skills', [])]}")
        return card
    except httpx.ConnectError:
        print(f"[discover]    ERROR: Could not reach {url}")
        print(f"              → Is the specialist running? uvicorn 12b_a2a_specialist:app --port 8001")
        sys.exit(1)


# ── Step 2: NEGOTIATE ─────────────────────────────────────────────────────────

def negotiate(card: dict, intent: str) -> str:
    """Match a skill from the Agent Card to the given intent.

    Simple keyword matching for demo purposes.
    In production: use embeddings to match intent to skill descriptions.
    """
    intent_lower = intent.lower()
    for skill in card.get("skills", []):
        skill_words = (skill["id"] + " " + skill["description"]).lower()
        # Check for keyword overlap
        if any(word in skill_words for word in intent_lower.split() if len(word) > 4):
            print(f"[negotiate]   Matched skill: {skill['id']!r}")
            print(f"              Description: {skill['description']}")
            return skill["id"]

    # Fallback: use the first available skill
    fallback = card["skills"][0]["id"]
    print(f"[negotiate]   No exact match — using default skill: {fallback!r}")
    return fallback


# ── Step 3: DELEGATE ──────────────────────────────────────────────────────────

def delegate(base_url: str, skill_id: str, goal: str) -> str:
    """Send task to specialist. Returns task_id immediately (async dispatch)."""
    payload = {
        "skill_id": skill_id,
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": goal}],
        },
    }
    response = httpx.post(f"{base_url}/tasks/send", json=payload, timeout=10.0)
    response.raise_for_status()
    data = response.json()
    task_id = data["task_id"]
    print(f"[delegate]    Task accepted → task_id={task_id[:8]}...  status={data['status']}")
    return task_id


# ── Step 4: RETURN ────────────────────────────────────────────────────────────

def await_result(base_url: str, task_id: str) -> dict:
    """Poll specialist until task completes. Returns result dict."""
    deadline = time.time() + POLL_TIMEOUT_S
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        response = httpx.get(f"{base_url}/tasks/{task_id}", timeout=5.0)
        response.raise_for_status()
        data = response.json()
        status = data["status"]

        print(f"[poll/{attempt:02d}]    status={status}", end="\r", flush=True)

        if status == "completed":
            print(f"\n[return]      Task completed ✓  (attempt {attempt})")
            return data["result"]

        if status == "failed":
            error = data.get("error", "unknown error")
            print(f"\n[return]      Task FAILED: {error}")
            raise RuntimeError(f"Specialist task failed: {error}")

        time.sleep(POLL_INTERVAL_S)

    raise TimeoutError(f"Task {task_id[:8]}... did not complete within {POLL_TIMEOUT_S}s")


# ── Pretty print result ───────────────────────────────────────────────────────

def print_result(result: dict) -> None:
    parts = result.get("parts", [])
    for part in parts:
        if part.get("type") == "data":
            data = part.get("data", {})
            print("\n" + "─" * 60)
            print("RESULT:")
            print("─" * 60)
            print(json.dumps(data, indent=2, ensure_ascii=False))
        elif part.get("type") == "text":
            print("\n" + "─" * 60)
            print("RESULT:")
            print("─" * 60)
            print(part.get("text", ""))


# ── Main orchestration flow ───────────────────────────────────────────────────

def run(goal: str, specialist_url: str = SPECIALIST_URL) -> dict:
    """Execute the full four-step A2A handshake for a given goal."""
    print(f"\n[orchestrator]  Goal: {goal}")
    print(f"[orchestrator]  Specialist: {specialist_url}\n")

    # 1. DISCOVER — read Agent Card
    card = discover(specialist_url)

    # 2. NEGOTIATE — match skill
    skill_id = negotiate(card, goal)

    # 3. DELEGATE — send task
    task_id = delegate(specialist_url, skill_id, goal)

    # 4. RETURN — await result
    result = await_result(specialist_url, task_id)

    print_result(result)
    return result


if __name__ == "__main__":
    import sys

    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Research TataMotors Q4-2025"
    run(goal)
