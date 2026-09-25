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

The lookups form a chain: ``list_tools`` yields tool ids,
``get_tool`` yields version names, and ``get_tool_version``'s
file listing yields the paths ``get_tool_descriptor_by_path`` takes.
"""

import asyncio
from typing import Annotated, Any
from urllib.parse import quote

import httpx2 as httpx
from fastmcp import FastMCP
from pydantic import Field

from dockstore_mcp import __version__
from dockstore_mcp.casing import normalize_keys
from dockstore_mcp.config import Settings
from dockstore_mcp.models import (
    FileWrapper,
    Tool,
    ToolClass,
    ToolDetail,
    ToolFile,
    ToolPage,
    ToolSummary,
    ToolVersion,
    ToolVersionSummary,
    ToolVersionWithFiles,
    TrsDescriptorType,
    TrsInfo,
)

__all__ = ["register"]

#: How long to wait for the Dockstore TRS API to respond.
REQUEST_TIMEOUT = 30.0

#: How many tools list_tools returns per page unless asked for more.
#: The TRS default of 1000 would flood a model's context: every tool carries all of
#: its versions.
DEFAULT_PAGE_SIZE = 20

#: How much of a tool's description a summary keeps.
SUMMARY_DESCRIPTION_LENGTH = 200

#: How many version names a summary keeps. Monorepo workflows can have a version
#: for every branch and tag of their repository, over a thousand of them.
SUMMARY_VERSION_LIMIT = 10

ToolId = Annotated[
    str,
    Field(description="TRS tool id, e.g. '#workflow/github.com/org/repo/name', as list_tools gives."),
]
VersionId = Annotated[str, Field(description="Version name, e.g. 'master' or '1.0', as get_tool gives.")]
DescriptorType = Annotated[TrsDescriptorType, Field(description="Descriptor language of the files to fetch.")]
Limit = Annotated[int, Field(ge=1, le=1000, description="Most tools to return in this page.")]
Summary = Annotated[
    bool,
    Field(
        description=(
            "Return each tool as a short summary (id, name, languages, a version count and up to "
            f"{SUMMARY_VERSION_LIMIT} version names, the start of its description) instead of in full. "
            "Much smaller: use it to scan or group many tools."
        )
    ),
]
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


def _summarize(tool: Tool) -> ToolSummary:
    """Reduce ``tool`` to a :class:`ToolSummary`, shortening its description and version list."""
    versions = tool.versions or []
    # Production-ready versions first; sorted() is stable, so the rest keep Dockstore's order.
    version_names = [
        version.name for version in sorted(versions, key=lambda version: not version.is_production) if version.name
    ]
    descriptor_types = sorted({language for version in versions for language in version.descriptor_type or []})
    description = " ".join((tool.description or "").split()) or None
    if description and len(description) > SUMMARY_DESCRIPTION_LENGTH:
        description = description[: SUMMARY_DESCRIPTION_LENGTH - 1].rstrip() + "…"
    return ToolSummary(
        id=tool.id,
        name=tool.name,
        organization=tool.organization,
        tool_class=tool.toolclass.name if tool.toolclass else None,
        descriptor_types=descriptor_types,
        version_names=version_names[:SUMMARY_VERSION_LIMIT],
        version_count=len(version_names),
        versions_truncated=len(version_names) > SUMMARY_VERSION_LIMIT,
        description=description,
    )


def _last_page_offset(response: httpx.Response) -> int | None:
    """The offset in a ``/tools`` response's ``last_page`` header, if it has one."""
    link = response.headers.get("last_page")
    offset = httpx.URL(link).params.get("offset") if link else None
    return int(offset) if offset is not None and offset.isdigit() else None


