#    Copyright 2026 OICR
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
"""Shared test fixtures."""

import os
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP

from dockstore_mcp.config import Settings
from dockstore_mcp.server import create_server


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep settings out of the ambient environment and away from any local .env."""
    for name in list(os.environ):
        if name.startswith("DOCKSTORE_MCP_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def settings() -> Settings:
    """Settings that do not depend on the developer's environment."""
    return Settings(dockstore_url="https://staging.dockstore.org/", transport="stdio")


@pytest.fixture
def server(settings: Settings) -> FastMCP:
    return create_server(settings)


@pytest.fixture
def client(server: FastMCP) -> Client[Any]:
    """A client wired directly to the server, with no transport in between."""
    return Client(server)
