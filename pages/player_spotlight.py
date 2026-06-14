from __future__ import annotations

from dash import Input, Output, callback, ctx, dcc, register_page
import dash_mantine_components as dmc
import plotly.graph_objects as go

from components.loading import build_loading_block
from components.player_card import build_player_card
from data import api, player_photos
from data.pitch_utils import GRAPH_CONFIG, build_progress, get_base_layout, safe_div

register_page(__name__, path="/players", name="Player Spotlight")

DEFAULT_PLAYER_STATS = {
    "goals": 0,
    "assists": 0,
    "playedMatches": 0,
    "startingXI": 0,
    "matchesOnPitch": 0,
    "goalInvolvements": 0,
}


def _normalize_player_stats(player: dict | None) -> dict:
    normalized = dict(DEFAULT_PLAYER_STATS)
    if not isinstance(player, dict):
        return normalized
    for key in normalized:
        value = player.get(key, normalized[key])
        normalized[key] = value if isinstance(value, (int, float)) else normalized[key]
    normalized["matchesOnPitch"] = normalized["matchesOnPitch"] or normalized["playedMatches"]
    normalized["playedMatches"] = normalized["playedMatches"] or normalized["matchesOnPitch"]
    normalized["goalInvolvements"] = normalized["goals"] + normalized["assists"]
    return normalized


def _parse_player_id(candidate_value: str | int | None) -> int | None:
    try:
        return int(candidate_value) if candidate_value is not None else None
    except (TypeError, ValueError):
        return None


def _enrich_selected_player(player: dict | None) -> dict | None:
    if not player or player.get("id") is None:
        return player

    details = dict(api.get_person(player["id"]))
    if details.get("id") != player["id"]:
        return player

    stats = _normalize_player_stats(player)
    enriched = {**player, **details, **stats}
    enriched["goalInvolvements"] = enriched.get("goals", 0) + enriched.get("assists", 0)
    return enriched


def _build_spotlight_context(candidate_value: str | int | None = None) -> dict:
    requested_player_id = _parse_player_id(candidate_value)
    scorers = [dict(row) for row in api.get_scorers(limit=10)]
    players = []
    seen_ids = set()
    for player in api.get_all_player_profiles():
        if player.get("id") in seen_ids:
            continue
        normalized = {**player, **_normalize_player_stats(player)}
        normalized["goalInvolvements"] = normalized.get("goals", 0) + normalized.get("assists", 0)
        players.append(normalized)
        seen_ids.add(normalized.get("id"))

    selected_player = next((player for player in players if player.get("id") == requested_player_id), None)
    if not selected_player and players:
        selected_player = players[0]

    if not selected_player and requested_player_id is not None:
        fallback_player = dict(api.get_person(requested_player_id))
        if fallback_player.get("id") == requested_player_id:
            selected_player = {**fallback_player, **DEFAULT_PLAYER_STATS}
            players.append(selected_player)
            seen_ids.add(requested_player_id)

    selected_player = _enrich_selected_player(selected_player)
    if selected_player and selected_player.get("id") not in seen_ids:
        players.append(selected_player)

    players.sort(
        key=lambda player: (
            player.get("goals", 0),
            player.get("assists", 0),
            player.get("playedMatches", 0),
            player.get("name", ""),
        ),
        reverse=True,
    )
    options = []
    seen_values = set()
    for player in players:
        value = str(player.get("id"))
        if not value or value in seen_values:
            continue
        options.append({"value": value, "label": player.get("name", f"Player {value}")})
        seen_values.add(value)

    return {
        "players": players,
        "scorers": scorers,
        "top_five_ids": {row["player"]["id"] for row in scorers[:5] if row.get("player", {}).get("id") is not None},
        "selected_player": selected_player,
        "selected_player_id": selected_player.get("id") if selected_player else None,
        "options": options,
    }


def _player_metric_values(player: dict) -> dict:
    matches = player.get("matchesOnPitch", 0)
    goal_involvements = player.get("goalInvolvements", player.get("goals", 0) + player.get("assists", 0))
    return {
        "Goals": player.get("goals", 0),
        "Assists": player.get("assists", 0),
        "Goals per Match": safe_div(player.get("goals", 0), matches),
        "Goal Involvements": goal_involvements,
    }


