"""MCP client — connects to mcp_server.py over stdio, discovers its tools,
and invokes each one to demonstrate the protocol.

This is the same propose-execute-feedback dance as agent.py, just with a
JSON-RPC server in the middle. The "click" moment: you see 4 tools
auto-discovered + their schemas + remote calls returning results, all
without a single line of HTTP plumbing.
"""

import asyncio
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent

# Spawn the server as a subprocess; communicate over its stdin/stdout.
server_params = StdioServerParameters(
    command=sys.executable,           # use the same Python that's running this client
    args=[str(HERE / "mcp_server.py")],
)


async def main() -> None:
    print("=" * 64)
    print("MCP client — connecting to mcp_server.py over stdio")
    print("=" * 64)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. Initialize — MCP handshake (capabilities, version exchange).
            print("\n[1] initialize() — handshake")
            init_result = await session.initialize()
            print(f"    server: {init_result.serverInfo.name}  "
                  f"v{init_result.serverInfo.version}")
            print(f"    protocol: {init_result.protocolVersion}")

            # 2. Discover tools — what does this server expose?
            print("\n[2] list_tools() — discovery")
            list_result = await session.list_tools()
            print(f"    server advertises {len(list_result.tools)} tools:")
            for tool in list_result.tools:
                params = list((tool.inputSchema or {}).get("properties", {}).keys())
                print(f"      - {tool.name}({', '.join(params) or 'no args'})")
                print(f"          {tool.description.splitlines()[0][:80]}")

            # 3. Call each tool — see the propose-execute dance over the wire.
            print("\n[3] call_tool() — invoking each tool remotely")

            tool_calls = [
                ("add",              {"a": 47, "b": 158}),
                ("count_letters",    {"text": "Vidya Karana"}),
                ("get_current_time", {}),
                ("retrieve_docs",    {"query": "What is prompt caching and why is it cheaper?"}),
            ]

            for tool_name, args in tool_calls:
                print(f"\n    → {tool_name}({args})")
                t0 = time.perf_counter()
                result = await session.call_tool(tool_name, args)
                dt = time.perf_counter() - t0

                # Tool results come back as content blocks; the text is in .text
                content = result.content[0]
                text = content.text if hasattr(content, "text") else str(content)
                preview = (text[:150] + "...") if len(text) > 150 else text
                print(f"      result ({dt*1000:.0f} ms): {preview}")

            print("\n" + "=" * 64)
            print("Done. Server is shutting down (stdio context exiting).")
            print("=" * 64)
            print("\nWhat just happened, in agent.py terms:")
            print("  • The LLM Client (this script) discovered tools from a server")
            print("    that runs in a different process.")
            print("  • Each call_tool() = the 'execute' phase of the propose-execute")
            print("    dance — same shape as your manual loop in agent.py.")
            print("  • The protocol on the wire: JSON-RPC 2.0 over stdio.")
            print("  • Add an LLM in front of session.list_tools() / call_tool()")
            print("    and you have a full MCP-powered agent.")


if __name__ == "__main__":
    asyncio.run(main())
