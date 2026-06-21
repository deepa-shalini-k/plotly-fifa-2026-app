from __future__ import annotations

import io
import logging
import os
import re
import time
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import requests

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
ELO_SNAPSHOTS_PATH = REPO_ROOT / "elo_snapshots.csv"
MATCH_RESULTS_PATH = REPO_ROOT / "match_results.csv"
WORLD_CUP_RESULTS_START_DATE = pd.Timestamp("2026-06-11")
WORLD_CUP_TOURNAMENT_NAME = "World Cup"
DEFAULT_PREDICTIONS_GITHUB_REPO = "deepa-shalini-k/plotly-fifa-2026-app"
DEFAULT_PREDICTIONS_GITHUB_REF = "main"
DEFAULT_PREDICTIONS_CACHE_TTL_SECONDS = 900
DEFAULT_PREDICTIONS_TIMEOUT_SECONDS = 10
_REMOTE_CSV_CACHE: dict[str, dict[str, object]] = {}

# The user supplied the 48 qualified teams in 12 consecutive quartets, which
# we preserve here as Groups A-L for the predictions pages and CSV exports.
GROUP_TEAMS: dict[str, tuple[str, str, str, str]] = {
    "A": ("Mexico", "South Africa", "South Korea", "Czechia"),
    "B": ("Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"),
    "C": ("Brazil", "Morocco", "Haiti", "Scotland"),
    "D": ("USA", "Paraguay", "Australia", "Turkey"),
    "E": ("Germany", "Curaçao", "Ecuador", "Ivory Coast"),
    "F": ("Japan", "Netherlands", "Sweden", "Tunisia"),
    "G": ("Belgium", "Egypt", "Iran", "New Zealand"),
    "H": ("Cape Verde Islands", "Saudi Arabia", "Spain", "Uruguay"),
    "I": ("France", "Iraq", "Norway", "Senegal"),
    "J": ("Jordan", "Argentina", "Austria", "Algeria"),
    "K": ("DR Congo", "Colombia", "Portugal", "Uzbekistan"),
    "L": ("England", "Ghana", "Panama", "Croatia"),
}

TARGET_TEAMS = tuple(team for teams in GROUP_TEAMS.values() for team in teams)
TARGET_TEAM_SET = frozenset(TARGET_TEAMS)
TEAM_TO_GROUP = {team: group for group, teams in GROUP_TEAMS.items() for team in teams}
TEAM_DISPLAY_ORDER = {team: index for index, team in enumerate(TARGET_TEAMS)}
GROUP_OPTIONS = [{"label": f"Group {group}", "value": group} for group in GROUP_TEAMS]

TEAM_TO_CONFEDERATION = {
    "Mexico": "CONCACAF",
    "South Africa": "CAF",
    "South Korea": "AFC",
    "Czechia": "UEFA",
    "Canada": "CONCACAF",
    "Bosnia and Herzegovina": "UEFA",
    "Qatar": "AFC",
    "Switzerland": "UEFA",
    "Brazil": "CONMEBOL",
    "Morocco": "CAF",
    "Haiti": "CONCACAF",
    "Scotland": "UEFA",
    "USA": "CONCACAF",
    "Paraguay": "CONMEBOL",
    "Australia": "AFC",
    "Turkey": "UEFA",
    "Germany": "UEFA",
    "Curaçao": "CONCACAF",
    "Netherlands": "UEFA",
    "Japan": "AFC",
    "Sweden": "UEFA",
    "Tunisia": "CAF",
    "Iran": "AFC",
    "New Zealand": "OFC",
    "Belgium": "UEFA",
    "Egypt": "CAF",
    "Spain": "UEFA",
    "Senegal": "CAF",
    "Cape Verde Islands": "CAF",
    "Argentina": "CONMEBOL",
    "Algeria": "CAF",
    "Portugal": "UEFA",
    "DR Congo": "CAF",
    "Uzbekistan": "AFC",
    "Colombia": "CONMEBOL",
    "France": "UEFA",
    "Jordan": "AFC",
    "Austria": "UEFA",
    "England": "UEFA",
    "Ghana": "CAF",
    "Panama": "CONCACAF",
    "Uruguay": "CONMEBOL",
    "Saudi Arabia": "AFC",
    "Iraq": "AFC",
    "Norway": "UEFA",
    "Ivory Coast": "CAF",
    "Ecuador": "CONMEBOL",
    "Croatia": "UEFA",
}

