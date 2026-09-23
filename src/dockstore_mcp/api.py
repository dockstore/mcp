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

One :class:`DockstoreApi` is built per server and shared by every tool, so that
calls reuse connections.  It speaks JSON and nothing else: turning a payload
into one of the models in :mod:`dockstore_mcp.models` is the tool's job.
"""

import logging
from typing import Any

import httpx2
from fastmcp.exceptions import ToolError

from dockstore_mcp import __version__
from dockstore_mcp.config import Settings

__all__ = ["DEFAULT_TIMEOUT", "DockstoreApi", "DockstoreError", "NotFoundError"]

logger = logging.getLogger(__name__)

#: Seconds to wait on the webservice before giving up on a request.
DEFAULT_TIMEOUT = 30.0


class DockstoreError(ToolError):
    """Dockstore could not answer a request.

    This derives from :class:`~fastmcp.exceptions.ToolError` so that the message
    reaches the client verbatim: a caller who asked for an entry that does not
    exist needs to be told that, not handed a masked internal error.
    """


class NotFoundError(DockstoreError):
    """Dockstore has nothing at the requested address."""


class DockstoreApi:
    """A client for one Dockstore instance's own (non-TRS) API.

    The underlying connection pool is opened on the first request and closed by
    :meth:`aclose`, which the server calls when it shuts down.
    """

    def __init__(self, settings: Settings, transport: httpx2.AsyncBaseTransport | None = None) -> None:
        """Prepare a client.

        Args:
            settings: Which Dockstore instance to talk to.
            transport: Transport to send requests over. Defaults to a real one;
                tests pass a stub.
        """
        self._base_url = settings.api_url
        self._transport = transport
        self._client: httpx2.AsyncClient | None = None

    async def get_object(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``path`` and return the JSON object Dockstore answered with."""
        payload = await self._request("GET", path, params)
        if not isinstance(payload, dict):
            raise DockstoreError(f"Dockstore answered {path} with something other than an object.")
        return payload

    async def get_list(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        """GET ``path`` and return the JSON array Dockstore answered with."""
        payload = await self._request("GET", path, params)
        if not isinstance(payload, list):
            raise DockstoreError(f"Dockstore answered {path} with something other than an array.")
        return payload

    async def post_object(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST ``body`` as JSON to ``path`` and return the JSON object Dockstore answered with."""
        payload = await self._request("POST", path, None, body)
        if not isinstance(payload, dict):
            raise DockstoreError(f"Dockstore answered {path} with something other than an object.")
        return payload

    async def aclose(self) -> None:
        """Close the connection pool, if one was ever opened."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self, method: str, path: str, params: dict[str, Any] | None, body: dict[str, Any] | None = None
    ) -> Any:
        """Make the request and decode the body.

        Raises:
            NotFoundError: if Dockstore answered 404.
            DockstoreError: if the request failed for any other reason.
        """
        client = self._open()
        logger.debug("%s %s%s params=%s", method, self._base_url, path, params)
        try:
            response = await client.request(method, path, params=params, json=body)
        except httpx2.RequestError as error:
            logger.warning("Request to %s%s failed: %s", self._base_url, path, error)
            raise DockstoreError(f"Could not reach Dockstore at {self._base_url}.") from error

        if response.status_code == httpx2.codes.NOT_FOUND:
            raise NotFoundError(f"Dockstore has nothing at {path}.")
        if response.is_error:
            logger.warning("Dockstore answered %s%s with %s", self._base_url, path, response.status_code)
            raise DockstoreError(f"Dockstore answered with HTTP {response.status_code}.")

        try:
            return response.json()
        except ValueError as error:
            logger.warning("Dockstore answered %s%s with a body that is not JSON", self._base_url, path)
            raise DockstoreError("Dockstore answered with a body that is not JSON.") from error

    def _open(self) -> httpx2.AsyncClient:
        if self._client is None:
            self._client = httpx2.AsyncClient(
                base_url=self._base_url,
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": f"dockstore-mcp/{__version__}"},
                transport=self._transport,
            )
        return self._client
