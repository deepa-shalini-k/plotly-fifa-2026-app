from __future__ import annotations

import dash_mantine_components as dmc

from data.pitch_utils import calculate_age


def _initials(name: str) -> str:
    parts = [part[0] for part in name.split() if part]
    return "".join(parts[:2]).upper() or "WC"


def build_avatar(player_name: str, photo_url: str | None, size: int = 132):
    if photo_url:
        return dmc.Avatar(src=photo_url, size=size, radius=size, mx="auto")
    return dmc.Avatar(
        _initials(player_name),
        size=size,
        radius=size,
        mx="auto",
        className="player-avatar-fallback",
        styles={"placeholder": {"fontFamily": "Barlow Condensed, sans-serif", "fontSize": "2.2rem", "color": "#4E9CFF"}},
    )


def _stat_cell(value: str, label: str, color: str):
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(value, className="display-number", c=color, ta="center", size="2.4rem"),
                dmc.Text(label, c="#7A8099", ta="center", size="sm"),
            ],
            gap=0,
            justify="center",
            h="100%",
        ),
        className="stats-mini-cell",
        p="md",
    )


def build_player_card(
    player: dict,
    stats: dict,
    photo_url: str | None,
    stat_items: list[tuple[str, str, str]] | None = None,
):
    age = calculate_age(player.get("dateOfBirth"))
    nationality = player.get("nationality", player.get("country", ""))
    stat_items = stat_items or [
        (str(stats.get("goals", 0)), "Goals", "#00D084"),
        (str(stats.get("assists", 0)), "Assists", "#4E9CFF"),
        (str(stats.get("minutesPlayed", 0)), "Minutes", "#FFD700"),
        (str(stats.get("yellowCards", 0)), "Yellow", "#FF4757"),
    ]
    badges = dmc.Group(
        [
            dmc.Badge(player.get("position", "Player"), color="blue", variant="light"),
            dmc.Badge(f"Age {age}" if age is not None else "Age N/A", color="green", variant="light"),
        ],
        justify="center",
        gap="sm",
    )

    return dmc.Paper(
        dmc.Stack(
            [
                build_avatar(player.get("name", "Unknown Player"), photo_url),
                dmc.Stack(
                    [
                        dmc.Text(player.get("name", "Unknown Player"), className="page-title", size="3rem", ta="center"),
                        dmc.Text(
                            f"{player.get('flag_emoji', '🏳️')}  {nationality} · {player.get('position', 'Player')} · #{player.get('shirtNumber', '—')}",
                            c="#7A8099",
                            ta="center",
                        ),
                    ],
                    gap=2,
                ),
                badges,
                dmc.Grid(
                    [
                        dmc.GridCol(_stat_cell(value, label, color), span=6)
                        for value, label, color in stat_items[:4]
                    ],
                    gutter="sm",
                ),
            ],
            gap="lg",
        )
    )
