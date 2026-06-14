from __future__ import annotations

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

NAV_SECTIONS = [
    (
        "OVERVIEW",
        [
            ("Tournament Hub", "/", "tabler:layout-dashboard"),
            ("Match Centre", "/live", "tabler:live-view"),
        ],
    ),
    (
        "COMPETITION",
        [
            ("Group Standings", "/standings", "tabler:list-numbers"),
        ],
    ),
    (
        "ANALYTICS",
        [
            ("Player Spotlight", "/players", "tabler:user"),
            ("Team Deep Dive", "/teams", "tabler:shield"),
            ("Leaderboards", "/leaderboards", "tabler:chart-bar"),
        ],
    ),
    (
        "ELO INTELLIGENCE",
        [
            ("Overall Rankings", "/predictions/elo-ratings", "tabler:chart-line"),
            ("Group Ratings", "/predictions/group-ratings", "tabler:git-compare"),
        ],
    ),
]


def _is_active(current_path: str, target_path: str) -> bool:
    if target_path == "/":
        return current_path == "/"
    if target_path == "/live":
        return current_path == "/live" or current_path.startswith("/match/")
    return current_path.startswith(target_path)


def build_navbar(current_path: str, live_matches: list[dict]):
    live_count = len([match for match in live_matches if match.get("status") in {"IN_PLAY", "PAUSED"}])
    nav_groups = []

    for section_title, links in NAV_SECTIONS:
        nav_groups.append(dmc.Text(section_title, className="shell-section-label", mt="md"))
        for label, path, icon in links:
            nav_groups.append(
                dmc.NavLink(
                    label=label,
                    href=path,
                    active=_is_active(current_path, path),
                    leftSection=DashIconify(icon=icon, width=20),
                    rightSection=dmc.Box(className="nav-live-dot")
                    if label == "Match Centre" and live_count
                    else None,
                    variant="subtle",
                    color="green",
                    px="lg",
                    py="sm",
                )
            )

    return dmc.Stack(
        [
            dmc.Box(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                html.Img(
                                    src=(
                                        "https://digitalhub.fifa.com/transform/"
                                        "157d23bf-7e13-4d7b-949e-5d27d340987e/WC26_Logo"
                                        "?&io=transform:fill&quality=75"
                                    ),
                                    alt="FIFA World Cup 2026 logo",
                                    className="brand-logo",
                                ),
                                dmc.Text("2026", className="brand-title"),
                            ],
                            gap="md",
                            align="center",
                        ),
                        dmc.Text("FIFA WORLD CUP", className="brand-subtitle"),
                    ],
                    gap=4,
                ),
                p="xl",
                style={"borderBottom": "1px solid var(--wc-border)"},
            ),
            dmc.ScrollArea(dmc.Stack(nav_groups, gap=6, pb="lg"), style={"flex": 1}),
            dmc.Box(
                dmc.Group(
                    [
                        dmc.Box(
                            DashIconify(icon="tabler:database", width=28, color="#7A8099"),
                            style={"display": "flex", "alignItems": "center", "justifyContent": "center"},
                        ),
                        dmc.Stack(
                            [
                                dmc.Text("football-data.org", c="#7A8099", lh=1.2),
                                dmc.Text("eloratings.net", c="#7A8099", lh=1.2),
                            ],
                            gap=2,
                            style={"flex": 1},
                        ),
                    ],
                    gap="md",
                    align="center",
                    wrap="nowrap",
                ),
                p="lg",
                style={"borderTop": "1px solid var(--wc-border)"},
            ),
        ],
        gap=0,
        h="100%",
    )
