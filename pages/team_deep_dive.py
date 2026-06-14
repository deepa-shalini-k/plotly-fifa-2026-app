from __future__ import annotations

from dash import Input, Output, State, callback, dcc, register_page
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import plotly.graph_objects as go

from components.loading import build_loading_block
from components.pitch import draw_pitch
from data import api
from data.pitch_utils import GRAPH_CONFIG, get_base_layout

register_page(__name__, path="/teams", name="Team Deep Dive")

MAP_ACTIVE_COLOR = "#00D084"
MAP_INACTIVE_COLOR = "#36537C"
MAP_OUTLINE_COLOR = "#11161F"
MAP_LAND_COLOR = "#0E131B"
MAP_HEIGHT = 460
MAP_LABEL_TARGETS = {
    1003: {"label": "ENG", "lat": 54.3, "lon": -2.5, "textposition": "top center"},
    1004: {"label": "JPN", "lat": 37.2, "lon": 138.3, "textposition": "middle right"},
    1016: {"label": "KOR", "lat": 36.3, "lon": 127.9, "textposition": "top left"},
    1022: {"label": "DEN", "lat": 56.0, "lon": 10.1, "textposition": "bottom left"},
    1043: {"label": "QAT", "lat": 25.2, "lon": 51.2, "textposition": "bottom left"},
    1044: {"label": "UAE", "lat": 24.3, "lon": 54.5, "textposition": "top right"},
    1045: {"label": "NZL", "lat": -41.2, "lon": 174.5, "textposition": "top left"},
    1046: {"label": "CRC", "lat": 9.8, "lon": -84.1, "textposition": "bottom left"},
    1047: {"label": "PAN", "lat": 8.7, "lon": -80.1, "textposition": "top right"},
    1048: {"label": "JAM", "lat": 18.1, "lon": -77.3, "textposition": "top center"},
}


def _coerce_selected_team_id(team_id: str | int | None) -> int | None:
    valid_ids = {entry["id"] for entry in api.get_team_map_entries()}
    fallback = api.get_default_team_deep_dive_id()
    if not valid_ids:
        return None

    candidate = team_id if team_id is not None else fallback
    if candidate is None:
        return fallback

    try:
        resolved = int(str(candidate))
    except (TypeError, ValueError):
        return fallback

    if valid_ids and resolved not in valid_ids:
        return fallback
    return resolved


def _team_map_figure(selected_team_id: int | None) -> go.Figure:
    entries = api.get_team_map_entries()
    figure = go.Figure()

    if not entries:
        figure.update_layout(get_base_layout(height=MAP_HEIGHT, margin=dict(t=0, r=0, b=0, l=0)))
        return figure

    figure.add_trace(
        go.Choropleth(
            locations=[entry["map_code"] for entry in entries],
            z=[1 if entry["id"] == selected_team_id else 0 for entry in entries],
            locationmode="ISO-3",
            colorscale=[
                [0.0, MAP_INACTIVE_COLOR],
                [0.499, MAP_INACTIVE_COLOR],
                [0.5, MAP_ACTIVE_COLOR],
                [1.0, MAP_ACTIVE_COLOR],
            ],
            zmin=0,
            zmax=1,
            showscale=False,
            marker=dict(line=dict(color=MAP_OUTLINE_COLOR, width=1.1)),
            customdata=[
                [str(entry["id"]), entry["name"], entry["flag_emoji"]]
                for entry in entries
            ],
            hovertemplate="%{customdata[2]} %{customdata[1]}<extra></extra>",
        )
    )

    label_entries = [entry for entry in entries if entry["id"] in MAP_LABEL_TARGETS]
    if label_entries:
        figure.add_trace(
            go.Scattergeo(
                lon=[MAP_LABEL_TARGETS[entry["id"]]["lon"] for entry in label_entries],
                lat=[MAP_LABEL_TARGETS[entry["id"]]["lat"] for entry in label_entries],
                text=[
                    f"<b>{MAP_LABEL_TARGETS[entry['id']]['label']}</b>"
                    for entry in label_entries
                ],
                mode="markers+text",
                marker=dict(
                    size=18,
                    color="rgba(0,0,0,0)",
                    line=dict(color="rgba(0,0,0,0)", width=0),
                ),
                textposition=[
                    MAP_LABEL_TARGETS[entry["id"]]["textposition"]
                    for entry in label_entries
                ],
                textfont=dict(
                    family="JetBrains Mono, monospace",
                    size=11,
                    color=[
                        MAP_ACTIVE_COLOR if entry["id"] == selected_team_id else "#C7D6FF"
                        for entry in label_entries
                    ],
                ),
                customdata=[
                    [str(entry["id"]), entry["name"], entry["flag_emoji"]]
                    for entry in label_entries
                ],
                hovertemplate="%{customdata[2]} %{customdata[1]}<extra></extra>",
                showlegend=False,
            )
        )

    figure.update_layout(
        get_base_layout(
            height=MAP_HEIGHT,
            margin=dict(t=0, r=0, b=0, l=0),
            clickmode="event+select",
        )
    )
    figure.update_geos(
        bgcolor="rgba(0,0,0,0)",
        projection_type="robinson",
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#30364C",
        coastlinewidth=0.6,
        showcountries=True,
        countrycolor="#30364C",
        countrywidth=1,
        showland=True,
        landcolor=MAP_LAND_COLOR,
        showocean=False,
        showlakes=False,
    )
    return figure


