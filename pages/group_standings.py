from __future__ import annotations

from dash import Input, Output, callback, dcc, register_page
import dash_mantine_components as dmc
import plotly.graph_objects as go

from components.loading import build_loading_block
from data import api
from data.pitch_utils import GRAPH_CONFIG, get_base_layout

register_page(__name__, path="/standings", name="Group Standings")


def _position_color(position: int) -> str:
    if position <= 2:
        return "#00D084"
    if position == 3:
        return "#FFD700"
    return "#FF4757"


def _ordinal(position: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(position, f"{position}th")


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


def _compact_group_card(group: dict):
    rows = []
    for team_row in group["table"]:
        rows.append(
            dmc.Group(
                [
                    dmc.Box(style={"width": 4, "height": 32, "background": _position_color(team_row["position"]), "borderRadius": 999}),
                    dmc.Text(team_row["team"].get("flag_emoji", "🏳️")),
                    dmc.Text(team_row["team"]["name"], style={"flex": 1}),
                    dmc.Text(str(team_row["playedGames"]), c="#7A8099", className="mono-text"),
                    dmc.Text(str(team_row["points"]), c="#00D084" if team_row["position"] <= 2 else "#E8EAF0", className="display-number", size="1.6rem"),
                ],
                gap="sm",
                align="center",
            )
        )
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(group["group"], className="section-title", size="2rem"),
                dmc.Stack(rows, gap="xs"),
            ],
            gap="md",
        ),
        h="100%",
    )


def _all_groups_overview_chart(standings: list[dict]) -> go.Figure:
    sorted_groups = sorted(standings, key=lambda item: item["group"])
    x_labels = ["1st", "2nd", "3rd", "4th"]
    y_labels = [group["group"].replace("GROUP ", "") for group in sorted_groups]
    z_values = []
    hover_rows = []
    annotations = []

    for group in sorted_groups:
        table = sorted(group["table"], key=lambda item: item["position"])
        heat_row = []
        hover_row = []
        group_label = group["group"].replace("GROUP ", "")

        for cell_index, team_row in enumerate(table[:4]):
            team = team_row["team"]
            points = int(team_row.get("points", 0) or 0)
            heat_row.append(min(points, 6))
            form_value = team_row.get("form")
            if isinstance(form_value, str):
                form_text = form_value.replace(",", " · ") or "No form yet"
            elif isinstance(form_value, (list, tuple)):
                form_text = " · ".join(str(result) for result in form_value if result) or "No form yet"
            else:
                form_text = "No form yet"

            hover_row.append(
                "<br>".join(
                    [
                        f"{group['group']} · {_ordinal(team_row['position'])} place",
                        f"{team.get('flag_emoji', '🏳️')} {team.get('name', 'Unknown')}",
                        f"{points} pts · GD {team_row.get('goalDifference', 0)}",
                        f"Form: {form_text}",
                    ]
                )
            )

            team_label = team.get("tla") or team.get("shortName", team.get("name", "TEAM"))[:3].upper()
            annotations.append(
                dict(
                    x=x_labels[cell_index],
                    y=group_label,
                    text=f"{team_label}<br>{points} pts",
                    showarrow=False,
                    font=dict(family="JetBrains Mono, monospace", size=12, color="#E8EAF0"),
                )
            )

        z_values.append(heat_row)
        hover_rows.append(hover_row)

    fig = go.Figure(
        go.Heatmap(
            z=z_values,
            x=x_labels,
            y=y_labels,
            zmin=0,
            zmax=6,
            colorscale=[
                [0.0, "#0D0F14"],
                [0.2, "#141720"],
                [0.45, "#1D4130"],
                [0.75, "#009F67"],
                [1.0, "#00D084"],
            ],
            xgap=10,
            ygap=10,
            showscale=False,
            customdata=hover_rows,
            hovertemplate="%{customdata}<extra></extra>",
        )
    )
    fig.update_layout(
        get_base_layout(
            height=620,
            margin=dict(t=16, b=16, l=16, r=16),
            annotations=annotations,
        )
    )
    fig.update_xaxes(
        side="top",
        showgrid=False,
        tickfont=dict(family="Barlow Condensed, sans-serif", size=20, color="#E8EAF0"),
        fixedrange=True,
    )
    fig.update_yaxes(
        autorange="reversed",
        showgrid=False,
        tickfont=dict(family="Barlow Condensed, sans-serif", size=18, color="#E8EAF0"),
        fixedrange=True,
    )
    return fig


