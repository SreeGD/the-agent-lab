# 42 — Browser Automation & Computer Use (Session 42)

> **Claude drives a real browser from a natural-language goal.** No DOM selectors, no Playwright scripts — just describe what you want done and Claude finds, clicks, fills, and extracts, fully autonomously.

---

## Roadmap — where this lesson sits in the journey

```
═══════ TRACK M: CLAUDE CODE MASTERY (optional) ═══════

  ✓ Session 38: CLAUDE.md + Settings
  ✓ Session 39: Claude Code Hooks
  ✓ Session 40: Autonomous Workflows
  ✓ Session 41: Codebase Archaeology
  ▶ Session 42: BROWSER AUTOMATION  ◄ HERE
    Session 43: Scheduled Cloud Routines
    Session 44: Document & Slide Generation
    Session 45: Multi-Agent Code Review Pipeline
```

**Maps to "12 Insane Claude Features" #06 — Automate the Browser End-to-End.**

---

## Files involved

| File | Role |
|---|---|
| [`browser_agent.py`](../browser_agent.py) | Goal-conditioned browser agent using Computer Use API |
| [`computer_use_demo.py`](../computer_use_demo.py) | Minimal screenshot-action loop demonstration |

---

## What problem it solves

Traditional browser automation (Selenium, Playwright) requires you to:
- Identify CSS selectors or XPath expressions
- Script every click, fill, and wait explicitly
- Maintain scripts as the UI changes

Claude's Computer Use changes the model: you describe the **goal**, Claude takes **screenshots**, decides **actions**, executes them, and loops until done. The UI can change; Claude adapts because it sees pixels, not selectors.

---

## The analogy

Traditional automation = **instructions for a robot that can't see** ("click the element with id='submit-btn'").

Computer Use = **instructions for a human** ("submit the form"). Claude sees the screen the same way you do and figures out the rest.

---

## Visual

```
  Natural language goal
  "Find the cheapest flight from HYD to BOM next Friday"
         │
         ▼
  ┌────────────────────────────────┐
  │  browser_agent.py              │
  │                                │
  │  loop:                         │
  │    1. take screenshot          │
  │    2. send to Claude with goal │
  │    3. Claude returns action:   │
  │       {type: "click",          │
  │        x: 342, y: 218}         │
  │    4. execute action           │
  │    5. repeat until done        │
  └────────────────┬───────────────┘
                   │
                   ▼
          Task completed
          + extracted result
```

---

## Key patterns

### 1. The screenshot-action loop

```python
import anthropic
import base64
from PIL import ImageGrab

client = anthropic.Anthropic()

def take_screenshot() -> str:
    img = ImageGrab.grab()
    img.save("/tmp/screen.png")
    with open("/tmp/screen.png", "rb") as f:
        return base64.b64encode(f.read()).decode()

def run_browser_agent(goal: str):
    messages = []
    while True:
        screenshot = take_screenshot()
        messages.append({
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot}},
                {"type": "text", "text": f"Goal: {goal}\nWhat action should I take next?"}
            ]
        })

        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1024,
            tools=[{"type": "computer_20250124", "name": "computer", "display_width_px": 1280, "display_height_px": 800}],
            messages=messages
        )

        if response.stop_reason == "end_turn":
            return response.content[-1].text  # task complete

        action = extract_action(response)
        execute_action(action)
        messages.append({"role": "assistant", "content": response.content})
```

### 2. Action types

Claude emits structured actions from the Computer Use tool:

| Action | When used |
|---|---|
| `screenshot` | Claude explicitly requests a fresh view |
| `left_click` | Click a button, link, or input |
| `type` | Type text into a focused field |
| `key` | Press keyboard shortcuts (Enter, Tab, Ctrl+C) |
| `scroll` | Scroll the page |
| `left_click_drag` | Drag elements |
| `double_click` | Open files, select words |
| `right_click` | Context menus |
| `mouse_move` | Hover for tooltips |

