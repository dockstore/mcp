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
Each takes a list of fields, so a caller can ask for a name and a date without
also pulling down a README or the contents of a descriptor.

TODO: ``get_version`` and ``get_file`` are still scaffolding and raise
``NotImplementedError`` until they are wired up to the Dockstore API.
"""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from dockstore_mcp.api import DockstoreApi, NotFoundError
from dockstore_mcp.config import Settings
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

__all__ = ["DEFAULT_ENTRY_FIELDS", "DEFAULT_FILE_FIELDS", "DEFAULT_VERSION_FIELDS", "register"]

logger = logging.getLogger(__name__)

#: What get_entry returns when the caller does not name any fields: enough to
#: identify the entry and to follow it to its versions, but no bulky text.
DEFAULT_ENTRY_FIELDS = [
    EntryField.ID,
    EntryField.ENTRY_TYPE,
    EntryField.DESCRIPTOR_TYPE,
    EntryField.NAME,
    EntryField.ORGANIZATION,
    EntryField.PATH,
    EntryField.TOPIC,
    EntryField.AUTHORS,
    EntryField.DEFAULT_VERSION,
    EntryField.VERSION_IDS,
    EntryField.UPDATED_AT,
    EntryField.URL,
]

#: What get_version returns when the caller does not name any fields.
DEFAULT_VERSION_FIELDS = [
    VersionField.ID,
    VersionField.ENTRY_ID,
    VersionField.NAME,
    VersionField.DESCRIPTOR_TYPE,
    VersionField.DESCRIPTOR_PATH,
    VersionField.FILE_PATHS,
    VersionField.IS_VALID,
    VersionField.IS_VERIFIED,
    VersionField.UPDATED_AT,
    VersionField.URL,
]

#: What get_file returns when the caller does not name any fields.  Unlike the
#: other two this includes the content, since that is the point of the file.
DEFAULT_FILE_FIELDS = [
    FileField.PATH,
    FileField.FILE_TYPE,
    FileField.CONTENT,
]

#: Fields that can only be answered from the entry's versions, which Dockstore
#: leaves out of an entry unless they are asked for by name.
_VERSION_BACKED = frozenset({EntryField.VERSION_IDS, EntryField.IS_VERIFIED})

#: Fields that come from the entry's categories, which are a second request.
_CATEGORY_BACKED = frozenset(
    {
        EntryField.CATEGORIES,
        EntryField.SUBJECT_AREAS,
        EntryField.OPERATIONS,
        EntryField.INPUT_FORMATS,
        EntryField.OUTPUT_FORMATS,
        EntryField.INPUT_DATA,
        EntryField.OUTPUT_DATA,
    }
)

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
    async def get_entry(entry_id: str, fields: list[EntryField] | None = None) -> Entry:
        """Retrieve information about one Dockstore entry.

        Use this once you have an entry's identifier, which ``search_entries`` returns.
        To read a particular version of the entry, take an identifier from the returned
        ``version_ids`` and pass it to ``get_version``.

        Args:
            entry_id: Dockstore identifier of the entry, as returned by ``search_entries``.
            fields: Which fields to return. Ask only for what you need: ``description``
                is often a whole README. Defaults to a summary of the entry.

        Returns:
            The entry, with the requested fields populated and the rest left unset.
        """
        requested = frozenset(fields or DEFAULT_ENTRY_FIELDS)
        identifier = _identifier(entry_id)
        payload = await _fetch_entry(api, identifier, versions=bool(requested & _VERSION_BACKED))
        categories = await _fetch_categories(api, identifier) if requested & _CATEGORY_BACKED else []
        return _to_entry(payload, categories, requested, settings)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_version(version_id: str, fields: list[VersionField] | None = None) -> Version:
        """Retrieve information about one version of a Dockstore entry.

        A version is a tag, branch, or snapshot of an entry, and it is the level at
        which descriptors and other files exist. Version identifiers come from
        ``get_entry``. To read one of the version's files, take a path from the returned
        ``file_paths`` and pass it to ``get_file``.

        Args:
            version_id: Dockstore identifier of the version, as returned by ``get_entry``.
            fields: Which fields to return. Defaults to a summary of the version.

        Returns:
            The version, with the requested fields populated and the rest left unset.
        """
        # TODO: fetch the version from the Dockstore API and populate the requested fields.
        raise NotImplementedError("get_version is not implemented yet")

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_file(version_id: str, path: str, fields: list[FileField] | None = None) -> File:
        """Retrieve one file belonging to a version of a Dockstore entry.

        This is how to read a descriptor, a test parameter file, or anything else
        Dockstore holds for a version. Paths come from a version's ``file_paths``, and
        the primary descriptor is at its ``descriptor_path``.

        Args:
            version_id: Dockstore identifier of the version the file belongs to.
            path: Path of the file within the version, as returned by ``get_version``.
            fields: Which fields to return. Defaults to the file's contents and what
                kind of file it is.

        Returns:
            The file, with the requested fields populated and the rest left unset.
        """
        # TODO: fetch the file from the Dockstore API and populate the requested fields.
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


async def _fetch_entry(api: DockstoreApi, identifier: str, *, versions: bool) -> dict[str, Any]:
    """Fetch a published entry, whichever kind of entry it turns out to be."""
    params = {"include": "versions"} if versions else None
    # Workflows, notebooks, services, and apptools are all served by the workflows
    # endpoint; only tools live elsewhere, so that endpoint is the one to try second.
    for endpoint in (f"/workflows/published/{identifier}", f"/containers/published/{identifier}"):
        try:
            return await api.get_object(endpoint, params)
        except NotFoundError:
            continue
    raise NotFoundError(
        f"Dockstore has no published entry with identifier '{identifier}'. "
        "Use search_entries to find an entry and its identifier."
    )


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
    requested: frozenset[EntryField],
    settings: Settings,
) -> Entry:
    """Map a Dockstore entry payload onto the requested fields of an :class:`Entry`."""
    facets = _facets(categories)
    versions = payload.get("workflowVersions")
    starred = payload.get("starredUsers")
    values: dict[str, Any] = {
        "id": _text(payload.get("id")),
        "entry_type": _entry_type(payload.get("entryType")),
        "descriptor_type": _descriptor_type(payload.get("descriptorType")),
        "name": _first_of(payload, "workflowName", "toolname", "repository", "name"),
        "organization": _first_of(payload, "organization", "namespace"),
        "path": _first_of(payload, "full_workflow_path", "tool_path", "path"),
        "trs_id": payload.get("trsId"),
        "topic": payload.get("topic"),
        "description": payload.get("description"),
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
        "is_verified": any(version.get("verified") for version in versions) if versions is not None else None,
        "star_count": len(starred) if starred is not None else None,
        "default_version": payload.get("defaultVersion"),
        "version_ids": [_text(v.get("id")) for v in versions if v.get("id") is not None] if versions else versions,
        "doi": _doi(payload),
        "created_at": _timestamp(payload.get("dbCreateDate")),
        "updated_at": _timestamp(
            payload.get("last_modified_date") or payload.get("lastUpdated") or payload.get("dbUpdateDate")
        ),
        "url": _url(payload, settings),
    }
    return Entry.model_validate({field.value: values[field.value] for field in requested})


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


def _descriptor_type(value: Any) -> DescriptorLanguage | None:
    # A tool carries a list, since one tool can have both a CWL and a WDL descriptor.
    if isinstance(value, list):
        value = next(iter(value), None)
    if not isinstance(value, str):
        return None
    try:
        return DescriptorLanguage(value)
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
