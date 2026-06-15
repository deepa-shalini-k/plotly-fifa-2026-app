from __future__ import annotations

import logging
import math
import os
import tempfile
import time
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

os.environ.setdefault("PLOTLY_FIFA_PREDICTIONS_SOURCE", "local")

from data.api import API_KEY, WC_CODE, WC_SEASON, get_completed_matches
from data.predictions import (
    ELO_SNAPSHOT_COLUMNS,
    ELO_SNAPSHOTS_PATH,
    MATCH_RESULT_COLUMNS,
    MATCH_RESULTS_PATH,
    TARGET_TEAMS,
    TEAM_TO_GROUP,
    WORLD_CUP_RESULTS_START_DATE,
    WORLD_CUP_TOURNAMENT_NAME,
    canonical_team_name,
    ensure_prediction_csvs,
    load_elo_snapshots,
    load_match_results,
)

FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 30
REQUEST_RETRY_TOTAL = 4
REQUEST_RETRY_BACKOFF_FACTOR = 1.5
REQUEST_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
SCRAPE_MAX_ATTEMPTS = 3
SCRAPE_RETRY_BACKOFF_BASE_SECONDS = 5
USER_AGENT = "plotly-fifa-predictions-scraper/2.0"
SYNTHETIC_WORLD_RANK_LIMIT = 250

LOGGER = logging.getLogger(__name__)

# The tournament is co-hosted, so nominal home/away is not enough for Elo's
# +100 adjustment. We only apply it when the venue country matches the team.
VENUE_HOST_CONTEXT = (
    ("new york new jersey stadium", ("USA", "America/New_York")),
    ("san francisco bay area stadium", ("USA", "America/Los_Angeles")),
    ("los angeles stadium", ("USA", "America/Los_Angeles")),
    ("kansas city stadium", ("USA", "America/Chicago")),
    ("philadelphia stadium", ("USA", "America/New_York")),
    ("mexico city stadium", ("Mexico", "America/Mexico_City")),
    ("guadalajara stadium", ("Mexico", "America/Mexico_City")),
    ("monterrey stadium", ("Mexico", "America/Monterrey")),
    ("vancouver stadium", ("Canada", "America/Vancouver")),
    ("toronto stadium", ("Canada", "America/Toronto")),
    ("metlife stadium", ("USA", "America/New_York")),
    ("levi s stadium", ("USA", "America/Los_Angeles")),
    ("lincoln financial field", ("USA", "America/New_York")),
    ("mercedes benz stadium", ("USA", "America/New_York")),
    ("hard rock stadium", ("USA", "America/New_York")),
    ("gillette stadium", ("USA", "America/New_York")),
    ("arrowhead stadium", ("USA", "America/Chicago")),
    ("lumen field", ("USA", "America/Los_Angeles")),
    ("at t stadium", ("USA", "America/Chicago")),
    ("sofi stadium", ("USA", "America/Los_Angeles")),
    ("bmo field", ("Canada", "America/Toronto")),
    ("bc place", ("Canada", "America/Vancouver")),
    ("nrg stadium", ("USA", "America/Chicago")),
    ("azteca", ("Mexico", "America/Mexico_City")),
    ("akron", ("Mexico", "America/Mexico_City")),
    ("bbva", ("Mexico", "America/Monterrey")),
)
HOST_TEAM_BY_COUNTRY = {"USA": "USA", "Canada": "Canada", "Mexico": "Mexico"}


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
    session.headers.update({"User-Agent": USER_AGENT, "X-Auth-Token": API_KEY or ""})
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _current_timestamp() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").floor("s")


def _retry_sleep_seconds(attempt_number: int) -> int:
    return SCRAPE_RETRY_BACKOFF_BASE_SECONDS * (2 ** max(attempt_number - 1, 0))


def _write_csv_atomically(frame: pd.DataFrame, path) -> None:
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            delete=False,
            dir=str(path.parent),
            prefix=f".{path.stem}-",
            suffix=".tmp",
        ) as temp_file:
            temp_name = temp_file.name
            frame.to_csv(temp_file, index=False)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.remove(temp_name)


def _round_half_away_from_zero(value: float) -> int:
    if value >= 0:
        return int(math.floor(value + 0.5))
    return -int(math.floor(abs(value) + 0.5))


def _goal_difference_multiplier(goal_difference: int) -> float:
    if goal_difference <= 1:
        return 1.0
    if goal_difference == 2:
        return 1.5
    if goal_difference == 3:
        return 1.75
    return 1.75 + ((goal_difference - 3) / 8)


