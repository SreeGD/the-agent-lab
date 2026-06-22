# 43 — Scheduled Cloud Routines (Session 43)

> **Set a prompt and a schedule — Claude runs when triggered, no human needed.** Cron-driven Claude Code workflows let you automate research, reports, monitoring, and alerts overnight, with results waiting when you wake up.

---

## Roadmap — where this lesson sits in the journey

```
═══════ TRACK M: CLAUDE CODE MASTERY (optional) ═══════

  ✓ Session 38: CLAUDE.md + Settings
  ✓ Session 39: Claude Code Hooks
  ✓ Session 40: Autonomous Workflows
  ✓ Session 41: Codebase Archaeology
  ✓ Session 42: Browser Automation
  ▶ Session 43: SCHEDULED CLOUD ROUTINES  ◄ HERE
    Session 44: Document & Slide Generation
    Session 45: Multi-Agent Code Review Pipeline
```

**Maps to "12 Insane Claude Features" #08 — Schedule Cloud Routines Overnight.**

---

## Files involved

| File | Role |
|---|---|
| [`scheduled_routine.py`](../scheduled_routine.py) | Idempotent Claude task runner with result persistence |
| [`cron_agent.py`](../cron_agent.py) | Wrapper that registers, runs, and monitors scheduled agents |

---

## What problem it solves

You want Claude to:
- Summarize your industry's news every morning at 7am
- Run a code review on every PR that opens overnight
- Check a competitor's pricing page weekly and alert on changes
- Generate a weekly status report and email it to stakeholders

Without scheduling, you have to trigger these manually. With scheduled routines, you set the prompt + schedule once and wake up to results.

---

## The analogy

A scheduled Claude routine is like a **standing order to a research assistant**:

- "Every Monday morning, summarize last week's AI papers and send me the highlights."
- The assistant doesn't ask for confirmation each time — they just do it.
- You review the output; if it's wrong you adjust the standing order.

The key shift: **you manage prompts, not triggers.**

---

## Visual

```
  Set once:
  ┌─────────────────────────────────────┐
  │  Prompt: "Summarize AI papers       │
  │           from the past week"       │
  │  Schedule: 0 7 * * 1 (Mon 7am)     │
  │  Output: email / file / Slack       │
  └──────────────────────┬──────────────┘
                         │
         ┌───────────────▼──────────────┐
         │    Cron trigger fires        │
         │         │                   │
         │         ▼                   │
         │   Claude executes task      │
         │         │                   │
         │         ▼                   │
         │   Result persisted          │
         │   (file / DB / API)         │
         └──────────────────────────────┘
                         │
                         ▼
         You wake up to a result waiting
```

---

## Key patterns

### 1. Idempotent task design

Scheduled tasks must be safe to re-run. Design for idempotency:

```python
from pathlib import Path
from datetime import date
import hashlib

def result_path(task_name: str, run_date: date) -> Path:
    key = f"{task_name}-{run_date.isoformat()}"
    return Path(f"./outputs/{key}.json")

def run_if_not_done(task_name: str, task_fn):
    path = result_path(task_name, date.today())
    if path.exists():
        return json.loads(path.read_text())  # already ran today
    result = task_fn()
    path.write_text(json.dumps(result))
    return result
```

### 2. Prompt-plus-schedule registration

```python
import anthropic

client = anthropic.Anthropic()

ROUTINE = {
    "name": "weekly-ai-summary",
    "prompt": """
    Search for the most important AI research papers and industry news from the past 7 days.
    Produce a structured summary:
    - Top 3 research breakthroughs (with brief explanation of why they matter)
    - Top 3 industry developments
    - 1 trend to watch
    Format as markdown suitable for an email.
    """,
    "schedule": "0 7 * * 1",  # Every Monday at 7am
    "output": "email",
    "to": "team@company.com"
}
```

### 3. The Claude Code `/schedule` skill

Claude Code has a built-in `/schedule` skill for creating and managing routines:

```bash
# Create a routine
/schedule "Every morning at 7am, summarize the top HN posts and save to daily-digest.md"

# List active routines
/schedule list

# Cancel a routine
/schedule cancel weekly-ai-summary
```

Under the hood, `/schedule` creates a cron entry + a Claude Code session that fires at the specified time.

### 4. Result persistence patterns

| Output target | Pattern |
|---|---|
| **File** | Write markdown to `./outputs/YYYY-MM-DD-task.md` |
| **Email** | Use SendGrid / SES API from within the Claude task |
| **Slack** | POST to webhook URL stored in env var |
| **GitHub** | Open issue or PR via `gh` CLI |
| **Database** | Insert row via psycopg / sqlalchemy |

