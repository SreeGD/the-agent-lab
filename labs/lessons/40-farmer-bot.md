# 40 — Case Study: Vernacular Farmer Bot (Session 27)

> **Build a WhatsApp-first farmer assistant for Tier 2/3 India.** Voice in, photo in, Telugu/Hindi out — with ₹-paise unit economics and trust calibration for a population that has been misled by agricultural advice before.

---

## Roadmap — where this lesson sits

```
═══════ TRACK I: AGRICULTURE ═══════

  ✓ Session 25: AgriTech AI Landscape
  ✓ Session 26: Reference Arch — Crop Diagnostic + Advisory
  ▶ Session 27: CASE STUDY — VERNACULAR FARMER BOT  ◄ HERE
```

---

## Files involved

| File | Role |
|---|---|
| `agritech/farmer_bot/whatsapp_adapter.py` | WhatsApp Business API integration |
| `agritech/farmer_bot/conversation_manager.py` | Multi-turn conversation state |
| `agritech/farmer_bot/trust_calibration.py` | Uncertainty expression + escalation |
| `agritech/farmer_bot/cost_tracker.py` | Per-query cost monitoring |

---

## The target user

**Raju, 38, paddy farmer, Nalgonda district, Telangana**
- 2.5 acre farm; rain-fed; one crop per year
- Smartphone (Android, 4G but often on 2G)
- Reads Telugu; basic English recognition
- WhatsApp: daily; YouTube: farming videos; no app installs for new tools
- Has been given wrong advice by input dealers who had products to sell
- Does not trust "AI" but trusts other farmers and extension officers
- Makes a farming decision worth ₹15,000–50,000 per season

This is the user the bot must serve. Every design decision flows from this profile.

---

## WhatsApp Business API integration

```python
import httpx
from pydantic import BaseModel

class WAMessage(BaseModel):
    from_number: str       # farmer's WhatsApp number
    message_type: str      # "text" | "image" | "audio" | "document"
    text: str | None
    media_id: str | None   # for image/audio
    timestamp: int

class WAAdapter:
    def __init__(self, phone_number_id: str, access_token: str):
        self._base = f"https://graph.facebook.com/v18.0/{phone_number_id}"
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def send_text(self, to: str, text: str):
        await httpx.AsyncClient().post(
            f"{self._base}/messages",
            headers=self._headers,
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text[:4096]},  # WA limit
            },
        )

    async def download_media(self, media_id: str) -> bytes:
        # Step 1: Get media URL
        r = await httpx.AsyncClient().get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers=self._headers,
        )
        media_url = r.json()["url"]
        # Step 2: Download
        r2 = await httpx.AsyncClient().get(media_url, headers=self._headers)
        return r2.content
```

**WABA constraints to design around:**
- 24-hour messaging window: can only send messages within 24h of farmer's last message (or use approved templates)
- Template messages: pre-approved for proactive outreach (weather alerts, mandi prices)
- Media limits: images < 5MB, audio < 16MB
- Rate limits: 1,000 messages/second per phone number

---

## Conversation state management

Farmer conversations are multi-turn and context-dependent:

```python
from enum import Enum
from pydantic import BaseModel

class ConversationState(str, Enum):
    GREETING = "greeting"
    AWAITING_PHOTO = "awaiting_photo"
    DIAGNOSIS_DONE = "diagnosis_done"
    AWAITING_FOLLOWUP = "awaiting_followup"
    CLOSED = "closed"

class FarmerSession(BaseModel):
    farmer_id: str              # hashed phone number
    language: str               # "te", "hi", "kn", ...
    state: ConversationState
    crop_context: str | None    # detected crop from photo
    disease_context: str | None
    last_diagnosis: dict | None
    message_count: int
    session_start: str          # ISO timestamp
    last_message: str           # ISO timestamp

# Sessions expire after 24 hours (WABA window)
# Use Redis with TTL = 24h
```

---

## Trust calibration

Raju has been given bad advice before. The bot must never overclaim:

```python
TRUST_RULES = {
    "high_confidence": (0.85, 1.0,
        "This looks like {disease}. Here's what I recommend:"),
    "medium_confidence": (0.60, 0.85,
        "This could be {disease}, but I'm not fully certain. "
        "The treatment below is safe for this type of problem:"),
    "low_confidence": (0.0, 0.60,
        "I can see there's a problem with your {crop}, but I'm not sure "
        "what it is from this photo. Please:\n"
        "1. Share a closer photo of the affected leaf\n"
        "2. Or visit your nearest KVK for an expert opinion\n\n"
        "Do not apply any treatment until you know the problem."),
}

def calibrate_response(diagnosis, advisory) -> str:
    conf = diagnosis.confidence
    for level, (low, high, template) in TRUST_RULES.items():
        if low <= conf < high:
            return template.format(
                disease=diagnosis.disease_identified or "unknown disease",
                crop=diagnosis.crop_identified,
            )
```

**Why this matters:** A farmer who applies the wrong pesticide because the bot was overconfident loses ₹5,000–15,000 and potentially their crop. Trust calibration is not a UX nicety — it is risk management.

---

