## =============================================================================
## CHRONOLOGY MOD — timeline_init.rpy
## Store variables, persistent data, constants, and utility functions.
## =============================================================================

init -2 python:

    import os, uuid, time as _tl_time, json as _tl_json
    import hashlib as _tl_hashlib
    try:
        import __builtin__ as _tl_builtins
    except ImportError:
        import builtins as _tl_builtins

    _tl_builtin_id = _tl_builtins.id

    ## Capture builtins before game characters can shadow them.
    _TL_MIN = min
    _TL_MAX = max

    def _tl_log(msg):
        try:
            _dbpath = os.path.join(renpy.config.gamedir, "renpy-chronology-mod", "debug.txt")
            with open(_dbpath, "a") as _f:
                _f.write(msg + "\n")
        except Exception:
            pass

    ## Thumbnail dimensions
    TL_THUMB_WIDTH  = 320
    TL_THUMB_HEIGHT = 180

    TL_SAVE_EVERY       = 10   ## write a checkpoint save every N choices
    TL_DENSE_SAVES      = 5    ## save every choice for the first N nodes
    TL_THUMB_CACHE_MAX  = 500  ## max thumbnails (~25MB at ~50KB/thumb)
    TL_DEBUG_GHOST      = False   ## ghost synthesis detail (if-execute, clustering, branch-img, image resolution)
    TL_DEBUG_SEEN       = False   ## seen-state resolution detail (opt_seen, peek_seen)
    TL_DEBUG_ROUTE      = False   ## route tracker detail (var diff per Python block, default walk detail)
    TL_DEBUG_MENU       = False   ## per-menu pipeline detail (menu enter, img_name, shadow path consumption)
    TL_DEBUG_ASSET      = False   ## thumbnail cache detail (hit/generated, scene map updates)

    def _tl_runtime_cache_store():
        """
        Return a transient runtime cache dict hung off `renpy.game.script`.

        This keeps live AST objects and other heavyweight helpers out of the
        save payload while preserving simple in-session memoization.
        """
        try:
            _script = renpy.game.script
        except Exception:
            return {}
        _cache = getattr(_script, "_tl_runtime_cache_store", None)
        if not isinstance(_cache, dict):
            _cache = {}
            try:
                setattr(_script, "_tl_runtime_cache_store", _cache)
            except Exception:
                return {}
        return _cache

    def _tl_runtime_choice_returns(node, create=False):
        """Return transient choice-return slots for one history node."""
        if not isinstance(node, dict):
            return None
        _rt = _tl_runtime_cache_store()
        _cache = _rt.setdefault("choice_returns", {})
        _key = _tl_builtin_id(node)
        if create and _key not in _cache:
            _cache[_key] = [None] * len(node.get("options", []))
        return _cache.get(_key) or node.get("_choice_returns")

    ## -------------------------------------------------------------------------
    ## Font size constants
    ## -------------------------------------------------------------------------
    TL_SIZE_BODY     = 21   ## all regular text — options, labels, buttons
    TL_SIZE_TITLE    = 38   ## "CHRONOLOGY" header
    TL_SIZE_DOT      = 14   ## ● indicator dots
    TL_SIZE_BADGE    = 12   ## small labels
    TL_SIZE_HEADER   = 28   ## modal header
    TL_SIZE_SUBTITLE = 17   ## secondary info lines (var deltas, conditions)

    _tl_chapters = _tl_load_chapters()   ## {display_name: end_label}

## Per-save variables — safe to load on saves that predate the mod
default _tl_history    = []   ## list of node dicts
default _tl_branch_id  = ""   ## unique branch ID, set on first menu
default _tl_context    = []   ## [(prompt, chosen_index), ...]
default _tl_node_count = 0

