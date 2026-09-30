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
"""Lookups of a single entry, version, or file.

The three tools here are a chain: an entry has versions, a version has files.
``get_entry`` limits by default how many of an entry's versions and how much of
its README it returns, so that a caller does not pull down more than it needs to
decide what to read next; ``get_version`` does the same for its file paths, and
``get_file`` for its content.

TODO: ``get_version`` and ``get_file`` are still scaffolding and raise
``NotImplementedError`` until they are wired up to the Dockstore API.
"""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from dockstore_mcp.api import DockstoreApi, NotFoundError
from dockstore_mcp.config import Settings
from dockstore_mcp.models import (
    DescriptorLanguage,
    Entry,
    EntryType,
    File,
    ReferenceType,
    Version,
    VersionSummary,
)

__all__ = [
    "DEFAULT_CONTENT_LIMIT",
    "DEFAULT_DESCRIPTION_LIMIT",
    "DEFAULT_FILE_LIMIT",
    "DEFAULT_VERSION_LIMIT",
    "register",
]

logger = logging.getLogger(__name__)

_EPOCH = datetime.fromtimestamp(0, tz=UTC)

#: How many versions get_entry returns by default: the first, in Dockstore's order.
DEFAULT_VERSION_LIMIT = 20

#: The most versions Dockstore returns in one page.
_VERSION_PAGE_LIMIT = 100

#: How many characters of the description get_entry returns by default.
DEFAULT_DESCRIPTION_LIMIT = 5000

#: How many file paths get_version returns by default: the primary descriptor first.
DEFAULT_FILE_LIMIT = 100

#: How many characters of a file's content get_file returns by default.
DEFAULT_CONTENT_LIMIT = 50_000

#: Dockstore files an entry under automatic categories whose names say which
#: facet they belong to, so one request for categories answers six of the
#: fields above; anything else is a category a person curated.
_CATEGORY_FACETS = {
    "subject_areas": ("topic-",),
    "operations": ("operation-",),
    "input_formats": ("input-format-",),
    "output_formats": ("output-format-",),
    "input_data": ("input-data-",),
    "output_data": ("output-data-",),
}


