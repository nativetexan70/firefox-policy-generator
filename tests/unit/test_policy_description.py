from ffpolicy.gui.policy_description import PolicyDescriptionPanel
from ffpolicy.models.policy_schema import PolicyDefinition, PolicyField, ValueType


def _definition(**kwargs) -> PolicyDefinition:
    defaults = dict(
        name="SomePolicy",
        root_field=PolicyField(key="SomePolicy", type=ValueType.BOOL),
    )
    defaults.update(kwargs)
    return PolicyDefinition(**defaults)


def test_panel_shows_description_and_impact(qtbot):
    definition = _definition(
        description="Disable Telemetry data collection.",
        security_privacy_impact="Stops usage data from being sent to Mozilla.",
    )
    panel = PolicyDescriptionPanel(definition)
    qtbot.addWidget(panel)

    assert panel.layout().count() == 3  # description + header + impact


def test_panel_omits_impact_section_when_not_applicable(qtbot):
    definition = _definition(description="Show the bookmarks toolbar by default.")
    panel = PolicyDescriptionPanel(definition)
    qtbot.addWidget(panel)

    assert panel.layout().count() == 1  # description only


def test_panel_handles_missing_description(qtbot):
    definition = _definition(security_privacy_impact="Some impact text.")
    panel = PolicyDescriptionPanel(definition)
    qtbot.addWidget(panel)

    assert panel.layout().count() == 2  # header + impact, no description
