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
"""A stand-in for the Dockstore webservice.

The payloads below are trimmed copies of what dockstore.org answers with, kept
down to the keys the tools read plus a few they should ignore.  They are the
awkward cases on purpose: a workflow that spells things one way and a tool that
spells the same things another, an author with no name, a tool with two
descriptor languages, a tool that only implies where its source lives, and a tool
version whose CWL descriptor path names a file that is not there.
"""

import json
from typing import Any

import httpx2

__all__ = [
    "CATEGORIES",
    "SEARCH_HITS",
    "TOOL",
    "TOOL_SOURCE_FILES",
    "TOOL_VERSIONS",
    "WORKFLOW",
    "WORKFLOW_SOURCE_FILES",
    "WORKFLOW_VERSIONS",
    "FakeDockstore",
]

EDAM = "http://edamontology.org"

#: A published workflow, as ``/workflows/path/workflow/{path}/published`` returns it.
WORKFLOW: dict[str, Any] = {
    "id": 16247,
    "type": "BioWorkflow",
    "entryType": "WORKFLOW",
    "entryTypeMetadata": {"sitePath": "workflows", "term": "workflow", "trsPrefix": "#workflow/"},
    "descriptorType": "gxformat2",
    "workflowName": "COVID-19-ARTIC-ILLUMINA",
    "repository": "sars-cov-2-variant-calling",
    "organization": "iwc-workflows",
    "sourceControl": "github.com",
    "gitUrl": "git@github.com:iwc-workflows/sars-cov-2-variant-calling.git",
    "full_workflow_path": "github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA",
    "trsId": "#workflow/github.com/iwc-workflows/sars-cov-2-variant-calling/COVID-19-ARTIC-ILLUMINA",
    "topic": "Variant calling from SARS-CoV-2 paired-end Illumina ARTIC data.",
    "description": "# COVID-19: variation analysis on ARTIC PE data\n\nA long README.\n",
    "authors": [{"name": "IWC", "email": None}, {"name": None, "email": "nobody@example.org"}],
    "labels": [{"id": 12, "value": "covid-19"}],
    "is_published": True,
    "starredUsers": [{"id": 24}, {"id": 19741}],
    "defaultVersion": "v0.5.2",
    "doiSelection": "DOCKSTORE",
    "conceptDoi": None,
    "conceptDois": {"DOCKSTORE": {"id": 5384, "name": "10.5281/zenodo.15685746", "type": "CONCEPT"}},
    "dbCreateDate": 1614068067928,
    "lastUpdated": 1614068067457,
    "last_modified_date": 1778686422000,
    "dbUpdateDate": 1778686489697,
    "workflowVersions": None,
}

#: The workflow's versions, as ``/workflows/published/{id}/workflowVersions`` pages them
#: and ``/workflows/published/{id}/workflowVersions/{versionId}`` returns each one.
WORKFLOW_VERSIONS: list[dict[str, Any]] = [
    {
        "id": 117122,
        "name": "v0.5.1",
        "reference": "v0.5.1",
        "referenceType": "TAG",
        "verified": False,
        "last_modified": 1747584000000,
        "dbUpdateDate": 1747670405000,
    },
    {
        "id": 117123,
        "name": "v0.5.2",
        "reference": "v0.5.2",
        "referenceType": "TAG",
        "verified": True,
        "valid": True,
        "frozen": True,
        "hidden": False,
        "workflow_path": "/pe-artic-variation.ga",
        "dois": {
            "DOCKSTORE": {"id": 5385, "name": "10.5281/zenodo.15685747", "type": "VERSION", "initiator": "DOCKSTORE"},
            "USER": {"id": 5386, "name": "10.5281/zenodo.99999999", "type": "VERSION", "initiator": "USER"},
        },
        "last_modified": 1778686422000,
        "dbUpdateDate": 1778686489697,
    },
]

