from dash import Dash

from index import create_layout

APP_TITLE = "FIFA World Cup 2026 — Live Stats Dashboard"
APP_DESCRIPTION = "Live scores, standings, player insights, and Elo projections for the 2026 FIFA World Cup."
APP_THUMBNAIL = "thumbnail.png"

THEME = {
    "colorScheme": "dark",
    "fontFamily": "DM Sans, Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif",
    "fontFamilyMonospace": "JetBrains Mono, monospace",
    "headings": {
        "fontFamily": "Barlow Condensed, sans-serif",
        "fontWeight": "700",
    },
    "primaryColor": "green",
    "colors": {
        "green": [
            "#e8faf2",
            "#c3f2de",
            "#9eeaca",
            "#79e2b6",
            "#54daa2",
            "#00D084",
            "#00b872",
            "#009e61",
            "#008450",
            "#006a3f",
        ]
    },
    "components": {
        "Paper": {"defaultProps": {"radius": "md", "p": "md", "withBorder": True}},
        "Badge": {"defaultProps": {"radius": "sm", "size": "sm"}},
        "Button": {"defaultProps": {"radius": "md"}},
        "Select": {"defaultProps": {"radius": "md"}},
        "Tabs": {
            "defaultProps": {
                "variant": "pills",
                "color": "green",
                "radius": "xl",
            }
        },
    },
}


def _build_index_string(thumbnail_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        <link rel="icon" type="image/png" href="{thumbnail_url}">
        <meta property="og:title" content="{APP_TITLE}">
        <meta property="og:description" content="{APP_DESCRIPTION}">
        <meta property="og:image" content="{thumbnail_url}">
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="{APP_TITLE}">
        <meta name="twitter:description" content="{APP_DESCRIPTION}">
        <meta name="twitter:image" content="{thumbnail_url}">
        {{%css%}}
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>"""


app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title=APP_TITLE,
)
app.index_string = _build_index_string(app.get_asset_url(APP_THUMBNAIL))
server = app.server
app.layout = create_layout(THEME)

if __name__ == "__main__":
    app.run(debug=True)
