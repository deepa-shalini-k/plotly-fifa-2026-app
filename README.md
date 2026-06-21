# FIFA World Cup 2026 Dash App

A multi-page Dash application for following the FIFA World Cup 2026 with live match context, tournament analytics, and an Elo-driven prediction layer.

The app is built to feel useful on the move: it uses a responsive `AppShell`, collapsible mobile navigation, and browser-side local time conversion so kickoffs and live match context travel with the user instead of forcing manual timezone math.

## What The App Does

- Shows tournament KPIs that refresh throughout the competition: matches played, goals scored, goals per match, and live fixtures in progress.
- Surfaces live and upcoming fixtures in the viewer's local timezone.
- Renders full 11v11 formations on an interactive football pitch when lineups are available in the feed.
- Preserves past match formations and event timelines for completed matches through replay mode.
- Tracks goal-by-goal match events with scorer, minute, assist, cards, and substitutions.
- Provides team-level analysis across all 48 qualified nations, including squad age profile, latest lineup, goal timing splits, and match-result timeline.
- Builds player and team leaderboards for goals, assists, goal involvements, cards, and clean sheets.
- Adds an Elo intelligence layer anchored to the 11 June Elo baseline and refreshed from finished `football-data.org` World Cup matches, currently exposed as:
  - overall rating/rank movement across finished-match checkpoints
  - group-by-group Elo swings after captured World Cup results

## App Tour

### `Tournament Hub` (`/`)

The landing page is the tournament control room. It combines headline KPIs, upcoming fixtures, a selected group table, top scorers, a live-match snapshot, and a formation preview for the featured live match.

### `Match Centre` (`/live`)

The match centre prioritizes real live fixtures. When a match is in play, it renders the shared match-centre experience with:

- live score and status
- formation board
- event timeline
- multi-match live context when more than one fixture is active

When nothing is live, the page gracefully falls back to:

- kickoff-window messaging when a feed has not switched to live yet
- next-match and recent-result context cards
- replay mode for completed matches

### `Match Detail` (`/match/<match_id>`)

This route is the single-match deep link. Live matches auto-refresh every 30 seconds and can raise in-app goal notifications when a new event appears between refreshes.

### `Group Standings` (`/standings`)

This page supports two views:

- `All Groups`: a points-intensity overview of all 12 groups plus compact group cards
- `Group Detail`: a full table and matchday-by-matchday points progression chart for one group

### `Player Spotlight` (`/players`)

This page focuses on real tournament scorers and lets the user switch players from a dropdown or scatter plot. It combines:

- a profile card with remote player photo
- a radar chart versus tournament scorer averages
- a goals-vs-matches scatter distribution
- a Golden Boot race panel

### `Team Deep Dive` (`/teams`)

This page uses a world map selector to jump across qualified nations. For the selected team it shows:

- team identity and metadata
- latest available lineup on the pitch
- goals for / against / difference
- squad age distribution
- goals by time bracket
- World Cup results timeline

### `Leaderboards` (`/leaderboards`)

This page rotates between metrics such as goals, assists, goal involvements, yellow cards, red cards, and clean sheets. Clicking a bar routes the user directly into the relevant player or team page.

The goals-based views still read live scorer data, while the more expensive yellow-card, red-card, and clean-sheet metrics now use a persisted `leaderboards.json` snapshot with a live delta patch when newly completed matches exist beyond the latest committed snapshot.

### `Elo Intelligence`

Two prediction pages sit under the Elo section of the nav:

- `Overall Rankings` (`/predictions/elo-ratings`): checkpoint-by-checkpoint movement in global Elo ranking across the 48 qualified teams
- `Group Ratings` (`/predictions/group-ratings`): per-group dumbbell charts showing each team's Elo change before and after captured World Cup matches

The codebase does not currently render explicit win-probability, qualification-probability, or outright-winner pages. The Elo pipeline in this repo is the foundation for those kinds of forecast layers, but the shipped UI today focuses on ranking movement and match-by-match rating swings.

## Data Sources

- `football-data.org`: live fixtures, match details, standings, scorers, teams, player/person records, and the finished World Cup results used to recalculate Elo after every match
- `eloratings.net`: the original world Elo methodology and the frozen 11 June baseline table committed into `elo_snapshots.csv`
- Hugging Face dataset: player headshots served from `https://huggingface.co/datasets/deepa-shalini/fifa-player-images`

Relevant source links:

- `football-data.org`: `https://www.football-data.org/`
- `eloratings.net`: `https://eloratings.net/`

