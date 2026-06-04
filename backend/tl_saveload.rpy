## =============================================================================
## CHRONOLOGY MOD — tl_saveload.rpy
## Save/load checkpoint logic, replay staging, and jump control.
## =============================================================================

init -2 python:

    ## ── Legacy: post-choice checkpoint slot naming ───────────────────────────
    ## Sparse _ch_* saves are no longer written; pre-saves cover all menus.
    ## These functions are kept so existing saves on disk remain loadable as
    ## fallback (via _tl_find_nearest_save) and so legacy tests still pass.

    def _tl_should_save(idx, dense=None, every=None):
        d = dense if dense is not None else TL_DENSE_SAVES
        e = every if every is not None else TL_SAVE_EVERY
        return idx < d or idx % e == e - 1

    def _tl_save_slot(node_index, context):
        raw = repr(tuple(context))
        h6  = _tl_hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
        return "_ch_{:04d}_{}".format(node_index, h6)

    ## ─────────────────────────────────────────────────────────────────────────

    def _tl_pre_save_slot(node_index, context, ast_key=None):
        """Slot name for a pre-menu stripped save at node_index.
        Hash input is (context[:node_index], ast_key) — path + menu identity.
        ast_key=(file, line) disambiguates sandbox games where multiple different
        menus can appear at the same node_index on the same context prefix."""
        raw = repr((tuple(context[:node_index]), ast_key))
        h6  = _tl_hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
        return "_pre_{:04d}_{}".format(node_index, h6)

    def _tl_find_pre_save(node_index, context, ast_key=None, save_dir=None):
        """Return pre-menu save slot for node_index if it exists on disk, else None."""
        import os as _os
        _slot = _tl_pre_save_slot(node_index, context, ast_key)
        _root = save_dir if save_dir is not None else renpy.config.savedir
        for _ext in ("-LT1.save", ".save"):
            if _os.path.exists(_os.path.join(_root, _slot + _ext)):
                return _slot
        return None

    def _tl_find_nearest_any_save(target_index, context, history=None, chap_candidates=None,
            save_dir=None):
        """
        Return the slot (pre-save or _ch_*) with the highest index <= target_index.
        Competes both pools so a nearby _ch_* checkpoint beats a distant pre-save,
        including chapter-end saves whose slot names are not index-parseable.
        """
        _pre_meta = {}
        _ch_meta  = {}
        _pre = _tl_find_nearest_pre_save(target_index, context, history,
            save_dir=save_dir, _meta=_pre_meta)
        _ch  = _tl_find_nearest_save(target_index, context, save_dir=save_dir,
            chap_candidates=chap_candidates, _meta=_ch_meta)
        if _pre is None:
            return _ch
        if _ch is None:
            return _pre
        return _pre if _pre_meta.get("index", -1) >= _ch_meta.get("index", -1) else _ch

    def _tl_find_nearest_pre_save(target_index, context, history=None, save_dir=None,
            _meta=None):
        """
        Return the pre-menu save slot with the highest index <= target_index
        that shares the same (context prefix, ast_key) as recorded in history.

        Unlike _tl_find_pre_save (exact match), this scans all _pre_* files.
        Used as a fallback when the exact pre-save for a target menu was deleted
        (e.g. by _tl_thin_pre_saves). The found save requires skip replay from
        its menu index up to the target, same as _ch_* fallback saves.

        history: list of history node dicts (from _tl_history). For each candidate
        file at index _idx, the node's ast_key is looked up from history to compute
        the expected hash — consistent with how _tl_pre_save_slot builds the slot.
        If history is None or the node is not found, ast_key=None is used.
        """
        import os as _os
        _root = save_dir if save_dir is not None else renpy.config.savedir
        _best_index = -1
        _best_slot  = None
        try:
            for _fname in _os.listdir(_root):
                if not _fname.startswith("_pre_"):
                    continue
                _name  = _fname.replace("-LT1.save", "").replace(".save", "")
                _parts = _name.split("_")
                ## ['', 'pre', '0027', 'hash']
                if len(_parts) < 4:
                    continue
                try:
                    _idx = int(_parts[2])
                except ValueError:
                    continue
                if _idx > target_index:
                    continue
                ## Look up ast_key for this index from history
                _hist_node = None
                if history:
                    for _n in history:
                        if _n.get("index") == _idx:
                            _hist_node = _n
                            break
                _ast_key      = _tl_derive_node_menu_site_key(_hist_node) if _hist_node else None
                _expected_slot = _tl_pre_save_slot(_idx, context, _ast_key)
                if _parts[3] != _expected_slot.split("_")[-1]:
                    continue
                if _idx > _best_index:
                    _best_index = _idx
                    _best_slot  = _name
        except Exception as _e:
            _tl_log("TL find_nearest_pre_save scan error: {}".format(_e))
        if _meta is not None:
            _meta["index"] = _best_index
        return _best_slot

    ## Minimal 1×1 black PNG — used to suppress full screenshots on RenPy 7
    ## where include_screenshot=False is not supported.
    _TL_EMPTY_PNG = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def _tl_save_no_screenshot(slot):
        """Call renpy.save(slot) without including a screenshot.
        RenPy 8+: include_screenshot=False kwarg.
        RenPy 7:  temporarily shadow interface.get_screenshot with a 1×1 PNG."""
        _renpy_major = getattr(renpy, "version_tuple", (7,))[0]
        if _renpy_major >= 8:
            renpy.save(slot, include_screenshot=False, mutate_flag=False)
        else:
            _iface = renpy.game.interface
            try:
                _iface.get_screenshot = lambda: _TL_EMPTY_PNG
                renpy.save(slot)
            finally:
                try:
                    del _iface.get_screenshot
                except AttributeError:
                    pass

    ## Key under which the pre-save threading.Event is stored in sys.modules.
    ## Using sys.modules keeps it out of the RenPy store and avoids pickle
    ## failures on RenPy 7 (Python 2) where threading.Lock is not picklable.
    def _tl_write_pre_save(node_index, context, ast_key=None):
        """
        Write a stripped pre-menu save synchronously on the main thread.

        ast_key=(filename, linenumber) is included in the slot hash so that
        sandbox games where different menus share the same (node_index,
        context[:N]) prefix get distinct slot names and don't collide.

        If autosave is in progress, the write is skipped — the next menu will
        get a fresh save. Log is truncated to 1 entry for the duration of the
        save call to keep files small, then restored in a finally block.
        """
        import os as _os

        ## Fast path: slot already on disk for this exact (index, path, menu)
        if _tl_find_pre_save(node_index, context, ast_key) is not None:
            _tl_log("TL pre-save skip (exists): node={}".format(node_index))
            return

        ## Skip if autosave is running to avoid concurrent save conflict.
        _autosave_evt = getattr(renpy.loadsave, "autosave_not_running", None)
        if _autosave_evt is not None and not _autosave_evt.is_set():
            _tl_log("TL pre-save skip (autosave): node={}".format(node_index))
            return

        _slot  = _tl_pre_save_slot(node_index, context, ast_key)
        _log   = renpy.game.log
        _saved = list(_log.log)

        try:
            _log.log = _saved[-1:] if _saved else []
            _tl_save_no_screenshot(_slot)

            _path = _os.path.join(renpy.config.savedir, _slot + "-LT1.save")
            _size = _os.path.getsize(_path) if _os.path.exists(_path) else -1
            _tl_log("TL pre-save: node={} slot={} entries={} size={}".format(
                node_index, _slot, len(_saved), _size))

        except Exception as _e:
            _tl_log("TL pre-save error node={}: {} ({})".format(
                node_index, _e, type(_e).__name__))
        finally:
            _log.log = _saved

    def _tl_chap_end_slot_name(label, context=None, after_index=None):
        """Return the save-slot name for a chapter-end checkpoint."""
        if context is not None and after_index is not None:
            h6 = _tl_hashlib.md5(
                repr(tuple(context[:after_index])).encode("utf-8")
            ).hexdigest()[:6]
            return "_ch_chap_{}_{}".format(label, h6)
        return "_ch_chap_{}".format(label)

    def _tl_chap_slot_exists(slot_name, save_dir=None):
        """Return (exists, slot_name) — checks root savedir."""
        import os as _os
        _root = save_dir if save_dir is not None else renpy.config.savedir
        for _ext in ("-LT1.save", ".save"):
            if _os.path.exists(_os.path.join(_root, slot_name + _ext)):
                return True, slot_name
        return False, None

    def _tl_find_nearest_save(target_index, context, save_dir=None,
            start_exists=None, chap_candidates=None, _meta=None):
        """
        Find the chronology save slot with the highest index <= target_index
        that shares the same path prefix as context.

        start_exists: False = skip _ch_start fallback; None = check filesystem;
            True = check filesystem, fall back to bare name if not found.
        chap_candidates: optional list of (after_index, full_slot_name) from
            chapter-end saves, pre-validated by the caller.
        _meta: optional dict; populated with {"index": best_index} when provided.
        Returns slot name or None.
        """
        import os as _os

        _root_dir = save_dir if save_dir is not None else renpy.config.savedir

        best_index = -1
        best_slot  = None

        try:
            for fname in _os.listdir(_root_dir):
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
            _tl_log("TL find_nearest_save scan error: {}".format(e))

        for chap_idx, chap_slot in (chap_candidates or []):
            if chap_idx <= target_index and chap_idx > best_index:
                best_index = chap_idx
                best_slot  = chap_slot

        if best_slot is None and start_exists is not False:
            _start = _os.path.join(_root_dir, "_ch_start-LT1.save")
            if _os.path.exists(_start):
                best_slot = "_ch_start"
                _tl_log("TL find_nearest_save: using _ch_start fallback")
            elif start_exists is True:
                best_slot = "_ch_start"
                _tl_log("TL find_nearest_save: using _ch_start fallback (caller-confirmed)")

        if _meta is not None:
            _meta["index"] = best_index

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
            _tl_save_no_screenshot("_ch_recovery")
            persistent._tl_recovery_slot = "_ch_recovery"

            ## Prefer loading the chapter-end save (captures all state cleanly)
            _marker = next((m for m in store._tl_chapter_markers if m["end_label"] == label), None)
            if _marker is not None:
                _ai   = _marker["after_index"]
                _slot = _tl_chap_end_slot_name(label, store._tl_context, _ai)
            else:
                _slot = _tl_chap_end_slot_name(label)
            _exists, _full_slot = _tl_chap_slot_exists(_slot)
            if _exists:
                store._tl_chap_end_slot = _full_slot
                _tl_log("TL chapter-end jump: loading save={}".format(_full_slot))
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
            _tl_save_no_screenshot("_ch_recovery")
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
            _chap_candidates = []
            for _m in store._tl_chapter_markers:
                _ai = _m["after_index"]
                if _ai > node_index - 1:
                    continue
                _cs = _tl_chap_end_slot_name(_m["end_label"], store._tl_context, _ai)
                _exists, _full_cs = _tl_chap_slot_exists(_cs)
                if _exists:
                    _chap_candidates.append((_ai, _full_cs))

            ## Tier 1: exact pre-save at target — zero skip
            _target_hist = next((n for n in _tl_history if n["index"] == node_index), None)
            _target_ast_key = _tl_derive_node_menu_site_key(_target_hist) if _target_hist else None
            _pre = _tl_find_pre_save(node_index, list(_tl_context), _target_ast_key)
            if _pre is not None:
                _tl_log("TL jump: pre-save found={}".format(_pre))
                store._tl_load_slot = _pre
                return "load"

            ## Tier 2: nearest save (pre or _ch_*) — whichever has the higher index wins
            nearest = _tl_find_nearest_any_save(
                node_index - 1, list(_tl_context), list(_tl_history), _chap_candidates)

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

    ## ── Experimental: pre-save thinning (console-only) ──────────────────────

    _TL_BLOCK_PY = ("renpy.pause(", "renpy.input(", "renpy.call_screen(", "ui.interact(")
    _TL_BLOCK_US = ("imagemap", "call screen")

    def _tl_read_pre_save_roots(slot_name, save_dir=None):
        """
        Read store var snapshot from a pre-save file without loading it.
        Opens the ZIP, reads the 'log' entry, unpickles with renpy.compat.pickle.loads,
        returns the roots dict. Never calls log.unfreeze() — current game state untouched.
        Returns None on any error.
        """
        import zipfile as _zf
        import os as _os
        from renpy.compat.pickle import loads as _loads
        _root = save_dir if save_dir is not None else renpy.config.savedir
        for _ext in ("-LT1.save", ".save"):
            _path = _os.path.join(_root, slot_name + _ext)
            if _os.path.exists(_path):
                try:
                    with _zf.ZipFile(_path, "r") as _z:
                        _log_data = _z.read("log")
                    _roots, _ = _loads(_log_data)
                    return _roots
                except Exception as _e:
                    _tl_log("TL read_pre_save_roots error {}: {}".format(slot_name, _e))
                    return None
        return None

    def _tl_path_has_danger(start_block, roots, label_map, danger_labels):
        """
        Walk forward from a menu option's block, following Jump/Call targets.
        Evaluates If conditions deterministically against roots; conservative fallback
        (follow all branches) when eval fails.
        Returns True if a danger label is reached before any Menu node, else False.
        """
        _work = [start_block]
        _visited_labels = set()
        while _work:
            _block = _work.pop()
            for _node in (_block or []):
                _nt = type(_node).__name__
                if _nt == "Menu":
                    return False
                elif _nt in ("Jump", "Call"):
                    _target = getattr(_node, "target", None)
                    if _target in danger_labels:
                        return True
                    if _target and _target not in _visited_labels and _target in label_map:
                        _visited_labels.add(_target)
                        _work.append(label_map[_target])
                elif _nt == "If":
                    _followed = False
                    for _cond, _eb in (getattr(_node, "entries", None) or []):
                        _cond_str = str(_cond)
                        if _cond_str in ("True", "else"):
                            if _eb:
                                _work.append(_eb)
                            _followed = True
                            break
                        try:
                            _taken = eval(_cond_str, {}, roots)  ## deterministic
                        except Exception:
                            _taken = True  ## conservative: follow this branch
                        if _taken:
                            if _eb:
                                _work.append(_eb)
                            _followed = True
                            break
                    ## if nothing matched, do nothing (branch not taken)
        return False

    def _tl_thin_pre_saves(keep_every=5, dry_run=True, save_dir=None):
        """
        Experimental cleanup: determine which pre-saves are essential for jump replay
        and delete the rest. Console-only — never called automatically.

        Essential = menu N where the AST path between menu N-1's chosen option
        and menu N passes through a blocking interaction (pause, input, call_screen,
        imagemap) that cannot be skip-replayed. Deleting that pre-save would break
        jump replay to menu N.

        False negatives (deleted essential save) = NOT OK.
        False positives (kept non-essential save) = OK — just wastes space.

        keep_every: of non-essential saves, keep every Nth (by node index)
        dry_run: if True, only log — don't delete anything.
        Returns (keep_list, delete_list).
        """
        import os as _os

        _root = save_dir if save_dir is not None else renpy.config.savedir
        _nodes = list(renpy.game.script.namemap.values())

        ## ── Build danger_labels: label names that contain blocking patterns ──
        _danger_labels = set()
        def _dv(_node, _state, _cur_label):
            _nt = type(_node).__name__
            if _nt == "Python":
                _src = getattr(getattr(_node, "code", None), "source", None) or ""
                if any(_p in _src for _p in _TL_BLOCK_PY):
                    _danger_labels.add(_cur_label)
            elif _nt == "UserStatement":
                _line = str(getattr(_node, "line", "") or "")
                if any(_line.startswith(_k) for _k in _TL_BLOCK_US):
                    _danger_labels.add(_cur_label)
            return _state

        _tl_walk_ast_blocks(_nodes, _dv)
        _tl_log("TL thin_pre_saves: {} danger labels".format(len(_danger_labels)))

        ## ── Live menu lookup (keyed by normalized (file, line)) ──
        _live_lookup = _tl_live_menu_lookup()

        ## ── Build label_map: label_name -> block ──
        _label_map = {}
        for _ln in _nodes:
            if type(_ln).__name__ != "Label":
                continue
            _lb = getattr(_ln, "block", None)
            if _lb is not None:
                _label_map[_ln.name] = _lb

        ## ── Scan savedir for _pre_* slots ──
        _pre_slots = {}  ## {slot_name: node_index}
        try:
            for _fname in _os.listdir(_root):
                if not _fname.startswith("_pre_"):
                    continue
                _name  = _fname.replace("-LT1.save", "").replace(".save", "")
                if _name in _pre_slots:
                    continue
                _parts = _name.split("_")
                ## ['', 'pre', '0027', 'hash']
                if len(_parts) < 4:
                    continue
                try:
                    _idx = int(_parts[2])
                except ValueError:
                    continue
                _pre_slots[_name] = _idx
        except Exception as _e:
            _tl_log("TL thin_pre_saves scan error: {}".format(_e))
            return [], []

        if not _pre_slots:
            _tl_log("TL thin_pre_saves: no pre-saves found")
            return [], []

        _tl_log("TL thin_pre_saves: {} pre-saves found".format(len(_pre_slots)))

        ## ── Determine essential saves ──
        ## For each pre-save at index N: read its own history. history[-1] is
        ## the preceding menu node (the last choice made before this save point).
        ## If the chosen option's AST block contains a blocking interaction before
        ## reaching any Menu node, this pre-save is essential for jump replay.
        _essential = set()

        for _slot, _idx in _pre_slots.items():
            _roots = _tl_read_pre_save_roots(_slot, _root)
            if _roots is None:
                ## Cannot read roots — conservative: keep
                _essential.add(_slot)
                continue

            ## RenPy stores store vars as "store.varname" in the roots dict
            _history = _roots.get("store._tl_history") or []
            if not _history:
                ## No preceding menu recorded — skip (cannot determine danger)
                continue

            ## The last entry is the menu immediately before this save point
            _preceding = _history[-1]
            _menu_key  = _tl_derive_node_menu_site_key(_preceding)
            _menu_node = _live_lookup.get(_menu_key) if _menu_key else None

            if _menu_node is None:
                _tl_log("TL thin: no menu node for slot={} key={}, marking essential".format(
                    _slot, _menu_key))
                _essential.add(_slot)
                continue

            ## Find the chosen option block by matching label (not by items index,
            ## because menu.items includes prompt/locked entries absent from options)
            _chosen_index = _preceding.get("chosen_index")
            _options      = _preceding.get("options") or []
            if _chosen_index is None or _chosen_index >= len(_options):
                _essential.add(_slot)
                continue

            _chosen_label = _options[_chosen_index]
            _block = None
            for _item in (getattr(_menu_node, "items", None) or []):
                if isinstance(_item, (list, tuple)) and len(_item) > 2:
                    if _item[0] == _chosen_label:
                        _block = _item[2]
                        break

            if _block is None:
                ## Label not found in AST items — conservative
                _essential.add(_slot)
                continue

            if _tl_path_has_danger(_block, _roots, _label_map, _danger_labels):
                _tl_log("TL thin: idx={} slot={} essential (danger after preceding menu)".format(
                    _idx, _slot))
                _essential.add(_slot)

                ## ── Build keep/delete lists ──
        _keep   = []
        _delete = []

        for _slot, _idx in sorted(_pre_slots.items(), key=lambda x: x[1]):
            if _slot in _essential:
                _keep.append(_slot)
                _tl_log("TL thin: keep {} (essential)".format(_slot))
            elif _idx % keep_every == 0:
                _keep.append(_slot)
                _tl_log("TL thin: keep {} (periodic {})".format(_slot, keep_every))
            else:
                _delete.append(_slot)
                _tl_log("TL thin: delete {}".format(_slot))

        _tl_log("TL thin_pre_saves: keep={} delete={} dry_run={}".format(
            len(_keep), len(_delete), dry_run))

        if not dry_run:
            for _slot in _delete:
                for _ext in ("-LT1.save", ".save"):
                    _path = _os.path.join(_root, _slot + _ext)
                    if _os.path.exists(_path):
                        try:
                            _os.remove(_path)
                            _tl_log("TL thin: removed {}".format(_path))
                        except Exception as _e:
                            _tl_log("TL thin: remove error {}: {}".format(_path, _e))

        return _keep, _delete

    ## ── End experimental ─────────────────────────────────────────────────────

    def _tl_cancel_replay():
        slot = persistent._tl_recovery_slot
        ## Snapshot all current node thumbnails into cache before loading
        ## the recovery save. After load, _tl_history will be restored from
        ## the save state — but the cache persists, so thumbnails are available.
        try:
            _tl_tc = getattr(renpy.game, "_tl_thumb_cache", {})
            for n in _tl_history:
                key = str(n.get("ast_key")) if n.get("ast_key") else None
                if key and n.get("thumb_bytes") and key not in _tl_tc:
                    _tl_tc[key] = n["thumb_bytes"]
                    n["thumb_bytes"] = None  ## cleared — served from cache
                    while len(_tl_tc) > TL_THUMB_CACHE_MAX:
                        _tl_tc.pop(next(iter(_tl_tc)))
        except Exception as e:
            _tl_log("TL cancel_replay cache error: {}".format(e))
        _tl_clear_replay_state()  ## clears _tl_recovery_slot
        if slot:
            store._tl_load_slot = slot
            return slot
        return None