## Escalation triggers

```python
ESCALATION_TRIGGERS = [
    # Conditions requiring expert human
    lambda d: d.confidence < 0.60,
    lambda d: d.severity == "severe" and d.affected_area_percent > 50,
    lambda d: d.disease_identified in HIGH_RISK_DISEASES,  # e.g., bacterial blight
    # Farmer explicitly asks
    lambda _, q: "expert" in q.lower() or "officer" in q.lower(),
]

ESCALATION_RESPONSE_TE = (
    "మీ పంటలో తీవ్రమైన సమస్య ఉన్నట్లు కనిపిస్తోంది. "
    "దయచేసి మీ దగ్గరలోని KVK (కృషి విజ్ఞాన కేంద్రం)ని సంప్రదించండి:\n"
    "📞 KVK Nalgonda: 08682-244321\n"
    "🕐 సమయం: 9am–5pm, సోమ–శని"
)
# "It appears there's a serious problem with your crop. 
#  Please contact your nearest KVK..."
```

---

## Unit economics implementation

```python
import time
from dataclasses import dataclass

@dataclass
class QueryCost:
    whisper_seconds: float = 0.0     # ₹0 (on-device)
    vision_tokens: int = 0           # claude-opus-4-7 vision
    text_tokens_in: int = 0          # claude-sonnet-4-6
    text_tokens_out: int = 0
    translation_chars: int = 0       # Google Translate API

    @property
    def total_inr(self) -> float:
        # Approximate rates (2026)
        OPUS_IN = 0.001125    # ₹/1k tokens (vision)
        SONNET_IN = 0.000225  # ₹/1k tokens
        SONNET_OUT = 0.001125
        TRANSLATE = 0.0000015 # ₹/char
        return (
            self.vision_tokens * OPUS_IN / 1000
            + self.text_tokens_in * SONNET_IN / 1000
            + self.text_tokens_out * SONNET_OUT / 1000
            + self.translation_chars * TRANSLATE
        )

# Target: < ₹0.10 per query (₹3/month for 1 query/day)
# If cost > ₹0.15: route to cheaper model or cached response
```

**Model routing for cost:**

```python
def select_model(query_type: str, has_image: bool) -> str:
    if has_image:
        return "claude-opus-4-7"     # vision required
    if query_type in ("mandi_price", "weather", "simple_faq"):
        return "claude-haiku-4-5-20251001"  # cheap for simple queries
    return "claude-sonnet-4-6"       # default
```

---

## Proactive alerts (template messages)

Farmers don't always remember to ask. Proactive alerts add value:

```python
# Pre-approved WABA templates (must be approved by Meta)
ALERT_TEMPLATES = {
    "weather_warning": {
        "name": "weather_alert_v1",
        "language": "te",
        "components": [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": "{district}"},   # "Nalgonda"
                {"type": "text", "text": "{alert_type}"}, # "భారీ వర్షం"
                {"type": "text", "text": "{advice}"},     # "పంట నీరు తీయండి"
            ]
        }]
    }
}

# Triggered by weather API: if IMD issues heavy rain warning for farmer's district
async def send_weather_alert(farmer_id: str, district: str, alert_type: str, advice: str):
    await wa_adapter.send_template(
        to=get_farmer_phone(farmer_id),
        template=ALERT_TEMPLATES["weather_warning"],
        parameters=[district, alert_type, advice],
    )
```

---

## Try this

1. **WhatsApp webhook** — set up the WABA webhook locally (use ngrok). Send a test message. Log the raw JSON payload. Understand the message structure before building the adapter.

2. **Trust calibration A/B** — generate 10 advisories at different confidence levels. Show them to a non-technical person. Ask: "Would you act on this?" Compare high-confidence vs. low-confidence framing responses.

3. **₹ unit economics** — instrument a test run of 20 queries (mix of image + text + voice). Calculate the actual cost using the QueryCost class. What's the cheapest query type? The most expensive?

4. **Template message** — draft a WABA-compliant weather alert template for Tamil Nadu farmers in Tamil. Follow Meta's template guidelines (no promotional language, clear variables). Submit it for approval (or mock the approval flow).

5. **Offline simulation** — disconnect network mid-conversation. Verify the bot falls back to the offline cache and queues outbound messages. Reconnect. Verify queued messages send correctly.

---

## Mental model in one line

> **The vernacular farmer bot is a WhatsApp adapter + multi-turn session state + trust-calibrated responses (never overclaim to a farmer who trusts you with their livelihood) + proactive template alerts + ₹-paise cost routing — designed for 2G, Telugu, and a farmer who has been burned by bad advice before.**

---

## Related

- **Previous:** [Session 26 — Reference Arch: Crop Diagnostic](39-crop-diagnostic.md)
- **Next:** [Session 28 — FinTech AI Landscape](41-fintech-landscape.md)
- **AgriTech capstone:** [Session 34 — Farm Planner](34-farm-planner.md)
- **Proactive scheduling:** [Session 43 — Scheduled Cloud Routines](43-scheduled-cloud-routines.md)
- **Curriculum tracker:** Session 27 of 46 — Track I capstone
