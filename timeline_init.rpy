## =============================================================================
## CHRONOLOGY MOD — timeline_init.rpy
## Store variables, persistent data, constants, and utility functions.
## =============================================================================

init -2 python:

    import os, uuid, json as _tl_json
    import hashlib as _tl_hashlib

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

    ## -------------------------------------------------------------------------
    ## Font size constants
    ## -------------------------------------------------------------------------
    TL_SIZE_BODY   = 21   ## all regular text — options, labels, buttons
    TL_SIZE_TITLE  = 38   ## "CHRONOLOGY" header
    TL_SIZE_DOT    = 14   ## ● indicator dots
    TL_SIZE_BADGE  = 12   ## small labels
    TL_SIZE_HEADER = 28   ## modal header

    def _tl_load_chapters():
        path = os.path.join(renpy.config.gamedir, "renpy-chronology-mod", "chapters.json")
        try:
            with open(path, "r") as _f:
                raw = _tl_json.load(_f)
        except Exception:
            return {}
        seen_labels = {}
        deduped = {}
        for _ch_name, _ch_label in raw.items():
            if _ch_name.startswith("_"):
                continue
            if _ch_label in seen_labels:
                _tl_log("TL WARNING chapters.json: label '{}' mapped to both '{}' and '{}'; '{}' wins".format(
                    _ch_label, seen_labels[_ch_label], _ch_name, seen_labels[_ch_label]))
            else:
                seen_labels[_ch_label] = _ch_name
                deduped[_ch_name] = _ch_label
        return deduped

    _tl_chapters = _tl_load_chapters()   ## {display_name: end_label}

    def _tl_begin_label_jump(label):
        try:
            renpy.save("_ch_recovery")
            persistent._tl_recovery_slot = "_ch_recovery"

            ## Prefer loading the chapter-end save (captures all state cleanly)
            import os as _os
            _slot = "_ch_chap_{}".format(label)
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
            store._tl_label_jump = label
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
default _tl_pending_chap_end_save = None  ## end_label to save at next interact
default _tl_chap_end_slot         = ""    ## load-slot for chapter-end jump (or "" = jump fallback)
default _tl_ast_ready  = False  ## True once AST map is built
default _tl_ast_map    = {}     ## {(filename, line): [seen_fn, ...]} — RenPy 7 fallback

## Replay state — stored in persistent so it survives a save/load cycle.
init python:
    if persistent._tl_replaying is None:
        persistent._tl_replaying = False
    if persistent._tl_thumb_cache is None:
        persistent._tl_thumb_cache = {}


