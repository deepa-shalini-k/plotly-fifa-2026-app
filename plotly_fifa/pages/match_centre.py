from __future__ import annotations

from dash import Input, Output, callback, dcc, register_page
import dash_mantine_components as dmc

from components.loading import build_loading_block
from components.local_time import render_local_time
from components.match_formatting import live_minute_label
from components.match_centre_view import render_match_centre
from data import api

register_page(__name__, path="/live", name="Match Centre")


def _format_kickoff(match: dict):
    kickoff = match.get("utcDate")
    if not kickoff:
        return "Kickoff TBC"
    return render_local_time(kickoff, fallback="Kickoff TBC")


def _score_text(match: dict) -> str:
    full_time = match.get("score", {}).get("fullTime", {})
    home = full_time.get("home")
    away = full_time.get("away")
    if home is None or away is None:
        return "vs"
    return f"{home} - {away}"


def _status_badge(match: dict):
    status = match.get("status")
    if status in api.LIVE_STATUSES:
        minute_label = live_minute_label(match)
        return dmc.Badge(f"LIVE · {minute_label}" if minute_label else "LIVE", color="green", variant="filled")
    if status in api.COMPLETED_STATUSES:
        return dmc.Badge("FINAL", color="gray", variant="light")
    return dmc.Badge("UP NEXT", color="blue", variant="light")


def _match_link_card(match: dict, eyebrow: str, badge=None):
    home = match["homeTeam"]
    away = match["awayTeam"]
    body = dmc.Paper(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.Text(eyebrow, className="section-label", size="0.8rem"),
                        badge or _status_badge(match),
                    ],
                    justify="space-between",
                    wrap="wrap",
                ),
                dmc.Group(
                    [
                        dmc.Text(f"{home.get('flag_emoji', '🏳️')} {home['name']}", fw=600),
                        dmc.Text(_score_text(match), className="score-mono", c="#00D084" if match.get("status") in api.LIVE_STATUSES else "#E8EAF0", fw=700),
                        dmc.Text(f"{away['name']} {away.get('flag_emoji', '🏳️')}", fw=600),
                    ],
                    justify="space-between",
                    wrap="wrap",
                ),
                dmc.Text([_format_kickoff(match), f" · {match.get('venue', 'Venue TBC')}"], c="#7A8099"),
            ],
            gap="sm",
        ),
        h="100%",
    )
    return dcc.Link(body, href=f"/match/{match['id']}", style={"textDecoration": "none"})


def _today_fixture_list(matches: list[dict], title: str = "TODAY'S REAL FIXTURES"):
    if not matches:
        return None
    cards = [
        dmc.GridCol(_match_link_card(match, "TODAY"), span={"base": 12, "md": 6, "xl": 4})
        for match in matches
    ]
    return dmc.Stack(
        [
            dmc.Text(title, className="section-label", size="1rem"),
            dmc.Grid(cards, gutter="md"),
        ],
        gap="md",
    )


def _live_match_selector(live_matches: list[dict]):
    if len(live_matches) <= 1:
        return dmc.Group(
            [
                dmc.Badge("LIVE NOW", color="green", variant="filled"),
            ],
            gap="sm",
            wrap="wrap",
        )

    cards = [
        dmc.GridCol(_match_link_card(match, "ALSO LIVE"), span={"base": 12, "md": 6})
        for match in live_matches[1:]
    ]
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Badge(f"{len(live_matches)} MATCHES LIVE", color="green", variant="filled"),
                    dcc.Link(
                        dmc.Button("Open Featured Match Page", variant="light", color="green"),
                        href=f"/match/{live_matches[0]['id']}",
                        style={"textDecoration": "none"},
                    ),
                ],
                gap="sm",
                wrap="wrap",
            ),
            dmc.Grid(cards, gutter="md") if cards else None,
        ],
        gap="md",
    )


def _replay_match_options(matches: list[dict]) -> list[dict]:
    options = []
    for match in matches:
        score = _score_text(match)
        options.append(
            {
                "value": str(match["id"]),
                "label": (
                    f"{match['homeTeam'].get('flag_emoji', '🏳️')} {match['homeTeam']['name']} "
                    f"{score} {match['awayTeam']['name']} {match['awayTeam'].get('flag_emoji', '🏳️')}"
                ),
            }
        )
    return options


