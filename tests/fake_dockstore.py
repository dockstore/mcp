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
descriptor languages, and a tool that only implies where its source lives.
"""

import json
from typing import Any

import httpx2

__all__ = ["CATEGORIES", "SEARCH_HITS", "TOOL", "TOOL_VERSIONS", "WORKFLOW", "WORKFLOW_VERSIONS", "FakeDockstore"]

EDAM = "http://edamontology.org"

#: A published workflow, as ``/workflows/published/{id}`` returns it.
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

#: What ``include=versions`` adds to the workflow above.
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
        "last_modified": 1778686422000,
        "dbUpdateDate": 1778686489697,
    },
]

#: A published tool, as ``/containers/published/{id}`` returns it.  A tool has
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

#: What ``include=versions`` adds to the tool above.
TOOL_VERSIONS: list[dict[str, Any]] = [
    {
        "id": 5011,
        "name": "2.2.0",
        "reference": "2.2.0",
        "referenceType": "BRANCH",
        "verified": True,
        "last_modified": None,
        "dbUpdateDate": 1648762651000,
    }
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

#: What the search endpoint answers with: the workflow and tool above as the
#: index holds them, plus a hit with no path, which cannot be summarized.  Each
#: document's own id is 0; the entry's identifier is the document's ``_id``.
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
                    "entryTypeMetadata": {"type": "WORKFLOW", "sitePath": "workflows"},
                    "descriptorType": "gxformat2",
                    "workflowName": "COVID-19-ARTIC-ILLUMINA",
                    "repository": "sars-cov-2-variant-calling",
                    "full_workflow_path": WORKFLOW["full_workflow_path"],
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
                    "entryTypeMetadata": {"type": "TOOL", "sitePath": "containers"},
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

    @property
    def transport(self) -> httpx2.MockTransport:
        """A transport to hand to :class:`~dockstore_mcp.api.DockstoreApi`."""
        return httpx2.MockTransport(self._handle)

    def search_bodies(self) -> list[Any]:
        """The query of every search made so far."""
        return [json.loads(request.content) for request in self.requests if request.method == "POST"]

    def paths(self) -> list[str]:
        """The path of every request made so far."""
        return [request.url.path for request in self.requests]

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        wants_versions = request.url.params.get("include") == "versions"
        match request.url.path:
            case "/api/workflows/published/16247":
                return self._entry(WORKFLOW, WORKFLOW_VERSIONS, wants_versions)
            case "/api/containers/published/188":
                return self._entry(TOOL, TOOL_VERSIONS, wants_versions)
            case "/api/entries/16247/categories":
                return httpx2.Response(200, json=CATEGORIES)
            case "/api/entries/188/categories":
                return httpx2.Response(200, json=[])
            case "/api/api/ga4gh/v2/extended/tools/entry/_search" if request.method == "POST":
                return httpx2.Response(200, json=self.search_response)
            case _:
                return httpx2.Response(404, json={"code": 404, "message": "Entry not found."})

    @staticmethod
    def _entry(payload: dict[str, Any], versions: list[dict[str, Any]], wants_versions: bool) -> httpx2.Response:
        return httpx2.Response(200, json=payload | {"workflowVersions": versions if wants_versions else None})
