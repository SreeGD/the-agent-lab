# 12 — MCP (Model Context Protocol)

> **Provider variant — OpenAI (`gpt-4o`)** This lesson's code is provider-agnostic — it does not directly instantiate an LLM. No OpenAI-specific code file is needed; use the original `labs/12_mcp_client.py` and `labs/12_mcp_server.py` unchanged.

> **Expose your tools over JSON-RPC so any LLM client — Claude Desktop, Cursor, Continue.dev, your own code — can discover and use them.** Same propose-execute-feedback dance as `03_agent_manual.py`, just over a wire.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (12 lessons) ═══════           PHASE 2          PHASE 3

  ✓ 01-11 (foundation)                                      ○ 13 system     ○ 16-19 Healthcare
                                                              design       ○ 20-22 Agriculture
  ▶ 12 MCP  ◄═══════ YOU ARE HERE                          ○ 14 red-team   ○ 23-25 Finance
                                                           ○ 15 AI UX      ○ 26-28 Vidya Karana
                                                                            ○ 29-32 Family AI
```

**Why this lesson now:** the bridge between Phase 1 (foundation) and Phase 2 (advanced agentic patterns starting next). MCP is **the emerging standard** for cross-LLM tool sharing — your tools become available to every MCP client in the ecosystem.

---

## Files involved

| File | Role |
|---|---|
| [`12_mcp_server.py`](../12_mcp_server.py) | FastMCP server exposing add, count_letters, get_current_time, retrieve_docs |
| [`12_mcp_client.py`](../12_mcp_client.py) | Python client — spawns server, discovers tools, calls each |
| [`claude-desktop.json`](../claude-desktop.json) | Config snippet to register the server with Claude Desktop |

---

## What problem it solves

Your `03_agent_manual.py` tools (`add`, `count_letters`, `retrieve_docs`) live inside one Python process. Useful for *that* script, useless to:
- Claude Desktop (a different process)
- Cursor's chat (a different process, different language even)
- Your colleague's code (a different machine)
- A long-running agent server vs. a CLI script

You'd traditionally wrap them in HTTP/gRPC/whatever-protocol — lots of plumbing per tool.

**MCP standardizes this.** Define your tools once with `@mcp.tool()`; any MCP-compatible client discovers and calls them automatically. One server, many consumers.

---

## The analogy

A **USB standard for tools**.

Before USB, every peripheral had its own connector (parallel printer, PS/2 mouse, serial modem, ADB keyboard). Hardware compatibility was an O(N×M) problem.

USB made it O(N+M): one plug, any device works with any host. The host doesn't need a printer-specific driver; it asks the USB device *"what can you do?"* and the device replies *"I'm a printer, here's my capabilities."*

MCP is USB for LLM tools. Server says *"here are the tools I expose."* Any client says *"give me your tools"* via the same JSON-RPC call. No tool-specific glue code per client.

---

## Visual

```
   ┌────────────────────────────┐        ┌─────────────────────────┐
   │   MCP CLIENT               │        │   MCP SERVER            │
   │   (any LLM app)            │        │   (your code)           │
   │                            │        │                         │
   │   - Claude Desktop         │        │  exposes:               │
   │   - Cursor                 │ stdio  │   add(a, b)             │
   │   - Continue.dev           │◄─────► │   count_letters(text)   │
   │   - your Python client     │ JSON-  │   get_current_time()    │
   │     (this lesson)          │  RPC   │   retrieve_docs(query)  │
   │                            │        │                         │
   └────────────────────────────┘        └─────────────────────────┘
                                              ↑
                                       Backing: the RAG pipeline
                                       (load → split → embed → store)
                                       initialized once at startup.
```

The protocol shape on the wire:

```json
// list_tools request:
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}

// list_tools response:
{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"add",...}]}}

// call_tool request:
{"jsonrpc":"2.0","id":2,"method":"tools/call",
 "params":{"name":"add","arguments":{"a":47,"b":158}}}