#: The files of the workflow's default version, as ``/workflows/{id}/workflowVersions/{versionId}/sourcefiles``
#: returns them: sorted by path, which puts the descriptor last.
WORKFLOW_SOURCE_FILES: list[dict[str, Any]] = [
    {"id": 1, "type": "DOCKSTORE_YML", "path": "/.dockstore.yml", "absolutePath": "/.dockstore.yml", "content": "x"},
    {"id": 2, "type": "GXFORMAT2_TEST_FILE", "path": "/pe-artic-variation-tests.yml", "content": "x"},
    {"id": 3, "type": "DOCKSTORE_GXFORMAT2", "path": "/pe-artic-variation.ga", "content": "x"},
]

#: A published tool, as ``/containers/path/tool/{path}/published`` returns it.  A tool has
#: no ``sourceControl``, no ``organization``, and a list of descriptor types.
TOOL: dict[str, Any] = {
    "id": 188,
    "entryType": "TOOL",
    "entryTypeMetadata": {"sitePath": "containers", "term": "tool", "trsPrefix": ""},
    "descriptorType": ["CWL", "WDL"],
    "name": "pcawg-dkfz-workflow",
    "toolname": None,
    "namespace": "pancancer",
    "registry": "QUAY_IO",
    "registry_string": "quay.io",
    "gitUrl": "git@github.com:ICGC-TCGA-PanCancer/dkfz_dockered_workflows.git",
    "path": "quay.io/pancancer/pcawg-dkfz-workflow",
    "tool_path": "quay.io/pancancer/pcawg-dkfz-workflow",
    "trsId": "quay.io/pancancer/pcawg-dkfz-workflow",
    "topic": "The container housing the Roddy-based component provided by DKFZ.",
    "description": "PCAWG DKFZ variant calling workflow.\n",
    "authors": [{"name": "Brian O'Connor", "email": "briandoconnor@gmail.com"}],
    "labels": [{"id": 981, "value": "pcawg"}, {"id": 31, "value": "variant-caller"}],
    "is_published": True,
    "starredUsers": [],
    "defaultVersion": "2.2.0",
    "doiSelection": "USER",
    "conceptDoi": None,
    "conceptDois": {},
    "dbCreateDate": 1571188929777,
    "lastUpdated": 1571188929777,
    "last_modified_date": None,
    "dbUpdateDate": 1648762651404,
    "workflowVersions": None,
}

#: What ``include=versions`` adds to the tool above, and what
#: ``/containers/published/{id}/tags/{tagId}`` returns for each tag.
TOOL_VERSIONS: list[dict[str, Any]] = [
    {
        "id": 5011,
        "name": "2.2.0",
        "reference": "2.2.0",
        "referenceType": "BRANCH",
        "verified": True,
        "valid": True,
        "frozen": False,
        "hidden": False,
        "cwl_path": "/Dockstore.cwl",
        "wdl_path": "/Dockstore.wdl",
        "dockerfile_path": "/Dockerfile",
        "dois": {},
        "last_modified": None,
        "dbUpdateDate": 1648762651000,
    }
]

#: The files of the tool's tag, as ``/containers/{id}/tags/{tagId}/sourcefiles`` returns
#: them.  There is no CWL descriptor, although the tag names a path for one.
TOOL_SOURCE_FILES: list[dict[str, Any]] = [
    {"id": 11, "type": "DOCKERFILE", "path": "/Dockerfile", "content": "FROM ubuntu"},
    {"id": 12, "type": "DOCKSTORE_WDL", "path": "/Dockstore.wdl", "content": "workflow x {}"},
]

