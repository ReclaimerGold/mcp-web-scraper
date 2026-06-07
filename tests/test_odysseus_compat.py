"""Compatibility tests mirroring Odysseus Streamable HTTP MCP client usage."""

from __future__ import annotations

import asyncio
import socket
from contextlib import AsyncExitStack

import httpx
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_web_scraper.config import Settings
from mcp_web_scraper.server import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _wait_for_health(url: str, timeout_s: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout_s
    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                response = await client.get(url, timeout=0.5)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.05)
    raise RuntimeError(f"Server did not become ready at {url}")


@pytest.fixture
async def mcp_base_url() -> str:
    port = _free_port()
    app = create_app(Settings(MCP_API_KEY=""))
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await _wait_for_health(f"http://127.0.0.1:{port}/health")

    yield f"http://127.0.0.1:{port}/mcp"

    server.should_exit = True
    await task


@pytest.mark.asyncio
async def test_odysseus_streamable_http_initialize_and_list_tools(mcp_base_url: str) -> None:
    """Odysseus uses transport=http with streamablehttp_client + list_tools."""
    async with AsyncExitStack() as stack:
        transport = await stack.enter_async_context(streamable_http_client(mcp_base_url))
        read_stream, write_stream, _get_session_id = transport
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))

        await session.initialize()
        tools_result = await session.list_tools()

    names = {tool.name for tool in tools_result.tools}
    assert names == {"scrape_url", "extract_from_html"}

    scrape_tool = next(t for t in tools_result.tools if t.name == "scrape_url")
    schema = scrape_tool.inputSchema
    assert schema["type"] == "object"
    assert "url" in schema["properties"]
    assert "url" in schema.get("required", [])


@pytest.mark.asyncio
async def test_missing_api_key_returns_403_not_401() -> None:
    """A 401 would make Odysseus start OAuth; static API keys must use 403."""
    port = _free_port()
    app = create_app(Settings(MCP_API_KEY="secret"))
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await _wait_for_health(f"http://127.0.0.1:{port}/health")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://127.0.0.1:{port}/mcp",
                headers={
                    "accept": "application/json, text/event-stream",
                    "content-type": "application/json",
                },
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
        assert response.status_code == 403
    finally:
        server.should_exit = True
        await task
