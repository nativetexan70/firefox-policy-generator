"""Displays validation status and the list of current issues."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ffpolicy.core.validator import IssueLevel, ValidationIssue


class ValidationPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._status_label = QLabel("")
        self._list = QListWidget()
        self._list.setMaximumHeight(90)
        self._list.setVisible(False)
        layout.addWidget(self._status_label)
        layout.addWidget(self._list)

    def _set_status_role(self, role: str) -> None:
        self._status_label.setProperty("role", role)
        style = self._status_label.style()
        style.unpolish(self._status_label)
        style.polish(self._status_label)

    def update_issues(self, issues: list[ValidationIssue]) -> None:
        self._list.clear()
        errors = sum(1 for issue in issues if issue.level is IssueLevel.ERROR)
        warnings = sum(1 for issue in issues if issue.level is IssueLevel.WARNING)

        if errors:
            self._status_label.setText(f"✗ {errors} error(s), {warnings} warning(s)")
            self._set_status_role("statusError")
        elif warnings:
            self._status_label.setText(f"✓ valid · {warnings} warning(s)")
            self._set_status_role("statusWarn")
        else:
            self._status_label.setText("✓ valid")
            self._set_status_role("statusOk")

        for issue in issues:
            prefix = "ERROR" if issue.level is IssueLevel.ERROR else "WARNING"
            self._list.addItem(QListWidgetItem(f"[{prefix}] {issue.policy}: {issue.message}"))
        self._list.setVisible(bool(issues))
