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
"""Construction of the Dockstore MCP server."""

import logging

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from dockstore_mcp import __version__
from dockstore_mcp.config import Settings, get_settings
from dockstore_mcp.tools import register_all

__all__ = ["create_server", "mcp"]

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
Tools for working with Dockstore, a registry of bioinformatics tools and workflows.

Dockstore descriptors are written in CWL, WDL, Nextflow, or Galaxy, and are served
through both the GA4GH Tool Registry Service (TRS) API and Dockstore's own API.
"""


def create_server(settings: Settings | None = None) -> FastMCP:
    """Build a server instance with every tool registered.

    Args:
        settings: Configuration to use. Defaults to the process-wide settings
            read from the environment.
    """
    settings = settings or get_settings()

    mcp: FastMCP = FastMCP(
        name="dockstore",
        version=__version__,
        instructions=INSTRUCTIONS,
        website_url=settings.dockstore_url,
    )

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> JSONResponse:
        """Liveness probe for the container and any load balancer in front of it."""
        return JSONResponse({"status": "ok", "version": __version__})

    register_all(mcp, settings)
    logger.debug("Server built against Dockstore instance %s", settings.dockstore_url)
    return mcp


#: Module-level instance, for ``fastmcp run dockstore_mcp.server:mcp`` and friends.
mcp = create_server()