def _detail_table(group_name: str):
    group = api.get_group_table(group_name)
    if not group or not group.get("table"):
        return build_loading_block(height=320)
    rows = []
    for row in group["table"]:
        team = row["team"]
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.ThemeIcon(radius="xl", color=_position_color(row["position"]), size=12, variant="filled")),
                    dmc.TableTd(dcc.Link(dmc.Group([dmc.Text(team.get("flag_emoji", "🏳️")), dmc.Text(team["name"], fw=500)], gap="sm"), href=f"/teams?team={team['id']}")),
                    dmc.TableTd(row["playedGames"]),
                    dmc.TableTd(row["won"]),
                    dmc.TableTd(row["draw"]),
                    dmc.TableTd(row["lost"]),
                    dmc.TableTd(row["goalsFor"]),
                    dmc.TableTd(row["goalsAgainst"]),
                    dmc.TableTd(row["goalDifference"]),
                    dmc.TableTd(dmc.Text(str(row["points"]), className="display-number", c="#00D084", size="1.75rem")),
                    dmc.TableTd(_form_badges(row["form"])),
                ]
            )
        )
    table = dmc.Table(
        [
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh(""),
                        dmc.TableTh("Team"),
                        dmc.TableTh("P"),
                        dmc.TableTh("W"),
                        dmc.TableTh("D"),
                        dmc.TableTh("L"),
                        dmc.TableTh("GF"),
                        dmc.TableTh("GA"),
                        dmc.TableTh("GD"),
                        dmc.TableTh("Pts"),
                        dmc.TableTh("Form"),
                    ]
                )
            ),
            dmc.TableTbody(rows),
        ],
        striped=True,
        highlightOnHover=True,
    )
    return dmc.TableScrollContainer(table, minWidth=900)


def _progression_chart(group_name: str) -> go.Figure:
    matchday_1 = api.get_standings(matchday=1)
    matchday_2 = api.get_standings(matchday=2)
    matchday_3 = api.get_standings(matchday=3)
    lookup = {}
    for dataset in [matchday_1, matchday_2, matchday_3]:
        for group in dataset["standings"]:
            if group["group"] == group_name:
                for team_row in group["table"]:
                    lookup.setdefault(team_row["team"]["name"], []).append(team_row["points"])
    fig = go.Figure()
    colors = ["#00D084", "#4E9CFF", "#FFD700", "#FF4757"]
    for index, (team_name, values) in enumerate(sorted(lookup.items(), key=lambda item: item[1][-1], reverse=True)):
        flag_emoji = api.TEAM_NAME_INDEX.get(team_name, {}).get("flag_emoji", api._resolve_flag_emoji(team_name))
        fig.add_trace(
            go.Scatter(
                x=["MD1", "MD2", "MD3"],
                y=values,
                mode="lines+markers",
                name=team_name,
                line=dict(color=colors[index % len(colors)], width=3),
                marker=dict(size=10),
                hovertemplate=f"{flag_emoji} {team_name}: %{{y}} pts<extra></extra>",
            )
        )
    fig.update_layout(get_base_layout(height=360, margin=dict(t=20, b=20, l=20, r=20)))
    fig.update_yaxes(title="Points", rangemode="tozero")
    return fig


