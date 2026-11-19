from typing import Optional, Dict, List, Union

import pyJianYingDraft as draft
from pyJianYingDraft import exceptions
from draft_cache import DRAFT_CACHE
from util import generate_draft_url


def _parse_volume(value: Union[str, float, int]) -> str:
    """Validate a volume value ("80%", "0.8" or 0.8) and return it in the string form the track expects."""
    text = str(value).strip()
    try:
        number = float(text[:-1]) / 100 if text.endswith('%') else float(text)
    except ValueError:
        raise ValueError(f"Invalid volume value: {value} (use e.g. 0.8 or \"80%\")")
    if number < 0:
        raise ValueError(f"Volume must not be negative: {value}")
    return text


def add_audio_keyframe_impl(
    draft_id: str,
    track_name: str = "audio_main",
    time: float = 0.0,
    volume: Union[str, float] = 1.0,
    times: Optional[List[float]] = None,
    volumes: Optional[List[Union[str, float]]] = None
) -> Dict[str, str]:
    """
    Add volume keyframes to an audio track (e.g. duck music under a voice-over)
    :param draft_id: ID of an existing draft
    :param track_name: Audio track name, default "audio_main"
    :param time: Keyframe time on the timeline (seconds); the segment playing at that time gets the keyframe
    :param volume: Volume at that time: 1.0 / "100%" = original, 0.5 / "50%" = half, 0 = mute
    :param times: Batch mode: list of times (seconds); overrides time/volume
    :param volumes: Batch mode: list of volumes, same length as times
    :return: Updated draft information
    """
    if draft_id not in DRAFT_CACHE:
        raise ValueError(f"Draft {draft_id} not found; create it first")
    script = DRAFT_CACHE[draft_id]

    if times is not None or volumes is not None:
        if times is None or volumes is None or len(times) != len(volumes) or not times:
            raise ValueError("times and volumes must both be given, non-empty, and the same length")
        keyframes = list(zip(times, volumes))
    else:
        keyframes = [(time, volume)]

    try:
        track = script.get_track(draft.Audio_segment, track_name=track_name)
    except (exceptions.TrackNotFound, NameError, TypeError):
        raise ValueError(f"Audio track named {track_name} not found")
    if not track.segments:
        raise ValueError(f"No segments in audio track {track_name}")

    # Applied when the draft is saved, once real media durations are known
    for t, v in keyframes:
        track.add_pending_keyframe("volume", float(t), _parse_volume(v))

    return {
        "draft_id": draft_id,
        "draft_url": generate_draft_url(draft_id),
        "added_keyframes_count": len(keyframes)
    }
