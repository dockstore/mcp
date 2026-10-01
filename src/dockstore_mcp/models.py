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
"""Types shared by the Dockstore tools.

The enum members below are the vocabulary the model sees in the tool schemas, so
they are named for what a caller would say rather than for Dockstore's internal
spelling.  Where the two differ, the value is the wire form the API expects.

TODO: confirm every wire value against the Dockstore API before the remaining
tools are wired up to it.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

__all__ = [
    "DescriptorLanguage",
    "Entry",
    "EntrySummary",
    "EntryType",
    "File",
    "ReferenceType",
    "SortBy",
    "SortOrder",
    "Version",
    "VersionSummary",
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
    GALAXY = "galaxy"
    SNAKEMAKE = "SMK"
    JUPYTER = "jupyter"

    @classmethod
    def from_dockstore(cls, value: str) -> "DescriptorLanguage":
        """Look up a language by the name Dockstore knows it by."""
        return cls.GALAXY if value == "gxformat2" else cls(value)

    @property
    def dockstore_value(self) -> str:
        """The name Dockstore knows this language by."""
        return "gxformat2" if self is DescriptorLanguage.GALAXY else self.value


class ReferenceType(StrEnum):
    """What kind of source control reference a version was built from."""

    TAG = "tag"
    BRANCH = "branch"
    COMMIT = "commit"


class SortBy(StrEnum):
    """What to order search results by."""

    RELEVANCE = "relevance"
    NAME = "name"
    STARS = "stars"
    UPDATED = "updated"


class SortOrder(StrEnum):
    """Which direction to order search results in."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class EntrySummary(BaseModel):
    """The handful of fields that identify an entry in a list of search results."""

    id: str = Field(description="GA4GH TRS identifier for the entry; pass this to get_entry.")
    type: EntryType = Field(description="Which kind of entry this is.")
    language: DescriptorLanguage | None = Field(
        default=None, description="Language the entry's descriptor is written in."
    )
    name: str = Field(description="Display name of the entry.")
    topic: str | None = Field(default=None, description="One-line description of what the entry does.")
    categories: list[str] = Field(default_factory=list, description="Categories the entry has been placed in.")
    subject_areas: list[str] = Field(default_factory=list, description="Subject areas the entry works in.")
    operations: list[str] = Field(default_factory=list, description="Operations the entry performs.")
    input_formats: list[str] = Field(default_factory=list, description="File formats the entry accepts as input.")
    output_formats: list[str] = Field(default_factory=list, description="File formats the entry produces as output.")
    input_data: list[str] = Field(default_factory=list, description="Kinds of data the entry accepts as input.")
    output_data: list[str] = Field(default_factory=list, description="Kinds of data the entry produces as output.")
    updated_at: datetime | None = Field(default=None, description="When the entry was last modified.")


class VersionSummary(BaseModel):
    """The handful of fields that identify one of an entry's versions."""

    id: str = Field(
        description="GA4GH TRS identifier for the version: the entry's TRS identifier and the version name, "
        "joined by a colon; pass this to get_version."
    )
    name: str | None = Field(default=None, description="Version name, usually a tag or branch.")
    reference_type: ReferenceType | None = Field(
        default=None, description="Whether the version was built from a tag, a branch, or a commit."
    )
    updated_at: datetime | None = Field(default=None, description="When the version was last modified.")


