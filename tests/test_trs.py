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
"""Tests for get_trs_info and list_tool_classes.

Unlike the other Dockstore tools, these two are wired up to the real API, so
instead of asserting ``NotImplementedError`` these tests stub the HTTP layer with
an ``httpx2.MockTransport`` and check that a response is parsed correctly.
"""

from typing import Any

import httpx2 as httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

SERVICE_INFO_RESPONSE = {
    "id": "org.dockstore.staging",
    "name": "Dockstore",
    "type": {"group": "org.ga4gh", "artifact": "trs", "version": "2.0.1"},
    "organization": {"name": "Dockstore", "url": "https://dockstore.org"},
    "version": "1.21.0",
    "description": "A tool and workflow registry.",
    "contactUrl": "mailto:support@dockstore.org",
}

TOOL_CLASSES_RESPONSE = [
    {"id": "CommandLineTool", "name": "CommandLineTool", "description": "A single command line tool."},
    {"id": "Workflow", "name": "Workflow", "description": "An ordered set of steps."},
]

#: Canned responses, keyed by path relative to the TRS API root.
RESPONSES = {
    "/service-info": SERVICE_INFO_RESPONSE,
    "/toolClasses": TOOL_CLASSES_RESPONSE,
}

#: The real class, captured before any test monkeypatches ``httpx.AsyncClient``.
_RealAsyncClient = httpx.AsyncClient


def _mock_client_factory(handler: Any) -> Any:
    """Build a stand-in for ``httpx.AsyncClient`` that routes every request through ``handler``."""

    def fake_client(*, timeout: float) -> httpx.AsyncClient:
        return _RealAsyncClient(timeout=timeout, transport=httpx.MockTransport(handler))

    return fake_client


@pytest.fixture(autouse=True)
def _mock_trs_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, httpx.Response]:
    """Route every request trs.py makes through a canned handler instead of the network.

    trs.py now builds its ``httpx.AsyncClient`` once, when the server is constructed,
    so the class can only be swapped before that happens (i.e. from this fixture, not
    from within a test body). A test that wants a different response overrides it here
    instead, since the handler consults ``overrides`` fresh on every request.
    """
    overrides: dict[str, httpx.Response] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/ga4gh/trs/v2")
        if path in overrides:
            return overrides[path]
        if path not in RESPONSES:
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(200, json=RESPONSES[path])

    monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(handler))
    return overrides


async def test_get_trs_info(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_trs_info", {})
    assert result.data.id == "org.dockstore.staging"
    assert result.data.name == "Dockstore"
    assert result.data.type.artifact == "trs"
    assert result.data.type.group == "org.ga4gh"
    assert result.data.organization.name == "Dockstore"
    assert result.data.contact_url == "mailto:support@dockstore.org"


async def test_list_tool_classes(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("list_tool_classes", {})
    assert [tool_class.id for tool_class in result.data] == ["CommandLineTool", "Workflow"]
    assert result.data[1].name == "Workflow"


async def test_get_trs_info_surfaces_http_errors(client: Client[Any], _mock_trs_api: dict[str, httpx.Response]) -> None:
    _mock_trs_api["/service-info"] = httpx.Response(500)

    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("get_trs_info", {})
