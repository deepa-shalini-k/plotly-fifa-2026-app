from __future__ import annotations

import datetime as dt
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import mean
from urllib.parse import quote

from data.cache import cached_get
from data.pitch_utils import calculate_age, safe_div


def _load_local_env() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [repo_root / ".env", repo_root / "data" / ".env"]

    for env_path in candidates:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_local_env()

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY")
APP_MODE = os.environ.get("APP_MODE", "").strip().lower()
WC_CODE = "WC"
WC_ID = 2000
WC_SEASON = 2026
WC_NAME = "FIFA World Cup"
BASE_URL = "https://api.football-data.org/v4"
DEFAULT_HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}
UNFOLD_HEADERS = {
    **DEFAULT_HEADERS,
    "X-Unfold-Lineups": "true",
    "X-Unfold-Bookings": "true",
    "X-Unfold-Goals": "true",
    "X-Unfold-Subs": "true",
}
TODAY = dt.date.today()
LIVE_STATUSES = {"IN_PLAY", "PAUSED"}
UPCOMING_STATUSES = {"TIMED", "SCHEDULED"}
COMPLETED_STATUSES = {"FINISHED"}
PLAYED_MATCH_STATUSES = {*LIVE_STATUSES, *COMPLETED_STATUSES, "EXTRA_TIME", "PENALTY_SHOOTOUT", "AWARDED"}
LIVE_FEED_GRACE_MINUTES = 20
ENGLAND_FLAG_EMOJI = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"
SCOTLAND_FLAG_EMOJI = "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"
GOAL_TIME_BRACKETS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90", "90+")


