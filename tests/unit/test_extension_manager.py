from unittest.mock import patch

from ffpolicy.fetchers.amo_client import AmoRateLimitedError
from ffpolicy.gui.extension_manager import ExtensionManager
from ffpolicy.models.amo import AmoAddon

BITWARDEN = AmoAddon(
    guid="{446900e4-71c2-419f-a6a7-df9c091e268b}",
    name="Bitwarden Password Manager",
    current_version={"file": {"url": "https://example.com/bitwarden.xpi"}},
)


def test_add_from_url_populates_table_from_addon_detail(qtbot):
    manager = ExtensionManager()
    qtbot.addWidget(manager)
    manager._url_box.setText(
        "https://addons.mozilla.org/en-US/firefox/addon/bitwarden-password-manager/"
    )

    with patch(
        "ffpolicy.gui.extension_manager.get_addon_detail", return_value=BITWARDEN
    ) as mock_detail:
        manager._on_add_from_url()

    mock_detail.assert_called_once_with("bitwarden-password-manager")
    assert manager.get_value() == {
        BITWARDEN.guid: {
            "installation_mode": "force_installed",
            "install_url": "https://example.com/bitwarden.xpi",
        }
    }
    assert "Bitwarden Password Manager" in manager._url_status.text()
    assert manager._url_box.text() == ""


def test_add_from_url_rejects_non_amo_link(qtbot):
    manager = ExtensionManager()
    qtbot.addWidget(manager)
    manager._url_box.setText("https://example.com/not-amo")

    with patch("ffpolicy.gui.extension_manager.get_addon_detail") as mock_detail:
        manager._on_add_from_url()

    mock_detail.assert_not_called()
    assert manager.get_value() == {}
    assert "Not a recognized addons.mozilla.org link" in manager._url_status.text()


def test_add_from_url_handles_rate_limit(qtbot):
    manager = ExtensionManager()
    qtbot.addWidget(manager)
    manager._url_box.setText(
        "https://addons.mozilla.org/en-US/firefox/addon/bitwarden-password-manager/"
    )

    with patch(
        "ffpolicy.gui.extension_manager.get_addon_detail",
        side_effect=AmoRateLimitedError("rate limited"),
    ):
        manager._on_add_from_url()

    assert manager.get_value() == {}
    assert "rate-limited" in manager._url_status.text()


def test_add_from_url_handles_lookup_failure(qtbot):
    manager = ExtensionManager()
    qtbot.addWidget(manager)
    manager._url_box.setText(
        "https://addons.mozilla.org/en-US/firefox/addon/does-not-exist/"
    )

    with patch(
        "ffpolicy.gui.extension_manager.get_addon_detail", side_effect=ValueError("404")
    ):
        manager._on_add_from_url()

    assert manager.get_value() == {}
    assert "Couldn't look up that link" in manager._url_status.text()


def test_add_from_url_ignores_empty_input(qtbot):
    manager = ExtensionManager()
    qtbot.addWidget(manager)
    manager._url_box.setText("   ")

    with patch("ffpolicy.gui.extension_manager.get_addon_detail") as mock_detail:
        manager._on_add_from_url()

    mock_detail.assert_not_called()
    assert manager.get_value() == {}