def _coerce_timestamp(value) -> pd.Timestamp | None:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp


def _normalize_venue_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = str(value).casefold()
    normalized = normalized.replace("&", " and ").replace("'", " ")
    return " ".join("".join(char if char.isalnum() else " " for char in normalized).split())


def _venue_context(venue: str | None) -> tuple[str | None, str | None]:
    venue_key = _normalize_venue_key(venue)
    if not venue_key:
        return None, None

    for keyword, context in VENUE_HOST_CONTEXT:
        if keyword in venue_key:
            return context
    return None, None


def _match_local_date(match: dict) -> pd.Timestamp:
    kickoff = _coerce_timestamp(match.get("utcDate"))
    if kickoff is None:
        raise ValueError(f"Completed match {match.get('id')} is missing a valid utcDate.")

    _, timezone_name = _venue_context(match.get("venue"))
    if timezone_name:
        kickoff = kickoff.tz_convert(ZoneInfo(timezone_name))
    return kickoff.normalize().tz_localize(None)


def _match_checkpoint_timestamp(match: dict, checkpoint_index: int) -> pd.Timestamp:
    kickoff = _coerce_timestamp(match.get("utcDate"))
    if kickoff is None:
        kickoff = _current_timestamp()
    return (kickoff + pd.Timedelta(seconds=checkpoint_index)).floor("s")


def _match_score(match: dict) -> tuple[int, int]:
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    full_time = score.get("fullTime") if isinstance(score.get("fullTime"), dict) else {}
    home = full_time.get("home")
    away = full_time.get("away")
    if home is None or away is None:
        raise ValueError(f"Completed match {match.get('id')} is missing a full-time score.")
    return int(home), int(away)


def _home_advantage(match: dict, home_team: str, away_team: str) -> int:
    venue_country, _ = _venue_context(match.get("venue"))
    if not venue_country:
        return 0

    home_host_team = HOST_TEAM_BY_COUNTRY.get(venue_country)
    if home_host_team == home_team:
        return 100
    if home_host_team == away_team:
        return -100
    return 0


def _fetch_completed_world_cup_matches() -> list[dict]:
    if not API_KEY:
        raise ValueError("FOOTBALL_DATA_API_KEY is required for the Elo refresh job.")

    try:
        with _build_session() as session:
            response = session.get(
                f"{FOOTBALL_DATA_BASE_URL}/competitions/{WC_CODE}/matches",
                params={"season": WC_SEASON},
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            )
            response.raise_for_status()
            payload = response.json()
            matches = payload.get("matches", [])
    except Exception as exc:
        LOGGER.warning("Live football-data fetch failed, falling back to cached completed matches: %s", exc)
        matches = get_completed_matches()

    completed = []
    for match in matches:
        if str(match.get("status") or "").upper() != "FINISHED":
            continue
        if _coerce_timestamp(match.get("utcDate")) is None:
            continue
        completed.append(match)

    completed.sort(
        key=lambda match: (
            _coerce_timestamp(match.get("utcDate")) or pd.Timestamp.max.tz_localize("UTC"),
            int(match.get("id") or 0),
        )
    )
    return completed


def _baseline_snapshot_rows(existing_snapshots: pd.DataFrame) -> tuple[pd.Timestamp, pd.DataFrame]:
    if existing_snapshots.empty:
        raise ValueError("elo_snapshots.csv is empty; the 11 June baseline is required for recalculation.")

    team_counts = existing_snapshots.groupby("scraped_at")["team"].nunique()
    full_snapshots = team_counts[team_counts >= len(TARGET_TEAMS)]
    if full_snapshots.empty:
        raise ValueError("No complete 48-team Elo snapshot is available for baseline reconstruction.")

    baseline_scraped_at = full_snapshots.sort_index().index[0]
    baseline_rows = existing_snapshots[existing_snapshots["scraped_at"] == baseline_scraped_at].copy()
    baseline_rows = baseline_rows.loc[:, ["team", "rank", "elo_rating"]].drop_duplicates(subset=["team"], keep="last")
    baseline_rows = baseline_rows.sort_values(["rank", "team"]).reset_index(drop=True)

    missing_teams = sorted(set(TARGET_TEAMS) - set(baseline_rows["team"]))
    if missing_teams:
        raise ValueError(f"Baseline snapshot is missing teams: {', '.join(missing_teams)}")

    return pd.Timestamp(baseline_scraped_at), baseline_rows


