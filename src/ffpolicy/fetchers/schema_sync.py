"""Fetch and parse Mozilla's policy-templates schema into a PolicySchema.

Fallback chain: live fetch -> disk cache -> bundled `resources/schema_backup.json`.
"""

from __future__ import annotations

import importlib.resources
import json
import re
from datetime import UTC, datetime
from typing import Any

import requests
import yaml

from ffpolicy.core.errors import SchemaLoadError
from ffpolicy.fetchers import cache
from ffpolicy.fetchers.base import build_session, get_with_etag
from ffpolicy.models.policy_schema import PolicyDefinition, PolicyField, PolicySchema, ValueType

SCHEMA_URL = "https://raw.githubusercontent.com/mozilla/policy-templates/master/schema.json"
README_URL = "https://raw.githubusercontent.com/mozilla/policy-templates/master/README.md"

_CACHE_NAMESPACE = "schema"
_SCHEMA_CACHE_KEY = "schema.json"
_README_CACHE_KEY = "README.md"

_FIREFOX_VERSION_RE = re.compile(r"Firefox\s+(?:ESR\s+)?(\d+)")
_HEADING_RE = re.compile(r"^##\s+([A-Za-z0-9_]+)\s*$", re.MULTILINE)


def _json_type_to_value_type(prop: dict[str, Any]) -> ValueType:
    if "enum" in prop:
        return ValueType.ENUM
    if prop.get("format") == "uri":
        return ValueType.URL
    json_type: str | None = prop.get("type")
    mapping = {
        "boolean": ValueType.BOOL,
        "string": ValueType.STRING,
        "integer": ValueType.INT,
        "number": ValueType.INT,
        "object": ValueType.OBJECT,
        "array": ValueType.ARRAY,
    }
    return mapping.get(json_type, ValueType.STRING) if json_type else ValueType.STRING


def _build_field(key: str, prop: dict[str, Any], required: set[str] | None = None) -> PolicyField:
    value_type = _json_type_to_value_type(prop)
    children: list[PolicyField] = []

    if value_type is ValueType.OBJECT:
        properties = prop.get("properties", {})
        nested_required = set(prop.get("required", []))
        for child_key, child_prop in properties.items():
            children.append(_build_field(child_key, child_prop, nested_required))
        if "additionalProperties" in prop and isinstance(prop["additionalProperties"], dict):
            children.append(_build_field("*", prop["additionalProperties"]))
    elif value_type is ValueType.ARRAY and isinstance(prop.get("items"), dict):
        children.append(_build_field("[]", prop["items"]))

    return PolicyField(
        key=key,
        type=value_type,
        description=prop.get("description"),
        enum_values=prop.get("enum"),
        default=prop.get("default"),
        required=bool(required and key in required),
        children=children,
    )


def parse_schema_json(schema_json: dict[str, Any]) -> dict[str, PolicyField]:
    """Map each top-level policy name to its parsed field tree."""
    properties = schema_json.get("properties", {})
    return {name: _build_field(name, prop) for name, prop in properties.items()}


def parse_readme_metadata(readme_text: str) -> dict[str, dict[str, Any]]:
    """Best-effort extraction of description + min Firefox version per policy heading."""
    metadata: dict[str, dict[str, Any]] = {}
    headings = list(_HEADING_RE.finditer(readme_text))

    for index, match in enumerate(headings):
        name = match.group(1)
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(readme_text)
        block = readme_text[start:end].strip()

        description = next((line.strip() for line in block.splitlines() if line.strip()), None)
        version_match = _FIREFOX_VERSION_RE.search(block)
        min_version = int(version_match.group(1)) if version_match else None

        metadata[name] = {"description": description, "min_firefox_version": min_version}

    return metadata


def _load_categories() -> dict[str, str]:
    text = importlib.resources.files("ffpolicy.resources").joinpath("categories.yaml").read_text()
    raw = yaml.safe_load(text) or {}
    return {name: category for category, names in raw.items() for name in names}


def merge_policy_schema(
    fields_by_name: dict[str, PolicyField],
    readme_meta: dict[str, dict[str, Any]],
    categories: dict[str, str],
    *,
    source_version: str,
) -> PolicySchema:
    policies: dict[str, PolicyDefinition] = {}
    for name, root_field in fields_by_name.items():
        meta = readme_meta.get(name, {})
        policies[name] = PolicyDefinition(
            name=name,
            category=categories.get(name, "Uncategorized"),
            description=meta.get("description"),
            min_firefox_version=meta.get("min_firefox_version"),
            root_field=root_field,
        )
    return PolicySchema(
        source_version=source_version, fetched_at=datetime.now(UTC), policies=policies
    )


def load_bundled_schema() -> PolicySchema:
    resource = importlib.resources.files("ffpolicy.resources").joinpath("schema_backup.json")
    return PolicySchema.model_validate(json.loads(resource.read_text()))


def sync_schema(session: requests.Session | None = None) -> tuple[PolicySchema, str]:
    """Fetch+parse the live schema, falling back to cache then the bundled copy.

    Returns `(schema, tier)` where tier is one of "live", "cached", "bundled".
    """
    session = session or build_session()

    cached_schema = cache.read_cached(_CACHE_NAMESPACE, _SCHEMA_CACHE_KEY)
    cached_readme = cache.read_cached(_CACHE_NAMESPACE, _README_CACHE_KEY)

    try:
        schema_result = get_with_etag(
            session,
            SCHEMA_URL,
            cached_etag=(cached_schema or {}).get("etag"),
        )
        readme_result = get_with_etag(
            session,
            README_URL,
            cached_etag=(cached_readme or {}).get("etag"),
        )

        if schema_result.not_modified:
            schema_json = (cached_schema or {}).get("data")
        else:
            schema_json = json.loads(schema_result.text) if schema_result.text else None

        readme_text = (
            readme_result.text
            if not readme_result.not_modified
            else (cached_readme or {}).get("data")
        )

        if schema_json is None or readme_text is None:
            raise SchemaLoadError("live fetch returned no usable data")

        if not schema_result.not_modified:
            cache.write_cached(
                _CACHE_NAMESPACE, _SCHEMA_CACHE_KEY, schema_json, etag=schema_result.etag
            )
        if not readme_result.not_modified:
            cache.write_cached(
                _CACHE_NAMESPACE, _README_CACHE_KEY, readme_text, etag=readme_result.etag
            )

        fields = parse_schema_json(schema_json)
        meta = parse_readme_metadata(readme_text)
        schema = merge_policy_schema(
            fields, meta, _load_categories(), source_version=schema_result.etag or "live"
        )
        return schema, "live"

    except (requests.RequestException, SchemaLoadError, json.JSONDecodeError):
        pass

    if cached_schema is not None and cached_readme is not None:
        fields = parse_schema_json(cached_schema["data"])
        meta = parse_readme_metadata(cached_readme["data"])
        schema = merge_policy_schema(
            fields, meta, _load_categories(), source_version="cached"
        )
        return schema, "cached"

    return load_bundled_schema(), "bundled"
