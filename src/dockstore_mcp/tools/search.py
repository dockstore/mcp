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
"""Entry search, the equivalent of Dockstore's Search page.

TODO: this is scaffolding.  ``search_entries`` raises ``NotImplementedError``
until it is wired up to Dockstore's search API.
"""

import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from dockstore_mcp.config import Settings
from dockstore_mcp.models import DescriptorLanguage, EntrySummary, EntryType, SortBy, SortOrder

__all__ = ["SearchResults", "register"]

logger = logging.getLogger(__name__)

#: How many results a caller gets when they do not ask for a particular number.
DEFAULT_LIMIT = 10

#: The most results one call will return, to keep a response readable.
MAX_LIMIT = 100


class SearchResults(BaseModel):
    """The result of a call to the ``search_entries`` tool."""

    entries: list[EntrySummary] = Field(description="Matching entries, best match or highest sorted value first.")
    returned_count: int = Field(description="How many entries are in this response.")
    total_count: int = Field(description="How many entries matched in total, which may exceed the limit.")


def register(mcp: FastMCP, settings: Settings) -> None:
    """Add the search tool to ``mcp``."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def search_entries(
        query: str | None = None,
        name: str | None = None,
        description: str | None = None,
        author: str | None = None,
        organization: str | None = None,
        subject_area: str | None = None,
        operation: str | None = None,
        input_format: str | None = None,
        output_format: str | None = None,
        entry_type: EntryType | None = None,
        descriptor_type: DescriptorLanguage | None = None,
        sort_by: SortBy = SortBy.RELEVANCE,
        sort_order: SortOrder = SortOrder.DESCENDING,
        limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    ) -> SearchResults:
        """Search Dockstore for tools, workflows, and notebooks.

        This is the Search page of the Dockstore site: it finds entries by keyword and
        narrows them by facet. Reach for it when you know what an entry does but not
        which entry it is. Once you have an entry from the results, ``get_entry`` will
        tell you more about it.

        Arguments left unset are not searched on. ``query`` searches across all of an
        entry's metadata; the other keyword arguments search one kind of metadata each,
        so use them when you know where the term should appear. Several arguments can be
        combined, and an entry has to satisfy all of them to match.

        Args:
            query: Keywords to look for anywhere in an entry's metadata.
            name: Keywords to look for in the entry's name and path.
            description: Keywords to look for in the entry's topic and description.
            author: Name of an author or maintainer of the entry.
            organization: Organization the entry belongs to.
            subject_area: Subject area an entry works in, such as 'Genomics'.
            operation: Operation an entry performs, such as 'Sequence alignment'.
            input_format: File format an entry takes as input, such as 'FASTQ'.
            output_format: File format an entry produces, such as 'VCF'.
            entry_type: Restrict results to one kind of entry.
            descriptor_type: Restrict results to one descriptor language.
            sort_by: What to order the results by. Defaults to how well they match.
            sort_order: Which direction to order the results in.
            limit: How many entries to return, at most 100.

        Returns:
            Matching entries with enough metadata to tell them apart, and a count of
            how many matched altogether.
        """
        # TODO: call the Dockstore search API, map the facets above onto its query, and
        # build EntrySummary objects from the hits.
        raise NotImplementedError("search_entries is not implemented yet")
