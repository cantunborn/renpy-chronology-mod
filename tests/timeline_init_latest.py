# Extracted from timeline_init.rpy for unit testing.
# Lives in: renpy-chronology-mod/tests/timeline_init_latest.py
# Keep in sync with timeline_init.rpy manually when logic changes.
import os, uuid, hashlib as _tl_hashlib

def _tl_save_slot(node_index, context):
    raw = repr(tuple(context))
    h6  = _tl_hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
    return "_ch_{:04d}_{}".format(node_index, h6)

def _tl_find_nearest_save(target_index, context, save_dir, start_exists=False):
    """Testable version with injected save_dir and start_exists flag."""
    best_index = -1
    best_slot  = None
    try:
        for fname in os.listdir(save_dir):
            if not fname.startswith("_ch_"):
                continue
            if "recovery" in fname or "start" in fname:
                continue
            name  = fname.replace("-LT1.save", "").replace(".save", "")
            parts = name.split("_")
            if len(parts) < 4:
                continue
            try:
                idx = int(parts[2])
            except ValueError:
                continue
            if idx > target_index:
                continue
            ctx_at_idx  = context[:idx + 1]
            expected_h6 = _tl_hashlib.md5(repr(tuple(ctx_at_idx)).encode("utf-8")).hexdigest()[:6]
            if parts[3] != expected_h6:
                continue
            if idx > best_index:
                best_index = idx
                best_slot  = name
    except Exception as e:
        pass

    if best_slot is None and start_exists:
        best_slot = "_ch_start"

    return best_slot

def _tl_validate_history(history):
    """Extracted from _tl_validate_on_load for unit testing."""
    if not isinstance(history, list):
        return []
    clean = []
    for node in history:
        if (isinstance(node, dict)
                and "index" in node
                and "options" in node
                and isinstance(node["options"], list)):
            clean.append(node)
    for i, node in enumerate(clean):
        node["index"] = i
    return clean

def _tl_should_save(idx, dense=5, every=10):
    """Return True if a checkpoint save should be written for this node index."""
    return idx < dense or idx % every == every - 1

def _tl_node_has_new(node, seen_fn):
    """seen_fn(node, i) -> bool — injected for testability."""
    chosen_idx = node.get("chosen_index")
    for i in range(len(node.get("options", []))):
        if i == chosen_idx:
            continue
        if not seen_fn(node, i):
            return True
    return False

# ---------------------------------------------------------------------------
# Chapter-end feature (added in v1.1)
# ---------------------------------------------------------------------------

def _tl_dedup_chapters(raw):
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

def _tl_chapter_marker_exists(markers, chapter, after_idx):
    """
    Return True if a marker for (chapter, after_idx) already exists.
    Used to deduplicate label callbacks that fire multiple times.
    """
    return any(
        m["after_index"] == after_idx and m["chapter_name"] == chapter
        for m in markers
    )

def _tl_rollback_timeline(history, context, markers, label, chapters):
    """
    Roll back history/context/markers to the state they had at the chapter
    end identified by `label`.  Returns (history, context, markers) sliced
    to after_index.  Returns originals unchanged if label is not found.
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

def _tl_chap_end_slot_name(label):
    """Return the save-slot name for a chapter-end checkpoint."""
    return "_ch_chap_{}".format(label)

def _tl_node_thumb(node, cache):
    """Return thumbnail bytes for a node: from the node itself or the persistent cache."""
    b = node.get("thumb_bytes")
    if b:
        return b
    key = str(node["ast_key"]) if node.get("ast_key") else None
    return cache.get(key) if key else None

def _tl_build_shadow_path(history, node_index):
    """Build the replay-aid shadow path from history nodes after node_index."""
    path, past = [], False
    for n in history:
        if past:
            loc = n.get("_location")
            ci  = n.get("chosen_index")
            if loc is not None and ci is not None:
                path.append({"location": loc, "chosen_index": ci})
        elif n["index"] == node_index:
            past = True
    return path

def _tl_shadow_match(shadow_path, location):
    """Return chosen_index from the first shadow path entry matching location, or None."""
    for entry in shadow_path:
        if entry["location"] == location:
            return entry["chosen_index"]
    return None

def _tl_consume_shadow_path(shadow_path, location, chosen_index):
    """
    Consume shadow path entries up to and including the first entry matching `location`.
    Returns (new_path_or_none, orig_ci_or_none).
    orig_ci is the matched entry's chosen_index when it differs from chosen_index (diverged),
    or None when choices match or no entry matched.
    """
    if not shadow_path:
        return shadow_path, None
    new_sp = []
    matched = False
    orig_ci = None
    for e in shadow_path:
        if not matched and e["location"] == location:
            matched = True
            orig_ci = e["chosen_index"]
        elif matched:
            new_sp.append(e)
    if not matched:
        return shadow_path, None
    diverged_ci = orig_ci if orig_ci != chosen_index else None
    return new_sp or None, diverged_ci

