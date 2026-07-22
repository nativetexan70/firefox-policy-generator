"""Dialog for picking an existing policies.json to import - a location
detected on this system, or a manually browsed-to path.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ffpolicy.core.paths import discover_installed_policies


class ImportSourceDialog(QDialog):
    """Pick an existing policies.json - detected at a standard system
    location, or a manually browsed-to path - to import into the current
    document. Mirrors `ffpolicy discover` + `ffpolicy import`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import existing policies.json")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Detected on this system:"))
        self._found_combo = QComboBox()
        found = discover_installed_policies()
        if found:
            for target, path in found:
                self._found_combo.addItem(f"{target.value}  ->  {path}", str(path))
        else:
            self._found_combo.addItem("(none found at standard locations)", None)
            self._found_combo.setEnabled(False)
        layout.addWidget(self._found_combo)

        layout.addWidget(QLabel("Or choose a file:"))
        browse_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path to policies.json")
        browse_row.addWidget(self._path_edit, 1)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse)
        browse_row.addWidget(browse_button)
        layout.addLayout(browse_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_browse(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select policies.json", "", "JSON (*.json)"
        )
        if path:
            self._path_edit.setText(path)

    @property
    def selected_path(self) -> str | None:
        """The manually entered/browsed path if set, else the picked
        detected location (or None if nothing is available/chosen)."""
        typed = self._path_edit.text().strip()
        if typed:
            return typed
        return self._found_combo.currentData()
