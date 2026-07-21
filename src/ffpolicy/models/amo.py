"""Response models for the addons.mozilla.org (AMO) API v5."""

from __future__ import annotations

from pydantic import BaseModel


class AmoFile(BaseModel):
    url: str


class AmoCurrentVersion(BaseModel):
    file: AmoFile


class AmoAddon(BaseModel):
    guid: str
    name: str
    icon_url: str | None = None
    current_version: AmoCurrentVersion

    @property
    def install_url(self) -> str:
        return self.current_version.file.url


class AmoSearchResponse(BaseModel):
    count: int
    results: list[AmoAddon]