def register(mcp: FastMCP, settings: Settings, api: DockstoreApi) -> None:
    """Add the entry, version, and file lookup tools to ``mcp``."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_entry(
        entry_id: str,
        description_limit: Annotated[int | None, Field(ge=1)] = DEFAULT_DESCRIPTION_LIMIT,
        version_limit: Annotated[int | None, Field(ge=1)] = DEFAULT_VERSION_LIMIT,
    ) -> Entry:
        """Retrieve information about one Dockstore entry.

        Use this once you have an entry's identifier, which ``search_entries`` returns.
        To read a particular version of the entry, take the id of one of the returned
        ``versions`` and pass it to ``get_version``.

        Args:
            entry_id: Dockstore identifier of the entry, as returned by ``search_entries``.
            description_limit: The most characters of the ``description``, which is
                often a whole README, to return. Pass null to get the full description.
            version_limit: The most ``versions`` to return, taken from the start of
                Dockstore's order, which puts the default version first and the most
                relevant after it. Pass null to get every version.

        Returns:
            The entry.
        """
        identifier = _identifier(entry_id)
        payload = await _fetch_entry(api, identifier, version_limit=version_limit)
        categories = await _fetch_categories(api, identifier)
        return _to_entry(
            payload,
            categories,
            settings,
            description_limit=description_limit,
            version_limit=version_limit,
        )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_version(
        version_id: str,
        file_limit: Annotated[int | None, Field(ge=1)] = DEFAULT_FILE_LIMIT,
    ) -> Version:
        """Retrieve information about one version of a Dockstore entry.

        A version is a tag, branch, or snapshot of an entry, and it is the level at
        which descriptors and other files exist. Version identifiers come from
        ``get_entry``. To read one of the version's files, take a path from the returned
        ``file_paths`` and pass it to ``get_file``.

        Args:
            version_id: Dockstore identifier of the version, as returned by ``get_entry``.
            file_limit: The most ``file_paths`` to return, starting with the
                ``descriptor_path``, which is never cut. Pass null to get every path.

        Returns:
            The version.
        """
        # TODO: fetch the version from the Dockstore API, putting the primary
        # descriptor first in file_paths and cutting them short at file_limit.
        raise NotImplementedError("get_version is not implemented yet")

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_file(
        version_id: str,
        path: str,
        content_limit: Annotated[int | None, Field(ge=1)] = DEFAULT_CONTENT_LIMIT,
    ) -> File:
        """Retrieve one file belonging to a version of a Dockstore entry.

        This is how to read a descriptor, a test parameter file, or anything else
        Dockstore holds for a version. Paths come from a version's ``file_paths``, and
        the primary descriptor is at its ``descriptor_path``.

        Args:
            version_id: Dockstore identifier of the version the file belongs to.
            path: Path of the file within the version, as returned by ``get_version``.
            content_limit: The most characters of the ``content`` to return. Pass
                null to get the whole file.

        Returns:
            The file.
        """
        # TODO: fetch the file from the Dockstore API, cutting its content short
        # at content_limit with _truncate.
        raise NotImplementedError("get_file is not implemented yet")


def _identifier(entry_id: str) -> str:
    """Check that ``entry_id`` looks like a Dockstore identifier, and normalize it."""
    identifier = entry_id.strip()
    if not identifier.isdecimal():
        raise ToolError(
            f"'{entry_id}' is not a Dockstore entry identifier. Identifiers are numbers; "
            "search_entries returns them, as does the id field of an entry."
        )
    return identifier


async def _fetch_entry(api: DockstoreApi, identifier: str, *, version_limit: int | None) -> dict[str, Any]:
    """Fetch a published entry and its versions, whichever kind of entry it turns out to be."""
    # Workflows, notebooks, services, and apptools are all served by the workflows
    # endpoint; only tools live elsewhere, so that endpoint is the one to try second.
    try:
        workflow = await api.get_object(f"/workflows/published/{identifier}")
    except NotFoundError:
        pass
    else:
        versions = await _fetch_workflow_versions(api, identifier, limit=version_limit)
        return workflow | {"workflowVersions": versions}
    try:
        # Tools have no paged endpoint for their versions, so they come with the tool.
        return await api.get_object(f"/containers/published/{identifier}", {"include": "versions"})
    except NotFoundError:
        raise NotFoundError(
            f"Dockstore has no published entry with identifier '{identifier}'. "
            "Use search_entries to find an entry and its identifier."
        ) from None


async def _fetch_workflow_versions(api: DockstoreApi, identifier: str, *, limit: int | None) -> list[Any]:
    """Fetch a workflow's visible versions in Dockstore's order, only the first ``limit`` if one is given."""
    endpoint = f"/workflows/published/{identifier}/workflowVersions"
    if limit is not None and limit <= _VERSION_PAGE_LIMIT:
        return await api.get_list(endpoint, {"limit": limit})
    versions: list[Any] = []
    while limit is None or len(versions) < limit:
        page_limit = _VERSION_PAGE_LIMIT if limit is None else min(_VERSION_PAGE_LIMIT, limit - len(versions))
        page = await api.get_list(endpoint, {"limit": page_limit, "offset": len(versions)})
        versions.extend(page)
        if len(page) < page_limit:
            break
    return versions


async def _fetch_categories(api: DockstoreApi, identifier: str) -> list[Any]:
    """Fetch the categories an entry has been filed under."""
    try:
        return await api.get_list(f"/entries/{identifier}/categories")
    except NotFoundError:
        # The entry exists, so treat a miss here as an entry nobody has categorized.
        return []


def _to_entry(
    payload: dict[str, Any],
    categories: list[Any],
    settings: Settings,
    *,
    description_limit: int | None,
    version_limit: int | None,
) -> Entry:
    """Map a Dockstore entry payload onto an :class:`Entry`, trimmed to the limits given."""
    facets = _facets(categories)
    versions = payload.get("workflowVersions")
    summaries = _versions(versions)
    description = payload.get("description")
    starred = payload.get("starredUsers")
    values: dict[str, Any] = {
        "id": _text(payload.get("id")),
        "type": _entry_type(payload.get("entryType")),
        "language": _language(payload.get("descriptorType")),
        "name": _first_of(payload, "workflowName", "toolname", "repository", "name"),
        "organization": _first_of(payload, "organization", "namespace"),
        "trs_id": payload.get("trsId"),
        "topic": payload.get("topic"),
        "description": _truncate(description, description_limit),
        "authors": _values_of(payload.get("authors"), "name"),
        "labels": _values_of(payload.get("labels"), "value"),
        "categories": facets["categories"],
        "subject_areas": facets["subject_areas"],
        "operations": facets["operations"],
        "input_formats": facets["input_formats"],
        "output_formats": facets["output_formats"],
        "input_data": facets["input_data"],
        "output_data": facets["output_data"],
        "registry": _first_of(payload, "registry_string", "registry"),
        "source_control": _source_control(payload),
        "is_published": payload.get("is_published"),
        "star_count": len(starred) if starred is not None else None,
        "default_version": _default_version(summaries, payload.get("defaultVersion")),
        # A workflow's versions are already in Dockstore's order, and too few to trim.
        "versions": _most_recent(summaries, version_limit),
        "doi": _doi(payload),
        "created_at": _timestamp(payload.get("dbCreateDate")),
        "updated_at": _timestamp(
            payload.get("last_modified_date") or payload.get("lastUpdated") or payload.get("dbUpdateDate")
        ),
        "url": _url(payload, settings),
    }
    return Entry.model_validate(values)


def _facets(categories: Iterable[Any]) -> dict[str, list[str]]:
    """Sort an entry's categories into the fields of an :class:`Entry` they belong to.

    Dockstore's automatic categorization files an entry under categories named for
    the facet they belong to ('topic-genomics', 'input-format-vcf') and records the
    ontology term each came from in the category's metadata.  A category without
    both of those is one a person curated, and stands for itself.
    """
    facets: dict[str, list[str]] = {name: [] for name in _CATEGORY_FACETS}
    facets["categories"] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        name = category.get("name") or ""
        label = category.get("displayName") or name
        if not label:
            continue
        facet = next(
            (field for field, prefixes in _CATEGORY_FACETS.items() if name.startswith(prefixes)),
            "categories",
        )
        if facet != "categories" and not category.get("metadata"):
            facet = "categories"
        facets[facet].append(label)
    # Two categories can share a display name, and a caller only needs it once.
    return {field: list(dict.fromkeys(labels)) for field, labels in facets.items()}


def _versions(versions: Any) -> list[VersionSummary] | None:
    """Summarize each of an entry's versions, skipping any without an identifier."""
    if not isinstance(versions, list):
        return None
    return [
        VersionSummary(
            id=str(version["id"]),
            name=version.get("name"),
            reference_type=_reference_type(version.get("referenceType")),
            updated_at=_timestamp(version.get("last_modified") or version.get("dbUpdateDate")),
        )
        for version in versions
        if isinstance(version, dict) and version.get("id") is not None
    ]


