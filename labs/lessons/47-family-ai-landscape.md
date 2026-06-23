# 47 — Landscape: Identity, Privacy & Channels (Session 34)

> **The family is the most complex multi-stakeholder unit in consumer AI.** Children, parents, grandparents — each with different consent requirements, data rights, and access channels. WhatsApp, web, and mobile: each with different constraints. This session maps the landscape before we build.

---

## Roadmap — where this lesson sits

```
═══════ TRACK L: FAMILY AI AGENT ═══════

  ▶ Session 34: LANDSCAPE — IDENTITY, PRIVACY, CHANNELS  ◄ HERE
    Session 35: Reference Arch I — Meal + Archivist Specialists
    Session 36: Reference Arch II — Scheduler + Proactive Loop
    Session 37: Case Study + Vertical Slice Build

  Prerequisites: Sessions 18–21
  Three channels: web + mobile + WhatsApp
```

---

## Files involved

| File | Role |
|---|---|
| `family_ai/landscape.md` | Stakeholder map + channel analysis |
| `family_ai/identity_model.md` | Multi-generational identity + consent model |

---

## The multi-generational stakeholder map

A family AI agent serves multiple people simultaneously — and their interests sometimes conflict:

```
  ┌─────────────────────────────────────────────────────┐
  │                  FAMILY UNIT                         │
  ├───────────────┬───────────────┬─────────────────────┤
  │   CHILDREN    │   PARENTS     │   GRANDPARENTS       │
  │   (< 13)      │   (primary)   │   (elder)            │
  │               │               │                      │
  │ • COPPA       │ • Account     │ • Digital literacy   │
  │   applies     │   owner       │   varies             │
  │ • No direct   │ • Consent     │ • Consent capacity   │
  │   data        │   giver       │   (cognitive)        │
  │ • Filtered    │ • Privacy     │ • Voice preferred    │
  │   content     │   controller  │ • Large text         │
  └───────────────┴───────────────┴─────────────────────┘
```

**Key tension:** Parents want visibility into what their children tell the AI. Children (especially teenagers) want privacy. The system must navigate this explicitly.

---

## Regulatory framework: family-specific

### COPPA (US) — Children under 13

- Cannot collect personal data from children under 13 without verifiable parental consent
- Cannot serve targeted content based on children's data
- Must provide parental access to children's data on request
- Must allow deletion of children's data

**Technical implication:** Every user session must have an age-verified profile. Children's sessions are logged separately, with stricter data retention limits and parental visibility controls.

### GDPR (EU) — Children's data

- Article 8: age of consent for data processing is 16 (member states can lower to 13)
- Parental consent required for under-16 data processing
- Right to erasure applies especially strongly for children's data

### India — DPDP Act 2023

- Section 9: Children's data requires verifiable parental consent
- Prohibition on processing children's data that causes detrimental effect
- No behavioural tracking of children

---

## Family account model

```python
from pydantic import BaseModel
from typing import Literal
from enum import Enum

class AgeGroup(str, Enum):
    CHILD = "child"           # < 13: COPPA-protected
    TEEN = "teen"             # 13–17: limited data processing
    ADULT = "adult"           # 18+: full consent capability
    ELDER = "elder"           # 65+: cognitive consent consideration

class FamilyMember(BaseModel):
    member_id: str
    display_name: str
    age_group: AgeGroup
    preferred_channel: str    # "whatsapp" | "web" | "mobile"
    preferred_language: str
    data_consent: bool
    consent_given_by: str | None   # parent_id for children

class FamilyAccount(BaseModel):
    family_id: str
    primary_account_holder: str    # adult with billing + consent authority
    members: list[FamilyMember]
    shared_memory: bool            # whether family members can see each other's data
    children_visibility: str       # "full" | "summary" | "none" (for parents seeing children's data)

def get_data_policy(member: FamilyMember) -> dict:
    if member.age_group == AgeGroup.CHILD:
        return {
            "retention_days": 30,        # shorter retention for children
            "analytics_allowed": False,
            "content_filter": "strict",
            "parent_visibility": "full",
        }
    if member.age_group == AgeGroup.TEEN:
        return {
            "retention_days": 90,
            "analytics_allowed": False,
            "content_filter": "moderate",
            "parent_visibility": "summary",  # teens get some privacy
        }
    return {
        "retention_days": 365,
        "analytics_allowed": True,
        "content_filter": "none",
        "parent_visibility": "none",
    }
```

---

## Three-channel architecture

Each channel has fundamentally different constraints:

### Channel 1: WhatsApp (WABA)

