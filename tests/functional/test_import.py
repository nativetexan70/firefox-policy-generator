import json

import pytest

from ffpolicy.core.errors import ExportError
from ffpolicy.core.importer import import_policies_json
from ffpolicy.core.paths import ExportTarget, discover_installed_policies, resolve_export_path
from ffpolicy.models.policy_document import PolicyDocument


def test_import_policies_json_wrapper_shape(tmp_path):
    source = tmp_path / "policies.json"
    source.write_text(json.dumps({"policies": {"DisableTelemetry": True}}))

    document = import_policies_json(source)

    assert document.values == {"DisableTelemetry": True}


def test_import_policies_json_bare_mapping_shape(tmp_path):
    source = tmp_path / "policies.json"
    source.write_text(json.dumps({"DisableTelemetry": True}))

    document = import_policies_json(source)

    assert document.values == {"DisableTelemetry": True}


def test_import_missing_file_raises_export_error(tmp_path):
    with pytest.raises(ExportError, match="failed to read"):
        import_policies_json(tmp_path / "missing.json")


def test_import_invalid_json_raises_export_error(tmp_path):
    source = tmp_path / "policies.json"
    source.write_text("not json")

    with pytest.raises(ExportError, match="not valid JSON"):
        import_policies_json(source)


def test_import_non_object_top_level_raises(tmp_path):
    source = tmp_path / "policies.json"
    source.write_text(json.dumps([1, 2, 3]))

    with pytest.raises(ExportError, match="top-level JSON object"):
        import_policies_json(source)


def test_import_non_object_policies_value_raises(tmp_path):
    source = tmp_path / "policies.json"
    source.write_text(json.dumps({"policies": "nope"}))

    with pytest.raises(ExportError, match='"policies" value must be a JSON object'):
        import_policies_json(source)


def test_discover_finds_existing_custom_resolved_path(monkeypatch, tmp_path):
    # Route every standard target's resolution to distinct tmp_path files so
    # discovery can be exercised without touching real system directories.
    fake_paths = {target: tmp_path / f"{target.value}.json" for target in ExportTarget}

    def _fake_resolve(target, custom_path=None):
        if target is ExportTarget.CUSTOM:
            return resolve_export_path(target, custom_path)
        return fake_paths[target]

    monkeypatch.setattr("ffpolicy.core.paths.resolve_export_path", _fake_resolve)

    existing_target = ExportTarget.LINUX_LIB64_DISTRIBUTION
    fake_paths[existing_target].write_text("{}")

    found = discover_installed_policies()

    assert found == [(existing_target, fake_paths[existing_target])]


def test_discover_returns_empty_when_nothing_installed(monkeypatch, tmp_path):
    fake_paths = {target: tmp_path / f"{target.value}.json" for target in ExportTarget}

    def _fake_resolve(target, custom_path=None):
        if target is ExportTarget.CUSTOM:
            return resolve_export_path(target, custom_path)
        return fake_paths[target]

    monkeypatch.setattr("ffpolicy.core.paths.resolve_export_path", _fake_resolve)

    assert discover_installed_policies() == []


def test_document_roundtrip_through_generator(tmp_path):
    source = tmp_path / "policies.json"
    source.write_text(json.dumps({"policies": {"DisableTelemetry": True}}))

    document = import_policies_json(source)

    assert isinstance(document, PolicyDocument)
    assert document.to_policies_json() == {"policies": {"DisableTelemetry": True}}