def _selected_team_badge(team_id: int | None):
    if team_id is None:
        return "Loading live team data"
    team = api.get_team(team_id)
    if not team:
        return "Loading live team data"
    return f"{team.get('flag_emoji', '🏳️')} {team['name']}"


def _timeline_figure(timeline: list[dict]) -> go.Figure:
    colors = {"W": "#00D084", "D": "#FFD700", "L": "#FF4757"}
    labels = [item["label"] for item in timeline]
    fig = go.Figure()

    if timeline:
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=[1] * len(timeline),
                mode="markers+text" if len(timeline) == 1 else "markers+lines+text",
                marker=dict(size=18, color=[colors[item["result"]] for item in timeline]),
                line=dict(color="#2A2F42", width=2),
                text=[item["result"] for item in timeline],
                textposition="top center",
                customdata=[[item["opponent"], item["score"]] for item in timeline],
                hovertemplate="Opponent: %{customdata[0]}<br>Score: %{customdata[1]}<extra></extra>",
                showlegend=False,
            )
        )
    else:
        fig.update_layout(
            get_base_layout(
                height=220,
                yaxis=dict(visible=False),
                xaxis=dict(showgrid=False),
                annotations=[
                    dict(
                        x=0.5,
                        y=0.5,
                        xref="paper",
                        yref="paper",
                        text="No FIFA World Cup 2026 matches played yet",
                        showarrow=False,
                        font=dict(color="#7A8099", size=15),
                    )
                ],
            )
        )
        return fig

    fig.update_layout(
        get_base_layout(
            height=220,
            yaxis=dict(visible=False),
            xaxis=dict(showgrid=False, categoryorder="array", categoryarray=labels),
        )
    )
    fig.update_yaxes(range=[0.96, 1.04], visible=False)
    return fig


def _goals_by_time_figure(brackets: dict) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=list(brackets.keys()),
            y=list(brackets.values()),
            marker=dict(color="#00D084"),
            hovertemplate="%{x}: %{y} goals<extra></extra>",
        )
    )
    fig.update_layout(get_base_layout(height=260))
    fig.update_yaxes(rangemode="tozero", tickmode="linear", tick0=0, dtick=1, tickformat="d")
    return fig


def _age_distribution_figure(age_buckets: dict) -> go.Figure:
    labels = ["U22", "22-25", "26-29", "30-33", "34+"]
    values = [age_buckets.get(label, 0) for label in labels]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            sort=False,
            direction="clockwise",
            rotation=90,
            marker=dict(colors=["#8DD3FF", "#4E9CFF", "#2D7DE0", "#6A5CFF", "#A78BFA"]),
            textinfo="label",
            textposition="outside",
            hovertemplate="%{label}: %{value} players<extra></extra>",
        )
    )
    fig.update_layout(get_base_layout(height=320, showlegend=False))
    return fig


def _world_cup_summary_card(analysis: dict):
    metrics = [
        ("Goals For", str(analysis["goals_for"]), "#00D084"),
        ("Goals Against", str(analysis["goals_against"]), "#FF4757"),
        ("Goal Difference", f"{analysis['goal_difference']:+d}", "#4E9CFF"),
    ]
    return dmc.Grid(
        [
            dmc.GridCol(
                dmc.Box(
                    dmc.Stack(
                        [
                            dmc.Text(label, c="#7A8099", size="sm", tt="uppercase"),
                            dmc.Text(value, size="2.3rem", fw=700, c=color),
                        ],
                        gap=2,
                    ),
                    style={
                        "height": "100%",
                        "padding": "1rem",
                        "borderRadius": "16px",
                        "background": "rgba(54,83,124,0.18)",
                        "border": "1px solid rgba(78,156,255,0.14)",
                    },
                ),
                span={"base": 12, "sm": 4},
            )
            for label, value, color in metrics
        ],
        gutter="sm",
    )


