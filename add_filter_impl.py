from typing import Optional, Dict

import pyJianYingDraft as draft
from pyJianYingDraft import trange, Filter_type, exceptions
from create_draft import get_or_create_draft
from util import generate_draft_url


def add_filter_impl(
    filter_type: str,
    start: float = 0,
    end: float = 3.0,
    draft_id: Optional[str] = None,
    track_name: Optional[str] = "filter_01",
    intensity: float = 100.0,
    width: int = 1080,
    height: int = 1920
) -> Dict[str, str]:
    """
    Add a filter segment to its own filter track in the specified draft
    :param filter_type: Filter name (see get_filter_types); case, spaces and underscores are ignored
    :param start: Start time on the timeline (seconds), default 0
    :param end: End time on the timeline (seconds), default 3 seconds
    :param draft_id: Draft ID, if None or not found, a new draft will be created
    :param track_name: Filter track name, created if it does not exist yet
    :param intensity: Filter strength 0-100, default 100 (only used by filters that support it)
    :param width: Video width, default 1080
    :param height: Video height, default 1920
    :return: Updated draft information
    """
    if end <= start:
        raise ValueError(f"end ({end}) must be greater than start ({start})")

    try:
        filter_enum = Filter_type.from_name(filter_type)
    except ValueError:
        raise ValueError(f"Unknown filter type: {filter_type} (see get_filter_types)")

    draft_id, script = get_or_create_draft(draft_id=draft_id, width=width, height=height)

    # Add filter track (only when it doesn't exist yet)
    if track_name is not None:
        try:
            script.get_imported_track(draft.Track_type.filter, name=track_name)
        except exceptions.TrackNotFound:
            script.add_track(draft.Track_type.filter, track_name=track_name)
    else:
        script.add_track(draft.Track_type.filter)

    t_range = trange(f"{start}s", f"{end - start}s")
    script.add_filter(filter_enum, t_range, track_name=track_name, intensity=intensity)

    return {
        "draft_id": draft_id,
        "draft_url": generate_draft_url(draft_id)
    }