def layout(**_kwargs):
    group_options = api.get_group_options()
    default_group = group_options[0]["value"] if group_options else None
    return dmc.Stack(
        [
            dmc.Stack(
                [
                    dmc.Text("Group Standings", className="page-title"),
                    dmc.Text("All 12 groups, qualification race, and points progression", c="#7A8099", size="xl"),
                ],
                gap=4,
            ),
            dmc.Group(
                [
                    dmc.SegmentedControl(
                        id="standings-view",
                        value="All Groups",
                        data=["All Groups", "Group Detail"],
                        color="green",
                        radius="xl",
                    ),
                    dmc.Box(
                        dmc.Select(
                            id="standings-group-select",
                            value=default_group,
                            data=group_options,
                            searchable=True,
                            w=170,
                        ),
                        id="standings-group-select-wrap",
                        style={"display": "none"},
                    ),
                ],
                justify="space-between",
                wrap="wrap",
            ),
            dmc.Box(id="standings-content"),
        ],
        gap="md",
    )


@callback(
    Output("standings-content", "children"),
    Input("standings-view", "value"),
    Input("standings-group-select", "value"),
)
def render_standings(view_name: str, group_name: str):
    standings = api.get_standings().get("standings", [])
    if not standings:
        return build_loading_block(height=720)

    if view_name == "All Groups":
        return dmc.Stack(
            [
                dmc.Paper(
                    dmc.Stack(
                        [
                            dmc.Group(
                                [
                                    dmc.Text("POINTS TALLY", className="section-label", size="1rem"),
                                    dmc.Badge("0 to 6+ pts intensity", color="green", variant="light"),
                                ],
                                justify="space-between",
                                wrap="wrap",
                            ),
                            dmc.Text(
                                "Each row is a group, each column is a standings position (1st through 4th). The brighter the tile, the more points that team has earned — darker tiles mean fewer or no points so far.",
                                c="#7A8099",
                            ),
                            dcc.Graph(
                                figure=_all_groups_overview_chart(standings),
                                config=GRAPH_CONFIG,
                                style={"height": "620px"},
                            ),
                            dmc.Group(
                                [
                                    dmc.Group([dmc.Box(style={"width": 14, "height": 14, "borderRadius": 999, "background": "#0D0F14", "border": "1px solid #2A2F42"}), dmc.Text("0 pts", c="#7A8099", size="sm")], gap=8),
                                    dmc.Group([dmc.Box(style={"width": 14, "height": 14, "borderRadius": 999, "background": "#1D4130"}), dmc.Text("3 pts", c="#7A8099", size="sm")], gap=8),
                                    dmc.Group([dmc.Box(style={"width": 14, "height": 14, "borderRadius": 999, "background": "#00D084"}), dmc.Text("6+ pts", c="#7A8099", size="sm")], gap=8),
                                ],
                                gap="lg",
                                wrap="wrap",
                            ),
                        ],
                        gap="md",
                    )
                ),
                dmc.Stack(
                    [
                        dmc.Text("GROUP SNAPSHOTS", className="section-label", size="1rem"),
                        dmc.Grid(
                            [dmc.GridCol(_compact_group_card(group), span={"base": 12, "md": 6, "xl": 4}) for group in standings],
                            gutter="md",
                        ),
                    ],
                    gap="md",
                ),
            ],
            gap="md",
        )

    if not group_name:
        return build_loading_block(height=520)

    return dmc.Stack(
        [
            dmc.Paper(_detail_table(group_name)),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("POINTS PROGRESSION", className="section-label", size="1rem"),
                        dcc.Graph(figure=_progression_chart(group_name), config=GRAPH_CONFIG, style={"height": "360px"}),
                    ],
                    gap="md",
                )
            ),
        ],
        gap="md",
    )


@callback(
    Output("standings-group-select-wrap", "style"),
    Input("standings-view", "value"),
)
def toggle_group_select(view_name: str):
    if view_name == "Group Detail":
        return {"display": "block"}
    return {"display": "none"}
