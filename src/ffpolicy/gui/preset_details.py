"""Read-only dialog listing every rule in a preset with its setting
description and recommendation - the detail view behind "View rule details..."
in the Presets menu.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ffpolicy.core.presets import Preset, PresetRule


def _rule_card(rule: PresetRule) -> QWidget:
    card = QWidget()
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    policy = rule.policy or "manual/procedural - no policies.json setting"
    header = QLabel(f"[{rule.id}, {rule.severity}] {rule.title}")
    header.setProperty("role", "sectionHeader")
    header.setWordWrap(True)
    layout.addWidget(header)

    policy_label = QLabel(f"Policy: {policy}")
    policy_label.setStyleSheet("color: #6b7480;")
    layout.addWidget(policy_label)

    description = QLabel(f"Description: {rule.description}")
    description.setWordWrap(True)
    layout.addWidget(description)

    recommendation = QLabel(f"Recommendation: {rule.recommendation}")
    recommendation.setWordWrap(True)
    layout.addWidget(recommendation)

    if rule.note:
        note = QLabel(f"Note: {rule.note}")
        note.setWordWrap(True)
        note.setStyleSheet("color: #b0790a;")
        layout.addWidget(note)

    return card


class PresetDetailsDialog(QDialog):
    """Shows every rule behind a preset: id, severity, policy, description,
    and recommendation. Rules are identical across profile variants of the
    same family, so the dialog is opened once per family, not per profile.
    """

    def __init__(self, preset: Preset, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{preset.family or preset.name} - Rule Details")
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        summary = QLabel(
            f"<b>{preset.family or preset.name}</b><br>{preset.description}<br>"
            f"<i>Source: {preset.source}</i>"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(14)

        for rule in sorted(preset.rules, key=lambda r: r.id):
            container_layout.addWidget(_rule_card(rule))
        container_layout.addStretch(1)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        close_button = QPushButton("Close")
        close_button.setProperty("role", "primary")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
