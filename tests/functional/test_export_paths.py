import subprocess
from pathlib import Path

import pytest

from ffpolicy.core.errors import ExportError
from ffpolicy.core.generator import export_policies_json, render_policies_json
from ffpolicy.core.paths import ExportTarget, resolve_export_path, target_requires_privileges
from ffpolicy.models.policy_document import PolicyDocument


def test_resolve_system_linux_target():
    path = resolve_export_path(ExportTarget.SYSTEM_LINUX)
    assert str(path) == "/etc/firefox/policies/policies.json"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (ExportTarget.LINUX_LIB64_DISTRIBUTION, "/usr/lib64/firefox/distribution/policies.json"),
        (ExportTarget.LINUX_LIB_DISTRIBUTION, "/usr/lib/firefox/distribution/policies.json"),
        (ExportTarget.LINUX_FIREFOX_ESR, "/usr/lib/firefox-esr/distribution/policies.json"),
        (ExportTarget.LINUX_OPT_DISTRIBUTION, "/opt/firefox/distribution/policies.json"),
    ],
)
def test_resolve_additional_linux_targets(target, expected):
    assert str(resolve_export_path(target)) == expected


def test_resolve_distribution_target():
    path = resolve_export_path(ExportTarget.DISTRIBUTION)
    assert str(path) == "distribution/policies.json"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (ExportTarget.SYSTEM_LINUX, True),
        (ExportTarget.LINUX_LIB64_DISTRIBUTION, True),
        (ExportTarget.LINUX_LIB_DISTRIBUTION, True),
        (ExportTarget.LINUX_FIREFOX_ESR, True),
        (ExportTarget.LINUX_OPT_DISTRIBUTION, True),
        (ExportTarget.DISTRIBUTION, False),
        (ExportTarget.CUSTOM, False),
    ],
)
def test_target_requires_privileges(target, expected):
    assert target_requires_privileges(target) is expected


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


def test_permission_denied_without_elevation_hints_at_flag(monkeypatch, tmp_path):
    target = tmp_path / "policies.json"
    document = PolicyDocument(values={"DisableTelemetry": True})

    def _deny_write(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "write_text", _deny_write)

    with pytest.raises(ExportError, match="allow_privilege_escalation"):
        export_policies_json(document, target)


def test_permission_denied_with_elevation_invokes_escalation_tool(monkeypatch, tmp_path):
    target = tmp_path / "policies.json"
    document = PolicyDocument(values={"DisableTelemetry": True})

    original_write_text = Path.write_text

    def _deny_first_write(self, *args, **kwargs):
        if self == target:
            raise PermissionError("denied")
        return original_write_text(self, *args, **kwargs)

    calls = []

    def _fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        # Emulate `install -D -m 644 <tmp> <target>` actually placing the file.
        original_write_text(target, Path(cmd[-2]).read_text(), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(Path, "write_text", _deny_first_write)
    monkeypatch.setattr("ffpolicy.core.privilege.shutil.which", lambda tool: "/usr/bin/pkexec")
    monkeypatch.setattr("ffpolicy.core.privilege.subprocess.run", _fake_run)

    written = export_policies_json(document, target, allow_privilege_escalation=True)

    assert written == target
    assert target.read_text() == render_policies_json(document)
    assert calls and calls[0][0] == "pkexec"


def test_no_escalation_tool_available_raises(monkeypatch, tmp_path):
    target = tmp_path / "policies.json"
    document = PolicyDocument(values={"DisableTelemetry": True})

    def _deny_write(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "write_text", _deny_write)
    monkeypatch.setattr("ffpolicy.core.privilege.shutil.which", lambda tool: None)

    with pytest.raises(ExportError, match="neither pkexec nor sudo"):
        export_policies_json(document, target, allow_privilege_escalation=True)