```
Strengths:
  + High adoption (2B+ users globally; dominant in India)
  + Async messaging fits family life
  + Rich media (photos, voice notes, documents)
  + Proactive messaging (with approved templates)

Constraints:
  - 24-hour messaging window (must use templates after 24h)
  - No persistent UI (no menus, no forms, no buttons beyond quick replies)
  - Text/media only (no voice calls via API)
  - Meta approval required for templates
  - Rate limits per phone number
  - Must have a business phone number (not personal)
```

### Channel 2: Web

```
Strengths:
  + Full UI capability (forms, calendars, image upload, drag-and-drop)
  + Desktop access for meal planning, family calendar
  + Real-time streaming (SSE for AI responses)
  + No third-party approval needed

Constraints:
  - Less habitual for family communication (vs. WhatsApp)
  - Desktop-first; mobile web is secondary
  - Push notifications require browser permission
  - No native camera/photo access (upload only)
```

### Channel 3: Mobile app

```
Strengths:
  + Camera access (food photos, memory capture)
  + Push notifications (reliable)
  + Offline capability
  + Voice input (native microphone)
  + Background sync

Constraints:
  - App install friction
  - iOS/Android maintenance overhead
  - App store approval for AI features
  - IDFA/GAID deprecation limits attribution
```

---

## Who-is-asking router

The same WhatsApp message can come from different family members using the same phone:

```python
class WhoIsAskingRouter:
    """
    Identify which family member sent a message.
    Strategy 1: Separate phone numbers per member (ideal)
    Strategy 2: Name prefix ("Mom: what's for dinner?")
    Strategy 3: Voice fingerprint (future capability)
    Strategy 4: Ask on ambiguity ("Is this Mom or Dad?")
    """

    def route(self, message: str, from_number: str, family: FamilyAccount) -> FamilyMember:
        # Strategy 1: number maps to one member
        member = family.get_member_by_phone(from_number)
        if member:
            return member

        # Strategy 2: prefix detection
        for m in family.members:
            if message.lower().startswith(m.display_name.lower() + ":"):
                return m

        # Default: primary account holder
        return family.get_primary_member()
```

---

## WABA constraints: the 24-hour window

The 24-hour window is the central WABA constraint for a proactive family assistant:

```
Within 24h of family member's last message:
  ✓ Send any message (reminders, meal plans, memory shares)
  ✓ Rich media (images, documents, audio)

After 24h:
  ✗ Cannot send free-form messages
  ✓ Can send pre-approved template messages ONLY

Template examples (must be Meta-approved):
  • "Hi {{1}}! Your weekly meal plan is ready. Reply to see it."
  • "Reminder: {{1}} has {{2}} at {{3}} today."
  • "The Family Archivist found a memory from {{1}} years ago. Reply 'show' to see it."
```

**Design implication:** All proactive AI features (meal plans, reminders, memory shares) must use approved templates. The AI generates the content; the template provides the wrapper.

---

## Try this

1. **Stakeholder conflict map** — take one family AI feature (e.g., shared calendar). List every stakeholder. Where do their interests conflict? How does the system resolve each conflict?

2. **COPPA compliance check** — design the parental consent flow for adding a child under 13 to a family account. What must be collected? How is it verified? What must be accessible to parents on request?

3. **Channel capability matrix** — for each planned family AI feature, mark which channels support it. Identify features that are impossible on WhatsApp but require web or mobile app.

4. **24-hour window simulation** — build a message scheduler that respects the WABA 24-hour window. Given a list of reminders to send, determine which need templates vs. free-form. Test with a family that hasn't messaged in 48 hours.

5. **Who-is-asking test** — given a family with 4 members sharing one WhatsApp number, design and test the routing logic. What percentage of messages are unambiguously routable? What's the fallback for ambiguous messages?

---

## Mental model in one line

> **Family AI is multi-generational (children need COPPA protection, elders need accessibility), multi-channel (WhatsApp for habit, web for power, mobile for camera + notifications), and multi-stakeholder (parents control children's data; members have individual privacy from each other) — the who-is-asking router and the 24-hour WABA window are the two hardest technical constraints.**

---

## Related

- **Next:** [Session 35 — Reference Arch I: Meal + Archivist](48-meal-archivist-arch.md)
- **WhatsApp integration:** [Session 27 — Vernacular Farmer Bot](40-farmer-bot.md)
- **Multi-agent memory:** [Session 3 — Multi-agent + LTM](14-multi-agent-ltm.md)
- **Curriculum tracker:** Session 34 of 46 — Track L
