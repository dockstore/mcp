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
"""Tests for the camelCase-to-snake_case helpers shared by the API-backed tools."""

import pytest

from dockstore_mcp.casing import camel_to_snake, normalize_keys


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("id", "id"),
        ("toolId", "tool_id"),
        ("contactUrl", "contact_url"),
        ("descriptorType", "descriptor_type"),
        ("already_snake", "already_snake"),
    ],
)
def test_camel_to_snake(key: str, expected: str) -> None:
    assert camel_to_snake(key) == expected


def test_normalize_keys_walks_nested_dicts_and_lists() -> None:
    payload = {
        "toolId": "abc",
        "organization": {"contactUrl": "mailto:a@b.com"},
        "versions": [{"toolVersionId": "1"}, {"toolVersionId": "2"}],
    }
    assert normalize_keys(payload) == {
        "tool_id": "abc",
        "organization": {"contact_url": "mailto:a@b.com"},
        "versions": [{"tool_version_id": "1"}, {"tool_version_id": "2"}],
    }


def test_normalize_keys_leaves_non_dict_values_alone() -> None:
    assert normalize_keys("plain string") == "plain string"
    assert normalize_keys(42) == 42
    assert normalize_keys(None) is None
