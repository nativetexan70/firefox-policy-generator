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


def _name_match_rank(name: str, query: str) -> tuple[int, int]:
    """Lower is a better match: exact name < name starts with query <
    query appears in name (earlier is better) < no direct name match.
    """
    name_lower = name.lower()
    query_lower = query.lower()

    if name_lower == query_lower:
        return (0, 0)
    if name_lower.startswith(query_lower):
        return (1, 0)
    position = name_lower.find(query_lower)
    if position != -1:
        return (2, position)
    return (3, 0)


def rank_by_name_relevance(addons: list[AmoAddon], query: str) -> list[AmoAddon]:
    """Sort search results so the closest name match to `query` comes first.

    AMO's own relevance ranking weighs description/summary matches alongside
    name matches, so a name search can otherwise surface an unrelated result
    above the extension whose name the user actually typed. The sort is
    stable, so results tied on name-match rank keep AMO's original order.
    """
    return sorted(addons, key=lambda addon: _name_match_rank(addon.name, query))


def search_extensions(query: str, session: requests.Session | None = None) -> AmoSearchResponse:
    session = session or build_session()
    cache_key = f"search:{query}"

    cached = cache.read_cached(_CACHE_NAMESPACE, cache_key, ttl_seconds=_CACHE_TTL_SECONDS)
    if cached is not None:
        result = AmoSearchResponse.model_validate(cached["data"])
    else:
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
        result = AmoSearchResponse.model_validate(data)

    result.results = rank_by_name_relevance(result.results, query)
    return result


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
