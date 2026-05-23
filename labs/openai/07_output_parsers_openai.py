"""Output-parsers showcase.

One movie review, six parsers. Each demonstrates a different concept:
  1. StrOutputParser                  — the baseline
  2. CommaSeparatedListOutputParser   — format-instructions pattern
  3. JsonOutputParser                 — dict output + streaming
  4. PydanticOutputParser             — typed output the OLD way
  5. Custom YamlOutputParser          — extensibility escape hatch
  6. OutputFixingParser               — error recovery via 2nd LLM call

Compare parser 4 here against `structured.py` for the
PydanticOutputParser vs with_structured_output contrast.
"""

import asyncio

import yaml
from dotenv import load_dotenv
from langchain.output_parsers import OutputFixingParser
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import (
    BaseOutputParser,
    CommaSeparatedListOutputParser,
    JsonOutputParser,
    PydanticOutputParser,
    StrOutputParser,
)
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

model = ChatOpenAI(model="gpt-4o", temperature=0)


REVIEW = """\
Blade Runner 2049 is a stunning visual achievement — Roger Deakins' cinematography
turns every frame into a painting. The pacing is deliberate, almost meditative,
which some will find slow but I found mesmerizing. Ryan Gosling carries the
emotional weight as K, a replicant detective grappling with identity and memory.
The story builds on the original's themes of what it means to be human while
introducing genuinely new questions about consciousness and free will. The
synth-heavy score by Hans Zimmer and Benjamin Wallfisch perfectly matches the
melancholy tone. My one complaint: at 163 minutes, a few scenes could have been
trimmed without losing impact. Overall: a rare sequel that honors and expands
on its predecessor. I'd give it a 9/10.
"""


# =====================================================================
# PARSER 1 — StrOutputParser: the baseline
# =====================================================================
print("=" * 68)
print("PARSER 1: StrOutputParser  (unwrap AIMessage.content)")
print("=" * 68)

summary_chain = (
    ChatPromptTemplate.from_messages(
        [("human", "Summarize this movie review in one sentence:\n\n{review}")]
    )
    | model
    | StrOutputParser()
)
summary = summary_chain.invoke({"review": REVIEW})
print(f"\nResult ({type(summary).__name__}): {summary}")


# =====================================================================
# PARSER 2 — CommaSeparatedListOutputParser: format-instructions pattern
# =====================================================================
print("\n" + "=" * 68)
print("PARSER 2: CommaSeparatedListOutputParser  (format-instructions)")
print("=" * 68)

csv_parser = CommaSeparatedListOutputParser()

print("\nAuto-generated format_instructions:")
print(f"  {csv_parser.get_format_instructions()}")

themes_chain = (
    ChatPromptTemplate.from_messages(
        [
            (
                "human",
                "List 3-5 major themes in this review.\n\n{review}\n\n{format_instructions}",
            )
        ]
    ).partial(format_instructions=csv_parser.get_format_instructions())
    | model
    | csv_parser
)

themes = themes_chain.invoke({"review": REVIEW})
print(f"\nResult ({type(themes).__name__}): {themes}")


# =====================================================================
# PARSER 3 — JsonOutputParser: dict output + streaming
# =====================================================================
print("\n" + "=" * 68)
print("PARSER 3: JsonOutputParser  (with .astream() streaming)")
print("=" * 68)

json_parser = JsonOutputParser()

json_chain = (
    ChatPromptTemplate.from_messages(
        [
            (
                "human",
                "Extract this review as JSON with keys: "
                '"rating" (int 1-10), "pros" (list[str]), "cons" (list[str]).\n\n'
                "Review:\n{review}\n\n{format_instructions}",
            )
        ]
    ).partial(format_instructions=json_parser.get_format_instructions())
    | model
    | json_parser
)


async def stream_json_demo():
    print("\nStreaming partial dicts as model generates:")
    prev = None
    chunks = 0
    async for chunk in json_chain.astream({"review": REVIEW}):
        if chunk != prev:  # JsonOutputParser yields the same dict if no new field arrived
            print(f"  chunk {chunks + 1}: {chunk}")
            chunks += 1
            prev = chunk
    print(f"\nTotal distinct partial dicts: {chunks}")
    print("(Each chunk is the JSON-so-far parsed into a usable dict.)")


asyncio.run(stream_json_demo())


