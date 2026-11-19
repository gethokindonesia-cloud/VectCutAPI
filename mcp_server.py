#!/usr/bin/env python3
"""
CapCut API MCP Server (Complete Version)

完整版本的MCP服务器，集成所有CapCut API接口
"""

import sys
import os
import json
import traceback
import io
import contextlib
from typing import Any, Dict, List, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入CapCut API功能
try:
    from create_draft import get_or_create_draft
    from add_text_impl import add_text_impl
    from add_video_track import add_video_track
    from add_audio_track import add_audio_track
    from add_image_impl import add_image_impl
    from add_subtitle_impl import add_subtitle_impl
    from add_effect_impl import add_effect_impl
    from add_sticker_impl import add_sticker_impl
    from add_filter_impl import add_filter_impl
    from add_video_keyframe_impl import add_video_keyframe_impl
    from get_duration_impl import get_video_duration
    from save_draft_impl import save_draft_impl
    from pyJianYingDraft.text_segment import TextStyleRange
    CAPCUT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import CapCut modules: {e}", file=sys.stderr)
    CAPCUT_AVAILABLE = False

# 完整的工具定义
TOOLS = [
    {
        "name": "create_draft",
        "description": "创建新的CapCut草稿",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "default": 1080, "description": "视频宽度"},
                "height": {"type": "integer", "default": 1920, "description": "视频高度"}
            }
        }
    },
    {
        "name": "add_video",
        "description": "添加视频到草稿，支持转场、蒙版、背景模糊等效果",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_url": {"type": "string", "description": "视频URL"},
                "draft_id": {"type": "string", "description": "草稿ID"},
                "start": {"type": "number", "default": 0, "description": "开始时间（秒）"},
                "end": {"type": "number", "description": "结束时间（秒）"},
                "target_start": {"type": "number", "default": 0, "description": "目标开始时间（秒）"},
                "width": {"type": "integer", "default": 1080, "description": "视频宽度"},
                "height": {"type": "integer", "default": 1920, "description": "视频高度"},
                "transform_x": {"type": "number", "default": 0, "description": "X轴位置"},
                "transform_y": {"type": "number", "default": 0, "description": "Y轴位置"},
                "scale_x": {"type": "number", "default": 1, "description": "X轴缩放"},
                "scale_y": {"type": "number", "default": 1, "description": "Y轴缩放"},
                "speed": {"type": "number", "default": 1.0, "description": "播放速度"},
                "track_name": {"type": "string", "default": "main", "description": "轨道名称"},
                "volume": {"type": "number", "default": 1.0, "description": "音量"},
                "transition": {"type": "string", "description": "转场类型"},
                "transition_duration": {"type": "number", "default": 0.5, "description": "转场时长"},
                "mask_type": {"type": "string", "description": "蒙版类型"},
                "mask_center_x": {"type": "number", "default": 0.5, "description": "Mask center X (0-1)"},
                "mask_center_y": {"type": "number", "default": 0.5, "description": "Mask center Y (0-1)"},
                "mask_size": {"type": "number", "default": 1.0, "description": "Mask size (0-1)"},
                "mask_rotation": {"type": "number", "default": 0.0, "description": "Mask rotation (degrees)"},
                "mask_feather": {"type": "number", "default": 0.0, "description": "Mask feather (0-1)"},
                "mask_invert": {"type": "boolean", "default": False, "description": "Invert the mask"},
                "mask_rect_width": {"type": "number", "description": "Rectangle mask width as a proportion of material width (rectangle mask only)"},
                "mask_round_corner": {"type": "number", "description": "Rectangle mask corner rounding, 0-100 (rectangle mask only)"},
                "background_blur": {"type": "integer", "description": "背景模糊级别(1-4)"},
                "relative_index": {"type": "integer", "default": 0, "description": "Track rendering order index"},
                "duration": {"type": "number", "description": "Known source duration in seconds (skips duration detection)"},
                "draft_folder": {"type": "string", "description": "Draft folder path (optional)"}
            },
            "required": ["video_url"]
        }
    },
    {
        "name": "add_audio",
        "description": "添加音频到草稿，支持音效处理",
        "inputSchema": {
            "type": "object",
            "properties": {
                "audio_url": {"type": "string", "description": "音频URL"},
                "draft_id": {"type": "string", "description": "草稿ID"},
                "start": {"type": "number", "default": 0, "description": "开始时间（秒）"},
                "end": {"type": "number", "description": "结束时间（秒）"},
                "target_start": {"type": "number", "default": 0, "description": "目标开始时间（秒）"},
                "volume": {"type": "number", "default": 1.0, "description": "音量"},
                "speed": {"type": "number", "default": 1.0, "description": "播放速度"},
                "track_name": {"type": "string", "default": "audio_main", "description": "轨道名称"},
                "effect_type": {"type": "string", "description": "Audio effect name (see get_audio_effect_types)"},
                "effect_params": {"type": "array", "items": {"type": ["number", "null"]}, "description": "Parameter values for effect_type, in the order listed by get_audio_effect_types"},
                "sound_effects": {"type": "array", "description": "Several audio effects: list of [effect_name, [params...]] pairs"},
                "duration": {"type": "number", "description": "Known source duration in seconds (skips duration detection)"},
                "draft_folder": {"type": "string", "description": "Draft folder path (optional)"},
                "width": {"type": "integer", "default": 1080, "description": "视频宽度"},
                "height": {"type": "integer", "default": 1920, "description": "视频高度"}
            },
            "required": ["audio_url"]
        }
    },
    {
        "name": "add_image",
        "description": "添加图片到草稿，支持动画、转场、蒙版等效果",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "图片URL"},
                "draft_id": {"type": "string", "description": "草稿ID"},
                "start": {"type": "number", "default": 0, "description": "开始时间（秒）"},
                "end": {"type": "number", "default": 3.0, "description": "结束时间（秒）"},
                "width": {"type": "integer", "default": 1080, "description": "视频宽度"},
                "height": {"type": "integer", "default": 1920, "description": "视频高度"},
                "transform_x": {"type": "number", "default": 0, "description": "X轴位置"},
                "transform_y": {"type": "number", "default": 0, "description": "Y轴位置"},
                "scale_x": {"type": "number", "default": 1, "description": "X轴缩放"},
                "scale_y": {"type": "number", "default": 1, "description": "Y轴缩放"},
                "track_name": {"type": "string", "default": "main", "description": "轨道名称"},
                "intro_animation": {"type": "string", "description": "入场动画"},
                "intro_animation_duration": {"type": "number", "default": 0.5, "description": "Intro animation duration (seconds)"},
                "outro_animation": {"type": "string", "description": "出场动画"},
                "outro_animation_duration": {"type": "number", "default": 0.5, "description": "Outro animation duration (seconds)"},
                "combo_animation": {"type": "string", "description": "Combo animation (see get_combo_animation_types)"},
                "combo_animation_duration": {"type": "number", "default": 0.5, "description": "Combo animation duration (seconds)"},
                "animation": {"type": "string", "description": "Legacy intro animation name (intro_animation takes priority)"},
                "animation_duration": {"type": "number", "default": 0.5, "description": "Legacy intro animation duration (seconds)"},
                "transition": {"type": "string", "description": "转场类型"},
                "transition_duration": {"type": "number", "default": 0.5, "description": "Transition duration (seconds)"},
                "mask_type": {"type": "string", "description": "蒙版类型"},
                "mask_center_x": {"type": "number", "default": 0.0, "description": "Mask center X (material pixels; 0 = center)"},
                "mask_center_y": {"type": "number", "default": 0.0, "description": "Mask center Y (material pixels; 0 = center)"},
                "mask_size": {"type": "number", "default": 0.5, "description": "Mask size as a proportion of material height"},
                "mask_rotation": {"type": "number", "default": 0.0, "description": "Mask rotation (degrees, clockwise)"},
                "mask_feather": {"type": "number", "default": 0.0, "description": "Mask feather, 0-100"},
                "mask_invert": {"type": "boolean", "default": False, "description": "Invert the mask"},
                "mask_rect_width": {"type": "number", "description": "Rectangle mask width as a proportion of material width (rectangle mask only)"},
                "mask_round_corner": {"type": "number", "description": "Rectangle mask corner rounding, 0-100 (rectangle mask only)"},
                "background_blur": {"type": "integer", "description": "Background blur level 1-4"},
                "relative_index": {"type": "integer", "default": 0, "description": "Track rendering order index"},
                "draft_folder": {"type": "string", "description": "Draft folder path (optional)"}
            },
            "required": ["image_url"]
        }
    },
    {
        "name": "add_text",
        "description": "添加文本到草稿，支持文本多样式、文字阴影和文字背景",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "文本内容"},
                "start": {"type": "number", "description": "开始时间（秒）"},
                "end": {"type": "number", "description": "结束时间（秒）"},
                "draft_id": {"type": "string", "description": "草稿ID"},
                "track_name": {"type": "string", "default": "text_main", "description": "Track name"},
                "transform_x": {"type": "number", "default": 0, "description": "X position"},
                "transform_y": {"type": "number", "default": -0.8, "description": "Y position (-0.8 = near bottom)"},
                "width": {"type": "integer", "default": 1080, "description": "Canvas width"},
                "height": {"type": "integer", "default": 1920, "description": "Canvas height"},
                "font": {"type": "string", "description": "Font name (see get_font_types)"},
                "font_color": {"type": "string", "default": "#ffffff", "description": "字体颜色"},
                "font_size": {"type": "number", "default": 8.0, "description": "字体大小"},
                "font_alpha": {"type": "number", "default": 1.0, "description": "Text opacity (0-1)"},
                "bold": {"type": "boolean", "default": False, "description": "Bold"},
                "italic": {"type": "boolean", "default": False, "description": "Italic"},
                "underline": {"type": "boolean", "default": False, "description": "Underline"},
                "vertical": {"type": "boolean", "default": False, "description": "Vertical text"},
                "align": {"type": "integer", "enum": [0, 1, 2], "default": 1, "description": "Alignment: 0 left, 1 center, 2 right"},
                "line_spacing": {"type": "number", "default": 0.25, "description": "Line spacing"},
                "letter_spacing": {"type": "number", "default": 0.0, "description": "Letter spacing"},
                "fixed_width": {"type": "number", "default": -1, "description": "Fixed text box width ratio 0-1 (-1 = auto)"},
                "fixed_height": {"type": "number", "default": -1, "description": "Fixed text box height ratio 0-1 (-1 = auto)"},
                "border_color": {"type": "string", "default": "#000000", "description": "Outline color"},
                "border_width": {"type": "number", "default": 0.0, "description": "Outline width (0 = none)"},
                "border_alpha": {"type": "number", "default": 1.0, "description": "Outline opacity (0-1)"},
                "shadow_enabled": {"type": "boolean", "default": False, "description": "是否启用文字阴影"},
                "shadow_color": {"type": "string", "default": "#000000", "description": "阴影颜色"},
                "shadow_alpha": {"type": "number", "default": 0.9, "description": "阴影透明度"},
                "shadow_angle": {"type": "number", "default": -45.0, "description": "阴影角度"},
                "shadow_distance": {"type": "number", "default": 5.0, "description": "阴影距离"},
                "shadow_smoothing": {"type": "number", "default": 0.15, "description": "阴影平滑度"},
                "background_color": {"type": "string", "default": "#000000", "description": "背景颜色"},
                "background_alpha": {"type": "number", "default": 0.0, "description": "背景透明度 (0 = no background)"},
                "background_style": {"type": "integer", "default": 1, "description": "背景样式"},
                "background_round_radius": {"type": "number", "default": 0.0, "description": "背景圆角半径"},
                "background_width": {"type": "number", "default": 0.14, "description": "Background width"},
                "background_height": {"type": "number", "default": 0.14, "description": "Background height"},
                "background_horizontal_offset": {"type": "number", "default": 0.5, "description": "Background horizontal offset (0-1)"},
                "background_vertical_offset": {"type": "number", "default": 0.5, "description": "Background vertical offset (0-1)"},
                "intro_animation": {"type": "string", "description": "Text intro animation (see get_text_intro_types)"},
                "intro_duration": {"type": "number", "default": 0.5, "description": "Intro animation duration (seconds)"},
                "outro_animation": {"type": "string", "description": "Text outro animation (see get_text_outro_types)"},
                "outro_duration": {"type": "number", "default": 0.5, "description": "Outro animation duration (seconds)"},
                "loop_animation": {"type": "string", "description": "Text loop animation (see get_text_loop_anim_types); fills the time between intro and outro"},
                "bubble_effect_id": {"type": "string", "description": "Text bubble effect ID (needs bubble_resource_id)"},
                "bubble_resource_id": {"type": "string", "description": "Text bubble resource ID (needs bubble_effect_id)"},
                "effect_effect_id": {"type": "string", "description": "Text effect (flower word) ID"},
                "text_styles": {"type": "array", "description": "文本多样式配置列表"}
            },
            "required": ["text", "start", "end"]
        }
    },
    {
        "name": "add_subtitle",
        "description": "添加字幕到草稿，支持SRT文件和样式设置",
        "inputSchema": {
            "type": "object",
            "properties": {
                "srt_path": {"type": "string", "description": "SRT字幕文件路径或URL"},
                "draft_id": {"type": "string", "description": "草稿ID"},
                "track_name": {"type": "string", "default": "subtitle", "description": "轨道名称"},
                "time_offset": {"type": "number", "default": 0, "description": "时间偏移（秒）"},
                "font": {"type": "string", "description": "字体"},
                "font_size": {"type": "number", "default": 8.0, "description": "字体大小"},
                "font_color": {"type": "string", "default": "#FFFFFF", "description": "字体颜色"},
                "bold": {"type": "boolean", "default": False, "description": "是否粗体"},
                "italic": {"type": "boolean", "default": False, "description": "是否斜体"},
                "underline": {"type": "boolean", "default": False, "description": "是否下划线"},
                "border_width": {"type": "number", "default": 0.0, "description": "边框宽度"},
                "border_color": {"type": "string", "default": "#000000", "description": "边框颜色"},
                "border_alpha": {"type": "number", "default": 1.0, "description": "Outline opacity (0-1)"},
                "background_color": {"type": "string", "default": "#000000", "description": "背景颜色"},
                "background_alpha": {"type": "number", "default": 0.0, "description": "背景透明度"},
                "background_style": {"type": "integer", "default": 1, "description": "Background style"},
                "bubble_effect_id": {"type": "string", "description": "Text bubble effect ID (needs bubble_resource_id)"},
                "bubble_resource_id": {"type": "string", "description": "Text bubble resource ID (needs bubble_effect_id)"},
                "effect_effect_id": {"type": "string", "description": "Text effect (flower word) ID"},
                "transform_x": {"type": "number", "default": 0.0, "description": "X轴位置"},
                "transform_y": {"type": "number", "default": -0.8, "description": "Y轴位置"},
                "scale_x": {"type": "number", "default": 1.0, "description": "X scale"},
                "scale_y": {"type": "number", "default": 1.0, "description": "Y scale"},
                "rotation": {"type": "number", "default": 0.0, "description": "Rotation (degrees)"},
                "alpha": {"type": "number", "default": 0.4, "description": "Subtitle opacity (0-1)"},
                "vertical": {"type": "boolean", "default": True, "description": "Vertical text"},
                "width": {"type": "integer", "default": 1080, "description": "视频宽度"},
                "height": {"type": "integer", "default": 1920, "description": "视频高度"}
            },
            "required": ["srt_path"]
        }
    },
    {
        "name": "add_effect",
        "description": "添加特效到草稿",
        "inputSchema": {
            "type": "object",
            "properties": {
                "effect_type": {"type": "string", "description": "特效类型名称"},
                "effect_category": {"type": "string", "enum": ["scene", "character"], "default": "scene", "description": "Effect category the effect_type is looked up in"},
                "draft_id": {"type": "string", "description": "草稿ID"},
                "start": {"type": "number", "default": 0, "description": "开始时间（秒）"},
                "end": {"type": "number", "default": 3.0, "description": "结束时间（秒）"},
                "track_name": {"type": "string", "default": "effect_01", "description": "轨道名称"},
                "params": {"type": "array", "description": "特效参数列表"},
                "width": {"type": "integer", "default": 1080, "description": "视频宽度"},
                "height": {"type": "integer", "default": 1920, "description": "视频高度"}
            },
            "required": ["effect_type"]
        }
    },
    {
        "name": "add_filter",
        "description": "Add a color filter over a time range on its own filter track",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter_type": {"type": "string", "description": "Filter name (see get_filter_types); case, spaces and underscores are ignored"},
                "draft_id": {"type": "string", "description": "Draft ID"},
                "start": {"type": "number", "default": 0, "description": "Start time on the timeline (seconds)"},
                "end": {"type": "number", "default": 3.0, "description": "End time on the timeline (seconds)"},
                "intensity": {"type": "number", "default": 100.0, "description": "Filter strength 0-100 (only for filters marked adjustable)"},
                "track_name": {"type": "string", "default": "filter_01", "description": "Filter track name"},
                "width": {"type": "integer", "default": 1080, "description": "Canvas width"},
                "height": {"type": "integer", "default": 1920, "description": "Canvas height"}
            },
            "required": ["filter_type"]
        }
    },
    {
        "name": "add_sticker",
        "description": "添加贴纸到草稿",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "贴纸资源ID"},
                "draft_id": {"type": "string", "description": "草稿ID"},
                "start": {"type": "number", "description": "开始时间（秒）"},
                "end": {"type": "number", "description": "结束时间（秒）"},
                "transform_x": {"type": "number", "default": 0, "description": "X轴位置"},
                "transform_y": {"type": "number", "default": 0, "description": "Y轴位置"},
                "scale_x": {"type": "number", "default": 1.0, "description": "X轴缩放"},
                "scale_y": {"type": "number", "default": 1.0, "description": "Y轴缩放"},
                "alpha": {"type": "number", "default": 1.0, "description": "透明度"},
                "rotation": {"type": "number", "default": 0.0, "description": "旋转角度"},
                "flip_horizontal": {"type": "boolean", "default": False, "description": "Mirror horizontally"},
                "flip_vertical": {"type": "boolean", "default": False, "description": "Mirror vertically"},
                "relative_index": {"type": "integer", "default": 0, "description": "Track rendering order index"},
                "track_name": {"type": "string", "default": "sticker_main", "description": "轨道名称"},
                "width": {"type": "integer", "default": 1080, "description": "视频宽度"},
                "height": {"type": "integer", "default": 1920, "description": "视频高度"}
            },
            "required": ["resource_id", "start", "end"]
        }
    },
    {
        "name": "add_video_keyframe",
        "description": "添加视频关键帧，支持位置、缩放、旋转、透明度等属性动画",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "草稿ID"},
                "track_name": {"type": "string", "default": "main", "description": "轨道名称"},
                "property_type": {"type": "string", "description": "关键帧属性类型(position_x, position_y, rotation, scale_x, scale_y, uniform_scale, alpha, saturation, contrast, brightness, volume)"},
                "time": {"type": "number", "default": 0.0, "description": "关键帧时间点（秒）"},
                "value": {"type": "string", "description": "关键帧值"},
                "property_types": {"type": "array", "description": "批量模式：关键帧属性类型列表"},
                "times": {"type": "array", "description": "批量模式：关键帧时间点列表"},
                "values": {"type": "array", "description": "批量模式：关键帧值列表"}
            }
        }
    },
    {
        "name": "get_video_duration",
        "description": "获取视频时长",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_url": {"type": "string", "description": "视频URL"}
            },
            "required": ["video_url"]
        }
    },
    {
        "name": "save_draft",
        "description": "保存草稿",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "草稿ID"},
                "project_name": {"type": "string", "description": "Project name shown in CapCut; also triggers deploy into CapCut's drafts folder"},
                "draft_folder": {"type": "string", "description": "Folder to generate the draft in (default: the repo directory)"},
                "auto_deploy": {"type": "boolean", "description": "Copy the draft into CapCut's drafts folder (default true)"}
            },
            "required": ["draft_id"]
        }
    }
]

