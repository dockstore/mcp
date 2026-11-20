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
from typing import Any

import mcp.types as mt
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware, default_serializer
from fastmcp.tools import ToolResult
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

from dockstore_mcp.api import DockstoreApi
from dockstore_mcp.config import Settings, get_settings
from dockstore_mcp.tools import register_all

__all__ = ["create_server", "mcp"]

logger = logging.getLogger(__name__)

#: Logs each MCP message (a request's start, then its success or error and duration; a notification's likewise) as a
#: line of JSON. It propagates to the root logger, which ``__main__`` points at stderr, since stdout belongs to the MCP
#: protocol under stdio.
REQUEST_LOGGER = "dockstore_mcp.requests"

#: Longest a message's logged parameters (as JSON) get before they're cut off with "...".
MAX_LOGGED_PARAMS_LENGTH = 2000

INSTRUCTIONS = """\
Tools for working with Dockstore, a registry of bioinformatics tools and workflows.

Dockstore descriptors are written in CWL, WDL, Nextflow, or Galaxy, and are served
through both the GA4GH Tool Registry Service (TRS) API and Dockstore's own API.
"""


def _params_payload(params: Any) -> str:
    """Serialize a message's parameters, leaving out the many protocol fields that are usually unset."""
    if isinstance(params, BaseModel):
        return params.model_dump_json(by_alias=True, exclude_none=True)
    return default_serializer(params)


class _RequestLogging(StructuredLoggingMiddleware):
    """Structured logging that also records the address a message came from, when it came over HTTP."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # The structured variant never truncates payloads, though its base class can; turn that back on.
        self.max_payload_length = MAX_LOGGED_PARAMS_LENGTH

    def _log_message(self, message: dict[str, str | int | float], log_level: int | None = None) -> None:
        try:
            client = get_http_request().client
        except RuntimeError:  # not over HTTP (stdio, or in memory): there's no address to log
            client = None
        if client is not None:
            message["client_address"] = client.host
        super()._log_message(message, log_level)


class _ConnectPerToolCall(Middleware):
    """Give each tool call a fresh connection pool, so it resolves and connects to Dockstore anew."""

    def __init__(self, api: DockstoreApi) -> None:
        self._api = api

    async def on_call_tool(
        self, context: MiddlewareContext[mt.CallToolRequestParams], call_next: CallNext[mt.CallToolRequestParams, Any]
    ) -> ToolResult:
        async with self._api.connection():
            result: ToolResult = await call_next(context)
            return result


def create_server(settings: Settings | None = None, api: DockstoreApi | None = None) -> FastMCP:
    """Build a server instance with every tool registered.

    Args:
        settings: Configuration to use. Defaults to the process-wide settings
            read from the environment.
        api: Client the tools reach Dockstore through. Defaults to one built
            from ``settings``; tests pass one that answers from canned data.
    """
    settings = settings or get_settings()
    api = api or DockstoreApi(settings)

    mcp: FastMCP = FastMCP(
        name="dockstore",
        version=settings.server_version,
        instructions=INSTRUCTIONS,
        website_url=settings.dockstore_public_url,
        middleware=[
            # Outermost, so a call's duration includes connecting to Dockstore.
            _RequestLogging(
                logger=logging.getLogger(REQUEST_LOGGER), include_payloads=True, payload_serializer=_params_payload
            ),
            _ConnectPerToolCall(api),
        ],
        # Unexpected exceptions can carry internal details, such as the API URL; only ToolErrors reach clients.
        mask_error_details=True,
    )

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> JSONResponse:
        """Liveness probe for the container and any load balancer in front of it."""
        return JSONResponse({"status": "ok", "version": settings.server_version})

    register_all(mcp, settings, api)
    logger.debug(
        "Server configured for Dockstore instance %s (API at %s)",
        settings.dockstore_public_url,
        settings.dockstore_api_url,
    )
    return mcp


#: Module-level instance, for ``fastmcp run dockstore_mcp.server:mcp`` and friends.
mcp = create_server()
