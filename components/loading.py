from __future__ import annotations

import dash_mantine_components as dmc


def build_loading_block(height: int | str = 320):
    return dmc.Box(
        dmc.Loader(color="green", size="xl"),
        style={
            "width": "100%",
            "minHeight": height,
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
        },
    )