TEAM_TO_FIFA_CODE = {
    "Mexico": "MEX",
    "South Africa": "RSA",
    "South Korea": "KOR",
    "Czechia": "CZE",
    "Canada": "CAN",
    "Bosnia and Herzegovina": "BIH",
    "Qatar": "QAT",
    "Switzerland": "SUI",
    "Brazil": "BRA",
    "Morocco": "MAR",
    "Haiti": "HAI",
    "Scotland": "SCO",
    "USA": "USA",
    "Paraguay": "PAR",
    "Australia": "AUS",
    "Turkey": "TUR",
    "Germany": "GER",
    "Curaçao": "CUW",
    "Netherlands": "NED",
    "Japan": "JPN",
    "Sweden": "SWE",
    "Tunisia": "TUN",
    "Iran": "IRN",
    "New Zealand": "NZL",
    "Belgium": "BEL",
    "Egypt": "EGY",
    "Spain": "ESP",
    "Senegal": "SEN",
    "Cape Verde Islands": "CPV",
    "Argentina": "ARG",
    "Algeria": "ALG",
    "Portugal": "POR",
    "DR Congo": "COD",
    "Uzbekistan": "UZB",
    "Colombia": "COL",
    "France": "FRA",
    "Jordan": "JOR",
    "Austria": "AUT",
    "England": "ENG",
    "Ghana": "GHA",
    "Panama": "PAN",
    "Uruguay": "URU",
    "Saudi Arabia": "KSA",
    "Iraq": "IRQ",
    "Norway": "NOR",
    "Ivory Coast": "CIV",
    "Ecuador": "ECU",
    "Croatia": "CRO",
}

CONFEDERATION_COLORS = {
    "CONCACAF": "#00D084",
    "UEFA": "#4E9CFF",
    "CAF": "#FFD700",
    "CONMEBOL": "#FF4757",
    "AFC": "#A78BFA",
    "OFC": "#FB923C",
}

# The Elo refresh exports match rows by the host city's local calendar day, so
# pages that line live fixtures up with persisted Elo rows need the same venue
# mapping to avoid off-by-one-day mismatches around midnight UTC.
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

ELO_SNAPSHOT_COLUMNS = ["scraped_at", "team", "rank", "elo_rating"]
MATCH_RESULT_COLUMNS = [
    "match_date",
    "team",
    "opponent",
    "team_score",
    "opponent_score",
    "tournament",
    "elo_change",
    "new_elo",
    "rank_change",
    "new_rank",
    "group",
]

TEAM_NAME_ALIASES = {
    "bosnia herzegovina": "Bosnia and Herzegovina",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "bosnia herz": "Bosnia and Herzegovina",
    "congo dr": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "democratic republic of the congo": "DR Congo",
    "dr congo": "DR Congo",
    "cote divoire": "Ivory Coast",
    "cote d ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "ivory coast": "Ivory Coast",
    "curacao": "Curaçao",
    "curaçao": "Curaçao",
    "cape verde": "Cape Verde Islands",
    "cape verde islands": "Cape Verde Islands",
    "cabo verde": "Cape Verde Islands",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "england": "England",
    "algeria": "Algeria",
    "austria": "Austria",
    "ghana": "Ghana",
    "iran": "Iran",
    "ir iran": "Iran",
    "jordan": "Jordan",
    "korea republic": "South Korea",
    "korea rep": "South Korea",
    "new zealand": "New Zealand",
    "panama": "Panama",
    "saudi arabia": "Saudi Arabia",
    "scotland": "Scotland",
    "south africa": "South Africa",
    "south korea": "South Korea",
    "turkey": "Turkey",
    "turkiye": "Turkey",
    "türkiye": "Turkey",
    "united states": "USA",
    "usa": "USA",
}


def normalize_team_key(name: str | None) -> str:
    if not name:
        return ""

    normalized = unicodedata.normalize("NFKD", str(name))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.casefold().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


