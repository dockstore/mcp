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
"""Entry search, the equivalent of Dockstore's Search page.

The search runs against the Elasticsearch index behind that page, through the
TRS extension that passes a query through to it verbatim.  The index holds one
document per published tool, workflow, and notebook; services are not indexed.
"""

import logging
import re
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from dockstore_mcp.api import DockstoreApi
from dockstore_mcp.config import Settings
from dockstore_mcp.models import DescriptorLanguage, EntrySummary, EntryType, SortBy, SortOrder
from dockstore_mcp.tools.entries import _descriptor_type, _entry_type, _first_of, _timestamp

__all__ = ["DEFAULT_LIMIT", "MAX_LIMIT", "SEARCH_PATH", "SearchResults", "register"]

logger = logging.getLogger(__name__)

#: Where Dockstore accepts an Elasticsearch query, relative to its API.
SEARCH_PATH = "/api/ga4gh/v2/extended/tools/entry/_search"

#: How many results a caller gets when they do not ask for a particular number.
DEFAULT_LIMIT = 10

#: The most results one call will return, to keep a response readable.
MAX_LIMIT = 100

#: The indexed field each way of sorting orders by.  Relevance is absent because
#: it means different things with and without keywords; see :func:`_sort`.
#: Dockstore does not index when an entry was created, so that cannot be sorted on.
_SORT_FIELDS = {
    SortBy.NAME: ("normalizedName", "keyword"),
    SortBy.STARS: ("stars_count", "long"),
    SortBy.UPDATED: ("last_modified_date", "date"),
}

#: The direction each way of sorting runs in when the caller does not say.
_NATURAL_ORDER = {
    SortBy.RELEVANCE: SortOrder.DESCENDING,
    SortBy.NAME: SortOrder.ASCENDING,
    SortBy.STARS: SortOrder.DESCENDING,
    SortBy.UPDATED: SortOrder.DESCENDING,
}

#: The most keywords a query is split into, as on the Search page.
_MAX_TERMS = 20

#: Where ``query`` looks, and how much a match in each place counts for.  The
#: weights are the Search page's, so results come back in the order a person
#: searching the site would see them.
_QUERY_FIELDS = [
    "description^2",
    "labels^2",
    "all_authors.name^3",
    "topicAutomatic^4",
    *(
        f"{facet}.{key}^{boost}"
        for facet in (
            "categories",
            "topic",
            "operation",
            "input-format",
            "output-format",
            "input-data",
            "output-data",
        )
        for key, boost in (("displayName", 3), ("topic", 2))
    ),
    "workflowVersions.sourceFiles.content^0.2",
    "tags.sourceFiles.content^0.2",
]

#: Path fields, which a keyword can match any part of.
_PATH_FIELDS = ("full_workflow_path", "tool_path")

#: How much a keyword found in an entry's path counts for.
_PATH_BOOST = 14

#: The fields of each hit that an :class:`EntrySummary` is built from.
_SOURCE_FIELDS = [
    "entryTypeMetadata.type",
    "descriptorType",
    "workflowName",
    "toolname",
    "repository",
    "name",
    "full_workflow_path",
    "tool_path",
    "topicAutomatic",
    "dbCreateDate",
    "last_modified_date",
    "lastUpdated",
    "dbUpdateDate",
]

#: Characters that have a meaning of their own in a wildcard query.
_WILDCARD_SPECIALS = re.compile(r"([\\*?])")


class SearchResults(BaseModel):
    """The result of a call to the ``search_entries`` tool."""

    entries: list[EntrySummary] = Field(description="Matching entries, best match first.")
    returned_count: int = Field(description="How many entries are in this response.")
    total_count: int = Field(description="How many entries matched in total, which may exceed the limit.")


