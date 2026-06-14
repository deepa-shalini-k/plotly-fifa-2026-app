from __future__ import annotations

from dash import Input, Output, callback, dcc, register_page
import dash_mantine_components as dmc

from components.loading import build_loading_block
from components.local_time import render_local_time
from components.match_formatting import live_minute_label
from components.pitch import draw_pitch
from data import api
from data.pitch_utils import GRAPH_CONFIG

register_page(__name__, path="/", name="Tournament Hub")


def _kpi_card(label: str, value: str, subtitle: str, color: str):
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(label, className="section-label", size="0.78rem"),
                dmc.Text(value, className="display-number", c=color),
                dmc.Text(subtitle, c="#7A8099"),
            ],
            gap=6,
            justify="space-between",
            h="100%",
        ),
        style={"borderLeft": f"3px solid {color}", "minHeight": "188px"},
    )


def _status_badge(match: dict):
    status = match.get("status")
    if status in {"IN_PLAY", "PAUSED"}:
        return dmc.Badge("LIVE", color="green", variant="light", className="status-live")
    if status == "FINISHED":
        return dmc.Badge("FT", color="gray", variant="light", className="status-finished")
    return dmc.Badge("UP NEXT", color="blue", variant="light", className="status-upcoming")


def _score_text(match: dict) -> tuple[str, str]:
    score = match.get("score", {}).get("fullTime", {})
    home = score.get("home")
    away = score.get("away")
    status = match.get("status")
    if home is None or away is None:
        if status in api.UPCOMING_STATUSES:
            return "vs", "#7A8099"
        return "–  –", "#7A8099"
    if status in {"IN_PLAY", "PAUSED"}:
        return f"{home} - {away}", "#00D084"
    if status == "FINISHED":
        return f"{home} - {away}", "#E8EAF0"
    return f"{home} - {away}", "#7A8099"


def _match_time(match: dict) -> tuple[object, str]:
    if match.get("status") in {"IN_PLAY", "PAUSED"}:
        return live_minute_label(match) or "LIVE", "#00D084"
    if match.get("status") == "FINISHED":
        return "FT", "#A3A8BC"
    kickoff = match.get("utcDate", "")
    if not kickoff:
        return "TBD", "#7A8099"
    return render_local_time(kickoff), "#7A8099"


def _match_row(match: dict):
    home = match["homeTeam"]
    away = match["awayTeam"]
    venue = match.get("venue", "Venue TBC")
    score_text, score_color = _score_text(match)
    time_text, time_color = _match_time(match)
    return dcc.Link(
        dmc.Paper(
            dmc.Group(
                [
                    dmc.Group(
                        [
                            dmc.Text(home.get("flag_emoji", "🏳️"), size="lg"),
                            dmc.Text(home.get("name", "Home"), fw=500),
                            dmc.Text(score_text.upper(), className="score-mono", c=score_color, size="lg", fw=700),
                            dmc.Text(away.get("flag_emoji", "🏳️"), size="lg"),
                            dmc.Text(away.get("name", "Away"), fw=500),
                        ],
                        gap="md",
                        wrap="wrap",
                        style={"flex": 1, "minWidth": 0},
                    ),
                    dmc.Group(
                        [
                            _status_badge(match),
                            dmc.Text(time_text, className="mono-text", c=time_color),
                            dmc.Text(venue, c="#7A8099", size="sm"),
                        ],
                        gap="sm",
                        wrap="wrap",
                        style={"marginLeft": "auto"},
                    ),
                ],
                justify="space-between",
                align="center",
                wrap="wrap",
            ),
            p="md",
            radius="md",
            className="match-row",
        ),
        href=f"/match/{match['id']}",
    )


def _position_color(position: int) -> str:
    if position <= 2:
        return "#00D084"
    if position == 3:
        return "#FFD700"
    return "#FF4757"


def _form_badges(form_value: str | list[str] | tuple[str, ...] | None):
    mapping = {"W": "green", "D": "yellow", "L": "red"}
    if isinstance(form_value, str):
        results = [result.strip() for result in form_value.split(",") if result.strip()]
    elif isinstance(form_value, (list, tuple)):
        results = [str(result).strip() for result in form_value if str(result).strip()]
    else:
        results = []

    if not results:
        return dmc.Text("—", c="#7A8099", size="sm")

    return dmc.Group(
        [dmc.Badge(result, color=mapping.get(result, "gray"), variant="filled") for result in results],
        gap=4,
    )