def _make_crest(label: str, fill: str = "#00D084") -> str:
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>
      <rect width='96' height='96' rx='24' fill='#141720'/>
      <circle cx='48' cy='48' r='32' fill='{fill}' fill-opacity='0.18' stroke='{fill}' stroke-width='3'/>
      <text x='48' y='58' font-family='Arial' font-size='26' text-anchor='middle' fill='{fill}'>{label}</text>
    </svg>
    """
    return "data:image/svg+xml;utf8," + quote(svg)


TEAM_SEED = [
    ("GROUP_A", 1001, "Brazil", "BRA", "🇧🇷"),
    ("GROUP_A", 1002, "Germany", "GER", "🇩🇪"),
    ("GROUP_A", 1003, "England", "ENG", ENGLAND_FLAG_EMOJI),
    ("GROUP_A", 1004, "Japan", "JPN", "🇯🇵"),
    ("GROUP_B", 1005, "Spain", "ESP", "🇪🇸"),
    ("GROUP_B", 1006, "France", "FRA", "🇫🇷"),
    ("GROUP_B", 1007, "Argentina", "ARG", "🇦🇷"),
    ("GROUP_B", 1008, "Portugal", "POR", "🇵🇹"),
    ("GROUP_C", 1009, "USA", "USA", "🇺🇸"),
    ("GROUP_C", 1010, "Mexico", "MEX", "🇲🇽"),
    ("GROUP_C", 1011, "Canada", "CAN", "🇨🇦"),
    ("GROUP_C", 1012, "Morocco", "MAR", "🇲🇦"),
    ("GROUP_D", 1013, "Netherlands", "NED", "🇳🇱"),
    ("GROUP_D", 1014, "Senegal", "SEN", "🇸🇳"),
    ("GROUP_D", 1015, "Croatia", "CRO", "🇭🇷"),
    ("GROUP_D", 1016, "South Korea", "KOR", "🇰🇷"),
    ("GROUP_E", 1017, "Italy", "ITA", "🇮🇹"),
    ("GROUP_E", 1018, "Uruguay", "URU", "🇺🇾"),
    ("GROUP_E", 1019, "Colombia", "COL", "🇨🇴"),
    ("GROUP_E", 1020, "Nigeria", "NGA", "🇳🇬"),
    ("GROUP_F", 1021, "Belgium", "BEL", "🇧🇪"),
    ("GROUP_F", 1022, "Denmark", "DEN", "🇩🇰"),
    ("GROUP_F", 1023, "Switzerland", "SUI", "🇨🇭"),
    ("GROUP_F", 1024, "Serbia", "SRB", "🇷🇸"),
    ("GROUP_G", 1025, "Ecuador", "ECU", "🇪🇨"),
    ("GROUP_G", 1026, "Poland", "POL", "🇵🇱"),
    ("GROUP_G", 1027, "Australia", "AUS", "🇦🇺"),
    ("GROUP_G", 1028, "Ghana", "GHA", "🇬🇭"),
    ("GROUP_H", 1029, "Sweden", "SWE", "🇸🇪"),
    ("GROUP_H", 1030, "Austria", "AUT", "🇦🇹"),
    ("GROUP_H", 1031, "Ukraine", "UKR", "🇺🇦"),
    ("GROUP_H", 1032, "Turkey", "TUR", "🇹🇷"),
    ("GROUP_I", 1033, "Norway", "NOR", "🇳🇴"),
    ("GROUP_I", 1034, "Chile", "CHI", "🇨🇱"),
    ("GROUP_I", 1035, "Peru", "PER", "🇵🇪"),
    ("GROUP_I", 1036, "Egypt", "EGY", "🇪🇬"),
    ("GROUP_J", 1037, "Algeria", "ALG", "🇩🇿"),
    ("GROUP_J", 1038, "Cameroon", "CMR", "🇨🇲"),
    ("GROUP_J", 1039, "Ivory Coast", "CIV", "🇨🇮"),
    ("GROUP_J", 1040, "Tunisia", "TUN", "🇹🇳"),
    ("GROUP_K", 1041, "Saudi Arabia", "KSA", "🇸🇦"),
    ("GROUP_K", 1042, "Iran", "IRN", "🇮🇷"),
    ("GROUP_K", 1043, "Qatar", "QAT", "🇶🇦"),
    ("GROUP_K", 1044, "United Arab Emirates", "UAE", "🇦🇪"),
    ("GROUP_L", 1045, "New Zealand", "NZL", "🇳🇿"),
    ("GROUP_L", 1046, "Costa Rica", "CRC", "🇨🇷"),
    ("GROUP_L", 1047, "Panama", "PAN", "🇵🇦"),
    ("GROUP_L", 1048, "Jamaica", "JAM", "🇯🇲"),
]


def _build_team(group_code: str, team_id: int, name: str, tla: str, flag_emoji: str) -> dict:
    return {
        "id": team_id,
        "name": name,
        "shortName": name,
        "tla": tla,
        "flag_emoji": flag_emoji,
        "group": group_code,
        "area": {"name": name, "flag": flag_emoji},
        "crest": _make_crest(tla),
        "coach": {"name": f"{name} Coach", "nationality": name},
        "founded": 1900 + (team_id % 70),
        "venue": f"{name} Arena",
        "clubColors": "Green / Blue",
    }


TEAMS = [_build_team(*seed) for seed in TEAM_SEED]
TEAM_INDEX = {team["id"]: team for team in TEAMS}
TEAM_NAME_INDEX = {team["name"]: team for team in TEAMS}
GROUP_INDEX = defaultdict(list)
for team in TEAMS:
    GROUP_INDEX[team["group"]].append(team)

TEAM_FLAG_BY_TLA = {team["tla"].upper(): team["flag_emoji"] for team in TEAMS if team.get("tla")}
TEAM_FLAG_BY_NAME = {team["name"].casefold(): team["flag_emoji"] for team in TEAMS if team.get("name")}
TEAM_FLAG_BY_CODE = {
    "ALG": "DZ",
    "ARG": "AR",
    "AUS": "AU",
    "AUT": "AT",
    "BEL": "BE",
    "BIH": "BA",
    "BRA": "BR",
    "CAN": "CA",
    "CHE": "CH",
    "CHI": "CL",
    "CMR": "CM",
    "CIV": "CI",
    "COD": "CD",
    "COL": "CO",
    "CPV": "CV",
    "CRO": "HR",
    "CUW": "CW",
    "CZE": "CZ",
    "DEU": "DE",
    "DEN": "DK",
    "ECU": "EC",
    "EGY": "EG",
    "ENG": "__ENG__",
    "ESP": "ES",
    "FRA": "FR",
    "GER": "DE",
    "GHA": "GH",
    "HAI": "HT",
    "HRV": "HR",
    "HTI": "HT",
    "IRN": "IR",
    "IRQ": "IQ",
    "ITA": "IT",
    "JOR": "JO",
    "JPN": "JP",
    "KOR": "KR",
    "KSA": "SA",
    "MAR": "MA",
    "MEX": "MX",
    "NED": "NL",
    "NGA": "NG",
    "NLD": "NL",
    "NOR": "NO",
    "NZL": "NZ",
    "PAN": "PA",
    "PAR": "PY",
    "POL": "PL",
    "POR": "PT",
    "PRY": "PY",
    "QAT": "QA",
    "RSA": "ZA",
    "SCO": "__SCO__",
    "SEN": "SN",
    "SRB": "RS",
    "SUI": "CH",
    "SWE": "SE",
    "TUN": "TN",
    "TUR": "TR",
    "UAE": "AE",
    "UKR": "UA",
    "URY": "UY",
    "USA": "US",
    "UZB": "UZ",
}
TEAM_SPECIAL_FLAG_BY_NAME = {
    # Home nations use subdivision-flag sequences rather than ordinary
    # country-code flags, so we keep them centralized for consistent lookup.
    "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "scotland": "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F",
}
TEAM_SPECIAL_FLAG_BY_NAME = {
    **TEAM_SPECIAL_FLAG_BY_NAME,
    "england": ENGLAND_FLAG_EMOJI,
    "scotland": SCOTLAND_FLAG_EMOJI,
}
TEAM_FLAG_NAME_TO_CODE = {
    "algeria": "DZ",
    "argentina": "AR",
    "australia": "AU",
    "austria": "AT",
    "belgium": "BE",
    "bosnia and herzegovina": "BA",
    "bosnia-herzegovina": "BA",
    "brazil": "BR",
    "canada": "CA",
    "cameroon": "CM",
    "cape verde": "CV",
    "cape verde islands": "CV",
    "colombia": "CO",
    "congo dr": "CD",
    "costa rica": "CR",
    "croatia": "HR",
    "curacao": "CW",
    "curaçao": "CW",
    "czech republic": "CZ",
    "czechia": "CZ",
    "denmark": "DK",
    "ecuador": "EC",
    "egypt": "EG",
    "france": "FR",
    "germany": "DE",
    "ghana": "GH",
    "haiti": "HT",
    "iran": "IR",
    "iraq": "IQ",
    "ivory coast": "CI",
    "jamaica": "JM",
    "japan": "JP",
    "jordan": "JO",
    "mexico": "MX",
    "morocco": "MA",
    "netherlands": "NL",
    "new zealand": "NZ",
    "nigeria": "NG",
    "norway": "NO",
    "panama": "PA",
    "paraguay": "PY",
    "peru": "PE",
    "poland": "PL",
    "portugal": "PT",
    "qatar": "QA",
    "saudi arabia": "SA",
    "senegal": "SN",
    "south africa": "ZA",
    "south korea": "KR",
    "spain": "ES",
    "sweden": "SE",
    "switzerland": "CH",
    "tunisia": "TN",
    "turkey": "TR",
    "uae": "AE",
    "ukraine": "UA",
    "united arab emirates": "AE",
    "united states": "US",
    "uruguay": "UY",
    "uzbekistan": "UZ",
}
COUNTRY_ALPHA2_TO_ALPHA3 = {
    "AE": "ARE",
    "AR": "ARG",
    "AT": "AUT",
    "AU": "AUS",
    "BA": "BIH",
    "BE": "BEL",
    "BR": "BRA",
    "CA": "CAN",
    "CM": "CMR",
    "CD": "COD",
    "CH": "CHE",
    "CI": "CIV",
    "CL": "CHL",
    "CO": "COL",
    "CR": "CRI",
    "CV": "CPV",
    "CW": "CUW",
    "CZ": "CZE",
    "DE": "DEU",
    "DK": "DNK",
    "DZ": "DZA",
    "EC": "ECU",
    "EG": "EGY",
    "ES": "ESP",
    "FR": "FRA",
    "GB": "GBR",
    "GH": "GHA",
    "HR": "HRV",
    "HT": "HTI",
    "IQ": "IRQ",
    "IR": "IRN",
    "IT": "ITA",
    "JM": "JAM",
    "JO": "JOR",
    "JP": "JPN",
    "KR": "KOR",
    "MA": "MAR",
    "MX": "MEX",
    "NG": "NGA",
    "NL": "NLD",
    "NO": "NOR",
    "NZ": "NZL",
    "PA": "PAN",
    "PE": "PER",
    "PL": "POL",
    "PT": "PRT",
    "PY": "PRY",
    "QA": "QAT",
    "RS": "SRB",
    "SA": "SAU",
    "SE": "SWE",
    "SN": "SEN",
    "TN": "TUN",
    "TR": "TUR",
    "UA": "UKR",
    "US": "USA",
    "UY": "URY",
    "UZ": "UZB",
    "ZA": "ZAF",
}
COUNTRY_ALPHA3_CODES = frozenset(COUNTRY_ALPHA2_TO_ALPHA3.values())
TEAM_MAP_CODE_OVERRIDES = {
    "england": "GBR",
    "scotland": "GBR",
}
TEAM_FLAG_BY_NAME.update(
    {
        "united states": "🇺🇸",
        "usa": "🇺🇸",
        "us": "🇺🇸",
        "korea republic": "🇰🇷",
        "south korea": "🇰🇷",
        "ir iran": "🇮🇷",
        "iran": "🇮🇷",
        "saudi arabia": "🇸🇦",
        "united arab emirates": "🇦🇪",
        "uae": "🇦🇪",
        "ivory coast": "🇨🇮",
        "cote d'ivoire": "🇨🇮",
        "paraguay": "🇵🇾",
        "bosnia and herzegovina": "🇧🇦",
        "bosnia-herzegovina": "🇧🇦",
        "south africa": "🇿🇦",
        "haiti": "🇭🇹",
        "cape verde islands": "🇨🇻",
        "cape verde": "🇨🇻",
        "congo dr": "🇨🇩",
        "democratic republic of the congo": "🇨🇩",
        "dr congo": "🇨🇩",
        "jordan": "🇯🇴",
        "iraq": "🇮🇶",
        "uzbekistan": "🇺🇿",
        "curaçao": "🇨🇼",
        "curacao": "🇨🇼",
        "czech republic": "🇨🇿",
        "czechia": "🇨🇿",
        "switzerland": "🇨🇭",
        "par": "🇵🇾",
        "bih": "🇧🇦",
        "rsa": "🇿🇦",
        "hai": "🇭🇹",
        "cpv": "🇨🇻",
        "cod": "🇨🇩",
        "jor": "🇯🇴",
        "irq": "🇮🇶",
        "uzb": "🇺🇿",
        "cuw": "🇨🇼",
    }
)


def _country_code_to_flag(code: str | None) -> str | None:
    if not code:
        return None
    normalized = code.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        return None
    return "".join(chr(127397 + ord(char)) for char in normalized)


def _country_code_to_iso3(code: str | None) -> str | None:
    if not code:
        return None

    normalized = code.strip().upper()
    if not normalized or not normalized.isalpha():
        return None

    if len(normalized) == 2:
        return COUNTRY_ALPHA2_TO_ALPHA3.get(normalized)

    if len(normalized) != 3:
        return None

    if normalized in COUNTRY_ALPHA3_CODES:
        return normalized

    mapped_alpha2 = TEAM_FLAG_BY_CODE.get(normalized)
    if mapped_alpha2 == "__ENG__" or mapped_alpha2 == "__SCO__":
        return "GBR"
    if mapped_alpha2:
        return COUNTRY_ALPHA2_TO_ALPHA3.get(mapped_alpha2)

    return None


def _lookup_team_map_code(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    override = TEAM_MAP_CODE_OVERRIDES.get(normalized.casefold())
    if override:
        return override

    as_code = _country_code_to_iso3(normalized)
    if as_code:
        return as_code

    name_code = TEAM_FLAG_NAME_TO_CODE.get(normalized.casefold())
    if name_code:
        return _country_code_to_iso3(name_code)

    return None


def _lookup_flag_emoji(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None

    by_tla = TEAM_FLAG_BY_TLA.get(normalized.upper())
    if by_tla:
        return by_tla

    special_flag = TEAM_SPECIAL_FLAG_BY_NAME.get(normalized.casefold())
    if special_flag:
        return special_flag

    by_code = TEAM_FLAG_BY_CODE.get(normalized.upper())
    if by_code == "__ENG__":
        return TEAM_SPECIAL_FLAG_BY_NAME["england"]
    if by_code == "__SCO__":
        return TEAM_SPECIAL_FLAG_BY_NAME["scotland"]
    if by_code:
        resolved_code = _country_code_to_flag(by_code)
        if resolved_code:
            return resolved_code

    by_name = TEAM_FLAG_BY_NAME.get(normalized.casefold())
    if by_name:
        return by_name

    name_code = TEAM_FLAG_NAME_TO_CODE.get(normalized.casefold())
    if name_code:
        resolved_code = _country_code_to_flag(name_code)
        if resolved_code:
            return resolved_code

    return _country_code_to_flag(normalized)


def _resolve_flag_emoji(team_like: dict | str | None) -> str:
    if isinstance(team_like, str):
        return _lookup_flag_emoji(team_like) or "🏳️"

    if not isinstance(team_like, dict):
        return "🏳️"

    if team_like.get("flag_emoji"):
        return team_like["flag_emoji"]

    area = team_like.get("area") if isinstance(team_like.get("area"), dict) else {}
    candidates = [
        team_like.get("tla"),
        team_like.get("name"),
        team_like.get("shortName"),
        team_like.get("nationality"),
        team_like.get("country"),
        area.get("name"),
        area.get("code"),
        area.get("countryCode"),
    ]
    for candidate in candidates:
        resolved = _lookup_flag_emoji(candidate)
        if resolved:
            return resolved

    return "🏳️"


def _normalize_player_entry(player: dict | None, team: dict | None = None) -> dict:
    if not isinstance(player, dict):
        return {}

    normalized = dict(player)
    if team:
        normalized.setdefault("nationality", team.get("name") or team.get("shortName"))
        normalized.setdefault(
            "currentTeam",
            {
                "id": team.get("id"),
                "name": team.get("name"),
                "shortName": team.get("shortName"),
                "tla": team.get("tla"),
                "flag_emoji": team.get("flag_emoji"),
            },
        )
    elif isinstance(normalized.get("currentTeam"), dict):
        normalized["currentTeam"] = _normalize_team(normalized["currentTeam"])

    normalized["flag_emoji"] = normalized.get("flag_emoji") or _resolve_flag_emoji(
        normalized.get("nationality")
        or normalized.get("country")
        or normalized.get("currentTeam")
    )
    return normalized


def _normalize_team(team: dict | None) -> dict:
    if not isinstance(team, dict):
        return {}

    normalized = dict(team)
    normalized["flag_emoji"] = _resolve_flag_emoji(normalized)
    normalized["name"] = str(normalized.get("name") or normalized.get("shortName") or "TBD")
    normalized["shortName"] = str(normalized.get("shortName") or normalized["name"] or "TBD")
    normalized["tla"] = str(normalized.get("tla") or normalized["shortName"][:3] or "TBD").upper()
    normalized["lineup"] = normalized.get("lineup") if isinstance(normalized.get("lineup"), list) else []
    normalized["bench"] = normalized.get("bench") if isinstance(normalized.get("bench"), list) else []
    normalized["statistics"] = normalized.get("statistics") if isinstance(normalized.get("statistics"), dict) else {}

    if isinstance(normalized.get("area"), dict):
        normalized["area"] = dict(normalized["area"])
        normalized["area"].setdefault("flag_emoji", normalized["flag_emoji"])

    lineup = normalized.get("lineup")
    bench = normalized.get("bench")
    normalized["lineup"] = [_normalize_player_entry(player, normalized) for player in lineup] if isinstance(lineup, list) else []
    normalized["bench"] = [_normalize_player_entry(player, normalized) for player in bench] if isinstance(bench, list) else []

    if isinstance(normalized.get("squad"), list):
        normalized["squad"] = [_normalize_player_entry(player, normalized) for player in normalized["squad"]]

    return normalized


def _normalize_match(match: dict | None) -> dict:
    if not isinstance(match, dict):
        return {}

    normalized = dict(match)
    home_team = _normalize_team(normalized.get("homeTeam"))
    away_team = _normalize_team(normalized.get("awayTeam"))
    normalized["homeTeam"] = home_team
    normalized["awayTeam"] = away_team

    goals = normalized.get("goals")
    bookings = normalized.get("bookings")
    substitutions = normalized.get("substitutions")
    normalized["goals"] = [
        {
            **goal,
            "team": _normalize_team(goal.get("team")),
            "scorer": _normalize_player_entry(goal.get("scorer"), home_team if goal.get("team", {}).get("id") == home_team.get("id") else away_team),
            "assist": _normalize_player_entry(goal.get("assist"), home_team if goal.get("team", {}).get("id") == home_team.get("id") else away_team) if goal.get("assist") else None,
        }
        for goal in goals
    ] if isinstance(goals, list) else []
    normalized["bookings"] = [
        {
            **booking,
            "team": _normalize_team(booking.get("team")),
            "player": _normalize_player_entry(booking.get("player"), home_team if booking.get("team", {}).get("id") == home_team.get("id") else away_team),
        }
        for booking in bookings
    ] if isinstance(bookings, list) else []
    normalized["substitutions"] = [
        {
            **substitution,
            "team": _normalize_team(substitution.get("team")),
            "playerOut": _normalize_player_entry(substitution.get("playerOut"), home_team if substitution.get("team", {}).get("id") == home_team.get("id") else away_team),
            "playerIn": _normalize_player_entry(substitution.get("playerIn"), home_team if substitution.get("team", {}).get("id") == home_team.get("id") else away_team),
        }
        for substitution in substitutions
    ] if isinstance(substitutions, list) else []
    return normalized


def _normalize_standings_payload(payload: dict) -> dict:
    normalized = dict(payload or {})
    standings = []
    for standing in normalized.get("standings", []):
        standing_copy = dict(standing)
        standing_copy["table"] = [
            {**row, "team": _normalize_team(row.get("team"))}
            for row in standing.get("table", [])
        ]
        standings.append(standing_copy)
    normalized["standings"] = standings
    return normalized


def _normalize_scorers_payload(rows: list[dict]) -> list[dict]:
    normalized_rows = []
    for row in rows:
        row_copy = dict(row)
        row_copy["team"] = _normalize_team(row.get("team"))
        row_copy["player"] = _normalize_player_entry(row.get("player"), row_copy["team"])
        normalized_rows.append(row_copy)
    return normalized_rows


def _player(pid: int, name: str, position: str, shirt_number: int, dob: str, team_name: str) -> dict:
    team = TEAM_NAME_INDEX[team_name]
    return {
        "id": pid,
        "name": name,
        "shortName": name.split()[-1] if " " in name else name,
        "position": position,
        "shirtNumber": shirt_number,
        "dateOfBirth": dob,
        "nationality": team_name,
        "flag_emoji": team["flag_emoji"],
        "currentTeam": {"id": team["id"], "name": team_name},
    }


BRAZIL_LINEUP = [
    _player(5001, "Alisson", "Goalkeeper", 1, "1992-10-02", "Brazil"),
    _player(5002, "Danilo", "Defender", 2, "1991-07-15", "Brazil"),
    _player(5003, "Marquinhos", "Defender", 4, "1994-05-14", "Brazil"),
    _player(5004, "Eder Militao", "Defender", 3, "1998-01-18", "Brazil"),
    _player(5005, "Alex Sandro", "Defender", 6, "1991-01-26", "Brazil"),
    _player(5006, "Casemiro", "Midfielder", 5, "1992-02-23", "Brazil"),
    _player(5007, "Lucas Paqueta", "Midfielder", 8, "1997-08-27", "Brazil"),
    _player(5008, "Rodrygo", "Forward", 7, "2001-01-09", "Brazil"),
    _player(5009, "Vinicius Jr.", "Forward", 11, "2000-07-12", "Brazil"),
    _player(5010, "Endrick", "Forward", 9, "2006-07-21", "Brazil"),
    _player(5011, "Savinho", "Forward", 10, "2004-04-10", "Brazil"),
]

GERMANY_LINEUP = [
    _player(5101, "Manuel Neuer", "Goalkeeper", 1, "1986-03-27", "Germany"),
    _player(5102, "Joshua Kimmich", "Defender", 2, "1995-02-08", "Germany"),
    _player(5103, "Jonathan Tah", "Defender", 3, "1996-02-11", "Germany"),
    _player(5104, "Nico Schlotterbeck", "Defender", 4, "1999-12-01", "Germany"),
    _player(5105, "David Raum", "Defender", 5, "1998-04-22", "Germany"),
    _player(5106, "Leon Goretzka", "Midfielder", 6, "1995-02-06", "Germany"),
    _player(5107, "Toni Kroos", "Midfielder", 8, "1990-01-04", "Germany"),
    _player(5108, "Serge Gnabry", "Forward", 7, "1995-07-14", "Germany"),
    _player(5109, "Jamal Musiala", "Forward", 11, "2003-02-26", "Germany"),
    _player(5110, "Kai Havertz", "Forward", 9, "1999-06-11", "Germany"),
    _player(5111, "Leroy Sane", "Forward", 10, "1996-01-11", "Germany"),
]

SPAIN_LINEUP = [
    _player(5201, "Unai Simon", "Goalkeeper", 1, "1997-06-11", "Spain"),
    _player(5202, "Dani Carvajal", "Defender", 2, "1992-01-11", "Spain"),
    _player(5203, "Aymeric Laporte", "Defender", 3, "1994-05-27", "Spain"),
    _player(5204, "Robin Le Normand", "Defender", 4, "1996-11-11", "Spain"),
    _player(5205, "Alejandro Grimaldo", "Defender", 5, "1995-09-20", "Spain"),
    _player(5206, "Rodri", "Midfielder", 6, "1996-06-22", "Spain"),
    _player(5207, "Fabian Ruiz", "Midfielder", 8, "1996-04-03", "Spain"),
    _player(5208, "Pedri", "Midfielder", 10, "2002-11-25", "Spain"),
    _player(5209, "Lamine Yamal", "Forward", 11, "2007-07-13", "Spain"),
    _player(5210, "Alvaro Morata", "Forward", 7, "1992-10-23", "Spain"),
    _player(5211, "Nico Williams", "Forward", 9, "2002-07-12", "Spain"),
]

FRANCE_LINEUP = [
    _player(5301, "Mike Maignan", "Goalkeeper", 1, "1995-07-03", "France"),
    _player(5302, "Jules Kounde", "Defender", 2, "1998-11-12", "France"),
    _player(5303, "William Saliba", "Defender", 3, "2001-03-24", "France"),
    _player(5304, "Ibrahima Konate", "Defender", 4, "1999-05-25", "France"),
    _player(5305, "Theo Hernandez", "Defender", 5, "1997-10-06", "France"),
    _player(5306, "Aurelien Tchouameni", "Midfielder", 6, "2000-01-27", "France"),
    _player(5307, "Adrien Rabiot", "Midfielder", 8, "1995-04-03", "France"),
    _player(5308, "Ousmane Dembele", "Forward", 7, "1997-05-15", "France"),
    _player(5309, "Kylian Mbappe", "Forward", 10, "1998-12-20", "France"),
    _player(5310, "Antoine Griezmann", "Forward", 11, "1991-03-21", "France"),
    _player(5311, "Randal Kolo Muani", "Forward", 9, "1998-12-05", "France"),
]

ARGENTINA_LINEUP = [
    _player(5401, "Emiliano Martinez", "Goalkeeper", 1, "1992-09-02", "Argentina"),
    _player(5402, "Nahuel Molina", "Defender", 2, "1998-04-06", "Argentina"),
    _player(5403, "Cristian Romero", "Defender", 4, "1998-04-27", "Argentina"),
    _player(5404, "Lisandro Martinez", "Defender", 3, "1998-01-18", "Argentina"),
    _player(5405, "Nicolas Tagliafico", "Defender", 6, "1992-08-31", "Argentina"),
    _player(5406, "Rodrigo De Paul", "Midfielder", 7, "1994-05-24", "Argentina"),
    _player(5407, "Enzo Fernandez", "Midfielder", 8, "2001-01-17", "Argentina"),
    _player(5408, "Alexis Mac Allister", "Midfielder", 10, "1998-12-24", "Argentina"),
    _player(5409, "Angel Di Maria", "Forward", 11, "1988-02-14", "Argentina"),
    _player(5410, "Lautaro Martinez", "Forward", 9, "1997-08-22", "Argentina"),
    _player(5411, "Julian Alvarez", "Forward", 17, "2000-01-31", "Argentina"),
]

PORTUGAL_LINEUP = [
    _player(5501, "Diogo Costa", "Goalkeeper", 1, "1999-09-19", "Portugal"),
    _player(5502, "Joao Cancelo", "Defender", 2, "1994-05-27", "Portugal"),
    _player(5503, "Ruben Dias", "Defender", 3, "1997-05-14", "Portugal"),
    _player(5504, "Goncalo Inacio", "Defender", 4, "2001-08-25", "Portugal"),
    _player(5505, "Nuno Mendes", "Defender", 5, "2002-06-19", "Portugal"),
    _player(5506, "Bruno Fernandes", "Midfielder", 8, "1994-09-08", "Portugal"),
    _player(5507, "Vitinha", "Midfielder", 10, "2000-02-13", "Portugal"),
    _player(5508, "Bernardo Silva", "Midfielder", 11, "1994-08-10", "Portugal"),
    _player(5509, "Rafael Leao", "Forward", 7, "1999-06-10", "Portugal"),
    _player(5510, "Goncalo Ramos", "Forward", 9, "2001-06-20", "Portugal"),
    _player(5511, "Cristiano Ronaldo", "Forward", 17, "1985-02-05", "Portugal"),
]

TEAM_LINEUPS = {
    "Brazil": BRAZIL_LINEUP,
    "Germany": GERMANY_LINEUP,
    "Spain": SPAIN_LINEUP,
    "France": FRANCE_LINEUP,
    "Argentina": ARGENTINA_LINEUP,
    "Portugal": PORTUGAL_LINEUP,
}

for squad in TEAM_LINEUPS.values():
    for player in squad:
        TEAM_INDEX[player["currentTeam"]["id"]].setdefault("squad", []).append(player)


PLAYER_AGGREGATES = {
    5009: {"goals": 4, "assists": 2, "minutesPlayed": 270, "yellowCards": 1, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5309: {"goals": 3, "assists": 1, "minutesPlayed": 250, "yellowCards": 0, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5208: {"goals": 3, "assists": 1, "minutesPlayed": 240, "yellowCards": 0, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    6001: {"goals": 2, "assists": 1, "minutesPlayed": 238, "yellowCards": 1, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5110: {"goals": 2, "assists": 0, "minutesPlayed": 225, "yellowCards": 0, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5109: {"goals": 2, "assists": 2, "minutesPlayed": 212, "yellowCards": 0, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5008: {"goals": 1, "assists": 2, "minutesPlayed": 210, "yellowCards": 0, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5511: {"goals": 1, "assists": 1, "minutesPlayed": 180, "yellowCards": 0, "redCards": 0, "startingXI": 2, "matchesOnPitch": 2},
    5410: {"goals": 1, "assists": 1, "minutesPlayed": 195, "yellowCards": 1, "redCards": 0, "startingXI": 2, "matchesOnPitch": 3},
    5408: {"goals": 1, "assists": 0, "minutesPlayed": 205, "yellowCards": 0, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5210: {"goals": 1, "assists": 1, "minutesPlayed": 190, "yellowCards": 0, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5006: {"goals": 0, "assists": 1, "minutesPlayed": 265, "yellowCards": 2, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5306: {"goals": 0, "assists": 1, "minutesPlayed": 240, "yellowCards": 1, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5106: {"goals": 0, "assists": 1, "minutesPlayed": 220, "yellowCards": 2, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
    5407: {"goals": 0, "assists": 1, "minutesPlayed": 215, "yellowCards": 0, "redCards": 0, "startingXI": 3, "matchesOnPitch": 3},
}

BELLINGHAM = _player(6001, "Jude Bellingham", "Midfielder", 10, "2003-06-29", "England")
TEAM_INDEX[1003].setdefault("squad", []).append(BELLINGHAM)

PLAYER_INDEX = {player["id"]: player for squad in TEAM_LINEUPS.values() for player in squad}
PLAYER_INDEX[BELLINGHAM["id"]] = BELLINGHAM

for player_id, aggregate in PLAYER_AGGREGATES.items():
    PLAYER_INDEX.setdefault(
        player_id,
        {
            "id": player_id,
            "name": f"Player {player_id}",
            "position": "Midfielder",
            "shirtNumber": 10,
            "dateOfBirth": "1999-01-01",
            "nationality": "World Cup",
            "flag_emoji": "🏳️",
            "currentTeam": {"id": 1001, "name": "Brazil"},
        },
    )


def _scoreline(home: int | None, away: int | None) -> dict:
    return {
        "winner": "HOME_TEAM" if (home or 0) > (away or 0) else "AWAY_TEAM" if (away or 0) > (home or 0) else "DRAW",
        "duration": "REGULAR",
        "fullTime": {"home": home, "away": away},
        "halfTime": {"home": home if home is not None else 0, "away": away if away is not None else 0},
    }


def _match_datetime(hour: int, minute: int = 0, day_offset: int = 0) -> str:
    return dt.datetime.combine(
        TODAY + dt.timedelta(days=day_offset),
        dt.time(hour=hour, minute=minute),
        tzinfo=dt.timezone.utc,
    ).isoformat().replace("+00:00", "Z")


def _build_match(
    match_id: int,
    home_name: str,
    away_name: str,
    status: str,
    home_goals: int | None,
    away_goals: int | None,
    minute: int | None,
    venue: str,
    group_code: str,
    matchday: int,
    kickoff: str,
    home_formation: str = "4-3-3",
    away_formation: str = "4-3-3",
    home_lineup: list | None = None,
    away_lineup: list | None = None,
    home_stats: dict | None = None,
    away_stats: dict | None = None,
    goals: list | None = None,
    bookings: list | None = None,
    substitutions: list | None = None,
    attendance: int = 0,
) -> dict:
    home_team = {**TEAM_NAME_INDEX[home_name], "formation": home_formation, "lineup": home_lineup or [], "bench": [], "statistics": home_stats or {}}
    away_team = {**TEAM_NAME_INDEX[away_name], "formation": away_formation, "lineup": away_lineup or [], "bench": [], "statistics": away_stats or {}}
    return {
        "id": match_id,
        "competition": {"id": WC_ID, "code": WC_CODE, "name": WC_NAME, "type": "CUP"},
        "season": {"year": WC_SEASON, "startDate": f"{WC_SEASON}-06-11", "endDate": f"{WC_SEASON}-07-19"},
        "utcDate": kickoff,
        "status": status,
        "minute": minute,
        "injuryTime": 0,
        "attendance": attendance,
        "venue": venue,
        "matchday": matchday,
        "stage": "GROUP_STAGE",
        "group": group_code,
        "homeTeam": home_team,
        "awayTeam": away_team,
        "score": _scoreline(home_goals, away_goals),
        "goals": goals or [],
        "bookings": bookings or [],
        "substitutions": substitutions or [],
        "odds": {"homeWin": 1.9, "draw": 3.4, "awayWin": 4.1},
    }


BRAZIL_GERMANY = _build_match(
    2026001,
    "Brazil",
    "Germany",
    "IN_PLAY",
    2,
    1,
    74,
    "AT&T Stadium, Dallas",
    "GROUP_A",
    2,
    _match_datetime(17, 0),
    home_lineup=BRAZIL_LINEUP,
    away_lineup=GERMANY_LINEUP,
    home_stats={"ball_possession": 58, "shots": 7, "shots_on_goal": 4, "corner_kicks": 3, "free_kicks": 11, "offsides": 1, "fouls": 9, "yellow_cards": 2, "red_cards": 0, "saves": 1},
    away_stats={"ball_possession": 42, "shots": 5, "shots_on_goal": 2, "corner_kicks": 3, "free_kicks": 8, "offsides": 2, "fouls": 11, "yellow_cards": 3, "red_cards": 0, "saves": 2},
    goals=[
        {"minute": 12, "type": "REGULAR", "team": {"id": 1001, "name": "Brazil"}, "scorer": {"id": 5009, "name": "Vinicius Jr."}, "assist": None, "score": {"home": 1, "away": 0}},
        {"minute": 41, "type": "REGULAR", "team": {"id": 1002, "name": "Germany"}, "scorer": {"id": 5110, "name": "Kai Havertz"}, "assist": None, "score": {"home": 1, "away": 1}},
        {"minute": 68, "type": "REGULAR", "team": {"id": 1001, "name": "Brazil"}, "scorer": {"id": 5009, "name": "Vinicius Jr."}, "assist": {"id": 5008, "name": "Rodrygo"}, "score": {"home": 2, "away": 1}},
    ],
    bookings=[
        {"minute": 28, "team": {"id": 1002, "name": "Germany"}, "player": {"id": 5106, "name": "Leon Goretzka"}, "card": "YELLOW"},
        {"minute": 71, "team": {"id": 1001, "name": "Brazil"}, "player": {"id": 5005, "name": "Alex Sandro"}, "card": "YELLOW"},
    ],
    substitutions=[
        {"minute": 55, "team": {"id": 1001, "name": "Brazil"}, "playerOut": {"id": 5008, "name": "Rodrygo"}, "playerIn": {"id": 5012, "name": "Savio"}},
    ],
    attendance=92000,
)

SPAIN_FRANCE = _build_match(
    2026002,
    "Spain",
    "France",
    "IN_PLAY",
    1,
    1,
    58,
    "NRG Stadium, Houston",
    "GROUP_B",
    2,
    _match_datetime(19, 0),
    home_lineup=SPAIN_LINEUP,
    away_lineup=FRANCE_LINEUP,
    home_stats={"ball_possession": 54, "shots": 8, "shots_on_goal": 3, "corner_kicks": 4, "free_kicks": 10, "offsides": 1, "fouls": 8, "yellow_cards": 1, "red_cards": 0, "saves": 2},
    away_stats={"ball_possession": 46, "shots": 6, "shots_on_goal": 3, "corner_kicks": 2, "free_kicks": 9, "offsides": 3, "fouls": 10, "yellow_cards": 2, "red_cards": 0, "saves": 2},
    goals=[
        {"minute": 19, "type": "REGULAR", "team": {"id": 1005, "name": "Spain"}, "scorer": {"id": 5208, "name": "Pedri"}, "assist": None, "score": {"home": 1, "away": 0}},
        {"minute": 51, "type": "REGULAR", "team": {"id": 1006, "name": "France"}, "scorer": {"id": 5309, "name": "Kylian Mbappe"}, "assist": None, "score": {"home": 1, "away": 1}},
    ],
    attendance=78120,
)

ARGENTINA_PORTUGAL = _build_match(
    2026003,
    "Argentina",
    "Portugal",
    "TIMED",
    None,
    None,
    None,
    "Mercedes-Benz Stadium, Atlanta",
    "GROUP_B",
    2,
    _match_datetime(22, 0),
    home_lineup=ARGENTINA_LINEUP,
    away_lineup=PORTUGAL_LINEUP,
)

ENGLAND_JAPAN = _build_match(
    2026004,
    "England",
    "Japan",
    "FINISHED",
    2,
    0,
    90,
    "SoFi Stadium, Los Angeles",
    "GROUP_A",
    2,
    _match_datetime(13, 30),
    home_lineup=[],
    away_lineup=[],
)

NETHERLANDS_SENEGAL = _build_match(
    2026005,
    "Netherlands",
    "Senegal",
    "FINISHED",
    1,
    1,
    90,
    "Levi's Stadium, Santa Clara",
    "GROUP_D",
    2,
    _match_datetime(10, 0),
)

SAMPLE_MATCHES = [BRAZIL_GERMANY, SPAIN_FRANCE, ARGENTINA_PORTUGAL, ENGLAND_JAPAN, NETHERLANDS_SENEGAL]
MATCH_INDEX = {match["id"]: match for match in SAMPLE_MATCHES}

STANDINGS_BLUEPRINT = {
    "GROUP_A": [
        {"team": "Brazil", "progression": [3, 6, 7], "won": 2, "draw": 1, "lost": 0, "gf": 5, "ga": 1, "form": ["W", "W", "D"]},
        {"team": "Germany", "progression": [0, 3, 6], "won": 2, "draw": 0, "lost": 1, "gf": 4, "ga": 3, "form": ["L", "W", "W"]},
        {"team": "England", "progression": [3, 3, 4], "won": 1, "draw": 1, "lost": 1, "gf": 3, "ga": 2, "form": ["W", "L", "D"]},
        {"team": "Japan", "progression": [0, 0, 0], "won": 0, "draw": 0, "lost": 3, "gf": 1, "ga": 7, "form": ["L", "L", "L"]},
    ],
    "GROUP_B": [
        {"team": "Spain", "progression": [1, 4, 5], "won": 1, "draw": 2, "lost": 0, "gf": 4, "ga": 2, "form": ["D", "W", "D"]},
        {"team": "France", "progression": [1, 4, 5], "won": 1, "draw": 2, "lost": 0, "gf": 4, "ga": 2, "form": ["D", "W", "D"]},
        {"team": "Argentina", "progression": [3, 4, 4], "won": 1, "draw": 1, "lost": 1, "gf": 3, "ga": 3, "form": ["W", "D", "L"]},
        {"team": "Portugal", "progression": [0, 3, 4], "won": 1, "draw": 1, "lost": 1, "gf": 2, "ga": 3, "form": ["L", "W", "D"]},
    ],
}

for group_code, teams in GROUP_INDEX.items():
    if group_code in STANDINGS_BLUEPRINT:
        continue
    entries = []
    for position, team in enumerate(teams):
        points = [3 - min(position, 2), 4 + max(0, 2 - position), 5 + max(0, 3 - position)]
        entries.append(
            {
                "team": team["name"],
                "progression": points,
                "won": max(0, 2 - position // 2),
                "draw": 1 if position in (1, 2) else 0,
                "lost": 1 if position > 1 else 0,
                "gf": 4 - position,
                "ga": 1 + position,
                "form": ["W" if position == 0 else "D" if position == 1 else "L", "W" if position < 2 else "L", "D" if position == 2 else "W" if position == 0 else "L"],
            }
        )
    STANDINGS_BLUEPRINT[group_code] = entries


LEADERBOARD_METRICS = {
    "Goals": [{"kind": "player", "id": pid, "value": stats["goals"]} for pid, stats in PLAYER_AGGREGATES.items()],
    "Assists": [{"kind": "player", "id": pid, "value": stats["assists"]} for pid, stats in PLAYER_AGGREGATES.items()],
    "Goal Involvements": [{"kind": "player", "id": pid, "value": stats["goals"] + stats["assists"]} for pid, stats in PLAYER_AGGREGATES.items()],
    "Yellow Cards": [{"kind": "player", "id": pid, "value": stats["yellowCards"]} for pid, stats in PLAYER_AGGREGATES.items()],
    "Red Cards": [{"kind": "player", "id": pid, "value": stats["redCards"]} for pid, stats in PLAYER_AGGREGATES.items()],
    "Clean Sheets": [
        {"kind": "team", "id": 1001, "value": 2},
        {"kind": "team", "id": 1006, "value": 2},
        {"kind": "team", "id": 1003, "value": 1},
        {"kind": "team", "id": 1005, "value": 1},
        {"kind": "team", "id": 1013, "value": 1},
    ],
}


def _request(path: str, ttl_key: str, params: dict | None = None, unfold: bool = False):
    headers = UNFOLD_HEADERS if unfold else DEFAULT_HEADERS
    return cached_get(f"{BASE_URL}{path}", headers=headers, ttl_key=ttl_key, params=params)


def _demo_mode() -> bool:
    # Synthetic tournament data is intentionally disabled so the UI never swaps
    # real feed gaps for seeded demo content.
    return False


def _sort_matches(matches: list[dict]) -> list[dict]:
    return sorted(matches, key=lambda match: match.get("utcDate", ""))


def _is_group_stage_match(match: dict) -> bool:
    stage = str(match.get("stage") or "").upper()
    return stage == "GROUP_STAGE" or bool(match.get("group"))


def _group_stage_matchday(match: dict) -> int | None:
    if not _is_group_stage_match(match):
        return None

    matchday = _coerce_int(match.get("matchday"))
    if matchday is None or matchday <= 0:
        return None
    return matchday


def _first_group_stage_matchday(matches: list[dict]) -> int | None:
    for match in _sort_matches(matches):
        matchday = _group_stage_matchday(match)
        if matchday is not None:
            return matchday
    return None


def _local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_match_datetime(match: dict) -> dt.datetime | None:
    kickoff = match.get("utcDate")
    if not kickoff:
        return None
    try:
        return dt.datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coerce_match_id(match_id: int | str | None) -> int | None:
    try:
        return int(str(match_id or "").strip())
    except ValueError:
        return None


def _coerce_int(value) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _is_local_matchday_match(match: dict, local_date: dt.date) -> bool:
    kickoff = _parse_match_datetime(match)
    if kickoff is None:
        return False
    return kickoff.astimezone().date() == local_date


def _match_season_year(match: dict) -> int | None:
    season = match.get("season")
    if isinstance(season, dict):
        for key in ("year", "startYear"):
            year = _coerce_int(season.get(key))
            if year is not None:
                return year
        start_date = str(season.get("startDate") or "").strip()
        if len(start_date) >= 4:
            return _coerce_int(start_date[:4])
        return None
    return _coerce_int(season)


def _is_world_cup_2026_match(match: dict) -> bool:
    competition = match.get("competition") if isinstance(match.get("competition"), dict) else {}
    competition_code = str(competition.get("code") or "").upper()
    competition_name = str(competition.get("name") or "").strip().casefold()
    competition_id = _coerce_int(competition.get("id"))
    season_year = _match_season_year(match)
    is_world_cup = competition_code == WC_CODE or competition_id == WC_ID or competition_name == WC_NAME.casefold()
    return is_world_cup and season_year == WC_SEASON


def _match_has_started(match: dict) -> bool:
    status = str(match.get("status") or "").upper()
    if status in UPCOMING_STATUSES or status in {"POSTPONED", "CANCELLED"}:
        return False
    if status in PLAYED_MATCH_STATUSES:
        return True
    minute = _coerce_int(match.get("minute"))
    if minute is not None and minute > 0:
        return True
    full_time = match.get("score", {}).get("fullTime", {}) if isinstance(match.get("score"), dict) else {}
    return full_time.get("home") is not None and full_time.get("away") is not None


def _resolve_match_score(match: dict) -> tuple[int, int]:
    score = match.get("score") if isinstance(match.get("score"), dict) else {}
    full_time = score.get("fullTime") if isinstance(score.get("fullTime"), dict) else {}
    home = _coerce_int(full_time.get("home"))
    away = _coerce_int(full_time.get("away"))
    if home is not None and away is not None:
        return home, away

    home_team_id = match.get("homeTeam", {}).get("id")
    away_team_id = match.get("awayTeam", {}).get("id")
    home_goals = 0
    away_goals = 0
    for goal in match.get("goals", []) if isinstance(match.get("goals"), list) else []:
        goal_team = goal.get("team") if isinstance(goal.get("team"), dict) else {}
        goal_team_id = goal_team.get("id")
        if goal_team_id == home_team_id:
            home_goals += 1
        elif goal_team_id == away_team_id:
            away_goals += 1
    return home_goals, away_goals


def _resolve_team_score(match: dict, team_id: int) -> tuple[int, int]:
    home_goals, away_goals = _resolve_match_score(match)
    is_home = match.get("homeTeam", {}).get("id") == team_id
    return (home_goals, away_goals) if is_home else (away_goals, home_goals)


def _goal_time_bracket(goal: dict) -> str:
    minute = _coerce_int(goal.get("minute")) or 0
    injury_time = _coerce_int(goal.get("injuryTime")) or 0

    if minute > 90 or (minute == 90 and injury_time > 0):
        return "90+"
    if minute <= 15:
        return "0-15"
    if minute <= 30:
        return "16-30"
    if minute <= 45:
        return "31-45"
    if minute <= 60:
        return "46-60"
    if minute <= 75:
        return "61-75"
    return "76-90"


def _date_query_bounds(local_date: dt.date) -> tuple[str, str]:
    return (
        (local_date - dt.timedelta(days=1)).isoformat(),
        (local_date + dt.timedelta(days=1)).isoformat(),
    )


def _is_awaiting_live_match(match: dict, now_utc: dt.datetime | None = None) -> bool:
    if match.get("status") not in UPCOMING_STATUSES:
        return False
    kickoff = _parse_match_datetime(match)
    if kickoff is None:
        return False

    current_utc = now_utc or _utc_now()
    if kickoff > current_utc:
        return False

    return current_utc <= kickoff + dt.timedelta(minutes=LIVE_FEED_GRACE_MINUTES)


def _enrich_featured_live_match(match: dict | None, today_matches: list[dict]) -> dict | None:
    if not isinstance(match, dict) or match.get("id") is None:
        return match

    same_day_match = next((item for item in today_matches if item.get("id") == match.get("id")), None)
    detailed_match = get_match(match["id"])
    if detailed_match.get("id") == match["id"]:
        return detailed_match
    if same_day_match:
        return same_day_match
    return match


def _zero_tournament_summary() -> dict:
    return {
        "teams": 48,
        "matches_played": 0,
        "matches_total": 104,
        "goals_scored": 0,
        "goals_per_match": 0,
        "live_now": 0,
    }


def _empty_standings_payload() -> dict:
    return {"standings": []}


def _empty_team_analysis(team: dict | None = None) -> dict:
    return {
        "team": team or {},
        "matches": [],
        "played_matches": [],
        "latest_match": {},
        "timeline": [],
        "goals_by_bracket": {label: 0 for label in GOAL_TIME_BRACKETS},
        "age_buckets": {},
        "wins": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
    }


def _known_match(match_id: int) -> dict:
    for match in get_live_matches() + get_today_matches():
        if match.get("id") == match_id:
            return match
    return {}


def _load_matches_for_local_date_result(
    local_date: dt.date,
    *,
    include_live_overflow: bool = False,
) -> tuple[list[dict], bool]:
    if _demo_mode():
        demo_matches = [
            match
            for match in SAMPLE_MATCHES
            if _is_local_matchday_match(match, local_date)
            or (include_live_overflow and match.get("status") in LIVE_STATUSES)
        ]
        return demo_matches, True
    if not API_KEY:
        return [], False

    date_from, date_to = _date_query_bounds(local_date)
    params = {"dateFrom": date_from, "dateTo": date_to}
    try:
        matches = _request(f"/competitions/{WC_CODE}/matches", "today", params=params, unfold=True).get("matches", [])
        normalized_matches = [_normalize_match(match) for match in matches]
        filtered_matches = [
            match
            for match in normalized_matches
            if _is_local_matchday_match(match, local_date)
            or (include_live_overflow and match.get("status") in LIVE_STATUSES)
        ]
        return filtered_matches, True
    except Exception:
        return [], False


def _load_live_matches_result() -> tuple[list[dict], bool]:
    today_matches, today_feed_ok = _load_today_matches_result()
    return [match for match in today_matches if match.get("status") in LIVE_STATUSES], today_feed_ok


def _load_today_matches_result() -> tuple[list[dict], bool]:
    return _load_matches_for_local_date_result(_local_now().date(), include_live_overflow=True)


def get_teams() -> list[dict]:
    if _demo_mode():
        return TEAMS
    if not API_KEY:
        return []
    try:
        return [_normalize_team(team) for team in _request(f"/competitions/{WC_CODE}/teams", "team").get("teams", [])]
    except Exception:
        return []


def get_team(team_id: int) -> dict:
    if _demo_mode():
        return _demo_team(team_id)
    if not API_KEY:
        return {}
    try:
        return _normalize_team(_request(f"/teams/{team_id}", "team"))
    except Exception:
        return {}


def _demo_team(team_id: int) -> dict:
    team = dict(TEAM_INDEX.get(team_id, TEAMS[0]))
    if "squad" not in team:
        team["squad"] = _generate_generic_squad(team)
    return team


def _generate_generic_squad(team: dict) -> list[dict]:
    lineup = []
    positions = [
        ("Goalkeeper", 1),
        ("Defender", 2),
        ("Defender", 3),
        ("Defender", 4),
        ("Defender", 5),
        ("Midfielder", 6),
        ("Midfielder", 8),
        ("Midfielder", 10),
        ("Forward", 7),
        ("Forward", 9),
        ("Forward", 11),
        ("Forward", 14),
        ("Midfielder", 16),
        ("Defender", 18),
        ("Goalkeeper", 23),
    ]
    for index, (position, shirt_number) in enumerate(positions, start=1):
        lineup.append(
            {
                "id": team["id"] * 100 + index,
                "name": f"{team['name']} Player {index}",
                "shortName": f"P{index}",
                "position": position,
                "shirtNumber": shirt_number,
                "dateOfBirth": f"199{index % 10}-0{(index % 8) + 1}-1{index % 9}",
                "nationality": team["name"],
                "flag_emoji": team["flag_emoji"],
                "currentTeam": {"id": team["id"], "name": team["name"]},
            }
        )
    return lineup


def get_live_matches() -> list[dict]:
    matches, _ = _load_live_matches_result()
    return matches


def get_today_matches() -> list[dict]:
    matches, _ = _load_today_matches_result()
    return matches


def get_current_group_stage_matchday() -> int | None:
    live_matchday = _first_group_stage_matchday(get_live_matches())
    if live_matchday is not None:
        return live_matchday

    today_matchday = _first_group_stage_matchday(get_today_matches())
    if today_matchday is not None:
        return today_matchday

    upcoming_matchday = _first_group_stage_matchday(get_upcoming_matches(limit=None, horizon_days=21))
    if upcoming_matchday is not None:
        return upcoming_matchday

    return None


def get_completed_matches() -> list[dict]:
    if _demo_mode():
        return sorted(
            [match for match in SAMPLE_MATCHES if match.get("status") in COMPLETED_STATUSES],
            key=lambda match: match.get("utcDate", ""),
            reverse=True,
        )
    if not API_KEY:
        return []
    try:
        matches = _request(f"/competitions/{WC_CODE}/matches", "historical").get("matches", [])
        completed_matches = [
            _normalize_match(match)
            for match in matches
            if match.get("status") in COMPLETED_STATUSES
        ]
        return sorted(completed_matches, key=lambda match: match.get("utcDate", ""), reverse=True)
    except Exception:
        return []


def get_all_matches() -> list[dict]:
    if _demo_mode():
        return _sort_matches([_normalize_match(match) for match in SAMPLE_MATCHES])
    if not API_KEY:
        return []
    try:
        matches = _request(f"/competitions/{WC_CODE}/matches", "historical").get("matches", [])
        normalized_matches = [_normalize_match(match) for match in matches]
        world_cup_matches = [match for match in normalized_matches if _is_world_cup_2026_match(match)]
        return sorted(
            world_cup_matches,
            key=lambda match: (match.get("utcDate", ""), _coerce_int(match.get("id")) or 0),
        )
    except Exception:
        return []


def get_upcoming_matches(limit: int | None = 4, horizon_days: int = 7) -> list[dict]:
    if limit is not None and limit <= 0:
        return []

    current_utc = _utc_now()
    if _demo_mode():
        upcoming = [
            match
            for match in SAMPLE_MATCHES
            if match.get("status") in UPCOMING_STATUSES
            and (_parse_match_datetime(match) or current_utc) >= current_utc
        ]
        upcoming = _sort_matches(upcoming)
        return upcoming[:limit] if limit is not None else upcoming
    if not API_KEY:
        return []

    date_from = (current_utc.date() - dt.timedelta(days=1)).isoformat()
    date_to = (current_utc.date() + dt.timedelta(days=horizon_days)).isoformat()
    params = {"dateFrom": date_from, "dateTo": date_to}
    try:
        matches = _request(f"/competitions/{WC_CODE}/matches", "today", params=params).get("matches", [])
        upcoming = [
            _normalize_match(match)
            for match in matches
            if match.get("status") in UPCOMING_STATUSES
            and (_parse_match_datetime(match) or current_utc) >= current_utc
        ]
        upcoming = _sort_matches(upcoming)
        return upcoming[:limit] if limit is not None else upcoming
    except Exception:
        return []


def get_ticker_matches() -> list[dict]:
    live_matches = _sort_matches(get_live_matches())[:1]
    upcoming_matches = get_upcoming_matches(limit=None, horizon_days=2)
    live_ids = {match.get("id") for match in live_matches}
    upcoming_matches = [match for match in upcoming_matches if match.get("id") not in live_ids]
    if live_matches:
        return [*live_matches, *upcoming_matches[:2]]
    return upcoming_matches[:3]


def get_default_match_id() -> int | None:
    live_matches = get_live_matches()
    if live_matches:
        return live_matches[0]["id"]
    today_matches = _sort_matches(get_today_matches())
    return today_matches[0]["id"] if today_matches else None


def get_match(match_id: int | str) -> dict:
    if _demo_mode():
        resolved_id = _coerce_match_id(match_id)
        if resolved_id is not None:
            return MATCH_INDEX.get(resolved_id, BRAZIL_GERMANY)
        return BRAZIL_GERMANY

    resolved_id = _coerce_match_id(match_id)
    if resolved_id is None:
        return {}
    if not API_KEY:
        return _known_match(resolved_id)
    try:
        return _normalize_match(_request(f"/matches/{resolved_id}", "live", unfold=True))
    except Exception:
        return _known_match(resolved_id)


def get_live_hub_payload() -> dict:
    today_matches, today_feed_ok = _load_today_matches_result()
    replay_matches = get_completed_matches()
    live_matches = _sort_matches([match for match in today_matches if match.get("status") in LIVE_STATUSES])
    today_matches = _sort_matches(today_matches)
    live_feed_ok = today_feed_ok
    awaiting_live_matches = [match for match in today_matches if _is_awaiting_live_match(match)]
    next_match = next((match for match in today_matches if match.get("status") in UPCOMING_STATUSES), None)
    recent_result = next((match for match in reversed(today_matches) if match.get("status") in COMPLETED_STATUSES), None)

    if live_matches:
        state = "live_match_available"
    elif awaiting_live_matches:
        state = "awaiting_live_feed"
    elif next_match:
        state = "no_live_match_but_upcoming_exists"
    elif recent_result:
        state = "no_live_match_but_recent_final_exists"
    elif today_matches:
        state = "no_matches_available"
    elif live_feed_ok or today_feed_ok:
        state = "no_matches_available"
    else:
        state = "data_unavailable"

    featured_match = _enrich_featured_live_match(live_matches[0], today_matches) if live_matches else None

    return {
        "state": state,
        "live_matches": live_matches,
        "awaiting_live_matches": awaiting_live_matches,
        "today_matches": today_matches,
        "replay_matches": replay_matches,
        "featured_match": featured_match,
        "next_match": next_match,
        "recent_result": recent_result,
        "is_demo_mode": _demo_mode(),
        "has_api_key": bool(API_KEY),
    }


def get_standings(matchday: int | None = None) -> dict:
    if _demo_mode():
        return _demo_standings(matchday)
    if not API_KEY:
        return _empty_standings_payload()
    try:
        params = {"matchday": matchday} if matchday else None
        return _normalize_standings_payload(_request(f"/competitions/{WC_CODE}/standings", "standings", params=params))
    except Exception:
        return _empty_standings_payload()


def _demo_standings(matchday: int | None = None) -> dict:
    standing_groups = []
    for group_code, rows in STANDINGS_BLUEPRINT.items():
        table = []
        for row in rows:
            team = TEAM_NAME_INDEX[row["team"]]
            played = matchday or 3
            points = row["progression"][played - 1]
            wins = min(row["won"], points // 3)
            draws = max(0, min(row["draw"], played - wins - row["lost"]))
            losses = max(0, played - wins - draws)
            goal_delta = row["gf"] - row["ga"]
            table.append(
                {
                    "position": 0,
                    "team": team,
                    "playedGames": played,
                    "won": wins,
                    "draw": draws,
                    "lost": losses,
                    "goalsFor": max(row["gf"] - max(0, 3 - played), 0),
                    "goalsAgainst": max(row["ga"] - max(0, 2 - played), 0),
                    "goalDifference": goal_delta,
                    "points": points,
                    "form": ",".join(row["form"][-played:]),
                    "progression": row["progression"],
                }
            )
        table = sorted(table, key=lambda item: (item["points"], item["goalDifference"], item["goalsFor"]), reverse=True)
        for position, team_row in enumerate(table, start=1):
            team_row["position"] = position
        standing_groups.append({"group": group_code.replace("_", " "), "type": "TOTAL", "table": table})
    standing_groups = sorted(standing_groups, key=lambda item: item["group"])
    return {"standings": standing_groups}


def get_group_options() -> list[dict]:
    standings = get_standings().get("standings", [])
    return [{"value": group["group"], "label": group["group"].replace("_", " ")} for group in standings]


def get_group_table(group_name: str) -> dict:
    for group in get_standings().get("standings", []):
        if group["group"] == group_name or group["group"].replace("_", " ") == group_name:
            return group
    return {}


def get_scorers(limit: int = 50) -> list[dict]:
    if _demo_mode():
        return _demo_scorers(limit)
    if not API_KEY:
        return []
    try:
        return _normalize_scorers_payload(_request(f"/competitions/{WC_CODE}/scorers", "scorers", params={"limit": limit}).get("scorers", []))
    except Exception:
        return []


def _demo_scorers(limit: int) -> list[dict]:
    rows = []
    for player_id, stats in PLAYER_AGGREGATES.items():
        player = PLAYER_INDEX[player_id]
        team = TEAM_INDEX[player["currentTeam"]["id"]]
        rows.append(
            {
                "player": {"id": player_id, "name": player["name"], "dateOfBirth": player.get("dateOfBirth")},
                "team": team,
                "playedMatches": stats["matchesOnPitch"],
                "goals": stats["goals"],
                "assists": stats["assists"],
                "penalties": 0,
            }
        )
    rows.sort(key=lambda row: (row["goals"], row["assists"]), reverse=True)
    return rows[:limit]


def _coerce_stat_number(value) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _profile_from_scorer_row(row: dict | None) -> dict:
    row = dict(row or {})
    team = _normalize_team(row.get("team"))
    player = _normalize_player_entry(row.get("player"), team)
    goals = _coerce_stat_number(row.get("goals"))
    assists = _coerce_stat_number(row.get("assists"))
    played_matches = _coerce_stat_number(row.get("playedMatches"))
    return {
        **player,
        "goals": goals,
        "assists": assists,
        "playedMatches": played_matches,
        "matchesOnPitch": played_matches,
        "goalInvolvements": goals + assists,
    }


def get_person(player_id: int) -> dict:
    if _demo_mode():
        return PLAYER_INDEX.get(player_id, next(iter(PLAYER_INDEX.values())))
    if not API_KEY:
        return {}
    try:
        return _normalize_player_entry(_request(f"/persons/{player_id}", "player"))
    except Exception:
        return {}


def get_person_matches(player_id: int) -> dict:
    if _demo_mode():
        return PLAYER_AGGREGATES.get(player_id, {"goals": 0, "assists": 0, "minutesPlayed": 0, "yellowCards": 0, "redCards": 0, "startingXI": 0, "matchesOnPitch": 0})
    if not API_KEY:
        return {"goals": 0, "assists": 0, "minutesPlayed": 0, "yellowCards": 0, "redCards": 0, "startingXI": 0, "matchesOnPitch": 0}
    try:
        return _request(f"/persons/{player_id}/matches", "player")
    except Exception:
        return {"goals": 0, "assists": 0, "minutesPlayed": 0, "yellowCards": 0, "redCards": 0, "startingXI": 0, "matchesOnPitch": 0}


def get_all_player_profiles() -> list[dict]:
    scorer_profiles = []
    seen_ids = set()
    for row in get_scorers(limit=100):
        profile = _profile_from_scorer_row(row)
        player_id = profile.get("id")
        if player_id is None or player_id in seen_ids:
            continue
        scorer_profiles.append(profile)
        seen_ids.add(player_id)

    if scorer_profiles:
        scorer_profiles.sort(
            key=lambda player: (
                player.get("goals", 0),
                player.get("assists", 0),
                player.get("playedMatches", 0),
                player.get("name", ""),
            ),
            reverse=True,
        )
        return scorer_profiles

    if not _demo_mode():
        return []

    profiles = []
    for player_id, stats in PLAYER_AGGREGATES.items():
        player = dict(get_person(player_id))
        player.update(stats)
        profiles.append(player)
    profiles.sort(key=lambda player: (player["goals"], player["assists"]), reverse=True)
    return profiles


def get_top_player_id() -> int | None:
    players = get_all_player_profiles()
    if players:
        return players[0]["id"]
    scorers = get_scorers(1)
    return scorers[0]["player"]["id"] if scorers else None


def get_tournament_summary() -> dict:
    if _demo_mode():
        live_now = len(get_live_matches())
        return {
            "teams": 48,
            "matches_played": 36,
            "matches_total": 104,
            "goals_scored": 89,
            "goals_per_match": 2.47,
            "live_now": live_now,
        }
    if not API_KEY:
        return _zero_tournament_summary()
    try:
        matches = _request(f"/competitions/{WC_CODE}/matches", "historical").get("matches", [])
        finished_matches = [match for match in matches if match.get("status") == "FINISHED"]
        total_goals = sum((match.get("score", {}).get("fullTime", {}).get("home") or 0) + (match.get("score", {}).get("fullTime", {}).get("away") or 0) for match in finished_matches)
        return {
            "teams": 48,
            "matches_played": len(finished_matches),
            "matches_total": 104,
            "goals_scored": total_goals,
            "goals_per_match": round(safe_div(total_goals, len(finished_matches)), 2),
            "live_now": len(get_live_matches()),
        }
    except Exception:
        return _zero_tournament_summary()


def get_team_matches(team_id: int) -> list[dict]:
    if _demo_mode():
        return _demo_team_matches(TEAM_INDEX.get(team_id, TEAMS[0]))
    if not API_KEY:
        return []
    params = {"competitions": WC_CODE, "season": WC_SEASON}
    try:
        matches = _request(f"/teams/{team_id}/matches", "historical", params=params, unfold=True).get("matches", [])
    except Exception:
        try:
            matches = _request(f"/teams/{team_id}/matches", "historical", unfold=True).get("matches", [])
        except Exception:
            return []
    normalized_matches = [_normalize_match(match) for match in matches]
    return [match for match in normalized_matches if _is_world_cup_2026_match(match)]


def _demo_team_matches(team: dict) -> list[dict]:
    explicit = [match for match in SAMPLE_MATCHES if match["homeTeam"]["id"] == team["id"] or match["awayTeam"]["id"] == team["id"]]
    opponents = [opponent for opponent in GROUP_INDEX[team["group"]] if opponent["id"] != team["id"]]
    generated = []
    for index, opponent in enumerate(opponents[:3], start=1):
        home_team = team if index % 2 else opponent
        away_team = opponent if index % 2 else team
        home_goals = max(0, 2 - index + (0 if home_team["id"] == team["id"] else -1))
        away_goals = max(0, 1 + (1 if away_team["id"] == team["id"] and index == 3 else 0))
        generated.append(
            _build_match(
                match_id=team["id"] * 10 + index,
                home_name=home_team["name"],
                away_name=away_team["name"],
                status="FINISHED" if index < 3 else "TIMED",
                home_goals=home_goals if index < 3 else None,
                away_goals=away_goals if index < 3 else None,
                minute=90 if index < 3 else None,
                venue=f"{home_team['name']} Park",
                group_code=team["group"],
                matchday=index,
                kickoff=_match_datetime(14 + index, 0, day_offset=index - 2),
                home_lineup=TEAM_LINEUPS.get(home_team["name"], _generate_generic_squad(home_team)[:11]),
                away_lineup=TEAM_LINEUPS.get(away_team["name"], _generate_generic_squad(away_team)[:11]),
            )
        )
    if explicit:
        seen_ids = {match["id"] for match in explicit}
        explicit.extend([match for match in generated if match["id"] not in seen_ids])
        explicit.sort(key=lambda match: match.get("utcDate", ""), reverse=True)
        return explicit
    generated.sort(key=lambda match: match.get("utcDate", ""), reverse=True)
    return generated


def get_player_options() -> list[dict]:
    return [{"value": str(player["id"]), "label": player["name"]} for player in get_all_player_profiles()]


def get_team_options() -> list[dict]:
    return [{"value": str(team["id"]), "label": f"{team['flag_emoji']} {team['name']}"} for team in get_teams()]


def get_team_map_entries() -> list[dict]:
    entries = []
    for team in get_teams():
        area = team.get("area") if isinstance(team.get("area"), dict) else {}
        candidates = [
            team.get("tla"),
            area.get("code"),
            area.get("countryCode"),
            team.get("name"),
            team.get("shortName"),
            area.get("name"),
        ]
        map_code = next((code for code in (_lookup_team_map_code(candidate) for candidate in candidates) if code), None)
        if not map_code:
            continue
        entries.append(
            {
                "id": team["id"],
                "name": team["name"],
                "flag_emoji": team.get("flag_emoji", _resolve_flag_emoji(team)),
                "map_code": map_code,
            }
        )
    return entries


def get_default_team_deep_dive_id() -> int | None:
    completed_matches = get_completed_matches()

    for match in completed_matches:
        winner = match.get("score", {}).get("winner")
        if winner == "HOME_TEAM":
            return match.get("homeTeam", {}).get("id")
        if winner == "AWAY_TEAM":
            return match.get("awayTeam", {}).get("id")

    map_entries = get_team_map_entries()
    if map_entries:
        return map_entries[0]["id"]
    return None


def get_tournament_average_metrics() -> dict:
    players = get_all_player_profiles()
    averages = {}
    for key in ["goals", "assists", "minutesPlayed", "yellowCards", "redCards", "startingXI", "matchesOnPitch"]:
        values = [player.get(key, 0) for player in players]
        averages[key] = round(mean(values), 2) if values else 0
    return averages


def _disciplinary_metric_key(card: str | None) -> str | None:
    normalized = str(card or "").upper()
    if normalized == "YELLOW":
        return "yellowCards"
    if "RED" in normalized:
        return "redCards"
    return None


def _completed_match_leaderboard_ids() -> tuple[int, ...]:
    match_ids = {
        match_id
        for match in get_completed_matches()
        if (match_id := _coerce_match_id(match.get("id"))) is not None
    }
    return tuple(sorted(match_ids))


@lru_cache(maxsize=8)
def _completed_match_leaderboards(match_ids: tuple[int, ...]) -> dict[str, list[dict]]:
    player_stats: dict[int, dict] = {}
    team_lookup: dict[int, dict] = {}
    clean_sheet_counts: defaultdict[int, int] = defaultdict(int)

    for match_id in match_ids:
        match = get_match(match_id)
        if not match:
            continue

        home_team = _normalize_team(match.get("homeTeam"))
        away_team = _normalize_team(match.get("awayTeam"))
        home_team_id = _coerce_int(home_team.get("id"))
        away_team_id = _coerce_int(away_team.get("id"))
        if home_team_id is not None:
            team_lookup[home_team_id] = home_team
        if away_team_id is not None:
            team_lookup[away_team_id] = away_team

        home_goals, away_goals = _resolve_match_score(match)
        if away_goals == 0 and home_team_id is not None:
            clean_sheet_counts[home_team_id] += 1
        if home_goals == 0 and away_team_id is not None:
            clean_sheet_counts[away_team_id] += 1

        for booking in match.get("bookings", []) if isinstance(match.get("bookings"), list) else []:
            metric_key = _disciplinary_metric_key(booking.get("card"))
            if metric_key is None:
                continue

            player = _normalize_player_entry(booking.get("player"))
            team = _normalize_team(booking.get("team"))
            player_id = _coerce_int(player.get("id"))
            if player_id is None:
                continue

            row = player_stats.setdefault(
                player_id,
                {
                    "id": player_id,
                    "name": player.get("name", f"Player {player_id}"),
                    "flag_emoji": team.get("flag_emoji", player.get("flag_emoji", "🏳️")),
                    "team_name": team.get("name", player.get("nationality", "Unknown")),
                    "photo_target": player.get("name", f"Player {player_id}"),
                    "yellowCards": 0,
                    "redCards": 0,
                },
            )
            row[metric_key] += 1
            if row.get("flag_emoji") in {None, "", "🏳️"}:
                row["flag_emoji"] = team.get("flag_emoji", "🏳️")
            if row.get("team_name") in {None, "", "Unknown"} and team.get("name"):
                row["team_name"] = team["name"]

    yellow_cards = [
        {
            "kind": "player",
            "id": row["id"],
            "value": row["yellowCards"],
            "name": row["name"],
            "flag_emoji": row["flag_emoji"],
            "team_name": row["team_name"],
            "photo_target": row["photo_target"],
        }
        for row in player_stats.values()
        if row["yellowCards"] > 0
    ]
    red_cards = [
        {
            "kind": "player",
            "id": row["id"],
            "value": row["redCards"],
            "name": row["name"],
            "flag_emoji": row["flag_emoji"],
            "team_name": row["team_name"],
            "photo_target": row["photo_target"],
        }
        for row in player_stats.values()
        if row["redCards"] > 0
    ]
    clean_sheets = [
        {
            "kind": "team",
            "id": team_id,
            "value": clean_sheet_count,
            "name": team_lookup.get(team_id, {}).get("name", f"Team {team_id}"),
            "flag_emoji": team_lookup.get(team_id, {}).get("flag_emoji", "🏳️"),
            "team_name": team_lookup.get(team_id, {}).get("name", f"Team {team_id}"),
            "photo_target": team_lookup.get(team_id, {}).get("name", f"Team {team_id}"),
        }
        for team_id, clean_sheet_count in clean_sheet_counts.items()
        if clean_sheet_count > 0
    ]

    for entries in (yellow_cards, red_cards, clean_sheets):
        entries.sort(key=lambda item: (item["value"], item["name"]), reverse=True)

    return {
        "Yellow Cards": yellow_cards,
        "Red Cards": red_cards,
        "Clean Sheets": clean_sheets,
    }


def get_leaderboard(metric: str) -> list[dict]:
    if metric in {"Goals", "Assists", "Goal Involvements"}:
        metric_key = {
            "Goals": "goals",
            "Assists": "assists",
            "Goal Involvements": "goalInvolvements",
        }[metric]
        entries = []
        for player in get_all_player_profiles():
            team = _normalize_team(player.get("currentTeam")) if isinstance(player.get("currentTeam"), dict) else {}
            entries.append(
                {
                    "kind": "player",
                    "id": player["id"],
                    "value": player.get(metric_key, 0),
                    "name": player.get("name", f"Player {player['id']}"),
                    "flag_emoji": player.get("flag_emoji", team.get("flag_emoji", "🏳️")),
                    "team_name": team.get("name", player.get("nationality", "Unknown")),
                    "photo_target": player.get("name", f"Player {player['id']}"),
                }
            )
        entries.sort(key=lambda item: (item["value"], item["name"]), reverse=True)
        return entries

    if metric in {"Yellow Cards", "Red Cards", "Clean Sheets"}:
        completed_match_ids = _completed_match_leaderboard_ids()
        if completed_match_ids:
            return _completed_match_leaderboards(completed_match_ids).get(metric, [])

    if not _demo_mode():
        return []

    entries = []
    for row in LEADERBOARD_METRICS.get(metric, []):
        if row["kind"] == "player":
            player = get_person(row["id"])
            team = _normalize_team(player.get("currentTeam")) if isinstance(player.get("currentTeam"), dict) else TEAM_INDEX.get(1001, TEAMS[0])
            entries.append(
                {
                    **row,
                    "name": player["name"],
                    "flag_emoji": team.get("flag_emoji", "🏳️"),
                    "team_name": team.get("name", player.get("nationality", "Unknown")),
                    "photo_target": player["name"],
                }
            )
        else:
            team = TEAM_INDEX.get(row["id"], TEAMS[0])
            entries.append(
                {
                    **row,
                    "name": team["name"],
                    "flag_emoji": team["flag_emoji"],
                    "team_name": team["name"],
                    "photo_target": team["name"],
                }
            )
    entries.sort(key=lambda item: item["value"], reverse=True)
    return entries


def get_team_analysis(team_id: int) -> dict:
    team = get_team(team_id)
    if not team:
        return _empty_team_analysis()

    matches = sorted(get_team_matches(team_id), key=lambda match: match.get("utcDate", ""), reverse=True)
    played_matches = [match for match in matches if _match_has_started(match)]
    latest_match = next(
        (
            match
            for match in matches
            if _match_has_started(match)
            and (
                (match["homeTeam"]["id"] == team_id and match["homeTeam"].get("lineup"))
                or (match["awayTeam"]["id"] == team_id and match["awayTeam"].get("lineup"))
            )
        ),
        matches[0] if matches else {},
    )
    squad = team.get("squad") or []
    wins = 0
    goals_for = 0
    goals_against = 0
    timeline = []
    brackets = {label: 0 for label in GOAL_TIME_BRACKETS}

    timeline_matches = sorted(
        played_matches,
        key=lambda match: (
            match.get("matchday") if match.get("matchday") is not None else 999,
            match.get("utcDate", ""),
        ),
    )
    for match in timeline_matches:
        team_goals, opp_goals = _resolve_team_score(match, team_id)
        goals_for += team_goals
        goals_against += opp_goals
        result = "W" if team_goals > opp_goals else "D" if team_goals == opp_goals else "L"
        wins += result == "W"
        is_home = match["homeTeam"]["id"] == team_id
        opponent = match["awayTeam"] if is_home else match["homeTeam"]
        timeline.append(
            {
                "label": f"MD{match.get('matchday', len(timeline) + 1)}",
                "result": result,
                "opponent": opponent["name"],
                "score": f"{team_goals}-{opp_goals}",
            }
        )
        for goal in match.get("goals", []) if isinstance(match.get("goals"), list) else []:
            goal_team = goal.get("team") if isinstance(goal.get("team"), dict) else {}
            if goal_team.get("id") == team_id:
                brackets[_goal_time_bracket(goal)] += 1

    age_buckets = defaultdict(int)
    for player in squad:
        age = calculate_age(player.get("dateOfBirth")) or 24
        if age < 22:
            bucket = "U22"
        elif age < 26:
            bucket = "22-25"
        elif age < 30:
            bucket = "26-29"
        elif age < 34:
            bucket = "30-33"
        else:
            bucket = "34+"
        age_buckets[bucket] += 1

    return {
        "team": team,
        "matches": matches,
        "played_matches": played_matches,
        "latest_match": latest_match,
        "timeline": timeline,
        "goals_by_bracket": brackets,
        "age_buckets": dict(age_buckets),
        "wins": wins,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_difference": goals_for - goals_against,
    }
