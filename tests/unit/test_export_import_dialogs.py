import json

from ffpolicy.core.paths import ExportTarget
from ffpolicy.gui.export_target_dialog import ExportTargetDialog
from ffpolicy.gui.import_source_dialog import ImportSourceDialog


def test_export_dialog_defaults_to_system_linux(qtbot):
    dialog = ExportTargetDialog()
    qtbot.addWidget(dialog)

    assert dialog.selected_target is ExportTarget.SYSTEM_LINUX
    assert "/etc/firefox/policies/policies.json" in dialog._resolved_path_label.text()
    assert dialog._elevate_checkbox.isEnabled()


def test_export_dialog_custom_target_shows_placeholder_until_path_entered(qtbot):
    dialog = ExportTargetDialog()
    qtbot.addWidget(dialog)

    index = dialog._target_combo.findData(ExportTarget.CUSTOM)
    dialog._target_combo.setCurrentIndex(index)

    assert dialog._custom_path_edit.isEnabled()
    assert not dialog._elevate_checkbox.isEnabled()
    assert dialog.custom_path is None

    dialog._custom_path_edit.setText("/tmp/some-dir")

    assert dialog.custom_path == "/tmp/some-dir"
    assert "/tmp/some-dir" in dialog._resolved_path_label.text()


def test_export_dialog_distribution_target_does_not_require_privileges(qtbot):
    dialog = ExportTargetDialog()
    qtbot.addWidget(dialog)

    index = dialog._target_combo.findData(ExportTarget.DISTRIBUTION)
    dialog._target_combo.setCurrentIndex(index)

    assert not dialog._elevate_checkbox.isEnabled()
    assert not dialog.elevate


def test_import_dialog_with_no_detected_locations_disables_combo(qtbot, monkeypatch):
    monkeypatch.setattr(
        "ffpolicy.gui.import_source_dialog.discover_installed_policies", lambda: []
    )
    dialog = ImportSourceDialog()
    qtbot.addWidget(dialog)

    assert not dialog._found_combo.isEnabled()
    assert dialog.selected_path is None


def test_import_dialog_prefers_typed_path_over_detected(qtbot, monkeypatch, tmp_path):
    found_path = tmp_path / "found-policies.json"
    found_path.write_text(json.dumps({"policies": {}}))
    monkeypatch.setattr(
        "ffpolicy.gui.import_source_dialog.discover_installed_policies",
        lambda: [(ExportTarget.SYSTEM_LINUX, found_path)],
    )
    dialog = ImportSourceDialog()
    qtbot.addWidget(dialog)

    assert dialog.selected_path == str(found_path)

    dialog._path_edit.setText("/explicit/path/policies.json")

    assert dialog.selected_path == "/explicit/path/policies.json"