def _standings_table(group_name: str):
    group = api.get_group_table(group_name)
    if not group or not group.get("table"):
        return build_loading_block(height=240)
    head = dmc.TableThead(
        dmc.TableTr(
            [
                dmc.TableTh(""),
                dmc.TableTh("Team"),
                dmc.TableTh("P"),
                dmc.TableTh("W"),
                dmc.TableTh("D"),
                dmc.TableTh("L"),
                dmc.TableTh("GD"),
                dmc.TableTh("Pts"),
            ]
        )
    )
    rows = []
    for team_row in group["table"]:
        team = team_row["team"]
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.ThemeIcon(radius="xl", color=_position_color(team_row["position"]), size=10, variant="filled")),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Text(team.get("flag_emoji", "🏳️")),
                                dmc.Text(team.get("name", ""), fw=500),
                            ],
                            gap="sm",
                        )
                    ),
                    dmc.TableTd(team_row["playedGames"]),
                    dmc.TableTd(team_row["won"]),
                    dmc.TableTd(team_row["draw"]),
                    dmc.TableTd(team_row["lost"]),
                    dmc.TableTd(team_row["goalDifference"]),
                    dmc.TableTd(dmc.Text(str(team_row["points"]), c="#00D084" if team_row["position"] <= 2 else "#E8EAF0", fw=700)),
                ]
            )
        )
    legend = dmc.Group(
        [
            dmc.Group([dmc.ThemeIcon(color="green", size=10, radius="xl"), dmc.Text("Qualify", c="#7A8099")], gap=6),
            dmc.Group([dmc.ThemeIcon(color="yellow", size=10, radius="xl"), dmc.Text("Play-off", c="#7A8099")], gap=6),
            dmc.Group([dmc.ThemeIcon(color="red", size=10, radius="xl"), dmc.Text("Eliminated", c="#7A8099")], gap=6),
        ],
        gap="lg",
        mt="sm",
    )
    return dmc.Stack(
        [
            dmc.TableScrollContainer(
                dmc.Table(
                    [head, dmc.TableTbody(rows)],
                    className="tournament-hub-standings-table",
                    striped=False,
                    highlightOnHover=True,
                    withTableBorder=False,
                ),
                minWidth=520,
            ),
            legend,
        ],
        gap="sm",
    )


def _top_scorers():
    scorers = api.get_scorers(limit=5)
    if not scorers:
        return build_loading_block(height=220)
    rows = []
    for index, scorer in enumerate(scorers, start=1):
        rows.append(
            dmc.Group(
                [
                    dmc.Text(str(index), className="mono-text", c="#7A8099", w=16),
                    dmc.Text(scorer["player"]["name"], fw=500, style={"flex": 1}),
                    dmc.Text(scorer["team"].get("flag_emoji", "🏳️")),
                    dmc.Text(str(scorer["goals"]), className="display-number", c="#FFD700", size="2rem"),
                ],
                justify="space-between",
                align="center",
                py="xs",
                style={"borderBottom": "1px solid rgba(42, 47, 66, 0.7)"} if index < len(scorers) else None,
            )
        )
    return dmc.Stack(rows, gap="xs")


def _live_match_widget():
    payload = api.get_live_hub_payload()
    source_match = payload.get("featured_match")
    if not source_match:
        cards = []
        if payload.get("next_match"):
            next_match = payload["next_match"]
            cards.append(
                dmc.Paper(
                    dmc.Stack(
                        [
                            dmc.Badge("NEXT KICKOFF", color="blue", variant="light"),
                            dmc.Text(
                                f"{next_match['homeTeam'].get('flag_emoji', '🏳️')} {next_match['homeTeam']['name']} vs {next_match['awayTeam']['name']} {next_match['awayTeam'].get('flag_emoji', '🏳️')}",
                                fw=600,
                            ),
                            dmc.Text(
                                render_local_time(
                                    next_match.get("utcDate"),
                                    format_style="datetime",
                                    fallback="Kickoff TBC",
                                ),
                                c="#7A8099",
                            ),
                        ],
                        gap=6,
                    ),
                    className="stats-mini-cell",
                )
            )
        if payload.get("recent_result"):
            result = payload["recent_result"]
            score = result.get("score", {}).get("fullTime", {})
            cards.append(
                dmc.Paper(
                    dmc.Stack(
                        [
                            dmc.Badge("LATEST RESULT", color="gray", variant="light"),
                            dmc.Text(
                                f"{result['homeTeam'].get('flag_emoji', '🏳️')} {result['homeTeam']['name']} {score.get('home', 0)} - {score.get('away', 0)} {result['awayTeam']['name']} {result['awayTeam'].get('flag_emoji', '🏳️')}",
                                fw=600,
                            ),
                            dmc.Text(result.get("venue", "Venue TBC"), c="#7A8099"),
                        ],
                        gap=6,
                    ),
                    className="stats-mini-cell",
                )
            )

        if cards:
            cards.append(
                dcc.Link(
                    dmc.Button("Open Match Centre", color="green", variant="light"),
                    href="/live",
                    style={"textDecoration": "none"},
                )
            )
            return dmc.Stack(cards, gap="sm")

        if payload.get("state") == "data_unavailable":
            return build_loading_block(height=220)

        return dmc.Alert("No live matches right now", color="gray", variant="light")

    home = source_match["homeTeam"]
    away = source_match["awayTeam"]
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Badge("LIVE", color="green", variant="filled"),
                    dmc.Text(f"{home.get('flag_emoji', '🏳️')} {home['name']}", fw=500),
                    dmc.Text(_score_text(source_match)[0], className="score-mono", c="#00D084" if source_match.get("status") in {"IN_PLAY", "PAUSED"} else "#E8EAF0", fw=700),
                    dmc.Text(f"{away['name']} {away.get('flag_emoji', '🏳️')}", fw=500),
                ],
                justify="space-between",
                wrap="wrap",
            ),
            dcc.Link(
                dmc.Button("Open Match Centre", color="green", variant="light"),
                href="/live",
                style={"textDecoration": "none"},
            ),
        ],
        gap="md",
    )