## UI state — not saved
default _tl_modal_node  = None  ## node whose modal is currently open
default _tl_load_slot   = ""    ## slot to load via _tl_do_load label
default _tl_label_jump  = ""    ## label to jump to via _tl_do_label_jump
default _tl_chapter_markers = []  ## [{chapter_name, end_label, after_index}] — recorded immediately at chapter end labels
default _tl_pending_save_index    = None  ## legacy — checkpoint writes removed; kept for old saves/tests
default _tl_early_save_idx        = None  ## legacy — checkpoint writes removed; kept for old saves/tests
default _tl_chap_end_slot         = ""    ## load-slot for chapter-end jump (or "" = jump fallback)
default _tl_ast_ready  = False  ## True once AST map is built
default _tl_shadow_path = None  ## [{location, chosen_index}] replay-aid hints, or None
default _tl_ghost_nodes      = []   ## ghost dicts for If branches in current scene segment
default _tl_skip_ghost_ifs   = set()   ## ast_keys whose sibling rows are already emitted
default _tl_pending_var_changes = {} ## {var_name: (old_val, new_val)} — flushed to notify, then cleared
default _tl_menu_var_snap = None    ## pre-menu route var snapshot for next-menu var-change attribution
default _tl_recently_changed_vars = set()  ## vars changed since last menu; cleared at _tl_record_before
default _tl_var_if_seen_keys = {}   ## {var_name: set(ast_keys)} — If nodes executed this session

## Replay state — stored in persistent so it survives a save/load cycle.
init python:
    if persistent._tl_replaying is None:
        persistent._tl_replaying = False
    if not hasattr(persistent, "_tl_img_movie_cache") or persistent._tl_img_movie_cache is None:
        persistent._tl_img_movie_cache = {}
    if not hasattr(persistent, "_tl_pending_shadow_path"):
        persistent._tl_pending_shadow_path = None

    if not hasattr(persistent, "_tl_var_notifs_enabled") or persistent._tl_var_notifs_enabled is None:
        persistent._tl_var_notifs_enabled = False

    if not hasattr(persistent, "_tl_asset_thumb_dirty"):
        persistent._tl_asset_thumb_dirty = False

    if not hasattr(persistent, "_tl_ghost_node_cache") or persistent._tl_ghost_node_cache is None:
        persistent._tl_ghost_node_cache = {}

    if persistent._tl_scene_map_version is None or persistent._tl_scene_map_version < 3:
        persistent._tl_menu_scene_map = {}
        persistent._tl_scene_map_version = 3
    elif persistent._tl_menu_scene_map is None:
        persistent._tl_menu_scene_map = {}

    ## ── Thumbnail cache — kept in renpy.game attrs (not persistent) ──────────
    ## renpy.game is a Python module object whose attrs survive renpy.load() but
    ## are not serialised by save_persistent(). This keeps persistent small so
    ## save_persistent() is fast during jumps.
    ## Cache is loaded from a pickle file at startup and written back at quit.
    import os as _os, gzip as _gz
    _tl_thumbs_path = _os.path.join(renpy.config.savedir, "_tl_thumbs.pkl")
    try:
        from renpy.compat.pickle import loads as _pl
        if _os.path.exists(_tl_thumbs_path):
            try:
                with _gz.open(_tl_thumbs_path, "rb") as _f:
                    _raw = _f.read()
                _d = _pl(_raw)
                _tl_log("TL thumbs loaded (gzip): thumb={} asset={}".format(
                    len(_d.get("thumb", {})), len(_d.get("asset_thumb", {}))))
            except Exception as _gz_e:
                _tl_log("TL thumbs gzip load error: {} — trying raw".format(_gz_e))
                try:
                    with open(_tl_thumbs_path, "rb") as _f:
                        _d = _pl(_f.read())
                    _tl_log("TL thumbs loaded (raw): thumb={} asset={}".format(
                        len(_d.get("thumb", {})), len(_d.get("asset_thumb", {}))))
                except Exception as _raw_e:
                    _tl_log("TL thumbs raw load error: {}".format(_raw_e))
                    _d = {}
            renpy.game._tl_thumb_cache      = _d.get("thumb", {})
            renpy.game._tl_asset_thumb_cache = _d.get("asset_thumb", {})
        else:
            _tl_log("TL thumbs init: no pkl file — starting empty")
            renpy.game._tl_thumb_cache      = {}
            renpy.game._tl_asset_thumb_cache = {}
    except Exception as _e:
        _tl_log("TL thumbs load error: {}".format(_e))
        renpy.game._tl_thumb_cache      = {}
        renpy.game._tl_asset_thumb_cache = {}

    ## One-time migration: drain any existing persistent caches into renpy.game.
    ## After this run persistent._tl_thumb_cache / _tl_asset_thumb_cache stay empty.
    _mig_thumb  = len(getattr(persistent, "_tl_thumb_cache", None) or {})
    _mig_asset  = len(getattr(persistent, "_tl_asset_thumb_cache", None) or {})
    if _mig_thumb:
        renpy.game._tl_thumb_cache.update(persistent._tl_thumb_cache)
        persistent._tl_thumb_cache = {}
    if _mig_asset:
        renpy.game._tl_asset_thumb_cache.update(persistent._tl_asset_thumb_cache)
        persistent._tl_asset_thumb_cache = {}
    if _mig_thumb or _mig_asset:
        _tl_log("TL thumbs migration: moved thumb={} asset={} from persistent".format(
            _mig_thumb, _mig_asset))
        if _mig_asset:
            persistent._tl_asset_thumb_dirty = True

    def _tl_save_thumbs():
        import os as _os, gzip as _gz
        _tc  = getattr(renpy.game, "_tl_thumb_cache", None)
        _atc = getattr(renpy.game, "_tl_asset_thumb_cache", None)
        _dirty = getattr(persistent, "_tl_asset_thumb_dirty", False)
        _has_replay_thumbs = bool(_tc)
        _path = _os.path.join(renpy.config.savedir, "_tl_thumbs.pkl")
        _no_file = not _os.path.exists(_path)
        _has_asset_thumbs = bool(_atc)
        if not _dirty and not _has_replay_thumbs and not (_no_file and _has_asset_thumbs):
            _tl_log("TL thumbs save skipped: cache unchanged")
            return
        try:
            from renpy.compat.pickle import dumps as _pd
            _d = {
                "thumb":       _tc or {},
                "asset_thumb": _atc or {},
            }
            with _gz.open(_path, "wb", compresslevel=1) as _f:
                _f.write(_pd(_d))
            _tl_log("TL thumbs saved: thumb={} asset={}".format(
                len(_d["thumb"]), len(_d["asset_thumb"])))
            persistent._tl_asset_thumb_dirty = False
            renpy.save_persistent()
        except Exception as _e:
            _tl_log("TL thumbs save error: {}".format(_e))

    config.quit_callbacks.append(_tl_save_thumbs)


