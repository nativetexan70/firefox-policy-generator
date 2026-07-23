"""addons.mozilla.org (AMO) API v5 client: search, detail, and URL parsing."""

from __future__ import annotations

import json
import re

import requests

from ffpolicy.fetchers import cache
from ffpolicy.fetchers.base import build_session
from ffpolicy.models.amo import AmoAddon, AmoSearchResponse

SEARCH_URL = "https://addons.mozilla.org/api/v5/addons/search/"
DETAIL_URL = "https://addons.mozilla.org/api/v5/addons/addon/{id_or_slug}/"

# AMO's API always returns translatable fields (name, summary, ...) as a
# {locale: value} object - `lang` only narrows which locales are included in
# that object, it does not flatten it to a plain string (mozilla/addons-server
# docs: "The response is always an object."). AmoAddon.name normalizes
# whichever shape comes back; `lang` is still worth sending to keep responses
# small and get the right fallback locale.
_LANG = "en-US"

_CACHE_NAMESPACE = "amo"
_CACHE_TTL_SECONDS = 24 * 60 * 60

_AMO_URL_RE = re.compile(r"/firefox/addon/([^/]+)/?")

# The addon listing page (a server-rendered React/Redux app) embeds the full
# page state - including the exact data the JSON API would return - in this
# script tag. Scraping it is a resilient fallback for the "paste a link"
# flow: it works directly off the page the user already has open/verified
# reachable, without depending on the separate api/v5 endpoint (which some
# networks/proxies block independently of the page itself).
_REDUX_STATE_RE = re.compile(
    r'<script type="application/json" id="redux-store-state">(.*?)</script>', re.S
)


class AmoRateLimitedError(Exception):
    """Raised on HTTP 429; callers should degrade to manual GUID entry."""


class AmoPageParseError(Exception):
    """Raised when an addon page was fetched but its embedded data couldn't
    be located/parsed; callers should degrade to manual GUID entry."""


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
            params={"q": query, "app": "firefox", "type": "extension", "lang": _LANG},
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

    response = session.get(
        DETAIL_URL.format(id_or_slug=id_or_slug), params={"lang": _LANG}, timeout=15
    )
    if response.status_code == 429:
        raise AmoRateLimitedError(f"AMO detail rate-limited for {id_or_slug!r}")
    response.raise_for_status()

    data = response.json()
    cache.write_cached(_CACHE_NAMESPACE, cache_key, data)
    return AmoAddon.model_validate(data)


def get_addon_detail_from_page(
    url: str, session: requests.Session | None = None
) -> AmoAddon:
    """Fetch an addon's listing page and extract its metadata from the
    embedded Redux state, rather than calling the separate JSON API.

    Raises `AmoPageParseError` if the page doesn't contain the expected
    embedded state (e.g. AMO changed its frontend, or `url` isn't actually
    an addon listing page); callers should treat that the same as any other
    lookup failure and degrade to manual GUID entry.
    """
    session = session or build_session()
    cache_key = f"page:{url}"

    cached = cache.read_cached(_CACHE_NAMESPACE, cache_key, ttl_seconds=_CACHE_TTL_SECONDS)
    if cached is not None:
        return AmoAddon.model_validate(cached["data"])

    response = session.get(url, timeout=15)
    if response.status_code == 429:
        raise AmoRateLimitedError(f"AMO page rate-limited for {url!r}")
    response.raise_for_status()

    match = _REDUX_STATE_RE.search(response.text)
    if match is None:
        raise AmoPageParseError(f"couldn't find addon data embedded in {url}")

    try:
        state = json.loads(match.group(1))
        addons = state["addons"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AmoPageParseError(f"unrecognized embedded data shape at {url}") from exc

    slug = parse_addon_slug_from_url(url)
    addon_id = addons.get("bySlug", {}).get(slug) if slug else None
    if addon_id is None:
        by_id = addons.get("byID", {})
        if len(by_id) == 1:
            addon_id = next(iter(by_id))

    record = addons.get("byID", {}).get(str(addon_id)) if addon_id is not None else None
    if record is None:
        raise AmoPageParseError(f"couldn't locate an addon record at {url}")

    version_id = record.get("currentVersionId")
    version = state.get("versions", {}).get("byId", {}).get(str(version_id), {})
    file_url = version.get("file", {}).get("url")
    if not file_url:
        raise AmoPageParseError(f"couldn't find a download URL at {url}")

    data = {
        "guid": record.get("guid"),
        "name": record.get("name"),
        "icon_url": record.get("icon_url"),
        "current_version": {"file": {"url": file_url}},
    }
    cache.write_cached(_CACHE_NAMESPACE, cache_key, data)
    return AmoAddon.model_validate(data)