def _formation_preview():
    payload = api.get_live_hub_payload()
    if payload.get("state") == "data_unavailable":
        return build_loading_block(height=300)
    match = payload.get("featured_match")
    if not match:
        return dmc.Alert("Formation preview appears here once a real live lineup is available", color="gray", variant="light")
    empty_state_text = (
        "Starting XIs are not available from the live data provider yet"
        if match.get("status") in api.LIVE_STATUSES
        else "Formation preview appears here once lineups are available in the match feed"
    )
    figure = draw_pitch(
        home_formation=match["homeTeam"].get("formation"),
        away_formation=match["awayTeam"].get("formation"),
        home_lineup=match["homeTeam"].get("lineup"),
        away_lineup=match["awayTeam"].get("lineup"),
        height=310,
        empty_state_text=empty_state_text,
    )
    return dcc.Graph(figure=figure, config=GRAPH_CONFIG, style={"height": "300px"})


def _hub_subtitle() -> str:
    matchday = api.get_current_group_stage_matchday()
    if matchday is None:
        return "Group Stage"
    return f"Group Stage · Matchday {matchday}"


def layout(**_kwargs):
    group_options = api.get_group_options()
    default_group = group_options[0]["value"] if group_options else None
    subtitle = _hub_subtitle()
    return dmc.Stack(
        [
            dcc.Interval(id="hub-interval", interval=60_000, n_intervals=0),
            dmc.Group(
                [
                    dmc.Group(
                        [
                            dmc.Text("Tournament Hub", className="page-title"),
                            dmc.Text(subtitle, id="hub-stage-label", c="#7A8099", size="xl"),
                        ],
                        gap="md",
                        align="end",
                    ),
                ],
                justify="space-between",
                align="end",
            ),
            dmc.Grid(id="hub-kpis", gutter="md"),
            dmc.Grid(
                [
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("UPCOMING MATCHES", className="section-label", size="1rem"),
                                    dmc.Stack(id="hub-matches", gap="sm"),
                                ],
                                gap="md",
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 7},
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Group(
                                        [
                                            dmc.Text("GROUP STANDINGS", className="section-label", size="1rem"),
                                            dmc.Select(
                                                id="hub-group-select",
                                                value=default_group,
                                                data=group_options,
                                                searchable=True,
                                                w=170,
                                            ),
                                        ],
                                        justify="space-between",
                                        align="center",
                                    ),
                                    dmc.Box(id="hub-standings"),
                                ],
                                gap="md",
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 5},
                    ),
                ],
                gutter="md",
            ),
            dmc.Grid(
                [
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("TOP SCORERS", className="section-label", size="1rem"),
                                    dmc.Box(id="hub-scorers"),
                                ],
                                gap="md",
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 4},
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("LIVE MATCH SNAPSHOT", className="section-label", size="1rem"),
                                    dmc.Box(id="hub-live-widget"),
                                ],
                                gap="md",
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 4},
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("FORMATION PREVIEW", className="section-label", size="1rem"),
                                    dmc.Box(id="hub-formation-preview"),
                                ],
                                gap="md",
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 4},
                    ),
                ],
                gutter="md",
            ),
        ],
        gap="md",
    )


@callback(
    Output("hub-stage-label", "children"),
    Output("hub-kpis", "children"),
    Output("hub-matches", "children"),
    Output("hub-standings", "children"),
    Output("hub-scorers", "children"),
    Output("hub-live-widget", "children"),
    Output("hub-formation-preview", "children"),
    Input("hub-interval", "n_intervals"),
    Input("hub-group-select", "value"),
)
def refresh_hub(_: int, group_name: str):
    subtitle = _hub_subtitle()
    summary = api.get_tournament_summary()
    matches = api.get_upcoming_matches(limit=4)
    kpis = [
        dmc.GridCol(_kpi_card("Teams", str(summary["teams"]), "Qualified nations", "#00D084"), span={"base": 12, "sm": 6, "xl": 3}),
        dmc.GridCol(_kpi_card("Matches Played", str(summary["matches_played"]), f"of {summary['matches_total']} total", "#4E9CFF"), span={"base": 12, "sm": 6, "xl": 3}),
        dmc.GridCol(_kpi_card("Goals Scored", str(summary["goals_scored"]), f"{summary['goals_per_match']} per match", "#FFD700"), span={"base": 12, "sm": 6, "xl": 3}),
        dmc.GridCol(_kpi_card("Live Now", str(summary["live_now"]), "Matches in play", "#FF4757"), span={"base": 12, "sm": 6, "xl": 3}),
    ]
    match_rows = [_match_row(match) for match in matches] if matches else [dmc.Alert("No upcoming matches scheduled", color="gray", variant="light")]
    return subtitle, kpis, match_rows, _standings_table(group_name), _top_scorers(), _live_match_widget(), _formation_preview()
