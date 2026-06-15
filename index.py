import inspect

from dash import Input, Output, State, callback, dcc, html, page_container
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from components.navbar import build_navbar
from components.ticker import build_ticker
from data import api


def _build_header() -> dmc.AppShellHeader:
    initial_ticker = build_ticker(api.get_ticker_matches())
    return dmc.AppShellHeader(
        html.Div(
            [
                dmc.Burger(
                    id="shell-burger",
                    size="sm",
                    hiddenFrom="sm",
                    opened=False,
                    color="#E8EAF0",
                ),
                dmc.Box(initial_ticker, id="ticker-content", className="app-header-ticker"),
                html.Div(
                    [
                        dmc.Tooltip(
                            html.A(
                                html.Div(
                                    DashIconify(icon="mdi:github", width=50, color="#F5F7FA"),
                                    className="header-icon-badge header-icon-badge-plain",
                                ),
                                href="https://github.com/deepa-shalini-k/plotly-fifa-2026-app",
                                target="_blank",
                                rel="noopener noreferrer",
                                **{"aria-label": "Open GitHub repository"},
                            ),
                            label="View code on GitHub",
                            withArrow=True,
                        ),
                        dmc.Tooltip(
                            html.A(
                                html.Div(
                                    html.Img(
                                        src="/assets/Deepa_Shalini_Profile_Photo.jpg",
                                        alt="Deepa Shalini profile photo",
                                        className="header-profile-image",
                                    ),
                                    className="header-profile-frame",
                                ),
                                href="https://deepa-shalini-k.github.io/",
                                target="_blank",
                                rel="noopener noreferrer",
                                **{"aria-label": "Open Deepa Shalini website"},
                            ),
                            label="Created by Deepa Shalini K",
                            withArrow=True,
                        ),
                    ],
                    className="app-header-actions",
                ),
            ],
            className="app-header-inner",
        ),
        className="app-header",
    )


def _mantine_provider_kwargs(theme: dict) -> dict:
    provider_params = inspect.signature(dmc.MantineProvider).parameters
    kwargs = {"theme": theme}

    if "forceColorScheme" in provider_params:
        kwargs["forceColorScheme"] = "dark"
    elif "defaultColorScheme" in provider_params:
        kwargs["defaultColorScheme"] = "dark"

    if "withGlobalStyles" in provider_params:
        kwargs["withGlobalStyles"] = True
    if "withNormalizeCSS" in provider_params:
        kwargs["withNormalizeCSS"] = True
    if "withGlobalClasses" in provider_params:
        kwargs["withGlobalClasses"] = True
    if "withCssVariables" in provider_params:
        kwargs["withCssVariables"] = True

    return kwargs


def create_layout(theme: dict) -> dmc.MantineProvider:
    initial_live_matches = api.get_live_matches()
    return dmc.MantineProvider(
        [
            dcc.Location(id="shell-location"),
            dcc.Interval(id="ticker-interval", interval=60_000, n_intervals=0),
            dmc.AppShell(
                [
                    _build_header(),
                    dmc.AppShellNavbar(
                        build_navbar("/", initial_live_matches),
                        id="app-navbar",
                        p=0,
                        className="app-navbar",
                    ),
                    dmc.AppShellMain(
                        dmc.Box(
                            [
                                dmc.Box(id="notification-region", className="notification-region"),
                                dmc.Box(page_container, className="page-shell"),
                            ],
                            className="page-shell-wrapper",
                        )
                    ),
                ],
                id="wc-app-shell",
                header={"height": 58},
                navbar={
                    "width": {"base": 220},
                    "breakpoint": "sm",
                    "collapsed": {"mobile": True},
                },
                padding=0,
            ),
        ],
        **_mantine_provider_kwargs(theme),
    )


@callback(
    Output("wc-app-shell", "navbar"),
    Input("shell-burger", "opened"),
    State("wc-app-shell", "navbar"),
)
def toggle_navbar(opened: bool, navbar: dict) -> dict:
    navbar = dict(navbar or {})
    navbar["collapsed"] = {"mobile": not opened}
    return navbar


@callback(
    Output("shell-burger", "opened"),
    Input("shell-location", "pathname"),
    prevent_initial_call=True,
)
def close_navbar_on_route_change(_: str) -> bool:
    return False


@callback(
    Output("app-navbar", "children"),
    Output("ticker-content", "children"),
    Input("shell-location", "pathname"),
    Input("ticker-interval", "n_intervals"),
)
def refresh_shell(pathname: str, _: int):
    live_matches = api.get_live_matches()
    ticker_matches = api.get_ticker_matches()
    return build_navbar(pathname or "/", live_matches), build_ticker(ticker_matches)