def _empty_figure(height: int, title_text: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(get_base_layout(height=height))
    fig.add_annotation(
        text=title_text,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(color="#7A8099", size=16),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _radar_figure(context: dict) -> go.Figure:
    players = context["players"]
    selected = context["selected_player"]
    if not players or not selected:
        return _empty_figure(420, "Loading live player data")

    metrics_by_player = {player["id"]: _player_metric_values(player) for player in players}
    selected_player_id = selected["id"]
    averages = {}
    maxima = {}
    axes = list(metrics_by_player[selected_player_id].keys())
    for axis in axes:
        values = [metric_map[axis] for metric_map in metrics_by_player.values()]
        averages[axis] = sum(values) / len(values)
        maxima[axis] = max(values) or 1

    selected_values = [metrics_by_player[selected_player_id][axis] / maxima[axis] for axis in axes]
    average_values = [averages[axis] / maxima[axis] for axis in axes]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=selected_values,
            theta=axes,
            fill="toself",
            name=selected["name"],
            line=dict(color="#00D084", width=3),
            fillcolor="rgba(0,208,132,0.16)",
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=average_values,
            theta=axes,
            name="Tournament Avg",
            line=dict(color="#4E9CFF", width=2, dash="dash"),
        )
    )
    fig.update_layout(get_base_layout(height=420, polar=dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(showticklabels=False, ticks="", gridcolor="#2A2F42"), angularaxis=dict(gridcolor="#2A2F42"))))
    return fig


def _scatter_figure(context: dict) -> go.Figure:
    players = context["players"]
    selected_player_id = context["selected_player_id"]
    top_five_ids = context["top_five_ids"]
    if not players:
        return _empty_figure(360, "Loading live scorer distribution")

    fig = go.Figure()
    for player in players:
        marker_color = "rgba(122,128,153,0.4)"
        marker_size = 10
        text = None
        if player["id"] in top_five_ids:
            marker_color = "#4E9CFF"
        if player["id"] == selected_player_id:
            marker_color = "#00D084"
            marker_size = 16
            text = player["name"]
        fig.add_trace(
            go.Scatter(
                x=[player.get("playedMatches", player.get("matchesOnPitch", 0))],
                y=[player.get("goals", 0)],
                mode="markers+text" if text else "markers",
                text=[text] if text else None,
                textposition="top center",
                marker=dict(size=marker_size, color=marker_color, line=dict(color="#E8EAF0", width=1 if player["id"] == selected_player_id else 0)),
                customdata=[[player["id"]]],
                hovertemplate=(
                    f"{player['name']}"
                    f"<br>Goals: {player.get('goals', 0)}"
                    f"<br>Assists: {player.get('assists', 0)}"
                    f"<br>Matches: {player.get('playedMatches', player.get('matchesOnPitch', 0))}"
                    f"<br>{player.get('nationality', '')}<extra></extra>"
                ),
                showlegend=False,
            )
        )
    fig.update_layout(
        get_base_layout(
            height=360,
            xaxis=dict(title="Matches Played", gridcolor="#2A2F42", rangemode="tozero"),
            yaxis=dict(title="Goals", gridcolor="#2A2F42", rangemode="tozero"),
        )
    )
    return fig


def _golden_boot_rows(scorers: list[dict]):
    if not scorers:
        return build_loading_block(height=320)

    max_goals = max([row["goals"] for row in scorers], default=1)
    rows = []
    for index, scorer in enumerate(scorers, start=1):
        progress = (scorer["goals"] / max_goals) * 100
        rows.append(
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Text(str(index), className="mono-text", c="#7A8099", w=16),
                                dmc.Text(f"{scorer['player']['name']} {scorer['team'].get('flag_emoji', '🏳️')}", fw=500, style={"flex": 1}),
                                dmc.Text(str(scorer["goals"]), className="display-number", c="#FFD700", size="2rem"),
                            ],
                            gap="md",
                            align="center",
                        ),
                        dmc.Group(
                            [
                                build_progress(value=progress, color="green", radius="xl", style={"flex": 1}),
                                dmc.Text(f"Assists {scorer['assists']}", c="#7A8099", size="sm", w=78, ta="right"),
                            ],
                            gap="md",
                            align="center",
                        ),
                    ],
                    gap="xs",
                ),
                className="stats-mini-cell",
                p="sm",
            )
        )
    return dmc.Stack(rows, gap="sm")


