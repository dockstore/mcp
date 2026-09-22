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
"""GA4GH TRS service metadata: what this Dockstore instance is, and what kinds of
tools it registers.

Unlike the tools in ``entries.py`` and ``search.py``, these two are wired up to the
real Dockstore API: both endpoints are unauthenticated, parameterless GETs against
the TRS V2 API, with small, fixed response shapes.
"""

import logging

import httpx2 as httpx
from fastmcp import FastMCP

from dockstore_mcp.casing import normalize_keys
from dockstore_mcp.config import Settings
from dockstore_mcp.models import ToolClass, TrsInfo

__all__ = ["register"]

logger = logging.getLogger(__name__)

#: How long to wait for the Dockstore TRS API to respond.
REQUEST_TIMEOUT = 30.0


def register(mcp: FastMCP, settings: Settings) -> None:
    """Add the TRS service-info and tool-class tools to ``mcp``."""

    # Shared for every call this server handles, so the tools below don't pay a
    # fresh TCP/TLS handshake to Dockstore on every invocation. Reuse this same
    # client as more TRS-backed tools join this module.
    client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

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
