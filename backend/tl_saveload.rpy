## =============================================================================
## CHRONOLOGY MOD — tl_saveload.rpy
## Save/load checkpoint logic, replay staging, and jump control.
## =============================================================================

init -2 python:

    def _tl_should_save(idx, dense=None, every=None):
        """Return True if a checkpoint save should be written for this node index."""
        d = dense if dense is not None else TL_DENSE_SAVES
        e = every if every is not None else TL_SAVE_EVERY
        return idx < d or idx % e == e - 1

    def _tl_save_slot(node_index, context):
        raw = repr(tuple(context))
        h6  = _tl_hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
        return "_ch_{:04d}_{}".format(node_index, h6)

    def _tl_chap_end_slot_name(label, context=None, after_index=None):
        """Return the save-slot name for a chapter-end checkpoint."""
        if context is not None and after_index is not None:
            h6 = _tl_hashlib.md5(
                repr(tuple(context[:after_index])).encode("utf-8")
            ).hexdigest()[:6]
            return "_ch_chap_{}_{}".format(label, h6)
        return "_ch_chap_{}".format(label)

    def _tl_find_nearest_save(target_index, context, save_dir=None,
                                start_exists=None, chap_candidates=None):
        """
        Find the chronology save slot with the highest index <= target_index
        that shares the same path prefix as context.

        save_dir: directory to scan. Defaults to renpy.config.savedir.
        start_exists: if True, fall back to _ch_start when no checkpoint found.
                        If None, checks the filesystem.
        chap_candidates: optional list of (after_index, slot_name) from chapter-end
                        saves, pre-validated by the caller.
        Returns slot name (without extension) or None.
        """
        import os as _os
        if save_dir is None:
            save_dir = renpy.config.savedir
        best_index = -1
        best_slot  = None
        try:
            for fname in _os.listdir(save_dir):
                if not fname.startswith("_ch_"):
                    continue
                if "recovery" in fname or "start" in fname or "chap" in fname:
                    continue
                name  = fname.replace("-LT1.save", "").replace(".save", "")
                parts = name.split("_")
                ## ['', 'ch', '0001', '6d0e4b']
                if len(parts) < 4:
                    continue
                try:
                    idx = int(parts[2])
                except ValueError:
                    continue
                if idx > target_index:
                    continue
                ctx_at_idx  = context[:idx + 1]
                expected_h6 = _tl_hashlib.md5(
                    repr(tuple(ctx_at_idx)).encode("utf-8")
                ).hexdigest()[:6]
                if parts[3] != expected_h6:
                    continue
                if idx > best_index:
                    best_index = idx
                    best_slot  = name
        except Exception as e:
            _tl_log("TL find_nearest_save error: {}".format(e))

        for chap_idx, chap_slot in (chap_candidates or []):
            if chap_idx <= target_index and chap_idx > best_index:
                best_index = chap_idx
                best_slot  = chap_slot

        if best_slot is None:
            if start_exists is None:
                import os as _os2
                start_file = _os2.path.join(save_dir, "_ch_start-LT1.save")
                start_exists = _os2.path.exists(start_file)
            if start_exists:
                best_slot = "_ch_start"
                _tl_log("TL find_nearest_save: using _ch_start fallback")

        return best_slot

    def _tl_clear_replay_state():
        persistent._tl_replaying    = False
        persistent._tl_recovery_slot = None
        persistent._tl_replay_path   = None
        persistent._tl_replay_target = None
        persistent._tl_prev_thumb    = None
        persistent._tl_pending_shadow_path = None
        renpy.save_persistent()

    def _tl_begin_label_jump(label):
        try:
            renpy.save("_ch_recovery")
            persistent._tl_recovery_slot = "_ch_recovery"

            ## Prefer loading the chapter-end save (captures all state cleanly)
            import os as _os
            _marker = next((m for m in store._tl_chapter_markers if m["end_label"] == label), None)
            if _marker is not None:
                _ai   = _marker["after_index"]
                _slot = _tl_chap_end_slot_name(label, store._tl_context, _ai)
            else:
                _slot = _tl_chap_end_slot_name(label)
            _sd   = renpy.config.savedir
            _exists = (
                _os.path.exists(_os.path.join(_sd, "{}-LT1.save".format(_slot))) or
                _os.path.exists(_os.path.join(_sd, "{}.save".format(_slot)))
            )
            if _exists:
                store._tl_chap_end_slot = _slot
                _tl_log("TL chapter-end jump: loading save={}".format(_slot))
                return

            ## Fallback (no save yet): jump + manual rollback
            store._tl_chap_end_slot = ""
            store._tl_label_jump    = label
            _chapter = next(
                (ch for ch, lbl in _tl_chapters.items() if lbl == label), None
            )
            if _chapter:
                _marker = next(
                    (m for m in store._tl_chapter_markers if m["chapter_name"] == _chapter),
                    None
                )
                if _marker:
                    _ai = _marker["after_index"]
                    store._tl_history         = store._tl_history[:_ai]
                    store._tl_node_count      = _ai
                    store._tl_context         = store._tl_context[:_ai]
                    store._tl_chapter_markers = [
                        m for m in store._tl_chapter_markers
                        if m["after_index"] <= _ai
                    ]
            _tl_log("TL chapter-end jump: no save for {}, falling back to jump".format(label))
        except Exception as e:
            _tl_log("TL ERROR label jump failed: {}".format(e))

    def _tl_begin_jump(node_index, option_index):
        try:
            _tl_log("TL jump: node={} option={}".format(node_index, option_index))
            renpy.save("_ch_recovery")
            persistent._tl_recovery_slot = "_ch_recovery"

            persistent._tl_replay_path = [
                {"index": n["index"], "chosen_index": n["chosen_index"]}
                for n in _tl_history
                if n.get("chosen_index") is not None
            ]
            persistent._tl_replay_target = {
                "node_index"  : node_index,
                "option_index": option_index,
            }
            prev_node = None
            for n in _tl_history:
                if n["index"] == node_index - 1:
                    prev_node = n
                    break
            persistent._tl_prev_thumb = prev_node["thumb_bytes"] if prev_node else None
            persistent._tl_replaying  = True

            ## ── Shadow path: menus after the target, shared with original history ──
            ## Built now so the store wrapper can auto-fill them after replay ends.
            _shadow_path  = _tl_stage_shadow_path(_tl_history, node_index)
            _shadow_count = len(_shadow_path or [])
            _tl_log("TL shadow stage: target_node={} count={} first={}".format(
                node_index, _shadow_count, (_shadow_path[0] if _shadow_count else None)))
            ## Shadow path must survive the checkpoint load that follows, so stage it in
            ## persistent. _tl_on_load transfers it into store._tl_shadow_path after load
            ## (store vars would be overwritten by the checkpoint). Recovery save is taken
            ## above before this line, so cancel restores store._tl_shadow_path cleanly.            
            persistent._tl_pending_shadow_path = _shadow_path

            renpy.save_persistent()

            ## ── Save+skip ────────────────────────────────────────────────────
            ## Build chapter-end save candidates: markers before target, hash-validated,
            ## existing on disk. Passed to _tl_find_nearest_save so chapter-end saves
            ## can serve as jump checkpoints when closer than a regular checkpoint.
            import os as _os
            _sd = renpy.config.savedir
            _chap_candidates = []
            for _m in store._tl_chapter_markers:
                _ai = _m["after_index"]
                if _ai > node_index - 1:
                    continue
                _cs = _tl_chap_end_slot_name(_m["end_label"], store._tl_context, _ai)
                if (_os.path.exists(_os.path.join(_sd, "{}-LT1.save".format(_cs))) or
                        _os.path.exists(_os.path.join(_sd, "{}.save".format(_cs)))):
                    _chap_candidates.append((_ai, _cs))

            nearest = _tl_find_nearest_save(
                node_index - 1, list(_tl_context), chap_candidates=_chap_candidates)

            if nearest is not None:
                _tl_log("TL jump: loading save={}".format(nearest))
                store._tl_load_slot = nearest
                return "load"
            else:
                _tl_log("TL jump: no save found for node={}".format(node_index))
                _tl_clear_replay_state()
                renpy.notify("No save found for that choice. Play further to enable jumping.")
                return None

        except Exception as e:
            _tl_log("TL ERROR jump failed: {}".format(e))
            _tl_clear_replay_state()
            return None

    def _tl_cancel_replay():
        slot = persistent._tl_recovery_slot
        ## Snapshot all current node thumbnails into cache before loading
        ## the recovery save. After load, _tl_history will be restored from
        ## the save state — but the cache persists, so thumbnails are available.
        try:
            for n in _tl_history:
                key = str(n.get("ast_key")) if n.get("ast_key") else None
                if key and n.get("thumb_bytes") and key not in persistent._tl_thumb_cache:
                    persistent._tl_thumb_cache[key] = n["thumb_bytes"]
                    n["thumb_bytes"] = None  ## cleared — served from persistent cache
                    while len(persistent._tl_thumb_cache) > TL_THUMB_CACHE_MAX:
                        persistent._tl_thumb_cache.pop(next(iter(persistent._tl_thumb_cache)))
            renpy.save_persistent()
        except Exception as e:
            _tl_log("TL cancel_replay cache error: {}".format(e))
        _tl_clear_replay_state()  ## clears _tl_recovery_slot
        if slot:
            store._tl_load_slot = slot
            return slot
        return None
