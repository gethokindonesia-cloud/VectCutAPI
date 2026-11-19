"""Open an existing CapCut desktop project, edit it, and save the result as a NEW project.

The original project folder is only ever read. save_project copies it to a new name and
writes the edited main timeline into the copy, so Resources/, subdraft/ (compound clips)
and the other timelines carry over unchanged.
"""
import json
import os
import shutil
import uuid
from copy import deepcopy
from typing import Optional, Dict, List, Any

import pyJianYingDraft as draft
from pyJianYingDraft.track import Track_type
from draft_cache import DRAFT_CACHE, update_cache
from util import url_to_hash, generate_draft_url

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
REPLACED_MEDIA_DIR = os.path.join(REPO_DIR, "replaced_media")

# draft_id -> info about the project it was opened from
OPENED_PROJECTS: Dict[str, Dict[str, Any]] = {}

_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv"}
_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic"}
_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def capcut_projects_dir() -> Optional[str]:
    """CapCut desktop drafts folder for this OS, or None if CapCut is not installed."""
    if os.name == 'nt':
        p = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
    else:
        p = os.path.expanduser('~/Library/Containers/com.lemon.lvpro/Data/Documents/JianyingPro/User Data/Projects/com.lveditor.draft')
    return p if os.path.exists(p) else None


def resolve_project_dir(project_name: str) -> str:
    """Project folder name (from list_projects) or absolute path -> existing folder path."""
    if os.path.isabs(project_name):
        target = project_name
    else:
        base = capcut_projects_dir()
        if not base:
            raise FileNotFoundError("CapCut drafts folder not found")
        target = os.path.join(base, project_name)
    if not os.path.isdir(target):
        raise FileNotFoundError(f"Project path does not exist: {target}")
    return target


def _timelines(project_dir: str) -> Dict[str, Any]:
    """Contents of Timelines/project.json ({} for projects with a single timeline)."""
    path = os.path.join(project_dir, "Timelines", "project.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_content_file(project_dir: str, timeline: Optional[str] = None) -> str:
    """Path of the draft_content.json for the main timeline, or for the named/ID'd timeline."""
    if timeline:
        info = _timelines(project_dir)
        for t in info.get("timelines", []):
            if not t.get("is_marked_delete") and timeline in (t.get("id"), t.get("name")):
                path = os.path.join(project_dir, "Timelines", t["id"], "draft_content.json")
                if os.path.exists(path):
                    return path
        names = [t.get("name") for t in info.get("timelines", []) if not t.get("is_marked_delete")]
        raise FileNotFoundError(f"Timeline {timeline!r} not found; available: {names}")

    root = os.path.join(project_dir, "draft_content.json")
    if os.path.exists(root):
        return root
    main_id = _timelines(project_dir).get("main_timeline_id")
    if main_id:
        path = os.path.join(project_dir, "Timelines", main_id, "draft_content.json")
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"draft_content.json not found in {project_dir}")


def _text_of(material: Dict[str, Any]) -> str:
    content = material.get("content", "")
    try:
        return json.loads(content).get("text", "")
    except (ValueError, AttributeError):
        return str(content)


def _summary(script: draft.Script_file, include_texts: bool, text_limit: int) -> Dict[str, Any]:
    texts_by_id = {m["id"]: _text_of(m) for m in script.imported_materials.get("texts", [])}
    for tpl in script.imported_materials.get("text_templates", []):
        texts_by_id[tpl["id"]] = " / ".join(
            texts_by_id.get(r.get("text_material_id"), "") for r in tpl.get("text_info_resources", []))

    tracks, texts = [], []
    index_by_type: Dict[str, int] = {}
    for track in script.imported_tracks:
        type_name = track.track_type.name
        idx = index_by_type.get(type_name, 0)
        index_by_type[type_name] = idx + 1
        tracks.append({"type": type_name, "index": idx, "name": track.name, "segments": len(track.segments)})
        if include_texts and track.track_type == Track_type.text:
            for seg_idx, seg in enumerate(track.segments):
                if len(texts) >= text_limit:
                    break
                texts.append({
                    "track_index": idx,
                    "segment_index": seg_idx,
                    "start": seg.target_timerange.start / 1e6,
                    "text": texts_by_id.get(seg.material_id, "")[:120],
                })

    def _names(kind: str, key: str) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        for m in script.imported_materials.get(kind, []):
            counts[m.get(key, "")] = counts.get(m.get(key, ""), 0) + 1
        return [{"name": n, "uses": c} for n, c in counts.items()]

    return {
        "duration": script.duration / 1e6,
        "width": script.width,
        "height": script.height,
        "fps": script.fps,
        "tracks": tracks,
        "texts": texts,
        "video_materials": _names("videos", "material_name"),
        "audio_materials": _names("audios", "name"),
    }