#: The categories the workflow above has been filed under: one a person
#: curated, and six from Dockstore's automatic categorization.
CATEGORIES: list[dict[str, Any]] = [
    {"id": 110, "name": "COVID-19", "displayName": "COVID-19", "metadata": None},
    {
        "id": 575,
        "name": "operation-variant-calling",
        "displayName": "Variant calling",
        "metadata": {"source": f"{EDAM}/operation_3227"},
    },
    {"id": 576, "name": "topic-virology", "displayName": "Virology", "metadata": {"source": f"{EDAM}/topic_0781"}},
    {
        "id": 577,
        "name": "input-format-fastq-sanger",
        "displayName": "FASTQ-sanger",
        "metadata": {"source": f"{EDAM}/format_1932"},
    },
    {
        "id": 578,
        "name": "input-data-short-read-sequencing-data",
        "displayName": "Short-read sequencing data",
        "metadata": {"source": "ai"},
    },
    {"id": 579, "name": "output-format-vcf", "displayName": "VCF", "metadata": {"source": f"{EDAM}/format_3016"}},
    {
        "id": 580,
        "name": "output-data-variant-call-data",
        "displayName": "Variant call data",
        "metadata": {"source": "ai"},
    },
]

#: The workflow's categories as the index holds them, filed by facet.
_INDEXED_CATEGORIES: dict[str, Any] = {
    "categories": [CATEGORIES[0]],
    "topic": [CATEGORIES[2]],
    "operation": [CATEGORIES[1], CATEGORIES[1]],
    "input-format": [CATEGORIES[3]],
    "output-format": [CATEGORIES[5]],
    "input-data": [CATEGORIES[4]],
    "output-data": [CATEGORIES[6]],
}

#: What the search endpoint answers with: the workflow and tool above as the
#: index holds them, plus a hit with no path, which cannot be summarized.  The
#: tool was indexed without its TRS identifier.
SEARCH_HITS: dict[str, Any] = {
    "took": 3,
    "timed_out": False,
    "hits": {
        "total": {"value": 42, "relation": "eq"},
        "max_score": 12.5,
        "hits": [
            {
                "_index": "workflows",
                "_id": "16247",
                "_score": 12.5,
                "_source": {
                    "entryTypeMetadata": {"type": "WORKFLOW", "trsPrefix": "#workflow/"},
                    "descriptorType": "gxformat2",
                    "workflowName": "COVID-19-ARTIC-ILLUMINA",
                    "repository": "sars-cov-2-variant-calling",
                    "full_workflow_path": WORKFLOW["full_workflow_path"],
                    "trsId": WORKFLOW["trsId"],
                    **_INDEXED_CATEGORIES,
                    "topicAutomatic": WORKFLOW["topic"],
                    "dbCreateDate": WORKFLOW["dbCreateDate"],
                    "last_modified_date": WORKFLOW["last_modified_date"],
                },
            },
            {
                "_index": "tools",
                "_id": "188",
                "_score": 3.0,
                "_source": {
                    "entryTypeMetadata": {"type": "TOOL", "trsPrefix": ""},
                    "descriptorType": ["CWL", "WDL"],
                    "name": "pcawg-dkfz-workflow",
                    "toolname": None,
                    "tool_path": TOOL["tool_path"],
                    "topicAutomatic": TOOL["topic"],
                    "dbCreateDate": TOOL["dbCreateDate"],
                    "last_modified_date": None,
                    "dbUpdateDate": TOOL["dbUpdateDate"],
                },
            },
            {"_index": "tools", "_id": "999", "_score": 1.0, "_source": {"entryTypeMetadata": {"type": "APPTOOL"}}},
        ],
    },
}


