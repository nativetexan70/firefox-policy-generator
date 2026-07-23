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
        (re.compile(r'"(?:[^"\\]|\\.)*"(?=\s*:)'), _format("#1e40af", bold=True)),  # keys (dark blue)
        (re.compile(r'(?<=:)\s*"(?:[^"\\]|\\.)*"'), _format("#b91c1c")),  # string values (dark red)
        (re.compile(r"\b(true|false)\b"), _format("#166534")),  # booleans (dark green)
        (re.compile(r"\bnull\b"), _format("#6b21a8")),  # null (dark purple)
        (re.compile(r"-?\b\d+(\.\d+)?\b"), _format("#7c2d12")),  # numbers (dark orange)
        (re.compile(r"[{}\[\],:]"), _format("#374151")),  # punctuation (dark gray)
    ]

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._RULES:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)
