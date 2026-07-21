"""Walks a PolicyDefinition.root_field and builds the dynamic editor form."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ffpolicy.gui.widgets.field_widgets import build_field_editor
from ffpolicy.models.policy_schema import PolicyDefinition


class PolicyForm(QScrollArea):
    """Scrollable form for a single top-level policy definition."""

    valueChanged = Signal(str, object)  # (policy name, new value)

    def __init__(
        self, definition: PolicyDefinition, value: Any, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._definition = definition
        self.setWidgetResizable(True)

        container = QWidget()
        layout = QVBoxLayout(container)
        self._editor = build_field_editor(definition.root_field, value)
        self._editor.valueChanged.connect(self._on_changed)
        layout.addWidget(self._editor)
        layout.addStretch()
        self.setWidget(container)

    def _on_changed(self, _value: Any) -> None:
        self.valueChanged.emit(self._definition.name, self._editor.get_value())

    def get_value(self) -> Any:
        return self._editor.get_value()
