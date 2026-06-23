# 50 — Case Study: Family Concierge Vertical Slice Build (Session 37)

> **The most complex vertical in the curriculum.** Reverse-engineer Ohai.ai, Maya, and Alexa Routines. Build the Family Concierge with three specialist agents, a WhatsApp adapter, and cost engineering. This is Track L's capstone.

---

## Roadmap — where this lesson sits

```
═══════ TRACK L: FAMILY AI AGENT ═══════

  ✓ Session 34: Landscape — Identity, Privacy, Channels
  ✓ Session 35: Reference Arch I — Meal + Archivist Specialists
  ✓ Session 36: Reference Arch II — Scheduler + Proactive Loop
  ▶ Session 37: CASE STUDY — VERTICAL SLICE BUILD  ◄ HERE  (Track L capstone)
```

---

## Files involved

| File | Role |
|---|---|
| `family_ai/family_concierge/concierge.py` | Main concierge + supervisor |
| `family_ai/family_concierge/whatsapp.py` | WABA adapter |
| `family_ai/family_concierge/specialists.py` | Three specialist agents |
| `family_ai/family_concierge/cost_tracker.py` | Per-family cost monitoring |

---

## Reverse engineering: what the market leaders do

### Ohai.ai
- **Core idea:** AI-powered family assistant with shared memory across household members
- **Key feature:** Proactive "family pulse" — surfaces things the family cares about without prompting
- **Architecture signal:** Shared memory graph across household, not per-user silos
- **What to steal:** Household-level memory schema with per-member privacy controls

### Maya (by Anthropic)
- **Core idea:** Personal AI with memory, scheduling, and proactive recommendations
- **Key feature:** Deep personalisation from long-term interaction history
- **Architecture signal:** Single LLM with rich long-term context, not specialist routing
- **What to steal:** Progressive personalisation — the assistant gets smarter the more you use it

### Alexa Routines / Google Home
- **Core idea:** Trigger → action automation for the home
- **Key feature:** Multi-step routines ("Good morning" → weather + calendar + news)
- **Architecture signal:** Declarative automation rules, not conversational AI
- **What to steal:** Routine templates as the proactive notification model

### The synthesis: what we build differently

| Feature | Market approach | Our approach |
|---|---|---|
| Memory | Per-user (Alexa) or black box (Maya) | Explicit shared FamilyMemoryStore with member privacy |
| Specialists | Monolithic (Google Home) | Routed specialists (Meal, Archivist, Scheduler) |
| Proactive | Rule-based (Alexa Routines) | LLM-generated + WABA template delivery |
| Channel | Native app (Ohai) | WhatsApp-first + web fallback |
| Cost | Subscription (Ohai/Maya) | ₹-paise engineered per family |

---

## The vertical slice: what we build

A working Family Concierge that:
1. Receives WhatsApp messages from family members
2. Routes to the right specialist (Meal, Archivist, or Scheduler)
3. Returns responses within 5 seconds
4. Sends proactive weekly meal plans and "on this day" memories
5. Costs under ₹5/family/month at 20 messages/day

---

## Full system wiring

```python
import asyncio
from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI()

# Initialise components
memory_store = FamilyMemoryStore(persist_dir="./family_memories")
meal_agent = MealSpecialist(memory_store)
archivist = FamilyArchivist(memory_store)
scheduler = SchedulerAgent(calendar_mcp=google_calendar_mcp)
concierge = FamilyConcierge(meal_agent, archivist, scheduler)
wa = WAAdapter(phone_number_id=PHONE_NUMBER_ID, access_token=WA_TOKEN)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    payload = await request.json()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for message in change.get("value", {}).get("messages", []):
                asyncio.create_task(handle_message(message))

    return {"status": "ok"}

async def handle_message(raw_message: dict):
    wa_msg = WAMessage(**parse_wa_message(raw_message))
    family = await load_family_by_phone(wa_msg.from_number)
    member = identify_member(wa_msg, family)

    # Handle media
    if wa_msg.message_type == "image":
        media = await wa.download_media(wa_msg.media_id)
        query = f"[photo] {wa_msg.text or 'No caption'}"
        await archivist.archive_photo(media, wa_msg.text, member.member_id, family.family_id)
        response = "Photo saved to your family archive! 📸"

    elif wa_msg.message_type == "audio":
        media = await wa.download_media(wa_msg.media_id)
        transcription, _ = transcribe_voice(media)
        query = transcription
        response = await concierge.route(query, member)

    else:
        query = wa_msg.text
        response = await concierge.route(query, member)

    await wa.send_text(wa_msg.from_number, response)
    await log_interaction(family.family_id, member.member_id, query, response)
```

---

## Cost engineering to ₹5/family/month