def _most_recent(summaries: list[VersionSummary] | None, limit: int | None) -> list[VersionSummary] | None:
    """Keep the ``limit`` most recently updated versions, newest first, or all of them if no limit."""
    if summaries is None or limit is None or len(summaries) <= limit:
        return summaries
    # A version with no date sorts after every version with one.
    return sorted(summaries, key=lambda summary: summary.updated_at or _EPOCH, reverse=True)[:limit]


def _truncate(text: Any, limit: int | None) -> Any:
    """Cut ``text`` down to ``limit`` characters, ending with an ellipsis if anything was cut."""
    if not isinstance(text, str) or limit is None or len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _default_version(summaries: list[VersionSummary] | None, name: Any) -> VersionSummary | None:
    """Find the version the entry names as its default, which Dockstore identifies by name."""
    if summaries is None or not name:
        return None
    return next((summary for summary in summaries if summary.name == name), None)


def _first_of(payload: dict[str, Any], *keys: str) -> Any:
    """Return the first of ``keys`` that the payload has a truthy value for.

    Tools and workflows spell several of the same things differently, so most of
    the fields above come from whichever of a couple of keys is present.
    """
    return next((payload[key] for key in keys if payload.get(key)), None)


def _values_of(items: Any, key: str) -> list[str]:
    """Pull one key out of each of a payload's nested objects, skipping the empty ones."""
    if not isinstance(items, list):
        return []
    return [item[key] for item in items if isinstance(item, dict) and item.get(key)]


