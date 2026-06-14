# FIFA World Cup 2026 Dash App

Multi-page Dash application for a World Cup 2026 tracker built with `dash-mantine-components`, Plotly, and a cached football-data.org integration.

## Features

- Shared `AppShell` architecture with sidebar navigation and live ticker
- Five primary content views plus the live Match Centre
- Reusable pitch renderer for formations and team comparisons
- Cached football-data access with an optional explicit demo mode
- Player Spotlight flow with radar, scatter selection, and leaderboard
- Team Deep Dive, Group Standings, and Leaderboards analytics pages
- Match Centre replay mode for the latest finished match, with a dropdown for all past completed matches when no match is currently live

## Project Structure

```text
.
├── app.py
├── index.py
├── assets/
├── components/
├── data/
├── pages/
└── requirements.txt
```

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

3. Export your API key:

```bash
export FOOTBALL_DATA_API_KEY="your-key-here"
```

Optional: enable seeded demo content for local presentations only:

```bash
export APP_MODE="demo"
```

4. Run the app:

```bash
python3 app.py
```

Optional: force the app to read the bundled local prediction CSVs instead of the public GitHub copies:

```bash
export PLOTLY_FIFA_PREDICTIONS_SOURCE="local"
```

Without `FOOTBALL_DATA_API_KEY`, live match surfaces stay truthful and show empty or unavailable states instead of inventing a live fixture. Demo content is only used when `APP_MODE=demo`.

With a football-data.org plan that includes match details, the app uses the football-data feed directly for live scores, lineups, events, and match stats.

## Player Photos

Player photos are read directly from the Hugging Face dataset at `https://huggingface.co/datasets/deepa-shalini/fifa-player-images`.

The app builds each player photo URL from the player ID at runtime, using the hosted `.../resolve/main/...` path, so no local photo assets, prefetch script, or manifest file are required for the app to run.

## Predictions Data Pipeline

Predictions data is refreshed outside the Dash app:

- GitHub Actions runs [.github/workflows/scrape-elo-predictions.yml](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/.github/workflows/scrape-elo-predictions.yml:1) every 30 minutes and on manual dispatch.
- The workflow runs [scraper.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/scraper.py:1), which updates [elo_snapshots.csv](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/elo_snapshots.csv:1) and [match_results.csv](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/match_results.csv:1).
- The workflow commits those CSVs back to the repository only when the contents actually changed.
- The Dash app reads those CSVs from the public GitHub repo at runtime and caches each fetch server-side for 15 minutes.
- Prediction pages also use a 15-minute `dcc.Interval` so already-open tabs can repaint with fresher GitHub-backed data.

The runtime data source can be overridden with these environment variables:

- `PLOTLY_FIFA_PREDICTIONS_SOURCE`: `remote` by default, set to `local` to read the bundled CSVs.
- `PLOTLY_FIFA_PREDICTIONS_GITHUB_REPO`: overrides the default public GitHub repo slug used for raw CSV fetches.
- `PLOTLY_FIFA_PREDICTIONS_GITHUB_REF`: overrides the branch or tag used for raw CSV fetches.
- `PLOTLY_FIFA_PREDICTIONS_BASE_URL`: overrides the raw GitHub base URL entirely.
- `PLOTLY_FIFA_PREDICTIONS_CACHE_TTL_SECONDS`: server-side cache TTL for remote CSV fetches, default `900`.

## Notes

- All live API requests go through the cache layer in [data/cache.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/data/cache.py:1).
- By default, on-disk API cache files are stored in the system temp directory, not in the repo. Override with `PLOTLY_FIFA_CACHE_DIR` if needed.
- The reusable pitch component lives in [components/pitch.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/components/pitch.py:1).
- Global theming and the `AppShell` entry live in [app.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/app.py:1) and [index.py](/Users/deepa.shalini/Documents/GitHub/plotly_fifa/index.py:1).
