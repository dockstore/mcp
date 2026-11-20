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
"""Tests for the structured logging of tool calls."""

import json
import logging
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from dockstore_mcp.server import MAX_LOGGED_PARAMS_LENGTH, TOOL_CALL_LOGGER


def _entries(caplog: pytest.LogCaptureFixture) -> list[tuple[int, dict[str, Any]]]:
    records = [record for record in caplog.records if record.name == TOOL_CALL_LOGGER]
    return [(record.levelno, json.loads(record.getMessage())) for record in records]


async def test_a_successful_call_is_logged(client: Client[Any], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=TOOL_CALL_LOGGER)
    async with client:
        await client.list_tools()  # not a tool call, so not logged
        await client.call_tool("get_trs_info", {"local_only": True})
    [(start_level, start), (end_level, end)] = _entries(caplog)
    assert start_level == end_level == logging.INFO
    assert start["event"] == "request_start"
    assert start["method"] == "tools/call"
    assert json.loads(start["payload"]) == {"name": "get_trs_info", "arguments": {"local_only": True}}
    assert end["event"] == "request_success"
    assert isinstance(end["duration_ms"], float)
    assert "client_address" not in start  # no network peer in memory or over stdio


async def test_a_failed_call_is_logged(client: Client[Any], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=TOOL_CALL_LOGGER)
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("get_version", {"version_id": 1, "file_limit": 0})
    [_, (level, end)] = _entries(caplog)
    assert level == logging.ERROR
    assert end["event"] == "request_error"
    assert "file_limit" in end["error"]


async def test_long_params_are_truncated(client: Client[Any], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=TOOL_CALL_LOGGER)
    async with client:
        await client.call_tool("search_entries", {"query": "x" * 5000})
    [(_, start), _] = _entries(caplog)
    assert start["payload"].startswith('{"name":"search_entries"')
    assert len(start["payload"]) == MAX_LOGGED_PARAMS_LENGTH + len("...")
    assert start["payload"].endswith("x...")


def test_an_http_call_is_logged_with_its_address(server: FastMCP, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=TOOL_CALL_LOGGER)
    with TestClient(server.http_app(stateless_http=True)) as http:
        response = http.post(
            "/mcp",
            headers={"accept": "application/json, text/event-stream", "mcp-protocol-version": "2025-06-18"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "get_trs_info", "arguments": {"local_only": True}},
            },
        )
    assert response.status_code == 200
    [(_, start), (_, end)] = _entries(caplog)
    assert start["client_address"] == end["client_address"] == "testclient"