// call_tool response:
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"205"}]}}
```

That's it. Two methods (`tools/list` + `tools/call`) over JSON-RPC. No new abstractions.

---

## The concept

### Server side (12_mcp_server.py):

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agenticcourse-tools")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b

@mcp.tool()
def retrieve_docs(query: str) -> str:
    """Search the AgenticCourse tutorial knowledge base."""
    hits = retriever.invoke(query)
    return format_context(hits)

if __name__ == "__main__":
    mcp.run()    # listens on stdio
```

Same `@tool`-style decorator as `03_agent_manual.py`. **Schemas auto-generated from type hints + docstrings.**

### Client side (12_mcp_client.py):

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(command="python", args=["12_mcp_server.py"])

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()              # 1. handshake
        tools = await session.list_tools()      # 2. discover
        result = await session.call_tool(       # 3. call
            "add", {"a": 47, "b": 158}
        )
```

Three calls. That's the entire MCP client API.

---

## Run it

```bash
python 12_mcp_client.py
```

Expected output:

```
[1] initialize()    → server: agenticcourse-tools v1.27.1, protocol 2025-11-25
[2] list_tools()    → 4 tools auto-discovered:
                       - add(a, b)
                       - count_letters(text)
                       - get_current_time()
                       - retrieve_docs(query)
[3] call_tool():
       add(47, 158)                          → 205        (9 ms)
       count_letters("Vidya Karana")         → 11         (3 ms)
       get_current_time()                    → "2026-..."  (2 ms)
       retrieve_docs("prompt caching ...")   → "[from LEARNINGS.md] ..."  (531 ms)
