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
"""Tests for the GA4GH TRS V2 tools in trs.py.

Unlike the other Dockstore tools, these are wired up to the real API, so
instead of asserting ``NotImplementedError`` these tests stub the HTTP layer with
an ``httpx2.MockTransport`` and check that a response is parsed correctly.
"""

from typing import Any

import httpx2 as httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from dockstore_mcp import __version__

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

TOOL_ID = "#workflow/github.com/org/repo/name"
VERSION_ID = "feature/branch"

VERSION_RESPONSE = {
    "id": f"{TOOL_ID}:{VERSION_ID}",
    "name": VERSION_ID,
    "url": "https://staging.dockstore.org/api/ga4gh/trs/v2/tools/x/versions/y",
    "author": ["Jane Doe"],
    "is_production": False,
    "images": [
        {
            "checksum": [{"checksum": "abc123", "type": "sha-256"}],
            "image_name": "quay.io/org/image:1.0",
            "image_type": "Docker",
            "registry_host": "quay.io",
            "size": 1024,
            "updated": "2026-09-23T20:42:58Z",
        }
    ],
    "descriptor_type": ["CWL"],
    "descriptor_type_version": {"CWL": ["v1.0"]},
    "containerfile": False,
    "meta_version": "Thu Jan 01 00:00:00 UTC 1970",
    "verified": False,
    "verified_source": [],
    "signed": False,
    "included_apps": [],
}

TOOL_RESPONSE = {
    "id": TOOL_ID,
    "url": "https://staging.dockstore.org/api/ga4gh/trs/v2/tools/x",
    "aliases": [],
    "organization": "org",
    "name": "repo/name",
    "toolclass": {"id": "1", "name": "Workflow", "description": "Workflow"},
    "description": "Does a thing.",
    "meta_version": "2026-01-01 00:00:00.0",
    "has_checker": False,
    "checker_url": "",
    "versions": [VERSION_RESPONSE],
}

DESCRIPTOR_RESPONSE = {
    "checksum": [{"checksum": "def456", "type": "sha-256"}],
    "content": "cwlVersion: v1.0\nclass: Workflow\n",
    "image_type": {},
    "url": "https://raw.githubusercontent.com/org/repo/feature/branch/main.cwl",
}

SECONDARY_PATH = "../tools/step.cwl"

FILES_RESPONSE = [
    {"checksum": {"checksum": "def456", "type": "sha-256"}, "file_type": "PRIMARY_DESCRIPTOR", "path": "main.cwl"},
    {
        "checksum": {"checksum": "789abc", "type": "sha-256"},
        "file_type": "SECONDARY_DESCRIPTOR",
        "path": SECONDARY_PATH,
    },
]

TESTS_RESPONSE = [{"checksum": [], "content": '{"input": 1}', "url": "https://example.org/test.json"}]

CONTAINERFILE_RESPONSE = [{"checksum": [], "content": "FROM ubuntu:24.04\n", "url": "https://example.org/Dockerfile"}]

_VERSION_PATH = f"/tools/{TOOL_ID}/versions/{VERSION_ID}"

#: Canned responses, keyed by (decoded) path relative to the TRS API root.
RESPONSES: dict[str, Any] = {
    "/service-info": SERVICE_INFO_RESPONSE,
    "/toolClasses": TOOL_CLASSES_RESPONSE,
    "/tools": [TOOL_RESPONSE],
    f"/tools/{TOOL_ID}": TOOL_RESPONSE,
    f"/tools/{TOOL_ID}/versions": [VERSION_RESPONSE],
    _VERSION_PATH: VERSION_RESPONSE,
    f"{_VERSION_PATH}/CWL/descriptor": DESCRIPTOR_RESPONSE,
    f"{_VERSION_PATH}/CWL/descriptor/{SECONDARY_PATH}": DESCRIPTOR_RESPONSE,
    f"{_VERSION_PATH}/CWL/files": FILES_RESPONSE,
    f"{_VERSION_PATH}/CWL/tests": TESTS_RESPONSE,
    f"{_VERSION_PATH}/containerfile": CONTAINERFILE_RESPONSE,
}

#: The real class, captured before any test monkeypatches ``httpx.AsyncClient``.
_RealAsyncClient = httpx.AsyncClient


def _mock_client_factory(handler: Any) -> Any:
    """Build a stand-in for ``httpx.AsyncClient`` that routes every request through ``handler``."""

    def fake_client(**kwargs: Any) -> httpx.AsyncClient:
        return _RealAsyncClient(**kwargs, transport=httpx.MockTransport(handler))

    return fake_client


@pytest.fixture
def requests_made() -> list[httpx.Request]:
    """Every request trs.py sends during a test, in order."""
    return []


