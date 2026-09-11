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
"""Tests for settings parsing."""

import pytest
from pydantic import ValidationError

from dockstore_mcp.config import Settings


def test_defaults() -> None:
    settings = Settings()
    assert settings.transport == "stdio"
    assert settings.port == 8000
    assert settings.dockstore_url == "https://dockstore.org"


def test_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKSTORE_MCP_TRANSPORT", "http")
    monkeypatch.setenv("DOCKSTORE_MCP_PORT", "9000")
    settings = Settings()
    assert settings.transport == "http"
    assert settings.port == 9000


def test_derived_api_urls() -> None:
    settings = Settings(dockstore_url="https://qa.dockstore.org/")
    assert settings.dockstore_url == "https://qa.dockstore.org"
    assert settings.trs_url == "https://qa.dockstore.org/api/ga4gh/trs/v2"
    assert settings.api_url == "https://qa.dockstore.org/api"


@pytest.mark.parametrize(("field", "value"), [("port", 0), ("path", "mcp"), ("transport", "carrier-pigeon")])
def test_rejects_bad_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})  # type: ignore[arg-type]
