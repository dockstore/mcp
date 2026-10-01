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

One of the tools is still scaffolding, so the tests for it cover the shape of
what is advertised to a client, plus the fact that calling it fails cleanly
rather than returning something made up.  ``get_entry``, ``get_version``, and
``search_entries`` are implemented, and are exercised against the canned Dockstore
in :mod:`tests.fake_dockstore`.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import ANY

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from dockstore_mcp.models import (
    DescriptorLanguage,
    Entry,
    EntryType,
    ReferenceType,
    Version,
)
from fake_dockstore import (
    CATEGORIES,
    SEARCH_HITS,
    TOOL,
    WORKFLOW,
    WORKFLOW_FILES,
    FakeDockstore,
)

#: The TRS identifiers of the canned workflow and tool.
WORKFLOW_ID = WORKFLOW["trsId"]
TOOL_ID = TOOL["trsId"]

#: The TRS identifier of the canned workflow's default version.
VERSION_ID = f"{WORKFLOW_ID}:v0.5.2"

#: Every tool that is scaffolded but not implemented, with valid arguments.
UNIMPLEMENTED: list[tuple[str, dict[str, Any]]] = [
    ("get_file", {"version_id": VERSION_ID, "path": "Dockstore.cwl"}),
]

#: Arguments that reach the canned Dockstore, for the tools that are implemented.
IMPLEMENTED: list[tuple[str, dict[str, Any]]] = [
    ("get_entry", {"entry_id": WORKFLOW_ID}),
    (
        "search_entries",
        {
            "query": "rna-seq",
            "type": "workflow",
            "language": "WDL",
            "author": "Jane Doe",
            "input_data": "Short-read sequencing data",
            "input_format": "FASTQ",
            "output_data": "Variant call data",
            "output_format": "VCF",
            "operation": "Variant calling",
            "subject_area": "Genomics",
            "sort_by": "stars",
            "sort_order": "asc",
            "limit": 25,
        },
    ),
    ("get_version", {"version_id": VERSION_ID, "file_limit": 10}),
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


@pytest.mark.parametrize(("name", "arguments"), UNIMPLEMENTED + IMPLEMENTED)
async def test_tools_accept_their_arguments(client: Client[Any], name: str, arguments: dict[str, Any]) -> None:
    """A schema mismatch would fail as a validation error instead of a missing body."""
    schema = await _schema(client, name)
    assert set(arguments) <= set(schema["properties"])


async def test_search_takes_every_facet(client: Client[Any]) -> None:
    schema = await _schema(client, "search_entries")
    assert set(schema["properties"]) == {
        "query",
        "type",
        "language",
        "author",
        "input_data",
        "input_format",
        "output_data",
        "output_format",
        "operation",
        "subject_area",
        "sort_by",
        "sort_order",
        "limit",
    }
    assert schema.get("required", []) == []


async def test_search_arguments_have_sane_defaults(client: Client[Any]) -> None:
    properties = (await _schema(client, "search_entries"))["properties"]
    assert properties["sort_by"]["default"] == "relevance"
    assert properties["sort_order"]["default"] is None
    assert properties["limit"]["default"] == 20
    assert properties["limit"]["maximum"] == 200


@pytest.mark.parametrize(
    ("name", "required"),
    [
        ("get_entry", ["entry_id"]),
        ("get_version", ["version_id"]),
        ("get_file", ["version_id", "path"]),
    ],
)
async def test_lookups_require_an_identifier(client: Client[Any], name: str, required: list[str]) -> None:
    schema = await _schema(client, name)
    assert schema["required"] == required


async def test_get_version_limits_by_default(client: Client[Any]) -> None:
    properties = (await _schema(client, "get_version"))["properties"]
    assert set(properties) == {"version_id", "file_limit"}
    assert properties["file_limit"]["default"] == 100


async def test_get_version_rejects_a_limit_below_one(client: Client[Any]) -> None:
    async with client:
        with pytest.raises(ToolError, match="file_limit"):
            await client.call_tool("get_version", {"version_id": VERSION_ID, "file_limit": 0})


async def test_get_file_limits_by_default(client: Client[Any]) -> None:
    properties = (await _schema(client, "get_file"))["properties"]
    assert set(properties) == {"version_id", "path", "content_limit"}
    assert properties["content_limit"]["default"] == 50_000


async def test_get_file_rejects_a_limit_below_one(client: Client[Any]) -> None:
    async with client:
        with pytest.raises(ToolError, match="content_limit"):
            await client.call_tool("get_file", {"version_id": VERSION_ID, "path": "Dockstore.cwl", "content_limit": 0})


async def test_get_entry_limits_by_default(client: Client[Any]) -> None:
    properties = (await _schema(client, "get_entry"))["properties"]
    assert set(properties) == {"entry_id", "description_limit", "version_limit"}
    assert properties["description_limit"]["default"] == 5000
    assert properties["version_limit"]["default"] == 20


@pytest.mark.parametrize("parameter", ["description_limit", "version_limit"])
async def test_get_entry_rejects_a_limit_below_one(client: Client[Any], parameter: str) -> None:
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("get_entry", {"entry_id": WORKFLOW_ID, parameter: 0})


async def _get_entry(client: Client[Any], **arguments: Any) -> Any:
    """Call get_entry and return the entry the client rebuilt from the response."""
    async with client:
        result = await client.call_tool("get_entry", arguments)
    return result.data


async def test_get_entry_summarizes_a_workflow(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id=WORKFLOW_ID)
    assert entry.id == WORKFLOW_ID
    assert entry.type == EntryType.WORKFLOW
    assert entry.language == DescriptorLanguage.GALAXY
    assert entry.name == "COVID-19-ARTIC-ILLUMINA"
    assert entry.organization == "iwc-workflows"
    assert entry.authors == ["IWC"]  # The author with no name is dropped.
    assert entry.default_version is not None
    assert (entry.default_version.id, entry.default_version.name) == (VERSION_ID, "v0.5.2")
    assert entry.updated_at == datetime(2026, 5, 13, 15, 33, 42, tzinfo=UTC)
    assert entry.url == (
        "https://staging.dockstore.org/workflows/"
        "github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA"
    )


async def test_get_entry_returns_every_field(client: Client[Any], dockstore: FakeDockstore) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": WORKFLOW_ID})
    assert result.structured_content is not None
    assert set(result.structured_content) == set(Entry.model_fields)
    entry = result.data
    assert entry.description is not None
    assert entry.description.startswith("# COVID-19")
    assert entry.doi == "10.5281/zenodo.15685746"
    assert entry.star_count == 2
    assert [(v.id, v.name, v.reference_type) for v in entry.versions] == [
        (f"{WORKFLOW_ID}:v0.5.1", "v0.5.1", ReferenceType.TAG),
        (VERSION_ID, "v0.5.2", ReferenceType.TAG),
    ]
    assert entry.operations == ["Variant calling"]
    assert dockstore.paths() == [
        "/api/workflows/path/workflow/"
        "github.com%2Fiwc-workflows%2Fsars-cov-2-variant-calling%2FCOVID-19-ARTIC-ILLUMINA/published",
        "/api/workflows/published/16247/workflowVersions",
        "/api/entries/16247/categories",
    ]
    assert dict(dockstore.requests[0].url.params) == {"subclass": "BIOWORKFLOW"}
    assert dict(dockstore.requests[1].url.params) == {"limit": "20"}


def _many_versions(count: int) -> list[dict[str, Any]]:
    """Versions of the workflow numbered 0 up, each updated a day after the last."""
    return [
        {
            "id": 200000 + number,
            "name": f"v{number}",
            "referenceType": "TAG",
            "last_modified": 1700000000000 + number * 86400000,
        }
        for number in range(count)
    ]


async def test_get_entry_limits_to_the_first_versions_in_dockstores_order(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    dockstore.workflow_versions = _many_versions(25)
    entry = await _get_entry(client, entry_id=WORKFLOW_ID)
    assert [version.name for version in entry.versions] == [f"v{number}" for number in range(20)]


async def test_get_entry_takes_a_smaller_version_limit(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow_versions = _many_versions(15)
    entry = await _get_entry(client, entry_id=WORKFLOW_ID, version_limit=3)
    assert [version.name for version in entry.versions] == ["v0", "v1", "v2"]
    pages = [dict(r.url.params) for r in dockstore.requests if r.url.path.endswith("/workflowVersions")]
    assert pages == [{"limit": "3"}]


async def test_get_entry_pages_up_to_a_version_limit_beyond_one_page(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    dockstore.workflow_versions = _many_versions(250)
    entry = await _get_entry(client, entry_id=WORKFLOW_ID, version_limit=150)
    assert [version.name for version in entry.versions] == [f"v{number}" for number in range(150)]
    pages = [dict(r.url.params) for r in dockstore.requests if r.url.path.endswith("/workflowVersions")]
    assert pages == [{"limit": "100", "offset": "0"}, {"limit": "50", "offset": "100"}]


async def test_get_entry_pages_through_every_version_without_a_limit(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    dockstore.workflow_versions = _many_versions(250)
    entry = await _get_entry(client, entry_id=WORKFLOW_ID, version_limit=None)
    assert [version.name for version in entry.versions] == [f"v{number}" for number in range(250)]
    pages = [dict(r.url.params) for r in dockstore.requests if r.url.path.endswith("/workflowVersions")]
    assert pages == [{"limit": "100", "offset": str(offset)} for offset in (0, 100, 200)]


async def test_get_entry_stops_paging_at_an_empty_page(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow_versions = _many_versions(200)
    entry = await _get_entry(client, entry_id=WORKFLOW_ID, version_limit=None)
    assert len(entry.versions) == 200
    assert dockstore.paths().count("/api/workflows/published/16247/workflowVersions") == 3


async def test_get_entry_fetches_a_tools_versions_with_the_tool(client: Client[Any], dockstore: FakeDockstore) -> None:
    """Tools have no paged endpoint for their versions, so they come with the tool."""
    entry = await _get_entry(client, entry_id=TOOL_ID)
    assert [version.name for version in entry.versions] == ["2.2.0"]
    assert dockstore.paths()[0] == "/api/containers/path/tool/quay.io%2Fpancancer%2Fpcawg-dkfz-workflow/published"
    assert dockstore.requests[0].url.params["include"] == "versions"


async def test_get_entry_limits_a_long_description(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow = WORKFLOW | {"description": "x" * 6000}
    entry = await _get_entry(client, entry_id=WORKFLOW_ID)
    assert len(entry.description) == 5000
    assert entry.description == "x" * 4999 + "…"


async def test_get_entry_leaves_a_short_description_alone(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow = WORKFLOW | {"description": "x" * 5000}
    entry = await _get_entry(client, entry_id=WORKFLOW_ID)
    assert entry.description == "x" * 5000


async def test_get_entry_takes_a_smaller_description_limit(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow = WORKFLOW | {"description": "x" * 6000}
    entry = await _get_entry(client, entry_id=WORKFLOW_ID, description_limit=100)
    assert entry.description == "x" * 99 + "…"


async def test_get_entry_returns_the_whole_description_without_a_limit(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    dockstore.workflow = WORKFLOW | {"description": "x" * 6000}
    entry = await _get_entry(client, entry_id=WORKFLOW_ID, description_limit=None)
    assert entry.description == "x" * 6000


async def test_get_entry_finds_a_tool_too(client: Client[Any]) -> None:
    """Tools are not served by the endpoint that answers for everything else."""
    entry = await _get_entry(client, entry_id=TOOL_ID)
    assert entry.id == TOOL_ID
    assert entry.type == EntryType.TOOL
    assert entry.name == "pcawg-dkfz-workflow"
    assert entry.registry == "quay.io"
    assert entry.url == "https://staging.dockstore.org/containers/quay.io/pancancer/pcawg-dkfz-workflow"


async def test_get_entry_reads_a_tools_differently_spelled_fields(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id=TOOL_ID)
    assert entry.organization == "pancancer"  # A tool calls this its namespace.
    assert entry.language == DescriptorLanguage.CWL  # A tool can have several.
    assert entry.source_control == "github.com"  # Only a workflow states this outright.
    assert entry.star_count == 0


async def test_get_entry_summarizes_each_version(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": TOOL_ID})
    assert result.structured_content is not None
    assert result.structured_content["versions"] == [
        {
            "id": f"{TOOL_ID}:2.2.0",
            "name": "2.2.0",
            "reference_type": "branch",
            "updated_at": "2022-03-31T21:37:31Z",
        }
    ]


async def test_get_entry_prefers_a_versions_last_modified_date(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id=WORKFLOW_ID)
    assert entry.versions is not None
    assert entry.versions[1].updated_at == datetime(2026, 5, 13, 15, 33, 42, tzinfo=UTC)


async def test_get_entry_finds_the_default_version_among_the_versions(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": TOOL_ID})
    assert result.structured_content is not None
    assert result.structured_content["default_version"] == {
        "id": f"{TOOL_ID}:2.2.0",
        "name": "2.2.0",
        "reference_type": "branch",
        "updated_at": "2022-03-31T21:37:31Z",
    }


async def test_get_entry_sorts_categories_into_their_fields(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id=WORKFLOW_ID)
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


@pytest.mark.parametrize(
    "entry_id", ["16247", "COVID-19-ARTIC-ILLUMINA", "#workflow/", "#gadget/github.com/org/repo", "quay.io/org repo"]
)
async def test_get_entry_rejects_something_that_is_not_an_identifier(
    client: Client[Any], dockstore: FakeDockstore, entry_id: str
) -> None:
    async with client:
        with pytest.raises(ToolError, match="not the TRS identifier of a Dockstore entry"):
            await client.call_tool("get_entry", {"entry_id": entry_id})
    assert dockstore.requests == []


async def test_get_entry_ignores_surrounding_whitespace(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id=f"  {WORKFLOW_ID} ")
    assert entry.id == WORKFLOW_ID


@pytest.mark.parametrize(("prefix", "subclass"), [("#notebook/", "NOTEBOOK"), ("#service/", "SERVICE")])
async def test_get_entry_asks_for_the_kind_of_entry_its_prefix_names(
    client: Client[Any], dockstore: FakeDockstore, prefix: str, subclass: str
) -> None:
    async with client:
        with pytest.raises(ToolError, match="no published entry"):
            await client.call_tool("get_entry", {"entry_id": f"{prefix}github.com/org/repo"})
    assert dockstore.paths() == ["/api/workflows/path/workflow/github.com%2Forg%2Frepo/published"]
    assert dict(dockstore.requests[0].url.params) == {"subclass": subclass}


async def test_get_entry_reports_an_entry_that_is_not_there(client: Client[Any], dockstore: FakeDockstore) -> None:
    async with client:
        with pytest.raises(ToolError, match=r"no published entry with TRS identifier 'github\.com/org/repo'"):
            await client.call_tool("get_entry", {"entry_id": "github.com/org/repo"})
    # With no prefix, it could have been a tool or an apptool, so both were looked for.
    assert dockstore.paths() == [
        "/api/containers/path/tool/github.com%2Forg%2Frepo/published",
        "/api/workflows/path/workflow/github.com%2Forg%2Frepo/published",
    ]
    assert dict(dockstore.requests[1].url.params) == {"subclass": "APPTOOL"}


@pytest.mark.parametrize(("name", "arguments"), [("get_version", {}), ("get_file", {"path": "Dockstore.cwl"})])
@pytest.mark.parametrize("version_id", [WORKFLOW_ID, f"{WORKFLOW_ID}:", ":v0.5.2", "16247:v0.5.2"])
async def test_version_lookups_reject_something_that_is_not_a_version_identifier(
    client: Client[Any], name: str, arguments: dict[str, Any], version_id: str
) -> None:
    async with client:
        with pytest.raises(ToolError, match="not the TRS identifier"):
            await client.call_tool(name, {"version_id": version_id, **arguments})


async def _get_version(client: Client[Any], **arguments: Any) -> Any:
    """Call get_version and return the version the client rebuilt from the response."""
    async with client:
        result = await client.call_tool("get_version", arguments)
    return result.data


#: Where TRS serves the canned workflow's default version.
TRS_VERSION_PATH = (
    "/api/ga4gh/trs/v2/tools/%23workflow%2Fgithub.com%2Fiwc-workflows%2Fsars-cov-2-variant-calling"
    "%2FCOVID-19-ARTIC-ILLUMINA/versions/v0.5.2"
)


async def test_get_version_returns_every_field(client: Client[Any], dockstore: FakeDockstore) -> None:
    async with client:
        result = await client.call_tool("get_version", {"version_id": VERSION_ID})
    assert result.structured_content is not None
    assert set(result.structured_content) == set(Version.model_fields)
    version = result.data
    assert version.id == VERSION_ID
    assert version.entry_id == WORKFLOW_ID
    assert version.name == "v0.5.2"
    assert version.reference == "v0.5.2"
    assert version.language == DescriptorLanguage.GALAXY
    assert version.descriptor_path == "pe-artic-variation.ga"
    assert (version.is_valid, version.is_verified, version.is_frozen) == (True, True, True)
    assert version.doi == "10.5281/zenodo.99999999"  # The owner's DOI wins over Dockstore's.
    assert version.updated_at == datetime(2026, 5, 13, 15, 33, 42, tzinfo=UTC)
    assert version.url == (
        "https://staging.dockstore.org/workflows/"
        "github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA:v0.5.2"
    )
    # The version and its files are fetched side by side once the version is found.
    assert dockstore.paths()[0] == "/api/entries/mapTrsVersionId"
    assert sorted(dockstore.paths()[1:]) == [
        TRS_VERSION_PATH,
        f"{TRS_VERSION_PATH}/GALAXY/files",
        "/api/workflows/published/16247/workflowVersions/117123",
    ]
    assert dict(dockstore.requests[0].url.params) == {"trsVersionId": VERSION_ID}


async def test_get_version_puts_the_descriptor_first(client: Client[Any]) -> None:
    version = await _get_version(client, version_id=VERSION_ID)
    assert version.file_paths == ["pe-artic-variation.ga", ".dockstore.yml", "pe-artic-variation-tests.yml"]


async def test_get_version_never_cuts_the_descriptor(client: Client[Any]) -> None:
    version = await _get_version(client, version_id=VERSION_ID, file_limit=1)
    assert version.file_paths == ["pe-artic-variation.ga"]


async def test_get_version_takes_a_file_limit(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow_files = {
        "GALAXY": WORKFLOW_FILES + [{"path": f"data/{number:03}.txt", "file_type": "OTHER"} for number in range(150)]
    }
    assert len((await _get_version(client, version_id=VERSION_ID)).file_paths) == 100
    assert len((await _get_version(client, version_id=VERSION_ID, file_limit=2)).file_paths) == 2
    assert len((await _get_version(client, version_id=VERSION_ID, file_limit=None)).file_paths) == 153


async def test_get_version_reports_a_missing_descriptor(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow_files = {"GALAXY": WORKFLOW_FILES[:2]}
    version = await _get_version(client, version_id=VERSION_ID)
    assert version.descriptor_path is None
    assert version.language is None
    assert version.file_paths == [".dockstore.yml", "pe-artic-variation-tests.yml"]


async def test_get_version_lists_no_files_without_a_descriptor_type(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    dockstore.workflow_files = {}
    version = await _get_version(client, version_id=VERSION_ID)
    assert (version.descriptor_path, version.language, version.file_paths) == (None, None, [])
    assert not any(path.endswith("/files") for path in dockstore.paths())


async def test_get_version_finds_a_tools_version(client: Client[Any], dockstore: FakeDockstore) -> None:
    version = await _get_version(client, version_id=f"{TOOL_ID}:2.2.0")
    assert version.id == f"{TOOL_ID}:2.2.0"
    assert version.entry_id == TOOL_ID
    assert version.doi is None
    assert version.updated_at == datetime(2022, 3, 31, 21, 37, 31, tzinfo=UTC)
    assert version.url == "https://staging.dockstore.org/containers/quay.io/pancancer/pcawg-dkfz-workflow:2.2.0"
    assert "/api/containers/published/188/tags/5011" in dockstore.paths()


async def test_get_version_merges_a_tools_files_across_languages(client: Client[Any], dockstore: FakeDockstore) -> None:
    """TRS lists a tool's files once per language, so a shared Dockerfile appears in both listings."""
    version = await _get_version(client, version_id=f"{TOOL_ID}:2.2.0")
    # The first language's descriptor is the primary one.
    assert version.descriptor_path == "Dockstore.cwl"
    assert version.language == DescriptorLanguage.CWL
    assert version.file_paths == ["Dockstore.cwl", "Dockerfile", "Dockstore.wdl"]
    files = sorted(path.rpartition("/versions/2.2.0")[2] for path in dockstore.paths() if "/trs/" in path)
    assert files == ["", "/CWL/files", "/WDL/files"]


async def test_get_version_reports_a_version_that_is_not_there(client: Client[Any], dockstore: FakeDockstore) -> None:
    async with client:
        with pytest.raises(ToolError, match=r"no published version with TRS identifier '.*:v9'.*get_entry"):
            await client.call_tool("get_version", {"version_id": f"{WORKFLOW_ID}:v9"})
    assert dockstore.paths() == ["/api/entries/mapTrsVersionId"]


async def test_get_version_ignores_surrounding_whitespace(client: Client[Any]) -> None:
    version = await _get_version(client, version_id=f"  {VERSION_ID} ")
    assert version.id == VERSION_ID


async def _search(client: Client[Any], dockstore: FakeDockstore, **arguments: Any) -> tuple[Any, dict[str, Any]]:
    """Call search_entries and return its structured result and the query Dockstore was sent."""
    async with client:
        result = await client.call_tool("search_entries", arguments)
    assert result.structured_content is not None
    [body] = dockstore.search_bodies()
    return result.structured_content, body


def _keywords(body: dict[str, Any]) -> dict[str, Any]:
    """Return the keyword clause of a search query, unwrapped from any relevance weighting."""
    [keywords] = body["query"]["bool"]["must"]
    unwrapped: dict[str, Any] = keywords.get("script_score", {}).get("query", keywords)
    return unwrapped


async def test_search_summarizes_each_hit(client: Client[Any], dockstore: FakeDockstore) -> None:
    results, _ = await _search(client, dockstore, query="covid")
    assert results["total_count"] == 42
    # The hit with no path cannot be summarized, so it is left out.
    assert results["returned_count"] == 2
    workflow, tool = results["entries"]
    assert workflow == {
        "id": "#workflow/github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA",
        "type": "workflow",
        "language": "galaxy",
        "name": "COVID-19-ARTIC-ILLUMINA",
        "topic": "Variant calling from SARS-CoV-2 paired-end Illumina ARTIC data.",
        "categories": ["COVID-19"],
        "subject_areas": ["Virology"],
        # A category filed twice is reported once.
        "operations": ["Variant calling"],
        "input_formats": ["FASTQ-sanger"],
        "output_formats": ["VCF"],
        "input_data": ["Short-read sequencing data"],
        "output_data": ["Variant call data"],
        "updated_at": "2026-05-13T15:33:42Z",
    }
    # The tool was indexed without its TRS identifier, so it has one made from its path.
    assert (tool["id"], tool["type"], tool["language"]) == ("quay.io/pancancer/pcawg-dkfz-workflow", "tool", "CWL")
    assert tool["name"] == "pcawg-dkfz-workflow"
    assert tool["updated_at"] == "2022-03-31T21:37:31.404000Z"
    # An entry filed under no categories has an empty list for each facet.
    assert tool["categories"] == tool["operations"] == tool["output_data"] == []


async def test_search_ids_lead_to_get_entry(client: Client[Any], dockstore: FakeDockstore) -> None:
    results, _ = await _search(client, dockstore, query="covid")
    entry = await _get_entry(client, entry_id=results["entries"][0]["id"])
    assert entry.name == "COVID-19-ARTIC-ILLUMINA"


async def test_search_posts_to_the_search_endpoint(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore)
    assert dockstore.paths() == ["/api/api/ga4gh/v2/extended/tools/entry/_search"]
    assert body["size"] == 20
    assert body["track_total_hits"] is True


async def test_search_with_no_arguments_matches_everything(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore)
    assert body["query"] == {"bool": {"filter": []}}
    assert body["sort"] == [{"relevance": {"order": "desc", "unmapped_type": "double"}}]


async def test_search_filters_galaxy_by_the_name_dockstore_indexes(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    _, body = await _search(client, dockstore, language="galaxy")
    assert body["query"]["bool"]["filter"] == [{"term": {"descriptorType": "gxformat2"}}]


async def test_search_turns_each_facet_into_a_filter(client: Client[Any], dockstore: FakeDockstore) -> None:
    arguments = {name: value for name, value in IMPLEMENTED[1][1].items() if name != "query"}
    _, body = await _search(client, dockstore, **arguments)
    assert "must" not in body["query"]["bool"]
    assert body["query"]["bool"]["filter"] == [
        {"term": {"entryTypeMetadata.type.keyword": "WORKFLOW"}},
        {"term": {"descriptorType": "WDL"}},
        *(
            {"query_string": {"query": value, "fields": fields, "default_operator": "AND"}}
            for fields, value in [
                (["all_authors.name"], "Jane Doe"),
                (["input-data.displayName", "input-data.topic"], "Short-read sequencing data"),
                (["input-format.displayName", "input-format.topic"], "FASTQ"),
                (["output-data.displayName", "output-data.topic"], "Variant call data"),
                (["output-format.displayName", "output-format.topic"], "VCF"),
                (["operation.displayName", "operation.topic"], "Variant calling"),
                (["topic.displayName", "topic.topic"], "Genomics"),
            ]
        ),
    ]


async def test_search_passes_facet_syntax_through(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore, input_format='"BAM" OR CRA?', author="O'Connor~")
    assert [clause["query_string"]["query"] for clause in body["query"]["bool"]["filter"]] == [
        "O'Connor~",
        '"BAM" OR CRA?',
    ]


async def test_search_ignores_blank_arguments(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore, query="  ", operation="", subject_area=" ")
    assert body["query"] == {"bool": {"filter": []}}


async def test_search_filters_apptools_by_their_own_type(client: Client[Any], dockstore: FakeDockstore) -> None:
    """Apptools share an index with tools, so the index alone cannot tell them apart."""
    _, body = await _search(client, dockstore, type="apptool")
    assert body["query"]["bool"]["filter"] == [{"term": {"entryTypeMetadata.type.keyword": "APPTOOL"}}]


async def test_search_ranks_keywords_by_where_they_match(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore, query=" gatk  OR haplotype-caller ")
    keywords = _keywords(body)
    query_string, *paths = keywords["bool"]["should"]
    assert keywords["bool"]["minimum_should_match"] == 1
    assert query_string["query_string"]["query"] == "gatk  OR haplotype-caller"
    assert query_string["query_string"]["default_operator"] == "AND"
    assert "topicAutomatic^4" in query_string["query_string"]["fields"]
    assert "operation.displayName^3" in query_string["query_string"]["fields"]
    # Each keyword can match any part of a path.
    assert [(field, clause["value"]) for path in paths for field, clause in path["wildcard"].items()] == [
        ("full_workflow_path", "*gatk*"),
        ("tool_path", "*gatk*"),
        ("full_workflow_path", "*haplotype-caller*"),
        ("tool_path", "*haplotype-caller*"),
    ]
    assert body["sort"] == [{"archived": {"order": "asc", "unmapped_type": "boolean"}}, {"_score": {"order": "desc"}}]


async def test_search_weighs_keyword_matches_by_relevance(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore, query="covid")
    [scored] = body["query"]["bool"]["must"]
    script = scored["script_score"]["script"]
    assert "_score * _score * Math.log(1.05 + relevance)" in script["source"]
    assert script["params"] == {"missing": 1e-9}


async def test_search_by_a_field_does_not_weigh_keyword_matches(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore, query="covid", sort_by="stars")
    [keywords] = body["query"]["bool"]["must"]
    assert "script_score" not in keywords


async def test_search_looks_for_only_plain_keywords_in_paths(client: Client[Any], dockstore: FakeDockstore) -> None:
    query = "gatk OR haplo* OR author:jane OR somatic~ OR haplotype\\-caller"
    _, body = await _search(client, dockstore, query=query)
    keywords = _keywords(body)
    query_string, *paths = keywords["bool"]["should"]
    assert query_string["query_string"]["query"] == query
    assert [clause["value"] for path in paths for clause in path["wildcard"].values()] == ["*gatk*", "*gatk*"]


@pytest.mark.parametrize(
    "query",
    [
        "rna NOT quantification",
        "rna -quantification",
        "rna !quantification",
        "+rna +quantification",
        "rna && quantification",
        "(rna OR dna) AND quantification",
        "rna AND (-quantification)",
        '"rna" AND quantification',
        'gatk "variant calling"',
        "rna quantification*",
        "rna OR dna quantification",
        "rna AND dna quantification",
        "(rna OR dna)",
    ],
)
async def test_search_skips_paths_when_matches_are_required(
    client: Client[Any], dockstore: FakeDockstore, query: str
) -> None:
    """A keyword found in a path would match an entry that the query requires or rules out otherwise."""
    _, body = await _search(client, dockstore, query=query)
    keywords = _keywords(body)
    assert keywords["bool"]["should"] == [{"query_string": {"query": query, "fields": ANY, "default_operator": "AND"}}]


@pytest.mark.parametrize("query", ["rna AND quantification", " rna  quantification "])
async def test_search_needs_every_keyword(client: Client[Any], dockstore: FakeDockstore, query: str) -> None:
    """A keyword found in the path alone must not satisfy the others it is joined to."""
    _, body = await _search(client, dockstore, query=query)
    clauses = _keywords(body)["bool"]["must"]
    assert len(clauses) == 2
    for clause, term in zip(clauses, ["rna", "quantification"], strict=True):
        query_string, *paths = clause["bool"]["should"]
        assert clause["bool"]["minimum_should_match"] == 1
        assert query_string["query_string"]["query"] == term
        assert "topicAutomatic^4" in query_string["query_string"]["fields"]
        assert [(field, wildcard["value"]) for path in paths for field, wildcard in path["wildcard"].items()] == [
            ("full_workflow_path", f"*{term}*"),
            ("tool_path", f"*{term}*"),
        ]


async def test_search_takes_slashes_literally(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore, query=r"github.com/iwc\/x \\/y", input_format="a/b")
    keywords = _keywords(body)
    assert keywords["bool"]["should"][0]["query_string"]["query"] == r"github.com\/iwc\/x \\\/y"
    assert body["query"]["bool"]["filter"][0]["query_string"]["query"] == r"a\/b"


async def test_search_reports_syntax_dockstore_rejects(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.search_status = 400
    dockstore.search_response = {"error": "parse_exception"}
    async with client:
        with pytest.raises(ToolError, match="Lucene syntax"):
            await client.call_tool("search_entries", {"query": "(unbalanced"})


async def test_search_refuses_services(client: Client[Any], dockstore: FakeDockstore) -> None:
    async with client:
        with pytest.raises(ToolError, match="does not index services"):
            await client.call_tool("search_entries", {"type": "service"})
    assert dockstore.requests == []


async def test_search_reports_a_dockstore_without_search(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.search_response = {key: value for key, value in SEARCH_HITS.items() if key != "hits"}
    async with client:
        with pytest.raises(ToolError, match="search may be unavailable"):
            await client.call_tool("search_entries", {"query": "covid"})


@pytest.mark.parametrize(
    ("arguments", "first"),
    [
        ({"sort_by": "name"}, {"normalizedName": {"order": "asc", "missing": "_last", "unmapped_type": "keyword"}}),
        ({"sort_by": "stars"}, {"stars_count": {"order": "desc", "missing": "_last", "unmapped_type": "long"}}),
        (
            {"sort_by": "updated", "sort_order": "asc"},
            {"last_modified_date": {"order": "asc", "missing": "_last", "unmapped_type": "date"}},
        ),
    ],
)
async def test_search_sorts_by_a_field(
    client: Client[Any], dockstore: FakeDockstore, arguments: dict[str, Any], first: dict[str, Any]
) -> None:
    """Each sort runs its natural way unless told otherwise, with ties going to the better match."""
    _, body = await _search(client, dockstore, query="covid", **arguments)
    assert body["sort"] == [first, {"_score": {"order": "desc"}}]


async def test_search_breaks_ties_by_relevance_without_keywords(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore, sort_by="stars", sort_order="asc")
    assert body["sort"][1] == {"relevance": {"order": "desc", "unmapped_type": "double"}}


@pytest.mark.parametrize("query", [None, "covid"])
async def test_search_can_put_the_worst_match_first(
    client: Client[Any], dockstore: FakeDockstore, query: str | None
) -> None:
    _, body = await _search(client, dockstore, query=query, sort_order="asc")
    [*_, relevance] = body["sort"]
    assert next(iter(relevance.values()))["order"] == "asc"


async def test_search_returns_as_many_as_asked_for(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore, limit=200)
    assert body["size"] == 200


@pytest.mark.parametrize("limit", [0, 201])
async def test_search_refuses_an_unreasonable_limit(client: Client[Any], dockstore: FakeDockstore, limit: int) -> None:
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("search_entries", {"limit": limit})
    assert dockstore.requests == []
