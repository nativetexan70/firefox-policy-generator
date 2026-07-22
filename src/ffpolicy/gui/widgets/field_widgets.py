"""Reusable field widgets: one editor class per ValueType, all exposing a
uniform `get_value()` / `set_value()` / `valueChanged` interface so
`form_builder` can treat them polymorphically.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ffpolicy.models.policy_schema import PolicyField, ValueType


class FieldEditor(QWidget):
    """Base class for all field editors."""

    valueChanged = Signal(object)

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError


class BoolField(FieldEditor):
    def __init__(self, field: PolicyField, value: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._checkbox = QCheckBox(field.description or field.key)
        self._checkbox.setChecked(bool(value) if value is not None else bool(field.default))
        self._checkbox.toggled.connect(lambda checked: self.valueChanged.emit(checked))
        layout.addWidget(self._checkbox)

    def get_value(self) -> bool:
        return self._checkbox.isChecked()

    def set_value(self, value: Any) -> None:
        self._checkbox.setChecked(bool(value))


class StringField(FieldEditor):
    def __init__(self, field: PolicyField, value: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit(str(value) if value is not None else "")
        if field.type is ValueType.URL:
            self._edit.setPlaceholderText("https://...")
        self._edit.textChanged.connect(lambda text: self.valueChanged.emit(text))
        layout.addWidget(self._edit)

    def get_value(self) -> str:
        return self._edit.text()

    def set_value(self, value: Any) -> None:
        self._edit.setText(str(value) if value is not None else "")


class IntField(FieldEditor):
    def __init__(self, field: PolicyField, value: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._spin = QSpinBox()
        self._spin.setRange(-(2**31), 2**31 - 1)
        self._spin.setValue(int(value) if value is not None else int(field.default or 0))
        self._spin.valueChanged.connect(lambda v: self.valueChanged.emit(v))
        layout.addWidget(self._spin)

    def get_value(self) -> int:
        return self._spin.value()

    def set_value(self, value: Any) -> None:
        self._spin.setValue(int(value or 0))


class EnumField(FieldEditor):
    def __init__(self, field: PolicyField, value: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        self._combo.addItems(field.enum_values or [])
        if value is not None:
            index = self._combo.findText(str(value))
            if index >= 0:
                self._combo.setCurrentIndex(index)
        self._combo.currentTextChanged.connect(lambda text: self.valueChanged.emit(text))
        layout.addWidget(self._combo)

    def get_value(self) -> str:
        return self._combo.currentText()

    def set_value(self, value: Any) -> None:
        index = self._combo.findText(str(value))
        if index >= 0:
            self._combo.setCurrentIndex(index)


class ObjectField(FieldEditor):
    """Recurses over named children, laid out inside a group box."""

    def __init__(
        self, field: PolicyField, value: Any, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        value = value if isinstance(value, dict) else {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        box = QGroupBox(field.description or field.key)
        box_layout = QVBoxLayout(box)
        layout.addWidget(box)

        self._children: dict[str, FieldEditor] = {}
        for child in field.children:
            editor = build_field_editor(child, value.get(child.key))
            editor.valueChanged.connect(lambda _v, k=child.key: self._on_child_changed(k))
            box_layout.addWidget(_labeled(child.key, editor))
            self._children[child.key] = editor

    def _on_child_changed(self, _key: str) -> None:
        self.valueChanged.emit(self.get_value())

    def get_value(self) -> dict[str, Any]:
        return {key: editor.get_value() for key, editor in self._children.items()}

    def set_value(self, value: Any) -> None:
        value = value if isinstance(value, dict) else {}
        for key, editor in self._children.items():
            editor.set_value(value.get(key))


class ArrayField(FieldEditor):
    """A list of rows, each editing one element via the child field type."""

    def __init__(self, field: PolicyField, value: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._element_field = field.children[0] if field.children else PolicyField(
            key="[]", type=ValueType.STRING
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout = QVBoxLayout()
        self._layout.addLayout(self._rows_layout)

        add_button = QPushButton("+ Add")
        add_button.clicked.connect(lambda: self._add_row(None))
        self._layout.addWidget(add_button)

        self._rows: list[FieldEditor] = []
        for item in value if isinstance(value, list) else []:
            self._add_row(item)

    def _add_row(self, item: Any) -> None:
        editor = build_field_editor(self._element_field, item)
        editor.valueChanged.connect(lambda _v: self.valueChanged.emit(self.get_value()))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(editor)

        remove_button = QPushButton("-")
        remove_button.setFixedWidth(28)
        remove_button.clicked.connect(lambda: self._remove_row(row, editor))
        row_layout.addWidget(remove_button)

        self._rows_layout.addWidget(row)
        self._rows.append(editor)
        self.valueChanged.emit(self.get_value())

    def _remove_row(self, row: QWidget, editor: FieldEditor) -> None:
        self._rows.remove(editor)
        row.setParent(None)
        row.deleteLater()
        self.valueChanged.emit(self.get_value())

    def get_value(self) -> list[Any]:
        return [editor.get_value() for editor in self._rows]

    def set_value(self, value: Any) -> None:
        for row in list(self._rows):
            row.setParent(None)
        self._rows.clear()
        for item in value if isinstance(value, list) else []:
            self._add_row(item)


class RawJsonField(FieldEditor):
    """Fallback editor for shapes the schema-driven builder can't render
    (e.g. wildcard-keyed maps like ExtensionSettings' `*` entries).
    """

    def __init__(self, field: PolicyField, value: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QTextEdit()
        self._edit.setPlainText(json.dumps(value if value is not None else {}, indent=2))
        self._edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._edit)

    def _on_text_changed(self) -> None:
        try:
            self.valueChanged.emit(self.get_value())
        except json.JSONDecodeError:
            pass  # let the user keep typing invalid JSON without crashing

    def get_value(self) -> Any:
        return json.loads(self._edit.toPlainText() or "{}")

    def set_value(self, value: Any) -> None:
        self._edit.setPlainText(json.dumps(value if value is not None else {}, indent=2))


def _labeled(label: str, editor: FieldEditor) -> QWidget:
    if label == "*" or isinstance(editor, (ObjectField, ArrayField, RawJsonField)):
        box = QGroupBox(label)
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(editor)
        return box

    if isinstance(editor, BoolField):
        # The checkbox already renders its own label text; a row label would duplicate it.
        return editor

    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.addWidget(QLabel(label))
    row_layout.addWidget(editor)
    return row


def build_field_editor(field: PolicyField, value: Any) -> FieldEditor:
    """Recursively build the editor for `field`, falling back to raw JSON
    for wildcard-keyed maps that the fixed-shape builders can't represent.
    """
    if field.type is ValueType.OBJECT and any(c.key == "*" for c in field.children):
        return RawJsonField(field, value)
    if field.type is ValueType.BOOL:
        return BoolField(field, value)
    if field.type in (ValueType.STRING, ValueType.URL):
        return StringField(field, value)
    if field.type is ValueType.INT:
        return IntField(field, value)
    if field.type is ValueType.ENUM:
        return EnumField(field, value)
    if field.type is ValueType.OBJECT:
        return ObjectField(field, value)
    if field.type is ValueType.ARRAY:
        return ArrayField(field, value)
    return RawJsonField(field, value)
