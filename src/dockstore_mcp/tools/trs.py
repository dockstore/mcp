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
"""GA4GH TRS V2 tools: what this Dockstore instance is, what kinds of tools it
registers, and the tools, versions, and files themselves.

Unlike the tools in ``entries.py`` and ``search.py``, these are wired up to the real
Dockstore API: every one is an unauthenticated GET against the TRS V2 API.

The lookups form a chain: ``list_tools``/``search_tools`` yield tool ids,
``get_tool``/``list_tool_versions`` yield version names, and a version's
``get_tool_files`` listing yields the paths ``get_tool_descriptor_by_path`` takes.
"""

from typing import Annotated, Any
from urllib.parse import quote

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

from dockstore_mcp.casing import normalize_keys
from dockstore_mcp.config import Settings
from dockstore_mcp.models import (
    FileWrapper,
    Tool,
    ToolClass,
    ToolFile,
    ToolVersion,
    TrsDescriptorType,
    TrsInfo,
)

__all__ = ["register"]

#: How long to wait for the Dockstore TRS API to respond.
REQUEST_TIMEOUT = 30.0

#: How many tools list_tools and search_tools return per page unless asked for more.
#: The TRS default of 1000 would flood a model's context: every tool carries all of
#: its versions.
DEFAULT_PAGE_SIZE = 20

ToolId = Annotated[
    str,
    Field(description="TRS tool id, e.g. '#workflow/github.com/org/repo/name', as list_tools or search_tools give."),
]
VersionId = Annotated[str, Field(description="Version name, e.g. 'master' or '1.0', as list_tool_versions gives.")]
DescriptorType = Annotated[TrsDescriptorType, Field(description="Descriptor language of the files to fetch.")]
Limit = Annotated[int, Field(ge=1, le=1000, description="Most tools to return in this page.")]
Offset = Annotated[
    int,
    Field(ge=0, description="Which page to return, counting from 0: Dockstore treats offset as a page number."),
]


def _segment(value: str) -> str:
    """Percent-encode ``value`` as one URL path segment.

    TRS ids, version names, and relative paths all routinely contain '/' (and ids
    a leading '#'), which Dockstore only accepts fully encoded.
    """
    return quote(value, safe="")


