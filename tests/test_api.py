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
"""Tests for how the Dockstore client manages its connections."""

from typing import Any

import httpx2
import pytest
from fastmcp import Client

from dockstore_mcp.api import DockstoreApi
from fake_dockstore import FakeDockstore
from test_tools import WORKFLOW_ID


@pytest.fixture
def pools(api: DockstoreApi, monkeypatch: pytest.MonkeyPatch) -> list[httpx2.AsyncClient]:
    """Every connection pool ``api`` opens, in order."""
    opened: list[httpx2.AsyncClient] = []
    new_client = api._new_client

    def spy() -> httpx2.AsyncClient:
        opened.append(new_client())
        return opened[-1]

    monkeypatch.setattr(api, "_new_client", spy)
    return opened


async def test_each_tool_call_connects_afresh_over_one_pool(
    client: Client[Any], dockstore: FakeDockstore, pools: list[httpx2.AsyncClient]
) -> None:
    async with client:
        await client.call_tool("get_entry", {"entry_id": WORKFLOW_ID})
        assert len(dockstore.requests) > 1
        assert len(pools) == 1
        await client.call_tool("get_entry", {"entry_id": WORKFLOW_ID})
    assert len(pools) == 2
    assert all(pool.is_closed for pool in pools)


async def test_a_tool_call_that_needs_no_request_never_contacts_dockstore(
    client: Client[Any], dockstore: FakeDockstore
) -> None:
    async with client:
        await client.call_tool("get_trs_info", {"local_only": True})
    assert dockstore.requests == []


async def test_a_request_outside_a_tool_call_gets_a_pool_of_its_own(
    api: DockstoreApi, pools: list[httpx2.AsyncClient]
) -> None:
    await api.get_list("/entries/16247/categories")
    await api.get_list("/entries/16247/categories")
    assert len(pools) == 2
    assert all(pool.is_closed for pool in pools)


async def test_a_nested_connection_reuses_the_outer_pool(api: DockstoreApi, pools: list[httpx2.AsyncClient]) -> None:
    async with api.connection():
        async with api.connection():
            await api.get_list("/entries/16247/categories")
        await api.get_list("/entries/16247/categories")
    assert len(pools) == 1