```
Target: ₹5/family/month at 20 messages/day (600/month)
Budget: ₹5 / 600 = ₹0.0083 per message

Message routing cost breakdown:
  Intent classification (Haiku):  ₹0.001
  Specialist response (Sonnet):   ₹0.006
  Total per message:              ₹0.007 ✓ (under budget)

Proactive message costs:
  Weekly meal plan (Sonnet, 1k tokens): ₹0.003/week = ₹0.012/month
  On this day (retrieval only):          ₹0.001/day  = ₹0.031/month
  Weekly digest (Sonnet):               ₹0.003/week  = ₹0.012/month

Total monthly cost per family:
  600 messages × ₹0.007 = ₹4.20
  Proactive messages:     ₹0.06
  Total:                  ≈ ₹4.26 ✓
```

**Key cost levers:**
1. Intent classification with Haiku (not Sonnet) saves ~70% on routing
2. Cache meal plans per family per week (generated once, served all week)
3. "On this day" is pure retrieval — no LLM needed for existing memories
4. Batch non-urgent queries (grocery list generation, weekly digest)

---

## WhatsApp conversation design

WhatsApp UX is fundamentally different from web chat. Key principles:

```
1. One question, one answer — no multi-part responses
2. Under 500 characters per message (longer = unread)
3. Emoji for visual scanning (⏰ 📷 🍽 ✅)
4. No markdown — it renders as raw asterisks on some phones
5. Quick reply buttons for simple choices (WhatsApp quick replies, max 3)
6. Always acknowledge receipt immediately (typing indicator via API)
```

```python
def format_for_whatsapp(response: str) -> str:
    # Strip markdown
    response = re.sub(r'\*\*(.+?)\*\*', r'\1', response)
    response = re.sub(r'#{1,6} ', '', response)

    # Truncate if too long
    if len(response) > 800:
        response = response[:780] + "... Reply 'more' for the rest."

    return response
```

---

## Testing the full system

```python
# End-to-end test scenarios
TEST_CONVERSATIONS = [
    {
        "description": "Meal planning request",
        "messages": [
            ("primary", "What should we have for dinner tonight?"),
            # Expected: meal suggestion respecting dietary profile
        ],
    },
    {
        "description": "Photo archiving",
        "messages": [
            ("primary", "[photo with caption: Priya's first day of school]"),
            # Expected: "Photo saved to your family archive!"
        ],
    },
    {
        "description": "Event scheduling with conflict",
        "messages": [
            ("primary", "Priya has football practice Saturday 4pm"),
            # Expected: schedules event; checks for conflicts
        ],
    },
    {
        "description": "Memory retrieval",
        "messages": [
            ("teen", "remember when we went to Ooty?"),
            # Expected: retrieves relevant family memories
        ],
    },
    {
        "description": "Child message (COPPA)",
        "from_member": "child",
        "messages": [
            ("child", "Can you show me funny videos?"),
            # Expected: content filter applies; no YouTube links
        ],
    },
]
```

---

## Try this

1. **Reverse engineer Ohai** — sign up for Ohai.ai (or review their public demos). Map their features to the architecture components from Sessions 34–36. What does Ohai do that this architecture doesn't? What vice versa?

2. **Full message flow** — run the webhook handler against 10 test messages (text, image, audio). Verify each reaches the right specialist and returns a response under 5 seconds.

3. **Cost measurement** — instrument all LLM calls for one week of simulated family usage (20 messages/day). Calculate actual cost. Compare to the ₹5/month target. What's the biggest cost driver?

4. **WhatsApp UX test** — send the system's responses to yourself on WhatsApp. Read them as a family member would. Are any too long? Do any use markdown that renders badly? Reformat the worst offenders.

5. **Proactive loop test** — trigger the Sunday meal plan job manually. Verify it: generates a plan, formats as a WABA template, logs the send, and doesn't re-send if already sent today.

---

## Mental model in one line

> **The Family Concierge is three specialists (Meal, Archivist, Scheduler) orchestrated by a keyword-routing supervisor, delivered via a WABA adapter with proactive template messages — cost-engineered to ₹5/family/month by routing intent classification to Haiku, caching weekly meal plans, and using retrieval-only (no LLM) for "on this day" memory surfacing.**

---

## Related

- **Previous:** [Session 36 — Reference Arch II: Scheduler + Proactive Loop](49-scheduler-proactive.md)
- **Next:** [Session 38 — CLAUDE.md + Settings (Track M)](38-claude-md-settings.md)
- **WhatsApp adapter:** [Session 27 — Vernacular Farmer Bot](40-farmer-bot.md)
- **Shared memory:** [Session 35 — Meal + Archivist](48-meal-archivist-arch.md)
- **Proactive scheduling:** [Session 43 — Scheduled Cloud Routines](43-scheduled-cloud-routines.md)
- **Curriculum tracker:** Session 37 of 46 — Track L capstone
