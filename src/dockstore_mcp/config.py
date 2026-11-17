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
"""Runtime configuration for the Dockstore MCP server.

Every setting can be supplied as an environment variable prefixed with
``DOCKSTORE_MCP_`` (for example ``DOCKSTORE_MCP_PORT=9000``), or placed in a
``.env`` file in the working directory.  See ``.env.example``.
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dockstore_mcp import __version__

Transport = Literal["stdio", "http"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Settings for a single server process."""

    model_config = SettingsConfigDict(
        env_prefix="DOCKSTORE_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    transport: Transport = Field(
        default="stdio",
        description="'stdio' for a locally launched client, 'http' when running as a service.",
    )
    host: str = Field(default="127.0.0.1", description="Interface to bind when transport is 'http'.")
    port: int = Field(default=8000, ge=1, le=65535, description="Port to bind when transport is 'http'.")
    path: str = Field(default="/mcp", description="HTTP path the MCP endpoint is served from.")
    log_level: LogLevel = Field(default="INFO", description="Logging verbosity.")

    dockstore_public_url: str = Field(
        default="https://dockstore.org",
        description="Public base URL of the Dockstore instance, as its users see it; links to entries point here.",
    )
    dockstore_api_url: str | None = Field(
        default=None,
        description=(
            "Base URL of the webservice's Dockstore/TRS APIs, e.g. an internal address for the webservice. "
            "Derived from dockstore_public_url when unset."
        ),
    )

    git_ref: str | None = Field(
        default=None,
        description=(
            "Git tag or ref this server was built from, e.g. '1.21.0'; set at build time. "
            "Falls back to the package version."
        ),
    )

    @field_validator("dockstore_api_url", mode="before")
    @classmethod
    def _empty_api_url_is_unset(cls, value: object) -> object:
        # docker-compose.yml passes "" when DOCKSTORE_API_URL is unset; derive it instead.
        return None if value == "" else value

    @field_validator("dockstore_public_url", "dockstore_api_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value is not None else None

    @field_validator("path")
    @classmethod
    def _require_leading_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("path must start with '/'")
        return value.rstrip("/") or "/"

    @property
    def api_url(self) -> str:
        """Base URL of the webservice's Dockstore/TRS APIs.

        ``dockstore_api_url`` when set. Otherwise it is derived from the public URL: deployed
        instances serve the webservice under ``/api`` behind a proxy, whereas a webservice
        running on localhost is typically reached directly, without the prefix.
        """
        if self.dockstore_api_url is not None:
            return self.dockstore_api_url
        if urlparse(self.dockstore_public_url).hostname == "localhost":
            return self.dockstore_public_url
        return f"{self.dockstore_public_url}/api"

    @property
    def trs_url(self) -> str:
        """Base URL of the instance's GA4GH Tool Registry Service API."""
        return f"{self.api_url}/ga4gh/trs/v2"

    @property
    def server_version(self) -> str:
        """Version this server reports: the git ref it was built from, else the package version."""
        return self.git_ref or __version__

    @property
    def user_agent(self) -> str:
        """User-Agent sent with every request to Dockstore, e.g. 'dockstore-mcp/1.21.0'."""
        return f"dockstore-mcp/{self.server_version}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, read from the environment once."""
    return Settings()
