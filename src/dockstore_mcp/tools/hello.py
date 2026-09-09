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
"""A minimal tool, useful as an end-to-end smoke test of a deployment."""

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from dockstore_mcp import __version__
from dockstore_mcp.config import Settings

__all__ = ["Greeting", "register"]


class Greeting(BaseModel):
    """The result of a call to the ``hello`` tool."""

    greeting: str = Field(description="A friendly greeting.")
    dockstore_url: str = Field(description="The Dockstore instance this server is configured to talk to.")
    server_version: str = Field(description="Version of the dockstore-mcp package that answered.")


def register(mcp: FastMCP, settings: Settings) -> None:
    """Add the hello tool to ``mcp``."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def hello(name: str = "world") -> Greeting:
        """Greet someone and report which Dockstore instance this server is attached to.

        Use this to confirm that the Dockstore MCP server is reachable and correctly
        configured. It does not contact Dockstore itself.
        """
        return Greeting(
            greeting=f"Hello, {name}!",
            dockstore_url=settings.dockstore_url,
            server_version=__version__,
        )
