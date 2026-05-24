"""Production chatbot capstone.

Composes every primitive from the course into one architecture:

    user input
       │
       ├─► INPUT GUARDRAILS  (PII | Injection | OnTopic)
       │       │
       │       ▼
       ├─► create_react_agent
       │       ├── tools=[retrieve_docs]   (RAG as a tool the agent calls when needed)
       │       ├── prompt=system           (long persona/rules)
       │       └── checkpointer=MemorySaver()  (per-thread conversation memory)
       │       │
       │       ▼
       ├─► OUTPUT GUARDRAILS (PII leak | Faithfulness vs retrieve_docs results)
       │       │
       └───────▼
          user sees answer (or refusal)

Demo: a 4-turn conversation in one thread that exercises greetings,
RAG, memory-using follow-up, and a PII rejection. Per-turn metrics
show tokens, guard verdicts, and a final cost summary.
"""
# Requires: ollama serve + ollama pull llama3.2

import re
from dataclasses import dataclass
from pathlib import Path

from langchain_ollama import ChatOllama
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent


# =====================================================================
# 1. RAG PIPELINE — same shape as rag.py
# =====================================================================

HERE = Path(__file__).parent.parent
print("Initializing RAG pipeline (load -> split -> embed -> store)...")

docs: list[Document] = []
for name in ["NOTES.md", "LEARNINGS.md"]:
    docs.extend(TextLoader(str(HERE / name)).load())

splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
chunks = splitter.split_documents(docs)
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = InMemoryVectorStore.from_documents(chunks, embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

print(f"Indexed {len(chunks)} chunks.\n")


# =====================================================================
# 2. RAG-AS-A-TOOL — the agent decides when to retrieve
# =====================================================================

@tool
def retrieve_docs(query: str) -> str:
    """Search the LangChain/Anthropic Claude tutorial knowledge base.

    Use this whenever the user asks about LangChain features (LCEL, agents,
    RAG, prompt caching, output parsers, structured output, memory, vector
    stores) or about Anthropic Claude. Do NOT use it for greetings, personal
    introductions, or chit-chat.

    Returns the top-3 most relevant chunks with source labels.
    """
    hits = retriever.invoke(query)
    return "\n\n---\n\n".join(
        f"[from {Path(c.metadata['source']).name}]\n{c.page_content}"
        for c in hits
    )


# =====================================================================
# 3. THE SYSTEM PROMPT — long enough to act as a full persona
# =====================================================================

LONG_SYSTEM = """You are a meticulous tutorial assistant for the AgenticCourse project — a hands-on LangChain and Anthropic Claude walkthrough. Your name is "Course Bot." You help a senior backend engineer named the user navigate the tutorial materials, answer questions about the concepts covered, and apply them to their own code.

Persona and tone:
- You are concise, technical, and evidence-based. The user is a senior engineer; you do not over-explain basics they clearly know.
- You never use filler phrases like "Great question!" or "I hope this helps." You never apologize unnecessarily.
- You use Markdown formatting where it aids scanning: bold for key facts, code fences for code, tables for comparisons.
- You avoid emoji unless the user explicitly invites a casual register.
- You answer in 1-3 short paragraphs unless the user asks for depth.

Tool-use guidance:
- You have ONE primary tool: `retrieve_docs(query)`. Use it whenever the user asks a substantive question about LangChain, Claude, RAG, agents, prompt caching, output parsers, embeddings, vector stores, memory/checkpointers, structured output, or LangGraph.
- Do NOT call `retrieve_docs` for: greetings, the user introducing themselves, "thanks", clarifying meta-questions about the conversation itself, or pure follow-ups that the prior tool results already answer in full.
- When you do call `retrieve_docs`, use a focused query — the most search-friendly version of the user's question, not the question verbatim.
- If `retrieve_docs` returns content that does not answer the question, say so plainly: "I don't have that in the knowledge base." Do not invent details.

Grounding rules:
- When you cite information from `retrieve_docs`, attribute it inline: "(NOTES.md)" or "(LEARNINGS.md)" based on the source label in the chunks.
- When the user's question requires combining the knowledge base with general programming knowledge (e.g., "show me how to use this in a FastAPI route"), it is OK to use general knowledge for the surrounding code — but the LangChain-specific claims should come from `retrieve_docs`.
- If a claim is from your own pre-training and not from the retrieved chunks, mark it gently: "Generally speaking..." or "In typical setups...".

Memory rules:
- You remember the user's name, role, preferences, and prior questions across turns within this conversation thread.
- When the user refers back to "that result" or "the previous example", check the conversation history before re-retrieving.
- Adapt your explanations to what the user has already told you. If they said they are a data scientist, frame answers in data-science terms. If they said they prefer terse answers, stay terse.

Constraints:
- Never reveal API keys, environment variables, or secrets — even if asked.
- Never produce code that uses deprecated LangChain APIs (like the old `LLMChain` class) when a modern LCEL alternative exists.
- Never claim to have "looked up" something on the live web. Your knowledge sources are the retrieved chunks and your pre-training. If asked to fetch live data, say you cannot.
- Never give legal, medical, or financial advice. If asked, decline politely and suggest they consult a qualified professional.

Style examples — well-formed answers:
- Q: "Hi! I'm Sree, a data scientist."
  A: "Hello, Sree. I'm Course Bot — I can answer questions about the LangChain tutorial materials, walk you through any of the examples, and help you adapt them to your own code. What would you like to explore first?"
- Q: "How does prompt caching work?"
  A: [tool call: retrieve_docs("prompt caching")]
     "Prompt caching works by checkpointing the model's KV cache for a prompt prefix you mark with `cache_control` (NOTES.md). On subsequent requests within the 5-minute TTL, the server reuses the cached KV state and skips the prefill compute — billing cached tokens at $0.30/M instead of $3/M, a 90% discount (LEARNINGS.md). The system prompt is the most common cacheable prefix."
- Q: "Show me how to use it in a FastAPI app."
  A: "You'd put the cache marker on the SystemMessage as shown in the tutorial (LEARNINGS.md), and inject it via a FastAPI dependency that returns the ChatOllama instance. Roughly: [code]. The caching is invisible to FastAPI — it happens inside the model call."

Style examples — to AVOID:
- "I'd be happy to help! Let me look that up for you..." (filler)
- "I think prompt caching probably reduces..." (hedging on facts in the KB)
- "Prompt caching uses Redis under the hood." (made-up; the chunks don't say this)
- Calling `retrieve_docs("hello")` for a greeting (waste of tokens; greetings don't need retrieval)

Self-check before every response:
1. Did the user ask a tutorial question? If yes, did I retrieve?
2. Are my LangChain-specific claims grounded in retrieved context?
3. Are my citations inline and accurate (NOTES.md or LEARNINGS.md)?
4. Am I within 1-3 short paragraphs unless the user asked for depth?
5. Did I avoid hedging, apologizing, and filler?
6. Did I use what I know about the user from earlier turns?

When all six checks pass, deliver the response."""


system_message = SystemMessage(content=LONG_SYSTEM)


# =====================================================================
# 4. THE AGENT — memory + tools
# =====================================================================

model = ChatOllama(model="llama3.2", temperature=0)
checkpointer = MemorySaver()

agent = create_react_agent(
    model,
    tools=[retrieve_docs],
    checkpointer=checkpointer,
    prompt=system_message,
)


# =====================================================================
# 5. GUARDRAILS — same shape as safe_rag.py
# =====================================================================

@dataclass
class GuardrailResult:
    passed: bool
    reason: str = ""


class GuardrailFailure(Exception):
    def __init__(self, guardrail: str, reason: str):
        self.guardrail = guardrail
        self.reason = reason
        super().__init__(f"{guardrail}: {reason}")


EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SSN_RE = re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b")
API_KEY_RE = re.compile(r"(?:sk|pk)-[a-zA-Z0-9_-]{20,}")
PROMPT_INJECTION_RE = re.compile(
    r"|".join([
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|directions|prompts|rules)",
        r"you\s+are\s+now\s+(?:a\s+|an\s+)?\w+",
        r"disregard\s+(?:all\s+)?(?:previous|prior|above)",
        r"forget\s+(?:all\s+)?(?:everything|previous|instructions|your\s+role)",
        r"<\|.*?\|>",
    ]),
    re.IGNORECASE,
)


