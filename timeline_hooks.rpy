## =============================================================================
## CHRONOLOGY MOD — timeline_hooks.rpy
## =============================================================================

init -1 python:

    def _tl_resolve_node_location():
        """
        Return (ast_key, location, node_type) for the current execution context.
        ast_key is (filename, linenumber) when the current node is a named AST node,
        else None. location is the raw context.current label string.
        """
        location  = None
        ast_key   = None
        node_type = None
        try:
            current = renpy.game.context().current
            if current is not None:
                location = current
                node_obj = renpy.game.script.namemap.get(current)
                if node_obj is not None:
                    node_type = type(node_obj).__name__
                    ast_key   = (node_obj.filename, node_obj.linenumber)
        except Exception as e:
            _tl_log("TL location lookup failed: {}".format(e))
        return ast_key, location, node_type

    def _tl_resolve_img_name(ast_key, location):
        """
        Return img_name for the current menu.
        Live scene resolution is authoritative and updates the persistent map;
        persistent map by ast_key or location key is the fallback.
        """
        ast_site_key = (_tl_menu_site_key(ast_key[0], ast_key[1])
                        if isinstance(ast_key, tuple) and len(ast_key) == 2 else None)
        img_name = None
        if not persistent._tl_replaying and not config.skipping:
            img_name = _tl_resolve_live_menu_img_name()
            if img_name and ast_site_key:
                persistent._tl_menu_scene_map[ast_site_key] = img_name
        if not img_name:
            img_cache = persistent._tl_menu_scene_map or {}
            loc_key   = _tl_location_menu_site_key(location)
            if ast_site_key and ast_site_key in img_cache:
                img_name = img_cache[ast_site_key]
            elif loc_key and loc_key in img_cache:
                img_name = img_cache[loc_key]
        if TL_DEBUG_MENU:
            _tl_log("TL img_name: ast_key={} img_name={}".format(ast_key, img_name))
        return img_name

    def _tl_capture_thumb(node, ast_key):
        """
        Capture or restore a screenshot thumbnail for the given menu node.
        Uses the runtime thumb cache; only captures when not replaying and not skipping.
        Sets node["thumb_bytes"] directly when the cache is unavailable.
        """
        need_frozen_thumb = bool(node["img_name"] and _tl_img_name_is_movie(node["img_name"]))
        if node["img_name"] and not need_frozen_thumb:
            return
        cache_key    = str(ast_key) if ast_key else None
        thumb_cache  = getattr(renpy.game, "_tl_thumb_cache", {})
        cached_thumb = thumb_cache.get(cache_key) if cache_key else None
        if not persistent._tl_replaying and not cached_thumb and not config.skipping:
            thumb = _tl_capture_thumbnail()
            if thumb:
                if cache_key:
                    try:
                        thumb_cache[cache_key] = thumb
                        while len(thumb_cache) > TL_THUMB_CACHE_MAX:
                            thumb_cache.pop(next(iter(thumb_cache)))
                    except Exception as e:
                        _tl_log("TL thumb cache write failed: {}".format(e))
                        node["thumb_bytes"] = thumb
                else:
                    node["thumb_bytes"] = thumb
        if need_frozen_thumb and TL_DEBUG_MENU:
            _tl_log("TL movie thumb fallback: ast_key={} img_name={}".format(ast_key, node["img_name"]))

    def _tl_record_before(items):
        if not hasattr(store, "_tl_history"):
            return None  ## store defaults not yet applied (pre-game-start menu)
        global _tl_node_count, _tl_history, _tl_context

        ## Flush immediate var changes (non-init) and init-in-arm changes (from menu snap).
        ## When notifs disabled: discard pending dict so enabling mid-session starts clean.
        try:
            if getattr(persistent, "_tl_var_notifs_enabled", True):
                _tl_flush_var_changes()
                _tl_flush_menu_snap()
            else:
                store._tl_pending_var_changes = {}
                store._tl_menu_var_snap = None
        except Exception as e:
            _tl_log("TL var flush error: {}".format(e))

        ## Ghost nodes accumulated since last menu are now resolved — clear them.
        store._tl_ghost_nodes          = []
        store._tl_skip_ghost_ifs       = set()
        store._tl_recently_changed_vars = set()

        ast_key, location, node_type = _tl_resolve_node_location()

        ## Snapshot for synthetic jump — captured before the menu fires so get_roots()
        ## does not yet include this node. Stored in renpy.game.log._tl_snapshot_cache
        ## (not in the store) so it travels with every save without appearing in roots.
        snap = None
        if not persistent._tl_replaying:
            try:
                snap = _tl_capture_snapshot()
                _tl_log("TL snapshot: idx={} ctx={} roots_keys={}".format(
                    _tl_node_count,
                    getattr(snap["context"], "current", "?"),
                    len(snap["roots"])
                ))
            except Exception as e:
                _tl_log("TL snapshot ERROR idx={}: {}".format(_tl_node_count, e))

        prompt, valid_items = _tl_parse_menu_items(items)
        if not valid_items:
            return None

        ## During replay, reuse the existing node from history rather than
        ## creating a new one. This preserves the original thumbnail and
        ## choice_returns so dot logic and display stay correct.
        if persistent._tl_replaying:
            target = persistent._tl_replay_target
            for existing in _tl_history:
                if existing["index"] == _tl_node_count:
                    ## Restore N-1 thumbnail from snapshot if present
                    if (target and existing["index"] == target["node_index"] - 1
                            and persistent._tl_prev_thumb):
                        existing["thumb_bytes"]   = persistent._tl_prev_thumb
                        persistent._tl_prev_thumb = None
                        renpy.save_persistent()
                    _tl_node_count += 1
                    return existing

        rollback_id = None
        ## Grab rollback identifier — lets us jump back via RollbackToIdentifier
        ## if this node is still within the rollback log.
        try:
            if renpy.game.log and renpy.game.log.current:
                rollback_id = renpy.game.log.current.identifier
        except Exception as e:
            _tl_log("TL rollback_id failed: {}".format(e))

        node = {
            "index"             : _tl_node_count,
            "prompt"            : prompt,
            "options"           : valid_items,
            "chosen_index"      : None,
            "thumb_bytes"       : None,
            "ast_key"           : ast_key,
            "_location"         : location,
            "_rollback_id"      : rollback_id,
        }
        menu_site = _tl_node_menu_site_key(node)
        _tl_log("TL menu enter: node={} ast={} site={} opts={} current_type={}".format(
            node["index"], node["ast_key"], menu_site,
            len(node["options"]), node_type))
        if node_type != "Menu":
            _tl_log("TL menu current-node mismatch: node={} ast={} current_type={} loc={}".format(
                node["index"], node["ast_key"], node_type, node.get("_location")))
        if (node["ast_key"] is not None and menu_site is not None
                and tuple(node["ast_key"]) != tuple(menu_site)):
            _tl_log("TL menu ast/site mismatch: node={} ast={} site={} loc={}".format(
                node["index"], node["ast_key"], menu_site, node.get("_location")))

        node["img_name"] = _tl_resolve_img_name(ast_key, location)
        _tl_capture_thumb(node, ast_key)

        _tl_history = _tl_history + [node]
        if snap is not None:
            _tl_cache_menu_snapshot(node["index"], snap)
        _tl_node_count += 1

        ## Snapshot all route vars (including None) for next-menu var-change detection.
        try:
            store._tl_menu_var_snap = _tl_snapshot_route_vars()
        except Exception as e:
            _tl_log("TL menu var snap error: {}".format(e))

        return node


    def _tl_record_after(node, chosen_label=None, chosen_index=None):
        global _tl_context

        if node is None:
            return

        choice_source = "index"
        if chosen_index is None and chosen_label is not None:
            choice_source = "label_fallback"
            for i, label in enumerate(node["options"]):
                if label == chosen_label:
                    chosen_index = i
                    break

        if chosen_index is None or chosen_index < 0 or chosen_index >= len(node["options"]):
            _tl_log("TL NO MATCH: chosen_index={} chosen_label={}".format(
                repr(chosen_index), repr(chosen_label)))
            return

        node["chosen_index"] = chosen_index
        _tl_context = _tl_context + [(node["prompt"], chosen_index)]
        _tl_log("TL choice: node={} idx={} label={} source={}".format(
            node.get("index"), chosen_index,
            repr(node["options"][chosen_index]) if chosen_index < len(node["options"]) else None,
            choice_source))

        pass  ## checkpoint saves removed; pre-saves cover all menus


    _tl_pending = [None]

    if not getattr(renpy.exports.menu, "_tl_wrapped", False):
        _tl_original_exports_menu = renpy.exports.menu

        def _tl_exports_wrapper(items, set=None, args=None, kwargs=None, item_arguments=None):
            _tl_pending[0] = _tl_record_before(items)
            return _tl_original_exports_menu(items, set, args, kwargs, item_arguments)

        _tl_exports_wrapper._tl_wrapped = True
        renpy.exports.menu = _tl_exports_wrapper

    def _tl_replay_pick(n_index, items, path, target):
        """
        During replay, return (chosen_index, choice_value) for the current node, or None
        if this node is not on the replay path. Does not modify persistent state.
        """
        if target and n_index == target["node_index"]:
            opt_index    = target["option_index"]
            choice_entry = _tl_choice_entry_for_index(items, opt_index)
            return (opt_index, choice_entry[1]) if choice_entry else None
        for path_entry in (path or []):
            if path_entry["index"] == n_index:
                chosen_index = path_entry["chosen_index"]
                choice_entry = (_tl_choice_entry_for_index(items, chosen_index)
                                if chosen_index is not None else None)
                return (chosen_index, choice_entry[1]) if choice_entry else None
        return None

    if not getattr(renpy.store.menu, "_tl_wrapped", False):
        _tl_original_store_menu = renpy.store.menu

        def _tl_store_wrapper(items):
            ## ── Replay interception ───────────────────────────────────────────
            if persistent._tl_replaying:
                node = _tl_pending[0]
                if node is not None:
                    target  = persistent._tl_replay_target
                    path    = persistent._tl_replay_path or []
                    n_index = node["index"]

                    if target and n_index == target["node_index"]:
                        _tl_log("TL replay: arrived at node={} option={}".format(
                            n_index, target["option_index"]))
                        persistent._tl_replaying     = False
                        persistent._tl_replay_path   = None
                        persistent._tl_replay_target = None
                        ## Always disable skip when replay ends — shadow_path stays set
                        ## for the "Autoplay from here?" button, but the player must
                        ## opt in manually. No automatic shadow replay activation.
                        config.skipping = None
                        renpy.save_persistent()

                        _tl_populate_choice_returns(node, items)
                        pick = _tl_replay_pick(n_index, items, path, target)
                        if pick is not None:
                            opt_index, value = pick
                            _tl_pending[0] = None
                            ## Stamp divergence marker if the jump chose a different option.
                            ## node["chosen_index"] may be None when the save loaded is from
                            ## before this node existed, so read the original choice from
                            ## persistent._tl_replay_path which was snapshotted pre-load.
                            orig_chosen = next(
                                (e["chosen_index"] for e in path if e["index"] == n_index), None)
                            _tl_record_after(node, chosen_index=opt_index)
                            if orig_chosen is not None and opt_index != orig_chosen:
                                node["_shadow_orig_chosen"] = orig_chosen
                            ## Call value() rather than reading .value directly so
                            ## ChoiceReturn.__call__ records this choice in
                            ## persistent._chosen — required for get_chosen() to
                            ## return True and dots to clear after replay.
                            return value() if hasattr(value, "value") else value

                    else:
                        pick = _tl_replay_pick(n_index, items, path, target)
                        if pick is not None:
                            chosen_index, value = pick
                            _tl_populate_choice_returns(node, items)
                            _tl_pending[0] = None
                            _tl_record_after(node, chosen_index=chosen_index)
                            return value() if hasattr(value, "value") else value

            ## ── Normal flow ───────────────────────────────────────────────────
            node = _tl_pending[0]
            if node is not None:
                _tl_populate_choice_returns(node, items)

            rv = _tl_original_store_menu(items)

            node = _tl_pending[0]
            if node is not None and rv is not None:
                chosen_index = _tl_choice_index_from_return_value(items, rv)

                if chosen_index is not None:
                    _tl_record_after(node, chosen_index=chosen_index)
                else:
                    _tl_log("TL choice resolve failed: node={} valid_opts={} rv_type={}".format(
                        node.get("index"), len(_tl_valid_choice_entries(items)), type(rv).__name__))

                ## Replay aid: consume shadow path entries when a matching menu is reached.
                ## Discard all entries before the match + the match itself.
                ## If the player chose differently, stamp _shadow_orig_chosen on the node
                ## so the divergence marker can still display after the entry is gone.
                if store._tl_shadow_path and node is not None:
                    try:
                        remaining, diverged_ci, _ = _tl_consume_shadow_path(
                            store._tl_shadow_path, node, node.get("chosen_index"))
                        if remaining != store._tl_shadow_path:  ## matched — update path
                            if diverged_ci is not None:
                                node["_shadow_orig_chosen"] = diverged_ci
                            store._tl_shadow_path = remaining
                    except Exception as e:
                        _tl_log("TL shadow ERROR: node={} err={}".format(node.get("index"), e))

                _tl_pending[0] = None

            return rv

        _tl_store_wrapper._tl_wrapped = True
        renpy.store.menu = _tl_store_wrapper


