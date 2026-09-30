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
rather than returning something made up.  ``get_entry`` and ``search_entries`` are
implemented, and are exercised against the canned Dockstore in :mod:`tests.fake_dockstore`.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from unittest.mock import ANY

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from dockstore_mcp.models import (
    DescriptorLanguage,
    Entry,
    EntryType,
    File,
    FileField,
    ReferenceType,
    Version,
    VersionField,
)
from fake_dockstore import CATEGORIES, SEARCH_HITS, WORKFLOW, FakeDockstore

#: Every tool that is scaffolded but not implemented, with valid arguments.
UNIMPLEMENTED: list[tuple[str, dict[str, Any]]] = [
    ("get_version", {"version_id": "a-version"}),
    ("get_file", {"version_id": "a-version", "path": "Dockstore.cwl"}),
]

#: Arguments that reach the canned Dockstore, for the tools that are implemented.
IMPLEMENTED: list[tuple[str, dict[str, Any]]] = [
    ("get_entry", {"entry_id": "16247"}),
    (
        "search_entries",
        {
            "query": "rna-seq",
            "entry_type": "workflow",
            "descriptor_type": "WDL",
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
        "entry_type",
        "descriptor_type",
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
    ("name", "required", "trimmer"),
    [
        ("get_entry", ["entry_id"], "version_limit"),
        ("get_version", ["version_id"], "fields"),
        ("get_file", ["version_id", "path"], "fields"),
    ],
)
async def test_lookups_require_an_identifier(client: Client[Any], name: str, required: list[str], trimmer: str) -> None:
    schema = await _schema(client, name)
    assert schema["required"] == required
    assert trimmer in schema["properties"]


async def test_get_entry_limits_by_default(client: Client[Any]) -> None:
    properties = (await _schema(client, "get_entry"))["properties"]
    assert set(properties) == {"entry_id", "description_limit", "version_limit"}
    assert properties["description_limit"]["default"] == 5000
    assert properties["version_limit"]["default"] == 10


@pytest.mark.parametrize("parameter", ["description_limit", "version_limit"])
async def test_get_entry_rejects_a_limit_below_one(client: Client[Any], parameter: str) -> None:
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("get_entry", {"entry_id": "16247", parameter: 0})


@pytest.mark.parametrize(("model", "field_enum"), [(Version, VersionField), (File, FileField)])
async def test_selectable_fields_match_their_model(model: type[BaseModel], field_enum: type[StrEnum]) -> None:
    """Field enums name the attributes they select, so callers cannot ask for a field that does not exist."""
    assert {member.value for member in field_enum} == set(model.model_fields)
    assert all(info.default is None for info in model.model_fields.values())


async def _get_entry(client: Client[Any], **arguments: Any) -> Any:
    """Call get_entry and return the entry the client rebuilt from the response."""
    async with client:
        result = await client.call_tool("get_entry", arguments)
    return result.data


async def test_get_entry_summarizes_a_workflow(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id="16247")
    assert entry.id == "16247"
    assert entry.entry_type == EntryType.WORKFLOW
    assert entry.descriptor_type == DescriptorLanguage.GALAXY
    assert entry.name == "COVID-19-ARTIC-ILLUMINA"
    assert entry.organization == "iwc-workflows"
    assert entry.authors == ["IWC"]  # The author with no name is dropped.
    assert entry.default_version is not None
    assert (entry.default_version.id, entry.default_version.name) == ("117123", "v0.5.2")
    assert entry.updated_at == datetime(2026, 5, 13, 15, 33, 42, tzinfo=UTC)
    assert entry.url == (
        "https://staging.dockstore.org/workflows/"
        "github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA"
    )


async def test_get_entry_returns_every_field(client: Client[Any], dockstore: FakeDockstore) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": "16247"})
    assert result.structured_content is not None
    assert set(result.structured_content) == set(Entry.model_fields)
    entry = result.data
    assert entry.description is not None
    assert entry.description.startswith("# COVID-19")
    assert entry.doi == "10.5281/zenodo.15685746"
    assert entry.star_count == 2
    assert [(v.id, v.name, v.reference_type) for v in entry.versions] == [
        ("117122", "v0.5.1", ReferenceType.TAG),
        ("117123", "v0.5.2", ReferenceType.TAG),
    ]
    assert entry.operations == ["Variant calling"]
    assert dockstore.paths() == [
        "/api/workflows/published/16247",
        "/api/workflows/published/16247/workflowVersions",
        "/api/entries/16247/categories",
    ]
    assert "include" not in dockstore.requests[0].url.params
    assert dict(dockstore.requests[1].url.params) == {"limit": "10"}


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
    dockstore.workflow_versions = _many_versions(15)
    entry = await _get_entry(client, entry_id="16247")
    assert [version.name for version in entry.versions] == [f"v{number}" for number in range(10)]


async def test_get_entry_takes_a_smaller_version_limit(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow_versions = _many_versions(15)
    entry = await _get_entry(client, entry_id="16247", version_limit=3)
    assert [version.name for version in entry.versions] == ["v0", "v1", "v2"]
    pages = [dict(r.url.params) for r in dockstore.requests if r.url.path.endswith("/workflowVersions")]
    assert pages == [{"limit": "3"}]


async def test_get_entry_pages_up_to_a_version_limit_beyond_one_page(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    dockstore.workflow_versions = _many_versions(250)
    entry = await _get_entry(client, entry_id="16247", version_limit=150)
    assert [version.name for version in entry.versions] == [f"v{number}" for number in range(150)]
    pages = [dict(r.url.params) for r in dockstore.requests if r.url.path.endswith("/workflowVersions")]
    assert pages == [{"limit": "100", "offset": "0"}, {"limit": "50", "offset": "100"}]


async def test_get_entry_pages_through_every_version_without_a_limit(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    dockstore.workflow_versions = _many_versions(250)
    entry = await _get_entry(client, entry_id="16247", version_limit=None)
    assert [version.name for version in entry.versions] == [f"v{number}" for number in range(250)]
    pages = [dict(r.url.params) for r in dockstore.requests if r.url.path.endswith("/workflowVersions")]
    assert pages == [{"limit": "100", "offset": str(offset)} for offset in (0, 100, 200)]


async def test_get_entry_stops_paging_at_an_empty_page(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow_versions = _many_versions(200)
    entry = await _get_entry(client, entry_id="16247", version_limit=None)
    assert len(entry.versions) == 200
    assert dockstore.paths().count("/api/workflows/published/16247/workflowVersions") == 3


async def test_get_entry_fetches_a_tools_versions_with_the_tool(client: Client[Any], dockstore: FakeDockstore) -> None:
    """Tools have no paged endpoint for their versions, so they come with the tool."""
    entry = await _get_entry(client, entry_id="188")
    assert [version.name for version in entry.versions] == ["2.2.0"]
    assert dockstore.paths()[1] == "/api/containers/published/188"
    assert dockstore.requests[1].url.params["include"] == "versions"


async def test_get_entry_limits_a_long_description(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow = WORKFLOW | {"description": "x" * 6000}
    entry = await _get_entry(client, entry_id="16247")
    assert len(entry.description) == 5000
    assert entry.description == "x" * 4999 + "…"


async def test_get_entry_leaves_a_short_description_alone(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow = WORKFLOW | {"description": "x" * 5000}
    entry = await _get_entry(client, entry_id="16247")
    assert entry.description == "x" * 5000


async def test_get_entry_takes_a_smaller_description_limit(client: Client[Any], dockstore: FakeDockstore) -> None:
    dockstore.workflow = WORKFLOW | {"description": "x" * 6000}
    entry = await _get_entry(client, entry_id="16247", description_limit=100)
    assert entry.description == "x" * 99 + "…"


async def test_get_entry_returns_the_whole_description_without_a_limit(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    dockstore.workflow = WORKFLOW | {"description": "x" * 6000}
    entry = await _get_entry(client, entry_id="16247", description_limit=None)
    assert entry.description == "x" * 6000


async def test_get_entry_finds_a_tool_too(client: Client[Any]) -> None:
    """Tools are not served by the endpoint that answers for everything else."""
    entry = await _get_entry(client, entry_id="188")
    assert entry.entry_type == EntryType.TOOL
    assert entry.name == "pcawg-dkfz-workflow"
    assert entry.registry == "quay.io"
    assert entry.url == "https://staging.dockstore.org/containers/quay.io/pancancer/pcawg-dkfz-workflow"


async def test_get_entry_reads_a_tools_differently_spelled_fields(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id="188")
    assert entry.organization == "pancancer"  # A tool calls this its namespace.
    assert entry.descriptor_type == DescriptorLanguage.CWL  # A tool can have several.
    assert entry.source_control == "github.com"  # Only a workflow states this outright.
    assert entry.star_count == 0


async def test_get_entry_summarizes_each_version(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": "188"})
    assert result.structured_content is not None
    assert result.structured_content["versions"] == [
        {
            "id": "5011",
            "name": "2.2.0",
            "reference_type": "branch",
            "updated_at": "2022-03-31T21:37:31Z",
        }
    ]


async def test_get_entry_prefers_a_versions_last_modified_date(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id="16247")
    assert entry.versions is not None
    assert entry.versions[1].updated_at == datetime(2026, 5, 13, 15, 33, 42, tzinfo=UTC)


async def test_get_entry_finds_the_default_version_among_the_versions(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": "188"})
    assert result.structured_content is not None
    assert result.structured_content["default_version"] == {
        "id": "5011",
        "name": "2.2.0",
        "reference_type": "branch",
        "updated_at": "2022-03-31T21:37:31Z",
    }


async def test_get_entry_sorts_categories_into_their_fields(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id="16247")
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
        "id": "16247",
        "entry_type": "workflow",
        "descriptor_type": "gxformat2",
        "name": "COVID-19-ARTIC-ILLUMINA",
        "trs_id": "#workflow/github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA",
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
    assert (tool["id"], tool["entry_type"], tool["descriptor_type"]) == ("188", "tool", "CWL")
    assert (tool["name"], tool["trs_id"]) == ("pcawg-dkfz-workflow", "quay.io/pancancer/pcawg-dkfz-workflow")
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
    _, body = await _search(client, dockstore, entry_type="apptool")
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
            await client.call_tool("search_entries", {"entry_type": "service"})
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
