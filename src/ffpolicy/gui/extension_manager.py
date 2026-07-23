"""AMO search + configured-extensions table, backing the ExtensionSettings policy."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ffpolicy.fetchers.amo_client import (
    AmoRateLimitedError,
    get_addon_detail,
    get_addon_detail_from_page,
    parse_addon_slug_from_url,
    search_extensions,
)
from ffpolicy.models.extension import MODES_REQUIRING_INSTALL_URL, InstallationMode

_ADDON_ROLE = Qt.ItemDataRole.UserRole


class ExtensionManager(QWidget):
    settingsChanged = Signal(dict)

    def __init__(self, value: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, dict[str, Any]] = dict(value or {})

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search AMO by extension name...")
        self._search_box.returnPressed.connect(self._on_search)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self._on_search)
        search_row.addWidget(self._search_box, 1)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)

        self._results_list = QListWidget()
        self._results_list.setMaximumHeight(110)
        self._results_list.itemDoubleClicked.connect(self._on_result_chosen)
        layout.addWidget(self._results_list)

        self._search_status = QLabel("")
        self._search_status.setStyleSheet("color: #6b7480;")
        layout.addWidget(self._search_status)

        url_header = QLabel("Add from an addons.mozilla.org link")
        url_header.setProperty("role", "sectionHeader")
        layout.addWidget(url_header)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self._url_box = QLineEdit()
        self._url_box.setPlaceholderText(
            "https://addons.mozilla.org/en-US/firefox/addon/<name>/"
        )
        self._url_box.returnPressed.connect(self._on_add_from_url)
        url_add_button = QPushButton("Add")
        url_add_button.clicked.connect(self._on_add_from_url)
        url_row.addWidget(self._url_box, 1)
        url_row.addWidget(url_add_button)
        layout.addLayout(url_row)

        self._url_status = QLabel("")
        self._url_status.setStyleSheet("color: #6b7480;")
        layout.addWidget(self._url_status)

        manual_header = QLabel("Add manually")
        manual_header.setProperty("role", "sectionHeader")
        layout.addWidget(manual_header)

        manual_row = QHBoxLayout()
        manual_row.setSpacing(8)
        self._manual_guid = QLineEdit()
        self._manual_guid.setPlaceholderText("Extension GUID (e.g. ext@example.com)")
        self._manual_mode = QComboBox()
        self._manual_mode.addItems([mode.value for mode in InstallationMode])
        self._manual_url = QLineEdit()
        self._manual_url.setPlaceholderText("Install URL (required for *_installed modes)")
        manual_add_button = QPushButton("Add")
        manual_add_button.clicked.connect(self._on_manual_add)
        manual_row.addWidget(self._manual_guid, 2)
        manual_row.addWidget(self._manual_mode, 1)
        manual_row.addWidget(self._manual_url, 2)
        manual_row.addWidget(manual_add_button)
        layout.addLayout(manual_row)

        configured_header = QLabel("Configured extensions")
        configured_header.setProperty("role", "sectionHeader")
        layout.addWidget(configured_header)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["GUID", "Mode", "Install URL", ""])
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Interactive (not ResizeToContents) for the widget-bearing columns: Qt's
        # ResizeToContents measures header text at setup time and does not reliably
        # re-measure QComboBox/QPushButton cell widgets added later via
        # setCellWidget(), leaving those columns pinned to a sliver.
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, 220)
        self._table.setColumnWidth(1, 180)  # fits "normal_installed", the longest mode value
        self._table.setColumnWidth(3, 90)
        layout.addWidget(self._table, 1)

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

    def _on_add_from_url(self) -> None:
        url = self._url_box.text().strip()
        if not url:
            return

        slug = parse_addon_slug_from_url(url)
        if slug is None:
            self._url_status.setText(
                "Not a recognized addons.mozilla.org link - paste the addon's page URL."
            )
            return

        # Scrape the page itself first: it's the exact URL the user gave us,
        # and doesn't depend on the separate api/v5 endpoint (which some
        # networks block independently of the page). Fall back to that API
        # on any failure (page unreachable, embedded data not found, ...).
        try:
            addon = get_addon_detail_from_page(url)
        except AmoRateLimitedError:
            self._url_status.setText(
                "AMO lookup unavailable (rate-limited) - enter GUID manually below."
            )
            return
        except Exception:  # noqa: BLE001 - fall back to the id/slug API before giving up
            try:
                addon = get_addon_detail(slug)
            except AmoRateLimitedError:
                self._url_status.setText(
                    "AMO lookup unavailable (rate-limited) - enter GUID manually below."
                )
                return
            except Exception as exc:  # noqa: BLE001 - any lookup failure degrades to manual
                self._url_status.setText(
                    f"Couldn't look up that link ({exc}) - enter GUID manually below."
                )
                return

        self.add_manual(addon.guid, InstallationMode.FORCE_INSTALLED, addon.install_url)
        self._url_status.setText(f"Added {addon.name} ({addon.guid}).")
        self._url_box.clear()

    def _on_manual_add(self) -> None:
        guid = self._manual_guid.text().strip()
        if not guid:
            return
        mode = InstallationMode(self._manual_mode.currentText())
        url = self._manual_url.text().strip() or None
        self.add_manual(guid, mode, url)

        self._manual_guid.clear()
        self._manual_url.clear()

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
