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

# ---- build ----------------------------------------------------------------
FROM python:3.13-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

# ---- runtime --------------------------------------------------------------
FROM python:3.13-slim-bookworm

LABEL org.opencontainers.image.title="dockstore-mcp" \
      org.opencontainers.image.description="Model Context Protocol server for Dockstore" \
      org.opencontainers.image.url="https://dockstore.org" \
      org.opencontainers.image.source="https://github.com/dockstore/mcp" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.vendor="OICR"

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin dockstore

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FASTMCP_SHOW_SERVER_BANNER=false \
    FASTMCP_CHECK_FOR_UPDATES=off \
    FASTMCP_ENABLE_RICH_LOGGING=false \
    DOCKSTORE_MCP_TRANSPORT=http \
    DOCKSTORE_MCP_HOST=0.0.0.0 \
    DOCKSTORE_MCP_PORT=8000 \
    DOCKSTORE_MCP_PATH=/mcp \
    DOCKSTORE_MCP_DOCKSTORE_URL=https://dockstore.org

USER dockstore
WORKDIR /home/dockstore
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('DOCKSTORE_MCP_PORT', '8000') + '/health').read()"]

ENTRYPOINT ["dockstore-mcp"]
