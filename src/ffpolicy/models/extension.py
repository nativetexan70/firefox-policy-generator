"""Models for the ExtensionSettings policy."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class InstallationMode(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    FORCE_INSTALLED = "force_installed"
    NORMAL_INSTALLED = "normal_installed"


MODES_REQUIRING_INSTALL_URL = frozenset(
    {InstallationMode.FORCE_INSTALLED, InstallationMode.NORMAL_INSTALLED}
)


class ExtensionSetting(BaseModel):
    guid: str
    installation_mode: InstallationMode
    install_url: str | None = None

    def to_policy_entry(self) -> dict[str, str]:
        entry: dict[str, str] = {"installation_mode": self.installation_mode.value}
        if self.install_url is not None:
            entry["install_url"] = self.install_url
        return entry
