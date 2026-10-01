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
"""Fixtures for the live smoke tests, which talk to a real Dockstore."""

import os
from typing import Any

import pytest
from fastmcp import Client

from dockstore_mcp.config import Settings
from dockstore_mcp.server import create_server

#: Where the smoke tests point. Not a ``DOCKSTORE_MCP_*`` name: the autouse fixture in
#: the parent conftest scrubs those so unit tests never see a developer's environment.
URL_VARIABLE = "SMOKE_DOCKSTORE_URL"
DEFAULT_URL = "https://dockstore.org"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark everything under tests/live as ``live``, so the default run skips it."""
    for item in items:
        if "/tests/live/" in str(item.path).replace(os.sep, "/"):
            item.add_marker(pytest.mark.live)


@pytest.fixture
def live_client() -> Client[Any]:
    """A client wired in memory to a server attached to the real Dockstore, with its real HTTP stack."""
    settings = Settings(dockstore_url=os.environ.get(URL_VARIABLE, DEFAULT_URL), transport="stdio")
    return Client(create_server(settings))
