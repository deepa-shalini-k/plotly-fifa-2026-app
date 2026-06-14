from __future__ import annotations

import os
import re
from collections import defaultdict

import pandas as pd
import requests

os.environ.setdefault("PLOTLY_FIFA_PREDICTIONS_SOURCE", "local")

from data.predictions import (
    ELO_SNAPSHOT_COLUMNS,
    ELO_SNAPSHOTS_PATH,
    MATCH_RESULT_COLUMNS,
    MATCH_RESULTS_PATH,
    TARGET_TEAMS,
    TEAM_TO_GROUP,
    WORLD_CUP_RESULTS_START_DATE,
    WORLD_CUP_TOURNAMENT_NAME,
    build_match_key,
    canonical_team_name,
    ensure_prediction_csvs,
    load_elo_snapshots,
)

BASE_URL = "https://www.eloratings.net"
TIMEOUT_SECONDS = 30
USER_AGENT = "plotly-fifa-predictions-scraper/1.0"
TEAM_NAMES_PATH = "en.teams.tsv"
TOURNAMENT_NAMES_PATH = "en.tournaments.tsv"
WORLD_RATINGS_PATH = "World.tsv"
LATEST_RESULTS_PATH = "latest.tsv"
GRAPH_PATH = "graph.tsv"
WORLD_CUP_TOURNAMENT_CODE = "WC"
GRAPH_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})(.*)$")
GRAPH_MONTH_RE = re.compile(r"^(\d{1,2})(\d{2})(.*)$")
GRAPH_DAY_RE = re.compile(r"^(\d{2})(.*)$")
GRAPH_MATCH_RE = re.compile(r"^([A-Z][A-Z])([A-Z][A-Z])(-?\d+)(.*)$")
GRAPH_TEAMS_RE = re.compile(r"^([A-Z][A-Z])([A-Z][A-Z])(.*)$")
GRAPH_TEAM_RE = re.compile(r"^([A-Z][A-Z])(-?\d+)(.*)$")


def _fetch_tsv(session: requests.Session, path: str) -> pd.DataFrame:
    payload = _fetch_text(session, path)
    if not payload:
        return pd.DataFrame()
    rows = [line.split("\t") for line in payload.splitlines() if line.strip()]
    return pd.DataFrame(rows)


