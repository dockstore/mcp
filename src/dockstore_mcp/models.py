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

TODO: confirm every wire value against the Dockstore API before the tools are
wired up to it; the search facets in particular are not all spelled the way the
webservice's own enums are.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

__all__ = [
    "Checksum",
    "DescriptorLanguage",
    "Entry",
    "EntryField",
    "EntrySummary",
    "EntryType",
    "File",
    "FileField",
    "FileWrapper",
    "ImageData",
    "ServiceOrganization",
    "ServiceType",
    "SortBy",
    "SortOrder",
    "Tool",
    "ToolClass",
    "ToolFile",
    "ToolPage",
    "ToolVersion",
    "TrsDescriptorType",
    "TrsInfo",
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
    """GA4GH TRS service-info: metadata describing a Dockstore instance's TRS API."""

    id: str = Field(description="Unique identifier of this service, in reverse domain name notation.")
    name: str = Field(description="Human-readable name of this service.")
    type: ServiceType = Field(description="Which GA4GH API this service implements, and at what version.")
    organization: ServiceOrganization = Field(description="Organization operating this service.")
    version: str = Field(description="Version of the service software.")
    description: str | None = Field(default=None, description="Human-readable description of the service.")
    contact_url: str | None = Field(default=None, description="Contact URL or mailto link for the service.")
    documentation_url: str | None = Field(default=None, description="URL of the service's documentation.")
    environment: str | None = Field(
        default=None, description="Deployment environment, for example 'prod' or 'staging'."
    )
    created_at: datetime | None = Field(default=None, description="When the service was first deployed.")
    updated_at: datetime | None = Field(default=None, description="When the service was last updated.")


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
    versions: list[ToolVersion] | None = Field(default=None, description="Every version of the tool.")


class ToolPage(BaseModel):
    """One page of TRS tools, with enough context to fetch the rest."""

    tools: list[Tool] = Field(description="The tools on this page, each with all of its versions.")
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