def register(mcp: FastMCP, settings: Settings, api: DockstoreApi) -> None:
    """Add the search tool to ``mcp``."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def search_entries(
        query: str | None = None,
        entry_type: EntryType | None = None,
        descriptor_type: DescriptorLanguage | None = None,
        author: str | None = None,
        input_data: str | None = None,
        input_format: str | None = None,
        output_data: str | None = None,
        output_format: str | None = None,
        operation: str | None = None,
        subject_area: str | None = None,
        sort_by: SortBy = SortBy.RELEVANCE,
        sort_order: SortOrder | None = None,
        limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    ) -> SearchResults:
        """Search Dockstore for tools, workflows, and notebooks.

        This is the Search page of the Dockstore site: it finds entries by keyword and
        narrows them by facet. Reach for it when you know what an entry does but not
        which entry it is. Once you have an entry from the results, ``get_entry`` will
        tell you more about it.

        Arguments left unset are not searched on. ``query`` searches across all of an
        entry's metadata and ranks the results; the other arguments each narrow the
        results to entries with matching metadata of one kind. Several arguments can be
        combined, and an entry has to satisfy all of them to match. The facet arguments
        match any entry whose metadata contains the words given, in order and ignoring
        case, so 'FASTQ' matches 'FASTQ-sanger'.

        Args:
            query: Keywords to look for anywhere in an entry's metadata, path, or descriptors.
            entry_type: Restrict results to one kind of entry. Services cannot be searched.
            descriptor_type: Restrict results to one descriptor language.
            author: Name of a person the entry credits, such as 'Jane Doe'.
            input_data: Kind of data an entry takes as input, such as 'Short-read sequencing data'.
            input_format: File format an entry takes as input, such as 'FASTQ'.
            output_data: Kind of data an entry produces, such as 'Variant call data'.
            output_format: File format an entry produces, such as 'VCF'.
            operation: Operation an entry performs, such as 'Sequence alignment'.
            subject_area: Subject area an entry works in, such as 'Genomics'.
            sort_by: What to order the results by. Defaults to how well they match, or,
                with no ``query``, to how relevant Dockstore considers each entry.
            sort_order: Which direction to order the results in. Defaults to
                alphabetical for ``name`` and largest or newest first for the rest.
            limit: How many entries to return, at most 100.

        Returns:
            Matching entries in the order asked for, with enough metadata to tell them
            apart, and a count of how many matched altogether.
        """
        body = _query(
            query,
            entry_type=entry_type,
            descriptor_type=descriptor_type,
            phrases={
                "all_authors.name": author,
                "input-data.displayName": input_data,
                "input-format.displayName": input_format,
                "output-data.displayName": output_data,
                "output-format.displayName": output_format,
                "operation.displayName": operation,
                "topic.displayName": subject_area,
            },
            sort_by=sort_by,
            sort_order=sort_order or _NATURAL_ORDER[sort_by],
            limit=limit,
        )
        response = await api.post_object(SEARCH_PATH, body)
        return _to_results(response)


def _query(
    query: str | None,
    *,
    entry_type: EntryType | None,
    descriptor_type: DescriptorLanguage | None,
    phrases: dict[str, str | None],
    sort_by: SortBy,
    sort_order: SortOrder,
    limit: int,
) -> dict[str, Any]:
    """Build the Elasticsearch query for a search."""
    if entry_type is EntryType.SERVICE:
        raise ToolError("Dockstore does not index services for search, so they cannot be searched for.")

    filters: list[dict[str, Any]] = []
    if entry_type is not None:
        filters.append({"term": {"entryTypeMetadata.type.keyword": entry_type.value.upper()}})
    if descriptor_type is not None:
        # A tool lists every language it has a descriptor in; a term matches any of them.
        filters.append({"term": {"descriptorType": descriptor_type.value}})
    filters.extend({"match_phrase": {field: value}} for field, value in phrases.items() if value and value.strip())

    body: dict[str, Any] = {
        "size": limit,
        "track_total_hits": True,
        "_source": _SOURCE_FIELDS,
        "query": {"bool": {"filter": filters}},
    }
    terms = (query or "").split()[:_MAX_TERMS]
    if terms:
        body["query"]["bool"]["must"] = [_keywords(" ".join(terms), terms)]
    body["sort"] = _sort(sort_by, sort_order, ranked=bool(terms))
    return body


def _sort(sort_by: SortBy, sort_order: SortOrder, *, ranked: bool) -> list[Any]:
    """Order the results as the Search page does, for a search with or without keywords."""
    # Relevance is how well an entry matched the keywords, or, with none, how
    # relevant Dockstore considers it overall.  It also breaks ties in any other sort.
    order = sort_order.value if sort_by is SortBy.RELEVANCE else SortOrder.DESCENDING.value
    relevance = {"_score": {"order": order}} if ranked else {"relevance": {"order": order, "unmapped_type": "double"}}
    if sort_by is SortBy.RELEVANCE:
        # Archived entries still match, but after everything that is not archived.
        return [{"archived": {"order": "asc", "unmapped_type": "boolean"}}, relevance] if ranked else [relevance]
    field, unmapped_type = _SORT_FIELDS[sort_by]
    # An entry with nothing to sort by goes last whichever way the results run.
    return [{field: {"order": sort_order.value, "missing": "_last", "unmapped_type": unmapped_type}}, relevance]


def _keywords(text: str, terms: list[str]) -> dict[str, Any]:
    """Match ``text`` against an entry's metadata, or any of ``terms`` against its path."""
    paths = [
        {
            "wildcard": {
                field: {
                    "value": f"*{_escape_wildcard(term)}*",
                    "case_insensitive": True,
                    "boost": _PATH_BOOST,
                }
            }
        }
        for term in terms
        for field in _PATH_FIELDS
    ]
    return {
        "bool": {
            "should": [{"multi_match": {"query": text, "fields": _QUERY_FIELDS}}, *paths],
            "minimum_should_match": 1,
        }
    }


