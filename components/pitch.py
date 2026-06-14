from __future__ import annotations

import plotly.graph_objects as go

from data.pitch_utils import formation_to_positions, get_base_layout

PITCH_BG = "#0A1A12"
PITCH_LINE = "rgba(0,208,132,0.3)"


def _pitch_shapes() -> list[dict]:
    return [
        dict(
            type="rect",
            x0=0,
            x1=105,
            y0=0,
            y1=68,
            layer="below",
            line=dict(color="rgba(0,208,132,0.4)", width=2),
            fillcolor=PITCH_BG,
        ),
        dict(type="line", x0=52.5, x1=52.5, y0=0, y1=68, layer="below", line=dict(color=PITCH_LINE, width=1)),
        dict(
            type="circle",
            x0=43.35,
            x1=61.65,
            y0=24.85,
            y1=43.15,
            layer="below",
            line=dict(color=PITCH_LINE, width=1),
        ),
        dict(type="rect", x0=0, x1=16.5, y0=13.84, y1=54.16, layer="below", line=dict(color="rgba(0,208,132,0.25)", width=1)),
        dict(type="rect", x0=88.5, x1=105, y0=13.84, y1=54.16, layer="below", line=dict(color="rgba(0,208,132,0.25)", width=1)),
        dict(type="rect", x0=0, x1=5.5, y0=24.84, y1=43.16, layer="below", line=dict(color="rgba(0,208,132,0.2)", width=1)),
        dict(type="rect", x0=99.5, x1=105, y0=24.84, y1=43.16, layer="below", line=dict(color="rgba(0,208,132,0.2)", width=1)),
        dict(type="circle", x0=10.8, x1=11.2, y0=33.8, y1=34.2, layer="below", fillcolor="rgba(0,208,132,0.55)", line=dict(width=0)),
        dict(type="circle", x0=93.8, x1=94.2, y0=33.8, y1=34.2, layer="below", fillcolor="rgba(0,208,132,0.55)", line=dict(width=0)),
    ]


def _player_marker_trace(
    players: list[dict],
    positions: list[dict],
    color: str,
    name: str,
    marker_size: int = 22,
    shirt_number_size: int | None = None,
) -> go.Scatter:
    shirt_number_size = shirt_number_size or max(10, round(marker_size * 0.45))
    return go.Scatter(
        x=[pos["x"] for pos in positions[: len(players)]],
        y=[pos["y"] for pos in positions[: len(players)]],
        mode="markers+text",
        marker=dict(size=marker_size, color=color, opacity=0.88, line=dict(color="#0D0F14", width=2)),
        text=[str(player.get("shirtNumber", "")) for player in players[: len(positions)]],
        textfont=dict(color="#0D0F14", size=shirt_number_size, family="Barlow Condensed, sans-serif"),
        textposition="middle center",
        customdata=[[player.get("name", ""), player.get("position", "")] for player in players[: len(positions)]],
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
        name=name,
        showlegend=False,
    )


def _player_name_trace(
    players: list[dict],
    positions: list[dict],
    color: str,
    font_size: int = 9,
    y_offset: float = 3.2,
) -> go.Scatter:
    return go.Scatter(
        x=[pos["x"] for pos in positions[: len(players)]],
        y=[max(pos["y"] - y_offset, 1.5) for pos in positions[: len(players)]],
        mode="text",
        text=[player.get("shortName") or player.get("name", "").split(" ")[0] for player in players[: len(positions)]],
        textfont=dict(color=color, size=font_size, family="DM Sans, sans-serif"),
        hoverinfo="skip",
        showlegend=False,
    )


def draw_pitch(
    home_formation: str | None = None,
    away_formation: str | None = None,
    home_lineup: list | None = None,
    away_lineup: list | None = None,
    home_color: str = "#4E9CFF",
    away_color: str = "#00D084",
    show_labels: bool = True,
    height: int = 500,
    empty_state_text: str | None = None,
    marker_size: int = 22,
    shirt_number_size: int | None = None,
    player_name_font_size: int = 9,
    player_name_offset: float = 3.2,
    formation_font_size: int = 18,
    layout_margin: dict | None = None,
    x_range: tuple[float, float] | None = None,
    y_range: tuple[float, float] | None = None,
) -> go.Figure:
    home_lineup = home_lineup or []
    away_lineup = away_lineup or []
    home_positions = formation_to_positions(home_formation, side="home") if home_lineup else []
    away_positions = formation_to_positions(away_formation, side="away") if away_lineup else []

    figure = go.Figure()

    if home_lineup:
        figure.add_trace(
            _player_marker_trace(
                home_lineup,
                home_positions,
                home_color,
                "Home",
                marker_size=marker_size,
                shirt_number_size=shirt_number_size,
            )
        )
        if show_labels:
            figure.add_trace(
                _player_name_trace(
                    home_lineup,
                    home_positions,
                    home_color,
                    font_size=player_name_font_size,
                    y_offset=player_name_offset,
                )
            )

    if away_lineup:
        figure.add_trace(
            _player_marker_trace(
                away_lineup,
                away_positions,
                away_color,
                "Away",
                marker_size=marker_size,
                shirt_number_size=shirt_number_size,
            )
        )
        if show_labels:
            figure.add_trace(
                _player_name_trace(
                    away_lineup,
                    away_positions,
                    away_color,
                    font_size=player_name_font_size,
                    y_offset=player_name_offset,
                )
            )

    annotations = []
    if home_lineup:
        annotations.append(
            dict(
                x=26,
                y=1.5,
                text=home_formation or "TBD",
                showarrow=False,
                font=dict(color=home_color, family="Barlow Condensed, sans-serif", size=formation_font_size),
            )
        )
    if away_lineup:
        annotations.append(
            dict(
                x=79,
                y=1.5,
                text=away_formation or "TBD",
                showarrow=False,
                font=dict(color=away_color, family="Barlow Condensed, sans-serif", size=formation_font_size),
            )
        )

    if not home_lineup and not away_lineup:
        annotations.append(
            dict(
                x=52.5,
                y=34,
                text=empty_state_text or "Starting lineups not yet announced",
                showarrow=False,
                font=dict(color="#7A8099", size=16, family="DM Sans, sans-serif"),
            )
        )

    figure.update_layout(
        get_base_layout(
            height=height,
            shapes=_pitch_shapes(),
            annotations=annotations,
            margin=layout_margin or dict(t=10, b=10, l=10, r=10),
        )
    )
    figure.update_xaxes(range=list(x_range or (-1.5, 106.5)), visible=False, fixedrange=True)
    figure.update_yaxes(range=list(y_range or (-2, 70)), visible=False, fixedrange=True, scaleanchor="x", scaleratio=1)
    return figure