## Technical Overview

### 1. Live tournament data

The live app data layer lives in [data/api.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/data/api.py:1).

It uses the football-data.org v4 API for:

- competition matches
- standings
- scorers
- teams
- persons
- team match history

For match detail requests, the app sends unfolded headers such as `X-Unfold-Lineups`, `X-Unfold-Goals`, `X-Unfold-Bookings`, and `X-Unfold-Subs` so the response can power:

- live formations
- event timelines
- replay mode for completed matches
- team and leaderboard rollups based on completed match detail

All incoming payloads are normalized into a stable internal shape, including:

- flag emoji enrichment
- lineup and bench normalization
- player/team payload cleanup
- goal, booking, and substitution reshaping

### 2. Truthful empty states instead of fake live data

The repository still contains seeded sample data structures in `data/api.py`, but synthetic demo mode is intentionally disabled by `_demo_mode()`. In practice that means:

- without `FOOTBALL_DATA_API_KEY`, live football-data pages do not invent matches
- the UI shows loading, unavailable, or empty states where appropriate
- prediction pages can still work from the Elo CSV pipeline even if live API access is unavailable

### 3. Caching and resilience

[data/cache.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/data/cache.py:1) wraps HTTP requests with `diskcache` when available, and falls back to in-memory caching otherwise.

Current server-side cache TTLs:

- `live`: 30 seconds
- `today`: 120 seconds
- `standings`: 300 seconds
- `scorers`: 300 seconds
- `team` / `player`: 3600 seconds
- `historical`: 86400 seconds

If a fresh request fails and a stale copy exists, the app serves the stale payload rather than hard-failing immediately.

### 4. Local timezone rendering

Kickoff times are rendered server-side as UTC placeholders, then localized in the browser by [assets/local-time.js](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/assets/local-time.js:1).

That gives the app two advantages:

- every user sees times in their own local timezone automatically
- the UI can show a readable timezone abbreviation without storing user-specific server state

The Python helper for this lives in [components/local_time.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/components/local_time.py:1).

### 5. Pitch rendering

The formation board is drawn with Plotly in [components/pitch.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/components/pitch.py:1), using formation parsing utilities from [data/pitch_utils.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/data/pitch_utils.py:1).

It supports:

- home and away 11s on the same pitch
- shirt-number markers
- short-name labels
- formation labels
- empty-state messaging when lineups are missing

### 6. Remote player photos

Player photos are not bundled in the repo. [data/player_photos.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/data/player_photos.py:1) builds a direct URL at runtime from the player ID and points it at the Hugging Face dataset.

That means:

- no local image manifest is required
- no image download job is required
- the app stays lightweight while still showing real player avatars when available

`PNG_PLAYER_IDS` handles a small list of exceptions where the hosted asset is a `.png` instead of `.jpg`.

## Elo Predictions Pipeline

The prediction layer is driven by two tracked CSVs in the repo:

- [elo_snapshots.csv](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/elo_snapshots.csv:1)
- [match_results.csv](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/match_results.csv:1)

### How the Elo calculator works

[calculate_elo.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/calculate_elo.py:1) now rebuilds the Elo layer from `football-data.org` match results while keeping the committed 11 June Elo table as the tournament baseline.

It then:

1. loads the earliest complete 48-team snapshot from `elo_snapshots.csv` as the frozen tournament baseline
2. fetches finished World Cup matches from `football-data.org`
3. applies the World Football Elo formula in code after each completed match
4. writes one snapshot checkpoint per finished match for all 48 teams
5. writes one `match_results.csv` row per team per finished match
6. keeps the CSV contract stable so the Dash pages continue to load unchanged

The ranking model freezes non-World-Cup teams at their 11 June ratings, so every checkpoint shows how the tournament itself moved the qualified teams relative to that starting world table.

[build_leaderboards.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/build_leaderboards.py:1) performs the same kind of precomputation for the expensive leaderboard metrics by:

1. fetching the finished World Cup match list
2. fetching unfolded detail for each completed match
3. aggregating yellow cards, red cards, and clean sheets into `leaderboards.json`
4. keeping the page fast by letting the Dash app read that snapshot instead of rebuilding the full card/clean-sheet state from scratch on each page load

### Automated refresh

GitHub Actions runs [.github/workflows/run-elo-calculations.yml](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/.github/workflows/run-elo-calculations.yml:1) on:

- manual dispatch
- a 5-minute schedule (`7-59/5 * * * *`)

The workflow:

