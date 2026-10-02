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
"""Smoke tests against a live Dockstore (production unless ``SMOKE_DOCKSTORE_URL`` says otherwise).

These are read-only and need no credentials. They run only on request (``make smoke``,
or ``pytest -m live``), because they depend on the network and on Dockstore's data, which
changes. So they assert on shape rather than content, and find their inputs by walking the
same lookup chain a model does: list_tools -> get_tool -> get_tool_version ->
get_tool_descriptor_by_path.
"""

import asyncio
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp.exceptions import ToolError

from dockstore_mcp.models import TrsDescriptorType

#: Longest any one tool call may take before the test fails, over the server's own 30s request timeout.
CALL_TIMEOUT = 90.0

#: Descriptor languages the server's file tools accept.
KNOWN_LANGUAGES = {language.value for language in TrsDescriptorType}


async def call(client: Client[Any], name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Call a tool, retrying once on a tool error: a blip on Dockstore's side should not fail the run."""
    for attempt in (1, 2):
        try:
            async with asyncio.timeout(CALL_TIMEOUT):
                return await client.call_tool(name, arguments)
        except ToolError:
            if attempt == 2:
                raise
            await asyncio.sleep(2)
    raise AssertionError("unreachable")


def payload(result: CallToolResult) -> dict[str, Any]:
    """A tool result's plain JSON body, which is easier to walk than the generated models for unions."""
    assert result.structured_content is not None
    return result.structured_content


async def find_workflow_with_files(client: Client[Any]) -> tuple[str, str, str, str]:
    """Walk the lookup chain to a (tool id, version name, language, primary descriptor path) that has files.

    Version names come from list_tools' summaries, not get_tool, so a get_tool failure shows up in its own
    test instead of hiding everything after it.
    """
    page = payload(await call(client, "list_tools", {"limit": 20, "summary": True}))
    candidates = [tool for tool in page["tools"] if tool.get("version_names") and tool.get("descriptor_types")]
    assert candidates, "the first page of list_tools had no tool with versions and a descriptor language"
    for tool in candidates:
        languages = [language for language in tool["descriptor_types"] if language in KNOWN_LANGUAGES]
        for version_name in tool["version_names"][:3] if languages else []:
            arguments = {"tool_id": tool["id"], "version_id": version_name, "files": languages[0]}
            files = payload(await call(client, "get_tool_version", arguments)).get("files") or []
            primary = [file for file in files if file.get("file_type") == "PRIMARY_DESCRIPTOR"]
            if primary:
                return tool["id"], version_name, languages[0], primary[0]["path"]
    raise AssertionError("no tool on the first page of list_tools had a version with a primary descriptor file")


async def test_trs_info_reaches_dockstore(live_client: Client[Any]) -> None:
    async with live_client:
        result = await call(live_client, "get_trs_info", {})
    info = result.data
    assert info.type.artifact.lower() == "trs"
    assert info.organization.name
    assert info.version
    assert {tool_class.name for tool_class in info.tool_classes} >= {"Workflow"}


async def test_local_only_info_needs_no_network(live_client: Client[Any]) -> None:
    async with live_client:
        result = await call(live_client, "get_trs_info", {"local_only": True})
    assert result.data.dockstore_url.startswith("https://")
    assert result.data.id is None


async def test_list_tools_returns_a_page(live_client: Client[Any]) -> None:
    async with live_client:
        result = await call(live_client, "list_tools", {"limit": 3, "summary": True})
    page = result.data
    assert 1 <= len(page.tools) <= 3
    assert page.total is not None and page.total >= len(page.tools)
    assert all(tool.id and tool.name for tool in page.tools)


async def test_list_tools_pages_differ(live_client: Client[Any]) -> None:
    async with live_client:
        first = await call(live_client, "list_tools", {"limit": 3, "offset": 0, "summary": True})
        second = await call(live_client, "list_tools", {"limit": 3, "offset": 1, "summary": True})
    assert first.data.next_offset == 1
    assert {tool.id for tool in first.data.tools}.isdisjoint({tool.id for tool in second.data.tools})


async def test_list_tools_filter_narrows_results(live_client: Client[Any]) -> None:
    async with live_client:
        everything = await call(live_client, "list_tools", {"limit": 1, "summary": True})
        workflows = await call(live_client, "list_tools", {"limit": 1, "summary": True, "tool_class": "Workflow"})
    assert 0 < workflows.data.total <= everything.data.total


async def test_lookup_chain_to_a_descriptor(live_client: Client[Any]) -> None:
    async with live_client:
        tool_id, version, language, path = await find_workflow_with_files(live_client)
        primary = await call(
            live_client,
            "get_tool_descriptor_by_path",
            {"tool_id": tool_id, "version_id": version, "descriptor_type": language},
        )
        by_path = await call(
            live_client,
            "get_tool_descriptor_by_path",
            {"tool_id": tool_id, "version_id": version, "descriptor_type": language, "relative_path": path},
        )
    assert primary.data.content
    assert by_path.data.content
    assert primary.data.url or by_path.data.url


@pytest.mark.xfail(
    raises=ToolError,
    strict=True,
    reason="SEAB-7771: dockstore.org does not page tool versions yet. Remove this marker once it is deployed.",
)
async def test_get_tool_pages_versions(live_client: Client[Any]) -> None:
    async with live_client:
        page = payload(await call(live_client, "list_tools", {"limit": 1, "summary": True}))
        tool_id = page["tools"][0]["id"]
        detail = payload(await call(live_client, "get_tool", {"tool_id": tool_id, "summary": True, "version_limit": 5}))
    assert detail["id"] == tool_id
    assert len(detail["versions"]) <= 5
    assert detail["version_limit"] == 5


async def test_missing_tool_is_a_tool_error(live_client: Client[Any]) -> None:
    async with live_client:
        with pytest.raises(ToolError):
            await live_client.call_tool("get_tool", {"tool_id": "#workflow/github.com/no-such-org/no-such-repo"})
