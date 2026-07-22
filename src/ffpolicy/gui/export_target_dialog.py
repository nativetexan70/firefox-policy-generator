"""Dialog for exporting to a standard Firefox policy location, or a custom path."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
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

from ffpolicy.core.paths import ExportTarget, resolve_export_path, target_requires_privileges

_TARGET_LABELS: dict[ExportTarget, str] = {
    ExportTarget.SYSTEM_LINUX: "System (Linux: /etc/firefox/policies, macOS: Library/Mozilla)",
    ExportTarget.LINUX_LIB64_DISTRIBUTION: "Linux distribution dir - lib64 (Fedora/RHEL)",
    ExportTarget.LINUX_LIB_DISTRIBUTION: "Linux distribution dir - lib (Debian/Ubuntu)",
    ExportTarget.LINUX_FIREFOX_ESR: "Linux distribution dir - firefox-esr (Debian ESR)",
    ExportTarget.LINUX_OPT_DISTRIBUTION: "Linux distribution dir - /opt (manual tarball install)",
    ExportTarget.LINUX_SNAP: "Firefox snap (same file as System)",
    ExportTarget.LINUX_FLATPAK_SYSTEM: "Flatpak Firefox - system-wide",
    ExportTarget.LINUX_FLATPAK_USER: "Flatpak Firefox - this user only",
    ExportTarget.DISTRIBUTION: "distribution/ (relative to current directory)",
    ExportTarget.CUSTOM: "Custom path...",
}


class ExportTargetDialog(QDialog):
    """Pick a standard Firefox policy location (or a custom path) to export to.

    Mirrors `ffpolicy export --target`: the resolved path and whether it's a
    root-owned location update live as the target changes, and an "elevate"
    checkbox opts into the pkexec/sudo retry the CLI's `--elevate` triggers.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export to standard location")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Target location:"))
        self._target_combo = QComboBox()
        for target in ExportTarget:
            self._target_combo.addItem(_TARGET_LABELS.get(target, target.value), target)
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        layout.addWidget(self._target_combo)

        custom_row = QHBoxLayout()
        self._custom_path_edit = QLineEdit()
        self._custom_path_edit.setPlaceholderText("Directory or policies.json path")
        self._custom_path_edit.textChanged.connect(self._update_resolved_path)
        custom_row.addWidget(self._custom_path_edit, 1)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse_custom_path)
        custom_row.addWidget(browse_button)
        layout.addLayout(custom_row)

        self._resolved_path_label = QLabel()
        self._resolved_path_label.setWordWrap(True)
        layout.addWidget(self._resolved_path_label)

        self._elevate_checkbox = QCheckBox(
            "Retry with elevated privileges (pkexec/sudo) if the write is denied"
        )
        layout.addWidget(self._elevate_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_target_changed()

    def _on_browse_custom_path(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, "Custom export path", "policies.json", "JSON (*.json)"
        )
        if path:
            self._custom_path_edit.setText(path)

    def _on_target_changed(self, _index: int = 0) -> None:
        self._custom_path_edit.setEnabled(self.selected_target is ExportTarget.CUSTOM)
        self._update_resolved_path()

    def _update_resolved_path(self) -> None:
        target = self.selected_target
        if target is ExportTarget.CUSTOM:
            custom = self._custom_path_edit.text().strip()
            if not custom:
                self._resolved_path_label.setText("Enter or browse to a custom path above.")
                self._elevate_checkbox.setEnabled(False)
                return
            path = resolve_export_path(target, custom)
        else:
            path = resolve_export_path(target)

        requires = target_requires_privileges(target)
        self._elevate_checkbox.setEnabled(requires)
        note = " (requires elevated privileges to write)" if requires else ""
        self._resolved_path_label.setText(f"Will write to: {path}{note}")

    @property
    def selected_target(self) -> ExportTarget:
        # Qt's QVariant storage coerces the str-subclassed ExportTarget back
        # to a plain str, so re-wrap it rather than comparing/using it as-is.
        return ExportTarget(self._target_combo.currentData())

    @property
    def custom_path(self) -> str | None:
        text = self._custom_path_edit.text().strip()
        return text or None

    @property
    def elevate(self) -> bool:
        return self._elevate_checkbox.isChecked()