# ---------------------------------------------------------------------------
# Extra tools that proxy to the Flask routes in capcut_server.py
# (called in-process via Flask's test client; no HTTP server needed)
# ---------------------------------------------------------------------------

_LIST_FILTER_PROPS = {
    "search": {"type": "string", "description": "Only return names containing this text (case-insensitive)"},
    "limit": {"type": "integer", "description": "Maximum number of items to return (default: all)"}
}

# tool name -> (route, http method, description)
_TYPE_LIST_TOOLS = {
    "get_intro_animation_types": ("/get_intro_animation_types", "List valid intro (entrance) animation names for video/image (use in add_image intro_animation)"),
    "get_outro_animation_types": ("/get_outro_animation_types", "List valid outro (exit) animation names for video/image (use in add_image outro_animation)"),
    "get_combo_animation_types": ("/get_combo_animation_types", "List valid combo (group) animation names for video/image"),
    "get_transition_types": ("/get_transition_types", "List valid transition names (use in add_video/add_image transition)"),
    "get_mask_types": ("/get_mask_types", "List valid mask names (use in add_video/add_image mask_type)"),
    "get_audio_effect_types": ("/get_audio_effect_types", "List valid audio effect names with their parameters"),
    "get_font_types": ("/get_font_types", "List valid font names (use in add_text/add_subtitle font)"),
    "get_text_intro_types": ("/get_text_intro_types", "List valid text intro animation names"),
    "get_text_outro_types": ("/get_text_outro_types", "List valid text outro animation names"),
    "get_text_loop_anim_types": ("/get_text_loop_anim_types", "List valid text loop animation names (use in add_text loop_animation)"),
    "get_filter_types": ("/get_filter_types", "List valid filter names (use in add_filter filter_type); adjustable=true means intensity has an effect"),
    "get_video_scene_effect_types": ("/get_video_scene_effect_types", "List valid scene effect names (use in add_effect with effect_category='scene')"),
    "get_video_character_effect_types": ("/get_video_character_effect_types", "List valid character effect names (use in add_effect with effect_category='character')"),
}

