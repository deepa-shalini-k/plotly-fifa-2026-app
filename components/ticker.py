from __future__ import annotations

import dash_mantine_components as dmc

from components.local_time import render_local_time
from components.match_formatting import live_minute_label


def _status_text(match: dict) -> tuple[object, str]:
    status = match.get("status")
    if status in {"IN_PLAY", "PAUSED"}:
        return live_minute_label(match, pad_numeric=True) or "LIVE", "#00D084"
    if status == "FINISHED":
        return "FT", "#A3A8BC"

    kickoff = match.get("utcDate")
    if kickoff:
        return render_local_time(kickoff), "#7A8099"
    return "TBD", "#7A8099"


def _score_text(match: dict) -> tuple[str, str]:
    status = match.get("status")
    score = match.get("score", {})
    full_time = score.get("fullTime", {})
    home = full_time.get("home")
    away = full_time.get("away")
    if home is None or away is None:
        if status in {"TIMED", "SCHEDULED"}:
            return "vs", "#7A8099"
        return "–", "#7A8099"
    if status in {"IN_PLAY", "PAUSED"}:
        return f"{home} - {away}", "#00D084"
    return f"{home} - {away}", "#E8EAF0" if status == "FINISHED" else "#7A8099"


def _ticker_segment(match: dict):
    home = match.get("homeTeam", {})
    away = match.get("awayTeam", {})
    status_text, status_color = _status_text(match)
    score_text, score_color = _score_text(match)
    return dmc.Group(
        [
            dmc.Text(home.get("flag_emoji", "🏳️"), size="lg"),
            dmc.Text(home.get("tla", home.get("shortName", "HOME")), fw=500),
            dmc.Text(score_text, c=score_color, fw=700, className="score-mono"),
            dmc.Text(away.get("tla", away.get("shortName", "AWAY")), fw=500),
            dmc.Text(away.get("flag_emoji", "🏳️"), size="lg"),
            dmc.Text(status_text, c=status_color, className="ticker-time", ml="sm"),
        ],
        gap=8,
        wrap="nowrap",
        className="ticker-segment",
    )


def build_ticker(matches: list[dict]):
    live_count = len([match for match in matches if match.get("status") in {"IN_PLAY", "PAUSED"}])
    segments = []
    for index, match in enumerate(matches):
        segments.append(_ticker_segment(match))
        if index < len(matches) - 1:
            segments.append(dmc.Text("|", className="ticker-divider"))
    if not segments:
        segments.append(dmc.Text("No live or upcoming fixtures in the current ticker window", c="#7A8099", className="ticker-time"))

    return dmc.Group(
        [
            dmc.Badge("LIVE", color="green", variant="filled", className="mono-text") if live_count else dmc.Badge("UPCOMING", color="gray", variant="light"),
            dmc.ScrollArea(
                dmc.Group(segments, gap="md", wrap="nowrap", className="ticker-track"),
                offsetScrollbars=False,
                scrollbarSize=4,
                className="ticker-scroll",
                type="never",
                style={"flex": 1},
            ),
        ],
        gap="md",
        align="center",
        className="ticker-shell",
    )