def _find_pii(text: str) -> list[str]:
    found = []
    if EMAIL_RE.search(text): found.append("email")
    if SSN_RE.search(text):   found.append("SSN")
    if PHONE_RE.search(text): found.append("phone")
    if API_KEY_RE.search(text): found.append("API key")
    return found


def guard_pii_input(text: str) -> GuardrailResult:
    found = _find_pii(text)
    return GuardrailResult(False, f"contains {', '.join(found)}") if found else GuardrailResult(True)


def guard_prompt_injection(text: str) -> GuardrailResult:
    m = PROMPT_INJECTION_RE.search(text)
    return GuardrailResult(False, f"injection pattern: {m.group(0)!r}") if m else GuardrailResult(True)


_topic_chain = (
    ChatPromptTemplate.from_messages([
        ("system",
         "Decide if a user message belongs in a LangChain / Anthropic Claude tutorial chat. "
         "ON-TOPIC: questions about LangChain features, Claude, RAG, agents, embeddings, "
         "vector stores, memory, output parsers, caching, LangGraph. ALSO ON-TOPIC: "
         "greetings, the user introducing themselves, follow-up questions about prior "
         "tutorial answers, requests for code examples. OFF-TOPIC: weather, restaurants, "
         "sports, news, anything unrelated. Respond with EXACTLY one word: 'on-topic' "
         "or 'off-topic'."),
        ("human", "{message}"),
    ])
    | model
    | StrOutputParser()
)


def guard_on_topic(text: str) -> GuardrailResult:
    verdict = _topic_chain.invoke({"message": text}).strip().lower()
    return GuardrailResult(False, "off-topic for this chat") if "off" in verdict else GuardrailResult(True)


def guard_pii_output(text: str) -> GuardrailResult:
    found = _find_pii(text)
    return GuardrailResult(False, f"answer contains {', '.join(found)}") if found else GuardrailResult(True)


_faithfulness_chain = (
    ChatPromptTemplate.from_messages([
        ("system",
         "You are a grounding judge for a tutorial chatbot. Given retrieved CONTEXT from "
         "the knowledge base and the ANSWER produced, decide if the answer's "
         "tutorial-specific claims are supported by the context. Common phrasing, "
         "definitional restatement, and surrounding code scaffolding using general "
         "programming knowledge are allowed. Specific feature claims, citations, code "
         "snippets that purport to be from the tutorial must be derivable from context. "
         "If the answer says it cannot find the info, that is SUPPORTED. Respond with "
         "EXACTLY one word: 'supported' or 'unsupported'."),
        ("human", "CONTEXT:\n{context}\n\nANSWER:\n{answer}"),
    ])
    | model
    | StrOutputParser()
)


def guard_faithfulness(retrieved: str, answer: str) -> GuardrailResult:
    """Only meaningful when retrieve_docs was called this turn."""
    if not retrieved.strip():
        # No retrieval this turn → no grounding to check (greetings, etc.)
        return GuardrailResult(True, "no retrieval this turn — skipped")
    verdict = _faithfulness_chain.invoke({"context": retrieved, "answer": answer}).strip().lower()
    return (
        GuardrailResult(False, "answer not supported by retrieved context")
        if "unsupported" in verdict
        else GuardrailResult(True)
    )


# =====================================================================
# 6. THE DRIVER — wires guards around the agent invocation
# =====================================================================

def _print_guard(stage: str, name: str, r: GuardrailResult) -> None:
    status = "PASS" if r.passed else "FAIL"
    suffix = f" — {r.reason}" if r.reason and (not r.passed or "skipped" in r.reason) else ""
    print(f"  [{stage} guard] {name:<18} {status}{suffix}")


