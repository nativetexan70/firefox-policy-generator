import pytest

from ffpolicy.fetchers.schema_sync import load_bundled_schema
from ffpolicy.gui.extension_manager import ExtensionManager
from ffpolicy.gui.main_window import MainWindow
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