def _player_card_region(player: dict | None):
    if not player:
        return build_loading_block(height=320)
    goal_involvements = player.get("goalInvolvements", player.get("goals", 0) + player.get("assists", 0))
    return build_player_card(
        player,
        player,
        player_photos.get_player_photo_url(player.get("id")),
        stat_items=[
            (str(player.get("goals", 0)), "Goals", "#00D084"),
            (str(player.get("assists", 0)), "Assists", "#4E9CFF"),
            (str(player.get("playedMatches", player.get("matchesOnPitch", 0))), "Matches", "#FFD700"),
            (str(goal_involvements), "Goal Inv.", "#FF4757"),
        ],
    )


def layout(player=None, **_kwargs):
    context = _build_spotlight_context(str(player) if player is not None else None)
    selected_player = context["selected_player"]
    default_player_id = context["selected_player_id"] or api.get_top_player_id()
    default_player = str(default_player_id) if default_player_id is not None and context["options"] else None
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            dmc.Text("Player Spotlight", className="page-title"),
                            dmc.Text("Select a real tournament scorer from the chart or dropdown", c="#7A8099", size="xl"),
                        ],
                        gap=4,
                    ),
                    dmc.Select(
                        id="player-select",
                        value=default_player,
                        data=context["options"],
                        searchable=True,
                        disabled=not context["options"],
                        w=260,
                    ),
                ],
                justify="space-between",
                align="center",
                wrap="wrap",
            ),
            dmc.Grid(
                [
                    dmc.GridCol(
                        dmc.Box(_player_card_region(selected_player), id="player-card-region"),
                        span={"base": 12, "xl": 4},
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("ATTACKING PROFILE · VS TOURNAMENT SCORER AVG", className="section-label", size="1rem"),
                                    dcc.Graph(id="player-radar", figure=_radar_figure(context), config=GRAPH_CONFIG, style={"height": "420px"}),
                                ],
                                gap="md",
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 8},
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
                                    dmc.Text("TOURNAMENT SCORERS · GOALS VS MATCHES PLAYED", className="section-label", size="1rem"),
                                    dcc.Graph(id="player-scatter", figure=_scatter_figure(context), config=GRAPH_CONFIG, style={"height": "380px"}),
                                ],
                                gap="md",
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 6},
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Text("GOLDEN BOOT RACE", className="section-label", size="1rem"),
                                    dmc.Box(_golden_boot_rows(context["scorers"]), id="golden-boot-region"),
                                ],
                                gap="md",
                            ),
                            h="100%",
                        ),
                        span={"base": 12, "xl": 6},
                    ),
                ],
                gutter="md",
            ),
        ],
        gap="md",
    )


@callback(
    Output("player-select", "value"),
    Output("player-card-region", "children"),
    Output("player-radar", "figure"),
    Output("player-scatter", "figure"),
    Output("golden-boot-region", "children"),
    Input("player-scatter", "clickData"),
    Input("player-select", "value"),
)
def update_player_spotlight(click_data: dict | None, dropdown_value: str | None):
    fallback_player_id = api.get_top_player_id()
    selected_player_id = dropdown_value or (str(fallback_player_id) if fallback_player_id is not None else None)
    if ctx.triggered_id == "player-scatter" and click_data:
        selected_player_id = str(click_data["points"][0]["customdata"][0])

    context = _build_spotlight_context(selected_player_id)
    selected_player = context["selected_player"]
    selected_player_id = context["selected_player_id"]
    if not selected_player or selected_player_id is None:
        return (
            str(fallback_player_id) if fallback_player_id is not None else None,
            build_loading_block(height=320),
            _empty_figure(420, "Loading live player data"),
            _empty_figure(360, "Loading live scorer distribution"),
            _golden_boot_rows(context["scorers"]),
        )

    return (
        str(selected_player_id),
        _player_card_region(selected_player),
        _radar_figure(context),
        _scatter_figure(context),
        _golden_boot_rows(context["scorers"]),
    )