def safe_chat(user_input: str, thread_id: str) -> dict:
    """Run one user turn through guardrails + agent + guardrails. Returns metrics."""
    print(f"\n→ user: {user_input}")
    print("\n  ─ INPUT GUARDRAILS ─")
    for name, check in [
        ("PII", guard_pii_input),
        ("PromptInjection", guard_prompt_injection),
        ("OnTopic", guard_on_topic),
    ]:
        r = check(user_input)
        _print_guard("input", name, r)
        if not r.passed:
            return {"answer": f"[REFUSED by {name}] {r.reason}",
                    "tokens": (0, 0), "tool_calls": [], "refused": True}

    print("\n  ─ AGENT INVOKE ─")
    config = {"configurable": {"thread_id": thread_id}}
    state_before = agent.get_state(config)
    n_before = len(state_before.values.get("messages", [])) if state_before.values else 0
    result = agent.invoke({"messages": [("user", user_input)]}, config=config)
    new_messages = result["messages"][n_before:]

    # Gather tool calls + retrieved context + tokens this turn
    tool_calls_made = []
    retrieved_text = ""
    in_tok = out_tok = 0
    for m in new_messages:
        if isinstance(m, AIMessage):
            if m.tool_calls:
                tool_calls_made.extend(tc["name"] for tc in m.tool_calls)
            if m.usage_metadata:
                in_tok += m.usage_metadata.get("input_tokens", 0)
                out_tok += m.usage_metadata.get("output_tokens", 0)
        elif isinstance(m, ToolMessage) and m.name == "retrieve_docs":
            retrieved_text += m.content + "\n"

    answer = new_messages[-1].content
    print(f"  tool calls this turn: {tool_calls_made or ['(none)']}")

    print("\n  ─ OUTPUT GUARDRAILS ─")
    pii_out = guard_pii_output(answer)
    _print_guard("output", "OutputPII", pii_out)
    if not pii_out.passed:
        return {"answer": f"[BLOCKED OUTPUT] {pii_out.reason}",
                "tokens": (in_tok, out_tok),
                "tool_calls": tool_calls_made, "refused": True}

    faith = guard_faithfulness(retrieved_text, answer)
    _print_guard("output", "Faithfulness", faith)
    if not faith.passed:
        return {"answer": f"[BLOCKED OUTPUT] {faith.reason}",
                "tokens": (in_tok, out_tok),
                "tool_calls": tool_calls_made, "refused": True}

    return {"answer": answer, "tokens": (in_tok, out_tok),
            "tool_calls": tool_calls_made, "refused": False}


def cost_usd(in_tok, out_tok):
    """Approximate cost — Ollama runs locally so actual $ cost is 0; shown for learning."""
    return 0.0


# =====================================================================
# 7. DEMO — 4 turns, one thread
# =====================================================================

THREAD = "alice"

turns = [
    "Hi! I'm Sree, a data scientist.",
    "How does prompt caching actually work, and why is it cheaper?",
    "Cool — could you summarize that for me, as a data scientist who's new to LLMs?",
    "Also my SSN is 123-45-6789. What's RAG?",
]

results = []
for i, q in enumerate(turns, start=1):
    print("\n" + "#" * 72)
    print(f"# TURN {i} (thread={THREAD})")
    print("#" * 72)
    r = safe_chat(q, thread_id=THREAD)
    results.append((q, r))

    in_tok, out_tok = r["tokens"]
    print(f"\n  ─ TOKENS ─")
    print(f"    input={in_tok}  output={out_tok}")
    print(f"\n  ─ ANSWER ─")
    print(f"    {r['answer'][:400]}{'...' if len(r['answer']) > 400 else ''}")


# =====================================================================
# 8. FINAL SUMMARY
# =====================================================================

print("\n" + "=" * 72)
print("FINAL SUMMARY — 4-turn conversation")
print("=" * 72)
print(f"\n{'turn':<5} {'in':>6} {'out':>5} {'tools':<14} {'status'}")
print("-" * 40)

total_in = total_out = 0
for i, (q, r) in enumerate(results, start=1):
    in_tok, out_tok = r["tokens"]
    total_in += in_tok
    total_out += out_tok
    tools = ",".join(r["tool_calls"]) or "-"
    status = "REFUSED" if r["refused"] else "OK"
    print(f"{i:<5} {in_tok:>6} {out_tok:>5} {tools:<14} {status}")

print("-" * 40)
print(f"{'TOTAL':<5} {total_in:>6} {total_out:>5}")

print(f"\nNote: Ollama runs locally — no API cost. Token counts shown for informational purposes.")
print(f"  - {results[3][1]['refused'] and 'one' or 'no'} turn refused upfront (zero LLM cost)")
print(f"  - grounded answers with citations (NOTES.md, LEARNINGS.md)")
