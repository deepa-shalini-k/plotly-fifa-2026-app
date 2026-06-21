from __future__ import annotations

import datetime as dt
import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from data import api, leaderboard_snapshots

CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 30
REQUEST_RETRY_TOTAL = 4
REQUEST_RETRY_BACKOFF_FACTOR = 1.5
REQUEST_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
USER_AGENT = "plotly-fifa-leaderboard-builder/1.0"
DETAIL_REQUEST_MAX_ATTEMPTS = 8
DETAIL_REQUEST_MIN_SPACING_SECONDS = 1.0

LOGGER = logging.getLogger(__name__)


def _build_session() -> requests.Session:
    retry_strategy = Retry(
        total=REQUEST_RETRY_TOTAL,
        connect=REQUEST_RETRY_TOTAL,
        read=REQUEST_RETRY_TOTAL,
        status=REQUEST_RETRY_TOTAL,
        allowed_methods=frozenset({"GET"}),
        backoff_factor=REQUEST_RETRY_BACKOFF_FACTOR,
        status_forcelist=REQUEST_RETRY_STATUS_CODES,
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, **api.UNFOLD_HEADERS})
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _fetch_completed_matches(session: requests.Session) -> list[dict]:
    response = session.get(
        f"{api.BASE_URL}/competitions/{api.WC_CODE}/matches",
        params={"season": api.WC_SEASON},
        timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    payload = response.json()
    matches = payload.get("matches", [])
    completed_matches = []

    for match in matches:
        if str(match.get("status") or "").upper() not in api.COMPLETED_STATUSES:
            continue
        match_id = api._coerce_match_id(match.get("id"))
        if match_id is None:
            continue
        completed_matches.append(api._normalize_match(match))

    completed_matches.sort(key=lambda match: (match.get("utcDate", ""), api._coerce_match_id(match.get("id")) or 0))
    return completed_matches


def _fetch_match_detail(session: requests.Session, match_id: int) -> dict:
    delay_seconds = DETAIL_REQUEST_MIN_SPACING_SECONDS

    for attempt in range(1, DETAIL_REQUEST_MAX_ATTEMPTS + 1):
        response = session.get(
            f"{api.BASE_URL}/matches/{match_id}",
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        )
        if response.status_code != 429:
            response.raise_for_status()
            time.sleep(DETAIL_REQUEST_MIN_SPACING_SECONDS)
            return api._normalize_match(response.json())

        retry_after = response.headers.get("Retry-After")
        wait_seconds = delay_seconds
        if retry_after is not None:
            try:
                wait_seconds = max(wait_seconds, float(retry_after))
            except ValueError:
                pass

        LOGGER.warning(
            "football-data rate limited match %s detail on attempt %s/%s; waiting %.1fs",
            match_id,
            attempt,
            DETAIL_REQUEST_MAX_ATTEMPTS,
            wait_seconds,
        )
        time.sleep(wait_seconds)
        delay_seconds = min(delay_seconds * 2, 60.0)

    response.raise_for_status()
    return {}


def build_snapshot() -> dict:
    if not api.API_KEY:
        raise ValueError("FOOTBALL_DATA_API_KEY is required to build leaderboard snapshots.")

    with _build_session() as session:
        completed_matches = _fetch_completed_matches(session)
        snapshot = leaderboard_snapshots.load_persisted_snapshot()
        snapshot_is_strict = bool(snapshot.get("strict_build"))
        snapshot_match_ids = tuple(snapshot.get("processed_match_ids", [])) if snapshot_is_strict else ()
        state = (
            api._completed_match_leaderboard_state_from_rows(snapshot.get("metrics"))
            if snapshot_is_strict
            else api._empty_completed_match_leaderboard_state()
        )
        processed_match_ids = list(snapshot_match_ids)
        seen_match_ids = set(processed_match_ids)

        for match in completed_matches:
            match_id = api._coerce_match_id(match.get("id"))
            if match_id is None or match_id in seen_match_ids:
                continue
            detail = _fetch_match_detail(session, match_id)
            api._apply_completed_match_to_leaderboard_state(state, detail)
            processed_match_ids.append(match_id)
            seen_match_ids.add(match_id)

        processed_match_ids.sort()

    return {
        "snapshot_version": 1,
        "strict_build": True,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "processed_match_ids": processed_match_ids,
        "metrics": api._materialize_completed_match_leaderboards(state),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    snapshot = build_snapshot()
    leaderboard_snapshots.write_snapshot(snapshot)
    LOGGER.info(
        "Wrote %s with %s completed matches",
        leaderboard_snapshots.LEADERBOARD_SNAPSHOT_PATH.name,
        len(snapshot["processed_match_ids"]),
    )


if __name__ == "__main__":
    main()