def _fetch_text(session: requests.Session, path: str) -> str:
    response = session.get(f"{BASE_URL}/{path}", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text.strip()


def _parse_signed_int(value: str | int | float | None) -> int:
    cleaned = str(value or "").strip().replace("−", "-").replace("–", "-")
    if not cleaned:
        return 0
    return int(cleaned)


def _build_lookup(frame: pd.DataFrame) -> dict[str, str]:
    if frame.empty or frame.shape[1] < 2:
        return {}
    lookup = (
        frame.iloc[:, :2]
        .rename(columns={0: "code", 1: "label"})
        .replace("", pd.NA)
        .dropna(subset=["code", "label"])
    )
    return dict(zip(lookup["code"], lookup["label"], strict=False))


def _current_timestamp() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").floor("s")


def _should_skip_scrape(min_interval_minutes: int) -> tuple[bool, pd.Timestamp | None]:
    snapshots = load_elo_snapshots()
    if snapshots.empty:
        return False, None

    latest_scrape = snapshots["scraped_at"].max()
    if pd.isna(latest_scrape):
        return False, None

    age = _current_timestamp() - latest_scrape
    return age < pd.Timedelta(minutes=min_interval_minutes), latest_scrape


def _scrape_elo_snapshots(
    ratings_frame: pd.DataFrame,
    team_lookup: dict[str, str],
    scraped_at: str,
) -> pd.DataFrame:
    if ratings_frame.empty or ratings_frame.shape[1] < 4:
        raise ValueError("World.tsv did not include the expected rank/team/rating columns.")

    snapshots = ratings_frame.iloc[:, :4].copy()
    snapshots.columns = ["rank", "local_rank", "team_code", "elo_rating"]
    snapshots["team_name"] = snapshots["team_code"].map(team_lookup).fillna(snapshots["team_code"])
    snapshots["team"] = snapshots["team_name"].map(canonical_team_name)
    snapshots["rank"] = pd.to_numeric(snapshots["rank"], errors="coerce")
    snapshots["elo_rating"] = pd.to_numeric(snapshots["elo_rating"], errors="coerce")
    snapshots = snapshots.dropna(subset=["team", "rank", "elo_rating"]).copy()
    snapshots["rank"] = snapshots["rank"].astype(int)
    snapshots["elo_rating"] = snapshots["elo_rating"].astype(int)
    snapshots = snapshots.loc[:, ["team", "rank", "elo_rating"]]
    snapshots = snapshots.drop_duplicates(subset=["team"]).sort_values("rank")

    missing_teams = [team for team in TARGET_TEAMS if team not in set(snapshots["team"])]
    if missing_teams:
        raise ValueError(f"Missing World Cup teams in Elo ratings feed: {', '.join(missing_teams)}")

    snapshots["scraped_at"] = scraped_at
    snapshots = snapshots.loc[:, ELO_SNAPSHOT_COLUMNS]
    return snapshots


def _parse_graph_daily_deltas(graph_payload: str) -> tuple[dict[pd.Timestamp, dict[str, int]], pd.Timestamp | None]:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    started = False
    latest_date: pd.Timestamp | None = None
    daily_deltas: dict[pd.Timestamp, dict[str, int]] = {}

    for raw_line in graph_payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        date_match = GRAPH_DATE_RE.match(line)
        month_match = None
        day_match = None
        if date_match:
            parsed_year = int(date_match.group(1))
            if parsed_year < WORLD_CUP_RESULTS_START_DATE.year:
                continue

            started = True
            year = parsed_year
            month = int(date_match.group(2))
            day = int(date_match.group(3))
            line = date_match.group(4)
        elif not started:
            continue
        else:
            month_match = GRAPH_MONTH_RE.match(line)
            if month_match and year is not None:
                month = int(month_match.group(1))
                day = int(month_match.group(2))
                line = month_match.group(3)
            else:
                day_match = GRAPH_DAY_RE.match(line)
                if day_match and year is not None and month is not None:
                    day = int(day_match.group(1))
                    line = day_match.group(2)
                else:
                    continue

        if year is None or month is None or day is None:
            continue

        current_date = pd.Timestamp(year=year, month=month, day=1) + pd.Timedelta(days=day - 1)
        latest_date = current_date
        if current_date < WORLD_CUP_RESULTS_START_DATE:
            continue

        deltas = daily_deltas.setdefault(current_date, defaultdict(int))
        remaining = line
        while remaining:
            match = GRAPH_MATCH_RE.match(remaining)
            if match:
                code_1, code_2, inc_raw, remaining = match.groups()
                inc = int(inc_raw)
                deltas[code_1] += inc
                deltas[code_2] -= inc
                continue

            teams_match = GRAPH_TEAMS_RE.match(remaining)
            if teams_match:
                # Team-code rename and retirement markers are rare and none are
                # expected for the 2026 tournament window, so we skip them here.
                _, _, remaining = teams_match.groups()
                continue

            team_match = GRAPH_TEAM_RE.match(remaining)
            if team_match:
                code, inc_raw, remaining = team_match.groups()
                deltas[code] += int(inc_raw)
                continue

            raise ValueError(f"Unable to parse graph payload near: {remaining[:30]}")

    normalized = {date: dict(delta_map) for date, delta_map in daily_deltas.items()}
    return normalized, latest_date


def _build_current_world_state(
    ratings_frame: pd.DataFrame,
    team_lookup: dict[str, str],
) -> tuple[dict[str, int], dict[str, int], dict[str, str]]:
    current = ratings_frame.iloc[:, :4].copy()
    current.columns = ["rank", "local_rank", "team_code", "elo_rating"]
    current["elo_rating"] = pd.to_numeric(current["elo_rating"], errors="coerce")
    current["rank"] = pd.to_numeric(current["rank"], errors="coerce")
    current = current.dropna(subset=["team_code", "elo_rating", "rank"]).copy()
    current["team_code"] = current["team_code"].astype(str)
    current["elo_rating"] = current["elo_rating"].astype(int)
    current["rank"] = current["rank"].astype(int)
    current = current.sort_values("rank")

    world_ratings = dict(zip(current["team_code"], current["elo_rating"], strict=False))
    world_ranks = dict(zip(current["team_code"], current["rank"], strict=False))
    target_codes: dict[str, str] = {}
    for row in current.itertuples(index=False):
        site_name = team_lookup.get(row.team_code, row.team_code)
        canonical_name = canonical_team_name(site_name)
        if canonical_name:
            target_codes[row.team_code] = canonical_name

    missing_teams = [team for team in TARGET_TEAMS if team not in set(target_codes.values())]
    if missing_teams:
        raise ValueError(f"Missing World Cup teams in current ratings feed: {', '.join(missing_teams)}")

    return world_ratings, world_ranks, target_codes


def _rank_lookup_from_ratings(
    world_ratings: dict[str, int],
    current_world_rank_order: dict[str, int],
) -> dict[str, int]:
    sorted_codes = sorted(
        world_ratings,
        key=lambda code: (-world_ratings[code], current_world_rank_order.get(code, 9999), code),
    )
    return {code: position for position, code in enumerate(sorted_codes, start=1)}


def _build_backfill_elo_snapshots(
    ratings_frame: pd.DataFrame,
    graph_payload: str,
    team_lookup: dict[str, str],
) -> pd.DataFrame:
    daily_deltas, latest_graph_date = _parse_graph_daily_deltas(graph_payload)
    if not daily_deltas or latest_graph_date is None:
        return pd.DataFrame(columns=ELO_SNAPSHOT_COLUMNS)

    world_ratings, current_world_rank_order, target_codes = _build_current_world_state(ratings_frame, team_lookup)
    working_ratings = world_ratings.copy()
    rows: list[dict[str, object]] = []

    for snapshot_date in sorted(daily_deltas.keys(), reverse=True):
        rank_lookup = _rank_lookup_from_ratings(working_ratings, current_world_rank_order)
        scraped_at = f"{snapshot_date.strftime('%Y-%m-%d')}T23:59:59+00:00"
        for code, team_name in target_codes.items():
            team_rating = working_ratings.get(code)
            team_rank = rank_lookup.get(code)
            if team_rating is None or team_rank is None:
                raise ValueError(f"Missing reconstructed rating state for {team_name} on {snapshot_date.date()}")

            rows.append(
                {
                    "scraped_at": scraped_at,
                    "team": team_name,
                    "rank": int(team_rank),
                    "elo_rating": int(team_rating),
                }
            )

        for code, delta in daily_deltas[snapshot_date].items():
            if code in working_ratings:
                working_ratings[code] -= delta

    return pd.DataFrame(rows, columns=ELO_SNAPSHOT_COLUMNS)


def _existing_match_keys() -> set[str]:
    ensure_prediction_csvs()
    existing = _prune_match_results_file()
    if existing.empty:
        return set()

    existing = existing.dropna(subset=["match_date", "team", "opponent"]).copy()
    return {
        build_match_key(str(row.match_date), str(row.team), str(row.opponent))
        for row in existing.itertuples(index=False)
    }


def _prune_match_results_file() -> pd.DataFrame:
    ensure_prediction_csvs()
    existing = pd.read_csv(MATCH_RESULTS_PATH)
    if existing.empty:
        empty = pd.DataFrame(columns=MATCH_RESULT_COLUMNS)
        empty.to_csv(MATCH_RESULTS_PATH, index=False)
        return empty

    for column in MATCH_RESULT_COLUMNS:
        if column not in existing.columns:
            existing[column] = pd.NA

    existing = existing.loc[:, MATCH_RESULT_COLUMNS].copy()
    existing["match_date"] = pd.to_datetime(existing["match_date"], errors="coerce")
    existing = existing.dropna(subset=["match_date", "team", "opponent", "tournament"]).copy()
    existing["match_date"] = existing["match_date"].dt.normalize()
    existing = existing[
        (existing["team"].isin(TARGET_TEAMS))
        & (existing["tournament"] == WORLD_CUP_TOURNAMENT_NAME)
        & (existing["match_date"] >= WORLD_CUP_RESULTS_START_DATE)
    ].copy()
    existing["group"] = existing["team"].map(TEAM_TO_GROUP)
    existing = existing.drop_duplicates(subset=["match_date", "team", "opponent"], keep="last")
    existing = existing.dropna(subset=["group"])
    existing = existing.sort_values(["match_date", "team", "opponent"])
    if existing.empty:
        empty = pd.DataFrame(columns=MATCH_RESULT_COLUMNS)
        empty.to_csv(MATCH_RESULTS_PATH, index=False)
        return empty

    existing["match_date"] = existing["match_date"].dt.strftime("%Y-%m-%d")
    existing.to_csv(MATCH_RESULTS_PATH, index=False)
    return existing


def _prune_elo_snapshots_file() -> pd.DataFrame:
    ensure_prediction_csvs()
    existing = pd.read_csv(ELO_SNAPSHOTS_PATH)
    if existing.empty:
        empty = pd.DataFrame(columns=ELO_SNAPSHOT_COLUMNS)
        empty.to_csv(ELO_SNAPSHOTS_PATH, index=False)
        return empty

    for column in ELO_SNAPSHOT_COLUMNS:
        if column not in existing.columns:
            existing[column] = pd.NA

    existing = existing.loc[:, ELO_SNAPSHOT_COLUMNS].copy()
    existing["scraped_at"] = pd.to_datetime(existing["scraped_at"], utc=True, errors="coerce")
    existing["rank"] = pd.to_numeric(existing["rank"], errors="coerce")
    existing["elo_rating"] = pd.to_numeric(existing["elo_rating"], errors="coerce")
    existing = existing.dropna(subset=["scraped_at", "team", "rank", "elo_rating"]).copy()
    existing = existing[existing["team"].isin(TARGET_TEAMS)].copy()
    existing = existing.drop_duplicates(subset=["scraped_at", "team"], keep="last")
    existing = existing.sort_values(["scraped_at", "rank", "team"])
    if existing.empty:
        empty = pd.DataFrame(columns=ELO_SNAPSHOT_COLUMNS)
        empty.to_csv(ELO_SNAPSHOTS_PATH, index=False)
        return empty

    existing["scraped_at"] = existing["scraped_at"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    existing["scraped_at"] = existing["scraped_at"].str.replace(r"(\+0000)$", "+00:00", regex=True)
    existing["rank"] = existing["rank"].astype(int)
    existing["elo_rating"] = existing["elo_rating"].astype(int)
    existing.to_csv(ELO_SNAPSHOTS_PATH, index=False)
    return existing


def _snapshot_payload_changed(existing_snapshots: pd.DataFrame, snapshot_rows: pd.DataFrame) -> bool:
    if existing_snapshots.empty:
        return True

    latest_scrape = existing_snapshots["scraped_at"].max()
    latest_rows = existing_snapshots[existing_snapshots["scraped_at"] == latest_scrape].copy()
    latest_rows = latest_rows.loc[:, ["team", "rank", "elo_rating"]].sort_values("team").reset_index(drop=True)
    candidate_rows = snapshot_rows.loc[:, ["team", "rank", "elo_rating"]].sort_values("team").reset_index(drop=True)
    return not latest_rows.equals(candidate_rows)


def _scrape_match_results(
    results_frame: pd.DataFrame,
    team_lookup: dict[str, str],
    tournament_lookup: dict[str, str],
    existing_keys: set[str],
) -> pd.DataFrame:
    if results_frame.empty or results_frame.shape[1] < 16:
        return pd.DataFrame(columns=MATCH_RESULT_COLUMNS)

    results = results_frame.iloc[:, :16].copy()
    results.columns = [
        "year",
        "month",
        "day",
        "team_code",
        "opponent_code",
        "team_score",
        "opponent_score",
        "tournament_code",
        "venue_code",
        "elo_change",
        "team_new_elo",
        "opponent_new_elo",
        "team_rank_change",
        "opponent_rank_change",
        "team_new_rank",
        "opponent_new_rank",
    ]
    results["team_name"] = results["team_code"].map(team_lookup).fillna(results["team_code"])
    results["opponent_name"] = results["opponent_code"].map(team_lookup).fillna(results["opponent_code"])
    results["team"] = results["team_name"].map(canonical_team_name)
    results["opponent"] = results["opponent_name"].map(canonical_team_name)
    results = results[(results["team"].notna()) | (results["opponent"].notna())].copy()

    if results.empty:
        return pd.DataFrame(columns=MATCH_RESULT_COLUMNS)

    results["match_date"] = pd.to_datetime(
        {
            "year": pd.to_numeric(results["year"], errors="coerce"),
            "month": pd.to_numeric(results["month"], errors="coerce"),
            "day": pd.to_numeric(results["day"], errors="coerce"),
        },
        errors="coerce",
    )
    results["team_score"] = pd.to_numeric(results["team_score"], errors="coerce")
    results["opponent_score"] = pd.to_numeric(results["opponent_score"], errors="coerce")
    results = results.dropna(subset=["match_date", "team_score", "opponent_score"]).copy()
    results["match_date"] = results["match_date"].dt.normalize()
    results = results[
        (results["tournament_code"] == WORLD_CUP_TOURNAMENT_CODE)
        & (results["match_date"] >= WORLD_CUP_RESULTS_START_DATE)
    ].copy()
    results["match_date"] = results["match_date"].dt.strftime("%Y-%m-%d")

    rows: list[dict[str, object]] = []
    new_match_keys: set[str] = set()

    for result in results.itertuples(index=False):
        primary_team = result.team or result.team_name
        secondary_team = result.opponent or result.opponent_name
        match_key = build_match_key(str(result.match_date), str(primary_team), str(secondary_team))
        if match_key in existing_keys or match_key in new_match_keys:
            continue

        elo_change = _parse_signed_int(result.elo_change)
        team_rank_change = _parse_signed_int(result.team_rank_change)
        opponent_rank_change = _parse_signed_int(result.opponent_rank_change)
        tournament = tournament_lookup.get(result.tournament_code, result.tournament_code)
        match_rows: list[dict[str, object]] = []

        if result.team:
            match_rows.append(
                {
                    "match_date": result.match_date,
                    "team": result.team,
                    "opponent": result.opponent or result.opponent_name,
                    "team_score": int(result.team_score),
                    "opponent_score": int(result.opponent_score),
                    "tournament": tournament,
                    "elo_change": elo_change,
                    "new_elo": _parse_signed_int(result.team_new_elo),
                    "rank_change": team_rank_change,
                    "new_rank": _parse_signed_int(result.team_new_rank),
                    "group": TEAM_TO_GROUP[result.team],
                }
            )

        if result.opponent:
            match_rows.append(
                {
                    "match_date": result.match_date,
                    "team": result.opponent,
                    "opponent": result.team or result.team_name,
                    "team_score": int(result.opponent_score),
                    "opponent_score": int(result.team_score),
                    "tournament": tournament,
                    "elo_change": -elo_change,
                    "new_elo": _parse_signed_int(result.opponent_new_elo),
                    "rank_change": opponent_rank_change,
                    "new_rank": _parse_signed_int(result.opponent_new_rank),
                    "group": TEAM_TO_GROUP[result.opponent],
                }
            )

        if match_rows:
            rows.extend(match_rows)
            new_match_keys.add(match_key)

    if not rows:
        return pd.DataFrame(columns=MATCH_RESULT_COLUMNS)

    return pd.DataFrame(rows, columns=MATCH_RESULT_COLUMNS)


def run_scrape(*, force: bool = False, min_interval_minutes: int = 30) -> dict[str, object]:
    ensure_prediction_csvs()
    should_skip, latest_scrape = _should_skip_scrape(min_interval_minutes)
    if should_skip and not force:
        latest_label = latest_scrape.isoformat() if latest_scrape is not None else "unknown"
        print(
            f"[{_current_timestamp().isoformat()}] Predictions scrape skipped | "
            f"last snapshot {latest_label} is newer than {min_interval_minutes} minutes."
        )
        return {
            "status": "skipped",
            "scraped_at": latest_label,
            "ratings_appended": 0,
            "match_rows_appended": 0,
            "new_matches": 0,
        }

    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})
        team_names = _fetch_tsv(session, TEAM_NAMES_PATH)
        tournament_names = _fetch_tsv(session, TOURNAMENT_NAMES_PATH)
        ratings = _fetch_tsv(session, WORLD_RATINGS_PATH)
        latest_results = _fetch_tsv(session, LATEST_RESULTS_PATH)
        graph_payload = _fetch_text(session, GRAPH_PATH)

    team_lookup = _build_lookup(team_names)
    tournament_lookup = _build_lookup(tournament_names)
    existing_match_keys = _existing_match_keys()
    scraped_at_ts = _current_timestamp()
    scraped_at = scraped_at_ts.isoformat()

    backfill_snapshot_rows = _build_backfill_elo_snapshots(ratings, graph_payload, team_lookup)
    current_snapshot_rows = _scrape_elo_snapshots(ratings, team_lookup, scraped_at)
    new_match_rows = _scrape_match_results(latest_results, team_lookup, tournament_lookup, existing_match_keys)

    existing_snapshots = _prune_elo_snapshots_file()
    snapshot_rows = (
        current_snapshot_rows
        if _snapshot_payload_changed(existing_snapshots, current_snapshot_rows)
        else pd.DataFrame(columns=ELO_SNAPSHOT_COLUMNS)
    )
    snapshot_export = pd.concat([existing_snapshots, backfill_snapshot_rows, snapshot_rows], ignore_index=True)
    snapshot_export = snapshot_export.drop_duplicates(subset=["scraped_at", "team"], keep="last")
    snapshot_export = snapshot_export.sort_values(["scraped_at", "rank", "team"])
    snapshot_export.to_csv(ELO_SNAPSHOTS_PATH, index=False)

    existing_results = _prune_match_results_file()
    if not new_match_rows.empty:
        results_export = pd.concat([existing_results, new_match_rows], ignore_index=True)
    else:
        results_export = existing_results
    results_export.to_csv(MATCH_RESULTS_PATH, index=False)

    new_match_count = (
        new_match_rows.apply(
            lambda row: build_match_key(str(row["match_date"]), str(row["team"]), str(row["opponent"])),
            axis=1,
        ).nunique()
        if not new_match_rows.empty
        else 0
    )
    print(
        f"[{scraped_at}] Predictions scrape complete | "
        f"elo snapshot rows: {len(snapshot_rows)} | "
        f"match rows appended: {len(new_match_rows)} | "
        f"new matches captured: {new_match_count}"
    )
    return {
        "status": "completed",
        "scraped_at": scraped_at,
        "ratings_appended": int(len(snapshot_rows)),
        "match_rows_appended": int(len(new_match_rows)),
        "new_matches": int(new_match_count),
    }


if __name__ == "__main__":
    run_scrape(force=True)
