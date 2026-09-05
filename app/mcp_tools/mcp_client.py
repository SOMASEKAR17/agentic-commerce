"""
A persistent MCP client the Merchant Agent service uses to call its own
tool server as a real subprocess over stdio — this is what makes MCP part
of the actual runtime path instead of a parallel, unused interface.

The subprocess is spawned once at service startup and kept alive for the
process lifetime (spawning a new one per request would be slow and fragile).
A single asyncio.Lock serializes calls through the one session, which is
simple and safe at hackathon-demo scale.
"""
import sys, os, json
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

_session: ClientSession | None = None
_stack: AsyncExitStack | None = None
_lock = None  # created lazily, needs a running event loop

async def start():
    global _session, _stack, _lock
    import asyncio
    _lock = asyncio.Lock()
    _stack = AsyncExitStack()
    # StdioServerParameters does NOT inherit the parent's environment by
    # default — without this, the tool subprocess never sees RAZORPAY_KEY_ID
    # etc. even though merchant_service's own process has them. Found this
    # by testing, not by inspection — it fails silently otherwise.
    params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_tools.tools"], env=os.environ.copy())
    read, write = await _stack.enter_async_context(stdio_client(params))
    _session = await _stack.enter_async_context(ClientSession(read, write))
    await _session.initialize()

async def stop():
    if _stack:
        await _stack.aclose()

async def call_tool(name: str, arguments: dict) -> dict:
    if _session is None:
        raise RuntimeError("MCP client not started — call mcp_client.start() at service startup.")
    async with _lock:
        result = await _session.call_tool(name, arguments)
    if result.isError:
        text = result.content[0].text if result.content else "unknown MCP tool error"
        return {"error": "MCP_TOOL_ERROR", "message": text}
    if not result.content:
        return {}
    return json.loads(result.content[0].text)
