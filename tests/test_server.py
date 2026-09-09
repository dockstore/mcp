#    Copyright 2026 OICR
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
"""Tests for server construction and the hello tool."""

from typing import Any

from fastmcp import Client, FastMCP
from starlette.testclient import TestClient

from dockstore_mcp import __version__


async def test_hello_is_advertised(client: Client[Any]) -> None:
    async with client:
        tools = await client.list_tools()
    assert [tool.name for tool in tools] == ["hello"]


async def test_hello_greets_by_name(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("hello", {"name": "Dockstore"})
    assert result.data.greeting == "Hello, Dockstore!"
    assert result.data.dockstore_url == "https://staging.dockstore.org"
    assert result.data.server_version == __version__


async def test_hello_has_a_default_name(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("hello", {})
    assert result.data.greeting == "Hello, world!"


def test_health_endpoint(server: FastMCP) -> None:
    with TestClient(server.http_app()) as http:
        response = http.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
