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
"""Translating the Dockstore and GA4GH APIs' camelCase JSON into this package's
snake_case models.

Every model in :mod:`dockstore_mcp.models` spells its fields snake_case, like the
rest of the codebase, but the APIs this server calls return camelCase keys. Tool
implementations run a response through :func:`normalize_keys` before handing it to
a model's ``model_validate``, rather than hand-writing a key map per endpoint.
"""

import re
from typing import Any

__all__ = ["camel_to_snake", "normalize_keys"]

#: Matches the position just before each interior capital letter, e.g. the two
#: gaps in 'toolId' -> ['tool', 'Id'].
_WORD_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(key: str) -> str:
    """Convert one camelCase key to snake_case, for example 'toolId' -> 'tool_id'."""
    return _WORD_BOUNDARY.sub("_", key).lower()


def normalize_keys(value: Any) -> Any:
    """Recursively convert every dict key in ``value`` from camelCase to snake_case.

    Walks into nested dicts and lists so a whole API response can be normalized in
    one call before validation, however deeply the objects it describes are nested.
    """
    if isinstance(value, dict):
        return {camel_to_snake(key): normalize_keys(val) for key, val in value.items()}
    if isinstance(value, list):
        return [normalize_keys(item) for item in value]
    return value