def _past_match_replay_selector(matches: list[dict]):
    if not matches:
        return dmc.Alert("No completed matches are available yet", color="gray", variant="light")

    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("MATCH REPLAY", className="section-label", size="1rem"),
                dmc.Text(
                    "The latest completed match is loaded by default. Use the dropdown to inspect any past match from the tournament.",
                    c="#7A8099",
                ),
                dmc.Select(
                    id="replay-match-select",
                    data=_replay_match_options(matches),
                    value=str(matches[0]["id"]),
                    clearable=False,
                    searchable=True,
                    persistence=True,
                    persistence_type="memory",
                ),
            ],
            gap="sm",
        ),
        h="100%",
    )


def _empty_live_state(payload: dict):
    next_match = payload.get("next_match")
    awaiting_live_matches = payload.get("awaiting_live_matches", [])
    replay_matches = payload.get("replay_matches", [])
    state = payload.get("state")

    if state == "awaiting_live_feed":
        title = "Kickoff is underway"
        description = (
            "A scheduled match has reached kickoff, but the official live feed has not switched to in-play yet. "
            "We'll surface the full live dashboard here as soon as the feed updates."
        )
    elif state == "data_unavailable":
        title = "Live data is currently unavailable"
        description = (
            "The live feed is not configured in this environment."
            if not payload.get("has_api_key") and not payload.get("is_demo_mode")
            else "We couldn't load the current live feed just now. Please try again shortly."
        )
    elif state == "no_matches_available":
        title = "No current live matches"
        description = "There are no in-play or upcoming fixtures in today's feed."
    else:
        title = "No current live matches"
        description = "We'll surface the live dashboard here as soon as a real match starts."

    panels = [
        dmc.Grid(
            [
                dmc.GridCol(
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Badge("MATCH CENTRE", color="gray", variant="light"),
                                dmc.Text(title, className="page-title", size="3rem"),
                                dmc.Text(description, c="#7A8099", maw=720),
                            ],
                            gap="sm",
                        ),
                        h="100%",
                    ),
                    span={"base": 12, "md": 7},
                ),
                dmc.GridCol(
                    _past_match_replay_selector(replay_matches),
                    span={"base": 12, "md": 5},
                ),
            ],
            gutter="md",
            align="stretch",
        )
    ]
    if replay_matches:
        panels.append(dmc.Box(id="replay-match-region"))

    context_cards = []
    awaiting_ids = {match.get("id") for match in awaiting_live_matches if match}
    for match in awaiting_live_matches:
        context_cards.append(
            dmc.GridCol(
                _match_link_card(
                    match,
                    "KICKOFF WINDOW",
                    badge=dmc.Badge("AWAITING LIVE", color="orange", variant="light"),
                ),
                span={"base": 12, "xl": 6},
            )
        )
    if next_match and next_match.get("id") not in awaiting_ids:
        context_cards.append(
            dmc.GridCol(_match_link_card(next_match, "NEXT KICKOFF"), span={"base": 12, "xl": 6})
        )

    if context_cards:
        panels.append(dmc.Grid(context_cards, gutter="md"))

    return dmc.Stack(panels, gap="md")


def layout(**_kwargs):
    return dmc.Stack(
        [
            dcc.Store(id="live-hub-payload"),
            dcc.Interval(id="live-hub-interval", interval=60_000, n_intervals=0),
            dmc.Box(id="live-hub-body"),
        ],
        gap="md",
    )


@callback(
    Output("live-hub-payload", "data"),
    Input("live-hub-interval", "n_intervals"),
)
def refresh_live_hub(_: int):
    return api.get_live_hub_payload()


@callback(
    Output("live-hub-body", "children"),
    Input("live-hub-payload", "data"),
)
def render_live_hub(payload: dict | None):
    if not payload:
        return dmc.Skeleton(height=700, visible=True)

    if payload.get("state") == "data_unavailable":
        return build_loading_block(height=700)

    featured_match = payload.get("featured_match")
    if featured_match:
        return dmc.Stack(
            [
                _live_match_selector(payload.get("live_matches", [])),
                render_match_centre(featured_match),
            ],
            gap="md",
        )

    return _empty_live_state(payload)


@callback(
    Output("replay-match-region", "children"),
    Input("live-hub-payload", "data"),
    Input("replay-match-select", "value"),
)
def render_replay_match(payload: dict | None, selected_match_id: str | None):
    if not payload or payload.get("featured_match"):
        return None

    replay_matches = payload.get("replay_matches", [])
    if not replay_matches:
        return None

    selected_match_meta = next(
        (match for match in replay_matches if str(match.get("id")) == str(selected_match_id)),
        replay_matches[0],
    )
    selected_match = api.get_match(selected_match_meta["id"])
    return render_match_centre(selected_match or selected_match_meta)
