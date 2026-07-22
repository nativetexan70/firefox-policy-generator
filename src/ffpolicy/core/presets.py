"""Bundled configuration presets (e.g. DISA STIG baselines) that pre-fill a
PolicyDocument with a known-good set of policy values.
"""

from __future__ import annotations

import importlib.resources
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ffpolicy.models.policy_document import PolicyDocument

_PRESETS_PACKAGE = "ffpolicy.resources.presets"


class PresetRule(BaseModel):
    """One source rule (e.g. a DISA STIG Vuln ID) backing a preset's values."""

    id: str
    version: str
    severity: str
    title: str
    policy: str | None = None
    note: str | None = None


class Preset(BaseModel):
    id: str
    name: str
    description: str
    source: str
    values: dict[str, Any] = Field(default_factory=dict)
    rules: list[PresetRule] = Field(default_factory=list)

    @property
    def manual_rules(self) -> list[PresetRule]:
        """Rules with no automatable policies.json value - need operator action."""
        return [rule for rule in self.rules if rule.policy is None]

    @property
    def automated_rules(self) -> list[PresetRule]:
        return [rule for rule in self.rules if rule.policy is not None]


def load_bundled_presets() -> dict[str, Preset]:
    """Load every bundled preset from resources/presets/*.yaml, keyed by preset id."""
    presets: dict[str, Preset] = {}
    for entry in importlib.resources.files(_PRESETS_PACKAGE).iterdir():
        if entry.name.endswith((".yaml", ".yml")):
            data = yaml.safe_load(entry.read_text(encoding="utf-8"))
            preset = Preset.model_validate(data)
            presets[preset.id] = preset
    return presets


def load_preset(preset_id: str) -> Preset:
    presets = load_bundled_presets()
    if preset_id not in presets:
        available = ", ".join(sorted(presets)) or "(none)"
        raise KeyError(f"Unknown preset {preset_id!r}. Available presets: {available}")
    return presets[preset_id]


def apply_preset(document: PolicyDocument, preset: Preset) -> PolicyDocument:
    """Overlay `preset.values` onto `document`, one top-level policy key at a time.

    Each key the preset sets fully replaces any existing value for that key
    (matching how policies.json itself treats top-level keys as independent
    units); keys the preset doesn't mention are left untouched.
    """
    for key, value in preset.values.items():
        document.set_policy(key, value)
    return document