# =====================================================================
# PARSER 4 — PydanticOutputParser: typed output the OLD way
# =====================================================================
print("\n" + "=" * 68)
print("PARSER 4: PydanticOutputParser  (vs with_structured_output)")
print("=" * 68)


class ReviewAnalysis(BaseModel):
    rating: int = Field(description="Score from 1 to 10")
    sentiment: str = Field(description="One of: positive, mixed, negative")
    standout_aspects: list[str] = Field(description="What the reviewer praised most")
    weaknesses: list[str] = Field(description="What the reviewer criticized")
    recommends: bool = Field(description="Would the reviewer recommend this movie?")


pydantic_parser = PydanticOutputParser(pydantic_object=ReviewAnalysis)

print(
    f"\nAuto-generated format_instructions: "
    f"{len(pydantic_parser.get_format_instructions())} chars of JSON-schema prompt"
)
print("(These tokens go into every prompt — model.with_structured_output puts")
print(" the schema in the tools field instead, slightly more token-efficient.)")

pydantic_chain = (
    ChatPromptTemplate.from_messages(
        [("human", "Analyze this movie review:\n\n{review}\n\n{format_instructions}")]
    ).partial(format_instructions=pydantic_parser.get_format_instructions())
    | model
    | pydantic_parser
)

analysis: ReviewAnalysis = pydantic_chain.invoke({"review": REVIEW})
print(f"\nResult ({type(analysis).__name__}):")
print(analysis.model_dump_json(indent=2))
print("\nDirect typed attribute access:")
print(f"  analysis.rating     = {analysis.rating}  ({type(analysis.rating).__name__})")
print(f"  analysis.recommends = {analysis.recommends}  ({type(analysis.recommends).__name__})")


# =====================================================================
# PARSER 5 — Custom YamlOutputParser: subclass BaseOutputParser
# =====================================================================
print("\n" + "=" * 68)
print("PARSER 5: Custom YamlOutputParser  (extensibility)")
print("=" * 68)


class YamlOutputParser(BaseOutputParser):
    """Parse YAML-formatted LLM output into a Python dict."""

    def parse(self, text: str) -> dict:
        text = text.strip()
        # Some models wrap YAML in code fences — strip them
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        return yaml.safe_load(text)

    def get_format_instructions(self) -> str:
        return (
            "Respond in valid YAML format with 2-space indentation. "
            "Do not wrap your response in code fences. Do not add commentary."
        )


yaml_parser = YamlOutputParser()

yaml_chain = (
    ChatPromptTemplate.from_messages(
        [
            (
                "human",
                "Summarize this review as YAML with keys 'one_liner', 'verdict', "
                "and 'rating' (1-10).\n\n{review}\n\n{format_instructions}",
            )
        ]
    ).partial(format_instructions=yaml_parser.get_format_instructions())
    | model
    | yaml_parser
)

yaml_result = yaml_chain.invoke({"review": REVIEW})
print(f"\nResult ({type(yaml_result).__name__}): {yaml_result}")


# =====================================================================
# PARSER 6 — OutputFixingParser: recover from malformed output
# =====================================================================
print("\n" + "=" * 68)
print("PARSER 6: OutputFixingParser  (recovery via 2nd LLM call)")
print("=" * 68)

# Deliberately broken: missing closing brace, `yes` instead of `true`
malformed = (
    '{"rating": 9, "sentiment": "positive", '
    '"standout_aspects": ["visuals", "score"], '
    '"weaknesses": ["length"], "recommends": yes'
)
print(f"\nMalformed input:\n  {malformed}")

print("\nStep 1 — feed it to bare PydanticOutputParser:")
try:
    pydantic_parser.parse(malformed)
except Exception as e:
    print(f"  → FAILED ({type(e).__name__}): {str(e)[:80]}...")

print("\nStep 2 — wrap with OutputFixingParser (allows a fix-up LLM call):")
fixing_parser = OutputFixingParser.from_llm(parser=pydantic_parser, llm=model)
fixed: ReviewAnalysis = fixing_parser.parse(malformed)
print(f"  → SUCCESS ({type(fixed).__name__})")
print(f"  fixed.rating     = {fixed.rating}")
print(f"  fixed.recommends = {fixed.recommends}  (model converted 'yes' → True)")

print("\n" + "=" * 68)
print("All six parsers ran. See NOTES.md → 'Reference: Output Parsers'")
print("=" * 68)
