## =============================================================================
## CHRONOLOGY MOD — tl_saveload.rpy
## Jump control: snapshot-primary, disk saves as backward-compat fallback.
## =============================================================================

init -2 python:

    _TL_EMPTY_PNG = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def _tl_save_no_screenshot(slot):
        """Call renpy.save(slot) without including a screenshot."""
        renpy_major = getattr(renpy, "version_tuple", (7,))[0]
        if renpy_major >= 8:
            renpy.save(slot, include_screenshot=False, mutate_flag=False)
        else:
            iface = renpy.game.interface
            try:
                iface.get_screenshot = lambda: _TL_EMPTY_PNG
                renpy.save(slot)
            finally:
                try:
                    del iface.get_screenshot
                except AttributeError:
                    pass

    def _tl_save_slot(node_index, context):
        raw = repr(tuple(context))
        slot_hash  = _tl_hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
        return "_ch_{:04d}_{}".format(node_index, slot_hash)

    def _tl_pre_save_slot(node_index, context, ast_key=None):
        raw = repr((tuple(context[:node_index]), ast_key))
        slot_hash  = _tl_hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
        return "_pre_{:04d}_{}".format(node_index, slot_hash)

    def _tl_find_pre_save(node_index, context, ast_key=None, save_dir=None):
        """Return pre-menu save slot for node_index if it exists on disk, else None."""
        import os
        slot = _tl_pre_save_slot(node_index, context, ast_key)
        root = save_dir if save_dir is not None else renpy.config.savedir
        for ext in ("-LT1.save", ".save"):
            if os.path.exists(os.path.join(root, slot + ext)):
                return slot
        return None

    def _tl_chap_end_slot_name(label, context=None, after_index=None):
        """Return the save-slot name for a chapter-end checkpoint."""
        if context is not None and after_index is not None:
            raw = repr(tuple(context[:after_index]))
            slot_hash = _tl_hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
            return "_ch_chap_{}_{}".format(label, slot_hash)
        return "_ch_chap_{}".format(label)

    def _tl_chap_slot_exists(slot_name, save_dir=None):
        """Return (exists, slot_name) — checks root savedir."""
        import os
        root = save_dir if save_dir is not None else renpy.config.savedir
        for ext in ("-LT1.save", ".save"):
            if os.path.exists(os.path.join(root, slot_name + ext)):
                return True, slot_name
        return False, None

    def _tl_clear_replay_state():
        persistent._tl_replaying      = False
        persistent._tl_recovery_slot  = None
        persistent._tl_replay_path    = None
        persistent._tl_replay_target  = None
        persistent._tl_prev_thumb     = None
        persistent._tl_synthetic_jump = False
        renpy.save_persistent()

    ## ── v2 internal helpers ──────────────────────────────────────────────────

    def _write_recovery():
        persistent._tl_recovery_slot = None
        _tl_save_no_screenshot("_ch_recovery")
        persistent._tl_recovery_slot = "_ch_recovery"

    def _replay_entries(hist):
        return [
            {
                "index"        : n["index"],
                "chosen_index" : n["chosen_index"],
                "ast_key"      : _tl_node_menu_site_key(n),
            }
            for n in hist if n.get("chosen_index") is not None
        ]

    def _stage_menu_replay(hist, node_index, option_index):
        prev_node = next((n for n in hist if n["index"] == node_index - 1), None)
        persistent._tl_replay_path   = _replay_entries(hist)
        persistent._tl_replay_target = {"node_index": node_index, "option_index": option_index}
        persistent._tl_prev_thumb    = prev_node["thumb_bytes"] if prev_node else None
        persistent._tl_replaying     = True

    def _stage_chapter_shadow(hist, after_index):
        ## replaying=False signals _tl_on_load to treat all entries as shadow directly.
        shadow_entries               = [e for e in _replay_entries(hist) if e["index"] >= after_index]
        persistent._tl_replay_path   = shadow_entries or None
        persistent._tl_replay_target = None
        persistent._tl_replaying     = False

    def _dispatch_snap(snap):
        persistent._tl_synthetic_jump = True
        renpy.save_persistent()
        renpy.game._tl_pending_snap = snap

    def _valid_snap(snap):
        """Accepts both the current live-reference shape and the legacy roots/context shape."""
        if not snap:
            return False
        if not snap.get("roots"):
            return False
        if "context" in snap:
            return snap.get("context") is not None
        return "ctx" in snap

    def _find_slot(node_index, hist, context):
        """
        Tier 1: exact pre-save at target index.
        Tier 2: walk history downward from node_index-1; first hit wins (closest save).
        """
        import os
        save_dir = renpy.config.savedir

        target_node = next((node for node in hist if node["index"] == node_index), None)
        ast_key     = _tl_node_menu_site_key(target_node) if target_node else None
        pre_slot    = _tl_find_pre_save(node_index, context, ast_key)
        if pre_slot:
            return pre_slot

        hist_by_idx   = {node["index"]: node for node in hist}
        marker_by_idx = {marker["after_index"]: marker for marker in store._tl_chapter_markers}

        for idx in range(node_index - 1, -1, -1):
            hist_node = hist_by_idx.get(idx)
            if hist_node:
                pre = _tl_find_pre_save(idx, context, _tl_node_menu_site_key(hist_node), save_dir)
                if pre:
                    return pre
                chk_slot = _tl_save_slot(idx, context)
                if os.path.exists(os.path.join(save_dir, chk_slot + "-LT1.save")):
                    return chk_slot

            chap_marker = marker_by_idx.get(idx)
            if chap_marker:
                slot_name = _tl_chap_end_slot_name(chap_marker["end_label"], context, idx)
                exists, full_slot = _tl_chap_slot_exists(slot_name)
                if exists:
                    return full_slot

        if os.path.exists(os.path.join(save_dir, "_ch_start-LT1.save")):
            return "_ch_start"
        return None

    ## ── Public API ───────────────────────────────────────────────────────────

    def _tl_jump(node_index=None, option_index=None, chapter_label=None):
        """
        Unified jump entry point. Menu jump: _tl_jump(node_index, option_index).
        Chapter jump: _tl_jump(chapter_label=label).
        Snapshot is primary; disk saves are backward-compat fallback.
        """
        hist       = list(getattr(store, "_tl_history", []))
        context    = list(store._tl_context)
        is_chapter = chapter_label is not None
        try:
            _write_recovery()

            if is_chapter:
                chap_marker = next(
                    (m for m in store._tl_chapter_markers if m["end_label"] == chapter_label),
                    None)
                after_index = chap_marker["after_index"] if chap_marker else len(hist)
                _stage_chapter_shadow(hist, after_index)
            else:
                _stage_menu_replay(hist, node_index, option_index)
            renpy.save_persistent()

            snap = (_tl_get_chapter_snapshot(chapter_label) if is_chapter
                    else _tl_get_menu_snapshot(node_index))
            if _valid_snap(snap):
                _dispatch_snap(snap)
                return

            if is_chapter:
                slot_name = (_tl_chap_end_slot_name(chapter_label, context, after_index)
                                if chap_marker else _tl_chap_end_slot_name(chapter_label))
                exists, full_slot = _tl_chap_slot_exists(slot_name)
                if exists:
                    store._tl_chap_end_slot = full_slot
                    return
            else:
                fallback_slot = _find_slot(node_index, hist, context)
                if fallback_slot:
                    store._tl_load_slot = fallback_slot
                    return

            _tl_clear_replay_state()
            renpy.notify("No save found for {}.".format(
                "chapter jump" if is_chapter else "that choice"))

        except (renpy.game.RestartTopContext, renpy.game.RestartContext):
            raise
        except Exception as exc:
            _tl_log("TL jump ERROR {}: {}".format(chapter_label or node_index, exc))
            _tl_clear_replay_state()

    def _tl_cancel_jump():
        """
        Cancel an in-progress jump and restore from recovery save.
        Caches thumbnails from history nodes into renpy.game._tl_thumb_cache
        to avoid re-loading them after the recovery load.
        """
        slot = persistent._tl_recovery_slot

        try:
            thumb_cache = getattr(renpy.game, "_tl_thumb_cache", {})
            for node in store._tl_history:
                cache_key = str(node.get("ast_key")) if node.get("ast_key") else None
                if cache_key and node.get("thumb_bytes") and cache_key not in thumb_cache:
                    thumb_cache[cache_key] = node["thumb_bytes"]
                    node["thumb_bytes"] = None
                    while len(thumb_cache) > TL_THUMB_CACHE_MAX:
                        thumb_cache.pop(next(iter(thumb_cache)))
        except Exception as exc:
            _tl_log("TL cancel thumb cache error: {}".format(exc))
        
        _tl_clear_replay_state()
        if slot:
            store._tl_load_slot = slot
            return slot
        return None
