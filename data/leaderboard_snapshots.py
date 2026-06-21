from __future__ import annotations

import datetime as dt
import json
import logging
import os
from pathlib import Path
import tempfile
import time

import requests

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD_SNAPSHOT_PATH = REPO_ROOT / "leaderboards.json"
EXPENSIVE_LEADERBOARD_METRICS = ("Yellow Cards", "Red Cards", "Clean Sheets")
DEFAULT_GITHUB_REPO = "deepa-shalini-k/plotly-fifa-2026-app"
DEFAULT_GITHUB_REF = "main"
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 10

_REMOTE_SNAPSHOT_CACHE: dict[str, dict[str, object]] = {}
_RUNTIME_LEADERBOARD_CACHE: dict[str, object] = {}


def _empty_snapshot() -> dict:
    return {
        "snapshot_version": 1,
        "strict_build": False,
        "generated_at": "",
        "processed_match_ids": [],
        "metrics": {metric: [] for metric in EXPENSIVE_LEADERBOARD_METRICS},
    }


def _source() -> str:
    configured = os.environ.get("PLOTLY_FIFA_LEADERBOARDS_SOURCE") or os.environ.get("PLOTLY_FIFA_PREDICTIONS_SOURCE", "remote")
    return configured.strip().lower() or "remote"


def _cache_ttl_seconds() -> int:
    raw_value = os.environ.get("PLOTLY_FIFA_LEADERBOARDS_CACHE_TTL_SECONDS") or os.environ.get(
        "PLOTLY_FIFA_PREDICTIONS_CACHE_TTL_SECONDS",
        str(DEFAULT_CACHE_TTL_SECONDS),
    )
    try:
        return max(0, int(raw_value))
    except ValueError:
        return DEFAULT_CACHE_TTL_SECONDS


def _timeout_seconds() -> int:
    raw_value = os.environ.get("PLOTLY_FIFA_LEADERBOARDS_TIMEOUT_SECONDS") or os.environ.get(
        "PLOTLY_FIFA_PREDICTIONS_TIMEOUT_SECONDS",
        str(DEFAULT_TIMEOUT_SECONDS),
    )
    try:
        return max(1, int(raw_value))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _remote_url(path: Path = LEADERBOARD_SNAPSHOT_PATH) -> str:
    if base_url := os.environ.get("PLOTLY_FIFA_LEADERBOARDS_BASE_URL") or os.environ.get("PLOTLY_FIFA_PREDICTIONS_BASE_URL"):
        return f"{base_url.rstrip('/')}/{path.name}"

    repo = (
        os.environ.get("PLOTLY_FIFA_LEADERBOARDS_GITHUB_REPO")
        or os.environ.get("PLOTLY_FIFA_PREDICTIONS_GITHUB_REPO")
        or DEFAULT_GITHUB_REPO
    ).strip("/")
    ref = (
        os.environ.get("PLOTLY_FIFA_LEADERBOARDS_GITHUB_REF")
        or os.environ.get("PLOTLY_FIFA_PREDICTIONS_GITHUB_REF")
        or DEFAULT_GITHUB_REF
    ).strip("/") or DEFAULT_GITHUB_REF
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path.name}"


def _read_remote_text(path: Path = LEADERBOARD_SNAPSHOT_PATH) -> str:
    url = _remote_url(path)
    now = time.monotonic()
    ttl_seconds = _cache_ttl_seconds()
    cached = _REMOTE_SNAPSHOT_CACHE.get(url)

    if cached and ttl_seconds > 0 and now - float(cached["fetched_at"]) < ttl_seconds:
        return str(cached["text"])

    try:
        response = requests.get(url, timeout=_timeout_seconds())
        response.raise_for_status()
        response.encoding = "utf-8"
        text = response.text
        _REMOTE_SNAPSHOT_CACHE[url] = {"fetched_at": now, "text": text}
        return text
    except requests.RequestException as exc:
        if cached and cached.get("text") and not path.exists():
            logger.warning("Serving stale leaderboard snapshot from %s after %s", url, exc)
            return str(cached["text"])
        if path.exists():
            logger.warning("Falling back to bundled leaderboard snapshot %s after %s", path.name, exc)
            local_mtime = path.stat().st_mtime
            if cached and cached.get("text") and cached.get("local_mtime") == local_mtime:
                return str(cached["text"])
            text = path.read_text(encoding="utf-8")
            _REMOTE_SNAPSHOT_CACHE[url] = {"fetched_at": now, "text": text, "local_mtime": local_mtime}
            return text
        if cached and cached.get("text"):
            logger.warning("Serving stale leaderboard snapshot from %s after %s", url, exc)
            return str(cached["text"])
        logger.warning("Leaderboard snapshot %s unavailable from %s and no local fallback exists", path.name, url)
        return ""


