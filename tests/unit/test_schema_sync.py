
import requests
import responses

from ffpolicy.fetchers.schema_sync import (
    README_URL,
    SCHEMA_URL,
    merge_policy_schema,
    parse_readme_metadata,
    parse_schema_json,
    sync_schema,
)
from ffpolicy.models.policy_schema import ValueType

SCHEMA_JSON = {
    "properties": {
        "DisableTelemetry": {"type": "boolean", "description": "Disable telemetry."},
        "Homepage": {
            "type": "object",
            "properties": {
                "URL": {"type": "string", "format": "uri"},
                "Locked": {"type": "boolean"},
            },
            "required": ["URL"],
        },
        "SSLVersionMin": {"type": "string", "enum": ["tls1", "tls1.2", "tls1.3"]},
    }
}

README_TEXT = """
## DisableTelemetry

Disable Telemetry data collection.

Compatibility: Firefox 60 and later.

## Homepage

Configure the default homepage.

Compatibility: Firefox 62 and later.
"""


def test_parse_schema_json_builds_expected_types():
    fields = parse_schema_json(SCHEMA_JSON)

    assert fields["DisableTelemetry"].type is ValueType.BOOL
    assert fields["SSLVersionMin"].type is ValueType.ENUM
    assert fields["SSLVersionMin"].enum_values == ["tls1", "tls1.2", "tls1.3"]

    homepage = fields["Homepage"]
    assert homepage.type is ValueType.OBJECT
    child_keys = {child.key for child in homepage.children}
    assert child_keys == {"URL", "Locked"}
    url_field = next(c for c in homepage.children if c.key == "URL")
    assert url_field.type is ValueType.URL
    assert url_field.required is True


def test_parse_readme_metadata_extracts_description_and_version():
    meta = parse_readme_metadata(README_TEXT)

    assert meta["DisableTelemetry"]["description"] == "Disable Telemetry data collection."
    assert meta["DisableTelemetry"]["min_firefox_version"] == 60
    assert meta["Homepage"]["min_firefox_version"] == 62


def test_merge_policy_schema_applies_categories():
    fields = parse_schema_json(SCHEMA_JSON)
    meta = parse_readme_metadata(README_TEXT)
    categories = {"DisableTelemetry": "Privacy & Network"}

    schema = merge_policy_schema(fields, meta, categories, source_version="test")

    assert schema.policies["DisableTelemetry"].category == "Privacy & Network"
    assert schema.policies["Homepage"].category == "Uncategorized"
    assert schema.policies["DisableTelemetry"].min_firefox_version == 60


@responses.activate
def test_sync_schema_live_tier(monkeypatch, tmp_path):
    monkeypatch.setattr("platformdirs.user_cache_dir", lambda *a, **k: str(tmp_path))

    responses.add(responses.GET, SCHEMA_URL, json=SCHEMA_JSON, status=200, headers={"ETag": "abc"})
    responses.add(responses.GET, README_URL, body=README_TEXT, status=200, headers={"ETag": "def"})

    schema, tier = sync_schema()

    assert tier == "live"
    assert "DisableTelemetry" in schema.policies
    assert schema.policies["DisableTelemetry"].min_firefox_version == 60


@responses.activate
def test_sync_schema_falls_back_to_bundled_on_network_error():
    responses.add(responses.GET, SCHEMA_URL, body=requests.exceptions.ConnectionError("boom"))
    responses.add(responses.GET, README_URL, body=requests.exceptions.ConnectionError("boom"))

    schema, tier = sync_schema()

    assert tier == "bundled"
    assert "ExtensionSettings" in schema.policies
