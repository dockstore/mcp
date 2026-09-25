#    Copyright 2026 OICR and UCSC
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
"""Tests for server construction."""

from typing import Any

from fastmcp import Client, FastMCP
from starlette.testclient import TestClient

from dockstore_mcp import __version__


async def test_every_tool_is_advertised(client: Client[Any]) -> None:
    async with client:
        tools = await client.list_tools()
    assert sorted(tool.name for tool in tools) == [
        "get_entry",
        "get_file",
        "get_tool",
        "get_tool_descriptor_by_path",
        "get_tool_version",
        "get_trs_info",
        "get_version",
        "list_tool_versions",
        "list_tools",
        "search_entries",
    ]


def test_health_endpoint(server: FastMCP) -> None:
    with TestClient(server.http_app()) as http:
        response = http.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