init -2 python:

    def _tl_new_branch_id():
        return uuid.uuid4().hex[:12]

    def _tl_should_save(idx, dense=None, every=None):
        """Return True if a checkpoint save should be written for this node index."""
        d = dense if dense is not None else TL_DENSE_SAVES
        e = every if every is not None else TL_SAVE_EVERY
        return idx < d or idx % e == e - 1

    def _tl_save_slot(node_index, context):
        raw = repr(tuple(context))
        h6  = _tl_hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
        return "_ch_{:04d}_{}".format(node_index, h6)

    def _tl_find_nearest_save(target_index, context):
        """
        Find the chronology save slot with the highest index <= target_index
        that shares the same path prefix as context.
        Returns slot name (without extension) or None.
        """
        import os as _os
        best_index = -1
        best_slot  = None
        try:
            save_dir = renpy.config.savedir
            for fname in _os.listdir(save_dir):
                if not fname.startswith("_ch_"):
                    continue
                if "recovery" in fname or "start" in fname:
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
                expected_h6 = _tl_hashlib.md5(repr(tuple(ctx_at_idx)).encode("utf-8")).hexdigest()[:6]
                if parts[3] != expected_h6:
                    continue
                if idx > best_index:
                    best_index = idx
                    best_slot  = name
        except Exception as e:
            _tl_log("TL find_nearest_save error: {}".format(e))

        if best_slot is None:
            import os as _os2
            start_file = _os2.path.join(renpy.config.savedir, "_ch_start-LT1.save")
            if _os2.path.exists(start_file):
                best_slot = "_ch_start"
                _tl_log("TL find_nearest_save: using _ch_start fallback")

        return best_slot

    _tl_im_Data = renpy.display.im.Data   ## canonical path; works RenPy 7 + 8, no deprecation warning

    def _tl_capture_thumbnail():
        ## screenshot_to_bytes was added in RenPy 7.5. Older versions lack a
        ## supported API for in-memory screenshot capture — the internal fallback
        ## (draw.screenshot) produces black images on 7.4.x due to a flip-ordering
        ## bug in the GL2 renderer. Thumbnails are silently skipped on < 7.5;
        ## the rest of the mod (choice tracking, dots, jump-back) still works.
        if not hasattr(renpy, "screenshot_to_bytes"):
            return None
        try:
            return renpy.screenshot_to_bytes((TL_THUMB_WIDTH, TL_THUMB_HEIGHT))
        except Exception as e:
            _tl_log("TL screenshot failed: {}".format(e))
            return None

    def _tl_thumb_displayable(thumb_bytes, index):
        try:
            ## Detect image format from magic bytes so im.Data decodes correctly
            ## regardless of what screenshot_to_bytes returns (JPEG on older RenPy,
            ## PNG or WebP on newer).
            if thumb_bytes[:4] == b"RIFF" and thumb_bytes[8:12] == b"WEBP":
                ext = "webp"
            elif thumb_bytes[:2] == b"\xff\xd8":
                ext = "jpg"
            else:
                ext = "png"
            return _tl_im_Data(thumb_bytes, "tl_t_{}.{}".format(index, ext))
        except Exception as e:
            _tl_log("TL thumb displayable failed: {}".format(e))
            return None

    ## -------------------------------------------------------------------------
    ## AST-based seen checking — RenPy 7 fallback only.
    ## -------------------------------------------------------------------------

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


    def _tl_make_seen_fn(block):
        ## Returns a picklable descriptor tuple, not a lambda.
        ## ("never",)        — always unseen
        ## ("say",  name)    — check persistent._seen_ever
        ## ("label", target) — check renpy.seen_label
        if not block:
            return ("never",)

        def find_check(start_node, max_hops=40):
            node = start_node
            hops = 0
            while node is not None and hops < max_hops:
                stype = type(node).__name__
                if stype == "Say":
                    node_name = getattr(node, "name", None)
                    if node_name is not None:
                        return ("say", node_name)
                    return ("never",)
                elif stype == "Jump":
                    target = getattr(node, "target", None)
                    if target:
                        return ("label", target)
                    return ("never",)
                elif stype == "Call":
                    target = getattr(node, "label", None)
                    if target and isinstance(target, str):
                        return ("label", target)
                    return ("never",)
                elif stype == "Label":
                    target = getattr(node, "name", None)
                    if target and isinstance(target, str):
                        return ("label", target)
                    node = getattr(node, "next", None)
                    hops += 1
                    continue
                elif stype in ("Return", "Menu"):
                    return ("never",)
                node = getattr(node, "next", None)
                hops += 1
            return ("never",)

        for stmt in block:
            return find_check(stmt)
        return ("never",)


    def _tl_option_seen(node, option_index):
        crs = node.get("_choice_returns", [])
        if option_index < len(crs):
            cr = crs[option_index]
            if cr is not None:
                try:
                    return bool(cr.get_chosen())
                except Exception:
                    pass
        key  = node.get("ast_key")
        desc = (_tl_ast_map.get(key, []) if key else [])
        if option_index < len(desc):
            try:
                d = desc[option_index]
                if d[0] == "say":
                    return d[1] in (persistent._seen_ever or {})
                elif d[0] == "label":
                    return renpy.seen_label(d[1])
            except Exception:
                pass
        return False


    def _tl_node_has_new(node):
        for i in range(len(node.get("options", []))):
            if not _tl_option_seen(node, i):
                return True
        return False


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
            persistent._tl_replaying = True
            renpy.save_persistent()

            ## ── Save+skip ────────────────────────────────────────────────────
            nearest = _tl_find_nearest_save(node_index - 1, list(_tl_context))

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


    def _tl_clear_thumb_cache():
        persistent._tl_thumb_cache = {}
        renpy.save_persistent()
        renpy.notify("Chronology: thumbnail cache cleared.")

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
