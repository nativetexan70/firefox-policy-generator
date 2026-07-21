"""QSyntaxHighlighter for JSON text, used by the live preview."""

from __future__ import annotations

import re

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat


def _format(color: str, *, bold: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(700)
    return fmt


class JsonHighlighter(QSyntaxHighlighter):
    _RULES = [
        (re.compile(r'"(?:[^"\\]|\\.)*"(?=\s*:)'), _format("#9cdcfe", bold=True)),  # keys
        (re.compile(r'(?<=:)\s*"(?:[^"\\]|\\.)*"'), _format("#ce9178")),  # string values
        (re.compile(r"\b(true|false)\b"), _format("#569cd6")),
        (re.compile(r"\bnull\b"), _format("#569cd6")),
        (re.compile(r"-?\b\d+(\.\d+)?\b"), _format("#b5cea8")),
        (re.compile(r"[{}\[\],:]"), _format("#d4d4d4")),
    ]

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._RULES:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)