def _text(value: Any) -> str | None:
    """Render an identifier as a string, since Dockstore numbers its entries."""
    return None if value is None else str(value)


def _entry_type(value: Any) -> EntryType | None:
    if not isinstance(value, str):
        return None
    try:
        return EntryType(value.lower())
    except ValueError:
        logger.debug("Dockstore reported an entry type this server does not know: %r", value)
        return None


def _reference_type(value: Any) -> ReferenceType | None:
    if not isinstance(value, str):
        return None
    try:
        return ReferenceType(value.lower())
    except ValueError:
        # Hosted entries have no source control, and report NOT_APPLICABLE or UNSET.
        logger.debug("Dockstore reported a reference type this server does not know: %r", value)
        return None


def _language(value: Any) -> DescriptorLanguage | None:
    # A tool carries a list, since one tool can have both a CWL and a WDL descriptor.
    if isinstance(value, list):
        value = next(iter(value), None)
    if not isinstance(value, str):
        return None
    try:
        return DescriptorLanguage.from_dockstore(value)
    except ValueError:
        # Services have no descriptor language, and report one that is not a language.
        logger.debug("Dockstore reported a descriptor type this server does not know: %r", value)
        return None


def _source_control(payload: dict[str, Any]) -> str | None:
    """Name the host the descriptor lives on, which only a workflow states outright."""
    source_control = payload.get("sourceControl")
    if isinstance(source_control, str) and source_control:
        return source_control
    git_url = payload.get("gitUrl")  # For a tool, 'git@github.com:org/repo.git'.
    if isinstance(git_url, str) and "@" in git_url and ":" in git_url:
        return git_url.split("@", 1)[1].split(":", 1)[0] or None
    return None


def _doi(payload: dict[str, Any]) -> str | None:
    """Return the concept DOI the entry's owner chose to advertise."""
    concept_dois = payload.get("conceptDois")
    if isinstance(concept_dois, dict):
        chosen = concept_dois.get(payload.get("doiSelection"))
        if isinstance(chosen, dict) and chosen.get("name"):
            return str(chosen["name"])
    legacy = payload.get("conceptDoi")
    return legacy if isinstance(legacy, str) and legacy else None


def _timestamp(value: Any) -> datetime | None:
    """Turn one of Dockstore's epoch milliseconds into a datetime."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _url(payload: dict[str, Any], settings: Settings) -> str | None:
    """Build the address of the entry's page, which varies by kind of entry."""
    metadata = payload.get("entryTypeMetadata")
    site_path = metadata.get("sitePath") if isinstance(metadata, dict) else None
    path = _first_of(payload, "full_workflow_path", "tool_path", "path")
    if not site_path or not path:
        return None
    return f"{settings.dockstore_url}/{site_path}/{path}"
