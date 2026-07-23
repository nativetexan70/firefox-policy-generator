"""Read-only header shown above a policy's editor: what it does, and - where
applicable - its security/privacy impact, so an admin can judge a setting
before changing it rather than after.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ffpolicy.models.policy_schema import PolicyDefinition


class PolicyDescriptionPanel(QWidget):
    def __init__(self, definition: PolicyDefinition, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(4)

        if definition.description:
            description = QLabel(definition.description)
            description.setWordWrap(True)
            layout.addWidget(description)

        if definition.security_privacy_impact:
            header = QLabel("Security & Privacy Impact")
            header.setProperty("role", "sectionHeader")
            layout.addWidget(header)

            impact = QLabel(definition.security_privacy_impact)
            impact.setWordWrap(True)
            impact.setStyleSheet("color: #b0790a;")
            layout.addWidget(impact)
