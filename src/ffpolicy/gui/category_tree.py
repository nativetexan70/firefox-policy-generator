"""Left-nav tree: policy categories, each expanding to its policy names."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from ffpolicy.models.policy_schema import PolicySchema

_NAME_ROLE = Qt.ItemDataRole.UserRole


class CategoryTree(QTreeWidget):
    policySelected = Signal(str)

    def __init__(self, schema: PolicySchema, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.itemClicked.connect(self._on_item_clicked)
        self.load_schema(schema)

    def load_schema(self, schema: PolicySchema) -> None:
        self.clear()
        by_category: dict[str, list[str]] = {}
        for name, definition in schema.policies.items():
            by_category.setdefault(definition.category, []).append(name)

        for category in sorted(by_category):
            category_item = QTreeWidgetItem([category])
            self.addTopLevelItem(category_item)
            for name in sorted(by_category[category]):
                policy_item = QTreeWidgetItem([name])
                policy_item.setData(0, _NAME_ROLE, name)
                category_item.addChild(policy_item)
        self.expandAll()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        name = item.data(0, _NAME_ROLE)
        if name:
            self.policySelected.emit(name)
