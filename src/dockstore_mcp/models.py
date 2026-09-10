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
"""Types shared by the Dockstore tools.

The enum members below are the vocabulary the model sees in the tool schemas, so
they are named for what a caller would say rather than for Dockstore's internal
spelling.  Where the two differ, the value is the wire form the API expects.

TODO: confirm every wire value against the Dockstore API before the tools are
wired up to it; the search facets in particular are not all spelled the way the
webservice's own enums are.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

__all__ = [
    "DescriptorLanguage",
    "Entry",
    "EntryField",
    "EntrySummary",
    "EntryType",
    "File",
    "FileField",
    "SortBy",
    "SortOrder",
    "Version",
    "VersionField",
]


class EntryType(StrEnum):
    """The kinds of thing Dockstore registers."""

    TOOL = "tool"
    WORKFLOW = "workflow"
    NOTEBOOK = "notebook"
    SERVICE = "service"
    APPTOOL = "apptool"


class DescriptorLanguage(StrEnum):
    """The languages an entry's descriptor can be written in."""

    CWL = "CWL"
    WDL = "WDL"
    NEXTFLOW = "NFL"
    GALAXY = "gxformat2"
    SNAKEMAKE = "SMK"
    JUPYTER = "jupyter"


class SortBy(StrEnum):
    """What to order search results by."""

    RELEVANCE = "relevance"
    NAME = "name"
    STARS = "stars"
    CREATED = "created"
    UPDATED = "updated"