### 3. Goal decomposition

For multi-step goals, decompose before sending:

```python
SYSTEM_PROMPT = """
You are a browser automation agent. You control a real browser via screenshots.

Rules:
- Always take a screenshot before deciding the next action
- If a page is loading, wait and take another screenshot
- Extract data as structured JSON when the task is complete
- If you cannot complete the task, explain why clearly
- Never enter credentials unless they are provided in the goal
"""
```

### 4. Headless vs. headed

For production scheduling (Session 43), run headed (visible browser) during development, then switch to headless:

```python
from playwright.sync_api import sync_playwright

def launch_browser(headless: bool = False):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        return browser, page
```

Computer Use + Playwright = vision-guided automation with full browser control.

---

## Run it

```bash
# Install dependencies
pip install anthropic pillow playwright
playwright install chromium

# Run the demo
python computer_use_demo.py

# Run a goal-driven task
python browser_agent.py --goal "Go to news.ycombinator.com and extract the top 5 story titles and point counts"
```

Expected output:

```json
{
  "task": "Extract HN top 5 stories",
  "status": "completed",
  "steps_taken": 3,
  "result": [
    {"rank": 1, "title": "Show HN: I built...", "points": 342},
    {"rank": 2, "title": "Ask HN: What...", "points": 218},
    ...
  ]
}
```

---

## Walk-through

### What Claude sees vs. what selectors see

| | CSS Selector | Computer Use |
|---|---|---|
| Input | `#email-field` | "The text box labeled 'Email'" |
| Button | `.btn-primary` | "The blue 'Sign In' button" |
| After UI update | Breaks | Adapts automatically |
| Works on | Your DOM | Any screen |
| Auth required | No | If screenshot visible |

### Latency profile

Each loop iteration costs:
- Screenshot capture: ~50ms
- Image encode: ~20ms
- Claude API call: ~1-3s (vision + reasoning)
- Action execution: ~100-500ms

For a 5-step task: ~15-20 seconds. For automation that used to need weeks of script maintenance, this is the right trade.

### Safety patterns

```python
BLOCKED_DOMAINS = {"banking.internal", "prod.company.com"}
BLOCKED_ACTIONS = {"type_password", "delete", "purchase"}

def safe_execute(action: dict) -> bool:
    if action.get("type") == "navigate":
        if any(blocked in action["url"] for blocked in BLOCKED_DOMAINS):
            return False
    return True
```

Never give Claude access to authenticated sessions for sensitive systems without explicit guardrails.

---

## Try this

1. **HN scraper** — run the agent with goal "Extract the top 10 Hacker News stories with their point counts." Inspect the structured output.
2. **Form fill** — create a local HTML form, run the agent with "Fill out this form with test data and submit it." Watch it navigate the form without selectors.
3. **UI regression testing** — describe the expected state of a page in plain English, run the agent, and have it report deviations. Natural-language test assertions.
4. **Multi-tab workflow** — extend `browser_agent.py` to open two tabs and cross-reference data between them (e.g., compare prices on two sites).
5. **Combine with Session 43** — schedule this agent to run nightly: "Check our status page and post a summary to Slack if any service is degraded."

---

## Mental model in one line

> **Browser automation with Computer Use is a screenshot-action loop: Claude sees pixels (not DOM), decides actions from a natural-language goal, and executes them until done — making the automation UI-change-tolerant by design.**

---

## Related

- **Previous:** [41 — Codebase Archaeology with Claude](41-codebase-archaeology.md)
- **Next:** [43 — Scheduled Cloud Routines](43-scheduled-cloud-routines.md)
- **Pairs naturally with:** [43 — Scheduled Cloud Routines](43-scheduled-cloud-routines.md) (schedule this agent)
- **Maps to image feature:** #06 — Automate the Browser End-to-End
- **Curriculum tracker:** Session 42 of 45
