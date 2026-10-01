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

Entries and versions are identified as GA4GH TRS identifies them: an entry by its
TRS identifier ('#workflow/github.com/org/repo/name' or, for a tool,
'quay.io/org/repo'), and a version by its entry's TRS identifier and its name,
joined by a colon ('#workflow/github.com/org/repo/name:v1.0').

TODO: ``get_file`` is still scaffolding and raises ``NotImplementedError`` until
it is wired up to the Dockstore API.
"""

import asyncio
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from dockstore_mcp.api import DockstoreApi, DockstoreError, NotFoundError
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

#: The TRS prefix of each kind of entry the workflows endpoint serves, with the
#: subclass that endpoint files that kind under.  An identifier with no prefix is
#: a tool's or an apptool's.
_WORKFLOW_SUBCLASSES = {"#workflow/": "BIOWORKFLOW", "#notebook/": "NOTEBOOK", "#service/": "SERVICE"}

#: The section of the site each kind of entry's pages live in, by TRS prefix.  Tools
#: and apptools, which have no prefix, both live among the containers.
_SITE_PATHS = {"#workflow/": "workflows", "#notebook/": "notebooks", "#service/": "services", "": "containers"}

#: The language each TRS descriptor type stands for.  A service's descriptor is
#: not written in a language.
_TRS_DESCRIPTOR_TYPES = {
    "CWL": DescriptorLanguage.CWL,
    "WDL": DescriptorLanguage.WDL,
    "NFL": DescriptorLanguage.NEXTFLOW,
    "GALAXY": DescriptorLanguage.GALAXY,
    "SMK": DescriptorLanguage.SNAKEMAKE,
    "JUPYTER": DescriptorLanguage.JUPYTER,
    "SERVICE": None,
}

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

        Use this once you have an entry's TRS identifier, which ``search_entries``
        returns. To read a particular version of the entry, take the id of one of the
        returned ``versions`` and pass it to ``get_version``.

        Args:
            entry_id: TRS identifier of the entry, as returned by ``search_entries``,
                such as '#workflow/github.com/org/repo/name' or, for a tool,
                'quay.io/org/repo'.
            description_limit: The most characters of the ``description``, which is
                often a whole README, to return. Pass null to get the full description.
            version_limit: The most ``versions`` to return, taken from the start of
                Dockstore's order, which puts the default version first and the most
                relevant after it. Pass null to get every version.

        Returns:
            The entry.
        """
        trs_id = _identifier(entry_id)
        payload = await _fetch_entry(api, trs_id, version_limit=version_limit)
        categories = await _fetch_categories(api, _dockstore_id(payload))
        return _to_entry(
            payload,
            categories,
            settings,
            description_limit=description_limit,
            version_limit=version_limit,
        )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_version(
        version_id: str,
        file_limit: Annotated[int | None, Field(ge=1)] = DEFAULT_FILE_LIMIT,
    ) -> Version:
        """Retrieve information about one version of a Dockstore entry.

        A version is a tag, branch, or snapshot of an entry, and it is the level at
        which descriptors and other files exist. Version identifiers come from
        ``get_entry``. To read one of the version's files, take a path from the returned
        ``file_paths`` and pass it to ``get_file``.

        Args:
            version_id: TRS identifier of the version, as returned by ``get_entry``: the
                entry's TRS identifier and the version name joined by a colon, such as
                '#workflow/github.com/org/repo/name:v1.0'.
            file_limit: The most ``file_paths`` to return, starting with the
                ``descriptor_path``, which is never cut. Pass null to get every path.

        Returns:
            The version.
        """
        trs_id, name = _version_identifier(version_id)
        version, files = await _fetch_version(api, trs_id, name)
        return _to_version(version, files, trs_id, settings, file_limit=file_limit)

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
            version_id: TRS identifier of the version the file belongs to, as returned
                by ``get_entry``.
            path: Path of the file within the version, as returned by ``get_version``.
            content_limit: The most characters of the ``content`` to return. Pass
                null to get the whole file.

        Returns:
            The file.
        """
        _version_identifier(version_id)
        # TODO: fetch the file from the Dockstore API, cutting its content short
        # at content_limit with _truncate.
        raise NotImplementedError("get_file is not implemented yet")


def _identifier(entry_id: str) -> str:
    """Check that ``entry_id`` looks like a TRS identifier, and normalize it."""
    trs_id = entry_id.strip()
    prefix, path = _split_trs_id(trs_id)
    if (
        "/" not in path
        or any(character.isspace() for character in trs_id)
        or (prefix and prefix not in _WORKFLOW_SUBCLASSES)
    ):
        raise ToolError(
            f"'{entry_id}' is not the TRS identifier of a Dockstore entry. Identifiers look like "
            "'#workflow/github.com/org/repo/name' or, for a tool, 'quay.io/org/repo'; "
            "search_entries returns them, as does the id field of an entry."
        )
    return trs_id


def _version_identifier(version_id: str) -> tuple[str, str]:
    """Split a TRS version identifier into its entry's TRS identifier and the version name."""
    # An entry's path has no colon in it, but a version name can have a slash.
    trs_id, _, name = version_id.strip().rpartition(":")
    if not trs_id or not name:
        raise ToolError(
            f"'{version_id}' is not the TRS identifier of a version. A version is identified by "
            "its entry's TRS identifier and its name, joined by a colon, such as "
            "'#workflow/github.com/org/repo/name:v1.0'; get_entry returns them as the id of each version."
        )
    return _identifier(trs_id), name


