# 49 — Reference Arch II: Scheduler + Proactive Loop (Session 36)

> **The third specialist and the layer that makes the Family Concierge feel alive.** The Scheduler/Reminder Agent manages family calendar and task coordination. The proactive loop sends unprompted updates — meal plans on Sunday, reminders before appointments, "on this day" memories in the morning. No human trigger needed.

---

## Roadmap — where this lesson sits

```
═══════ TRACK L: FAMILY AI AGENT ═══════

  ✓ Session 34: Landscape — Identity, Privacy, Channels
  ✓ Session 35: Reference Arch I — Meal + Archivist Specialists
  ▶ Session 36: REFERENCE ARCH II — SCHEDULER + PROACTIVE  ◄ HERE
    Session 37: Case Study + Vertical Slice Build
```

---

## Files involved

| File | Role |
|---|---|
| `family_ai/scheduler_proactive_arch.md` | Architecture document |

---

## Scheduler / Reminder Agent

```
Capabilities:
  • Add events to shared family calendar ("Priya's dentist on Thursday 3pm")
  • Set reminders for individuals or the whole family
  • Coordinate scheduling across family members ("find time for a family dinner")
  • Query upcoming events ("what do we have this week?")
  • Integrate with Google Calendar via MCP
```

### Natural language → structured event

```python
from pydantic import BaseModel
from datetime import datetime

class FamilyEvent(BaseModel):
    event_id: str
    family_id: str
    member_ids: list[str]          # who it applies to (empty = whole family)
    title: str
    start_time: datetime
    end_time: datetime | None
    location: str | None
    reminder_minutes_before: int   # default 30
    recurrence: str | None         # "weekly" | "monthly" | None
    created_by: str                # member_id of who asked

class SchedulerAgent:
    def __init__(self, llm, calendar_mcp, family: FamilyAccount):
        self._llm = llm
        self._calendar = calendar_mcp
        self._family = family

    async def parse_and_schedule(
        self,
        utterance: str,
        speaker: FamilyMember,
        now: datetime,
    ) -> FamilyEvent:
        structured = self._llm.with_structured_output(FamilyEvent)

        event = structured.invoke([
            SystemMessage(content=(
                f"Extract a calendar event from this message. "
                f"Current time: {now.isoformat()}. "
                f"Family members: {[m.display_name for m in self._family.members]}. "
                f"Speaker: {speaker.display_name}. "
                "If a family member is named, include them in member_ids. "
                "Infer missing details from context."
            )),
            HumanMessage(content=utterance),
        ])

        # Add to Google Calendar via MCP
        await self._calendar.create_event(event)
        return event
```

### Conflict detection

```python
async def check_conflicts(
    new_event: FamilyEvent,
    calendar_mcp,
    family: FamilyAccount,
) -> list[FamilyEvent]:
    """Check if any family member has a conflicting event."""
    conflicts = []
    for member_id in new_event.member_ids:
        existing = await calendar_mcp.list_events(
            member_id=member_id,
            start=new_event.start_time,
            end=new_event.end_time or new_event.start_time,
        )
        conflicts.extend(existing)
    return conflicts
```

---

## Proactive notification engine

The proactive loop is what separates a reactive chatbot from an assistant that feels like part of the family:

```python
from dataclasses import dataclass
from typing import Callable, Awaitable

@dataclass
class ProactiveJob:
    name: str
    schedule: str                    # cron expression
    condition: Callable              # run only if this returns True
    generator: Callable[..., Awaitable[str | None]]  # returns message or None
    template_name: str | None        # WABA template for post-24h sending
    target_members: list[str]        # member_ids to notify

PROACTIVE_JOBS = [
    ProactiveJob(
        name="sunday_meal_plan",
        schedule="0 9 * * 0",        # Sunday 9am
        condition=lambda f: f.meal_planning_enabled,
        generator=generate_weekly_meal_plan_message,
        template_name="weekly_meal_plan_v1",
        target_members=["primary"],  # send to primary account holder
    ),
    ProactiveJob(
        name="morning_on_this_day",
        schedule="0 8 * * *",        # Every day 8am
        condition=lambda f: has_memories_today(f.family_id),
        generator=generate_on_this_day_message,
        template_name="on_this_day_v1",
        target_members=["all"],
    ),
    ProactiveJob(
        name="event_reminder",
        schedule="*/15 * * * *",     # Every 15 minutes
        condition=lambda f: has_upcoming_events(f.family_id, within_minutes=60),
        generator=generate_event_reminder,
        template_name="event_reminder_v1",
        target_members=["event_members"],
    ),
    ProactiveJob(
        name="weekly_family_digest",
        schedule="0 18 * * 5",       # Friday 6pm
        condition=lambda _: True,
        generator=generate_weekly_digest,
        template_name="weekly_digest_v1",
        target_members=["all"],
    ),
]
```

