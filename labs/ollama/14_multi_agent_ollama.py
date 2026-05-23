# Requires: ollama serve + ollama pull llama3.2
"""Multi-agent supervisor pattern — supervisor + 3 specialists.

The trick: each specialist is a normal `create_react_agent`. Each is wrapped
as an `@tool` so the supervisor can invoke it. The supervisor itself is also
a `create_react_agent` whose "tools" happen to be other agents.

   ┌──────────────────────┐
   │     SUPERVISOR       │   ReAct agent — picks who to call
   └──────┬───────────────┘
          │
          ├──► call_researcher(query)  → researcher agent → RAG over notes
          ├──► call_writer(brief)      → writer agent      → drafts text
          └──► call_reviewer(draft)    → reviewer agent    → checks accuracy
"""

import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import create_react_agent

load_dotenv()

MODEL = "llama3.2"
model = ChatOllama(model=MODEL, temperature=0)


# =====================================================================
# RAG pipeline backing the researcher specialist
# =====================================================================

HERE = Path(__file__).parent
print("[multi_agent] Initializing RAG pipeline for researcher...")

_docs: list[Document] = []
for _name in ["NOTES.md", "LEARNINGS.md"]:
    _docs.extend(TextLoader(str(HERE / _name)).load())

_chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120).split_documents(_docs)
_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
_vectorstore = InMemoryVectorStore.from_documents(_chunks, _embeddings)
_retriever = _vectorstore.as_retriever(search_kwargs={"k": 3})
print(f"[multi_agent] Indexed {len(_chunks)} chunks.\n")


# =====================================================================
# Researcher's tool: retrieve_docs (the only specialist with tools)
# =====================================================================

@tool
def retrieve_docs(query: str) -> str:
    """Search the AgenticCourse tutorial knowledge base for information."""
    hits = _retriever.invoke(query)
    return "\n\n---\n\n".join(
        f"[from {Path(c.metadata['source']).name}]\n{c.page_content}"
        for c in hits
    )


# =====================================================================
# Three specialist agents
# =====================================================================

researcher = create_react_agent(
    model,
    tools=[retrieve_docs],
    prompt=SystemMessage(
        "You are a researcher. Given a question, call retrieve_docs as needed "
        "to gather precise facts from the knowledge base. Return a focused "
        "research brief — bullet points of facts plus inline source labels "
        "like (NOTES.md). Do NOT write prose; you are research, not writing. "
        "Keep it under 200 words."
    ),
)

writer = create_react_agent(
    model,
    tools=[],
    prompt=SystemMessage(
        "You are a technical writer. Given a research brief, produce polished "
        "prose that uses the brief's facts. Audience: senior backend engineers. "
        "Aim for exactly 3 paragraphs. Use precise terminology; avoid filler."
    ),
)

reviewer = create_react_agent(
    model,
    tools=[],
    prompt=SystemMessage(
        "You are a reviewer. Given a draft and the original task, return either:\n"
        "  - 'APPROVED' if the draft fully meets the task with accurate, "
        "specific claims and no filler\n"
        "  - A revised version of the draft with improvements\n"
        "Be brief: do NOT include commentary, just APPROVED or the revised draft."
    ),
)


# =====================================================================
# Wrap each specialist as a tool for the supervisor
# =====================================================================

@tool
def call_researcher(query: str) -> str:
    """Researcher: searches the knowledge base. Use FIRST to gather facts.

    Input: a focused research query.
    Output: a brief with bullet-pointed facts and source labels.
    """
    print(f"  [supervisor → researcher] {query[:80]}...")
    result = researcher.invoke({"messages": [("user", query)]})
    return result["messages"][-1].content


@tool
def call_writer(brief: str) -> str:
    """Writer: drafts polished text from a research brief.

    Input: a research brief (typically the researcher's output).
    Output: a 3-paragraph draft.
    """
    print(f"  [supervisor → writer]     {brief[:80]}...")
    result = writer.invoke({"messages": [("user", brief)]})
    return result["messages"][-1].content


@tool
def call_reviewer(draft_and_task: str) -> str:
    """Reviewer: checks a draft against the original task. Returns APPROVED or a revised draft.

    Input: a string containing both the original task and the draft to review.
    Output: 'APPROVED' or the revised draft text.
    """
    print(f"  [supervisor → reviewer]   {draft_and_task[:80]}...")
    result = reviewer.invoke({"messages": [("user", draft_and_task)]})
    return result["messages"][-1].content


# =====================================================================
# Supervisor — ReAct agent over specialist tools
# =====================================================================

supervisor = create_react_agent(
    model,
    tools=[call_researcher, call_writer, call_reviewer],
    prompt=SystemMessage(
        "You are a supervisor coordinating three specialists: a researcher, a "
        "writer, and a reviewer. Your job is to deliver the final artifact to "
        "the user.\n"
        "\n"
        "Workflow:\n"
        "  1. Use call_researcher to gather facts about the topic\n"
        "  2. Use call_writer with the researcher's brief to produce a draft\n"
        "  3. Use call_reviewer with both the original task and the draft\n"
        "  4. If reviewer returned APPROVED, output the writer's draft\n"
        "     If reviewer returned a revised draft, output the revised one\n"
        "\n"
        "Each specialist runs in its own context. You orchestrate by deciding "
        "what to pass to each. Do NOT do their work for them — route and "
        "compose."
    ),
)


# =====================================================================
# Demo + metrics
# =====================================================================

TASK = (
    "Write a 3-paragraph technical explainer about prompt caching for senior "
    "backend engineers. Cover (a) the mechanism (KV cache, prefill skip), "
    "(b) why it's cheaper, (c) one production gotcha."
)


def count_tokens(messages: list) -> tuple[int, int, int]:
    """Sum tokens across all AIMessages."""
    in_tok = out_tok = calls = 0
    for m in messages:
        if isinstance(m, AIMessage) and m.usage_metadata:
            in_tok += m.usage_metadata.get("input_tokens", 0)
            out_tok += m.usage_metadata.get("output_tokens", 0)
            calls += 1
    return calls, in_tok, out_tok


if __name__ == "__main__":
    print("=" * 70)
    print("MULTI-AGENT SUPERVISOR — researcher + writer + reviewer")
    print("=" * 70)
    print(f"task: {TASK}\n")

    t0 = time.perf_counter()
    result = supervisor.invoke({"messages": [("user", TASK)]})
    elapsed = time.perf_counter() - t0

    final = result["messages"][-1].content
    calls, in_tok, out_tok = count_tokens(result["messages"])
    # NOTE: this only counts supervisor-side calls. Specialist calls happen
    # inside the tool functions and don't show up in the supervisor's messages.

    print("\n" + "=" * 70)
    print("FINAL OUTPUT (from supervisor)")
    print("=" * 70)
    print(final)

    print("\n" + "=" * 70)
    print("METRICS (supervisor visible only — specialists' calls hidden in tools)")
    print("=" * 70)
    print(f"  supervisor llm calls : {calls}")
    print(f"  supervisor in/out    : {in_tok} / {out_tok}")
    print(f"  wall clock           : {elapsed:.2f}s")
    print(f"  ~cost (visible)      : ${(in_tok * 3 + out_tok * 15) / 1_000_000:.6f}")
    print(
        f"\n  NOTE: each specialist made its own internal model calls. The TOTAL\n"
        f"  cost is supervisor + sum of specialist runs. In production, instrument\n"
        f"  each specialist to track its own token usage."
    )
