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
"""HTTP access to the Dockstore webservice.

One :class:`DockstoreApi` is built per server and shared by every tool.  Each tool
call gets a connection pool of its own (see :meth:`DockstoreApi.connection`), so a
call resolves the webservice's name and connects afresh, following DNS changes
such as a failover, while the requests within it still share connections.  It
speaks JSON and nothing else: turning a payload
into one of the models in :mod:`dockstore_mcp.models` is the tool's job.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

import httpx2
from fastmcp.exceptions import ToolError

from dockstore_mcp.config import Settings

__all__ = [
    "DEFAULT_TIMEOUT",
    "MAX_CONNECTIONS_PER_CALL",
    "TRS_PATH",
    "BadRequestError",
    "DockstoreApi",
    "DockstoreError",
    "NotFoundError",
]

logger = logging.getLogger(__name__)

#: Seconds to wait on the webservice before giving up on a request.
DEFAULT_TIMEOUT = 30.0

#: Most connections one tool call's pool opens at once; further requests wait for one to free up.
MAX_CONNECTIONS_PER_CALL = 4

#: Where the GA4GH Tool Registry Service V2 API lives, relative to the webservice's root.
TRS_PATH = "/ga4gh/trs/v2"


class DockstoreError(ToolError):
    """Dockstore could not answer a request.

    This derives from :class:`~fastmcp.exceptions.ToolError` so that the message
    reaches the client verbatim: a caller who asked for an entry that does not
    exist needs to be told that, not handed a masked internal error.
    """


class NotFoundError(DockstoreError):
    """Dockstore has nothing at the requested address."""


class BadRequestError(DockstoreError):
    """Dockstore rejected the request as malformed."""


class DockstoreApi:
    """A client for one Dockstore instance's webservice: both its own API and its TRS API (under :data:`TRS_PATH`).

    Connections last no longer than a tool call: the server wraps each call in
    :meth:`connection`, which opens a pool for the call's requests and closes it
    afterwards.  A request made outside :meth:`connection` gets a pool of its own.
    """

    def __init__(self, settings: Settings, transport: httpx2.AsyncBaseTransport | None = None) -> None:
        """Prepare a client.

        Args:
            settings: Which Dockstore instance to talk to.
            transport: Transport to send requests over, shared by every pool, each
                of which closes it on exit, so it must survive being closed
                repeatedly (an ``httpx2.MockTransport`` does). Defaults to a fresh
                real one per pool; tests pass a stub.
        """
        self._base_url = settings.dockstore_api_url
        self._user_agent = settings.user_agent
        self._transport = transport
        self._client: ContextVar[httpx2.AsyncClient | None] = ContextVar("dockstore_api_client", default=None)

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[None]:
        """Send the requests made inside this block over a fresh pool, closed when the block exits.

        The pool connects lazily, so a block that makes no request never contacts
        Dockstore.  Within a block that is already inside one, the outer pool is used.
        """
        if self._client.get() is not None:
            yield
            return
        async with self._new_client() as client:
            token = self._client.set(client)
            try:
                yield
            finally:
                self._client.reset(token)

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``path`` and return the JSON Dockstore answered with, whatever its shape."""
        payload, _ = await self._request("GET", path, params)
        return payload

    async def get_with_headers(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, httpx2.Headers]:
        """GET ``path`` and return the JSON Dockstore answered with, plus the response's headers.

        For paged endpoints, which report where the other pages are in headers.
        """
        return await self._request("GET", path, params)

    async def get_object(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``path`` and return the JSON object Dockstore answered with."""
        payload = await self.get_json(path, params)
        if not isinstance(payload, dict):
            raise DockstoreError(f"Dockstore answered {path} with something other than an object.")
        return payload

    async def get_list(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        """GET ``path`` and return the JSON array Dockstore answered with."""
        payload = await self.get_json(path, params)
        if not isinstance(payload, list):
            raise DockstoreError(f"Dockstore answered {path} with something other than an array.")
        return payload

    async def post_object(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST ``body`` as JSON to ``path`` and return the JSON object Dockstore answered with."""
        payload, _ = await self._request("POST", path, None, body)
        if not isinstance(payload, dict):
            raise DockstoreError(f"Dockstore answered {path} with something other than an object.")
        return payload

    async def _request(
        self, method: str, path: str, params: dict[str, Any] | None, body: dict[str, Any] | None = None
    ) -> tuple[Any, httpx2.Headers]:
        """Make the request and decode the body, returning it with the response's headers.

        httpx's own errors name the full request URL, which may be an internal
        address (``dockstore_api_url``), so they are logged here and never reach
        the client.

        Raises:
            NotFoundError: if Dockstore answered 404.
            BadRequestError: if Dockstore answered 400.
            DockstoreError: if the request failed for any other reason.
        """
        client = self._client.get()
        if client is None:
            async with self.connection():
                return await self._request(method, path, params, body)
        logger.debug("%s %s%s params=%s", method, self._base_url, path, params)
        try:
            response = await client.request(method, path, params=params, json=body)
        except httpx2.RequestError as error:
            logger.warning("Request to %s%s failed: %s", self._base_url, path, error)
            raise DockstoreError("Could not reach Dockstore.") from error

        if response.status_code == httpx2.codes.NOT_FOUND:
            raise NotFoundError(f"Dockstore has nothing at {path}.")
        if response.status_code == httpx2.codes.BAD_REQUEST:
            logger.warning("Dockstore rejected %s%s as malformed", self._base_url, path)
            raise BadRequestError(f"Dockstore rejected the request to {path} as malformed.")
        if response.is_error:
            logger.warning("Dockstore answered %s%s with %s", self._base_url, path, response.status_code)
            raise DockstoreError(f"Dockstore answered with HTTP {response.status_code}.")

        try:
            return response.json(), response.headers
        except ValueError as error:
            logger.warning("Dockstore answered %s%s with a body that is not JSON", self._base_url, path)
            raise DockstoreError("Dockstore answered with a body that is not JSON.") from error

    def _new_client(self) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(
            base_url=self._base_url,
            timeout=DEFAULT_TIMEOUT,
            limits=httpx2.Limits(max_connections=MAX_CONNECTIONS_PER_CALL),
            headers={"User-Agent": self._user_agent},
            transport=self._transport,
        )
