"""MCP server — exposes our tools (add, count_letters, get_current_time,
retrieve_docs) over JSON-RPC stdio so any MCP-compatible client can use them.

Run directly:   python mcp_server.py     # speaks JSON-RPC on stdio
Or wire into Claude Desktop / Cursor / any MCP client via config.

Logs go to stderr (stdout is the JSON-RPC transport — printing there breaks
the protocol). Use sys.stderr.write or logging with stream=sys.stderr.
"""

import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from mcp.server.fastmcp import FastMCP

load_dotenv()


# =====================================================================
# RAG pipeline — initialized once at server startup (eagerly).
# Subsequent retrieve_docs() calls reuse the warm retriever.
# =====================================================================

HERE = Path(__file__).parent
print("[mcp_server] Initializing RAG pipeline...", file=sys.stderr, flush=True)

_docs = []
for _name in ["NOTES.md", "LEARNINGS.md"]:
    _docs.extend(TextLoader(str(HERE / _name)).load())

_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
_chunks = _splitter.split_documents(_docs)
_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
_vectorstore = InMemoryVectorStore.from_documents(_chunks, _embeddings)
_retriever = _vectorstore.as_retriever(search_kwargs={"k": 3})

print(f"[mcp_server] Indexed {len(_chunks)} chunks.", file=sys.stderr, flush=True)


# =====================================================================
# MCP server — FastMCP decorator API.
# =====================================================================

mcp = FastMCP("agenticcourse-tools")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b


@mcp.tool()
def count_letters(text: str) -> int:
    """Return the number of alphabetic letters in `text` (ignoring spaces/punctuation)."""
    return sum(1 for ch in text if ch.isalpha())


@mcp.tool()
def get_current_time() -> str:
    """Return the current local time as an ISO 8601 string."""
    return datetime.now().isoformat(timespec="seconds")


@mcp.tool()
def retrieve_docs(query: str) -> str:
    """Search the AgenticCourse tutorial knowledge base (NOTES.md + LEARNINGS.md).

    Returns the top-3 most relevant chunks with source labels. Use this to
    answer questions about LangChain, LCEL, agents, RAG, prompt caching,
    output parsers, structured output, memory, vector stores, or LangGraph.
    """
    hits = _retriever.invoke(query)
    return "\n\n---\n\n".join(
        f"[from {Path(c.metadata['source']).name}]\n{c.page_content}"
        for c in hits
    )


if __name__ == "__main__":
    print("[mcp_server] Ready. Listening on stdio.", file=sys.stderr, flush=True)
    mcp.run()
