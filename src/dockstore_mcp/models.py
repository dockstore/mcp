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
    "Checksum",
    "DescriptorLanguage",
    "Entry",
    "EntrySummary",
    "EntryType",
    "File",
    "FileSummary",
    "FileWrapper",
    "ImageData",
    "PageOfTools",
    "ReferenceType",
    "ServiceOrganization",
    "ServiceType",
    "SortBy",
    "SortOrder",
    "Tool",
    "ToolClass",
    "ToolFile",
    "ToolSummary",
    "ToolVersion",
    "ToolVersionSummary",
    "ToolVersionWithFiles",
    "ToolWithPageOfVersions",
    "TrsDescriptorType",
    "TrsInfo",
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


class FileSummary(BaseModel):
    """The handful of fields that identify one of a version's files."""

    path: str = Field(description="Path of the file within the version; pass this to get_file.")
    file_type: str | None = Field(default=None, description="What the file is, for example a primary descriptor.")


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
    reference_type: ReferenceType | None = Field(
        default=None, description="Whether the version was built from a tag, a branch, or a commit."
    )
    authors: list[str] | None = Field(default=None, description="Authors credited on the version.")
    language: DescriptorLanguage | None = Field(
        default=None, description="Language this version's descriptor is written in."
    )
    descriptor_path: str | None = Field(default=None, description="Path of the primary descriptor within the version.")
    files: list[FileSummary] | None = Field(
        default=None,
        description="The version's files, the primary descriptor first and no more than get_version's file_limit; "
        "pass a file's path to get_file.",
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


class ServiceType(BaseModel):
    """Which GA4GH API a service implements, and at what version."""

    group: str = Field(description="Namespace in reverse domain name format, for example 'org.ga4gh'.")
    artifact: str = Field(description="Name of the API or GA4GH specification implemented, for example 'trs'.")
    version: str = Field(description="Version of the API or specification implemented.")


class ServiceOrganization(BaseModel):
    """The organization operating a GA4GH service."""

    name: str = Field(description="Name of the organization responsible for the service.")
    url: str = Field(description="URL of the organization's website.")


class TrsInfo(BaseModel):
    """The Dockstore instance this server talks to and, unless only local details were asked for, its TRS service-info.

    Only ``dockstore_url`` and ``server_version`` are filled in when ``get_trs_info`` is
    asked not to contact Dockstore.
    """

    dockstore_url: str = Field(description="The Dockstore instance this server is configured to talk to.")
    server_version: str = Field(
        description="Git tag or ref the answering server was built from, else its package version."
    )
    id: str | None = Field(
        default=None, description="Unique identifier of this service, in reverse domain name notation."
    )
    name: str | None = Field(default=None, description="Human-readable name of this service.")
    type: ServiceType | None = Field(
        default=None, description="Which GA4GH API this service implements, and at what version."
    )
    organization: ServiceOrganization | None = Field(default=None, description="Organization operating this service.")
    version: str | None = Field(default=None, description="Version of the service software.")
    description: str | None = Field(default=None, description="Human-readable description of the service.")
    contact_url: str | None = Field(default=None, description="Contact URL or mailto link for the service.")
    documentation_url: str | None = Field(default=None, description="URL of the service's documentation.")
    environment: str | None = Field(
        default=None, description="Deployment environment, for example 'prod' or 'staging'."
    )
    created_at: datetime | None = Field(default=None, description="When the service was first deployed.")
    updated_at: datetime | None = Field(default=None, description="When the service was last updated.")
    tool_classes: list["ToolClass"] = Field(
        default_factory=list,
        description="Every tool class (e.g. 'Workflow') the service sorts entries into; list_tools filters by these.",
    )


class ToolClass(BaseModel):
    """A GA4GH TRS tool class: a category of entry, such as 'Workflow' or 'CommandLineTool'."""

    id: str | None = Field(default=None, description="Unique identifier for the class.")
    name: str | None = Field(default=None, description="Short, friendly name for the class.")
    description: str | None = Field(default=None, description="Longer explanation of what this class is.")


class TrsDescriptorType(StrEnum):
    """The descriptor languages the GA4GH TRS API addresses files by, spelled as its URLs expect."""

    CWL = "CWL"
    WDL = "WDL"
    NEXTFLOW = "NFL"
    GALAXY = "GALAXY"
    SNAKEMAKE = "SMK"
    JUPYTER = "JUPYTER"
    SERVICE = "SERVICE"


class Checksum(BaseModel):
    """A checksum of a file or container image."""

    checksum: str | None = Field(default=None, description="The hex-encoded checksum value.")
    type: str | None = Field(default=None, description="Hash algorithm used, for example 'sha-256'.")


class ImageData(BaseModel):
    """A container image a TRS tool version runs in."""

    registry_host: str | None = Field(default=None, description="Registry hosting the image, e.g. 'quay.io'.")
    image_name: str | None = Field(default=None, description="Name of the image, including its registry and tag.")
    size: int | None = Field(default=None, description="Size of the image in bytes.")
    updated: str | None = Field(default=None, description="When the image was last updated.")
    checksum: list[Checksum] | None = Field(default=None, description="Checksums of the image.")
    image_type: str | None = Field(default=None, description="Container technology, for example 'Docker'.")


class ToolVersion(BaseModel):
    """One version of a GA4GH TRS tool, for example a Git branch or tag."""

    id: str | None = Field(default=None, description="TRS identifier of this version, '<tool id>:<version name>'.")
    name: str | None = Field(default=None, description="Version name; pass this as version_id to the version tools.")
    url: str | None = Field(default=None, description="TRS API URL of this version.")
    author: list[str] | None = Field(default=None, description="Authors of this version.")
    is_production: bool | None = Field(default=None, description="Whether the version is marked production-ready.")
    images: list[ImageData] | None = Field(default=None, description="Container images this version runs in.")
    descriptor_type: list[str] | None = Field(
        default=None, description="Descriptor languages this version is available in, for example ['CWL']."
    )
    descriptor_type_version: dict[str, list[str]] | None = Field(
        default=None, description="Language versions used, keyed by descriptor type, e.g. {'WDL': ['1.0']}."
    )
    containerfile: bool | None = Field(default=None, description="Whether a containerfile (e.g. Dockerfile) exists.")
    meta_version: str | None = Field(default=None, description="Revision of this version's metadata.")
    verified: bool | None = Field(default=None, description="Whether this version has been verified.")
    verified_source: list[str] | None = Field(default=None, description="Who or what verified this version.")
    signed: bool | None = Field(default=None, description="Whether this version is signed.")
    included_apps: list[str] | None = Field(default=None, description="Apps bundled with this version.")


class ToolVersionSummary(BaseModel):
    """The few fields that pick out a TRS tool version in a list, without its images or authors."""

    name: str | None = Field(default=None, description="Version name; pass this as version_id to the version tools.")
    meta_version: str | None = Field(default=None, description="Revision of this version's metadata.")
    is_production: bool | None = Field(default=None, description="Whether the version is marked production-ready.")


class Tool(BaseModel):
    """A GA4GH TRS tool: a Dockstore tool, workflow, or other entry as the TRS API describes it."""

    id: str | None = Field(default=None, description="TRS identifier of the tool; pass this as tool_id.")
    url: str | None = Field(default=None, description="TRS API URL of the tool.")
    aliases: list[str] | None = Field(default=None, description="Other identifiers the tool is known by.")
    organization: str | None = Field(default=None, description="Organization that published the tool.")
    name: str | None = Field(default=None, description="Name of the tool.")
    toolclass: ToolClass | None = Field(default=None, description="Category of the tool, e.g. 'Workflow'.")
    description: str | None = Field(default=None, description="Description of the tool, usually its README.")
    meta_version: str | None = Field(default=None, description="Revision of this tool's metadata.")
    has_checker: bool | None = Field(default=None, description="Whether the tool has a checker workflow.")
    checker_url: str | None = Field(default=None, description="TRS URL of the checker workflow, if any.")
    # Parsed from the TRS API, versions are always in full: every ToolVersion field is
    # optional, so left_to_right always picks it. Only get_tool(summary=True) swaps in
    # summaries.
    versions: list[ToolVersion] | list[ToolVersionSummary] | None = Field(
        default=None,
        union_mode="left_to_right",
        description="Every version of the tool, in full or (if summarized) just its name and status.",
    )


class ToolWithPageOfVersions(Tool):
    """A GA4GH TRS tool with one page of its versions, as get_tool returns it."""

    versions: list[ToolVersion] | list[ToolVersionSummary] | None = Field(
        default=None,
        union_mode="left_to_right",
        description="One page of the tool's versions, in full or (if summarized) just their names and status.",
    )
    version_offset: int = Field(description="Which page of versions this is, counting from 0.")
    version_limit: int = Field(description="Most versions a page holds.")
    next_version_offset: int | None = Field(
        default=None, description="Offset of the next page of versions; unset when this is the last page."
    )


class ToolSummary(BaseModel):
    """The handful of fields that identify a TRS tool in a list, without its README or version details."""

    id: str | None = Field(default=None, description="TRS identifier of the tool; pass this as tool_id.")
    name: str | None = Field(default=None, description="Name of the tool.")
    organization: str | None = Field(default=None, description="Organization that published the tool.")
    tool_class: str | None = Field(default=None, description="Category of the tool, e.g. 'Workflow'.")
    descriptor_types: list[str] = Field(
        default_factory=list, description="Every descriptor language any of its versions is available in."
    )
    version_names: list[str] = Field(
        default_factory=list,
        description=(
            "Names of up to 10 versions, production-ready ones first; pass one as version_id to the version tools. "
            "Use get_tool for the rest."
        ),
    )
    version_count: int = Field(default=0, description="How many versions the tool has in all.")
    versions_truncated: bool = Field(
        default=False, description="Whether version_names leaves some versions out; see version_count."
    )
    description: str | None = Field(default=None, description="The start of the tool's description, shortened.")


class PageOfTools(BaseModel):
    """One page of TRS tools, with enough context to fetch the rest."""

    tools: list[Tool] | list[ToolSummary] = Field(
        description="The tools on this page: in full, or as summaries if they were asked for."
    )
    offset: int = Field(description="Which page this is, counting from 0.")
    limit: int = Field(description="Most tools a page holds.")
    total: int | None = Field(
        default=None, description="How many tools there are across every page, if Dockstore reported it."
    )
    next_offset: int | None = Field(
        default=None, description="Offset of the next page; unset when this is the last page."
    )


class FileWrapper(BaseModel):
    """The content of one file from a TRS tool version: a descriptor, test parameter file, or containerfile."""

    content: str | None = Field(default=None, description="The file's full text.")
    checksum: list[Checksum] | None = Field(default=None, description="Checksums of the file.")
    url: str | None = Field(default=None, description="Where the raw file can be fetched from.")


class ToolFile(BaseModel):
    """One entry in the file listing of a TRS tool version."""

    path: str | None = Field(
        default=None,
        description="Path relative to the primary descriptor; pass this to get_tool_descriptor_by_path.",
    )
    file_type: str | None = Field(
        default=None,
        description="One of TEST_FILE, PRIMARY_DESCRIPTOR, SECONDARY_DESCRIPTOR, CONTAINERFILE, or OTHER.",
    )
    checksum: Checksum | None = Field(default=None, description="Checksum of the file.")


class ToolVersionWithFiles(ToolVersion):
    """One version of a GA4GH TRS tool, optionally with its file listing."""

    # Dockstore only fills this in here: in a tool's list of versions, it is always empty.
    description: str | None = Field(default=None, description="Description of this version, if it has its own.")
    files: list[ToolFile] | None = Field(
        default=None, description="Every file of this version in the requested descriptor language, if asked for."
    )
    files_error: str | None = Field(
        default=None, description="Why the file listing could not be fetched, if it was asked for and failed."
    )
