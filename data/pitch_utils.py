from __future__ import annotations

import inspect
from copy import deepcopy
from datetime import date

import dash_mantine_components as dmc

BASE_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans, sans-serif", color="#E8EAF0", size=12),
    xaxis=dict(
        gridcolor="#2A2F42",
        zerolinecolor="#2A2F42",
        tickfont=dict(color="#7A8099"),
    ),
    yaxis=dict(
        gridcolor="#2A2F42",
        zerolinecolor="#2A2F42",
        tickfont=dict(color="#7A8099"),
    ),
    colorway=["#00D084", "#4E9CFF", "#FFD700", "#FF4757", "#A78BFA", "#FB923C"],
    margin=dict(t=30, b=30, l=20, r=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#E8EAF0")),
    hoverlabel=dict(
        bgcolor="#1C2030",
        bordercolor="#2A2F42",
        font=dict(color="#E8EAF0"),
    ),
)

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
PROGRESS_SUPPORTS_SECTIONS = "sections" in inspect.signature(dmc.Progress).parameters

STAT_KEY_MAP = {
    "possession": "ball_possession",
    "shots": "shots",
    "shots_on_target": "shots_on_goal",
    "corners": "corner_kicks",
    "free_kicks": "free_kicks",
    "offsides": "offsides",
    "fouls": "fouls",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
    "saves": "saves",
}


def get_base_layout(**overrides) -> dict:
    layout = deepcopy(BASE_LAYOUT)
    layout.update(overrides)
    return layout


def formation_to_positions(formation_str: str | None, side: str = "home") -> list[dict]:
    formation = formation_str or "4-3-3"
    try:
        lines = [int(n) for n in formation.split("-")[:4]]
    except ValueError:
        lines = [4, 3, 3]

    positions = []

    if side == "home":
        x_gk = 6
        x_lines = [18, 33, 48, 58]
    else:
        x_gk = 99
        x_lines = [87, 72, 57, 47]

    positions.append({"x": x_gk, "y": 34})

    for line_index, player_count in enumerate(lines):
        x = x_lines[min(line_index, len(x_lines) - 1)]
        y_spacing = 68 / (player_count + 1)
        for idx in range(player_count):
            positions.append({"x": x, "y": round(y_spacing * (idx + 1), 2)})

    return positions[:11]


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if not denominator:
        return default
    return numerator / denominator


def calculate_age(date_of_birth: str | None) -> int | None:
    if not date_of_birth:
        return None
    year, month, day = [int(part) for part in date_of_birth.split("-")]
    born = date(year, month, day)
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def get_stat_value(team_payload: dict, label: str) -> float:
    stats = team_payload.get("statistics", {}) if team_payload else {}
    api_key = STAT_KEY_MAP.get(label, label)
    return float(stats.get(api_key, 0) or 0)


def split_progress_sections(
    left_value: float,
    right_value: float,
    left_color: str = "#4E9CFF",
    right_color: str = "#00D084",
):
    total = max(left_value + right_value, 1)
    return [
        {"value": round((left_value / total) * 100, 2), "color": left_color},
        {"value": round((right_value / total) * 100, 2), "color": right_color},
    ]


def build_progress(
    *,
    sections: list[dict] | None = None,
    value: float | None = None,
    color: str | None = None,
    **kwargs,
):
    if sections is not None:
        if PROGRESS_SUPPORTS_SECTIONS:
            return dmc.Progress(sections=sections, **kwargs)

        return dmc.ProgressRoot(
            [
                dmc.ProgressSection(
                    value=section.get("value", 0),
                    color=section.get("color"),
                    striped=section.get("striped"),
                    animated=section.get("animated"),
                )
                for section in sections
            ],
            **kwargs,
        )

    return dmc.Progress(value=value, color=color, **kwargs)


def tug_of_war_sections(left_value: float, right_value: float):
    max_value = max(left_value, right_value, 1)
    left_fill = (left_value / max_value) * 50
    right_fill = (right_value / max_value) * 50
    center_gap = max(0, 100 - left_fill - right_fill)
    return [
        {"value": round(left_fill, 2), "color": "#4E9CFF"},
        {"value": round(center_gap, 2), "color": "rgba(42,47,66,0.9)"},
        {"value": round(right_fill, 2), "color": "#00D084"},
    ]