NORMALIZED_TEAM_LOOKUP = {normalize_team_key(team): team for team in TARGET_TEAMS}
for alias, canonical in TEAM_NAME_ALIASES.items():
    NORMALIZED_TEAM_LOOKUP[normalize_team_key(alias)] = canonical


def canonical_team_name(name: str | None) -> str | None:
    key = normalize_team_key(name)
    if not key:
        return None
    return NORMALIZED_TEAM_LOOKUP.get(key)


def build_match_key(match_date: str, team: str, opponent: str) -> str:
    ordered = sorted(
        [canonical_team_name(team) or team.strip(), canonical_team_name(opponent) or opponent.strip()],
        key=normalize_team_key,
    )
    return f"{match_date}|{'::'.join(ordered)}"


def _coerce_utc_timestamp(value) -> pd.Timestamp | None:
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


def venue_context(venue: str | None) -> tuple[str | None, str | None]:
    venue_key = _normalize_venue_key(venue)
    if not venue_key:
        return None, None

    for keyword, context in VENUE_HOST_CONTEXT:
        if keyword in venue_key:
            return context
    return None, None


def match_local_date(match: dict | None) -> pd.Timestamp | None:
    if not isinstance(match, dict):
        return None

    kickoff = _coerce_utc_timestamp(match.get("utcDate"))
    if kickoff is None:
        return None

    _, timezone_name = venue_context(match.get("venue"))
    if timezone_name:
        try:
            kickoff = kickoff.tz_convert(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            logger.warning("Timezone data unavailable for %s; falling back to UTC match date", timezone_name)
    return kickoff.normalize().tz_localize(None)


def build_match_key_from_match(match: dict | None) -> str | None:
    if not isinstance(match, dict):
        return None

    local_match_date = match_local_date(match)
    home_name = canonical_team_name((match.get("homeTeam") or {}).get("name"))
    away_name = canonical_team_name((match.get("awayTeam") or {}).get("name"))
    if local_match_date is None or not home_name or not away_name:
        return None

    return build_match_key(local_match_date.strftime("%Y-%m-%d"), home_name, away_name)


def ensure_prediction_csvs() -> None:
    if not ELO_SNAPSHOTS_PATH.exists():
        pd.DataFrame(columns=ELO_SNAPSHOT_COLUMNS).to_csv(ELO_SNAPSHOTS_PATH, index=False)
    if not MATCH_RESULTS_PATH.exists():
        pd.DataFrame(columns=MATCH_RESULT_COLUMNS).to_csv(MATCH_RESULTS_PATH, index=False)


def _prediction_source() -> str:
    configured = os.environ.get("PLOTLY_FIFA_PREDICTIONS_SOURCE", "remote")
    return configured.strip().lower() or "remote"


def _prediction_cache_ttl_seconds() -> int:
    raw_value = os.environ.get("PLOTLY_FIFA_PREDICTIONS_CACHE_TTL_SECONDS", str(DEFAULT_PREDICTIONS_CACHE_TTL_SECONDS))
    try:
        return max(0, int(raw_value))
    except ValueError:
        return DEFAULT_PREDICTIONS_CACHE_TTL_SECONDS


def _prediction_timeout_seconds() -> int:
    raw_value = os.environ.get("PLOTLY_FIFA_PREDICTIONS_TIMEOUT_SECONDS", str(DEFAULT_PREDICTIONS_TIMEOUT_SECONDS))
    try:
        return max(1, int(raw_value))
    except ValueError:
        return DEFAULT_PREDICTIONS_TIMEOUT_SECONDS


def _prediction_remote_url(path: Path) -> str:
    if base_url := os.environ.get("PLOTLY_FIFA_PREDICTIONS_BASE_URL"):
        return f"{base_url.rstrip('/')}/{path.name}"

    repo = os.environ.get("PLOTLY_FIFA_PREDICTIONS_GITHUB_REPO", DEFAULT_PREDICTIONS_GITHUB_REPO).strip("/")
    ref = os.environ.get("PLOTLY_FIFA_PREDICTIONS_GITHUB_REF", DEFAULT_PREDICTIONS_GITHUB_REF).strip("/") or DEFAULT_PREDICTIONS_GITHUB_REF
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path.name}"


