"""On-disk cache (XDG dirs) with TTL, for parsed schemas and AMO responses."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import platformdirs

_APP_NAME = "ffpolicy"


def cache_dir(*subdirs: str) -> Path:
    path = Path(platformdirs.user_cache_dir(_APP_NAME)).joinpath(*subdirs)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _entry_path(namespace: str, key: str) -> Path:
    safe_key = key.replace("/", "_").replace(":", "_")
    return cache_dir(namespace) / f"{safe_key}.json"


def read_cached(
    namespace: str, key: str, *, ttl_seconds: float | None = None
) -> dict[str, Any] | None:
    """Return the cached envelope `{"etag": ..., "data": ...}`, or None if absent/expired."""
    path = _entry_path(namespace, key)
    if not path.exists():
        return None
    if ttl_seconds is not None and (time.time() - path.stat().st_mtime) > ttl_seconds:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cached(namespace: str, key: str, data: Any, *, etag: str | None = None) -> None:
    path = _entry_path(namespace, key)
    envelope = {"etag": etag, "data": data}
    path.write_text(json.dumps(envelope), encoding="utf-8")
