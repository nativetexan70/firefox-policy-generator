import pytest
import responses

from ffpolicy.fetchers.amo_client import (
    DETAIL_URL,
    SEARCH_URL,
    AmoRateLimitedError,
    get_addon_detail,
    parse_addon_slug_from_url,
    rank_by_name_relevance,
    search_extensions,
)
from ffpolicy.models.amo import AmoAddon

ADDON_JSON = {
    "guid": "uBlock0@raymondhill.net",
    "name": "uBlock Origin",
    "icon_url": "https://example.com/icon.png",
    "current_version": {"file": {"url": "https://example.com/ublock.xpi"}},
}

SEARCH_JSON = {"count": 1, "results": [ADDON_JSON]}


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setattr("platformdirs.user_cache_dir", lambda *a, **k: str(tmp_path))


def test_parse_addon_slug_from_url():
    url = "https://addons.mozilla.org/en-US/firefox/addon/ublock-origin/"
    assert parse_addon_slug_from_url(url) == "ublock-origin"
    assert parse_addon_slug_from_url("https://example.com/not-amo") is None


@responses.activate
def test_search_extensions_parses_and_extracts_install_url():
    responses.add(responses.GET, SEARCH_URL, json=SEARCH_JSON, status=200)

    result = search_extensions("ublock")

    assert result.count == 1
    addon = result.results[0]
    assert addon.guid == "uBlock0@raymondhill.net"
    assert addon.install_url == "https://example.com/ublock.xpi"


@responses.activate
def test_get_addon_detail():
    responses.add(
        responses.GET, DETAIL_URL.format(id_or_slug="ublock-origin"), json=ADDON_JSON, status=200
    )

    addon = get_addon_detail("ublock-origin")

    assert addon.name == "uBlock Origin"
    assert addon.install_url == "https://example.com/ublock.xpi"


@responses.activate
def test_search_extensions_raises_on_rate_limit():
    responses.add(responses.GET, SEARCH_URL, json={"detail": "rate limited"}, status=429)

    with pytest.raises(AmoRateLimitedError):
        search_extensions("ublock")


@responses.activate
def test_search_extensions_uses_cache_on_second_call():
    responses.add(responses.GET, SEARCH_URL, json=SEARCH_JSON, status=200)

    search_extensions("ublock")
    search_extensions("ublock")  # should hit cache, not require a second registered response

    assert len(responses.calls) == 1


def _addon(name: str, guid: str) -> AmoAddon:
    return AmoAddon(
        guid=guid,
        name=name,
        current_version={"file": {"url": f"https://example.com/{guid}.xpi"}},
    )


def test_rank_by_name_relevance_prefers_exact_and_prefix_matches():
    unrelated = _addon("Tab Manager Plus", "tab-manager@example.com")
    contains = _addon("My uBlock Origin Clone", "companion@example.com")
    prefix = _addon("uBlock Origin Lite", "lite@example.com")
    exact = _addon("uBlock Origin", "ublock@example.com")

    ranked = rank_by_name_relevance([unrelated, contains, prefix, exact], "uBlock Origin")

    assert [addon.guid for addon in ranked] == [
        "ublock@example.com",
        "lite@example.com",
        "companion@example.com",
        "tab-manager@example.com",
    ]


def test_rank_by_name_relevance_is_case_insensitive_and_stable_on_ties():
    first = _addon("Password Manager", "a@example.com")
    second = _addon("password vault", "b@example.com")

    ranked = rank_by_name_relevance([first, second], "password")

    # Neither is an exact/prefix match to "password" alone in a way that
    # distinguishes them beyond "contains" - original order is preserved.
    assert [addon.guid for addon in ranked] == ["a@example.com", "b@example.com"]


@responses.activate
def test_search_extensions_reorders_results_by_name_relevance():
    unrelated_first = {
        "guid": "unrelated@example.com",
        "name": "Totally Different Addon",
        "current_version": {"file": {"url": "https://example.com/unrelated.xpi"}},
    }
    exact_match_second = {
        "guid": "ublock@example.com",
        "name": "uBlock Origin",
        "current_version": {"file": {"url": "https://example.com/ublock.xpi"}},
    }
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={"count": 2, "results": [unrelated_first, exact_match_second]},
        status=200,
    )

    result = search_extensions("uBlock Origin")

    assert [addon.guid for addon in result.results] == [
        "ublock@example.com",
        "unrelated@example.com",
    ]