Always persist the raw Claude response AND the structured output separately — the raw response is your audit trail.

### 5. Wake-up-to-result pipeline

```python
async def scheduled_routine(prompt: str, output_path: str):
    response = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system="You are a research analyst. Complete the assigned task and return structured output.",
        messages=[{"role": "user", "content": prompt}]
    )

    result = {
        "run_at": datetime.utcnow().isoformat(),
        "prompt": prompt,
        "output": response.content[0].text,
        "tokens_used": response.usage.input_tokens + response.usage.output_tokens
    }

    Path(output_path).write_text(json.dumps(result, indent=2))
    return result
```

---

## Run it

```bash
# Run a one-off scheduled task now
python scheduled_routine.py --task "Summarize today's top AI news" --output ./outputs/

# Register a recurring routine (cron)
python cron_agent.py register --name weekly-summary --prompt "..." --schedule "0 7 * * 1"

# List registered routines
python cron_agent.py list

# Run a registered routine immediately (for testing)
python cron_agent.py run --name weekly-summary
```

Expected output after a run:

```
[2026-06-22T07:00:01Z] weekly-summary started
[2026-06-22T07:00:14Z] Claude responded (1842 tokens)
[2026-06-22T07:00:14Z] Result written to ./outputs/2026-06-22-weekly-summary.json
[2026-06-22T07:00:15Z] Email sent to team@company.com
[2026-06-22T07:00:15Z] weekly-summary completed (14s)
```

---

## Walk-through

### What makes a good scheduled prompt

| Trait | Bad | Good |
|---|---|---|
| **Time-anchored** | "Summarize AI news" | "Summarize AI news from the past 7 days" |
| **Self-contained** | Assumes context from last run | Fully specifies scope each run |
| **Structured output** | "Give me a summary" | "Return JSON with keys: breakthroughs, industry_news, trend_to_watch" |
| **Idempotent** | Side effects on every run | Check-before-act pattern |

### Cost estimation

Before scheduling, estimate:

```python
# Rough estimate: input tokens × model rate
# Claude Opus 4.7: ~$15/MTok input, ~$75/MTok output
# A typical summary task: ~2000 tokens input, ~1000 tokens output
# Daily cost: (2000 × $0.000015) + (1000 × $0.000075) = $0.105/day ≈ $3.15/month
```

For high-frequency routines, use Claude Haiku 4.5 (~15× cheaper) unless the task needs deep reasoning.

### Monitoring scheduled routines

```python
def alert_on_failure(task_name: str, error: Exception):
    # Send to Slack on failure
    requests.post(os.environ["SLACK_WEBHOOK"], json={
        "text": f"❌ Scheduled routine `{task_name}` failed: {str(error)}"
    })
```

Always instrument: task start, task complete, token usage, output path, any errors.

---

## Try this

1. **Morning digest** — schedule "every day at 7am, find the top 5 AI-related HN posts and save to `./digests/YYYY-MM-DD.md`." Read the output over coffee.
2. **Competitor monitor** — schedule weekly: "Fetch [competitor pricing page URL], extract all plan names and prices, compare to last week's file in `./competitor/`, alert if anything changed."
3. **Cost tracking** — extend `scheduled_routine.py` to accumulate token usage in a CSV. After a week, open the CSV and see what each routine actually costs.
4. **Chaining routines** — routine A produces a JSON file; routine B (runs 1 hour later) reads that file and sends a formatted summary. Build a two-step pipeline.
5. **Combine with Session 42** — schedule the browser agent from Session 42 to run nightly: "Check our status page and write a health report to `./status/YYYY-MM-DD.md`."

---

## Mental model in one line

> **Scheduled routines decouple you from the trigger — you write the prompt and the schedule once, Claude runs idempotently on each fire, and results persist to a stable location you check when convenient.**

---

## Related

- **Previous:** [42 — Browser Automation & Computer Use](42-browser-automation.md)
- **Next:** [44 — Document & Slide Generation](44-document-slide-generation.md)
- **Pairs with:** [42 — Browser Automation](42-browser-automation.md) (schedule browser tasks)
- **Uses concepts from:** [39 — Claude Code Hooks](39-claude-code-hooks.md) (pre/post hooks around scheduled runs)
- **Maps to image feature:** #08 — Schedule Cloud Routines Overnight
- **Curriculum tracker:** Session 43 of 45
