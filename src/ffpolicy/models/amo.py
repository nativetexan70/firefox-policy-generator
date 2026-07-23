"""Response models for the addons.mozilla.org (AMO) API v5."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

_PREFERRED_LOCALES = ("en-US", "en")


def _flatten_translated_field(value: Any) -> Any:
    """AMO's API always returns translatable fields (name, summary, ...) as
    a `{locale: value}` object - even with `?lang=` narrowing which locales
    are included (mozilla/addons-server docs: "The response is always an
    object.") - so a plain string is never actually guaranteed. Pick the
    best available translation rather than assuming a shape.
    """
    if not isinstance(value, dict):
        return value

    default_locale = value.get("_default")
    for locale in (default_locale, *_PREFERRED_LOCALES):
        if locale and value.get(locale):
            return value[locale]

    return next((v for v in value.values() if v), None)


class AmoFile(BaseModel):
    url: str


class AmoCurrentVersion(BaseModel):
    file: AmoFile


class AmoAddon(BaseModel):
    guid: str
    name: str
    icon_url: str | None = None
    current_version: AmoCurrentVersion

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> Any:
        return _flatten_translated_field(value)

    @property
    def install_url(self) -> str:
        return self.current_version.file.url


class AmoSearchResponse(BaseModel):
    count: int
    results: list[AmoAddon]
