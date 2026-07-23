import json

import pytest
import responses

from ffpolicy.fetchers.amo_client import (
    DETAIL_URL,
    SEARCH_URL,
    AmoPageParseError,
    AmoRateLimitedError,
    get_addon_detail,
    get_addon_detail_from_page,
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

ADDON_PAGE_URL = "https://addons.mozilla.org/en-US/firefox/addon/bitwarden-password-manager/"


def _redux_state_html(*, addon_id=735894, slug="bitwarden-password-manager") -> str:
    """A minimal stand-in for the real `redux-store-state` script tag AMO's
    addon page embeds - shape verified against an actual saved AMO page:
    addons.byID (string-keyed) / addons.bySlug (int-valued) + versions.byId,
    exactly what the JSON API itself returns.
    """
    state = {
        "addons": {
            "byID": {
                str(addon_id): {
                    "guid": "{446900e4-71c2-419f-a6a7-df9c091e268b}",
                    "name": "Bitwarden Password Manager",
                    "icon_url": "https://example.com/bitwarden-icon.png",
                    "slug": slug,
                    "currentVersionId": 6331750,
                }
            },
            "bySlug": {slug: addon_id},
        },
        "versions": {
            "byId": {
                "6331750": {
                    "file": {"url": "https://example.com/bitwarden.xpi"},
                    "version": "2026.6.1",
                }
            }
        },
    }
    return (
        "<html><body>"
        f'<script type="application/json" id="redux-store-state">{json.dumps(state)}</script>'
        "</body></html>"
    )


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
    # `lang` narrows which locale AMO includes (smaller payload, right
    # fallback) - it doesn't change the {locale: value} shape, but it's
    # still worth sending, so assert we actually do.
    assert responses.calls[0].request.params.get("lang") == "en-US"
    # A default "python-requests/X.Y" User-Agent is a common bot-blocking
    # signature - assert we send an identifiable one instead.
    assert "python-requests" not in responses.calls[0].request.headers["User-Agent"]


@responses.activate
def test_get_addon_detail():
    responses.add(
        responses.GET, DETAIL_URL.format(id_or_slug="ublock-origin"), json=ADDON_JSON, status=200
    )

    addon = get_addon_detail("ublock-origin")
    assert responses.calls[0].request.params.get("lang") == "en-US"

    assert addon.name == "uBlock Origin"
    assert addon.install_url == "https://example.com/ublock.xpi"


@responses.activate
def test_get_addon_detail_from_page_extracts_redux_state():
    responses.add(responses.GET, ADDON_PAGE_URL, body=_redux_state_html(), status=200)

    addon = get_addon_detail_from_page(ADDON_PAGE_URL)

    assert addon.guid == "{446900e4-71c2-419f-a6a7-df9c091e268b}"
    assert addon.name == "Bitwarden Password Manager"
    assert addon.install_url == "https://example.com/bitwarden.xpi"


@responses.activate
def test_get_addon_detail_from_page_uses_cache_on_second_call():
    responses.add(responses.GET, ADDON_PAGE_URL, body=_redux_state_html(), status=200)

    get_addon_detail_from_page(ADDON_PAGE_URL)
    get_addon_detail_from_page(ADDON_PAGE_URL)

    assert len(responses.calls) == 1


@responses.activate
def test_get_addon_detail_from_page_raises_on_missing_script_tag():
    responses.add(responses.GET, ADDON_PAGE_URL, body="<html><body>nope</body></html>", status=200)

    with pytest.raises(AmoPageParseError):
        get_addon_detail_from_page(ADDON_PAGE_URL)


@responses.activate
def test_get_addon_detail_from_page_raises_on_missing_download_url():
    html = _redux_state_html()
    # Strip the version's file url out of the embedded state.
    broken = html.replace('"file": {"url": "https://example.com/bitwarden.xpi"}', '"file": {}')
    responses.add(responses.GET, ADDON_PAGE_URL, body=broken, status=200)

    with pytest.raises(AmoPageParseError):
        get_addon_detail_from_page(ADDON_PAGE_URL)


@responses.activate
def test_get_addon_detail_from_page_raises_on_rate_limit():
    responses.add(responses.GET, ADDON_PAGE_URL, json={"detail": "rate limited"}, status=429)

    with pytest.raises(AmoRateLimitedError):
        get_addon_detail_from_page(ADDON_PAGE_URL)


def test_addon_model_flattens_translated_name_object():
    """AMO's API always returns translatable fields as a {locale: value}
    object, even with `?lang=` narrowing which locales are present
    (mozilla/addons-server docs: "The response is always an object.") -
    AmoAddon.name must normalize that rather than assume a plain string.
    """
    translated = dict(ADDON_JSON, name={"en-US": "uBlock Origin"})
    assert AmoAddon.model_validate(translated).name == "uBlock Origin"


def test_addon_model_prefers_default_locale_when_requested_locale_missing():
    # Matches AMO's documented ?lang= fallback shape:
    # {"en-US": "Games", "de": null, "_default": "en-US"}
    translated = dict(ADDON_JSON, name={"en-US": "uBlock Origin", "de": None, "_default": "en-US"})
    assert AmoAddon.model_validate(translated).name == "uBlock Origin"


def test_addon_model_name_passes_through_plain_string():
    assert AmoAddon.model_validate(ADDON_JSON).name == "uBlock Origin"


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