def open_project_impl(project_name: str, timeline: Optional[str] = None,
                      include_texts: bool = True, text_limit: int = 300) -> Dict[str, Any]:
    """
    Load an existing CapCut project into a draft you can edit with the add_* / replace_* tools.
    :param project_name: Project folder name (from list_projects) or absolute path
    :param timeline: Timeline name or ID for multi-timeline projects (default: main timeline)
    :param include_texts: List text segments (track_index, segment_index, text) for replace_text
    :param text_limit: Maximum number of text segments to list
    :return: draft_id plus a summary of tracks, texts and media names
    """
    project_dir = resolve_project_dir(project_name)
    content_file = resolve_content_file(project_dir, timeline)
    script = draft.Script_file.load_template(content_file)

    draft_id = f"proj_{uuid.uuid4().hex[:12]}"
    update_cache(draft_id, script)
    with open(content_file, "r", encoding="utf-8") as f:
        original = json.load(f)
    OPENED_PROJECTS[draft_id] = {
        "project_dir": project_dir,
        "content_file": content_file,
        "keep": {k: deepcopy(original[k]) for k in ("platform", "last_modified_platform", "canvas_config") if k in original},
    }

    result = {"draft_id": draft_id, "project_dir": project_dir, "content_file": content_file}
    result.update(_summary(script, include_texts, text_limit))
    return result


def _script(draft_id: str) -> draft.Script_file:
    if draft_id not in DRAFT_CACHE:
        raise ValueError(f"Draft {draft_id} not found; open it with open_project first")
    return DRAFT_CACHE[draft_id]


def replace_text_impl(draft_id: str, segment_index: int, text: Any, track_index: int = 0,
                      recalc_style: bool = True) -> Dict[str, Any]:
    """
    Replace the words of one text segment in an opened project, keeping its style and animation.
    :param draft_id: Draft ID from open_project
    :param segment_index: Segment index in the text track (from open_project texts)
    :param text: New text; for a text template pass a list with one string per text part
    :param track_index: Index among the project's text tracks (from open_project texts), default 0
    :param recalc_style: Stretch per-character style ranges to the new length, default True
    """
    script = _script(draft_id)
    track = script.get_imported_track(Track_type.text, index=track_index)
    script.replace_text(track, segment_index, text, recalc_style=recalc_style)
    return {"draft_id": draft_id, "track_index": track_index, "segment_index": segment_index}


def _local_media(path_or_url: str) -> str:
    """Return a local file path, downloading URLs into replaced_media/ (kept so the project can use it)."""
    if not path_or_url.lower().startswith(("http://", "https://")):
        path = os.path.abspath(path_or_url)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"File not found: {path}")
        return path
    from downloader import download_file
    ext = os.path.splitext(path_or_url.split("?")[0])[1].lower() or ".bin"
    os.makedirs(REPLACED_MEDIA_DIR, exist_ok=True)
    local = os.path.join(REPLACED_MEDIA_DIR, url_to_hash(path_or_url) + ext)
    if not os.path.exists(local):
        download_file(path_or_url, local)
    return local


