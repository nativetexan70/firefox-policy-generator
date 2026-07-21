"""QMainWindow: layout, menu, status bar - wires the whole visual build-validate-export loop."""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import Qt, QTimer
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
from ffpolicy.gui.validation_panel import ValidationPanel
from ffpolicy.models.policy_document import PolicyDocument
from ffpolicy.models.policy_schema import PolicySchema

_PREVIEW_DEBOUNCE_MS = 150


class MainWindow(QMainWindow):
    def __init__(
        self,
        schema: PolicySchema | None = None,
        schema_tier: str = "unknown",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Firefox Policy Generator")
        self.resize(1200, 800)

        self.document = PolicyDocument()
        if schema is None:
            schema, schema_tier = sync_schema()
        self.schema = schema

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_PREVIEW_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._refresh_preview_and_validation)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = CategoryTree(self.schema)
        self.tree.policySelected.connect(self._on_policy_selected)
        splitter.addWidget(self.tree)

        self._editor_container = QWidget()
        self._editor_layout = QVBoxLayout(self._editor_container)
        self._editor_layout.addWidget(QLabel("Select a policy from the left"))
        splitter.addWidget(self._editor_container)

        self.preview = JsonPreview()
        splitter.addWidget(self.preview)
        splitter.setSizes([250, 500, 450])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addWidget(splitter)

        self.validation_panel = ValidationPanel()
        central_layout.addWidget(self.validation_panel)

        export_row = QHBoxLayout()
        export_row.addStretch()
        export_button = QPushButton("Export policies.json")
        export_button.clicked.connect(self._on_export)
        export_row.addWidget(export_button)
        central_layout.addLayout(export_row)

        self.setCentralWidget(central)
        self.statusBar().showMessage(
            f"Schema: {schema_tier} · {len(self.schema.policies)} policies"
        )

        self._refresh_preview_and_validation()

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
            self._editor_layout.addWidget(manager)
        else:
            form = PolicyForm(definition, self.document.values.get(name))
            form.valueChanged.connect(self._on_value_changed)
            self._editor_layout.addWidget(form)

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
