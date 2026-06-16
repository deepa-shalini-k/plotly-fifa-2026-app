from __future__ import annotations

import json

from dash import Input, Output, callback, dcc, html, register_page
import dash_nivo as dn
import dash_mantine_components as dmc

from components.local_time import render_local_time
from data.predictions import (
    CONFEDERATION_COLORS,
    TEAM_DISPLAY_ORDER,
    TEAM_TO_FIFA_CODE,
    TARGET_TEAMS,
    TEAM_TO_CONFEDERATION,
    WORLD_CUP_RESULTS_START_DATE,
    load_elo_snapshots,
    load_match_results,
)

register_page(__name__, path="/predictions/elo-ratings", name="Overall Rankings")

RANK_BAND_BASE = 10_000


def _format_signed(value: int | float | None) -> str:
    if value is None:
        return "—"
    numeric = int(value)
    if numeric > 0:
        return f"+{numeric}"
    if numeric < 0:
        return str(numeric)
    return "0"


def _placeholder(message: str):
    return dmc.Center(
        dmc.Stack(
            [
                dmc.Text("Elo bump chart is warming up", className="section-title", ta="center"),
                dmc.Text(message, c="#7A8099", ta="center", maw=520),
            ],
            gap="xs",
            align="center",
        ),
        className="empty-state",
        mih=580,
    )


def _legend_badges():
    items = []
    for confederation, color in CONFEDERATION_COLORS.items():
        items.append(
            dmc.Badge(
                confederation,
                variant="light",
                color="gray",
                style={"border": f"1px solid {color}", "color": color},
            )
        )
    return dmc.Group(items, gap="xs", wrap="wrap")


def _daily_snapshots(snapshots, match_results=None):
    frame = snapshots.copy()
    frame = frame.sort_values(["team", "scraped_at"])
    frame = frame.groupby(["team", "scraped_at"], as_index=False).last()
    frame["team_order"] = frame["team"].map(TEAM_DISPLAY_ORDER)
    signature_frame = frame.sort_values(["scraped_at", "team_order"]).copy()
    signature_frame["signature"] = (
        signature_frame["team"]
        + "|"
        + signature_frame["rank"].astype(str)
        + "|"
        + signature_frame["elo_rating"].astype(str)
    )
    checkpoint_signatures = signature_frame.groupby("scraped_at")["signature"].agg("||".join)
    distinct_checkpoints = checkpoint_signatures[checkpoint_signatures.ne(checkpoint_signatures.shift())].index
    frame = frame[frame["scraped_at"].isin(distinct_checkpoints)].copy()
    frame = frame.drop(columns=["team_order"])
    checkpoint_meta = frame[["scraped_at"]].drop_duplicates().sort_values("scraped_at").reset_index(drop=True)
    checkpoint_meta["snapshot_day"] = checkpoint_meta["scraped_at"].dt.tz_localize(None).dt.normalize()
    if match_results is not None and not match_results.empty and len(checkpoint_meta) > 1:
        baseline_day = checkpoint_meta.loc[0, "snapshot_day"]
        unique_matches = (
            match_results[match_results["match_date"] > baseline_day].copy()
            .assign(
                match_key=lambda value: value.apply(
                    lambda row: f"{row['match_date'].strftime('%Y-%m-%d')}|{'::'.join(sorted([row['team'], row['opponent']]))}",
                    axis=1,
                )
            )
            .drop_duplicates(subset=["match_key"], keep="first")
            .sort_values(["match_date", "team", "opponent"])
        )
        local_match_days = list(unique_matches["match_date"].dt.normalize())
        expected_checkpoints = len(checkpoint_meta) - 1
        if len(local_match_days) >= expected_checkpoints:
            checkpoint_meta.loc[1:, "snapshot_day"] = local_match_days[:expected_checkpoints]
    checkpoint_meta["day_number"] = (checkpoint_meta["snapshot_day"] - WORLD_CUP_RESULTS_START_DATE).dt.days + 1
    checkpoint_meta["day_label"] = checkpoint_meta["day_number"].map(lambda value: f"Day {int(value)}")
    checkpoint_meta["date_label"] = checkpoint_meta["snapshot_day"].dt.strftime("%d %b %Y")
    frame = frame.merge(checkpoint_meta, on="scraped_at", how="left")
    frame = frame.sort_values(["team", "scraped_at"])
    frame = frame.groupby(["team", "snapshot_day"], as_index=False).last()
    frame["team_order"] = frame["team"].map(TEAM_DISPLAY_ORDER)
    daily_signature_frame = frame.sort_values(["snapshot_day", "team_order"]).copy()
    daily_signature_frame["signature"] = (
        daily_signature_frame["team"]
        + "|"
        + daily_signature_frame["rank"].astype(str)
        + "|"
        + daily_signature_frame["elo_rating"].astype(str)
    )
    day_signatures = daily_signature_frame.groupby("snapshot_day")["signature"].agg("||".join)
    distinct_days = day_signatures[day_signatures.ne(day_signatures.shift())].index
    frame = frame[frame["snapshot_day"].isin(distinct_days)].copy()
    frame = frame.drop(columns=["team_order"])
    return frame


