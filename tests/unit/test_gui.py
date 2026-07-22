from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from ffpolicy.core.presets import load_preset
from ffpolicy.fetchers.schema_sync import load_bundled_schema
from ffpolicy.gui.extension_manager import ExtensionManager
from ffpolicy.gui.main_window import MainWindow
from ffpolicy.gui.preset_details import PresetDetailsDialog
from ffpolicy.models.extension import InstallationMode


@pytest.fixture
def schema():
    return load_bundled_schema()


@pytest.fixture
def main_window(qtbot, schema):
    window = MainWindow(schema=schema, schema_tier="bundled")
    qtbot.addWidget(window)
    return window


def test_selecting_category_populates_form(qtbot, main_window):
    main_window._on_policy_selected("DisableTelemetry")
    assert main_window._editor_layout.count() == 1


def test_toggling_field_updates_live_json_preview(qtbot, main_window):
    main_window._on_policy_selected("DisableTelemetry")
    form = main_window._editor_layout.itemAt(0).widget()

    form._editor.set_value(True)
    form._editor.valueChanged.emit(True)

    with qtbot.waitSignal(main_window._debounce.timeout, timeout=1000):
        pass

    assert '"DisableTelemetry": true' in main_window.preview.toPlainText()
    assert main_window.document.values.get("DisableTelemetry") is True


def test_selecting_extension_settings_shows_extension_manager(qtbot, main_window):
    main_window._on_policy_selected("ExtensionSettings")
    widget = main_window._editor_layout.itemAt(0).widget()
    assert isinstance(widget, ExtensionManager)


def test_adding_extension_writes_extension_settings_entry(qtbot, main_window):
    main_window._on_policy_selected("ExtensionSettings")
    manager = main_window._editor_layout.itemAt(0).widget()

    manager.add_manual(
        "uBlock0@raymondhill.net",
        InstallationMode.FORCE_INSTALLED,
        "https://example.com/ublock.xpi",
    )

    with qtbot.waitSignal(main_window._debounce.timeout, timeout=1000):
        pass

    settings = main_window.document.values["ExtensionSettings"]
    assert settings["uBlock0@raymondhill.net"]["installation_mode"] == "force_installed"
    assert settings["uBlock0@raymondhill.net"]["install_url"] == "https://example.com/ublock.xpi"


def test_manual_add_row_works_when_search_is_unavailable(qtbot, main_window):
    """Covers the fallback path promised by the "enter GUID manually below"
    message shown when AMO search fails (rate-limited, blocked, offline).
    """
    main_window._on_policy_selected("ExtensionSettings")
    manager = main_window._editor_layout.itemAt(0).widget()

    manager._manual_guid.setText("ext@example.com")
    manager._manual_mode.setCurrentText(InstallationMode.BLOCKED.value)
    manager._on_manual_add()

    assert manager.get_value() == {"ext@example.com": {"installation_mode": "blocked"}}
    # fields reset so another extension can be entered right away
    assert manager._manual_guid.text() == ""


def test_manual_add_row_ignores_empty_guid(qtbot, main_window):
    main_window._on_policy_selected("ExtensionSettings")
    manager = main_window._editor_layout.itemAt(0).widget()

    manager._manual_guid.setText("   ")
    manager._on_manual_add()

    assert manager.get_value() == {}


def test_apply_preset_updates_document_and_preview(qtbot, main_window):
    preset = load_preset("disa_stig__mac_1_classified")

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok):
            main_window._on_apply_preset(preset)

    assert main_window.document.values["DisableTelemetry"] is True
    assert main_window.document.values["SSLVersionMin"] == "tls1.2"
    assert '"DisableTelemetry": true' in main_window.preview.toPlainText()


def test_declining_preset_confirmation_leaves_document_unchanged(qtbot, main_window):
    preset = load_preset("disa_stig__mac_1_classified")

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        main_window._on_apply_preset(preset)

    assert main_window.document.values == {}


def test_apply_preset_refreshes_currently_open_form(qtbot, main_window):
    main_window._on_policy_selected("DisableTelemetry")
    preset = load_preset("disa_stig__mac_1_classified")

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok):
            main_window._on_apply_preset(preset)

    form = main_window._editor_layout.itemAt(0).widget()
    assert form._editor.get_value() is True


def test_presets_menu_groups_disa_stig_profiles_under_one_submenu(qtbot, main_window):
    # Hold each intermediate Qt object in a local variable: chaining calls
    # like `main_window.menuBar().actions()` inline can let PySide6 collect
    # the temporary wrapper and invalidate objects fetched through it.
    menu_bar = main_window.menuBar()
    top_actions = menu_bar.actions()
    presets_action = next(a for a in top_actions if a.text() == "&Presets")
    presets_menu = presets_action.menu()

    presets_actions = presets_menu.actions()
    family_action = next(a for a in presets_actions if a.text() == "DISA STIG - Mozilla Firefox")
    family_menu = family_action.menu()

    action_texts = [action.text() for action in family_menu.actions()]

    assert "View rule details..." in action_texts
    assert "Apply I - Mission Critical Classified..." in action_texts
    assert "Apply III - Administrative Sensitive..." in action_texts
    # one details action + separator + 9 profile actions
    assert len([t for t in action_texts if t.startswith("Apply ")]) == 9


def test_preset_details_dialog_opens_without_error(qtbot, main_window):
    preset = load_preset("disa_stig__mac_1_classified")
    dialog = PresetDetailsDialog(preset, main_window)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle().startswith("DISA STIG - Mozilla Firefox")