def _read_local_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    ensure_prediction_csvs()
    frame = pd.read_csv(path)
    if frame.empty:
        return pd.DataFrame(columns=columns)
    missing_columns = [column for column in columns if column not in frame.columns]
    if missing_columns:
        for column in missing_columns:
            frame[column] = pd.NA
    return frame.loc[:, columns]


def _read_remote_csv_text(path: Path) -> str:
    url = _prediction_remote_url(path)
    now = time.monotonic()
    ttl_seconds = _prediction_cache_ttl_seconds()
    cached = _REMOTE_CSV_CACHE.get(url)

    if cached and ttl_seconds > 0 and now - float(cached["fetched_at"]) < ttl_seconds:
        return str(cached["text"])

    try:
        response = requests.get(url, timeout=_prediction_timeout_seconds())
        response.raise_for_status()
        response.encoding = "utf-8"
        text = response.text
        _REMOTE_CSV_CACHE[url] = {"fetched_at": now, "text": text}
        return text
    except requests.RequestException as exc:
        if cached and cached.get("text"):
            logger.warning("Serving stale predictions CSV from %s after %s", url, exc)
            return str(cached["text"])
        if path.exists():
            logger.warning("Falling back to bundled predictions CSV %s after %s", path.name, exc)
            return path.read_text(encoding="utf-8")
        logger.warning("Predictions CSV %s unavailable from %s and no local fallback exists", path.name, url)
        return ""


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if _prediction_source() == "local":
        return _read_local_csv(path, columns)

    payload = _read_remote_csv_text(path)
    if not payload.strip():
        return pd.DataFrame(columns=columns)

    frame = pd.read_csv(io.StringIO(payload))
    if frame.empty:
        return pd.DataFrame(columns=columns)
    missing_columns = [column for column in columns if column not in frame.columns]
    if missing_columns:
        for column in missing_columns:
            frame[column] = pd.NA
    return frame.loc[:, columns]


def load_elo_snapshots() -> pd.DataFrame:
    frame = _read_csv(ELO_SNAPSHOTS_PATH, ELO_SNAPSHOT_COLUMNS)
    if frame.empty:
        return frame

    frame["scraped_at"] = pd.to_datetime(frame["scraped_at"], utc=True, errors="coerce")
    frame["rank"] = pd.to_numeric(frame["rank"], errors="coerce")
    frame["elo_rating"] = pd.to_numeric(frame["elo_rating"], errors="coerce")
    frame = frame.dropna(subset=["scraped_at", "team", "rank", "elo_rating"])
    frame = frame[frame["team"].isin(TARGET_TEAM_SET)].copy()
    frame["team_order"] = frame["team"].map(TEAM_DISPLAY_ORDER)
    frame = frame.sort_values(["team_order", "scraped_at"]).drop(columns=["team_order"])
    frame["rank"] = frame["rank"].astype(int)
    frame["elo_rating"] = frame["elo_rating"].astype(int)
    return frame


def load_match_results() -> pd.DataFrame:
    frame = _read_csv(MATCH_RESULTS_PATH, MATCH_RESULT_COLUMNS)
    if frame.empty:
        return frame

    frame["match_date"] = pd.to_datetime(frame["match_date"], errors="coerce")
    for column in ["team_score", "opponent_score", "elo_change", "new_elo", "rank_change", "new_rank"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["group"] = frame["team"].map(TEAM_TO_GROUP)

    frame = frame.dropna(
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
    )
    frame = frame[frame["team"].isin(TARGET_TEAM_SET)].copy()
    frame["match_date"] = frame["match_date"].dt.normalize()
    frame = frame[
        (frame["tournament"] == WORLD_CUP_TOURNAMENT_NAME)
        & (frame["match_date"] >= WORLD_CUP_RESULTS_START_DATE)
    ].copy()
    integer_columns = ["team_score", "opponent_score", "elo_change", "new_elo", "rank_change", "new_rank"]
    frame[integer_columns] = frame[integer_columns].astype(int)
    frame["team_order"] = frame["team"].map(TEAM_DISPLAY_ORDER)
    frame = frame.sort_values(["match_date", "team_order", "opponent"]).drop(columns=["team_order"])
    return frame