```

The first three tools are pure Python, sub-10 ms. `retrieve_docs` is slower because it embeds the query and does cosine search.

---

## Four ways to start the MCP server

| # | Method | When to use |
|---|---|---|
| **1** | Python client launches it automatically: `python 12_mcp_client.py` | The demo — and how MCP works in production (client owns server lifecycle) |
| **2** | Claude Desktop loads it via config | The "click" moment — your tools usable from the GUI |
| **3** | MCP Inspector: `pip install "mcp[cli]" && mcp dev 12_mcp_server.py` | Interactive debugging in browser |
| **4** | Raw stdio: `python 12_mcp_server.py` | Protocol debugging |

For #2 (Claude Desktop), edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agenticcourse-tools": {
      "command": "/path/to/python",
      "args": ["/path/to/12_mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop completely (Cmd+Q + reopen). Look for the plugin icon. Ask Claude *"What is prompt caching?"* — it'll call your `retrieve_docs`.

---

## Walk-through

### Schema is the contract

The `@mcp.tool()` decorator reads your type hints + docstring and emits the same JSON Schema you'd get from LangChain's `@tool`. **The schema is the cross-language contract.** Once it's defined, the LLM (in any client) knows how to call your function.

### Server-side state is real

The RAG pipeline initializes once at server startup (~3-5 seconds — loading the embedding model, indexing chunks). Subsequent `retrieve_docs` calls reuse the warm retriever. **Big advantage over in-process tools: expensive setup happens once and amortizes over many client connections.**

### Logs go to stderr, NOT stdout

Critical: MCP servers communicate over stdout in JSON-RPC. Printing anything else to stdout breaks the protocol.

```python
print("[mcp_server] loading...", file=sys.stderr, flush=True)
```

This trips up everyone at least once. Symptom: the client mysteriously fails to handshake.

---

## MCP vs `03_agent_manual.py`'s tool loop

| Aspect | `03_agent_manual.py` (in-process) | `12_mcp_server.py` + client |
|---|---|---|
| Tool definition | `@tool` decorator | `@mcp.tool()` decorator (~identical) |
| Tool registry | `tools_by_name` dict | Server's internal dict |
| Tool execution | Direct Python call | JSON-RPC over stdio |
| Tool sharing | One process only | Any MCP client |
| Server-side state | Same process as client | Persistent across connections |
| Schema generation | LangChain's `@tool` | MCP's `@mcp.tool()` |
| Transport overhead | Function call (~µs) | stdio + JSON parse (~ms) |

**Conceptually identical, operationally different.**

---

## Production patterns this unlocks

| Pattern | Example |
|---|---|
| Shared tool library across products | One MCP server; web app + CLI + IDE all use it |
| Heavy-compute tools | Expensive Python tools live in the server process, not duplicated in every client |
| Cross-language access | A Node.js or Rust LLM client calls your Python tools |
| Sandbox/security boundary | Tool execution in a separate process is easier to audit + sandbox |
| Tool versioning | Bump server version; clients negotiate via `initialize()` protocol version |

---

## Try this

1. **Add a new tool** to the server (e.g., `multiply(a, b)`). Restart `12_mcp_client.py`. Watch it auto-discover the new tool with no client-side changes.
2. **Wire Claude Desktop** to your MCP server (config snippet above). Ask it questions that use your tools. The most satisfying moment of this lesson.
3. **Add an LLM in front of the client** — wrap `session.list_tools()` + `session.call_tool()` in a LangChain `create_react_agent` with `ChatOpenAI`. Now you have a real MCP-powered agent.
4. **Try MCP Inspector** — `mcp dev 12_mcp_server.py`. Click through the tools in the browser inspector.

---

## Mental model in one line

> **MCP is `03_agent_manual.py`'s tool-calling, but over a wire. Server defines tools, clients discover and call them. Any client can use any server. The schema is the contract; JSON-RPC is the wire format; stdio is the most common transport.**

---

## FAQ

**Q: Why does my server crash with weird JSON parsing errors on the client side?**

A: Almost always because the server printed something to `stdout`. MCP uses stdout for JSON-RPC; any stray print breaks the protocol. **Logging must go to stderr.**

**Q: Can I use MCP over HTTP instead of stdio?**

A: Yes — MCP supports stdio, SSE (Server-Sent Events), and Streamable HTTP. Stdio is most common for local tools; SSE/HTTP for remote servers. The protocol is the same; the transport differs.

**Q: How do clients authenticate to MCP servers?**

A: Local stdio servers inherit the client's permissions (no auth). Remote MCP servers (HTTP/SSE) use OAuth 2.0 or API keys. The MCP spec defines this; check the docs for your transport.

**Q: How is this different from LangServe / FastAPI just exposing tools as REST endpoints?**

A: Convention. With MCP, *any* MCP client discovers and uses your tools without per-server code. With REST, every client needs custom integration code (URL paths, auth, schema fetching). MCP is the standard.

**Q: Does Claude Desktop have built-in MCP support?**

A: Yes, since 2024. Other clients with MCP support: Cursor, Continue.dev, Zed editor, Cody, and growing fast.

**Q: Can I use MCP for things besides tools?**

A: Yes — MCP defines three primitives:
- **Tools** — function-call style (what we built)
- **Resources** — read-only data (a file, a DB query, a URL)
- **Prompts** — templated prompt workflows the client can invoke
This lesson covered tools. Resources and prompts work the same way (`resources/list`, `resources/read`, `prompts/list`, etc.).

**Q: What's the relationship between MCP and OpenAI's function-calling?**

A: OpenAI's function-calling is the *model-side* API (the model emits tool_use blocks). MCP is the *infrastructure-side* protocol (how tools get discovered + called across processes). They compose: an MCP client can host a model that emits function calls, then route those calls to MCP server tools.

**Q: How do I add MCP support to my custom LLM client?**

A: Use the official `mcp` Python SDK (`pip install mcp`). It provides `ClientSession` + transport adapters. ~20 lines of code to add MCP discovery + invocation to any agent.

**Q: How do I handle long-running tool calls (e.g., a 30-second computation)?**

A: MCP supports streaming progress via the `progress` notification. Server emits intermediate updates; client handles them. For really long jobs, return a job ID immediately and expose a `check_status` tool — the client polls.

**Q: Is MCP the future or a phase?**

A: Hard to say definitively, but adoption is fast. Anthropic, OpenAI integrations, multiple IDE makers, and the broader ecosystem are converging on MCP as the standard. Bet on it for new tool work.

---

## Related

- **Previous:** [11 — Production capstone](11-production-capstone.md)
- **Foundation for:** Track A Session 1 of the 32-session curriculum (already covered here, since this lesson IS that session)
- **Bridges to:** Phase 2 agentic patterns (Reflection, Plan-and-Execute, Multi-agent)
- **MCP standard:** https://modelcontextprotocol.io