def _escape_wildcard(term: str) -> str:
    """Make every character of ``term`` stand for itself in a wildcard query."""
    return _WILDCARD_SPECIALS.sub(r"\\\1", term)


def _to_results(response: dict[str, Any]) -> SearchResults:
    """Turn Elasticsearch's answer into search results."""
    hits = response.get("hits")
    if not isinstance(hits, dict):
        raise ToolError("Dockstore did not return search results; its search may be unavailable.")
    total = hits.get("total")
    total_count = total.get("value", 0) if isinstance(total, dict) else total if isinstance(total, int) else 0
    entries = [summary for hit in hits.get("hits") or [] if (summary := _to_summary(hit)) is not None]
    return SearchResults(entries=entries, returned_count=len(entries), total_count=total_count)


def _to_summary(hit: Any) -> EntrySummary | None:
    """Summarize one search hit, or return None for a hit that cannot be identified."""
    source = hit.get("_source") if isinstance(hit, dict) else None
    if not isinstance(source, dict):
        return None
    metadata = source.get("entryTypeMetadata")
    entry_type = _entry_type(metadata.get("type") if isinstance(metadata, dict) else None)
    path = _first_of(source, "full_workflow_path", "tool_path")
    # A document's own id field is always 0; Dockstore files it under the entry's identifier.
    identifier = hit.get("_id")
    if not identifier or entry_type is None or not path:
        logger.debug("Skipping a search hit that cannot be identified: %r", identifier)
        return None
    return EntrySummary(
        id=str(identifier),
        entry_type=entry_type,
        descriptor_type=_descriptor_type(source.get("descriptorType")),
        name=_first_of(source, "workflowName", "toolname", "repository", "name") or path,
        path=path,
        topic=source.get("topicAutomatic"),
        created_at=_timestamp(source.get("dbCreateDate")),
        updated_at=_timestamp(
            source.get("last_modified_date") or source.get("lastUpdated") or source.get("dbUpdateDate")
        ),
    )
