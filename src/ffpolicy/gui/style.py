"""Centralized QSS stylesheet: a flat, modern look with a consistent spacing
rhythm, applied once from MainWindow so every child widget inherits it.
"""

from __future__ import annotations

_ACCENT = "#2f6fed"
_ACCENT_DARK = "#2559c9"
_BORDER = "#dde1e7"
_BG = "#f5f6f8"
_PANEL_BG = "#ffffff"
_TEXT = "#1f2430"
_MUTED = "#6b7480"
_DANGER = "#d64545"

APP_STYLESHEET = f"""
* {{
    font-family: -apple-system, "Segoe UI", "Cantarell", sans-serif;
    font-size: 13px;
    color: {_TEXT};
}}

QMainWindow, QWidget {{
    background: {_BG};
}}

QLabel[role="sectionHeader"] {{
    font-weight: 600;
    color: {_MUTED};
    padding: 2px 0 4px 0;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    font-size: 11px;
}}

QLabel[role="statusOk"] {{
    color: #1f8a4c;
    font-weight: 600;
}}

QLabel[role="statusWarn"] {{
    color: #b0790a;
    font-weight: 600;
}}

QLabel[role="statusError"] {{
    color: {_DANGER};
    font-weight: 600;
}}

QTreeWidget, QListWidget, QTableWidget, QTextEdit, QScrollArea {{
    background: {_PANEL_BG};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    outline: none;
}}

QScrollArea > QWidget > QWidget {{
    background: {_PANEL_BG};
}}

QTreeWidget::item, QListWidget::item {{
    padding: 5px 6px;
    border-radius: 4px;
}}

QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {_ACCENT};
    color: white;
}}

QTreeWidget::item:hover:!selected, QListWidget::item:hover:!selected {{
    background: #eef2fc;
}}

QHeaderView::section {{
    background: #eef0f3;
    color: {_MUTED};
    border: none;
    border-bottom: 1px solid {_BORDER};
    padding: 6px 8px;
    font-weight: 600;
}}

QTableWidget {{
    gridline-color: {_BORDER};
}}

QTableWidget::item {{
    padding: 2px 4px;
}}

QGroupBox {{
    border: 1px solid {_BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    background: {_PANEL_BG};
    font-weight: 600;
    color: {_MUTED};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}

QLineEdit, QComboBox, QSpinBox {{
    background: {_PANEL_BG};
    border: 1px solid {_BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: {_ACCENT};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {_ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QPushButton {{
    background: {_PANEL_BG};
    border: 1px solid {_BORDER};
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 500;
}}

QPushButton:hover {{
    background: #eef2fc;
    border-color: {_ACCENT};
}}

QPushButton:pressed {{
    background: #e2e9fb;
}}

QPushButton[role="primary"] {{
    background: {_ACCENT};
    color: white;
    border: 1px solid {_ACCENT_DARK};
    font-weight: 600;
    padding: 8px 18px;
}}

QPushButton[role="primary"]:hover {{
    background: {_ACCENT_DARK};
}}

QPushButton[role="danger"] {{
    color: {_DANGER};
    border-color: #f0c2c2;
}}

QPushButton[role="danger"]:hover {{
    background: #fdeeee;
    border-color: {_DANGER};
}}

QSplitter::handle {{
    background: {_BG};
    width: 10px;
}}

QSplitter::handle:hover {{
    background: {_BORDER};
}}

#footerBar {{
    background: {_PANEL_BG};
    border-top: 1px solid {_BORDER};
}}

QStatusBar {{
    background: {_PANEL_BG};
    border-top: 1px solid {_BORDER};
    color: {_MUTED};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: #c7cdd6;
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: #a9b1bd;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""