def _build_frozen_world_state(baseline_rows: pd.DataFrame) -> tuple[dict[str, int], dict[str, float], dict[str, int]]:
    team_ratings = {row.team: int(row.elo_rating) for row in baseline_rows.itertuples(index=False)}
    world_ratings: dict[str, float] = {}
    baseline_order: dict[str, int] = {}
    insertion_index = 0
    previous_rank: int | None = None
    previous_rating: int | None = None

    for row in baseline_rows.itertuples(index=False):
        current_rank = int(row.rank)
        current_rating = int(row.elo_rating)
        if previous_rank is not None and current_rank - previous_rank > 1:
            gap = current_rank - previous_rank - 1
            for offset in range(1, gap + 1):
                synthetic_name = f"__world_rank_{previous_rank + offset}__"
                interpolated_rating = previous_rating + ((current_rating - previous_rating) * (offset / (gap + 1)))
                world_ratings[synthetic_name] = float(interpolated_rating)
                baseline_order[synthetic_name] = insertion_index
                insertion_index += 1

        world_ratings[row.team] = float(current_rating)
        baseline_order[row.team] = insertion_index
        insertion_index += 1
        previous_rank = current_rank
        previous_rating = current_rating

    if previous_rank is None or previous_rating is None:
        raise ValueError("Baseline Elo snapshot did not include any rows.")

    for rank in range(previous_rank + 1, SYNTHETIC_WORLD_RANK_LIMIT + 1):
        synthetic_name = f"__world_rank_{rank}__"
        world_ratings[synthetic_name] = float(previous_rating - (rank - previous_rank))
        baseline_order[synthetic_name] = insertion_index
        insertion_index += 1

    return team_ratings, world_ratings, baseline_order


def _rank_lookup_from_world_ratings(
    world_ratings: dict[str, float],
    baseline_order: dict[str, int],
) -> dict[str, int]:
    ordered_entities = sorted(
        world_ratings,
        key=lambda entity: (-world_ratings[entity], baseline_order.get(entity, 999_999), entity),
    )
    return {entity: position for position, entity in enumerate(ordered_entities, start=1)}


def _home_elo_delta(
    *,
    home_rating: int,
    away_rating: int,
    home_goals: int,
    away_goals: int,
    home_advantage: int,
) -> int:
    goal_difference = abs(home_goals - away_goals)
    adjusted_k = 60 * _goal_difference_multiplier(goal_difference)
    if home_goals > away_goals:
        result = 1.0
    elif home_goals < away_goals:
        result = 0.0
    else:
        result = 0.5

    rating_delta = (home_rating - away_rating) + home_advantage
    expected_result = 1 / (10 ** (-rating_delta / 400) + 1)
    return _round_half_away_from_zero(adjusted_k * (result - expected_result))