init -2 python:

    def _tl_new_branch_id():
        return uuid.uuid4().hex[:12]

    def _tl_count_locked_branches():
        _descs = getattr(persistent, "_tl_all_branch_descs", None) or []
        return sum(1 for _d in _descs if not _tl_eval_seen_fn(_d))


    def _tl_build_ast_map():
        try:
            namemap = renpy.game.script.namemap
        except Exception as e:
            _tl_log("TL AST: namemap not available: {}".format(e))
            store._tl_ast_ready = True
            return

        nodes = list(namemap.values())
        if not nodes:
            store._tl_ast_ready = True
            return

        _tl_log("TL AST: scanning {} named nodes".format(len(nodes)))
        store._tl_ast_ready = True

        _tl_build_route_index(nodes)
        _tl_build_coverage_index(nodes)
        _tl_build_menu_scene_index(nodes)


    def _tl_salvage_history_ast_keys(line_slop=100):
        """
        Re-match stale history ast_keys to current AST menus after a game script update.

        A node is stale when its ast_key is not present in the live menu lookup.
        Matching uses content (history options ⊆ live menu labels) as the primary
        signal and line proximity (within line_slop) as secondary. A used-key set
        prevents two history nodes from claiming the same live menu.

        On match: re-stamps ast_key and clears img_name so _tl_migrate_img_names()
        can refill it from the current scene map.

        Returns {skipped, matched, unmatched, total}.
        User-triggered only — not called automatically on load.
        """
        _live    = _tl_live_menu_lookup()
        _history = getattr(store, "_tl_history", [])
        if not _history:
            _msg = "Salvage: nothing to do (empty history)"
            _tl_log("TL salvage: " + _msg)
            renpy.notify(_msg)
            return {"skipped": 0, "matched": 0, "unmatched": 0, "total": 0}

        ## Build candidate map: filename -> sorted [(line, menu_node)]
        _by_file = {}
        for (_cfile, _cline), _cmenu in _live.items():
            _by_file.setdefault(_cfile, []).append((_cline, _cmenu))
        for _lst in _by_file.values():
            _lst.sort()

        _skipped       = 0
        _matched       = 0
        _unmatched     = 0
        _any_matched   = False
        _used_keys     = set()   ## live (file, line) keys claimed by a resolved stale key
        _stale_to_live = {}      ## stale (file, line) -> live (file, line) or None

        for _n in _history:
            _ak = _n.get("ast_key")
            if not isinstance(_ak, (list, tuple)) or len(_ak) != 2:
                _unmatched += 1
                continue
            _ak = tuple(_ak)
            _stored_file, _stored_line = _ak

            ## Already valid — live menu exists at this exact key
            if _ak in _live:
                _skipped += 1
                continue

            ## Same stale key seen before (e.g. looping menu) — reuse cached result
            if _ak in _stale_to_live:
                _cached = _stale_to_live[_ak]
                if _cached is None:
                    _unmatched += 1
                else:
                    _live_menu = _live[_cached]
                    _n["ast_key"]  = (_live_menu.filename, _live_menu.linenumber)
                    _n["img_name"] = None
                    _matched    += 1
                    _any_matched = True
                continue

            ## Stale and unseen — search candidates in same file
            _candidates   = _by_file.get(_stored_file, [])
            _history_opts = frozenset(_n.get("options") or [])

            _best      = None
            _best_dist = line_slop + 1
            for (_cline, _cmenu) in _candidates:
                _ckey = (_stored_file, _cline)
                if _ckey in _used_keys:
                    continue                   ## already claimed by a different stale key
                _live_labels = frozenset(
                    _item[0] for _item in (_cmenu.items or []) if _item[2] is not None
                )
                if not (_history_opts <= _live_labels):
                    continue                   ## content mismatch
                _dist = abs(_stored_line - _cline)
                if _dist <= line_slop and _dist < _best_dist:
                    _best      = (_cline, _cmenu)
                    _best_dist = _dist

            if _best is None:
                _stale_to_live[_ak] = None
                _unmatched += 1
                _tl_log("TL salvage: node={} {}:{} -> unmatched (opts={})".format(
                    _n.get("index"), _stored_file, _stored_line, len(_history_opts)))
                continue

            _new_line, _new_menu = _best
            _new_key              = (_stored_file, _new_line)
            _stale_to_live[_ak]  = _new_key
            _used_keys.add(_new_key)
            _n["ast_key"]  = (_new_menu.filename, _new_menu.linenumber)
            _n["img_name"] = None
            _matched    += 1
            _any_matched = True
            _tl_log("TL salvage: node={} {} {}->{}".format(
                _n.get("index"), _stored_file, _stored_line, _new_line))

        if _any_matched:
            _tl_migrate_img_names()
            renpy.save_persistent()

        _msg = "Salvage: {} matched / {} missed / {} ok".format(_matched, _unmatched, _skipped)
        _tl_log("TL salvage: total={} matched={} unmatched={} skipped={}".format(
            len(_history), _matched, _unmatched, _skipped))
        renpy.notify(_msg)
        return {"skipped": _skipped, "matched": _matched, "unmatched": _unmatched, "total": len(_history)}


    def _tl_migrate_img_names():
        """
        Stamp img_name on history nodes that are missing it, using the persistent
        menu image map. Runs once per load (store flag guards re-entry from timeline screen).
        """
        _scene_map = persistent._tl_menu_scene_map or {}
        if not _scene_map:
            return
        _history  = getattr(store, "_tl_history", [])
        _changed  = 0
        _misses   = 0
        for _n in _history:
            if _n.get("img_name") is not None:
                continue
            _k = _n.get("ast_key")
            _ast_key = _tl_menu_site_key(_k[0], _k[1]) if isinstance(_k, tuple) and len(_k) == 2 else None
            _loc_key = _tl_location_menu_site_key(_n.get("_location"))
            if _ast_key and _ast_key in _scene_map:
                _n["img_name"] = _scene_map[_ast_key]
                _changed += 1
            elif _loc_key and _loc_key in _scene_map:
                _n["img_name"] = _scene_map[_loc_key]
                _changed += 1
            else:
                _misses += 1
        _tl_log("TL img migration: total={} changed={} misses={}".format(
            len(_history), _changed, _misses))


