"""A2A Demo — starts both specialist and orchestrator, runs the full handshake.

Demonstrates the complete four-step A2A protocol:
  DISCOVER → NEGOTIATE → DELEGATE → RETURN

Run with: python 12b_a2a_demo.py
"""

from __future__ import annotations

import subprocess
import sys
import time

import httpx


def wait_for_specialist(url: str, timeout: int = 15) -> bool:
    """Wait until the specialist's Agent Card is reachable."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/.well-known/agent.json", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    specialist_url = "http://localhost:8001"

    print("=" * 60)
    print("  A2A Protocol Demo")
    print("  Lesson 12b — Agent-to-Agent Protocol")
    print("=" * 60)

    # Start specialist in background
    print("\n[demo]  Starting specialist agent on port 8001...")
    specialist = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "12b_a2a_specialist:app",
         "--port", "8001", "--log-level", "warning"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if not wait_for_specialist(specialist_url):
        print("[demo]  ERROR: Specialist did not start in time.")
        specialist.terminate()
        sys.exit(1)

    print("[demo]  Specialist ready ✓\n")

    try:
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "a2a_orchestrator",
            pathlib.Path(__file__).parent / "12b_a2a_orchestrator.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        run = mod.run

        # Demo 1 — company research
        print("\n── Demo 1: Company Research ──────────────────────────────")
        run("Research Infosys Q3-2025", specialist_url=specialist_url)

        # Demo 2 — risk scoring (different skill)
        print("\n\n── Demo 2: Risk Scoring ──────────────────────────────────")
        run("Score TataMotors on risk dimensions", specialist_url=specialist_url)

        # Demo 3 — show Agent Card directly
        print("\n\n── Demo 3: Agent Card (what the orchestrator reads) ──────")
        card = httpx.get(f"{specialist_url}/.well-known/agent.json").json()
        import json
        print(json.dumps(card, indent=2))

    finally:
        specialist.terminate()
        print("\n\n[demo]  Specialist stopped. Demo complete.")


if __name__ == "__main__":
    main()