for _name, (_route, _desc) in _TYPE_LIST_TOOLS.items():
    TOOLS.append({
        "name": _name,
        "description": _desc,
        "inputSchema": {"type": "object", "properties": dict(_LIST_FILTER_PROPS)}
    })

TOOLS.extend([
    {
        "name": "query_script",
        "description": "Return the full JSON content of a draft (tracks, segments, materials, timing)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID"},
                "force_update": {"type": "boolean", "default": True, "description": "Recompute the script before returning it"}
            },
            "required": ["draft_id"]
        }
    },
    {
        "name": "query_draft_status",
        "description": "Check the status of a draft save task",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID (usually the draft ID)"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "generate_draft_url",
        "description": "Generate a preview/download URL for a draft",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "Draft ID"},
                "draft_folder": {"type": "string", "description": "Draft folder (optional)"}
            },
            "required": ["draft_id"]
        }
    },
    {
        "name": "list_projects",
        "description": "List projects in the local CapCut desktop drafts folder, newest first",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "read_project",
        "description": "Read a summary (duration, fps, canvas, tracks, materials) of an existing CapCut desktop project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project folder name (from list_projects) or absolute path"}
            },
            "required": ["project_name"]
        }
    },
    {
        "name": "reload_desktop",
        "description": "Ask CapCut desktop to reload so newly saved drafts appear",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project to open after reload (optional)"}
            }
        }
    },
])

