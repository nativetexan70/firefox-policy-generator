"""Live, syntax-highlighted preview of the rendered policies.json."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextEdit

from ffpolicy.core.generator import render_policies_json
from ffpolicy.gui.highlight import JsonHighlighter
from ffpolicy.models.policy_document import PolicyDocument


class JsonPreview(QTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("monospace"))
        self._highlighter = JsonHighlighter(self.document())

    def update_document(self, document: PolicyDocument) -> None:
        self.setPlainText(render_policies_json(document))
