from dash import Dash

from index import create_layout

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

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="FIFA World Cup 2026 — Live Stats Dashboard",
)
server = app.server
app.layout = create_layout(THEME)

if __name__ == "__main__":
    app.run(debug=True)
