## =============================================================================
## CHRONOLOGY MOD — tl_chapter_ren.py
## Chapter metadata: loading, dedup, marker tracking, timeline rollback.
## =============================================================================

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Tuple
    import renpy  # type-check-only; injected into store namespace at runtime
    from timeline_init_ren import _tl_log  # type-check-only; injected into store namespace at runtime

"""renpy
init -2 python:
"""

import os as _tl_os_ch
import json as _tl_json_ch

def _tl_load_chapters():  # type: () -> dict
    path = _tl_os_ch.path.join(renpy.config.gamedir, "renpy-chronology-mod", "chapters.json")
    try:
        with open(path, "r") as f:
            raw = _tl_json_ch.load(f)
    except Exception as e:
        _tl_log("TL chapters load failed: {}".format(e))
        return {}
    seen_labels = {}
    deduped = {}
    for ch_name, ch_label in raw.items():
        if ch_name.startswith("_"):
            continue
        if ch_label in seen_labels:
            _tl_log("TL WARNING chapters.json: label '{}' mapped to both '{}' and '{}'; '{}' wins".format(
                ch_label, seen_labels[ch_label], ch_name, seen_labels[ch_label]))
        else:
            seen_labels[ch_label] = ch_name
            deduped[ch_name] = ch_label
    _tl_log("TL chapters: loaded {} from {}".format(len(deduped), path))
    return deduped

def _tl_dedup_chapters(raw):  # type: (dict) -> dict
    """
    Deduplicates a {chapter_name: end_label} dict.
    Duplicate labels (same label mapped to multiple chapters) are silently
    dropped — first occurrence wins.
    """
    seen_labels = {}
    deduped = {}
    for ch_name, ch_label in raw.items():
        if ch_label not in seen_labels:
            seen_labels[ch_label] = ch_name
            deduped[ch_name] = ch_label
    return deduped

def _tl_chapter_marker_exists(markers, chapter, after_idx):  # type: (list, str, int) -> bool
    """
    Return True if a marker for (chapter, after_idx) already exists.
    Used to deduplicate label callbacks that fire multiple times.
    """
    return any(
        m["after_index"] == after_idx and m["chapter_name"] == chapter
        for m in markers
    )

def _tl_rollback_timeline(history, context, markers, label, chapters):  # type: (list, list, list, str, dict) -> Tuple[list, list, list]
    """
    Roll back history/context/markers to the state they had at the chapter
    end identified by `label`. Returns (history, context, markers) sliced
    to after_index. Returns originals unchanged if label is not found.
    """
    chapter = next((ch for ch, lbl in chapters.items() if lbl == label), None)
    if not chapter:
        return history, context, markers
    marker = next((m for m in markers if m["chapter_name"] == chapter), None)
    if not marker:
        return history, context, markers
    ai = marker["after_index"]
    return (
        history[:ai],
        context[:ai],
        [m for m in markers if m["after_index"] <= ai],
    )