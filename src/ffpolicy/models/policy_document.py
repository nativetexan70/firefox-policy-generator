"""The user's in-progress set of configured policy values."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PolicyDocument(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)

    def set_policy(self, name: str, value: Any) -> None:
        self.values[name] = value

    def unset_policy(self, name: str) -> None:
        self.values.pop(name, None)

    def to_policies_json(self) -> dict[str, Any]:
        """Serialize to the standard `{"policies": {...}}` shape.

        Keys are sorted for deterministic, byte-identical output across runs.
        """
        return {"policies": dict(sorted(self.values.items()))}
