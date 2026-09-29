.PHONY: help install git-hooks test lint format typecheck check run run-http docker-build docker-run clean

VENV ?= .venv
PY   ?= $(VENV)/bin/python
PIP  ?= $(VENV)/bin/pip
IMAGE ?= dockstore/dockstore-mcp:local
# Reported in the User-Agent the server sends to Dockstore.
GIT_REF ?= $(shell git describe --tags --always 2>/dev/null)

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

$(VENV): ## Create the development virtualenv
	python3 -m venv $(VENV)

install: $(VENV) git-hooks ## Install the package and development dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -e '.[dev]'

git-hooks: ## Register the git-secrets hooks (requires git-secrets)
	bash scripts/install-git-hooks.sh

test: ## Run the test suite
	$(VENV)/bin/pytest

lint: ## Check formatting and lint rules
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .

format: ## Apply formatting and safe lint fixes
	$(VENV)/bin/ruff check --fix .
	$(VENV)/bin/ruff format .

typecheck: ## Run the type checker
	$(VENV)/bin/mypy

check: lint typecheck test ## Everything CI runs

run: ## Run the server over stdio
	DOCKSTORE_MCP_GIT_REF=$(GIT_REF) $(VENV)/bin/dockstore-mcp

run-http: ## Run the server over HTTP on port 8000
	DOCKSTORE_MCP_GIT_REF=$(GIT_REF) $(VENV)/bin/dockstore-mcp --transport http --port 8000

docker-build: ## Build the container image
	docker build --build-arg GIT_REF=$(GIT_REF) -t $(IMAGE) .

docker-run: ## Run the container image on port 8000
	docker run --rm -p 8000:8000 $(IMAGE)

clean: ## Remove build and cache artifacts
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
