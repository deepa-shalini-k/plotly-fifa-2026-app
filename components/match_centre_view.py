from __future__ import annotations

from dash import dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from components.match_formatting import live_minute_label
from components.pitch import draw_pitch
from data.pitch_utils import GRAPH_CONFIG


def _lineup_empty_text(match: dict) -> str:
    status = match.get("status")
    if status in {"IN_PLAY", "PAUSED"}:
        return "Starting XIs are not available from the live data provider yet"
    if status == "TIMED":
        return "Starting lineups have not been published in the match feed yet"
    return "Starting lineups were not available for this match feed"


def _match_status_badge(match: dict):
    status = match.get("status")
    if status in {"IN_PLAY", "PAUSED"}:
        minute_label = live_minute_label(match)
        return dmc.Group(
            [dmc.Badge("LIVE", color="green", variant="filled")]
            + (
                [dmc.Badge(minute_label, color="green", variant="light", className="mono-text")]
                if minute_label
                else []
            ),
            gap="sm",
        )
    return dmc.Badge("FT", color="gray", variant="filled")


def _event_icon(card: str | None = None, goal: bool = False, substitution: bool = False):
    if goal:
        return DashIconify(icon="tabler:ball-football", width=18)
    if substitution:
        return DashIconify(icon="tabler:replace", width=18)
    if card == "YELLOW":
        return DashIconify(icon="tabler:square-filled", width=16, color="#FFD700")
    if card == "RED":
        return DashIconify(icon="tabler:square-filled", width=16, color="#FF4757")
    return DashIconify(icon="tabler:point-filled", width=12)


def _event_bullet(color: str, card: str | None = None, goal: bool = False, substitution: bool = False):
    return dmc.ThemeIcon(
        _event_icon(card=card, goal=goal, substitution=substitution),
        color=color,
        variant="light",
        radius="xl",
        size=26,
    )


def _timeline_items(match: dict):
    items = []
    for goal in match.get("goals", []):
        assist = goal.get("assist")
        assist_text = f" · Assist: {assist['name']}" if assist else ""
        score = goal.get("score", {})
        items.append(
            {
                "minute": goal["minute"],
                "title": goal["scorer"]["name"],
                "description": f"{goal['team']['name']} {score.get('home', 0)}-{score.get('away', 0)}{assist_text}",
                "bullet": _event_bullet("green", goal=True),
            }
        )
    for booking in match.get("bookings", []):
        booking_color = "yellow" if booking["card"] == "YELLOW" else "red"
        items.append(
            {
                "minute": booking["minute"],
                "title": booking["player"]["name"],
                "description": f"{booking['team']['name']} {booking['card'].title()} card",
                "bullet": _event_bullet(booking_color, card=booking["card"]),
            }
        )
    for substitution in match.get("substitutions", []):
        items.append(
            {
                "minute": substitution["minute"],
                "title": f"{substitution['playerOut']['name']} → {substitution['playerIn']['name']}",
                "description": f"{substitution['team']['name']} substitution",
                "bullet": _event_bullet("blue", substitution=True),
            }
        )
    items.sort(key=lambda item: item["minute"])
    components = []
    for event in items:
        components.append(
            dmc.TimelineItem(
                title=dmc.Group(
                    [
                        dmc.Text(f"{event['minute']}'", c="#7A8099", className="mono-text", w=34),
                        dmc.Text(event["title"], fw=500),
                    ],
                    gap="md",
                    align="flex-start",
                ),
                bullet=event["bullet"],
                children=dmc.Text(event["description"], c="#7A8099", ml=48),
            )
        )
    if match.get("status") in {"IN_PLAY", "PAUSED"}:
        minute_label = live_minute_label(match)
        components.append(
            dmc.TimelineItem(
                title=dmc.Text(
                    f"{minute_label} — Live" if minute_label else "Live Now",
                    c="#00D084",
                    className="mono-text",
                ),
                bullet=dmc.ThemeIcon(
                    DashIconify(icon="tabler:point-filled", width=10),
                    color="green",
                    radius="xl",
                    size=26,
                    variant="light",
                ),
                children=dmc.Text("Match is currently in progress", c="#7A8099"),
            )
        )
    return dmc.Timeline(components, active=len(components), bulletSize=24, lineWidth=2)


def _match_header(match: dict):
    home = match["homeTeam"]
    away = match["awayTeam"]
    score = match.get("score", {}).get("fullTime", {})
    live_color = "#00D084" if match.get("status") in {"IN_PLAY", "PAUSED"} else "#E8EAF0"
    return dmc.Paper(
        dmc.Group(
            [
                dmc.Group(
                    [
                        dmc.Text(home.get("flag_emoji", "🏳️"), size="2rem"),
                        dmc.Stack(
                            [
                                dmc.Text(home["name"], className="section-title"),
                                dmc.Text(home.get("formation", "TBD"), c="#7A8099", className="mono-text"),
                            ],
                            gap=0,
                        ),
                    ],
                    gap="md",
                ),
                dmc.Paper(
                    dmc.Text(f"{score.get('home', 0)} - {score.get('away', 0)}", className="score-pill-value", c=live_color),
                    className="score-box",
                    px="xl",
                    py="sm",
                    radius="lg",
                    withBorder=True,
                ),
                dmc.Group(
                    [
                        dmc.Stack(
                            [
                                dmc.Text(away["name"], className="section-title", ta="right"),
                                dmc.Text(away.get("formation", "TBD"), c="#7A8099", className="mono-text", ta="right"),
                            ],
                            gap=0,
                        ),
                        dmc.Text(away.get("flag_emoji", "🏳️"), size="2rem"),
                    ],
                    gap="md",
                ),
                dmc.Stack(
                    [
                        _match_status_badge(match),
                        dmc.Text(f"{match.get('group', '').replace('_', ' ')} · {match.get('venue', 'Venue TBC')}", c="#7A8099"),
                    ],
                    gap="xs",
                    align="flex-end",
                ),
            ],
            justify="space-between",
            align="center",
            wrap="wrap",
        )
    )


def render_match_centre(match: dict):
    pitch_figure = draw_pitch(
        home_formation=match["homeTeam"].get("formation"),
        away_formation=match["awayTeam"].get("formation"),
        home_lineup=match["homeTeam"].get("lineup"),
        away_lineup=match["awayTeam"].get("lineup"),
        height=700,
        empty_state_text=_lineup_empty_text(match),
        marker_size=28,
        shirt_number_size=13,
        player_name_font_size=11,
        player_name_offset=3.8,
        formation_font_size=24,
        layout_margin=dict(t=0, b=0, l=0, r=0),
        x_range=(-0.5, 105.5),
        y_range=(-1.5, 69.0),
    )
    formation_panel = dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("FORMATION", className="section-label", size="1rem"),
                dcc.Graph(figure=pitch_figure, config=GRAPH_CONFIG, style={"height": "700px"}),
            ],
            gap="sm",
        ),
        h="100%",
    )

    return dmc.Stack(
        [
            _match_header(match),
            dmc.Grid(
                [
                    dmc.GridCol(formation_panel, span={"base": 12, "xl": 8}),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("EVENTS TIMELINE", className="section-label", size="1rem"),
                                    _timeline_items(match),
                                ],
                                gap="md",
                            )
                        ),
                        span={"base": 12, "xl": 4},
                    ),
                ],
                gutter="md",
            ),
        ],
        gap="md",
    )
