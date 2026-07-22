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
    description: str = ""
    recommendation: str = ""
    note: str | None = None


class Preset(BaseModel):
    id: str
    name: str
    description: str
    source: str
    values: dict[str, Any] = Field(default_factory=dict)
    rules: list[PresetRule] = Field(default_factory=list)
    family: str | None = None
    """Shared name across profile variants of the same underlying ruleset
    (e.g. all nine DISA STIG Mission Assurance Category profiles), used to
    group them together in menus. None for a preset with no profile variants.
    """
    profile_id: str | None = None
    profile_title: str | None = None

    @property
    def manual_rules(self) -> list[PresetRule]:
        """Rules with no automatable policies.json value - need operator action."""
        return [rule for rule in self.rules if rule.policy is None]

    @property
    def automated_rules(self) -> list[PresetRule]:
        return [rule for rule in self.rules if rule.policy is not None]


def _expand_profiles(data: dict[str, Any]) -> list[Preset]:
    """Expand a preset document's `profiles` list into one Preset per profile,
    all sharing the same values/rules - the profile only changes id/name/
    description. Documents with no `profiles` key load as a single Preset.
    """
    profiles = data.get("profiles")
    if not profiles:
        return [Preset.model_validate(data)]

    base_id = data["id"]
    base_name = data["name"]
    shared = {k: v for k, v in data.items() if k != "profiles"}

    presets = []
    for profile in profiles:
        profile_id = profile["id"]
        profile_title = profile["title"]
        preset_data = {
            **shared,
            "id": f"{base_id}__{profile_id.lower().replace('-', '_')}",
            "name": f"{base_name} ({profile_title})",
            "family": base_name,
            "profile_id": profile_id,
            "profile_title": profile_title,
        }
        presets.append(Preset.model_validate(preset_data))
    return presets


def load_bundled_presets() -> dict[str, Preset]:
    """Load every bundled preset from resources/presets/*.yaml, keyed by preset id.

    A resource whose document defines a `profiles` list expands into one
    Preset per profile (see `_expand_profiles`); one without expands to a
    single Preset as-is.
    """
    presets: dict[str, Preset] = {}
    for entry in importlib.resources.files(_PRESETS_PACKAGE).iterdir():
        if entry.name.endswith((".yaml", ".yml")):
            data = yaml.safe_load(entry.read_text(encoding="utf-8"))
            for preset in _expand_profiles(data):
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
