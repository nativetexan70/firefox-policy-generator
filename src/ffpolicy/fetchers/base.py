"""Shared HTTP client: retry, timeout, and ETag-aware conditional GETs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

DEFAULT_TIMEOUT = 15

# Some hosts (notably addons.mozilla.org's CDN) reject the default
# "python-requests/X.Y" User-Agent as a bot signature. A descriptive,
# identifiable UA avoids that without pretending to be a browser.
USER_AGENT = "ffpolicy/1.0 (+https://github.com/nativetexan70/firefox-policy-generator)"


@dataclass
class FetchResult:
    status_code: int
    text: str | None
    etag: str | None
    not_modified: bool


def build_session(*, retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_with_etag(
    session: requests.Session,
    url: str,
    *,
    cached_etag: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    params: dict[str, Any] | None = None,
) -> FetchResult:
    """Conditional GET. Returns `not_modified=True` (text=None) on a 304."""
    headers = {"If-None-Match": cached_etag} if cached_etag else {}
    response = session.get(url, headers=headers, timeout=timeout, params=params)

    if response.status_code == 304:
        return FetchResult(304, None, cached_etag, not_modified=True)

    response.raise_for_status()
    return FetchResult(
        response.status_code,
        response.text,
        response.headers.get("ETag"),
        not_modified=False,
    )
