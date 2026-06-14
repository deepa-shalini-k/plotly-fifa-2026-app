from __future__ import annotations

from dash import Input, Output, callback, dcc, html, register_page
import dash_mantine_components as dmc
import plotly.graph_objects as go

from data.pitch_utils import GRAPH_CONFIG, get_base_layout
from data.predictions import GROUP_OPTIONS, GROUP_TEAMS, load_match_results

register_page(__name__, path="/predictions/group-ratings", name="Group Ratings")


def _format_signed(value: int | float) -> str:
    numeric = int(value)
    if numeric > 0:
        return f"+{numeric}"
    if numeric < 0:
        return str(numeric)
    return "0"


def _marker_size(value: int) -> int:
    return max(10, min(24, 10 + abs(int(value)) // 3))


def _arrow_inset(delta: int) -> float:
    magnitude = abs(int(delta))
    if magnitude == 0:
        return 0
    return min(8, max(2, magnitude * 0.2))


def _placeholder(group_value: str):
    return dmc.Center(
        dmc.Stack(
            [
                dmc.Text(f"Group {group_value} still has no captured results", className="section-title", ta="center"),
                dmc.Text(
                    "Once eloratings.net posts a result for one of these teams, the dumbbell chart will appear here automatically.",
                    c="#7A8099",
                    ta="center",
                    maw=520,
                ),
            ],
            gap="xs",
            align="center",
        ),
        className="empty-state",
        mih=520,
    )


def _team_badges(group_value: str):
    return dmc.Group(
        [dmc.Badge(team, variant="light", color="green") for team in GROUP_TEAMS[group_value]],
        gap="xs",
        wrap="wrap",
    )


def _dumbbell_chart(group_rows) -> go.Figure:
    frame = group_rows.copy()
    frame["elo_before"] = frame["new_elo"] - frame["elo_change"]
    frame["elo_after"] = frame["new_elo"]
    frame["label"] = frame.apply(
        lambda row: f"{row['team']} vs {row['opponent']} — {row['match_date'].strftime('%d %b')}",
        axis=1,
    )
    frame["trend_color"] = frame["elo_change"].apply(
        lambda value: "#00D084" if value > 0 else "#FF4757" if value < 0 else "#7A8099"
    )
    frame["dot_size"] = frame["elo_change"].apply(_marker_size)
    frame = frame.sort_values(["match_date", "team", "opponent"], ascending=[False, True, True]).reset_index(drop=True)
    frame["row_position"] = list(range(len(frame)))

    figure = go.Figure()
    for row in frame.itertuples(index=False):
        figure.add_trace(
            go.Scatter(
                x=[row.elo_before, row.elo_after],
                y=[row.row_position, row.row_position],
                mode="lines",
                line=dict(color=row.trend_color, width=3),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        if row.elo_change != 0:
            inset = _arrow_inset(row.elo_change)
            direction = 1 if row.elo_change > 0 else -1
            figure.add_annotation(
                x=row.elo_after - (direction * inset),
                y=row.row_position,
                ax=row.elo_before + (direction * inset),
                ay=row.row_position,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.5,
                arrowwidth=1.8,
                arrowside="end",
                arrowcolor="#F5F7FA",
                opacity=1,
            )

    hover_rows = [
        [
            row["team"],
            row["opponent"],
            f"{row['team_score']}-{row['opponent_score']}",
            row["elo_before"],
            row["elo_after"],
            _format_signed(row["elo_change"]),
            _format_signed(row["rank_change"]),
            row["tournament"],
        ]
        for _, row in frame.iterrows()
    ]

    figure.add_trace(
        go.Scatter(
            x=frame["elo_before"],
            y=frame["row_position"],
            mode="markers",
            marker=dict(size=frame["dot_size"], color="#7A8099", opacity=0.9),
            customdata=hover_rows,
            hovertemplate=(
                "<b>%{customdata[0]}</b> vs %{customdata[1]}<br>"
                "Score: %{customdata[2]}<br>"
                "Tournament: %{customdata[7]}<br>"
                "Elo before: %{customdata[3]}<br>"
                "Elo after: %{customdata[4]}<br>"
                "Elo swing: %{customdata[5]}<br>"
                "Rank change: %{customdata[6]}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=frame["elo_after"],
            y=frame["row_position"],
            mode="markers",
            marker=dict(size=frame["dot_size"], color=frame["trend_color"]),
            customdata=hover_rows,
            hovertemplate=(
                "<b>%{customdata[0]}</b> vs %{customdata[1]}<br>"
                "Score: %{customdata[2]}<br>"
                "Tournament: %{customdata[7]}<br>"
                "Elo before: %{customdata[3]}<br>"
                "Elo after: %{customdata[4]}<br>"
                "Elo swing: %{customdata[5]}<br>"
                "Rank change: %{customdata[6]}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    figure.update_layout(
        get_base_layout(
            height=max(420, 68 * len(frame) + 120),
            margin=dict(t=24, b=24, l=24, r=24),
        )
    )
    figure.update_xaxes(title="Elo rating")
    figure.update_yaxes(
        tickmode="array",
        tickvals=frame["row_position"],
        ticktext=frame["label"],
        autorange="reversed",
        showgrid=False,
    )
    return figure


def layout(**_kwargs):
    default_group = GROUP_OPTIONS[0]["value"]
    return dmc.Stack(
        [
            dcc.Interval(id="group-ratings-refresh-interval", interval=900_000, n_intervals=0),
            dmc.Stack(
                [
                    dmc.Stack(
                        [
                            dmc.Text("Group Ratings", className="page-title"),
                            dmc.Text(
                                "Elo is a rating system wherein unlike simple win/loss records, it accounts for the strength of the opponent — beating a top-ranked team earns far more points than beating a weaker one. It also considers match history going back decades, so a team's rating reflects long-term form, not just recent results. Every match updates both teams' ratings — the winner gains what the loser loses.",
                                c="#7A8099",
                                size="xl",
                            ),
                        ],
                        gap=4,
                        w="100%",
                    ),
                    dmc.Group(
                        [
                            dmc.Select(
                                id="group-ratings-group-select",
                                value=default_group,
                                data=GROUP_OPTIONS,
                                w=180,
                                allowDeselect=False,
                            ),
                        ],
                        justify="end",
                    ),
                ],
                gap="sm",
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Box(
                                    dmc.Stack(
                                        [
                                            dmc.Text("GROUP FILTER", className="section-label", size="1rem"),
                                            dmc.Text(
                                                "Each row shows how a team's Elo rating changed after a match — the first team named in the row is the one being tracked. The grey dot marks their rating before the match, and the coloured dot shows their rating after. Follow the arrowhead to see the direction of change — a green dot means their rating increased, a red dot means it dropped. Select a group to see all four teams' Elo swings across their matches. ",
                                                c="#7A8099",
                                            ),
                                        ],
                                        gap="md",
                                    ),
                                    style={"flex": "1 1 0", "minWidth": 0},
                                ),
                                dmc.Box(id="group-ratings-meta", style={"flexShrink": 0, "marginLeft": "auto"}),
                            ],
                            justify="space-between",
                            align="start",
                            wrap="nowrap",
                        ),
                        html.Div(id="group-ratings-chart-region"),
                    ],
                    gap="md",
                )
            ),
        ],
        gap="md",
    )


@callback(
    Output("group-ratings-chart-region", "children"),
    Output("group-ratings-meta", "children"),
    Input("group-ratings-group-select", "value"),
    Input("group-ratings-refresh-interval", "n_intervals"),
)
def render_group_ratings(group_value: str, _: int):
    group_value = group_value or GROUP_OPTIONS[0]["value"]
    results = load_match_results()
    group_rows = results[results["group"] == group_value].copy() if not results.empty else results

    meta = dmc.Stack(
        [
            dmc.Badge(f"Group {group_value}", variant="light", color="green"),
            _team_badges(group_value),
        ],
        gap="xs",
    )
    if group_rows.empty:
        return _placeholder(group_value), meta

    chart = dcc.Graph(
        figure=_dumbbell_chart(group_rows),
        config=GRAPH_CONFIG,
        style={"height": f"{max(420, 68 * len(group_rows) + 120)}px"},
    )
    return chart, meta
