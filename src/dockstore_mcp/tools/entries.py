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

TODO: this is scaffolding.  Every tool raises ``NotImplementedError`` until it
is wired up to the Dockstore API.
"""

import logging

from fastmcp import FastMCP

from dockstore_mcp.config import Settings
from dockstore_mcp.models import Entry, EntryField, File, FileField, Version, VersionField

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


def register(mcp: FastMCP, settings: Settings) -> None:
    """Add the entry, version, and file lookup tools to ``mcp``."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_entry(entry_id: str, fields: list[EntryField] | None = None) -> Entry:
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
        # TODO: fetch the entry from the Dockstore API and populate the requested fields.
        raise NotImplementedError("get_entry is not implemented yet")

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