def replace_material_impl(draft_id: str, material_name: str, new_media: str) -> Dict[str, Any]:
    """
    Swap a video, photo or audio file in an opened project for another file, everywhere it is used.
    Clip lengths and trims stay the same, so the new file should be at least as long as the old one.
    :param draft_id: Draft ID from open_project
    :param material_name: Current media name (from open_project video_materials / audio_materials)
    :param new_media: Local file path or URL of the replacement
    """
    script = _script(draft_id)
    local = _local_media(new_media)
    ext = os.path.splitext(local)[1].lower()

    if ext in _AUDIO_EXTS:
        kind, name_key = "audios", "name"
        new = draft.Audio_material(path=local)
        updates = {"path": local, "name": os.path.basename(local), "duration": new.duration}
    elif ext in _VIDEO_EXTS or ext in _PHOTO_EXTS:
        kind, name_key = "videos", "material_name"
        new = draft.Video_material("photo" if ext in _PHOTO_EXTS else "video", path=local)
        updates = {"path": local, "material_name": os.path.basename(local), "duration": new.duration,
                   "width": new.width, "height": new.height, "type": new.material_type}
    else:
        raise ValueError(f"Unsupported media type {ext!r}")

    matches = [m for m in script.imported_materials.get(kind, []) if m.get(name_key) == material_name]
    if not matches:
        names = sorted({m.get(name_key, "") for m in script.imported_materials.get(kind, [])})
        raise ValueError(f"No {kind[:-1]} named {material_name!r}; available: {names[:50]}")
    for m in matches:
        m.update(updates)

    return {"draft_id": draft_id, "replaced": len(matches), "new_path": local}


def _rewrite_meta(dest: str, new_name: str) -> None:
    """Give the copied project its own name, path and ID so CapCut treats it as a separate project."""
    meta_path = os.path.join(dest, "draft_meta_info.json")
    if not os.path.exists(meta_path):
        return
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["draft_name"] = new_name
    meta["draft_fold_path"] = dest.replace("\\", "/")
    meta["draft_id"] = str(uuid.uuid4()).upper()
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def save_project_impl(draft_id: str, new_project_name: str) -> Dict[str, Any]:
    """
    Save an opened project as a NEW CapCut project; the original project is never modified.
    :param draft_id: Draft ID from open_project
    :param new_project_name: Folder name for the new project; must not exist yet
    """
    from save_draft_impl import save_draft_background
    from draft_profiles import get_draft_profile
    from save_task_cache import create_task

    if draft_id not in OPENED_PROJECTS:
        raise ValueError(f"Draft {draft_id} was not opened with open_project; use save_draft instead")
    info = OPENED_PROJECTS[draft_id]
    if not new_project_name or os.path.basename(new_project_name) != new_project_name:
        raise ValueError("new_project_name must be a plain folder name")

    src = info["project_dir"]
    dest = os.path.join(os.path.dirname(src), new_project_name)
    if os.path.exists(dest):
        raise FileExistsError(f"Project {new_project_name!r} already exists; pick another name")

    shutil.copytree(src, dest)
    try:
        lock = os.path.join(dest, ".locked")
        if os.path.exists(lock):
            os.remove(lock)

        # Normal save into a work folder inside the new project: downloads any new media
        # into it and writes the processed draft JSON.
        work_root = os.path.join(dest, "vectcut_assets")
        create_task(draft_id)
        save_draft_background(draft_id, work_root, draft_id, auto_deploy=False)
        profile = get_draft_profile()
        with open(os.path.join(work_root, draft_id, profile.content_file), "r", encoding="utf-8") as f:
            content = json.load(f)
        content.update(deepcopy(info["keep"]))  # keep CapCut's own platform/canvas info

        # Write the edited timeline over the copied one (root file and its Timelines/ twin)
        rel = os.path.relpath(info["content_file"], src)
        targets = {os.path.join(dest, rel)}
        if rel == "draft_content.json":
            main_id = _timelines(dest).get("main_timeline_id")
            if main_id and os.path.isdir(os.path.join(dest, "Timelines", main_id)):
                targets.add(os.path.join(dest, "Timelines", main_id, "draft_content.json"))
        text = json.dumps(content, ensure_ascii=False)
        for t in targets:
            with open(t, "w", encoding="utf-8") as f:
                f.write(text)

        _rewrite_meta(dest, new_project_name)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise

    return {"project_name": new_project_name, "project_dir": dest, "draft_url": generate_draft_url(draft_id)}