def _results_and_snapshots_from_matches(
    matches: list[dict],
    *,
    baseline_day: pd.Timestamp,
    team_ratings: dict[str, int],
    world_ratings: dict[str, float],
    baseline_order: dict[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    result_rows: list[dict[str, object]] = []
    snapshot_rows: list[dict[str, object]] = []
    checkpoint_index = 0

    for match in matches:
        local_match_day = _match_local_date(match)
        if local_match_day <= baseline_day:
            continue

        home_name = canonical_team_name(match.get("homeTeam", {}).get("name"))
        away_name = canonical_team_name(match.get("awayTeam", {}).get("name"))
        if not home_name or not away_name:
            LOGGER.warning(
                "Skipping finished match %s because one side could not be mapped: %s vs %s",
                match.get("id"),
                match.get("homeTeam", {}).get("name"),
                match.get("awayTeam", {}).get("name"),
            )
            continue
        if home_name not in team_ratings or away_name not in team_ratings:
            LOGGER.warning("Skipping finished match %s because a mapped side is missing from the baseline table.", match.get("id"))
            continue

        checkpoint_index += 1
        home_goals, away_goals = _match_score(match)
        pre_match_ranks = _rank_lookup_from_world_ratings(world_ratings, baseline_order)
        pre_home_rank = int(pre_match_ranks[home_name])
        pre_away_rank = int(pre_match_ranks[away_name])
        home_delta = _home_elo_delta(
            home_rating=team_ratings[home_name],
            away_rating=team_ratings[away_name],
            home_goals=home_goals,
            away_goals=away_goals,
            home_advantage=_home_advantage(match, home_name, away_name),
        )

        team_ratings[home_name] += home_delta
        team_ratings[away_name] -= home_delta
        world_ratings[home_name] = float(team_ratings[home_name])
        world_ratings[away_name] = float(team_ratings[away_name])

        post_match_ranks = _rank_lookup_from_world_ratings(world_ratings, baseline_order)
        post_home_rank = int(post_match_ranks[home_name])
        post_away_rank = int(post_match_ranks[away_name])
        local_match_date = local_match_day.strftime("%Y-%m-%d")

        result_rows.extend(
            [
                {
                    "match_date": local_match_date,
                    "team": home_name,
                    "opponent": away_name,
                    "team_score": int(home_goals),
                    "opponent_score": int(away_goals),
                    "tournament": WORLD_CUP_TOURNAMENT_NAME,
                    "elo_change": int(home_delta),
                    "new_elo": int(team_ratings[home_name]),
                    "rank_change": int(pre_home_rank - post_home_rank),
                    "new_rank": post_home_rank,
                    "group": TEAM_TO_GROUP[home_name],
                },
                {
                    "match_date": local_match_date,
                    "team": away_name,
                    "opponent": home_name,
                    "team_score": int(away_goals),
                    "opponent_score": int(home_goals),
                    "tournament": WORLD_CUP_TOURNAMENT_NAME,
                    "elo_change": int(-home_delta),
                    "new_elo": int(team_ratings[away_name]),
                    "rank_change": int(pre_away_rank - post_away_rank),
                    "new_rank": post_away_rank,
                    "group": TEAM_TO_GROUP[away_name],
                },
            ]
        )

        checkpoint_timestamp = _match_checkpoint_timestamp(match, checkpoint_index)
        for team in TARGET_TEAMS:
            snapshot_rows.append(
                {
                    "scraped_at": checkpoint_timestamp,
                    "team": team,
                    "rank": int(post_match_ranks[team]),
                    "elo_rating": int(team_ratings[team]),
                }
            )

    return (
        pd.DataFrame(result_rows, columns=MATCH_RESULT_COLUMNS),
        pd.DataFrame(snapshot_rows, columns=ELO_SNAPSHOT_COLUMNS),
    )


def _export_snapshots(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=ELO_SNAPSHOT_COLUMNS)

    export = frame.copy()
    export["scraped_at"] = pd.to_datetime(export["scraped_at"], utc=True, errors="coerce")
    export["rank"] = pd.to_numeric(export["rank"], errors="coerce")
    export["elo_rating"] = pd.to_numeric(export["elo_rating"], errors="coerce")
    export = export.dropna(subset=["scraped_at", "team", "rank", "elo_rating"]).copy()
    export = export[export["team"].isin(TARGET_TEAMS)].copy()
    export = export.drop_duplicates(subset=["scraped_at", "team"], keep="last")
    export = export.sort_values(["scraped_at", "rank", "team"])
    export["scraped_at"] = export["scraped_at"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    export["scraped_at"] = export["scraped_at"].str.replace(r"(\+0000)$", "+00:00", regex=True)
    export["rank"] = export["rank"].astype(int)
    export["elo_rating"] = export["elo_rating"].astype(int)
    return export.loc[:, ELO_SNAPSHOT_COLUMNS]


def _export_match_results(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=MATCH_RESULT_COLUMNS)

    export = frame.copy()
    export["match_date"] = pd.to_datetime(export["match_date"], errors="coerce")
    numeric_columns = ["team_score", "opponent_score", "elo_change", "new_elo", "rank_change", "new_rank"]
    for column in numeric_columns:
        export[column] = pd.to_numeric(export[column], errors="coerce")
    export["group"] = export["team"].map(TEAM_TO_GROUP)
    export = export.dropna(
        subset=[
            "match_date",
            "team",
            "opponent",
            "team_score",
            "opponent_score",
            "elo_change",
            "new_elo",
            "rank_change",
            "new_rank",
            "group",
        ]
    ).copy()
    export = export[
        (export["team"].isin(TARGET_TEAMS))
        & (export["tournament"] == WORLD_CUP_TOURNAMENT_NAME)
        & (export["match_date"] >= WORLD_CUP_RESULTS_START_DATE)
    ].copy()
    export = export.drop_duplicates(subset=["match_date", "team", "opponent"], keep="last")
    export = export.sort_values(["match_date", "team", "opponent"])
    export["match_date"] = export["match_date"].dt.strftime("%Y-%m-%d")
    export[numeric_columns] = export[numeric_columns].astype(int)
    return export.loc[:, MATCH_RESULT_COLUMNS]


def _existing_predictions_are_usable() -> bool:
    try:
        return not load_elo_snapshots().empty
    except Exception:
        LOGGER.exception("Existing prediction CSVs could not be validated.")
        return False


def _run_scrape_once(*, force: bool = False, min_interval_minutes: int = 30) -> dict[str, object]:
    del force, min_interval_minutes

    ensure_prediction_csvs()
    existing_snapshots = load_elo_snapshots()
    existing_results = load_match_results()
    baseline_scraped_at, baseline_rows = _baseline_snapshot_rows(existing_snapshots)
    baseline_day = baseline_scraped_at.tz_convert("UTC").normalize().tz_localize(None)
    historical_results = existing_results[existing_results["match_date"] <= baseline_day].copy()

    completed_matches = _fetch_completed_world_cup_matches()
    team_ratings, world_ratings, baseline_order = _build_frozen_world_state(baseline_rows)
    recalculated_results, recalculated_snapshots = _results_and_snapshots_from_matches(
        completed_matches,
        baseline_day=baseline_day,
        team_ratings=team_ratings,
        world_ratings=world_ratings,
        baseline_order=baseline_order,
    )

    baseline_snapshot_export = baseline_rows.copy()
    baseline_snapshot_export["scraped_at"] = baseline_scraped_at
    baseline_snapshot_export = baseline_snapshot_export.loc[:, ELO_SNAPSHOT_COLUMNS]
    snapshot_export = pd.concat([baseline_snapshot_export, recalculated_snapshots], ignore_index=True)
    result_export = (
        pd.concat([historical_results, recalculated_results], ignore_index=True)
        if not historical_results.empty
        else recalculated_results
    )

    snapshot_export = _export_snapshots(snapshot_export)
    result_export = _export_match_results(result_export)
    _write_csv_atomically(snapshot_export, ELO_SNAPSHOTS_PATH)
    _write_csv_atomically(result_export, MATCH_RESULTS_PATH)

    new_match_count = 0
    if not recalculated_results.empty:
        new_match_count = (
            recalculated_results.assign(
                match_key=recalculated_results.apply(
                    lambda row: "::".join(sorted([str(row["team"]), str(row["opponent"])]))
                    + f"|{row['match_date']}",
                    axis=1,
                )
            )["match_key"].nunique()
        )

    completed_at = _current_timestamp().isoformat()
    print(
        f"[{completed_at}] Predictions refresh complete | "
        f"baseline snapshot: {baseline_scraped_at.isoformat()} | "
        f"match checkpoints written: {recalculated_snapshots['scraped_at'].nunique() if not recalculated_snapshots.empty else 0} | "
        f"match rows written: {len(result_export)}"
    )
    return {
        "status": "completed",
        "scraped_at": completed_at,
        "ratings_appended": int(len(recalculated_snapshots)),
        "match_rows_appended": int(len(recalculated_results)),
        "new_matches": int(new_match_count),
    }


def run_scrape(*, force: bool = False, min_interval_minutes: int = 30) -> dict[str, object]:
    last_error: Exception | None = None
    for attempt in range(1, SCRAPE_MAX_ATTEMPTS + 1):
        try:
            return _run_scrape_once(force=force, min_interval_minutes=min_interval_minutes)
        except Exception as exc:
            last_error = exc
            LOGGER.warning("Predictions refresh attempt %s/%s failed: %s", attempt, SCRAPE_MAX_ATTEMPTS, exc)
            if attempt < SCRAPE_MAX_ATTEMPTS:
                sleep_seconds = _retry_sleep_seconds(attempt)
                LOGGER.info("Retrying predictions refresh in %s seconds.", sleep_seconds)
                time.sleep(sleep_seconds)
                continue

            if _existing_predictions_are_usable():
                degraded_at = _current_timestamp().isoformat()
                print(
                    f"[{degraded_at}] Predictions refresh degraded | "
                    f"using previously committed CSVs after {SCRAPE_MAX_ATTEMPTS} failed attempts: {exc}"
                )
                return {
                    "status": "degraded",
                    "scraped_at": degraded_at,
                    "ratings_appended": 0,
                    "match_rows_appended": 0,
                    "new_matches": 0,
                }
            raise

    raise RuntimeError("Predictions refresh failed without raising a terminal error.") from last_error


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("PLOTLY_FIFA_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_scrape(force=True)