def register(mcp: FastMCP, settings: Settings) -> None:
    """Add the TRS V2 tools to ``mcp``."""

    # Shared for every call this server handles, so the tools below don't pay a
    # fresh TCP/TLS handshake to Dockstore on every invocation. Reuse this same
    # client as more TRS-backed tools join this module.
    client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers={"User-Agent": settings.user_agent})

    async def get(path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET ``path`` under the TRS API root, raising on an error status."""
        response = await client.get(f"{settings.trs_url}{path}", params=params)
        response.raise_for_status()
        return response

    async def get_json(path: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``path`` under the TRS API root and return its parsed body.

        Unlike service-info, the TRS ``/tools`` responses already use snake_case
        keys, so they skip ``normalize_keys``, which would also mangle data-valued
        keys such as the 'CWL' in ``descriptor_type_version``.
        """
        return (await get(path, params)).json()

    async def get_tool_page(filters: dict[str, Any], limit: int, offset: int, summary: bool) -> ToolPage:
        """Fetch one page of ``/tools`` matching ``filters``, and work out the total across every page.

        Dockstore reports the last page's offset in a ``last_page`` header but no
        total, and computes that offset as ``floor(total / limit)``, which is one
        page past the end whenever ``limit`` divides the total evenly. So the total
        is counted from the last page's contents, fetching it if this isn't it.
        """
        response = await get("/tools", {**filters, "limit": limit, "offset": offset})
        tools = [Tool.model_validate(item) for item in response.json()]
        total = None
        last_offset = _last_page_offset(response)
        if last_offset is not None:
            if last_offset == offset:
                last_page_size = len(tools)
            else:
                last_page = await get_json("/tools", {**filters, "limit": limit, "offset": last_offset})
                last_page_size = len(last_page)
            total = last_offset * limit + last_page_size
        more = total is not None and (offset + 1) * limit < total
        return ToolPage(
            tools=[_summarize(tool) for tool in tools] if summary else tools,
            offset=offset,
            limit=limit,
            total=total,
            next_offset=offset + 1 if more else None,
        )

    def version_path(tool_id: str, version_id: str) -> str:
        return f"/tools/{_segment(tool_id)}/versions/{_segment(version_id)}"

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_trs_info(
        local_only: Annotated[
            bool,
            Field(
                description=(
                    "Report only which Dockstore instance this server is attached to and the server's version, "
                    "without contacting Dockstore: a quick check that the server is up and configured."
                )
            ),
        ] = False,
    ) -> TrsInfo:
        """Describe the Dockstore instance this server is attached to, and its GA4GH Tool Registry Service (TRS) API.

        Use this to identify which Dockstore instance a server is talking to, which
        version of the TRS API it implements, and who operates it, and to see which
        tool classes (for example 'Workflow' or 'CommandLineTool') it sorts entries
        into, e.g. before filtering list_tools by one. It always describes the
        ``dockstore_url`` this server is configured with. Pass ``local_only`` to
        confirm the server is reachable and configured without calling Dockstore.

        Returns:
            The Dockstore URL and server version, plus (unless ``local_only``) the
            service's identifiers, the TRS API version implemented, the organization
            operating it, and every tool class it recognizes.
        """
        local = {"dockstore_url": settings.dockstore_url, "server_version": __version__}
        if local_only:
            return TrsInfo.model_validate(local)
        service_info, tool_classes = await asyncio.gather(get("/service-info"), get("/toolClasses"))
        info = TrsInfo.model_validate({**normalize_keys(service_info.json()), **local})
        info.tool_classes = [ToolClass.model_validate(item) for item in normalize_keys(tool_classes.json())]
        return info

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def list_tools(
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
            str | None, Field(description="Only tools of this class, e.g. 'Workflow'; see get_trs_info.")
        ] = None,
        descriptor_type: Annotated[
            TrsDescriptorType | None, Field(description="Only tools available in this descriptor language.")
        ] = None,
        checker: Annotated[
            bool | None, Field(description="True for only checker workflows, False to exclude them.")
        ] = None,
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
        summary: Summary = False,
    ) -> ToolPage:
        """List one page of the tools and workflows this Dockstore instance's TRS API serves, optionally filtered.

        With no filters this pages through everything; narrow it by name, language,
        class, and other filters. Every filter given must match; text filters match
        substrings. The page's ``total`` says how many tools match in all, so to
        count them, ask for one page with ``limit`` 1. Fetch the next page by passing
        ``next_offset`` as ``offset`` (a page number, not an item index); it is unset
        on the last page. For richer keyword search with facets, the Dockstore
        Search page equivalent is search_entries.

        Returns:
            Up to ``limit`` matching tools, each with all of its versions (or summarized, if ``summary``), plus
            the total and next page's offset.
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
        return await get_tool_page(params, limit, offset, summary)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool(
        tool_id: ToolId,
        summary: Annotated[
            bool,
            Field(
                description=(
                    "Return each version as just its name, meta_version, and is_production instead of in full. "
                    "Much smaller: use it to scan or pick from many versions, then get_tool_version for details."
                )
            ),
        ] = False,
    ) -> ToolDetail:
        """Retrieve one tool or workflow by its TRS id, including every one of its versions.

        Each version's ``name`` is what the version tools take as ``version_id``, and
        its ``descriptor_type`` lists the languages its files can be fetched in.

        A workflow in a monorepo can have a version for every branch and tag of its
        repository, over a thousand of them, so ask for a ``summary`` unless you need
        each version's images or authors.

        Returns:
            The tool's metadata and every one of its versions, in full or (if ``summary``) summarized.
        """
        tool = Tool.model_validate(await get_json(f"/tools/{_segment(tool_id)}"))
        versions: list[ToolVersion] | list[ToolVersionSummary] | None = tool.versions
        if summary and tool.versions is not None:
            versions = [ToolVersionSummary.model_validate(version, from_attributes=True) for version in tool.versions]
        return ToolDetail.model_validate({**dict(tool), "versions": versions})

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool_version(
        tool_id: ToolId,
        version_id: VersionId,
        files: Annotated[
            TrsDescriptorType | None,
            Field(
                description=(
                    "Also list every file of the version in this descriptor language, without their content. "
                    "Omit it for just the version's metadata."
                )
            ),
        ] = None,
    ) -> ToolVersionWithFiles:
        """Retrieve one version of a tool or workflow: its authors, container images, languages, and optionally files.

        Pass ``files`` to also list the version's secondary descriptors, test parameter
        files, and containerfile, then fetch each with get_tool_descriptor_by_path.

        Returns:
            The version's metadata and, if ``files`` is given, each file's path and type
            (primary or secondary descriptor, test file, etc.).
        """
        path = version_path(tool_id, version_id)
        if files is None:
            return ToolVersionWithFiles.model_validate(await get_json(path))
        version, file_list = await asyncio.gather(get_json(path), get_json(f"{path}/{files}/files"))
        return ToolVersionWithFiles.model_validate(
            {**version, "files": [ToolFile.model_validate(item) for item in file_list]}
        )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_tool_descriptor_by_path(
        tool_id: ToolId,
        version_id: VersionId,
        descriptor_type: DescriptorType,
        relative_path: Annotated[
            str | None,
            Field(
                description=(
                    "Path of the file relative to the primary descriptor, as get_tool_version's files give. "
                    "Omit it to fetch the primary descriptor itself."
                )
            ),
        ] = None,
    ) -> FileWrapper:
        """Fetch one file of a version: its primary descriptor, or any other file by path.

        Omit ``relative_path`` for the primary descriptor: the main CWL, WDL, Nextflow,
        etc. file, or notebook. That needs no get_tool_version call first, so the two can
        run together. Otherwise pass any path get_tool_version's files list, including imported
        descriptors, test parameter files, and the containerfile (e.g. Dockerfile),
        which any of the version's descriptor types can fetch.

        Returns:
            The file's content, checksum, and source URL.
        """
        path = f"{version_path(tool_id, version_id)}/{descriptor_type}/descriptor"
        if relative_path is not None:
            path += f"/{_segment(relative_path)}"
        return FileWrapper.model_validate(await get_json(path))