def register(mcp: FastMCP, settings: Settings) -> None:
    """Add the TRS V2 tools to ``mcp``."""

    # Shared for every call this server handles, so the tools below don't pay a
    # fresh TCP/TLS handshake to Dockstore on every invocation. Reuse this same
    # client as more TRS-backed tools join this module.
    client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers={"User-Agent": settings.user_agent})

    async def get_json(path: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``path`` under the TRS API root and return its parsed body.

        Unlike service-info, the TRS ``/tools`` responses already use snake_case
        keys, so they skip ``normalize_keys``, which would also mangle data-valued
        keys such as the 'CWL' in ``descriptor_type_version``.
        """
        response = await client.get(f"{settings.trs_url}{path}", params=params)
        response.raise_for_status()
        return response.json()

    def version_path(tool_id: str, version_id: str) -> str:
        return f"/tools/{_segment(tool_id)}/versions/{_segment(version_id)}"

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_trs_info() -> TrsInfo:
        """Describe this Dockstore instance's GA4GH Tool Registry Service (TRS) API.

        Use this to identify which Dockstore instance a server is talking to, which
        version of the TRS API it implements, and who operates it. It takes no
        arguments and always describes the ``dockstore_url`` this server is
        configured with.

        Returns:
            Service metadata: identifiers, the TRS API version implemented, and the
            organization operating the service.
        """
        response = await client.get(f"{settings.trs_url}/service-info")
        response.raise_for_status()
        return TrsInfo.model_validate(normalize_keys(response.json()))

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def list_tool_classes() -> list[ToolClass]:
        """List the tool classes this Dockstore instance's TRS API sorts entries into.

        A tool class (for example 'Workflow' or 'CommandLineTool') is the category
        Dockstore assigns an entry under the GA4GH TRS API. Reach for this to see
        which classes exist, for example before filtering a TRS-level lookup by one.

        Returns:
            Every tool class the service recognizes.
        """
        response = await client.get(f"{settings.trs_url}/toolClasses")
        response.raise_for_status()
        return [ToolClass.model_validate(item) for item in normalize_keys(response.json())]

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def list_tools(limit: Limit = DEFAULT_PAGE_SIZE, offset: Offset = 0) -> list[Tool]:
        """List one page of every tool and workflow this Dockstore instance's TRS API serves.

        Reach for search_tools instead to narrow the list by name, language, class,
        or other filters; this one pages through everything. Ask for the next page by
        incrementing ``offset`` by one (it is a page number, not an item index); a
        page shorter than ``limit`` is the last one.

        Returns:
            Up to ``limit`` tools, each with all of its versions.
        """
        data = await get_json("/tools", {"limit": limit, "offset": offset})
        return [Tool.model_validate(item) for item in data]

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def search_tools(
        name: Annotated[str | None, Field(description="Match against the tool's repository path, e.g. 'gatk'.")] = None,
        toolname: Annotated[str | None, Field(description="Match against the tool or workflow's own name.")] = None,
        description: Annotated[str | None, Field(description="Match against the tool's description.")] = None,
        organization: Annotated[
            str | None, Field(description="Match against the publishing organization, e.g. 'broadinstitute'.")
        ] = None,
        author: Annotated[str | None, Field(description="Match against the tool's author.")] = None,
        registry: Annotated[
            str | None, Field(description="Match against the image or source registry, e.g. 'quay.io'.")
        ] = None,
        alias: Annotated[str | None, Field(description="Match against one of the tool's aliases.")] = None,
        tool_class: Annotated[
            str | None, Field(description="Only tools of this class, e.g. 'Workflow'; see list_tool_classes.")
        ] = None,
        descriptor_type: Annotated[
            TrsDescriptorType | None, Field(description="Only tools available in this descriptor language.")
        ] = None,
        checker: Annotated[
            bool | None, Field(description="True for only checker workflows, False to exclude them.")
        ] = None,
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> list[Tool]:
        """Find tools and workflows through the TRS API by name, language, class, and other filters.

        Every filter given must match; text filters match substrings. Page through
        the results as with list_tools. For richer keyword search with facets, the
        Dockstore Search page equivalent is search_entries.

        Returns:
            Up to ``limit`` matching tools, each with all of its versions.
        """
        filters = {
            "name": name,
            "toolname": toolname,
            "description": description,
            "organization": organization,
            "author": author,
            "registry": registry,
            "alias": alias,
            "toolClass": tool_class,
            "descriptorType": descriptor_type,
            "checker": None if checker is None else str(checker).lower(),
        }
        params = {key: value for key, value in filters.items() if value is not None}
        data = await get_json("/tools", {**params, "limit": limit, "offset": offset})
        return [Tool.model_validate(item) for item in data]

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool(tool_id: ToolId) -> Tool:
        """Retrieve one tool or workflow by its TRS id, including every one of its versions.

        Returns:
            The tool's metadata and its full list of versions.
        """
        return Tool.model_validate(await get_json(f"/tools/{_segment(tool_id)}"))

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def list_tool_versions(tool_id: ToolId) -> list[ToolVersion]:
        """List every version of one tool or workflow.

        Each version's ``name`` is what the other version tools take as
        ``version_id``, and its ``descriptor_type`` lists the languages its files can
        be fetched in.

        Returns:
            Every version of the tool.
        """
        data = await get_json(f"/tools/{_segment(tool_id)}/versions")
        return [ToolVersion.model_validate(item) for item in data]

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool_version(tool_id: ToolId, version_id: VersionId) -> ToolVersion:
        """Retrieve one version of a tool or workflow: its authors, container images, and languages.

        Returns:
            The version's metadata.
        """
        return ToolVersion.model_validate(await get_json(version_path(tool_id, version_id)))

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool_descriptor(
        tool_id: ToolId, version_id: VersionId, descriptor_type: DescriptorType
    ) -> FileWrapper:
        """Fetch the primary descriptor of one version: the main CWL, WDL, Nextflow, etc. file.

        Reach for get_tool_files to see what other files the version has, and
        get_tool_descriptor_by_path to fetch one of them.

        Returns:
            The descriptor's content, checksum, and source URL.
        """
        path = f"{version_path(tool_id, version_id)}/{descriptor_type}/descriptor"
        return FileWrapper.model_validate(await get_json(path))

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool_descriptor_by_path(
        tool_id: ToolId,
        version_id: VersionId,
        descriptor_type: DescriptorType,
        relative_path: Annotated[
            str,
            Field(description="Path of the file relative to the primary descriptor, as get_tool_files gives."),
        ],
    ) -> FileWrapper:
        """Fetch one file of a version by path: an imported descriptor, a config file, and so on.

        Returns:
            The file's content, checksum, and source URL.
        """
        path = f"{version_path(tool_id, version_id)}/{descriptor_type}/descriptor/{_segment(relative_path)}"
        return FileWrapper.model_validate(await get_json(path))

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool_files(tool_id: ToolId, version_id: VersionId, descriptor_type: DescriptorType) -> list[ToolFile]:
        """List every file of one version, without their content.

        Use this to find a version's secondary descriptors, test parameter files, and
        containerfile before fetching one.

        Returns:
            Each file's path and type (primary or secondary descriptor, test file, etc.).
        """
        data = await get_json(f"{version_path(tool_id, version_id)}/{descriptor_type}/files")
        return [ToolFile.model_validate(item) for item in data]

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool_tests(
        tool_id: ToolId, version_id: VersionId, descriptor_type: DescriptorType
    ) -> list[FileWrapper]:
        """Fetch the test parameter files of one version: example inputs for running it.

        Returns:
            The content of every test parameter file; empty if the version has none.
        """
        data = await get_json(f"{version_path(tool_id, version_id)}/{descriptor_type}/tests")
        return [FileWrapper.model_validate(item) for item in data]

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool_containerfile(tool_id: ToolId, version_id: VersionId) -> list[FileWrapper]:
        """Fetch the containerfile (e.g. Dockerfile) that builds one version's image.

        Only some tools have one, typically those registered from a Docker image
        rather than as a workflow; a version whose ``containerfile`` is false has
        none, and the call fails.

        Returns:
            The content of each containerfile.
        """
        data = await get_json(f"{version_path(tool_id, version_id)}/containerfile")
        return [FileWrapper.model_validate(item) for item in data]
