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

> **Status: early.** `hello`, `search_entries`, and `get_entry` work. `get_version`
> and `get_file` are declared — names, arguments, and response shapes — but each one
> raises `NotImplementedError` until it is wired up to the Dockstore API.

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

The container image overrides the first four so that it listens on `0.0.0.0:8000` out of
the box. It also sets a few `FASTMCP_*` variables so that a deployed server logs plainly
and does not check PyPI for updates on startup; see the
[FastMCP settings](https://gofastmcp.com) for the full list.

## Tools

| Tool             | Description                                                                      |
| ---------------- | -------------------------------------------------------------------------------- |
| `hello`          | Greets the caller and reports the Dockstore instance and server version. No I/O.  |
| `search_entries` | Searches entries by keyword and facet, the equivalent of the site's Search page.  |
| `get_entry`      | Retrieves one entry, with its versions and description limited by default.       |
| `get_version`    | Retrieves the requested fields of one version of an entry.                        |
| `get_file`       | Retrieves the requested fields of one file belonging to a version.                |

`get_version` and `get_file` are scaffolding and are not implemented yet. The four
form a chain: `search_entries` yields entry identifiers, an entry yields
its versions, and a version yields file paths. `get_entry` returns at most
`version_limit` versions (10 by default), in the order Dockstore ranks them (the default
version first), and at most `description_limit` characters of the description (5,000 by
default); setting either limit to null returns them in full. The other two lookups
take a list of fields so that a caller can ask for a name and a date without also
pulling down a whole descriptor.

`search_entries` sends an Elasticsearch query to Dockstore's TRS extension,
`POST /api/ga4gh/v2/extended/tools/entry/_search`, which searches the same index as the
site's Search page. Keywords are ranked with the Search page's weights. The entry
type, descriptor language, author, and EDAM facets (subject area, operation, and
input and output data and formats) are filters. Keywords, author, and EDAM facets are
written in Lucene query syntax and sent as `query_string` queries. Results can be sorted by relevance
(with keywords, the square of the Elasticsearch score times the natural log of 1.05 plus the entry's
indexed `relevance`),
name, stars, or last update, and a call returns up to 100 of them (ten by default)
along with the total number that matched. Each result carries the entry's categories and
EDAM facets as the index files them, so they cost no extra request. Services are not indexed, so they cannot be
searched for.

`get_entry` takes the numeric identifier Dockstore gives an entry and reads it from
the webservice, trying the workflow endpoint first and the tool endpoint second, since
only tools are served by the latter. It then fetches the categories the entry is
filed under, from which it derives the entry's EDAM facets.

## Layout

```
src/dockstore_mcp/
├── __main__.py      command line entry point (`dockstore-mcp`)
├── api.py           HTTP client for the Dockstore webservice
├── config.py        settings, read from the environment
├── models.py        entry, version, and file types shared by the tools
├── server.py        server construction, /health route
└── tools/
    ├── __init__.py  registers every tool group
    ├── entries.py   get_entry, get_version, get_file
    ├── hello.py     the hello tool
    └── search.py    search_entries
tests/               pytest suite, using FastMCP's in-memory client
Dockerfile           two-stage build of the deployable image
```

### Adding a tool

Add a module under `src/dockstore_mcp/tools/` that exposes
`register(mcp: FastMCP, settings: Settings, api: DockstoreApi) -> None`, and call it
from `register_all` in `tools/__init__.py`. Group related tools in one module. The
`api` argument is the shared HTTP client; reach Dockstore through it rather than
opening a connection of your own, so that calls reuse the connection pool and the
server can close it on shutdown.

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
starting a server or opening a socket. Tools that call Dockstore are pointed at
`tests/fake_dockstore.py`, which answers from trimmed copies of real payloads and
records what it was asked, so a test can show that a field nobody wanted cost nothing.

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
