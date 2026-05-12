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
    TL_PROFILE_TIMELINE = False
    _tl_timeline_perf_stats = {}

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

    def _tl_perf_mark():
        if not TL_PROFILE_TIMELINE:
            return None
        try:
            return _tl_time.perf_counter()
        except Exception:
            return None

    def _tl_perf_add(label, started_at):
        if not TL_PROFILE_TIMELINE or started_at is None:
            return
        try:
            _elapsed_ms = (_tl_time.perf_counter() - started_at) * 1000.0
            _stats = _tl_timeline_perf_stats.setdefault(label, {
                "calls": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
            })
            _stats["calls"] += 1
            _stats["total_ms"] += _elapsed_ms
            if _elapsed_ms > _stats["max_ms"]:
                _stats["max_ms"] = _elapsed_ms
        except Exception:
            pass

    def _tl_perf_reset(scope):
        if not TL_PROFILE_TIMELINE:
            return None
        try:
            _tl_timeline_perf_stats.clear()
        except Exception:
            pass
        return _tl_perf_mark()

    def _tl_perf_dump(scope, started_at=None):
        if not TL_PROFILE_TIMELINE:
            return
        try:
            _total_ms = None
            if started_at is not None:
                _total_ms = (_tl_time.perf_counter() - started_at) * 1000.0
            _parts = []
            if _total_ms is not None:
                _parts.append("total={:.2f}ms".format(_total_ms))
            for _label in sorted(_tl_timeline_perf_stats.keys()):
                _stats = _tl_timeline_perf_stats.get(_label) or {}
                _parts.append(
                    "{}:calls={} total={:.2f}ms max={:.2f}ms".format(
                        _label,
                        int(_stats.get("calls", 0) or 0),
                        float(_stats.get("total_ms", 0.0) or 0.0),
                        float(_stats.get("max_ms", 0.0) or 0.0),
                    )
                )
            if _parts:
                _tl_log("TL PERF {} | {}".format(scope, " | ".join(_parts)))
        except Exception:
            pass

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
default _tl_pending_save_index    = None  ## node index to save after next interact
default _tl_early_save_idx        = None  ## idx of save needing refresh after untracked menus
default _tl_chap_end_slot         = ""    ## load-slot for chapter-end jump (or "" = jump fallback)
default _tl_ast_ready  = False  ## True once AST map is built
default _tl_ast_map    = {}     ## {(filename, line): [seen_fn, ...]} — RenPy 7 fallback
default _tl_shadow_path = None  ## [{location, chosen_index}] replay-aid hints, or None
default _tl_ghost_nodes      = []    ## ghost dicts for If branches in current scene segment
default _tl_ghost_highlight  = None  ## (ast_key, branch_index) or None — selected branch row

## Replay state — stored in persistent so it survives a save/load cycle.
init python:
    if persistent._tl_replaying is None:
        persistent._tl_replaying = False
    if persistent._tl_thumb_cache is None:
        persistent._tl_thumb_cache = {}
    if not hasattr(persistent, "_tl_asset_thumb_cache") or persistent._tl_asset_thumb_cache is None:
        persistent._tl_asset_thumb_cache = {}
    if not hasattr(persistent, "_tl_img_movie_cache") or persistent._tl_img_movie_cache is None:
        persistent._tl_img_movie_cache = {}
    if not hasattr(persistent, "_tl_pending_shadow_path"):
        persistent._tl_pending_shadow_path = None
    if persistent._tl_scene_map_version is None or persistent._tl_scene_map_version < 3:
        persistent._tl_menu_scene_map = {}
        persistent._tl_scene_map_version = 3
    elif persistent._tl_menu_scene_map is None:
        persistent._tl_menu_scene_map = {}


init -2 python:

    def _tl_new_branch_id():
        return uuid.uuid4().hex[:12]


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
        ast_map = {}

        for node in nodes:
            if type(node).__name__ != "Menu":
                continue
            key      = (node.filename, node.linenumber)
            seen_fns = []
            for item in node.items:
                block = item[2] if len(item) > 2 else None
                if not block:
                    continue
                seen_fns.append(_tl_make_seen_fn(block))
            if seen_fns:
                ast_map[key] = seen_fns

        store._tl_ast_map   = ast_map
        store._tl_ast_ready = True
        _tl_log("TL AST done: {} menus".format(len(ast_map)))

        ## Build persistent scene-before-menu map for backfill only.
        ## Runtime-captured menu images are authoritative and overwrite this map.
        _new_scene_entries = [0]
        def _walk_menu_imgs(_cur, _last_img, _seen):
            while _cur is not None:
                _nid = _tl_builtin_id(_cur)
                if _nid in _seen:
                    return
                _seen.add(_nid)
                _nt = type(_cur).__name__
                if _nt in ("Scene", "Show"):
                    _img = _tl_scene_stmt_img_name(_cur)
                    if _img:
                        _last_img = _img
                elif _nt == "Menu":
                    _mk = _tl_menu_site_key(_cur.filename, _cur.linenumber)
                    if _mk not in persistent._tl_menu_scene_map and _last_img:
                        persistent._tl_menu_scene_map[_mk] = _last_img
                        _new_scene_entries[0] += 1
                    elif _mk not in persistent._tl_menu_scene_map and not _last_img:
                        _tl_log("TL ast-walk miss: menu=({},{}) last_img=None".format(_cur.filename, _cur.linenumber))
                    return
                elif _nt == "Jump":
                    _target = getattr(_cur, "target", None)
                    if _target:
                        _jnode = namemap.get(_target)
                        if _jnode is not None:
                            _walk_menu_imgs(getattr(_jnode, "next", None), _last_img, set(_seen))
                    return
                elif _nt in ("Return", "Call"):
                    return
                _cur = getattr(_cur, "next", None)

        for _ln in (n for n in nodes if type(n).__name__ == "Label"):
            _walk_menu_imgs(getattr(_ln, "next", None), None, set())
        if _new_scene_entries[0]:
            _tl_log("TL menu_scene_map: {} new entries cached".format(_new_scene_entries[0]))


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
