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

TEST_FILE_RESPONSE = {"checksum": [], "content": '{"input": 1}', "url": "https://example.org/test.json"}

CONTAINERFILE_RESPONSE = {"checksum": [], "content": "FROM ubuntu:24.04\n", "url": "https://example.org/Dockerfile"}

_VERSION_PATH = f"/tools/{TOOL_ID}/versions/{VERSION_ID}"

#: Canned responses, keyed by (decoded) path relative to the TRS API root.
RESPONSES: dict[str, Any] = {
    "/service-info": SERVICE_INFO_RESPONSE,
    "/toolClasses": TOOL_CLASSES_RESPONSE,
    f"/tools/{TOOL_ID}": TOOL_RESPONSE,
    _VERSION_PATH: VERSION_RESPONSE,
    f"{_VERSION_PATH}/CWL/descriptor": DESCRIPTOR_RESPONSE,
    f"{_VERSION_PATH}/CWL/descriptor/{SECONDARY_PATH}": DESCRIPTOR_RESPONSE,
    f"{_VERSION_PATH}/CWL/files": FILES_RESPONSE,
    f"{_VERSION_PATH}/CWL/descriptor/test.json": TEST_FILE_RESPONSE,
    f"{_VERSION_PATH}/CWL/descriptor/Dockerfile": CONTAINERFILE_RESPONSE,
    f"{_VERSION_PATH}/JUPYTER/files": [{"checksum": None, "file_type": "PRIMARY_DESCRIPTOR", "path": "main.ipynb"}],
}

#: Every tool the fake ``/tools`` endpoint pages through: TOOL_RESPONSE, then six more.
CATALOG = [TOOL_RESPONSE, *({**TOOL_RESPONSE, "id": f"{TOOL_ID}-{i}"} for i in range(1, 7))]


