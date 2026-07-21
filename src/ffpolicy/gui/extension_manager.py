"""AMO search + configured-extensions table, backing the ExtensionSettings policy."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ffpolicy.fetchers.amo_client import AmoRateLimitedError, search_extensions
from ffpolicy.models.extension import MODES_REQUIRING_INSTALL_URL, InstallationMode

_ADDON_ROLE = Qt.ItemDataRole.UserRole


class ExtensionManager(QWidget):
    settingsChanged = Signal(dict)

    def __init__(self, value: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, dict[str, Any]] = dict(value or {})

        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search AMO for an extension...")
        self._search_box.returnPressed.connect(self._on_search)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self._on_search)
        search_row.addWidget(self._search_box)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)

        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._on_result_chosen)
        layout.addWidget(self._results_list)

        self._search_status = QLabel("")
        layout.addWidget(self._search_status)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["GUID", "Mode", "Install URL", ""])
        layout.addWidget(self._table)

        self._refresh_table()

    def _on_search(self) -> None:
        query = self._search_box.text().strip()
        if not query:
            return

        self._results_list.clear()
        try:
            response = search_extensions(query)
        except AmoRateLimitedError:
            self._search_status.setText(
                "Search unavailable (rate-limited) - enter GUID manually below."
            )
            return
        except Exception:  # noqa: BLE001 - any network failure degrades to manual entry
            self._search_status.setText("Search unavailable - enter GUID manually below.")
            return

        self._search_status.setText(f"{response.count} result(s)")
        for addon in response.results:
            item = QListWidgetItem(f"{addon.name} ({addon.guid})")
            item.setData(_ADDON_ROLE, addon)
            self._results_list.addItem(item)

    def _on_result_chosen(self, item: QListWidgetItem) -> None:
        addon = item.data(_ADDON_ROLE)
        self.add_manual(addon.guid, InstallationMode.FORCE_INSTALLED, addon.install_url)

    def add_manual(
        self, guid: str, mode: InstallationMode, install_url: str | None = None
    ) -> None:
        entry: dict[str, Any] = {"installation_mode": mode.value}
        if install_url:
            entry["install_url"] = install_url
        self._settings[guid] = entry
        self._refresh_table()
        self.settingsChanged.emit(dict(self._settings))

    def _refresh_table(self) -> None:
        self._table.setRowCount(0)
        for guid, entry in self._settings.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(guid))

            mode_combo = QComboBox()
            mode_combo.addItems([mode.value for mode in InstallationMode])
            mode_combo.setCurrentText(
                entry.get("installation_mode", InstallationMode.ALLOWED.value)
            )
            mode_combo.currentTextChanged.connect(
                lambda text, g=guid: self._on_mode_changed(g, text)
            )
            self._table.setCellWidget(row, 1, mode_combo)

            url_edit = QLineEdit(entry.get("install_url", ""))
            url_edit.textChanged.connect(lambda text, g=guid: self._on_url_changed(g, text))
            self._table.setCellWidget(row, 2, url_edit)

            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(lambda _checked=False, g=guid: self._on_remove(g))
            self._table.setCellWidget(row, 3, remove_button)

    def _on_mode_changed(self, guid: str, mode_text: str) -> None:
        if guid not in self._settings:
            return
        self._settings[guid]["installation_mode"] = mode_text
        if InstallationMode(mode_text) not in MODES_REQUIRING_INSTALL_URL:
            self._settings[guid].pop("install_url", None)
        self.settingsChanged.emit(dict(self._settings))

    def _on_url_changed(self, guid: str, text: str) -> None:
        if guid not in self._settings:
            return
        if text:
            self._settings[guid]["install_url"] = text
        else:
            self._settings[guid].pop("install_url", None)
        self.settingsChanged.emit(dict(self._settings))

    def _on_remove(self, guid: str) -> None:
        self._settings.pop(guid, None)
        self._refresh_table()
        self.settingsChanged.emit(dict(self._settings))

    def get_value(self) -> dict[str, Any]:
        return dict(self._settings)

    def set_value(self, value: dict[str, Any] | None) -> None:
        self._settings = dict(value or {})
        self._refresh_table()
