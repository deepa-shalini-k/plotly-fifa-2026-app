from __future__ import annotations

from dash import Input, Output, State, callback, dcc, no_update, register_page
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from components.loading import build_loading_block
from components.match_centre_view import render_match_centre
from data import api

register_page(__name__, path_template="/match/<match_id>", name="Match Detail")


def _match_unavailable():
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Badge("MATCH DATA", color="gray", variant="light"),
                dmc.Text("This match isn't available right now", className="page-title", size="3rem"),
                dmc.Text(
                    "The live detail feed for this fixture could not be loaded. Try returning to the match centre or checking today's fixtures from the tournament hub.",
                    c="#7A8099",
                    maw=720,
                ),
                dmc.Group(
                    [
                        dcc.Link(
                            dmc.Button("Go to Match Centre", color="green"),
                            href="/live",
                            style={"textDecoration": "none"},
                        ),
                        dcc.Link(
                            dmc.Button("Back to Tournament Hub", variant="light", color="green"),
                            href="/",
                            style={"textDecoration": "none"},
                        ),
                    ],
                    gap="sm",
                    wrap="wrap",
                ),
            ],
            gap="md",
        )
    )


def layout(match_id=None, **_kwargs):
    return dmc.Stack(
        [
            dcc.Store(id="match-detail-match-id", data=str(match_id or "")),
            dcc.Store(id="match-detail-data"),
            dcc.Store(id="match-detail-prev-goals"),
            dcc.Interval(id="match-detail-interval", interval=30_000, n_intervals=0),
            dmc.Box(id="match-detail-body"),
        ],
        gap="md",
    )


@callback(
    Output("match-detail-data", "data"),
    Output("match-detail-interval", "disabled"),
    Input("match-detail-interval", "n_intervals"),
    Input("match-detail-match-id", "data"),
)
def refresh_match_data(_: int, match_id: str):
    if not match_id:
        return {}, True
    match = api.get_match(match_id)
    if not match:
        return {}, True
    is_live = match.get("status") in api.LIVE_STATUSES
    return match, not is_live


@callback(
    Output("match-detail-body", "children"),
    Input("match-detail-data", "data"),
)
def render_match_page(match_data: dict):
    if not match_data:
        return build_loading_block(height=700)
    return render_match_centre(match_data)


@callback(
    Output("notification-region", "children"),
    Output("match-detail-prev-goals", "data"),
    Input("match-detail-data", "data"),
    State("match-detail-prev-goals", "data"),
)
def detect_new_goal(match_data: dict, previous_goal_state: dict | None):
    if not match_data:
        return no_update, previous_goal_state

    current_goal_count = len(match_data.get("goals", []))
    if previous_goal_state is None:
        return no_update, {"count": current_goal_count}

    previous_count = previous_goal_state.get("count", current_goal_count)
    if current_goal_count > previous_count:
        new_goal = match_data["goals"][-1]
        notification = dmc.Notification(
            title=f"GOAL! {new_goal['scorer']['name']}",
            message=f"{new_goal['team']['name']} {new_goal['score']['home']}-{new_goal['score']['away']} ({new_goal['minute']}')",
            color="green",
            icon=DashIconify(icon="tabler:ball-football", width=18),
            withCloseButton=True,
        )
        return notification, {"count": current_goal_count}

    return no_update, {"count": current_goal_count}
