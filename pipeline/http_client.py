"""Polite HTTP client: at most ~1 request/second, with a date-stamped disk cache.

Cache layout: data/raw/YYYY-MM-DD/<name>. A cached file is reused from the most
recent date folder that has it, unless refresh=True.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import requests

from . import config

_last_request = 0.0
_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT


def today_dir() -> Path:
    d = config.RAW / date.today().isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_cached(name: str) -> Path | None:
    """Newest cached copy of `name` across all date folders."""
    if not config.RAW.exists():
        return None
    for d in sorted((p for p in config.RAW.iterdir() if p.is_dir()), reverse=True):
        if (d / name).exists():
            return d / name
    return None


def polite_get(url: str, params: dict | None = None, timeout: int = 60) -> requests.Response:
    """GET with rate limiting and simple retry/backoff. Raises on HTTP errors."""
    global _last_request
    for attempt in range(4):
        wait = config.MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
            r.raise_for_status()
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            if attempt == 3:
                raise
            backoff = 5 * (attempt + 1)
            print(f"  request failed ({e}); retrying in {backoff}s")
            time.sleep(backoff)
    raise RuntimeError("unreachable")


def get_json_cached(name: str, url: str, params: dict | None = None, refresh: bool = False) -> dict:
    """Return parsed JSON, from cache if present (unless refresh)."""
    if not refresh and (cached := find_cached(name)):
        return json.loads(cached.read_text())
    r = polite_get(url, params)
    data = r.json()
    if isinstance(data, dict) and "error" in data:  # ArcGIS returns errors with HTTP 200
        raise RuntimeError(f"ArcGIS error for {url}: {data['error']}")
    path = today_dir() / name
    path.write_text(json.dumps(data))
    return data
