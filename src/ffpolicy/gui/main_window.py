"""QMainWindow: layout, menu, status bar - wires the whole visual build-validate-export loop."""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ffpolicy.core.errors import ExportError
from ffpolicy.core.generator import export_policies_json
from ffpolicy.core.validator import validate_document
from ffpolicy.fetchers.schema_sync import sync_schema
from ffpolicy.gui.category_tree import CategoryTree
from ffpolicy.gui.extension_manager import ExtensionManager
from ffpolicy.gui.form_builder import PolicyForm
from ffpolicy.gui.json_preview import JsonPreview
from ffpolicy.gui.style import APP_STYLESHEET
from ffpolicy.gui.validation_panel import ValidationPanel
from ffpolicy.models.policy_document import PolicyDocument
from ffpolicy.models.policy_schema import PolicySchema

_PREVIEW_DEBOUNCE_MS = 150

# The window is fixed (non-resizable) and sized for a 1920x1080 (FHD) display:
# comfortably smaller than the full screen so window decorations, taskbars, and
# panels never push it off-screen, while still using the space well.
_WINDOW_WIDTH = 1600
_WINDOW_HEIGHT = 900
_SPLITTER_SIZES = [280, 640, 680]  # tree | editor | preview, sums to _WINDOW_WIDTH


def _panel(title: str, content: QWidget) -> QWidget:
    """Wrap `content` with an uppercase section header, so the three splitter
    panes read as clearly labeled columns instead of unlabeled whitespace.
    """
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    header = QLabel(title)
    header.setProperty("role", "sectionHeader")
    layout.addWidget(header)
    layout.addWidget(content, 1)
    return panel


class MainWindow(QMainWindow):
    def __init__(
        self,
        schema: PolicySchema | None = None,
        schema_tier: str = "unknown",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Firefox Policy Generator")
        self.setFixedSize(_WINDOW_WIDTH, _WINDOW_HEIGHT)
        self.setStyleSheet(APP_STYLESHEET)
        self._center_on_screen()

        self.document = PolicyDocument()
        if schema is None:
            schema, schema_tier = sync_schema()
        self.schema = schema

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_PREVIEW_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._refresh_preview_and_validation)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)

        self.tree = CategoryTree(self.schema)
        self.tree.policySelected.connect(self._on_policy_selected)
        splitter.addWidget(_panel("Categories", self.tree))

        self._editor_container = QWidget()
        self._editor_layout = QVBoxLayout(self._editor_container)
        self._editor_layout.setContentsMargins(0, 0, 0, 0)
        self._editor_placeholder = QLabel("Select a policy from the left to configure it.")
        self._editor_placeholder.setWordWrap(True)
        self._editor_placeholder.setStyleSheet("color: #6b7480; padding-top: 4px;")
        self._editor_layout.addWidget(self._editor_placeholder)
        self._editor_layout.addStretch(1)
        splitter.addWidget(_panel("Policy Editor", self._editor_container))

        self.preview = JsonPreview()
        splitter.addWidget(_panel("JSON Preview", self.preview))
        splitter.setSizes(_SPLITTER_SIZES)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 12)
        content_layout.addWidget(splitter)
        central_layout.addWidget(content, 1)

        footer = QWidget()
        footer.setObjectName("footerBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)

        self.validation_panel = ValidationPanel()
        footer_layout.addWidget(self.validation_panel, 1)

        export_button = QPushButton("Export policies.json")
        export_button.setProperty("role", "primary")
        export_button.clicked.connect(self._on_export)
        footer_layout.addWidget(export_button, 0, Qt.AlignmentFlag.AlignBottom)

        central_layout.addWidget(footer, 0)

        self.setCentralWidget(central)
        self.statusBar().showMessage(
            f"Schema: {schema_tier} · {len(self.schema.policies)} policies"
        )

        self._refresh_preview_and_validation()

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        x = available.x() + (available.width() - _WINDOW_WIDTH) // 2
        y = available.y() + (available.height() - _WINDOW_HEIGHT) // 2
        self.move(max(x, available.x()), max(y, available.y()))

    def _clear_editor(self) -> None:
        while self._editor_layout.count():
            item = self._editor_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

    def _on_policy_selected(self, name: str) -> None:
        definition = self.schema.policies.get(name)
        if definition is None:
            return

        self._clear_editor()

        if name == "ExtensionSettings":
            manager = ExtensionManager(self.document.values.get(name))
            manager.settingsChanged.connect(lambda value: self._on_value_changed(name, value))
            self._editor_layout.addWidget(manager, 1)
        else:
            form = PolicyForm(definition, self.document.values.get(name))
            form.valueChanged.connect(self._on_value_changed)
            self._editor_layout.addWidget(form, 1)

    def _on_value_changed(self, name: str, value: Any) -> None:
        self.document.set_policy(name, value)
        self._debounce.start()

    def _refresh_preview_and_validation(self) -> None:
        self.preview.update_document(self.document)
        issues = validate_document(self.document, policy_schema=self.schema)
        self.validation_panel.update_issues(issues)

    def _on_export(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export policies.json", "policies.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            export_policies_json(self.document, path, overwrite=True)
        except ExportError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported to {path}", 5000)


def run_gui() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