def _tools_page(request: httpx.Request) -> httpx.Response:
    """Serve one page of CATALOG the way Dockstore does.

    That includes its ``last_page`` header, whose offset Dockstore computes as
    ``floor(total / limit)``: one page past the end when ``limit`` divides the total.
    """
    limit = int(request.url.params["limit"])
    offset = int(request.url.params["offset"])
    last_page = request.url.copy_merge_params({"offset": str(len(CATALOG) // limit)})
    page = CATALOG[offset * limit : (offset + 1) * limit]
    return httpx.Response(200, json=page, headers={"last_page": str(last_page)})


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
        if path == "/tools":
            return _tools_page(request)
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
    assert [tool_class.id for tool_class in result.data.tool_classes] == ["CommandLineTool", "Workflow"]
    assert result.data.tool_classes[1].name == "Workflow"
    assert result.data.dockstore_url == "https://staging.dockstore.org"
    assert result.data.server_version == __version__


async def test_get_trs_info_local_only_skips_dockstore(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool("get_trs_info", {"local_only": True})
    assert result.data.dockstore_url == "https://staging.dockstore.org"
    assert result.data.server_version == __version__
    assert (result.data.id, result.data.tool_classes) == (None, [])
    assert requests_made == []


@pytest.mark.parametrize("path", ["/service-info", "/toolClasses"])
async def test_get_trs_info_surfaces_http_errors(
    client: Client[Any], _mock_trs_api: dict[str, httpx.Response], path: str
) -> None:
    _mock_trs_api[path] = httpx.Response(500)

    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("get_trs_info", {})


async def test_list_tools_pages(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool("list_tools", {"limit": 5, "offset": 0})
    assert [tool.id for tool in result.data.tools] == [tool["id"] for tool in CATALOG[:5]]
    assert result.data.tools[0].toolclass.name == "Workflow"
    assert result.data.tools[0].versions[0].name == VERSION_ID
    assert (result.data.offset, result.data.limit, result.data.total, result.data.next_offset) == (0, 5, 7, 1)
    # The total needs the last page's size, so that page is fetched too.
    assert [dict(request.url.params) for request in requests_made] == [
        {"limit": "5", "offset": "0"},
        {"limit": "5", "offset": "1"},
    ]


async def test_list_tools_last_page(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool("list_tools", {"limit": 5, "offset": 1})
    assert len(result.data.tools) == 2
    assert (result.data.total, result.data.next_offset) == (7, None)
    assert len(requests_made) == 1


@pytest.mark.parametrize("limit", [1, 7])
async def test_list_tools_counts_evenly_divided_totals(client: Client[Any], limit: int) -> None:
    # Dockstore's last_page points one page past the end here, at an empty page.
    async with client:
        result = await client.call_tool("list_tools", {"limit": limit, "offset": 0})
    assert result.data.total == 7
    assert result.data.next_offset == (1 if limit == 1 else None)


async def test_list_tools_past_the_end(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("list_tools", {"limit": 5, "offset": 9})
    assert (result.data.tools, result.data.total, result.data.next_offset) == ([], 7, None)


async def test_list_tools_without_a_last_page_header(
    client: Client[Any], _mock_trs_api: dict[str, httpx.Response]
) -> None:
    _mock_trs_api["/tools"] = httpx.Response(200, json=[TOOL_RESPONSE])

    async with client:
        result = await client.call_tool("list_tools", {})
    assert [tool.id for tool in result.data.tools] == [TOOL_ID]
    assert (result.data.total, result.data.next_offset) == (None, None)


async def test_list_tools_summarizes(client: Client[Any], _mock_trs_api: dict[str, httpx.Response]) -> None:
    long_readme = "# Title\n\n" + "word " * 100
    tool = {**TOOL_RESPONSE, "description": long_readme}
    tool["versions"] = [VERSION_RESPONSE, {**VERSION_RESPONSE, "name": "1.0", "descriptor_type": ["WDL", "CWL"]}]
    _mock_trs_api["/tools"] = httpx.Response(200, json=[tool])

    async with client:
        result = await client.call_tool("list_tools", {"summary": True})
    assert result.structured_content is not None
    summary = result.structured_content["tools"][0]
    assert summary["id"] == TOOL_ID
    assert summary["tool_class"] == "Workflow"
    assert summary["descriptor_types"] == ["CWL", "WDL"]
    assert summary["version_names"] == [VERSION_ID, "1.0"]
    assert (summary["version_count"], summary["versions_truncated"]) == (2, False)
    assert summary["description"].startswith("# Title word word")
    assert len(summary["description"]) == 200
    assert summary["description"].endswith("…")
    assert "versions" not in summary


async def test_summary_caps_version_names(client: Client[Any], _mock_trs_api: dict[str, httpx.Response]) -> None:
    versions = [{**VERSION_RESPONSE, "name": f"branch-{i}", "is_production": i == 25} for i in range(30)]
    tool = {**TOOL_RESPONSE, "versions": versions}
    _mock_trs_api["/tools"] = httpx.Response(200, json=[tool])

    async with client:
        result = await client.call_tool("list_tools", {"summary": True})
    assert result.structured_content is not None
    summary = result.structured_content["tools"][0]
    assert summary["version_names"] == ["branch-25"] + [f"branch-{i}" for i in range(9)]
    assert (summary["version_count"], summary["versions_truncated"]) == (30, True)


async def test_list_tools_filters_and_summarizes(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("list_tools", {"toolname": "name", "summary": True, "limit": 5})
    page = result.structured_content
    assert page is not None
    assert [tool["id"] for tool in page["tools"]] == [tool["id"] for tool in CATALOG[:5]]
    assert page["total"] == 7
    assert page["tools"][0]["description"] == "Does a thing."


async def test_list_tools_returns_full_tools_by_default(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("list_tools", {"limit": 1})
    assert result.structured_content is not None
    assert result.structured_content["tools"][0]["versions"][0]["name"] == VERSION_ID


async def test_list_tools_defaults_to_a_small_page(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        await client.call_tool("list_tools", {})
    assert dict(requests_made[0].url.params) == {"limit": "20", "offset": "0"}


async def test_list_tools_sends_only_given_filters(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool(
            "list_tools",
            {"toolname": "name", "tool_class": "Workflow", "descriptor_type": "NFL", "checker": False, "limit": 5},
        )
    assert result.data.total == 7
    filters = {"toolname": "name", "toolClass": "Workflow", "descriptorType": "NFL", "checker": "false"}
    # The last page, fetched for the total, is filtered the same way.
    assert [dict(request.url.params) for request in requests_made] == [
        {**filters, "limit": "5", "offset": "0"},
        {**filters, "limit": "5", "offset": "1"},
    ]


async def test_get_tool_encodes_the_id(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool("get_tool", {"tool_id": TOOL_ID})
    assert result.data.id == TOOL_ID
    assert result.data.organization == "org"
    assert requests_made[0].url.raw_path.endswith(b"/tools/%23workflow%2Fgithub.com%2Forg%2Frepo%2Fname")


async def test_get_tool_returns_full_versions_by_default(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_tool", {"tool_id": TOOL_ID})
    assert result.structured_content is not None
    [version] = result.structured_content["versions"]
    assert version["name"] == VERSION_ID
    assert version["images"][0]["registry_host"] == "quay.io"


async def test_get_tool_summarizes_versions(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_tool", {"tool_id": TOOL_ID, "summary": True})
    assert result.structured_content is not None
    assert result.structured_content["organization"] == "org"
    [version] = result.structured_content["versions"]
    assert set(version) == {"name", "meta_version", "is_production"}
    assert version["name"] == VERSION_ID


async def test_get_tool_version(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        result = await client.call_tool("get_tool_version", {"tool_id": TOOL_ID, "version_id": VERSION_ID})
    assert result.data.author == ["Jane Doe"]
    assert result.data.images[0].registry_host == "quay.io"
    assert result.data.images[0].checksum[0].type == "sha-256"
    assert result.data.descriptor_type_version == {"CWL": ["v1.0"]}
    assert requests_made[0].url.raw_path.endswith(b"/versions/feature%2Fbranch")
    assert result.data.files is None
    assert len(requests_made) == 1


async def test_get_tool_descriptor_by_path_defaults_to_the_primary_descriptor(
    client: Client[Any], requests_made: list[httpx.Request]
) -> None:
    async with client:
        result = await client.call_tool(
            "get_tool_descriptor_by_path", {"tool_id": TOOL_ID, "version_id": VERSION_ID, "descriptor_type": "CWL"}
        )
    assert result.data.content.startswith("cwlVersion: v1.0")
    assert result.data.checksum[0].checksum == "def456"
    assert requests_made[0].url.raw_path.endswith(b"/CWL/descriptor")


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


async def test_get_tool_version_with_files(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool(
            "get_tool_version", {"tool_id": TOOL_ID, "version_id": VERSION_ID, "files": "CWL"}
        )
    assert result.data.author == ["Jane Doe"]
    assert [(file.path, file.file_type) for file in result.data.files] == [
        ("main.cwl", "PRIMARY_DESCRIPTOR"),
        (SECONDARY_PATH, "SECONDARY_DESCRIPTOR"),
    ]
    assert result.data.files[1].checksum.checksum == "789abc"


@pytest.mark.parametrize(
    ("relative_path", "content"), [("test.json", '{"input": 1}'), ("Dockerfile", "FROM ubuntu:24.04\n")]
)
async def test_get_tool_descriptor_by_path_fetches_tests_and_containerfiles(
    client: Client[Any], relative_path: str, content: str
) -> None:
    async with client:
        result = await client.call_tool(
            "get_tool_descriptor_by_path",
            {"tool_id": TOOL_ID, "version_id": VERSION_ID, "descriptor_type": "CWL", "relative_path": relative_path},
        )
    assert result.data.content == content


async def test_get_tool_version_with_files_for_a_notebook(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool(
            "get_tool_version", {"tool_id": TOOL_ID, "version_id": VERSION_ID, "files": "JUPYTER"}
        )
    assert [file.path for file in result.data.files] == ["main.ipynb"]


async def test_get_tool_rejects_unknown_descriptor_types(client: Client[Any]) -> None:
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "get_tool_descriptor_by_path",
                {"tool_id": TOOL_ID, "version_id": VERSION_ID, "descriptor_type": "PLAIN_CWL"},
            )


async def test_get_tool_surfaces_not_found(client: Client[Any]) -> None:
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("get_tool", {"tool_id": "#workflow/github.com/org/missing"})


async def test_requests_identify_the_server(client: Client[Any], requests_made: list[httpx.Request]) -> None:
    async with client:
        await client.call_tool("get_trs_info", {})
    assert requests_made[0].headers["User-Agent"] == f"dockstore-mcp/{__version__}"