# tool name -> (route, http method)
_ROUTE_TOOLS = {name: (route, "GET") for name, (route, _d) in _TYPE_LIST_TOOLS.items()}
_ROUTE_TOOLS.update({
    "query_script": ("/query_script", "POST"),
    "query_draft_status": ("/query_draft_status", "POST"),
    "generate_draft_url": ("/generate_draft_url", "POST"),
    "list_projects": ("/list_projects", "GET"),
    "read_project": ("/read_project", "POST"),
    "reload_desktop": ("/reload_desktop", "POST"),
})

_flask_client = None

def _call_route(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call a capcut_server.py Flask route in-process and return its output."""
    global _flask_client
    if _flask_client is None:
        from capcut_server import app as flask_app  # lazy: heavy import
        _flask_client = flask_app.test_client()

    route, method = _ROUTE_TOOLS[tool_name]
    args = dict(arguments)
    search = args.pop("search", None)
    limit = args.pop("limit", None)

    if method == "GET":
        resp = _flask_client.get(route)
    else:
        resp = _flask_client.post(route, json=args)
    data = resp.get_json(silent=True)
    if data is None:
        raise RuntimeError(f"{route} returned HTTP {resp.status_code} with non-JSON body")
    if not data.get("success", False):
        raise RuntimeError(data.get("error") or f"{route} failed")

    output = data.get("output")
    if tool_name == "query_script" and isinstance(output, str):
        try:
            output = json.loads(output)
        except ValueError:
            pass
    if isinstance(output, list):
        if search:
            needle = search.lower()
            output = [o for o in output
                      if needle in str(o.get("name", o) if isinstance(o, dict) else o).lower()]
        total = len(output)
        if limit:
            output = output[:int(limit)]
        return {"total": total, "returned": len(output), "items": output}
    return output

@contextlib.contextmanager
def capture_stdout():
    """捕获标准输出，防止CapCut API的调试信息干扰JSON响应"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield sys.stdout
    finally:
        sys.stdout = old_stdout

def convert_text_styles(text_styles_data):
    """将字典格式的text_styles转换为TextStyleRange对象列表"""
    if not text_styles_data:
        return None
    
    try:
        text_style_ranges = []
        for style_dict in text_styles_data:
            style_range = TextStyleRange(
                start=style_dict.get("start", 0),
                end=style_dict.get("end", 0),
                font_size=style_dict.get("font_size"),
                font_color=style_dict.get("font_color"),
                bold=style_dict.get("bold", False),
                italic=style_dict.get("italic", False),
                underline=style_dict.get("underline", False)
            )
            text_style_ranges.append(style_range)
        return text_style_ranges
    except Exception as e:
        print(f"[ERROR] Error converting text_styles: {e}", file=sys.stderr)
        return None

def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """执行具体的工具"""
    try:
        print(f"[DEBUG] Executing tool: {tool_name} with args: {arguments}", file=sys.stderr)
        
        if not CAPCUT_AVAILABLE:
            return {"success": False, "error": "CapCut modules not available"}
        
        # 捕获标准输出，防止调试信息干扰
        with capture_stdout() as captured:
            if tool_name == "create_draft":
                draft_id, script = get_or_create_draft(
                    width=arguments.get("width", 1080),
                    height=arguments.get("height", 1920)
                )
                result = {
                    "draft_id": str(draft_id),
                    "draft_url": f"https://www.install-ai-guider.top/draft/downloader?draft_id={draft_id}"
                }
                
            elif tool_name == "add_video":
                result = add_video_track(**arguments)
                
            elif tool_name == "add_audio":
                # Same shortcut as the /add_audio route: effect_type + effect_params -> sound_effects
                effect_type = arguments.pop("effect_type", None)
                effect_params = arguments.pop("effect_params", None)
                if effect_type:
                    arguments["sound_effects"] = list(arguments.get("sound_effects") or []) + [(effect_type, effect_params)]
                if arguments.get("sound_effects"):
                    arguments["sound_effects"] = [tuple(e) if isinstance(e, list) else e
                                                  for e in arguments["sound_effects"]]
                result = add_audio_track(**arguments)
                
            elif tool_name == "add_image":
                result = add_image_impl(**arguments)
                
            elif tool_name == "add_text":
                # 处理text_styles参数
                text_styles_converted = None
                if "text_styles" in arguments and arguments["text_styles"]:
                    text_styles_converted = convert_text_styles(arguments["text_styles"])
                    arguments["text_styles"] = text_styles_converted
                
                result = add_text_impl(**arguments)
                
            elif tool_name == "add_subtitle":
                result = add_subtitle_impl(**arguments)
                
            elif tool_name == "add_effect":
                arguments.setdefault("effect_category", "scene")
                result = add_effect_impl(**arguments)
                
            elif tool_name == "add_filter":
                result = add_filter_impl(**arguments)

            elif tool_name == "add_sticker":
                result = add_sticker_impl(**arguments)
                
            elif tool_name == "add_video_keyframe":
                result = add_video_keyframe_impl(**arguments)
                
            elif tool_name == "get_video_duration":
                duration = get_video_duration(arguments["video_url"])
                result = {"duration": duration}
                
            elif tool_name == "save_draft":
                save_result = save_draft_impl(**arguments)
                if isinstance(save_result, dict) and "draft_url" in save_result:
                    result = {"draft_url": save_result["draft_url"]}
                else:
                    result = {"draft_url": f"https://www.install-ai-guider.top/draft/downloader?draft_id=unknown"}

            elif tool_name in _ROUTE_TOOLS:
                result = _call_route(tool_name, arguments)

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        return {
            "success": True,
            "result": result,
            "features_used": {
                "shadow": arguments.get("shadow_enabled", False) if tool_name == "add_text" else False,
                "background": bool(arguments.get("background_color")) if tool_name == "add_text" else False,
                "multi_style": bool(arguments.get("text_styles")) if tool_name == "add_text" else False
            }
        }
        
    except Exception as e:
        print(f"[ERROR] Tool execution error: {e}", file=sys.stderr)
        print(f"[ERROR] Traceback: {traceback.format_exc()}", file=sys.stderr)
        return {"success": False, "error": str(e)}

def handle_request(request_data: str) -> Optional[str]:
    """处理JSON-RPC请求"""
    try:
        request = json.loads(request_data.strip())
        print(f"[DEBUG] Received request: {request.get('method', 'unknown')}", file=sys.stderr)
        
        if request.get("method") == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "experimental": {},
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "capcut-api",
                        "version": "1.12.3"
                    }
                }
            }
            return json.dumps(response)
            
        elif request.get("method") == "notifications/initialized":
            return None
            
        elif request.get("method") == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {"tools": TOOLS}
            }
            return json.dumps(response)
            
        elif request.get("method") == "tools/call":
            tool_name = request["params"]["name"]
            arguments = request["params"].get("arguments", {})
            
            result = execute_tool(tool_name, arguments)
            
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
            return json.dumps(response)
            
        else:
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32601, "message": "Method not found"}
            }
            return json.dumps(error_response)
            
    except Exception as e:
        print(f"[ERROR] Request handling error: {e}", file=sys.stderr)
        print(f"[ERROR] Traceback: {traceback.format_exc()}", file=sys.stderr)
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": 0, "message": str(e)}
        }
        return json.dumps(error_response)

def main():
    """主函数"""
    print("🚀 Starting CapCut API MCP Server (Complete Version)...", file=sys.stderr)
    print(f"📋 Available tools: {len(TOOLS)} tools loaded", file=sys.stderr)
    print("✨ Features: 视频、音频、图片、文本、字幕、特效、贴纸、关键帧、类型列表、项目管理", file=sys.stderr)
    print("🔌 Waiting for client connections...", file=sys.stderr)
    
    try:
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    print("[DEBUG] EOF received, shutting down", file=sys.stderr)
                    break
                
                response = handle_request(line)
                if response:
                    print(response)
                    sys.stdout.flush()
                    
            except EOFError:
                print("[DEBUG] EOF exception, shutting down", file=sys.stderr)
                break
            except Exception as e:
                print(f"[ERROR] Server error: {e}", file=sys.stderr)
                print(f"[ERROR] Traceback: {traceback.format_exc()}", file=sys.stderr)
                
    except KeyboardInterrupt:
        print("[INFO] Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Fatal server error: {e}", file=sys.stderr)
        print(f"[ERROR] Traceback: {traceback.format_exc()}", file=sys.stderr)

if __name__ == "__main__":
    main()