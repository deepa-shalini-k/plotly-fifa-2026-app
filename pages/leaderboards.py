from __future__ import annotations

from functools import lru_cache

from dash import Input, Output, callback, dcc, no_update, register_page
import dash_mantine_components as dmc
import plotly.graph_objects as go

from components.player_card import build_avatar
from data import api, player_photos
from data.pitch_utils import GRAPH_CONFIG, get_base_layout

register_page(__name__, path="/leaderboards", name="Leaderboards")

METRICS = ["Goals", "Assists", "Goal Involvements", "Yellow Cards", "Red Cards", "Clean Sheets"]
LEADERBOARD_HEIGHT = 640
LEADERBOARD_MARGIN_TOP = 20
LEADERBOARD_MARGIN_BOTTOM = 20
LEADERBOARD_MARGIN_RIGHT = 50
LEADERBOARD_MARGIN_LEFT = 20
LEADERBOARD_LABEL_PADDING = 20
LEADERBOARD_CHAR_WIDTH = 7
LEADERBOARD_TICK_SUFFIX = "\u00A0\u00A0"
LEADERBOARD_TICK_SUFFIX_WIDTH = 12
APP_BACKGROUND_COLOR = "#0D0F14"


def _bar_color(metric: str, index: int) -> str:
    if metric == "Red Cards":
        return "#FF4757"
    if index == 0:
        return "#FFD700"
    return "#00D084"


@lru_cache(maxsize=1)
def _leaderboard_left_margin() -> int:
    # Plotly auto-expands the left gutter for long y-axis labels, so we reserve
    # one shared width across every leaderboard metric.
    longest_name_length = 0
    for leaderboard_metric in METRICS:
        rows = api.get_leaderboard(leaderboard_metric)[:15]
        for row in rows:
            longest_name_length = max(longest_name_length, len(row.get("name", "")))

    if not longest_name_length:
        return LEADERBOARD_MARGIN_LEFT

    return max(
        LEADERBOARD_MARGIN_LEFT,
        longest_name_length * LEADERBOARD_CHAR_WIDTH
        + LEADERBOARD_LABEL_PADDING
        + LEADERBOARD_TICK_SUFFIX_WIDTH,
    )


def _leaderboard_margin() -> dict:
    return dict(
        t=LEADERBOARD_MARGIN_TOP,
        b=LEADERBOARD_MARGIN_BOTTOM,
        l=_leaderboard_left_margin(),
        r=LEADERBOARD_MARGIN_RIGHT,
    )


def _empty_leaderboard_figure(message: str | None = None) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        get_base_layout(
            height=LEADERBOARD_HEIGHT,
            margin=_leaderboard_margin(),
            paper_bgcolor=APP_BACKGROUND_COLOR,
            plot_bgcolor=APP_BACKGROUND_COLOR,
        )
    )
    if message:
        fig.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(color="#7A8099", size=18),
        )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _leaderboard_figure(metric: str) -> go.Figure:
    rows = api.get_leaderboard(metric)[:15]
    if not rows:
        return _empty_leaderboard_figure(f"No {metric.lower()} data available yet")

    labels = [f"{row['flag_emoji']} {row['name']}" for row in rows]
    values = [row["value"] for row in rows]
    colors = [_bar_color(metric, index) for index, _ in enumerate(rows)]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=colors),
            text=values,
            textposition="outside",
            customdata=[[row["kind"], row["id"]] for row in rows],
            hovertemplate="%{y}: %{x}<extra></extra>",
        )
    )
    fig.update_layout(
        get_base_layout(
            height=LEADERBOARD_HEIGHT,
            yaxis=dict(
                autorange="reversed",
                tickfont=dict(color="#E8EAF0"),
                ticksuffix=LEADERBOARD_TICK_SUFFIX,
                showticksuffix="all",
                automargin=False,
            ),
            xaxis=dict(gridcolor="#2A2F42", rangemode="tozero"),
            transition={"duration": 600},
            margin=_leaderboard_margin(),
        )
    )
    return fig


def _podium_cards(metric: str):
    podium = api.get_leaderboard(metric)[:3]
    if not podium:
        return dmc.Center(
            dmc.Text(f"No {metric.lower()} data available yet", c="#7A8099", ta="center"),
            h=280,
        )
    accents = ["#FFD700", "#C0C0C0", "#CD7F32"]
    cards = []
    for index, row in enumerate(podium, start=1):
        photo_url = player_photos.get_player_photo_url(row["id"]) if row["kind"] == "player" else None
        cards.append(
            dmc.Paper(
                dmc.Group(
                    [
                        build_avatar(row["name"], photo_url, size=72),
                        dmc.Stack(
                            [
                                dmc.Text(f"#{index} · {row['name']}", fw=700),
                                dmc.Text(f"{row['flag_emoji']} {row['team_name']}", c="#7A8099"),
                            ],
                            gap=2,
                            style={"flex": 1},
                        ),
                        dmc.Text(str(row["value"]), className="display-number", c=accents[index - 1], size="3rem"),
                    ],
                    gap="md",
                    align="center",
                ),
                className="podium-card",
                style={"color": accents[index - 1]},
            )
        )
    return dmc.Stack(cards, gap="md")


def layout(**_kwargs):
    return dmc.Stack(
        [
            dcc.Location(id="leaderboard-nav"),
            dcc.Interval(id="leaderboard-refresh-interval", interval=300_000, n_intervals=0),
            dmc.Group(
                [
                    dmc.Text("Leaderboards", className="page-title"),
                    dmc.SegmentedControl(
                        id="leaderboard-metric",
                        value=METRICS[0],
                        data=METRICS,
                        color="green",
                        radius="xl",
                    ),
                ],
                justify="space-between",
                align="center",
                wrap="wrap",
            ),
            dmc.Grid(
                [
                    dmc.GridCol(
                        dmc.Paper(
                            dcc.Graph(
                                id="leaderboard-chart",
                                figure=_empty_leaderboard_figure(),
                                config=GRAPH_CONFIG,
                                style={"height": f"{LEADERBOARD_HEIGHT}px"},
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 8},
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("TOP 3 PODIUM", className="section-label", size="1rem"),
                                    dmc.Box(id="leaderboard-podium"),
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
    Output("leaderboard-chart", "figure"),
    Output("leaderboard-podium", "children"),
    Input("leaderboard-metric", "value"),
    Input("leaderboard-refresh-interval", "n_intervals"),
)
def render_leaderboard(metric: str, _: int):
    return _leaderboard_figure(metric), _podium_cards(metric)


@callback(
    Output("leaderboard-nav", "pathname"),
    Output("leaderboard-nav", "search"),
    Input("leaderboard-chart", "clickData"),
    prevent_initial_call=True,
)
def navigate_from_leaderboard(click_data: dict | None):
    if not click_data:
        return no_update, no_update
    kind, item_id = click_data["points"][0]["customdata"]
    if kind == "player":
        return "/players", f"?player={item_id}"
    return "/teams", f"?team={item_id}"