def _extract_lineup(match: dict, team_id: int):
    if not isinstance(match, dict):
        return None, []
    home_team = match.get("homeTeam") if isinstance(match.get("homeTeam"), dict) else {}
    away_team = match.get("awayTeam") if isinstance(match.get("awayTeam"), dict) else {}
    if home_team.get("id") == team_id:
        return home_team.get("formation"), home_team.get("lineup") or []
    if away_team.get("id") == team_id:
        return away_team.get("formation"), away_team.get("lineup") or []
    return None, []


def _team_website_href(team: dict) -> str | None:
    website = str(team.get("website") or "").strip()
    if not website:
        return None
    if website.startswith(("http://", "https://")):
        return website
    return f"https://{website}"


def _clean_team_metadata(value) -> str | None:
    if value is None:
        return None

    text = " ".join(str(value).strip().split())
    if not text:
        return None

    nullish_words = {"null", "none", "undefined", "n/a", "na", "unknown", "tbd"}
    cleaned_tokens = [
        token
        for token in text.split()
        if token.strip(" ,;/|-").casefold() not in nullish_words
    ]
    cleaned = " ".join(cleaned_tokens).strip(" ,;/|-")
    if not cleaned:
        return None

    if cleaned.casefold() in nullish_words:
        return None
    return cleaned


def _team_metadata_fragment(label: str, value) -> str | None:
    cleaned = _clean_team_metadata(value)
    return f"{label}: {cleaned}" if cleaned else None


def _team_info_card(analysis: dict):
    team = analysis["team"]
    coach = team.get("coach", {}) if isinstance(team.get("coach"), dict) else {}
    website_href = _team_website_href(team)
    coach_name = _clean_team_metadata(coach.get("name"))
    coach_nationality = _clean_team_metadata(coach.get("nationality"))

    coach_line = None
    if coach_name:
        coach_parts = [f"Coach: {coach_name}"]
        if coach_nationality:
            coach_parts.append(coach_nationality)
        coach_line = " · ".join(coach_parts)

    facts_line = " · ".join(
        fragment
        for fragment in [
            _team_metadata_fragment("Founded", team.get("founded")),
            _team_metadata_fragment("Address", team.get("address")),
        ]
        if fragment
    )

    return dmc.Stack(
        [item for item in [
            dmc.Group(
                [
                    dmc.Group(
                        [
                            dmc.Image(src=team.get("crest"), h=72, w=72, fit="contain"),
                            dmc.Stack(
                                [
                                    dmc.Text(team["name"], className="page-title", size="3rem"),
                                ],
                                gap=2,
                            ),
                        ],
                        gap="md",
                        style={"flex": 1, "minWidth": 0},
                    ),
                    dmc.Anchor(
                        dmc.ThemeIcon(
                            DashIconify(icon="tabler:world-www", width=18),
                            size=42,
                            radius="xl",
                            color="green",
                            variant="light",
                        ),
                        href=website_href,
                        target="_blank",
                        style={"display": "inline-flex"},
                    ) if website_href else dmc.Box(),
                ],
                justify="space-between",
                align="flex-start",
                wrap="nowrap",
            ),
            dmc.Text(coach_line, c="#7A8099") if coach_line else None,
            dmc.Text(facts_line, c="#7A8099") if facts_line else None,
            dmc.Group(
                [
                    dmc.Badge(f"Played {len(analysis['played_matches'])}", color="blue", variant="light"),
                    dmc.Badge(f"Wins {analysis['wins']}", color="green", variant="light"),
                    dmc.Badge(f"Goals For {analysis['goals_for']}", color="yellow", variant="light"),
                ],
                gap="sm",
            ),
        ] if item is not None],
        gap="md",
    )


