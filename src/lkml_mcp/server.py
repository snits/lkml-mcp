"""MCP server for LKML thread retrieval."""

import argparse
import asyncio
import contextlib
import os
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .client import LKMLAPIError, LKMLClient
from .handlers import (
    handle_lkml_compare_patch_versions,
    handle_lkml_get_patch,
    handle_lkml_get_raw,
    handle_lkml_get_thread,
    handle_lkml_get_thread_summary,
    handle_lkml_get_user_series,
    handle_lkml_search_patches,
)

DEFAULT_TRANSPORT = "stdio"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8772
VALID_TRANSPORTS = ("stdio", "sse", "streamable-http")

server = Server("lkml-mcp")
base_url = os.environ.get("LKML_BASE_URL", "https://lore.kernel.org")
client = LKMLClient(base_url=base_url)


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools."""
    return [
        Tool(
            name="lkml_get_thread",
            description=(
                "Fetch a full LKML thread by message ID from lore.kernel.org or compatible public-inbox instances. "
                "Returns all messages in the thread with subject, from, date, "
                "message-id, in-reply-to, and body content. By default, "
                "filters out automated bot messages (kernel test robot, "
                "CI bots, etc.)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Message ID to fetch (e.g., '20251111105634.1684751-1-lzampier@redhat.com')",
                    },
                    "inbox": {
                        "type": "string",
                        "description": "Inbox/list name (required for sourceware-style instances, optional for lore.kernel.org)",
                    },
                    "include_bots": {
                        "type": "boolean",
                        "description": "Include automated bot messages (kernel test robot, CI bots). Default false filters them out.",
                        "default": False,
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="lkml_get_raw",
            description=(
                "Fetch a single LKML message in raw RFC822 format from lore.kernel.org or compatible public-inbox instances. "
                "Useful for getting raw MIME bodies, headers, or inline diffs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Message ID to fetch (e.g., '20251111105634.1684751-1-lzampier@redhat.com')",
                    },
                    "inbox": {
                        "type": "string",
                        "description": "Inbox/list name (required for sourceware-style instances, optional for lore.kernel.org)",
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="lkml_get_user_series",
            description=(
                "Find recent patch series and messages by user email address. "
                "Returns a list of patch series (with cover letters and "
                "patches grouped together) and standalone messages. Useful "
                "for discovering what patches a user has recently proposed "
                "or been involved in."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "User email address (e.g., 'lzampier@redhat.com')",
                    },
                    "inbox": {
                        "type": "string",
                        "description": "Inbox/list name (required for sourceware-style instances, optional for lore.kernel.org)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of messages to retrieve",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
                "required": ["email"],
            },
        ),
        Tool(
            name="lkml_search_patches",
            description=(
                "Search for patches by keywords, subsystem, author, or other criteria. "
                "Returns matching patch series and individual patches from lore.kernel.org or compatible public-inbox instances."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "inbox": {
                        "type": "string",
                        "description": "Inbox/list name (required for sourceware-style instances, optional for lore.kernel.org)",
                    },
                    "subsystem": {
                        "type": "string",
                        "description": "Filter by subsystem (e.g., 'net', 'kvm', 'riscv', 'mm')",
                    },
                    "author": {
                        "type": "string",
                        "description": "Filter by author email or name",
                    },
                    "since_date": {
                        "type": "string",
                        "description": "Return patches since this date in YYYYMMDD format",
                        "pattern": "^\\d{8}$",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="lkml_get_patch",
            description=(
                "Fetch patches from lore.kernel.org in git am-ready mbox format. "
                "Can fetch a single patch or all patches in a series. "
                "Returns file paths to clean mbox files suitable for 'git am'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Message ID of the patch (e.g., '20251111105634.1684751-1-lzampier@redhat.com')",
                    },
                    "inbox": {
                        "type": "string",
                        "description": "Inbox/list name (required for sourceware-style instances, optional for lore.kernel.org)",
                    },
                    "include_bots": {
                        "type": "boolean",
                        "description": "Include automated bot messages. Default false.",
                        "default": False,
                    },
                    "series": {
                        "type": "boolean",
                        "description": "If true, fetch all patches in the series. If false, fetch only this single patch.",
                        "default": False,
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="lkml_get_thread_summary",
            description=(
                "Get a structured summary of an LKML thread: reply hierarchy, "
                "participants, and review tags (Reviewed-by, Acked-by, etc.)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Message ID of any message in the thread",
                    },
                    "inbox": {
                        "type": "string",
                        "description": "Inbox/list name (required for sourceware-style instances, optional for lore.kernel.org)",
                    },
                    "include_bots": {
                        "type": "boolean",
                        "description": "Include automated bot messages. Default false.",
                        "default": False,
                    },
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="lkml_compare_patch_versions",
            description=(
                "Compare two versions of a patch series. Shows subject changes, "
                "file differences, and new/removed patches between versions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "old_message_id": {
                        "type": "string",
                        "description": "Message ID of the older version's cover letter or first patch",
                    },
                    "new_message_id": {
                        "type": "string",
                        "description": "Message ID of the newer version's cover letter or first patch",
                    },
                    "inbox": {
                        "type": "string",
                        "description": "Inbox/list name (required for sourceware-style instances, optional for lore.kernel.org)",
                    },
                },
                "required": ["old_message_id", "new_message_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Optional[Dict[str, Any]]):
    """Handle tool calls."""
    arguments = arguments or {}

    try:
        if name == "lkml_get_thread":
            return await handle_lkml_get_thread(client, arguments)
        elif name == "lkml_get_raw":
            return await handle_lkml_get_raw(client, arguments)
        elif name == "lkml_get_user_series":
            return await handle_lkml_get_user_series(client, arguments)
        elif name == "lkml_search_patches":
            return await handle_lkml_search_patches(client, arguments)
        elif name == "lkml_get_patch":
            return await handle_lkml_get_patch(client, arguments)
        elif name == "lkml_get_thread_summary":
            return await handle_lkml_get_thread_summary(client, arguments)
        elif name == "lkml_compare_patch_versions":
            return await handle_lkml_compare_patch_versions(client, arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except LKMLAPIError as e:
        return [TextContent(type="text", text=f"LKML API Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


def _init_options() -> InitializationOptions:
    return InitializationOptions(
        server_name="lkml-mcp",
        server_version="0.1.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )


async def run_stdio() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, _init_options())


def run_sse(host: str, port: int) -> None:
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], _init_options())
        return Response()

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )
    uvicorn.run(app, host=host, port=port)


def run_streamable_http(host: str, port: int) -> None:
    import uvicorn
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.routing import Mount

    session_manager = StreamableHTTPSessionManager(app=server)

    async def handle_mcp(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            yield

    app = Starlette(
        routes=[Mount("/mcp", app=handle_mcp)],
        lifespan=lifespan,
    )
    uvicorn.run(app, host=host, port=port)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lkml-mcp", description="MCP server for LKML thread retrieval")
    parser.add_argument(
        "--transport",
        choices=VALID_TRANSPORTS,
        default=os.environ.get("LKML_MCP_TRANSPORT", DEFAULT_TRANSPORT),
        help="Transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("LKML_MCP_HOST", DEFAULT_HOST),
        help="Bind host for sse/streamable-http (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LKML_MCP_PORT", DEFAULT_PORT)),
        help="Bind port for sse/streamable-http (default: 8772)",
    )
    return parser.parse_args(argv)


def asyncio_main() -> None:
    """Entry point for console scripts."""
    args = _parse_args()
    if args.transport == "stdio":
        asyncio.run(run_stdio())
    elif args.transport == "sse":
        run_sse(args.host, args.port)
    elif args.transport == "streamable-http":
        run_streamable_http(args.host, args.port)
    else:
        raise SystemExit(f"Unknown transport: {args.transport}")


async def main():
    """Legacy stdio entry kept for backwards compatibility."""
    await run_stdio()


if __name__ == "__main__":
    asyncio_main()
