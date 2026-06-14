from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile
from urllib.parse import urlencode

import requests

try:
    import diskcache
except ImportError:  # pragma: no cover - local dependency fallback
    diskcache = None

logger = logging.getLogger(__name__)


def _default_cache_dir() -> Path:
    configured_dir = os.environ.get("PLOTLY_FIFA_CACHE_DIR")
    if configured_dir:
        return Path(configured_dir).expanduser()
    return Path(tempfile.gettempdir()) / "plotly_fifa_cache"


if diskcache is not None:
    cache = diskcache.Cache(str(_default_cache_dir()))
else:
    class _MemoryCache(dict):
        def set(self, key, value, expire=None):
            self[key] = value

        def iterkeys(self):
            return iter(self.keys())

    cache = _MemoryCache()

CACHE_TTL = {
    "live": 30,
    "today": 120,
    "standings": 300,
    "scorers": 300,
    "team": 3600,
    "player": 3600,
    "historical": 86400,
}


def _cache_key(url: str, params: dict | None = None) -> str:
    if not params:
        return url
    return f"{url}?{urlencode(sorted(params.items()))}"


def cached_get(
    url: str,
    headers: dict,
    ttl_key: str,
    params: dict | None = None,
    timeout: int = 10,
):
    key = _cache_key(url, params)
    stale_key = f"stale::{key}"

    if key in cache:
        return cache[key]

    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        cache.set(key, data, expire=CACHE_TTL[ttl_key])
        cache.set(stale_key, data, expire=max(CACHE_TTL[ttl_key] * 10, 600))
        return data
    except requests.RequestException as exc:
        if stale_key in cache:
            logger.warning("Serving stale cache for %s after %s", key, exc)
            return cache[stale_key]
        raise


def prime_cache(key: str, value, ttl_key: str = "historical") -> None:
    cache.set(key, value, expire=CACHE_TTL.get(ttl_key, CACHE_TTL["historical"]))


def dump_cache_index() -> list[str]:
    return [json.dumps(item) if not isinstance(item, str) else item for item in cache.iterkeys()]
