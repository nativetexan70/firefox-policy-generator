"""Displays validation status and the list of current issues."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ffpolicy.core.validator import IssueLevel, ValidationIssue


class ValidationPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._status_label = QLabel("")
        self._list = QListWidget()
        self._list.setMaximumHeight(120)
        layout.addWidget(self._status_label)
        layout.addWidget(self._list)

    def update_issues(self, issues: list[ValidationIssue]) -> None:
        self._list.clear()
        errors = sum(1 for issue in issues if issue.level is IssueLevel.ERROR)
        warnings = sum(1 for issue in issues if issue.level is IssueLevel.WARNING)

        if errors:
            self._status_label.setText(f"✗ {errors} error(s), {warnings} warning(s)")
        elif warnings:
            self._status_label.setText(f"✓ valid · {warnings} warning(s)")
        else:
            self._status_label.setText("✓ valid")

        for issue in issues:
            prefix = "ERROR" if issue.level is IssueLevel.ERROR else "WARNING"
            self._list.addItem(QListWidgetItem(f"[{prefix}] {issue.policy}: {issue.message}"))
