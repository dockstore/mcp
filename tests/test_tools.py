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
    EntryField,
    EntryType,
    File,
    FileField,
    ReferenceType,
    Version,
    VersionField,
)
from dockstore_mcp.tools.entries import DEFAULT_ENTRY_FIELDS
from fake_dockstore import CATEGORIES, SEARCH_HITS, FakeDockstore

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
    assert entry.default_version is not None
    assert (entry.default_version.id, entry.default_version.name) == ("117123", "v0.5.2")
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
    assert entry.versions is None


async def test_get_entry_leaves_the_unrequested_fields_out_of_the_response(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": "16247", "fields": ["name", "doi", "registry"]})
    # A field that was asked for is sent even when it is empty; the rest are not sent at all.
    assert result.structured_content == {
        "name": "COVID-19-ARTIC-ILLUMINA",
        "doi": "10.5281/zenodo.15685746",
        "registry": None,
    }


async def test_get_entry_returns_every_field_for_a_star(client: Client[Any], dockstore: FakeDockstore) -> None:
    entry = await _get_entry(client, entry_id="16247", fields=["*"])
    assert entry.description is not None
    assert [(v.id, v.name, v.reference_type) for v in entry.versions] == [
        ("117122", "v0.5.1", ReferenceType.TAG),
        ("117123", "v0.5.2", ReferenceType.TAG),
    ]
    assert entry.operations == ["Variant calling"]
    # Every field was asked for, so both of the follow-up requests were made.
    assert dockstore.paths() == ["/api/workflows/published/16247", "/api/entries/16247/categories"]
    assert dockstore.requests[0].url.params["include"] == "versions"


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


async def test_get_entry_summarizes_each_version(client: Client[Any]) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": "188", "fields": ["versions"]})
    assert result.structured_content == {
        "versions": [
            {
                "id": "5011",
                "name": "2.2.0",
                "reference_type": "branch",
                "updated_at": "2022-03-31T21:37:31Z",
            }
        ]
    }


async def test_get_entry_prefers_a_versions_last_modified_date(client: Client[Any]) -> None:
    entry = await _get_entry(client, entry_id="16247", fields=["versions"])
    assert entry.versions is not None
    assert entry.versions[1].updated_at == datetime(2026, 5, 13, 15, 33, 42, tzinfo=UTC)


async def test_get_entry_finds_the_default_version_among_the_versions(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    async with client:
        result = await client.call_tool("get_entry", {"entry_id": "188", "fields": ["default_version"]})
    assert result.structured_content == {
        "default_version": {
            "id": "5011",
            "name": "2.2.0",
            "reference_type": "branch",
            "updated_at": "2022-03-31T21:37:31Z",
        }
    }
    assert dockstore.requests[0].url.params["include"] == "versions"


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
    await _get_entry(client, entry_id="16247", fields=["versions", "operations"])
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
        "path": "github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA",
        "topic": "Variant calling from SARS-CoV-2 paired-end Illumina ARTIC data.",
        "created_at": "2021-02-23T08:14:27.928000Z",
        "updated_at": "2026-05-13T15:33:42Z",
    }
    assert (tool["id"], tool["entry_type"], tool["descriptor_type"]) == ("188", "tool", "CWL")
    assert (tool["name"], tool["path"]) == ("pcawg-dkfz-workflow", "quay.io/pancancer/pcawg-dkfz-workflow")
    assert tool["updated_at"] == "2022-03-31T21:37:31.404000Z"


async def test_search_ids_lead_to_get_entry(client: Client[Any], dockstore: FakeDockstore) -> None:
    results, _ = await _search(client, dockstore, query="covid")
    entry = await _get_entry(client, entry_id=results["entries"][0]["id"], fields=["name"])
    assert entry.name == "COVID-19-ARTIC-ILLUMINA"


async def test_search_posts_to_the_search_endpoint(client: Client[Any], dockstore: FakeDockstore) -> None:
    _, body = await _search(client, dockstore)
    assert dockstore.paths() == ["/api/api/ga4gh/v2/extended/tools/entry/_search"]
    assert body["size"] == 10
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
            {"query_string": {"query": value, "default_field": field, "default_operator": "AND"}}
            for field, value in [
                ("all_authors.name", "Jane Doe"),
                ("input-data.displayName", "Short-read sequencing data"),
                ("input-format.displayName", "FASTQ"),
                ("output-data.displayName", "Variant call data"),
                ("output-format.displayName", "VCF"),
                ("operation.displayName", "Variant calling"),
                ("topic.displayName", "Genomics"),
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
    _, body = await _search(client, dockstore, query=" gatk  haplotype-caller ")
    keywords = _keywords(body)
    query_string, *paths = keywords["bool"]["should"]
    assert keywords["bool"]["minimum_should_match"] == 1
    assert query_string["query_string"]["query"] == "gatk  haplotype-caller"
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
    query = 'gatk "variant calling" (bwa OR bowtie2) haplo* author:jane somatic~ haplotype\\-caller'
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
    ],
)
async def test_search_skips_paths_when_matches_are_required(
    client: Client[Any], dockstore: FakeDockstore, query: str
) -> None:
    """A keyword found in a path would match an entry that the query requires or rules out otherwise."""
    _, body = await _search(client, dockstore, query=query)
    keywords = _keywords(body)
    assert keywords["bool"]["should"] == [{"query_string": {"query": query, "fields": ANY}}]


async def test_search_needs_every_keyword_joined_by_and(client: Client[Any], dockstore: FakeDockstore) -> None:
    """A keyword found in the path alone must not satisfy the others it is joined to."""
    _, body = await _search(client, dockstore, query="rna AND quantification")
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
    _, body = await _search(client, dockstore, limit=100)
    assert body["size"] == 100


@pytest.mark.parametrize("limit", [0, 101])
async def test_search_refuses_an_unreasonable_limit(client: Client[Any], dockstore: FakeDockstore, limit: int) -> None:
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool("search_entries", {"limit": limit})
    assert dockstore.requests == []
