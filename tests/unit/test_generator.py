import pytest

from ffpolicy.core.errors import ExportError
from ffpolicy.core.generator import export_policies_json, render_policies_json
from ffpolicy.models.policy_document import PolicyDocument


def test_render_policies_json_sorts_keys_deterministically():
    doc = PolicyDocument(values={"Zeta": True, "Alpha": False})
    text = render_policies_json(doc)
    assert text.index('"Alpha"') < text.index('"Zeta"')
    assert text == render_policies_json(PolicyDocument(values={"Alpha": False, "Zeta": True}))


def test_export_policies_json_writes_file(tmp_path):
    doc = PolicyDocument(values={"DisableTelemetry": True})
    target = tmp_path / "nested" / "policies.json"

    result = export_policies_json(doc, target)

    assert result == target
    assert '"DisableTelemetry": true' in target.read_text()


def test_export_policies_json_refuses_overwrite_by_default(tmp_path):
    doc = PolicyDocument(values={"DisableTelemetry": True})
    target = tmp_path / "policies.json"
    target.write_text("existing")

    with pytest.raises(ExportError):
        export_policies_json(doc, target)


def test_export_policies_json_overwrites_when_requested(tmp_path):
    doc = PolicyDocument(values={"DisableTelemetry": True})
    target = tmp_path / "policies.json"
    target.write_text("existing")

    export_policies_json(doc, target, overwrite=True)

    assert '"DisableTelemetry": true' in target.read_text()