def layout(team=None, **_kwargs):
    default_team_id = _coerce_selected_team_id(team)
    return dmc.Stack(
        [
            dcc.Store(id="team-deep-dive-selection", data=str(default_team_id) if default_team_id is not None else None),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Stack(
                                    [
                                        dmc.Text("Team Deep Dive", className="page-title"),
                                        dmc.Text("Select a highlighted country on the map to switch the team analysis.", c="#7A8099", size="lg"),
                                    ],
                                    gap=4,
                                ),
                                dmc.Badge(
                                    _selected_team_badge(default_team_id),
                                    id="team-deep-dive-selected-badge",
                                    color="green",
                                    variant="light",
                                    size="lg",
                                ),
                            ],
                            justify="space-between",
                            align="flex-start",
                            wrap="wrap",
                        ),
                        dcc.Graph(
                            id="team-deep-dive-map",
                            figure=_team_map_figure(default_team_id),
                            config=GRAPH_CONFIG,
                            style={"height": f"{MAP_HEIGHT}px"},
                        ),
                    ],
                    gap="md",
                )
            ),
            dmc.Grid(
                [
                    dmc.GridCol(dmc.Box(id="team-deep-dive-left"), span={"base": 12, "xl": 4}),
                    dmc.GridCol(dmc.Box(id="team-deep-dive-right"), span={"base": 12, "xl": 8}),
                ],
                gutter="md",
            ),
        ],
        gap="md",
    )


@callback(
    Output("team-deep-dive-selection", "data"),
    Input("team-deep-dive-map", "clickData"),
    State("team-deep-dive-selection", "data"),
    prevent_initial_call=True,
)
def select_team_from_map(click_data: dict | None, current_team_id: str):
    if not click_data or not click_data.get("points"):
        raise PreventUpdate

    selected_team_id = str(click_data["points"][0]["customdata"][0])
    if selected_team_id == str(current_team_id):
        raise PreventUpdate
    return selected_team_id


@callback(
    Output("team-deep-dive-map", "figure"),
    Output("team-deep-dive-selected-badge", "children"),
    Output("team-deep-dive-left", "children"),
    Output("team-deep-dive-right", "children"),
    Input("team-deep-dive-selection", "data"),
)
def render_team_deep_dive(team_id: str):
    selected_team_id = _coerce_selected_team_id(team_id)
    if selected_team_id is None:
        return (
            _team_map_figure(None),
            _selected_team_badge(None),
            build_loading_block(height=420),
            build_loading_block(height=520),
        )

    analysis = api.get_team_analysis(selected_team_id)
    if not analysis.get("team"):
        return (
            _team_map_figure(selected_team_id),
            _selected_team_badge(selected_team_id),
            build_loading_block(height=420),
            build_loading_block(height=520),
        )
    formation, lineup = _extract_lineup(analysis["latest_match"], selected_team_id)
    pitch = draw_pitch(
        home_formation=formation,
        home_lineup=lineup,
        away_lineup=None,
        height=350,
        empty_state_text="No FIFA World Cup 2026 lineup available yet",
    )
    left = dmc.Stack(
        [
            dmc.Paper(_team_info_card(analysis)),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("LATEST FORMATION", className="section-label", size="1rem"),
                        dcc.Graph(figure=pitch, config=GRAPH_CONFIG, style={"height": "350px"}),
                    ],
                    gap="md",
                )
            ),
        ],
        gap="md",
    )
    right = dmc.Grid(
        [
            dmc.GridCol(
                dmc.Stack(
                    [
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("GOAL SUMMARY", className="section-label", size="1rem"),
                                    _world_cup_summary_card(analysis),
                                ],
                                gap="md",
                            )
                        ),
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("SQUAD AGE DISTRIBUTION", className="section-label", size="1rem"),
                                    dcc.Graph(figure=_age_distribution_figure(analysis["age_buckets"]), config=GRAPH_CONFIG, style={"height": "414px"}),
                                ],
                                gap="md",
                            )
                        ),
                    ],
                    gap="md",
                ),
                span={"base": 12, "xl": 6},
            ),
            dmc.GridCol(
                dmc.Stack(
                    [
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("GOALS BY TIME BRACKET (MINS)", className="section-label", size="1rem"),
                                    dcc.Graph(figure=_goals_by_time_figure(analysis["goals_by_bracket"]), config=GRAPH_CONFIG, style={"height": "260px"}),
                                ],
                                gap="md",
                            )
                        ),
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("MATCH RESULTS TIMELINE", className="section-label", size="1rem"),
                                    dcc.Graph(figure=_timeline_figure(analysis["timeline"]), config=GRAPH_CONFIG, style={"height": "247px"}),
                                ],
                                gap="md",
                            )
                        ),
                    ],
                    gap="md",
                ),
                span={"base": 12, "xl": 6},
            ),
        ],
        gutter="md",
    )
    return _team_map_figure(selected_team_id), _selected_team_badge(selected_team_id), left, right