class FakeDockstore:
    """Answers the handful of Dockstore endpoints the tools call.

    It records every request, so a test can show that a field nobody asked for
    cost nothing to leave out.
    """

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        #: What the search endpoint answers with, which a test can replace.
        self.search_response: Any = SEARCH_HITS
        self.search_status = 200
        #: What the workflow endpoint answers with, which a test can replace.
        self.workflow: dict[str, Any] = WORKFLOW
        self.workflow_versions: list[dict[str, Any]] = WORKFLOW_VERSIONS
        self.workflow_source_files: list[dict[str, Any]] = WORKFLOW_SOURCE_FILES

    @property
    def transport(self) -> httpx2.MockTransport:
        """A transport to hand to :class:`~dockstore_mcp.api.DockstoreApi`."""
        return httpx2.MockTransport(self._handle)

    def search_bodies(self) -> list[Any]:
        """The query of every search made so far."""
        return [json.loads(request.content) for request in self.requests if request.method == "POST"]

    def paths(self) -> list[str]:
        """The path of every request made so far, still percent-encoded."""
        return [_raw_path(request) for request in self.requests]

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        wants_versions = request.url.params.get("include") == "versions"
        # The workflows endpoint looks only among bioworkflows unless told otherwise.
        subclass = request.url.params.get("subclass", "BIOWORKFLOW")
        match _raw_path(request):
            case path if path == _path_endpoint("workflows/path/workflow", WORKFLOW) and subclass == "BIOWORKFLOW":
                return self._entry(self.workflow, self.workflow_versions, wants_versions)
            case "/api/workflows/published/16247/workflowVersions":
                offset = int(request.url.params.get("offset", 0))
                limit = int(request.url.params.get("limit", 100))
                return httpx2.Response(200, json=self.workflow_versions[offset : offset + limit])
            case path if path == _path_endpoint("containers/path/tool", TOOL):
                return self._entry(TOOL, TOOL_VERSIONS, wants_versions)
            case "/api/entries/mapTrsVersionId":
                return self._map_trs_version_id(request.url.params.get("trsVersionId", ""))
            case path if path.startswith("/api/workflows/published/16247/workflowVersions/"):
                return self._version(self.workflow_versions, path)
            case "/api/workflows/16247/workflowVersions/117123/sourcefiles":
                return httpx2.Response(200, json=self.workflow_source_files)
            case path if path.startswith("/api/containers/published/188/tags/"):
                return self._version(TOOL_VERSIONS, path)
            case "/api/containers/188/tags/5011/sourcefiles":
                return httpx2.Response(200, json=TOOL_SOURCE_FILES)
            case "/api/entries/16247/categories":
                return httpx2.Response(200, json=CATEGORIES)
            case "/api/entries/188/categories":
                return httpx2.Response(200, json=[])
            case "/api/api/ga4gh/v2/extended/tools/entry/_search" if request.method == "POST":
                return httpx2.Response(self.search_status, json=self.search_response)
            case _:
                return httpx2.Response(404, json={"code": 404, "message": "Entry not found."})

    def _map_trs_version_id(self, trs_version_id: str) -> httpx2.Response:
        trs_id, _, name = trs_version_id.rpartition(":")
        for entry, versions in ((self.workflow, self.workflow_versions), (TOOL, TOOL_VERSIONS)):
            version = next((version for version in versions if version["name"] == name), None)
            if entry["trsId"] == trs_id and version is not None:
                return httpx2.Response(200, json={"entryId": entry["id"], "versionId": version["id"]})
        return httpx2.Response(404, json={"code": 404, "message": "No published entry or version corresponds."})

    @staticmethod
    def _version(versions: list[dict[str, Any]], path: str) -> httpx2.Response:
        version_id = path.rpartition("/")[2]
        version = next((version for version in versions if str(version["id"]) == version_id), None)
        if version is None:
            return httpx2.Response(404, json={"code": 404, "message": "Version not found."})
        return httpx2.Response(200, json=version)

    @staticmethod
    def _entry(payload: dict[str, Any], versions: list[dict[str, Any]], wants_versions: bool) -> httpx2.Response:
        return httpx2.Response(200, json=payload | {"workflowVersions": versions if wants_versions else None})


def _raw_path(request: httpx2.Request) -> str:
    return request.url.raw_path.decode().partition("?")[0]


def _path_endpoint(endpoint: str, payload: dict[str, Any]) -> str:
    """Where Dockstore serves ``payload`` by its path, which goes in the request as one segment."""
    path = payload.get("full_workflow_path") or payload["tool_path"]
    return f"/api/{endpoint}/{path.replace('/', '%2F')}/published"
