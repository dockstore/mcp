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
"""Tests for the Dockstore lookup tools.

Two of the tools are still scaffolding, so the tests for those cover the shape of
what is advertised to a client, plus the fact that calling one fails cleanly
rather than returning something made up.  ``get_entry`` is implemented, and is
exercised against the canned Dockstore in :mod:`tests.fake_dockstore`.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from dockstore_mcp.models import (
    DescriptorLanguage,
    Entry,
    EntryField,
    EntryType,
    File,
    FileField,
    Version,
    VersionField,
)
from dockstore_mcp.tools.entries import DEFAULT_ENTRY_FIELDS
from fake_dockstore import CATEGORIES, FakeDockstore

#: Every tool that is scaffolded but not implemented, with valid arguments.
UNIMPLEMENTED = [
    ("search_entries", {"query": "rna-seq"}),
    ("get_version", {"version_id": "a-version"}),
    ("get_file", {"version_id": "a-version", "path": "Dockstore.cwl"}),
]

#: Arguments that reach the canned Dockstore, for the tools that are implemented.
IMPLEMENTED = [("get_entry", {"entry_id": "16247"})]


async def _schema(client: Client[Any], name: str) -> dict[str, Any]:
    async with client:
        tools = await client.list_tools()
    return next(tool.input_schema for tool in tools if tool.name == name)


@pytest.mark.parametrize(("name", "arguments"), UNIMPLEMENTED)
async def test_tools_are_not_implemented_yet(client: Client[Any], name: str, arguments: dict[str, Any]) -> None:
    async with client:
        with pytest.raises(ToolError, match="not implemented"):
            await client.call_tool(name, arguments)


@pytest.mark.parametrize(("name", "arguments"), UNIMPLEMENTED + IMPLEMENTED)
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
        "subject_area",
        "operation",
        "input_format",
        "output_format",
        "input_data",
        "output_data",
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


async def _get_entry(client: Client[Any], **arguments: Any) -> Any:
    """Call get_entry and return the entry the client rebuilt from the response."""
    async with client:
        result = await client.call_tool("get_entry", arguments)
    return result.data


async def _populated_fields(client: Client[Any], **arguments: Any) -> set[str]:
    """The names of the fields get_entry answered with a value for."""
    async with client:
        result = await client.call_tool("get_entry", arguments)
    assert result.structured_content is not None
    return {name for name, value in result.structured_content.items() if value is not None}


async def test_get_entry_summarizes_a_workflow(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id="16247")
    assert entry.id == "16247"
    assert entry.entry_type == EntryType.WORKFLOW
    assert entry.descriptor_type == DescriptorLanguage.GALAXY
    assert entry.name == "COVID-19-ARTIC-ILLUMINA"
    assert entry.organization == "iwc-workflows"
    assert entry.path == ("github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA")
    assert entry.authors == ["IWC"]  # The author with no name is dropped.
    assert entry.default_version == "v0.5.2"
    assert entry.version_ids == ["117122", "117123"]
    assert entry.updated_at == datetime(2026, 5, 13, 15, 33, 42, tzinfo=UTC)
    assert entry.url == (
        "https://staging.dockstore.org/workflows/"
        "github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA"
    )


async def test_get_entry_returns_the_summary_fields_and_no_others(client: Client[Any]) -> None:
    populated = await _populated_fields(client, entry_id="16247")
    assert populated == {field.value for field in DEFAULT_ENTRY_FIELDS}
    # The README is in the payload Dockstore answered with, but nobody asked for it.
    assert "description" not in populated


async def test_get_entry_returns_only_the_requested_fields(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id="16247", fields=["name", "description", "doi", "star_count"])
    assert entry.name == "COVID-19-ARTIC-ILLUMINA"
    assert entry.description is not None
    assert entry.description.startswith("# COVID-19")
    assert entry.doi == "10.5281/zenodo.15685746"
    assert entry.star_count == 2
    assert entry.id is None
    assert entry.version_ids is None


async def test_get_entry_finds_a_tool_too(client: Client[Any]) -> None:
    """Tools are not served by the endpoint that answers for everything else."""
    entry = await _get_entry(client, entry_id="188", fields=["entry_type", "name", "path", "registry", "url"])
    assert entry.entry_type == EntryType.TOOL
    assert entry.name == "pcawg-dkfz-workflow"
    assert entry.path == "quay.io/pancancer/pcawg-dkfz-workflow"
    assert entry.registry == "quay.io"
    assert entry.url == "https://staging.dockstore.org/containers/quay.io/pancancer/pcawg-dkfz-workflow"


async def test_get_entry_reads_a_tools_differently_spelled_fields(client: Client[Any]) -> None:
    entry = await _get_entry(
        client,
        entry_id="188",
        fields=["organization", "descriptor_type", "source_control", "star_count", "is_verified"],
    )
    assert entry.organization == "pancancer"  # A tool calls this its namespace.
    assert entry.descriptor_type == DescriptorLanguage.CWL  # A tool can have several.
    assert entry.source_control == "github.com"  # Only a workflow states this outright.
    assert entry.star_count == 0
    assert entry.is_verified is True


async def test_get_entry_sorts_categories_into_their_fields(client: Client[Any]) -> None:
    entry = await _get_entry(
        client,
        entry_id="16247",
        fields=[
            "categories",
            "subject_areas",
            "operations",
            "input_formats",
            "output_formats",
            "input_data",
            "output_data",
        ],
    )
    assert entry.categories == ["COVID-19"]
    assert entry.subject_areas == ["Virology"]
    assert entry.operations == ["Variant calling"]
    assert entry.input_formats == ["FASTQ-sanger"]
    assert entry.output_formats == ["VCF"]
    assert entry.input_data == ["Short-read sequencing data"]
    assert entry.output_data == ["Variant call data"]
    # Every canned category is accounted for exactly once.
    sorted_labels = entry.categories + entry.subject_areas + entry.operations
    sorted_labels += entry.input_formats + entry.output_formats + entry.input_data + entry.output_data
    assert len(sorted_labels) == len(CATEGORIES)


async def test_get_entry_asks_dockstore_for_no_more_than_it_needs(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    await _get_entry(client, entry_id="16247", fields=["name"])
    assert dockstore.paths() == ["/api/workflows/published/16247"]
    assert "include" not in dockstore.requests[0].url.params


async def test_get_entry_asks_for_versions_and_categories_when_they_are_wanted(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    await _get_entry(client, entry_id="16247", fields=["version_ids", "operations"])
    assert dockstore.paths() == ["/api/workflows/published/16247", "/api/entries/16247/categories"]
    assert dockstore.requests[0].url.params["include"] == "versions"


async def test_get_entry_rejects_something_that_is_not_an_identifier(client: Client[Any]) -> None:
    async with client:
        with pytest.raises(ToolError, match="not a Dockstore entry identifier"):
            await client.call_tool("get_entry", {"entry_id": "github.com/iwc-workflows/sars-cov-2"})


async def test_get_entry_reports_an_entry_that_is_not_there(client: Client[Any], dockstore: FakeDockstore) -> None:
    async with client:
        with pytest.raises(ToolError, match="no published entry with identifier '404'"):
            await client.call_tool("get_entry", {"entry_id": "404"})
    # Both endpoints were tried before giving up.
    assert dockstore.paths() == ["/api/workflows/published/404", "/api/containers/published/404"]
