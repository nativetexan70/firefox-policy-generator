"""addons.mozilla.org (AMO) API v5 client: search, detail, and URL parsing."""

from __future__ import annotations

import re

import requests

from ffpolicy.fetchers import cache
from ffpolicy.fetchers.base import build_session
from ffpolicy.models.amo import AmoAddon, AmoSearchResponse

SEARCH_URL = "https://addons.mozilla.org/api/v5/addons/search/"
DETAIL_URL = "https://addons.mozilla.org/api/v5/addons/addon/{id_or_slug}/"

_CACHE_NAMESPACE = "amo"
_CACHE_TTL_SECONDS = 24 * 60 * 60

_AMO_URL_RE = re.compile(r"/firefox/addon/([^/]+)/?")


class AmoRateLimitedError(Exception):
    """Raised on HTTP 429; callers should degrade to manual GUID entry."""


def parse_addon_slug_from_url(url: str) -> str | None:
    match = _AMO_URL_RE.search(url)
    return match.group(1) if match else None


def search_extensions(query: str, session: requests.Session | None = None) -> AmoSearchResponse:
    session = session or build_session()
    cache_key = f"search:{query}"

    cached = cache.read_cached(_CACHE_NAMESPACE, cache_key, ttl_seconds=_CACHE_TTL_SECONDS)
    if cached is not None:
        return AmoSearchResponse.model_validate(cached["data"])

    response = session.get(
        SEARCH_URL,
        params={"q": query, "app": "firefox", "type": "extension"},
        timeout=15,
    )
    if response.status_code == 429:
        raise AmoRateLimitedError(f"AMO search rate-limited for query {query!r}")
    response.raise_for_status()

    data = response.json()
    cache.write_cached(_CACHE_NAMESPACE, cache_key, data)
    return AmoSearchResponse.model_validate(data)


def get_addon_detail(id_or_slug: str, session: requests.Session | None = None) -> AmoAddon:
    session = session or build_session()
    cache_key = f"detail:{id_or_slug}"

    cached = cache.read_cached(_CACHE_NAMESPACE, cache_key, ttl_seconds=_CACHE_TTL_SECONDS)
    if cached is not None:
        return AmoAddon.model_validate(cached["data"])

    response = session.get(DETAIL_URL.format(id_or_slug=id_or_slug), timeout=15)
    if response.status_code == 429:
        raise AmoRateLimitedError(f"AMO detail rate-limited for {id_or_slug!r}")
    response.raise_for_status()

    data = response.json()
    cache.write_cached(_CACHE_NAMESPACE, cache_key, data)
    return AmoAddon.model_validate(data)