def _split_trs_id(trs_id: str) -> tuple[str, str]:
    """Split a TRS identifier into its prefix, if it has one, and the entry's path."""
    if not trs_id.startswith("#"):
        return "", trs_id
    prefix, _, path = trs_id.partition("/")
    return f"{prefix}/", path


async def _fetch_entry(api: DockstoreApi, trs_id: str, *, version_limit: int | None) -> dict[str, Any]:
    """Fetch a published entry and its versions, whichever kind of entry it turns out to be."""
    prefix, path = _split_trs_id(trs_id)
    # The path goes in the request as a single segment, slashes and all.
    encoded = quote(path, safe="")
    if prefix:
        subclass = _WORKFLOW_SUBCLASSES[prefix]
    else:
        # Tools and apptools share identifiers with no prefix, but only tools live
        # outside the workflows endpoint.
        try:
            # Tools have no paged endpoint for their versions, so they come with the tool.
            return await api.get_object(f"/containers/path/tool/{encoded}/published", {"include": "versions"})
        except NotFoundError:
            subclass = "APPTOOL"
    try:
        workflow = await api.get_object(f"/workflows/path/workflow/{encoded}/published", {"subclass": subclass})
    except NotFoundError:
        raise NotFoundError(
            f"Dockstore has no published entry with TRS identifier '{trs_id}'. "
            "Use search_entries to find an entry and its identifier."
        ) from None
    versions = await _fetch_workflow_versions(api, _dockstore_id(workflow), limit=version_limit)
    return workflow | {"workflowVersions": versions}


async def _fetch_version(
    api: DockstoreApi, trs_id: str, name: str
) -> tuple[dict[str, Any], list[tuple[str, list[Any]]]]:
    """Fetch a published entry's visible version and its files, whichever kind of entry it belongs to."""
    trs_version_id = f"{trs_id}:{name}"
    try:
        ids = await api.get_object("/entries/mapTrsVersionId", {"trsVersionId": trs_version_id})
    except NotFoundError:
        raise NotFoundError(
            f"Dockstore has no published version with TRS identifier '{trs_version_id}'. "
            "Use get_entry to list an entry's versions and their identifiers."
        ) from None
    entry_id, version_id = ids.get("entryId"), ids.get("versionId")
    if entry_id is None or version_id is None:
        raise DockstoreError("Dockstore answered with a version that has no identifier.")
    version, files = await asyncio.gather(
        _fetch_version_by_ids(api, trs_id, entry_id, version_id),
        _fetch_trs_files(api, trs_id, name),
    )
    return version, files


async def _fetch_version_by_ids(api: DockstoreApi, trs_id: str, entry_id: Any, version_id: Any) -> dict[str, Any]:
    """Fetch a version by the numbers Dockstore files it and its entry under."""
    prefix, _ = _split_trs_id(trs_id)
    if not prefix:
        # Tools and apptools share identifiers with no prefix, but only tools keep
        # their versions outside the workflows endpoint.
        try:
            return await api.get_object(f"/containers/published/{entry_id}/tags/{version_id}")
        except NotFoundError:
            pass
    return await api.get_object(f"/workflows/published/{entry_id}/workflowVersions/{version_id}")


async def _fetch_trs_files(api: DockstoreApi, trs_id: str, name: str) -> list[tuple[str, list[Any]]]:
    """Fetch the TRS listing of a version's files for each descriptor type it has, in TRS's order of types.

    TRS lists a version's files one descriptor type at a time, and reports which
    types a version has from the descriptors it actually holds.
    """
    endpoint = f"/ga4gh/trs/v2/tools/{quote(trs_id, safe='')}/versions/{quote(name, safe='')}"
    tool_version = await api.get_object(endpoint)
    types = tool_version.get("descriptor_type")
    types = [type_ for type_ in types if isinstance(type_, str)] if isinstance(types, list) else []
    listings = await asyncio.gather(*(api.get_list(f"{endpoint}/{type_}/files") for type_ in types))
    return list(zip(types, listings, strict=True))


