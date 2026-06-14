from __future__ import annotations

import datetime as dt

from dash import html

LOCAL_TIME_CLASS = "local-time"
LOCAL_TIME_VALUE_CLASS = "local-time-value"
LOCAL_TIME_ZONE_CLASS = "local-time-zone"


def _parse_utc_iso(utc_iso: str | None) -> dt.datetime | None:
    if not utc_iso:
        return None

    try:
        return dt.datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _format_utc_parts(utc_iso: str, format_style: str) -> tuple[str, str]:
    dt_value = _parse_utc_iso(utc_iso)
    if dt_value is None:
        return "", ""

    if format_style == "time":
        return dt_value.strftime("%H:%M"), "UTC"
    if format_style == "date":
        return dt_value.strftime("%d %b %Y"), ""
    if format_style == "date_iso":
        return dt_value.strftime("%Y-%m-%d"), ""

    return dt_value.strftime("%d %b · %H:%M"), "UTC"


def render_local_time(
    utc_iso: str | None,
    *,
    format_style: str = "datetime",
    fallback: str = "TBD",
    show_timezone: bool = True,
    class_name: str | None = None,
):
    if not utc_iso:
        return fallback

    fallback_value, fallback_zone = _format_utc_parts(utc_iso, format_style)
    if not fallback_value:
        return fallback

    class_names = " ".join(part for part in [LOCAL_TIME_CLASS, class_name] if part)
    children = [html.Span(fallback_value, className=LOCAL_TIME_VALUE_CLASS)]
    if show_timezone and fallback_zone:
        children.append(html.Span(fallback_zone, className=LOCAL_TIME_ZONE_CLASS))

    return html.Time(
        children,
        dateTime=utc_iso,
        className=class_names,
        **{
            "data-utc-iso": utc_iso,
            "data-local-time-format": format_style,
            "data-local-time-show-timezone": str(show_timezone).lower(),
        },
    )
