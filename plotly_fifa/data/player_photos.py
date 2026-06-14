from __future__ import annotations

import os

PLAYER_PHOTO_REMOTE_PREFIX = os.environ.get(
    "PLAYER_PHOTO_REMOTE_PREFIX",
    "https://huggingface.co/datasets/deepa-shalini/fifa-player-images/resolve/main",
).rstrip("/")

# Most hosted images are JPGs; these player IDs are PNGs in the dataset.
PNG_PLAYER_IDS = {"114102", "16739", "191295", "61450", "76250"}


def get_player_photo_url(player_id: int | str | None) -> str | None:
    if player_id is None:
        return None

    normalized_id = str(player_id).strip()
    if not normalized_id:
        return None

    extension = "png" if normalized_id in PNG_PLAYER_IDS else "jpg"
    return f"{PLAYER_PHOTO_REMOTE_PREFIX}/{normalized_id}.{extension}"
