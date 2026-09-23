# Dockstore MCP Server

[![license](https://img.shields.io/hexpm/l/plug.svg?maxAge=2592000)](LICENSE)

An [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server that exposes
[Dockstore](https://dockstore.org) to AI assistants and other MCP clients.

Dockstore is a registry of bioinformatics tools and workflows described in CWL, WDL,
Nextflow, and Galaxy. It serves them through the GA4GH [Tool Registry Service
(TRS)](https://ga4gh.github.io/tool-registry-service-schemas/) API and through Dockstore's
own API. This server is a standalone process that sits in front of those APIs and speaks
MCP, so it is deployed alongside the Dockstore webservice rather than inside it.

It is built on [FastMCP](https://gofastmcp.com) 4 and ships as a container image.

> **Status: scaffold.** `hello` and the GA4GH TRS tools (`get_trs_info` through
> `get_tool_containerfile`) have working bodies; the other four Dockstore tools are
> declared — names, arguments, and response shapes — but each one raises
> `NotImplementedError` until it is wired up to the Dockstore API.

## Requirements

- Python 3.11 or newer (the container image uses 3.13)
- Docker, if you want to build or run the image

## Quick start

```bash
make install          # create .venv and install the package plus dev dependencies
make test             # run the test suite
make run              # start the server on stdio
```

Or without `make`:

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/dockstore-mcp --help
```

## Running the server

The server supports the two standard MCP transports.

**stdio** — the client launches the server as a subprocess. This is how desktop MCP
clients normally work:

```bash
dockstore-mcp --transport stdio
```

**HTTP** — the server runs as a long-lived service, which is how it is deployed:

```bash
dockstore-mcp --transport http --host 0.0.0.0 --port 8000
```

Over HTTP it serves two paths:

| Path      | Purpose                                             |
| --------- | --------------------------------------------------- |
| `/mcp`    | The MCP endpoint (streamable HTTP)                  |
| `/health` | Liveness probe, returns `{"status": "ok", ...}`     |

### With a container

```bash
docker build -t dockstore/dockstore-mcp:local .
docker run --rm -p 8000:8000 \
  -e DOCKSTORE_MCP_DOCKSTORE_URL=https://qa.dockstore.org \
  dockstore/dockstore-mcp:local
```

The image defaults to the HTTP transport on port 8000 and runs as a non-root user. A
`docker-compose.yml` is included for local runs against a Dockstore webservice on your
machine:

```bash
DOCKSTORE_URL=http://host.docker.internal:8080 docker compose up --build
```

### With an MCP client

To use a local checkout from a client that launches servers itself, point it at the
entry point. For example, in Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dockstore": {
      "command": "/path/to/mcp/.venv/bin/dockstore-mcp",
      "env": { "DOCKSTORE_MCP_DOCKSTORE_URL": "https://dockstore.org" }
    }
  }
}
```

To connect to a running HTTP deployment instead, point the client at
`https://<host>/mcp`. In Claude Code that is:

```bash
claude mcp add --transport http dockstore https://<host>/mcp
```

## Configuration

Every option can be set with a `DOCKSTORE_MCP_`-prefixed environment variable, in a
`.env` file (see [.env.example](.env.example)), or with a command line flag. Flags win
over the environment.

| Variable                      | Flag              | Default                 | Meaning                                          |
| ----------------------------- | ----------------- | ----------------------- | ------------------------------------------------ |
| `DOCKSTORE_MCP_TRANSPORT`     | `--transport`     | `stdio`                 | `stdio` or `http`                                |
| `DOCKSTORE_MCP_HOST`          | `--host`          | `127.0.0.1`             | Interface to bind, HTTP only                     |
| `DOCKSTORE_MCP_PORT`          | `--port`          | `8000`                  | Port to bind, HTTP only                          |
| `DOCKSTORE_MCP_PATH`          | `--path`          | `/mcp`                  | Path the MCP endpoint is served from             |
| `DOCKSTORE_MCP_LOG_LEVEL`     | `--log-level`     | `INFO`                  | Logging verbosity                                |
| `DOCKSTORE_MCP_DOCKSTORE_URL` | `--dockstore-url` | `https://dockstore.org` | Dockstore instance whose APIs are exposed        |
| `DOCKSTORE_MCP_GIT_REF`       |                   | package version         | Version in the `dockstore-mcp/<ref>` User-Agent  |

The container image overrides the first four so that it listens on `0.0.0.0:8000` out of
the box, and sets `DOCKSTORE_MCP_GIT_REF` from its `GIT_REF` build argument, which the
release workflow and `make docker-build` fill in with the git tag or ref being built. It
also sets a few `FASTMCP_*` variables so that a deployed server logs plainly and does not
check PyPI for updates on startup; see the [FastMCP settings](https://gofastmcp.com) for
the full list.

## Tools

| Tool                          | Description                                                                          |
| ----------------------------- | ------------------------------------------------------------------------------------ |
| `hello`                       | Greets the caller and reports the Dockstore instance and server version. No I/O.     |
| `get_trs_info`                | Describes this instance's GA4GH TRS API: identifiers, version, and operator.         |
| `list_tool_classes`           | Lists the tool classes (e.g. `Workflow`) this instance's TRS API sorts entries into. |
| `list_tools`                  | Lists one page of every tool and workflow the TRS API serves, with the total count.  |
| `search_tools`                | Finds TRS tools by name, organization, author, class, descriptor language, etc.      |
| `get_tool`                    | Retrieves one TRS tool by id, including all of its versions.                         |
| `list_tool_versions`          | Lists every version of one TRS tool.                                                 |
| `get_tool_version`            | Retrieves one version of a TRS tool: authors, images, descriptor languages.          |
| `get_tool_descriptor`         | Fetches the primary descriptor (CWL, WDL, etc., or a notebook) of a version.         |
| `get_tool_descriptor_by_path` | Fetches one of a version's files by its relative path.                               |
| `get_tool_files`              | Lists every file of a version, without content.                                      |
| `get_tool_tests`              | Fetches a version's test parameter files.                                            |
| `get_tool_containerfile`      | Fetches the containerfile (e.g. Dockerfile) that builds a version's image.           |
| `search_entries`              | Searches entries by keyword and facet, the equivalent of the site's Search page.     |
| `get_entry`                   | Retrieves the requested fields of one entry.                                         |
| `get_version`                 | Retrieves the requested fields of one version of an entry.                           |
| `get_file`                    | Retrieves the requested fields of one file belonging to a version.                   |

The TRS tools, from `get_trs_info` to `get_tool_containerfile`, call Dockstore's GA4GH
TRS V2 API directly. They form a chain: `list_tools` and `search_tools` yield tool ids, a
tool yields version names, and a version's `get_tool_files` yields the paths that
`get_tool_descriptor_by_path` takes. Pass `summary` to `list_tools` or `search_tools` to get
each tool's id, languages, and version names without its full README and version details.

The last four are scaffolding and are not implemented yet. They are a chain too:
`search_entries` yields entry identifiers, an entry yields version identifiers, and a
version yields file paths. Each lookup takes a list of fields so that a caller can ask
for a name and a date without also pulling down a README or a whole descriptor.

## Layout

```
src/dockstore_mcp/
├── __main__.py      command line entry point (`dockstore-mcp`)
├── casing.py        camelCase JSON -> snake_case models, for API-backed tools
├── config.py        settings, read from the environment
├── models.py        entry, version, and file types shared by the tools
├── server.py        server construction, /health route
└── tools/
    ├── __init__.py  registers every tool group
    ├── entries.py   get_entry, get_version, get_file
    ├── hello.py     the hello tool
    ├── search.py    search_entries
    └── trs.py       get_trs_info, list_tool_classes, and the other GA4GH TRS tools
tests/               pytest suite, using FastMCP's in-memory client
Dockerfile           two-stage build of the deployable image
```

### Adding a tool

Add a module under `src/dockstore_mcp/tools/` that exposes
`register(mcp: FastMCP, settings: Settings) -> None`, and call it from
`register_all` in `tools/__init__.py`. Group related tools in one module.

Keep tool docstrings written for the model that will read them: say what the tool
returns and when to reach for it. Note that FastMCP can also generate tools directly
from an OpenAPI specification (`FastMCP.from_openapi`), which may be the right way to
cover large parts of the Dockstore API.

## Development

```bash
make check      # lint, type check, and test
make format     # apply ruff formatting and safe fixes
```

Tests use FastMCP's in-memory client, so they exercise real tool dispatch without
starting a server or opening a socket.

### Installing git-secrets

Dockstore uses [git-secrets](https://github.com/awslabs/git-secrets) to help make sure
that keys and private data stay out of the source tree. For information on installing it
on your platform check <https://github.com/awslabs/git-secrets#id6>.

If you're on mac with homebrew use `brew install git-secrets`.

With git-secrets on your path, `make install` (or `make git-hooks`) registers the AWS
patterns and points `core.hookspath` at [git-hooks/](git-hooks), so the scan runs on
every commit. CI runs `git secrets --scan` over the whole repository as well. False
positives can be listed in [.gitallowed](.gitallowed).

## License

Apache License 2.0. See [LICENSE](LICENSE).