def _dockstore_id(payload: dict[str, Any]) -> str:
    """Return the number Dockstore files an entry under, which its other endpoints are addressed by."""
    identifier = payload.get("id")
    if identifier is None:
        raise DockstoreError("Dockstore answered with an entry that has no identifier.")
    return str(identifier)


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
    trs_id = _trs_id(payload)
    summaries = _versions(payload.get("workflowVersions"), trs_id)
    description = payload.get("description")
    starred = payload.get("starredUsers")
    values: dict[str, Any] = {
        "id": trs_id,
        "type": _entry_type(payload.get("entryType")),
        "language": _language(payload.get("descriptorType")),
        "name": _first_of(payload, "workflowName", "toolname", "repository", "name"),
        "organization": _first_of(payload, "organization", "namespace"),
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


def _to_version(
    payload: dict[str, Any],
    files_by_type: list[tuple[str, list[Any]]],
    trs_id: str,
    settings: Settings,
    *,
    file_limit: int | None,
) -> Version:
    """Map a Dockstore version payload and its files onto a :class:`Version`, trimmed to the limit given."""
    paths: list[str] = []
    descriptor_path: str | None = None
    language: DescriptorLanguage | None = None
    for type_, files in files_by_type:
        for file in files:
            if not isinstance(file, dict) or not isinstance(file.get("path"), str):
                continue
            # A file every language uses, such as a Dockerfile, is listed under each.
            if file["path"] not in paths:
                paths.append(file["path"])
            # A tool can have a descriptor in each of two languages; the first is the primary one.
            if descriptor_path is None and file.get("file_type") == "PRIMARY_DESCRIPTOR":
                descriptor_path = file["path"]
                language = _TRS_DESCRIPTOR_TYPES.get(type_)
    if descriptor_path is not None:
        # The descriptor leads, so that no limit can cut it.
        paths.remove(descriptor_path)
        paths.insert(0, descriptor_path)
    name = payload.get("name")
    values: dict[str, Any] = {
        "id": f"{trs_id}:{name}" if name else None,
        "entry_id": trs_id,
        "name": name,
        "reference": payload.get("reference"),
        "language": language,
        "descriptor_path": descriptor_path,
        "file_paths": paths if file_limit is None else paths[:file_limit],
        "is_valid": payload.get("valid"),
        "is_verified": payload.get("verified"),
        "is_frozen": payload.get("frozen"),
        "doi": _version_doi(payload),
        "created_at": _timestamp(payload.get("dbCreateDate")),
        "updated_at": _timestamp(payload.get("last_modified") or payload.get("dbUpdateDate")),
        "url": _version_url(trs_id, name, settings),
    }
    return Version.model_validate(values)


def _version_doi(payload: dict[str, Any]) -> str | None:
    """Return the version's DOI, preferring the one its owner minted, as Dockstore does."""
    dois = payload.get("dois")
    if isinstance(dois, dict):
        for initiator in ("USER", "GITHUB", "DOCKSTORE"):
            doi = dois.get(initiator)
            if isinstance(doi, dict) and doi.get("name"):
                return str(doi["name"])
    return None


def _version_url(trs_id: str, name: Any, settings: Settings) -> str | None:
    """Build the address of the version's page, the entry's page with the version name behind a colon."""
    prefix, path = _split_trs_id(trs_id)
    if not name or prefix not in _SITE_PATHS:
        return None
    return f"{settings.dockstore_url}/{_SITE_PATHS[prefix]}/{path}:{name}"


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


def _versions(versions: Any, trs_id: str | None) -> list[VersionSummary] | None:
    """Summarize each of an entry's versions, skipping any without a name to identify it by."""
    if not isinstance(versions, list) or trs_id is None:
        return None
    return [
        VersionSummary(
            id=f"{trs_id}:{version['name']}",
            name=version.get("name"),
            reference_type=_reference_type(version.get("referenceType")),
            updated_at=_timestamp(version.get("last_modified") or version.get("dbUpdateDate")),
        )
        for version in versions
        if isinstance(version, dict) and isinstance(version.get("name"), str) and version["name"]
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


def _trs_id(payload: dict[str, Any]) -> str | None:
    """Return an entry's TRS identifier, or make one from its path behind its type's prefix."""
    trs_id = payload.get("trsId")
    if isinstance(trs_id, str) and trs_id:
        return trs_id
    path = _first_of(payload, "full_workflow_path", "tool_path")
    if not path:
        return None
    metadata = payload.get("entryTypeMetadata")
    prefix = metadata.get("trsPrefix") if isinstance(metadata, dict) else None
    return f"{prefix or ''}{path}"


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