init 0 python:
    try:
        _tl_build_ast_map()
    except Exception as e:
        _tl_log("TL AST error: {}".format(e))
        store._tl_ast_ready = True


init python:
    def _tl_on_game_start():
        try:
            _tl_clear_replay_state()
            _tl_save_no_screenshot("_ch_start")
        except Exception as e:
            _tl_log("TL ERROR initial save failed: {}".format(e))

    def _tl_on_load():
        _tl_init_snapshot_cache()

        ## Only clear if replaying is True but target is None — stale state
        ## from a crashed session. If both are set, this is a valid replay load
        ## and we must NOT clear or menus will fire with replaying=False and
        ## take fresh screenshots.
        is_synthetic = getattr(persistent, "_tl_synthetic_jump", False)
        if is_synthetic:
            persistent._tl_synthetic_jump = False
            try:
                for scr in renpy.config.overlay_screens:
                    if renpy.display.screen.get_screen(scr) is not None:
                        renpy.display.screen.hide_screen(scr)
                _tl_log("TL on_load: overlay screens hidden after snapshot jump")
            except Exception as e:
                _tl_log("TL on_load: overlay hide failed: {}".format(e))

        if persistent._tl_replaying and persistent._tl_replay_target is None:
            _tl_log("TL stale replay state cleared on load")
            _tl_clear_replay_state()
        elif persistent._tl_replaying:
            _tl_log("TL on_load: path={} target={} replay_path_len={}".format(
                "synthetic" if is_synthetic else "pre-save",
                persistent._tl_replay_target,
                len(persistent._tl_replay_path or [])
            ))
            if not is_synthetic:
                ## Pre-save path: re-enable skip to fast-forward to target.
                ## Synthetic path lands directly at target — no skip needed.
                config.skipping = "fast"
        elif persistent._tl_recovery_slot and not persistent._tl_replay_path:
            ## Jump completed (target reached), but user saved and reloaded before
            ## cancelling — recovery slot is stale. Clear it so the timeline
            ## doesn't show a cancel button for a jump that already finished.
            _tl_log("TL on_load: stale recovery slot cleared (completed jump)")
            _tl_clear_replay_state()
        
        ## Reconstruct store._tl_shadow_path from replay_path.
        ## Menu jump: replaying=True + replay_target set → shadow = entries after target.
        ## Chapter jump: replaying=False + replay_path set → all entries are shadow.
        if persistent._tl_replay_path:
            if persistent._tl_replaying and persistent._tl_replay_target:
                target_idx = persistent._tl_replay_target["node_index"]
                shadow = [e for e in persistent._tl_replay_path if e.get("index", -1) > target_idx]
            else:
                shadow = list(persistent._tl_replay_path)
                persistent._tl_replay_path = None
            store._tl_shadow_path = shadow or None
            _tl_log("TL on_load: shadow_path set count={}".format(
                len(store._tl_shadow_path) if isinstance(store._tl_shadow_path, list) else store._tl_shadow_path))
        
        ## Write _ch_start if it doesn't exist yet.
        if not os.path.exists(os.path.join(renpy.config.savedir, "_ch_start-LT1.save")):
            try:
                _tl_save_no_screenshot("_ch_start")
            except Exception as e:
                _tl_log("TL ERROR start save failed on load: {}".format(e))
        ## Ghost nodes are ephemeral — always reset on load to clear any stale
        ## state (including old _TlNoRollbackList saves from a previous session).
        store._tl_ghost_nodes    = []
        store._tl_skip_ghost_ifs = set()
        ## Backfill img_name on history nodes from the persistent scene map.
        ## Skip on replay loads — pre-save was written this session so all
        ## nodes already have img_name populated.
        if not persistent._tl_replaying:
            _tl_migrate_img_names()

    def _tl_interact_callback():
        if not hasattr(store, "_tl_history"):
            return  ## store defaults not yet applied (pre-game-start interact)

        ## Flush all var changes accumulated since the last interact as one batched
        ## notification. When disabled: discard instead so enabling mid-session starts clean.
        if getattr(persistent, "_tl_var_notifs_enabled", True):
            _tl_flush_var_changes()
        else:
            store._tl_pending_var_changes = {}

    config.start_callbacks.append(_tl_on_game_start)
    config.after_load_callbacks.append(_tl_on_load)
    config.interact_callbacks.append(_tl_interact_callback)

    ## Register chapter end label dispatcher (no-op if chapters.json is absent or
    ## RenPy version predates config.label_callbacks, added in 7.6/8.1).
    if _tl_chapters and hasattr(config, "label_callbacks"):
        _tl_label_to_chapter = {v: k for k, v in _tl_chapters.items()}
        def _tl_chapter_label_cb(label_name, abnormal):
            chapter = _tl_label_to_chapter.get(label_name)
            if chapter is None:
                return
            after_idx = store._tl_node_count
            ## Deduplicate: rollback can re-fire this callback at the same position
            seen = any(
                m["after_index"] == after_idx and m["chapter_name"] == chapter
                for m in store._tl_chapter_markers
            )
            if seen:
                return
            if not persistent._tl_replaying:
                try:
                    chap_snap = _tl_capture_snapshot()
                    _tl_log("TL chapter snapshot: '{}' ctx={} roots_keys={}".format(
                        chapter,
                        getattr(chap_snap["context"], "current", "?"),
                        len(chap_snap["roots"])
                    ))
                    _tl_cache_chapter_snapshot(label_name, chap_snap)
                except Exception as snap_e:
                    _tl_log("TL chapter snapshot ERROR '{}': {}".format(chapter, snap_e))
            store._tl_chapter_markers = store._tl_chapter_markers + [
                {"chapter_name": chapter, "end_label": label_name,
                    "after_index": after_idx}
            ]
            ## Mark the last history node — ties divider position to a specific node
            if store._tl_history:
                store._tl_history[-1]["chapter_end"] = chapter
            _tl_log("TL chapter end: '{}' after_index={}".format(chapter, after_idx))
        config.label_callbacks.append(_tl_chapter_label_cb)