def _normalize_snapshot(snapshot: dict | None) -> dict:
    from data import api

    payload = snapshot if isinstance(snapshot, dict) else {}
    metrics_payload = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    seen_match_ids: set[int] = set()
    processed_match_ids: list[int] = []
    for raw_match_id in payload.get("processed_match_ids", []) if isinstance(payload.get("processed_match_ids"), list) else []:
        match_id = api._coerce_match_id(raw_match_id)
        if match_id is None or match_id in seen_match_ids:
            continue
        seen_match_ids.add(match_id)
        processed_match_ids.append(match_id)

    normalized_metrics = {}
    for metric in EXPENSIVE_LEADERBOARD_METRICS:
        metric_rows = metrics_payload.get(metric, [])
        if not isinstance(metric_rows, list):
            normalized_metrics[metric] = []
            continue
        normalized_metrics[metric] = [row for row in metric_rows if isinstance(row, dict)]

    return {
        "snapshot_version": api._coerce_stat_number(payload.get("snapshot_version")) or 1,
        "strict_build": bool(payload.get("strict_build")),
        "generated_at": str(payload.get("generated_at") or ""),
        "processed_match_ids": sorted(processed_match_ids),
        "metrics": normalized_metrics,
    }


def load_persisted_snapshot() -> dict:
    if _source() == "local":
        if not LEADERBOARD_SNAPSHOT_PATH.exists():
            return _empty_snapshot()
        try:
            return _normalize_snapshot(json.loads(LEADERBOARD_SNAPSHOT_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read local leaderboard snapshot %s: %s", LEADERBOARD_SNAPSHOT_PATH.name, exc)
            return _empty_snapshot()

    payload = _read_remote_text()
    if not payload.strip():
        return _empty_snapshot()
    try:
        return _normalize_snapshot(json.loads(payload))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to decode leaderboard snapshot JSON: %s", exc)
        return _empty_snapshot()


def build_snapshot_from_current_api_state() -> dict:
    from data import api

    match_ids = api._completed_match_leaderboard_ids()
    return {
        "snapshot_version": 1,
        "strict_build": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "processed_match_ids": list(match_ids),
        "metrics": api._completed_match_leaderboards(match_ids) if match_ids else {metric: [] for metric in EXPENSIVE_LEADERBOARD_METRICS},
    }


def write_snapshot(snapshot: dict, path: Path = LEADERBOARD_SNAPSHOT_PATH) -> None:
    normalized_snapshot = _normalize_snapshot(snapshot)
    temp_name: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(path.parent),
            prefix=f".{path.stem}-",
            suffix=".tmp",
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write(json.dumps(normalized_snapshot, ensure_ascii=False, indent=2) + "\n")
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.remove(temp_name)


def _runtime_expensive_leaderboards() -> dict[str, list[dict]]:
    from data import api

    snapshot = load_persisted_snapshot()
    current_completed_ids = api._completed_match_leaderboard_ids()
    snapshot_is_strict = bool(snapshot.get("strict_build"))
    cache_key = (
        snapshot_is_strict,
        snapshot.get("generated_at", ""),
        tuple(snapshot.get("processed_match_ids", [])),
        current_completed_ids,
    )
    if _RUNTIME_LEADERBOARD_CACHE.get("key") == cache_key:
        return dict(_RUNTIME_LEADERBOARD_CACHE["boards"])

    snapshot_metrics = snapshot.get("metrics", {})
    snapshot_match_ids = tuple(snapshot.get("processed_match_ids", []))
    snapshot_match_id_set = set(snapshot_match_ids)

    if snapshot_is_strict and snapshot_metrics and current_completed_ids and set(current_completed_ids).issubset(snapshot_match_id_set):
        boards = snapshot_metrics
    elif snapshot_is_strict and snapshot_metrics and current_completed_ids:
        missing_match_ids = tuple(match_id for match_id in current_completed_ids if match_id not in snapshot_match_id_set)
        state = api._completed_match_leaderboard_state_from_rows(snapshot_metrics)
        can_apply_delta = True

        for match_id in missing_match_ids:
            match = api.get_match_detail(match_id, allow_known_fallback=False)
            if not match:
                can_apply_delta = False
                break
            api._apply_completed_match_to_leaderboard_state(state, match)

        boards = api._materialize_completed_match_leaderboards(state) if can_apply_delta else api._completed_match_leaderboards(current_completed_ids)
    elif current_completed_ids:
        boards = api._completed_match_leaderboards(current_completed_ids)
    else:
        boards = snapshot_metrics if snapshot_is_strict and any(snapshot_metrics.values()) else {metric: [] for metric in EXPENSIVE_LEADERBOARD_METRICS}

    _RUNTIME_LEADERBOARD_CACHE["key"] = cache_key
    _RUNTIME_LEADERBOARD_CACHE["boards"] = boards
    return dict(boards)


def get_expensive_leaderboard(metric: str) -> list[dict]:
    if metric not in EXPENSIVE_LEADERBOARD_METRICS:
        return []
    return _runtime_expensive_leaderboards().get(metric, [])