---

## Template management for WhatsApp

WABA templates must be pre-approved. Design them to be flexible:

```python
TEMPLATES = {
    "weekly_meal_plan_v1": {
        "name": "weekly_meal_plan_v1",
        "language": "en",
        # Variables: {{1}} = family_name, {{2}} = top_meals_preview
        "body": "Hi {{1}} family! 🍽 Your meal plan for the week is ready. "
                "Highlights: {{2}}. Reply 'meals' to see the full plan.",
    },
    "on_this_day_v1": {
        "name": "on_this_day_v1",
        "language": "en",
        # Variables: {{1}} = years_ago, {{2}} = memory_preview
        "body": "🗓 On this day {{1}} year(s) ago: {{2}} Reply 'memories' to see more.",
    },
    "event_reminder_v1": {
        "name": "event_reminder_v1",
        "language": "en",
        # Variables: {{1}} = member_name, {{2}} = event_title, {{3}} = time
        "body": "⏰ Reminder for {{1}}: {{2}} at {{3}}.",
    },
}

def fill_template(template_name: str, variables: list[str]) -> dict:
    template = TEMPLATES[template_name]
    return {
        "name": template["name"],
        "language": {"code": template["language"]},
        "components": [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": v} for v in variables
            ],
        }],
    }
```

---

## Family Concierge supervisor

The Concierge routes incoming messages to the right specialist:

```python
from enum import Enum

class Intent(str, Enum):
    MEAL = "meal"
    MEMORY = "memory"
    SCHEDULE = "schedule"
    GENERAL = "general"

class FamilyConcierge:
    def __init__(self, meal_agent, archivist, scheduler, llm):
        self._agents = {
            Intent.MEAL: meal_agent,
            Intent.MEMORY: archivist,
            Intent.SCHEDULE: scheduler,
        }
        self._llm = llm

    async def route(self, message: str, member: FamilyMember) -> str:
        # Fast intent classification
        intent = self._classify_intent(message)

        if intent in self._agents:
            return await self._agents[intent].handle(message, member)

        # General conversation
        return await self._general_response(message, member)

    def _classify_intent(self, message: str) -> Intent:
        msg = message.lower()
        if any(k in msg for k in ["meal", "recipe", "cook", "dinner", "lunch", "breakfast", "food", "grocery"]):
            return Intent.MEAL
        if any(k in msg for k in ["remember", "photo", "memory", "when did", "years ago", "archive"]):
            return Intent.MEMORY
        if any(k in msg for k in ["remind", "schedule", "appointment", "meeting", "calendar", "when is"]):
            return Intent.SCHEDULE
        return Intent.GENERAL
```

Fast keyword-based routing for 90% of messages. Reserve LLM-based classification for the ambiguous 10%.

---

## Try this

1. **Natural language scheduling** — test 10 scheduling utterances ("Priya has football practice every Tuesday at 4pm", "Family dinner Saturday 7pm, all of us"). Verify the parser extracts correct member_ids, times, and recurrence.

2. **Conflict detection** — add 5 events to the calendar. Add a 6th that conflicts with one of them. Verify the conflict is detected and the right family member is notified.

3. **Proactive loop** — implement the Sunday meal plan job. Seed the family with dietary preferences. Run the job. Verify the message is formatted as a valid WABA template.

4. **Template approval simulation** — write 3 WABA templates for the Family Concierge. Review them against Meta's template guidelines (no promotional language, clear variable placeholders, under 1,024 characters). Would they pass approval?

5. **Intent routing accuracy** — test 20 messages across all intent categories. Measure routing accuracy of the keyword classifier. Where does it fail? Add patterns to fix the failures.

---

## Mental model in one line

> **The Scheduler + Proactive Loop adds time-awareness to the Family Concierge: the scheduler converts natural language to calendar events (conflict-aware), and the proactive engine fires WABA templates on cron schedules (meal plans, reminders, memories) — the Concierge supervisor routes incoming messages to the right specialist in < 50ms using keyword classification.**

---

## Related

- **Previous:** [Session 35 — Reference Arch I: Meal + Archivist](48-meal-archivist-arch.md)
- **Next:** [Session 37 — Case Study + Vertical Slice Build](50-family-ai-case-study.md)
- **WhatsApp constraints:** [Session 34 — Family AI Landscape](47-family-ai-landscape.md)
- **Scheduled routines:** [Session 43 — Scheduled Cloud Routines](43-scheduled-cloud-routines.md)
- **Multi-agent supervisor pattern:** [Session 3 — Multi-agent + LTM](14-multi-agent-ltm.md)
- **Curriculum tracker:** Session 36 of 46 — Track L
