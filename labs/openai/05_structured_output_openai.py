from typing import Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()


class EmailTriage(BaseModel):
    """Triage information extracted from an email."""

    summary: str = Field(description="One-sentence summary of what the email is about.")
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        description="How urgently the recipient should respond, based on tone and content."
    )
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        description="Overall emotional tone of the sender."
    )
    requires_response: bool = Field(
        description="True if the email expects a reply, false if it is purely informational."
    )
    action_items: list[str] = Field(
        description="Concrete next steps the recipient must take. Empty list if none."
    )
    estimated_response_time_minutes: int = Field(
        description="Rough time the recipient should budget to read, decide, and reply."
    )


model = ChatOpenAI(model="gpt-4o", temperature=0)
extractor = model.with_structured_output(EmailTriage)


email_1 = """\
Subject: URGENT — production billing pipeline is dropping events

Hi team,

We're seeing a 30% drop in billed events since the deploy at 14:00 UTC. The
on-call rotation just got paged. I need someone to roll back the billing-worker
service to commit 8a3f12 ASAP and confirm event counts recover before EOD. Also
please post in #incidents with status updates every 15 minutes until resolved.

This is blocking month-end revenue recognition. We need eyes on it now.

Thanks,
Priya
"""

email_2 = """\
Subject: Quick question — your thoughts on the offsite venue?

Hey!

Hope you're having a good week. Wanted to get your take on the two venue
options for the team offsite in October — the lakeside lodge or the downtown
hotel. No rush, just curious which you'd lean toward when you have a sec.

Cheers,
Marco
"""


# ---- Single extraction ------------------------------------------------------

print("=" * 60)
print("Email 1 — extraction")
print("=" * 60)
result_1: EmailTriage = extractor.invoke(email_1)

# Pretty-print every field at once
print(result_1.model_dump_json(indent=2))

# Type-safe attribute access — IDE autocompletes these, mypy validates them
print("\nDirect field access:")
print(f"  priority         : {result_1.priority}")
print(f"  requires_response: {result_1.requires_response}")
print(f"  first action item: {result_1.action_items[0]}")
print(f"  type of priority : {type(result_1.priority).__name__}")


# ---- Same extractor, different email ---------------------------------------

print("\n" + "=" * 60)
print("Email 2 — extraction")
print("=" * 60)
result_2: EmailTriage = extractor.invoke(email_2)
print(result_2.model_dump_json(indent=2))


# ---- Batched (parallel) extraction over a list of emails -------------------

# .batch() is the same Runnable interface from earlier — works on the typed
# extractor too. Both emails go to Claude concurrently; results come back as
# a list of EmailTriage instances.
print("\n" + "=" * 60)
print("Batch extraction over both emails (parallel)")
print("=" * 60)
batch_results: list[EmailTriage] = extractor.batch([email_1, email_2])
for i, r in enumerate(batch_results, start=1):
    print(f"\nEmail {i}:")
    print(f"  priority = {r.priority:<8}  sentiment = {r.sentiment:<8}  "
          f"requires_response = {r.requires_response}")
    print(f"  summary  = {r.summary}")