def _nivo_bump_data(snapshots, match_results=None):
    frame = _daily_snapshots(snapshots, match_results=match_results)
    frame["elo_delta"] = frame.groupby("team")["elo_rating"].diff()
    frame["rank_delta"] = frame.groupby("team")["rank"].diff()
    series = []

    for team in TARGET_TEAMS:
        team_rows = frame[frame["team"] == team].copy()
        if team_rows.empty:
            continue

        confederation = TEAM_TO_CONFEDERATION[team]
        series.append(
            {
                "id": team,
                "color": CONFEDERATION_COLORS[confederation],
                "data": [
                    {
                        "x": row.day_label,
                        # AreaBump uses y for both stacking order and band thickness.
                        # A large shared base keeps ribbons visually even while the
                        # rank offset still preserves the correct ordering.
                        "y": RANK_BAND_BASE + (49 - int(row.rank)),
                        "rank": int(row.rank),
                        "elo_rating": int(row.elo_rating),
                        "elo_delta": _format_signed(row.elo_delta if row.elo_delta == row.elo_delta else 0),
                        "rank_delta": _format_signed(row.rank_delta if row.rank_delta == row.rank_delta else 0),
                        "date_label": row.date_label,
                    }
                    for row in team_rows.itertuples(index=False)
                ],
            }
        )

    axis_bottom = {
        "tickSize": 0,
        "tickPadding": 14,
        "tickRotation": 0,
        "legend": "Tournament day since 11 Jun 2026",
        "legendPosition": "middle",
        "legendOffset": 42,
        "truncateTickAt": 0,
    }
    return series, axis_bottom


def layout(**_kwargs):
    return dmc.Stack(
        [
            dcc.Interval(id="elo-ratings-refresh-interval", interval=900_000, n_intervals=0),
            dmc.Stack(
                [
                    dmc.Stack(
                        [
                            dmc.Text("Overall Rankings", className="page-title"),
                            dmc.Text(
                                "Elo is a rating system wherein unlike simple win/loss records, it accounts for the strength of the opponent — beating a top-ranked team earns far more points than beating a weaker one. It also considers match history going back decades, so a team's rating reflects long-term form, not just recent results. Every match updates both teams' ratings — the winner gains what the loser loses.",
                                c="#7A8099",
                                size="xl",
                                lh=1.6,
                                w="100%",
                            ),
                        ],
                        gap=4,
                        w="100%",
                    ),
                ]
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Box(
                                    dmc.Stack(
                                        [
                                            dmc.Text("RANK TREND", className="section-label", size="1rem"),
                                            dmc.Text(
                                                "The chart tracks how each team's global ranking shifts across tournament days. Higher-ranked teams are statistically stronger opponents, but Elo is a probability indicator — not a guarantee. Watch the day-by-day trend rather than a single snapshot to get a clearer picture of which teams are genuinely building momentum. Lines are colored by confederation. This chart prioritizes relative order among the 48 tracked teams; hence, a small global-rank gain or drop can still appear flat if a team does not overtake another team.",
                                                c="#7A8099",
                                            ),
                                        ],
                                        gap="md",
                                    ),
                                    style={"flex": "1 1 0", "minWidth": 0},
                                ),
                                dmc.Box(id="elo-ratings-meta", style={"flexShrink": 0, "marginLeft": "auto"}),
                            ],
                            justify="space-between",
                            align="start",
                            wrap="nowrap",
                        ),
                        _legend_badges(),
                        html.Div(id="elo-ratings-chart-region"),
                    ],
                    gap="md",
                )
            ),
        ],
        gap="md",
    )


@callback(
    Output("elo-ratings-chart-region", "children"),
    Output("elo-ratings-meta", "children"),
    Input("elo-ratings-refresh-interval", "n_intervals"),
)
def render_elo_ratings(_: int):
    snapshots = load_elo_snapshots()
    match_results = load_match_results()
    unique_scrapes = snapshots["scraped_at"].nunique() if not snapshots.empty else 0
    plotted_daily_snapshots = _daily_snapshots(snapshots, match_results=match_results) if not snapshots.empty else snapshots
    unique_days = plotted_daily_snapshots["snapshot_day"].nunique() if not plotted_daily_snapshots.empty else 0

    if unique_days < 2:
        return (
            _placeholder(
                "This view needs snapshots from at least two tournament days before the day-by-day movement becomes meaningful. "
                "The scheduler will fill this in automatically as new daily states land."
            ),
            dmc.Text(
                f"{unique_scrapes} raw snapshots across {unique_days} tournament day"
                f"{'' if unique_days == 1 else 's'}",
                c="#7A8099",
            ),
        )

    latest_scrape = snapshots["scraped_at"].max()
    latest_rows = snapshots[snapshots["scraped_at"] == latest_scrape].sort_values("rank")
    meta = dmc.Group(
        [
            dmc.Badge(f"{len(TARGET_TEAMS)} teams", variant="light", color="gray"),
            dmc.Badge(f"{unique_days} tournament day{'' if unique_days == 1 else 's'}", variant="light", color="gray"),
            dmc.Badge(
                ["Last refreshed: ", render_local_time(latest_scrape.isoformat(), format_style="datetime")],
                variant="light",
                color="gray",
            ),
            dmc.Badge(f"Current leader: {latest_rows.iloc[0]['team']}", variant="light", color="gray"), 
        ],
        gap="xs",
        wrap="wrap",
    )
    bump_data, axis_bottom = _nivo_bump_data(snapshots, match_results=match_results)
    chart = html.Div(
        dn.AreaBump(
            id="elo-nivo-bump-chart",
            data=bump_data,
            colors={"datum": "color"},
            blendMode="normal",
            spacing=10,
            startLabel="id",
            endLabel="id",
            axisTop=None,
            axisBottom=axis_bottom,
            margin={"top": 20, "right": 44, "bottom": 64, "left": 52},
        ),
        className="elo-nivo-chart",
        **{"data-team-code-map": json.dumps(TEAM_TO_FIFA_CODE)},
    )
    return chart, meta