1. installs dependencies
2. runs `python calculate_elo.py`
3. runs `python build_leaderboards.py`
4. commits `elo_snapshots.csv`, `match_results.csv`, and `leaderboards.json` only if they changed

### Runtime behavior inside the Dash app

[data/predictions.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/data/predictions.py:1) reads the predictions CSVs either:

- from the public GitHub repository at runtime, or
- from bundled local files when explicitly configured

Remote CSV reads are cached in-process, and if the remote fetch fails the app falls back to:

- stale in-memory content if available
- bundled local CSV files if present

Prediction pages also use a 15-minute `dcc.Interval` so already-open tabs can repaint as fresh Elo data lands.

[data/leaderboard_snapshots.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/data/leaderboard_snapshots.py:1) reads `leaderboards.json` from the public GitHub repository at runtime by default, falls back to the bundled local file when needed, and only replays live football-data match detail for completed matches that were not yet included in the latest snapshot.

## Project Structure

```text
.
├── app.py                         # Dash app bootstrap and global theme
├── index.py                       # AppShell layout, header, navbar, ticker
├── assets/
│   ├── custom.css                # global styling and responsive shell behavior
│   ├── local-time.js             # client-side timezone localization
│   └── elo-chart-labels.js       # relabels Nivo bump-chart endpoints with FIFA codes
├── components/                    # reusable UI components
├── data/
│   ├── api.py                    # football-data integration and analytics helpers
│   ├── cache.py                  # request cache and stale-response fallback
│   ├── pitch_utils.py            # shared chart and formation utilities
│   ├── player_photos.py          # runtime player-photo URL builder
│   └── predictions.py            # Elo CSV loading and normalization
├── pages/
│   ├── tournament_hub.py
│   ├── match_centre.py
│   ├── match_detail.py
│   ├── group_standings.py
│   ├── player_spotlight.py
│   ├── team_deep_dive.py
│   ├── leaderboards.py
│   └── predictions/
│       ├── elo_ratings.py
│       └── group_ratings.py
├── calculate_elo.py               # Elo snapshot/result calculation job
├── build_leaderboards.py          # persisted yellow/red/clean-sheet snapshot job
├── elo_snapshots.csv              # persisted rating snapshots
├── leaderboards.json              # persisted expensive leaderboard metrics
├── match_results.csv              # persisted World Cup Elo result rows
└── requirements.txt
```

## Local Setup

### Prerequisites

- Python 3.12 is the safest target because the GitHub Actions workflow uses it
- a `football-data.org` API key if you want live tournament data in the Dash app

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### Configure

```bash
export FOOTBALL_DATA_API_KEY="your-key-here"
```

Optional environment variables:

```bash
export PLOTLY_FIFA_CACHE_DIR="/tmp/plotly_fifa_cache"
export PLAYER_PHOTO_REMOTE_PREFIX="https://huggingface.co/datasets/deepa-shalini/fifa-player-images/resolve/main"
export PLOTLY_FIFA_PREDICTIONS_SOURCE="remote"   # or "local"
export PLOTLY_FIFA_PREDICTIONS_GITHUB_REPO="deepa-shalini-k/plotly-fifa-2026-app"
export PLOTLY_FIFA_PREDICTIONS_GITHUB_REF="main"
export PLOTLY_FIFA_PREDICTIONS_BASE_URL=""
export PLOTLY_FIFA_PREDICTIONS_CACHE_TTL_SECONDS="900"
export PLOTLY_FIFA_PREDICTIONS_TIMEOUT_SECONDS="10"
export PLOTLY_FIFA_LEADERBOARDS_SOURCE="remote"  # or "local"; falls back to the predictions settings when omitted
```

### Run the app

```bash
python3 app.py
```

## Running The Elo Calculator Locally

To refresh the prediction CSVs on your machine:

```bash
python3 calculate_elo.py
python3 build_leaderboards.py
```

The Elo calculator forces `PLOTLY_FIFA_PREDICTIONS_SOURCE=local` for its own run so it always writes against local CSV files rather than round-tripping through the GitHub-hosted copies. The leaderboard builder writes `leaderboards.json` into the repo root so the Dash page can either read it locally or pick it up remotely from the committed repository.

## Important Notes

- Without `FOOTBALL_DATA_API_KEY`, prediction pages can still load, but football-data-powered pages will show truthful unavailable or empty states.
- Match lineups, goals, cards, and substitutions depend on your football-data plan supporting unfolded match detail.
- This repository does not currently include automated tests.
- The current README is intentionally aligned to the shipped code, not to aspirational future forecast pages.