class Entry(BaseModel):
    """A Dockstore entry.

    Every field is optional, since Dockstore does not fill in every one for every
    kind of entry.
    """

    id: str | None = Field(default=None, description="GA4GH TRS identifier for the entry.")
    type: EntryType | None = Field(default=None, description="Which kind of entry this is.")
    language: DescriptorLanguage | None = Field(
        default=None, description="Language the entry's descriptor is written in."
    )
    name: str | None = Field(default=None, description="Display name of the entry.")
    organization: str | None = Field(default=None, description="Organization the entry belongs to.")
    topic: str | None = Field(default=None, description="One-line description of what the entry does.")
    description: str | None = Field(
        default=None, description="Long description, usually the README; cut short past get_entry's description_limit."
    )
    authors: list[str] | None = Field(default=None, description="Authors credited on the entry.")
    labels: list[str] | None = Field(default=None, description="Free-form labels applied to the entry.")
    categories: list[str] | None = Field(default=None, description="Categories the entry has been placed in.")
    subject_areas: list[str] | None = Field(default=None, description="Subject areas the entry works in.")
    operations: list[str] | None = Field(default=None, description="Operations the entry performs.")
    input_formats: list[str] | None = Field(default=None, description="File formats the entry accepts as input.")
    output_formats: list[str] | None = Field(default=None, description="File formats the entry produces as output.")
    input_data: list[str] | None = Field(default=None, description="Kinds of data the entry accepts as input.")
    output_data: list[str] | None = Field(default=None, description="Kinds of data the entry produces as output.")
    registry: str | None = Field(default=None, description="Image or workflow registry hosting the entry.")
    source_control: str | None = Field(default=None, description="Source control provider the descriptor lives in.")
    is_published: bool | None = Field(default=None, description="Whether the entry is publicly visible.")
    star_count: int | None = Field(default=None, description="How many users have starred the entry.")
    default_version: VersionSummary | None = Field(default=None, description="The version served by default.")
    versions: list[VersionSummary] | None = Field(
        default=None,
        description="The entry's versions, most relevant first and no more than get_entry's version_limit; "
        "pass a version's id to get_version.",
    )
    doi: str | None = Field(default=None, description="Concept DOI for the entry as a whole, if there is one.")
    created_at: datetime | None = Field(default=None, description="When the entry was registered.")
    updated_at: datetime | None = Field(default=None, description="When the entry was last modified.")
    url: str | None = Field(default=None, description="Address of the entry's page on Dockstore.")


class Version(BaseModel):
    """One version of a Dockstore entry.

    Every field is optional, since Dockstore does not fill in every one for every
    kind of entry.
    """

    id: str | None = Field(
        default=None,
        description="GA4GH TRS identifier for the version: the entry's TRS identifier and the version name, "
        "joined by a colon.",
    )
    entry_id: str | None = Field(default=None, description="GA4GH TRS identifier of the entry this version belongs to.")
    name: str | None = Field(default=None, description="Version name, usually a tag or branch.")
    reference: str | None = Field(default=None, description="Source control reference the version was built from.")
    language: DescriptorLanguage | None = Field(
        default=None, description="Language this version's descriptor is written in."
    )
    descriptor_path: str | None = Field(default=None, description="Path of the primary descriptor within the version.")
    file_paths: list[str] | None = Field(
        default=None,
        description="Paths of the files, the primary descriptor first and no more than get_version's file_limit; "
        "pass one to get_file.",
    )
    is_valid: bool | None = Field(default=None, description="Whether Dockstore could parse the descriptor.")
    is_verified: bool | None = Field(default=None, description="Whether the version has been verified.")
    is_frozen: bool | None = Field(default=None, description="Whether the version is a snapshot and cannot change.")
    doi: str | None = Field(default=None, description="DOI minted for the version, if there is one.")
    created_at: datetime | None = Field(default=None, description="When the version was created.")
    updated_at: datetime | None = Field(default=None, description="When the version was last modified.")
    url: str | None = Field(default=None, description="Address of the version's page on Dockstore.")


class File(BaseModel):
    """One file belonging to a version of an entry.

    Every field is optional, since Dockstore does not fill in every one for every
    kind of file.
    """

    path: str | None = Field(default=None, description="Path of the file within the version.")
    absolute_path: str | None = Field(default=None, description="Path of the file within its source repository.")
    file_type: str | None = Field(default=None, description="What the file is, for example a primary descriptor.")
    content: str | None = Field(
        default=None, description="Contents of the file; cut short past get_file's content_limit."
    )
    checksums: dict[str, str] | None = Field(default=None, description="Checksums of the content, keyed by algorithm.")
    url: str | None = Field(default=None, description="Address the file can be fetched from.")