@pytest.fixture(autouse=True)
def _mock_trs_api(monkeypatch: pytest.MonkeyPatch, requests_made: list[httpx.Request]) -> dict[str, httpx.Response]:
    """Route every request trs.py makes through a canned handler instead of the network.

    trs.py now builds its ``httpx.AsyncClient`` once, when the server is constructed,
    so the class can only be swapped before that happens (i.e. from this fixture, not
    from within a test body). A test that wants a different response overrides it here
    instead, since the handler consults ``overrides`` fresh on every request.
    """
    overrides: dict[str, httpx.Response] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requests_made.append(request)
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


async def test_list_tools_pages(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool("list_tools", {"limit": 5, "offset": 2})
    assert [tool.id for tool in result.data] == [TOOL_ID]
    assert result.data[0].toolclass.name == "Workflow"
    assert result.data[0].versions[0].name == VERSION_ID
    assert dict(requests_made[0].url.params) == {"limit": "5", "offset": "2"}


async def test_list_tools_defaults_to_a_small_page(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        await client.call_tool("list_tools", {})
    assert dict(requests_made[0].url.params) == {"limit": "20", "offset": "0"}


async def test_search_tools_sends_only_given_filters(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool(
            "search_tools",
            {"toolname": "name", "tool_class": "Workflow", "descriptor_type": "NFL", "checker": False},
        )
    assert [tool.id for tool in result.data] == [TOOL_ID]
    assert dict(requests_made[0].url.params) == {
        "toolname": "name",
        "toolClass": "Workflow",
        "descriptorType": "NFL",
        "checker": "false",
        "limit": "20",
        "offset": "0",
    }


async def test_get_tool_encodes_the_id(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool("get_tool", {"tool_id": TOOL_ID})
    assert result.data.id == TOOL_ID
    assert result.data.organization == "org"
    assert requests_made[0].url.raw_path.endswith(b"/tools/%23workflow%2Fgithub.com%2Forg%2Frepo%2Fname")


async def test_list_tool_versions(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("list_tool_versions", {"tool_id": TOOL_ID})
    assert [version.name for version in result.data] == [VERSION_ID]


async def test_get_tool_version(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool("get_tool_version", {"tool_id": TOOL_ID, "version_id": VERSION_ID})
    assert result.data.author == ["Jane Doe"]
    assert result.data.images[0].registry_host == "quay.io"
    assert result.data.images[0].checksum[0].type == "sha-256"
    assert result.data.descriptor_type_version == {"CWL": ["v1.0"]}
    assert requests_made[0].url.raw_path.endswith(b"/versions/feature%2Fbranch")


async def test_get_tool_descriptor(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool(
            "get_tool_descriptor", {"tool_id": TOOL_ID, "version_id": VERSION_ID, "descriptor_type": "CWL"}
        )
    assert result.data.content.startswith("cwlVersion: v1.0")
    assert result.data.checksum[0].checksum == "def456"


async def test_get_tool_descriptor_by_path_encodes_the_path(
    client: Client[Any], requests_made: list[httpx.Request]
) -> None:
    async with client:
        result = await client.call_tool(
            "get_tool_descriptor_by_path",
            {"tool_id": TOOL_ID, "version_id": VERSION_ID, "descriptor_type": "CWL", "relative_path": SECONDARY_PATH},
        )
    assert result.data.content.startswith("cwlVersion")
    assert requests_made[0].url.raw_path.endswith(b"/CWL/descriptor/..%2Ftools%2Fstep.cwl")


async def test_get_tool_files(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool(
            "get_tool_files", {"tool_id": TOOL_ID, "version_id": VERSION_ID, "descriptor_type": "CWL"}
        )
    assert [(file.path, file.file_type) for file in result.data] == [
        ("main.cwl", "PRIMARY_DESCRIPTOR"),
        (SECONDARY_PATH, "SECONDARY_DESCRIPTOR"),
    ]
    assert result.data[1].checksum.checksum == "789abc"


async def test_get_tool_tests(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool(
            "get_tool_tests", {"tool_id": TOOL_ID, "version_id": VERSION_ID, "descriptor_type": "CWL"}
        )
    assert [test.content for test in result.data] == ['{"input": 1}']


async def test_get_tool_containerfile(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_tool_containerfile", {"tool_id": TOOL_ID, "version_id": VERSION_ID})
    assert result.data[0].content == "FROM ubuntu:24.04\n"


async def test_get_tool_rejects_unknown_descriptor_types(client: Client[Any]) -> None:
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "get_tool_descriptor", {"tool_id": TOOL_ID, "version_id": VERSION_ID, "descriptor_type": "PLAIN_CWL"}
            )


async def test_get_tool_surfaces_not_found(client: Client[Any]) -> None:
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("get_tool", {"tool_id": "#workflow/github.com/org/missing"})


async def test_requests_identify_the_server(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        await client.call_tool("get_trs_info", {})
    assert requests_made[0].headers["User-Agent"] == f"dockstore-mcp/{__version__}"
