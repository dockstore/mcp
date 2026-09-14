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
"""Command line entry point: ``dockstore-mcp`` (or ``python -m dockstore_mcp``)."""

import argparse
import logging
import sys
from collections.abc import Sequence

from dockstore_mcp import __version__
from dockstore_mcp.config import Settings, get_settings
from dockstore_mcp.server import create_server

__all__ = ["main"]


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dockstore-mcp",
        description="Run the Dockstore MCP server. Every option also has a DOCKSTORE_MCP_* environment variable.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        help="'stdio' for a locally launched client, 'http' when running as a service.",
    )
    parser.add_argument("--host", help="Interface to bind when serving over HTTP.")
    parser.add_argument("--port", type=int, help="Port to bind when serving over HTTP.")
    parser.add_argument("--path", help="HTTP path the MCP endpoint is served from.")
    parser.add_argument("--dockstore-url", help="Base URL of the Dockstore instance to expose.")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def _settings_from(args: argparse.Namespace) -> Settings:
    """Layer command line arguments on top of the environment-derived settings."""
    overrides = {key: value for key, value in vars(args).items() if value is not None}
    if not overrides:
        return get_settings()
    # pydantic-settings gives explicit arguments precedence over the environment.
    return Settings(**overrides)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the server until it is interrupted."""
    settings = _settings_from(_parse_args(argv))

    # stdout belongs to the MCP protocol under the stdio transport, so log to stderr.
    logging.basicConfig(
        level=settings.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    server = create_server(settings)
    if settings.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(
            transport="http",
            host=settings.host,
            port=settings.port,
            path=settings.path,
            log_level=settings.log_level,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
