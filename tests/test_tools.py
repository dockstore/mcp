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
"""Tests for the Dockstore lookup tools.

The tools are scaffolding, so these tests cover the shape of what is advertised
to a client, plus the fact that calling one fails cleanly rather than returning
something made up.
"""

from enum import StrEnum
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from dockstore_mcp.models import Entry, EntryField, File, FileField, Version, VersionField

#: Every tool that is scaffolded but not implemented, with valid arguments.
UNIMPLEMENTED = [
    ("search_entries", {"query": "rna-seq"}),
    ("get_entry", {"entry_id": "an-entry"}),
    ("get_version", {"version_id": "a-version"}),
    ("get_file", {"version_id": "a-version", "path": "Dockstore.cwl"}),
]


async def _schema(client: Client[Any], name: str) -> dict[str, Any]:
    async with client:
        tools = await client.list_tools()
    return next(tool.input_schema for tool in tools if tool.name == name)


@pytest.mark.parametrize(("name", "arguments"), UNIMPLEMENTED)
async def test_tools_are_not_implemented_yet(client: Client[Any], name: str, arguments: dict[str, Any]) -> None:
    async with client:
        with pytest.raises(ToolError, match="not implemented"):
            await client.call_tool(name, arguments)


@pytest.mark.parametrize(("name", "arguments"), UNIMPLEMENTED)
async def test_tools_accept_their_arguments(client: Client[Any], name: str, arguments: dict[str, Any]) -> None:
    """A schema mismatch would fail as a validation error instead of a missing body."""
    schema = await _schema(client, name)
    assert set(arguments) <= set(schema["properties"])


async def test_search_takes_every_facet(client: Client[Any]) -> None:
    schema = await _schema(client, "search_entries")
    assert set(schema["properties"]) == {
        "query",
        "name",
        "description",
        "author",
        "organization",
        "edam_topic",
        "edam_operation",
        "input_format",
        "output_format",
        "entry_type",
        "descriptor_type",
        "sort_by",
        "sort_order",
        "limit",
    }
    assert schema.get("required", []) == []


async def test_search_arguments_have_sane_defaults(client: Client[Any]) -> None:
    properties = (await _schema(client, "search_entries"))["properties"]
    assert properties["sort_by"]["default"] == "relevance"
    assert properties["sort_order"]["default"] == "desc"
    assert properties["limit"]["default"] == 10
    assert properties["limit"]["maximum"] == 100


@pytest.mark.parametrize(
    ("name", "required"),
    [("get_entry", ["entry_id"]), ("get_version", ["version_id"]), ("get_file", ["version_id", "path"])],
)
async def test_lookups_require_an_identifier(client: Client[Any], name: str, required: list[str]) -> None:
    schema = await _schema(client, name)
    assert schema["required"] == required
    assert "fields" in schema["properties"]


@pytest.mark.parametrize(("model", "field_enum"), [(Entry, EntryField), (Version, VersionField), (File, FileField)])
async def test_selectable_fields_match_their_model(model: type[BaseModel], field_enum: type[StrEnum]) -> None:
    """Field enums name the attributes they select, so callers cannot ask for a field that does not exist."""
    assert {member.value for member in field_enum} == set(model.model_fields)
    assert all(info.default is None for info in model.model_fields.values())
