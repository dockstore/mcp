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
"""Tool registration.

Each module in this package exposes a ``register(mcp, settings)`` function that
adds one cohesive group of tools to the server.  Add new modules here as the
Dockstore surface area grows (TRS lookups, workflow search, and so on).
"""

from fastmcp import FastMCP

from dockstore_mcp.config import Settings
from dockstore_mcp.tools import entries, hello, search

__all__ = ["register_all"]


def register_all(mcp: FastMCP, settings: Settings) -> None:
    """Register every tool this server provides."""
    hello.register(mcp, settings)
    search.register(mcp, settings)
    entries.register(mcp, settings)