class SortOrder(StrEnum):
    """Which direction to order search results in."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class EntrySummary(BaseModel):
    """The handful of fields that identify an entry in a list of search results."""

    id: str = Field(description="Dockstore identifier for the entry; pass this to get_entry.")
    entry_type: EntryType = Field(description="Which kind of entry this is.")
    descriptor_type: DescriptorLanguage | None = Field(
        default=None, description="Language the entry's descriptor is written in."
    )
    name: str = Field(description="Display name of the entry.")
    path: str = Field(description="Full Dockstore path, for example 'github.com/org/repo/name'.")
    topic: str | None = Field(default=None, description="One-line description of what the entry does.")
    created_at: datetime | None = Field(default=None, description="When the entry was registered.")
    updated_at: datetime | None = Field(default=None, description="When the entry was last modified.")


class Entry(BaseModel):
    """A Dockstore entry.

    Every field is optional: a response carries only the fields the caller asked
    for, and leaves the rest unset.
    """

    id: str | None = Field(default=None, description="Dockstore identifier for the entry.")
    entry_type: EntryType | None = Field(default=None, description="Which kind of entry this is.")
    descriptor_type: DescriptorLanguage | None = Field(
        default=None, description="Language the entry's descriptor is written in."
    )
    name: str | None = Field(default=None, description="Display name of the entry.")
    organization: str | None = Field(default=None, description="Organization the entry belongs to.")
    path: str | None = Field(default=None, description="Full Dockstore path of the entry.")
    trs_id: str | None = Field(default=None, description="GA4GH TRS identifier, for use against the TRS API.")
    topic: str | None = Field(default=None, description="One-line description of what the entry does.")
    description: str | None = Field(default=None, description="Long description, usually the README.")
    authors: list[str] | None = Field(default=None, description="Authors credited on the entry.")
    labels: list[str] | None = Field(default=None, description="Free-form labels applied to the entry.")
    categories: list[str] | None = Field(default=None, description="Categories the entry has been placed in.")
    subject_areas: list[str] | None = Field(default=None, description="Subject areas the entry works in.")
    operations: list[str] | None = Field(default=None, description="Operations the entry performs.")
    input_formats: list[str] | None = Field(default=None, description="File formats the entry accepts as input.")
    output_formats: list[str] | None = Field(default=None, description="File formats the entry produces as output.")
    registry: str | None = Field(default=None, description="Image or workflow registry hosting the entry.")
    source_control: str | None = Field(default=None, description="Source control provider the descriptor lives in.")
    is_published: bool | None = Field(default=None, description="Whether the entry is publicly visible.")
    is_verified: bool | None = Field(default=None, description="Whether any version has been verified.")
    star_count: int | None = Field(default=None, description="How many users have starred the entry.")
    default_version: str | None = Field(default=None, description="Name of the version served by default.")
    version_ids: list[str] | None = Field(default=None, description="Version identifiers; pass one to get_version.")
    doi: str | None = Field(default=None, description="Concept DOI for the entry as a whole, if there is one.")
    created_at: datetime | None = Field(default=None, description="When the entry was registered.")
    updated_at: datetime | None = Field(default=None, description="When the entry was last modified.")
    url: str | None = Field(default=None, description="Address of the entry's page on Dockstore.")


class Version(BaseModel):
    """One version of a Dockstore entry.

    Every field is optional, for the same reason as on :class:`Entry`.
    """

    id: str | None = Field(default=None, description="Dockstore identifier for the version.")
    entry_id: str | None = Field(default=None, description="Identifier of the entry this version belongs to.")
    name: str | None = Field(default=None, description="Version name, usually a tag or branch.")
    reference: str | None = Field(default=None, description="Source control reference the version was built from.")
    descriptor_type: DescriptorLanguage | None = Field(
        default=None, description="Language this version's descriptor is written in."
    )
    descriptor_path: str | None = Field(default=None, description="Path of the primary descriptor within the version.")
    file_paths: list[str] | None = Field(default=None, description="Paths of the files; pass one to get_file.")
    is_valid: bool | None = Field(default=None, description="Whether Dockstore could parse the descriptor.")
    is_verified: bool | None = Field(default=None, description="Whether the version has been verified.")
    is_frozen: bool | None = Field(default=None, description="Whether the version is a snapshot and cannot change.")
    doi: str | None = Field(default=None, description="DOI minted for the version, if there is one.")
    created_at: datetime | None = Field(default=None, description="When the version was created.")
    updated_at: datetime | None = Field(default=None, description="When the version was last modified.")
    url: str | None = Field(default=None, description="Address of the version's page on Dockstore.")


class File(BaseModel):
    """One file belonging to a version of an entry.

    Every field is optional, for the same reason as on :class:`Entry`.
    """

    path: str | None = Field(default=None, description="Path of the file within the version.")
    absolute_path: str | None = Field(default=None, description="Path of the file within its source repository.")
    file_type: str | None = Field(default=None, description="What the file is, for example a primary descriptor.")
    content: str | None = Field(default=None, description="Contents of the file.")
    checksums: dict[str, str] | None = Field(default=None, description="Checksums of the content, keyed by algorithm.")
    url: str | None = Field(default=None, description="Address the file can be fetched from.")


class EntryField(StrEnum):
    """Fields of an :class:`Entry` that get_entry can return."""

    ID = "id"
    ENTRY_TYPE = "entry_type"
    DESCRIPTOR_TYPE = "descriptor_type"
    NAME = "name"
    ORGANIZATION = "organization"
    PATH = "path"
    TRS_ID = "trs_id"
    TOPIC = "topic"
    DESCRIPTION = "description"
    AUTHORS = "authors"
    LABELS = "labels"
    CATEGORIES = "categories"
    SUBJECT_AREAS = "subject_areas"
    OPERATIONS = "operations"
    INPUT_FORMATS = "input_formats"
    OUTPUT_FORMATS = "output_formats"
    REGISTRY = "registry"
    SOURCE_CONTROL = "source_control"
    IS_PUBLISHED = "is_published"
    IS_VERIFIED = "is_verified"
    STAR_COUNT = "star_count"
    DEFAULT_VERSION = "default_version"
    VERSION_IDS = "version_ids"
    DOI = "doi"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    URL = "url"


class VersionField(StrEnum):
    """Fields of a :class:`Version` that get_version can return."""

    ID = "id"
    ENTRY_ID = "entry_id"
    NAME = "name"
    REFERENCE = "reference"
    DESCRIPTOR_TYPE = "descriptor_type"
    DESCRIPTOR_PATH = "descriptor_path"
    FILE_PATHS = "file_paths"
    IS_VALID = "is_valid"
    IS_VERIFIED = "is_verified"
    IS_FROZEN = "is_frozen"
    DOI = "doi"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    URL = "url"


class FileField(StrEnum):
    """Fields of a :class:`File` that get_file can return."""

    PATH = "path"
    ABSOLUTE_PATH = "absolute_path"
    FILE_TYPE = "file_type"
    CONTENT = "content"
    CHECKSUMS = "checksums"
    URL = "url"
