from __future__ import annotations


def live_minute_label(match: dict, pad_numeric: bool = False) -> str | None:
    minute = match.get("minute")
    if minute is None or isinstance(minute, bool):
        return None

    if isinstance(minute, str):
        minute_text = minute.strip()
        if not minute_text:
            return None
        if minute_text.endswith("'"):
            return minute_text
        if minute_text.isdigit():
            minute_value = int(minute_text)
            return f"{minute_value:02d}'" if pad_numeric else f"{minute_value}'"
        return f"{minute_text}'"

    try:
        minute_value = int(minute)
    except (TypeError, ValueError):
        return None

    return f"{minute_value:02d}'" if pad_numeric else f"{minute_value}'"


def match_venue_label(match: dict, fallback: str = "Venue TBC") -> str:
    venue = match.get("venue")
    if venue is None:
        return fallback

    venue_text = str(venue).strip()
    return venue_text or fallback


def match_context_label(match: dict) -> str:
    group_value = match.get("group")
    group_label = str(group_value).replace("_", " ").strip() if group_value else ""
    venue_label = match_venue_label(match)
    return f"{group_label} · {venue_label}" if group_label else venue_label
