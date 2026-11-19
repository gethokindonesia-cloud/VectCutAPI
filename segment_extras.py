"""Per-clip extras shared by add_video and add_image: background color, filter and effect."""
import re
from typing import Optional, List

import pyJianYingDraft as draft
from pyJianYingDraft import Filter_type
from add_effect_impl import resolve_video_effect

_HEX_COLOR = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def normalize_rgba(color: str) -> str:
    """Turn '#RRGGBB' or '#RRGGBBAA' into the '#RRGGBBAA' form CapCut expects."""
    if not isinstance(color, str) or not _HEX_COLOR.match(color):
        raise ValueError(f"Invalid background_color {color!r}: use '#RRGGBB' or '#RRGGBBAA'")
    return (color if len(color) == 9 else color + "FF").upper()


def apply_segment_extras(
    segment: draft.Video_segment,
    background_blur_used: bool = False,
    background_color: Optional[str] = None,
    filter_type: Optional[str] = None,
    filter_intensity: float = 100.0,
    effect_type: Optional[str] = None,
    effect_category: str = "scene",
    effect_params: Optional[List[Optional[float]]] = None,
) -> None:
    """Apply the optional per-clip background color, filter and effect to a video/image segment."""
    if background_color:
        if background_blur_used:
            raise ValueError("Use either background_blur or background_color, not both")
        segment.add_background_filling("color", color=normalize_rgba(background_color))

    if filter_type:
        try:
            filter_enum = Filter_type.from_name(filter_type)
        except ValueError:
            raise ValueError(f"Unknown filter type: {filter_type} (see get_filter_types)")
        segment.add_filter(filter_enum, filter_intensity)

    if effect_type:
        effect_enum = resolve_video_effect(effect_type, effect_category)
        segment.add_effect(effect_enum, effect_params[::-1] if effect_params else None)
