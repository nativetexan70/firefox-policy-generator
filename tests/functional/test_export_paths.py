import pytest

from ffpolicy.core.errors import ExportError
from ffpolicy.core.generator import export_policies_json
from ffpolicy.core.paths import ExportTarget, resolve_export_path
from ffpolicy.models.policy_document import PolicyDocument


def test_resolve_system_linux_target():
    path = resolve_export_path(ExportTarget.SYSTEM_LINUX)
    assert str(path) == "/etc/firefox/policies/policies.json"


def test_resolve_distribution_target():
    path = resolve_export_path(ExportTarget.DISTRIBUTION)
    assert str(path) == "distribution/policies.json"


def test_resolve_custom_target_with_directory(tmp_path):
    path = resolve_export_path(ExportTarget.CUSTOM, tmp_path)
    assert path == tmp_path / "policies.json"


def test_resolve_custom_target_with_explicit_file(tmp_path):
    explicit = tmp_path / "my-policies.json"
    path = resolve_export_path(ExportTarget.CUSTOM, explicit)
    assert path == explicit


def test_resolve_custom_target_requires_path():
    with pytest.raises(ValueError):
        resolve_export_path(ExportTarget.CUSTOM, None)


def test_export_to_resolved_custom_path_creates_parents(tmp_path):
    target_root = tmp_path / "fake-fs-root" / "custom"
    document = PolicyDocument(values={"DisableTelemetry": True})

    resolved = resolve_export_path(ExportTarget.CUSTOM, target_root)
    written = export_policies_json(document, resolved)

    assert written == target_root / "policies.json"
    assert written.exists()


def test_export_overwrite_guard_then_explicit_overwrite(tmp_path):
    document = PolicyDocument(values={"DisableTelemetry": True})
    target = tmp_path / "policies.json"

    export_policies_json(document, target)
    with pytest.raises(ExportError):
        export_policies_json(document, target)

    document2 = PolicyDocument(values={"DisableTelemetry": False})
    export_policies_json(document2, target, overwrite=True)
    assert '"DisableTelemetry": false' in target.read_text()


def test_export_os_error_is_wrapped(tmp_path):
    # A regular file where a directory is expected forces mkdir() to fail
    # with an OSError even when running as root (which bypasses permission bits).
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    document = PolicyDocument(values={"DisableTelemetry": True})

    with pytest.raises(ExportError):
        export_policies_json(document, blocker / "nested" / "policies.json")
