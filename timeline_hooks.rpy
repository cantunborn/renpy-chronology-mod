## =============================================================================
## CHRONOLOGY MOD — timeline_hooks.rpy
## =============================================================================

init -1 python:

    def _tl_record_before(items):
        if not hasattr(store, "_tl_history"):
            return None  ## store defaults not yet applied (pre-game-start menu)
        global _tl_branch_id, _tl_node_count, _tl_history, _tl_context

        ## Ghost nodes accumulated since last menu are now resolved — clear them.
        store._tl_ghost_nodes     = []
        store._tl_ghost_highlight = None
        store._tl_skip_ghost_ifs  = set()

        ## Refresh any early save now that we're past any untracked menus
        ## (image menus, call screens) that may have fired since the save was written.
        if getattr(store, "_tl_early_save_idx", None) is not None and not persistent._tl_replaying:
            try:
                slot = _tl_save_slot(store._tl_early_save_idx, list(_tl_context))
                renpy.save(slot)
            except Exception as e:
                _tl_log("TL ERROR save refresh failed: {}".format(e))
            store._tl_early_save_idx = None

        if not _tl_branch_id:
            _tl_branch_id  = _tl_new_branch_id()
            _tl_node_count = 0
            ## Write the game-start save right before the first menu fires.
            ## This is the earliest safe point — used as ultimate fallback
            ## for jumping to node 0.
            try:
                import os as _os
                start_file = _os.path.join(renpy.config.savedir, "_ch_start-LT1.save")
                if not _os.path.exists(start_file):
                    renpy.save("_ch_start")
            except Exception as e:
                _tl_log("TL ERROR _ch_start write failed: {}".format(e))

        prompt      = ""
        valid_items = []
        for entry in items:
            label = entry[0]
            value = entry[2] if len(entry) > 2 else None
            if value is None:
                if not prompt:
                    prompt = label
            else:
                valid_items.append(label)

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

        location    = None
        ast_key     = None
        node_type   = None
        rollback_id = None
        try:
            current = renpy.game.context().current
            if current is not None:
                location = current
                node_obj = renpy.game.script.namemap.get(current)
                if node_obj is not None:
                    node_type = type(node_obj).__name__
                    ast_key = (node_obj.filename, node_obj.linenumber)
        except Exception as e:
            _tl_log("TL location lookup failed: {}".format(e))
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
            "_option_conditions": [],   ## [condition_str per option] — populated below
        }
        _derived_site = _tl_node_menu_site_key(node)
        _tl_log("TL menu enter: node={} ast={} site={} opts={} current_type={}".format(
            node["index"], node["ast_key"], _derived_site,
            len(node["options"]), node_type))
        if node_type != "Menu":
            _tl_log("TL menu current-node mismatch: node={} ast={} current_type={} loc={}".format(
                node["index"], node["ast_key"], node_type, node.get("_location")))
        if (node["ast_key"] is not None and _derived_site is not None
                and tuple(node["ast_key"]) != tuple(_derived_site)):
            _tl_log("TL menu ast/site mismatch: node={} ast={} site={} loc={}".format(
                node["index"], node["ast_key"], _derived_site, node.get("_location")))

        ## Extract option conditions from the RenPy AST.
        ## Only runs when the current script node is directly a Menu node —
        ## gracefully skipped otherwise.
        try:
            if location is not None:
                _menu_ast = renpy.game.script.namemap.get(location)
                if _menu_ast is not None and type(_menu_ast).__name__ == "Menu":
                    for _item in _menu_ast.items:
                        _blk  = _item[2] if len(_item) > 2 else None
                        _cond = _item[1] if len(_item) > 1 else None
                        if _blk is None:
                            continue  ## prompt/separator entry — skip
                        node["_option_conditions"].append(
                            None if _cond in (None, "True", True) else str(_cond))
        except Exception as _e:
            _tl_log("TL option_conditions extraction failed: {}".format(_e))

        ## Thumbnail: runtime-captured img_name is authoritative.
        ## Persistent menu scene map is the backfill source for older / unresolved menus.
        node["img_name"] = None
        if not persistent._tl_replaying and not config.skipping:
            node["img_name"] = _tl_resolve_live_menu_img_name()
            if ast_key and node["img_name"]:
                _ak = _tl_menu_site_key(ast_key[0], ast_key[1]) if isinstance(ast_key, tuple) and len(ast_key) == 2 else None
                if _ak:
                    persistent._tl_menu_scene_map[_ak] = node["img_name"]
        if not node["img_name"]:
            _img_cache = persistent._tl_menu_scene_map or {}
            _ak = _tl_menu_site_key(ast_key[0], ast_key[1]) if isinstance(ast_key, tuple) and len(ast_key) == 2 else None
            _lk = _tl_location_menu_site_key(location)
            if _ak and _ak in _img_cache:
                node["img_name"] = _img_cache[_ak]
            elif _lk and _lk in _img_cache:
                node["img_name"] = _img_cache[_lk]
        _tl_log("TL img_name: ast_key={} img_name={}".format(ast_key, node["img_name"]))

        ## Screenshot fallback: explicit migration/backstop path only.
        _tl_need_frozen_thumb = bool(node["img_name"] and _tl_img_name_is_movie(node["img_name"]))
        if not node["img_name"] or _tl_need_frozen_thumb:
            cache_key = str(ast_key) if ast_key else None
            cached_thumb = persistent._tl_thumb_cache.get(cache_key) if cache_key else None
            if not persistent._tl_replaying and not cached_thumb and not config.skipping:
                thumb = _tl_capture_thumbnail()
                if cache_key and thumb:
                    try:
                        persistent._tl_thumb_cache[cache_key] = thumb
                        while len(persistent._tl_thumb_cache) > TL_THUMB_CACHE_MAX:
                            persistent._tl_thumb_cache.pop(next(iter(persistent._tl_thumb_cache)))
                    except Exception as e:
                        _tl_log("TL thumb cache write failed: {}".format(e))
                        node["thumb_bytes"] = thumb
                elif thumb:
                    node["thumb_bytes"] = thumb
            if _tl_need_frozen_thumb:
                _tl_log("TL movie thumb fallback: ast_key={} img_name={}".format(ast_key, node["img_name"]))


        _tl_history    = _tl_history + [node]
        _tl_node_count += 1

        return node


    def _tl_record_after(node, chosen_label=None, chosen_index=None):
        global _tl_context

        if node is None:
            return

        _choice_source = "index"
        if chosen_index is None and chosen_label is not None:
            _choice_source = "label_fallback"
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
            _choice_source))

        if not persistent._tl_replaying:
            ## Cannot save here — mid-interaction saves capture rollback
            ## state from before this interaction, so _tl_history and
            ## _tl_context would be missing the current node.
            ## Defer to _tl_interact_callback which fires after interact ends.
            store._tl_pending_save_index = node["index"]


    _tl_pending = [None]

    if not getattr(renpy.exports.menu, "_tl_wrapped", False):
        _tl_original_exports_menu = renpy.exports.menu

        def _tl_exports_wrapper(items, set=None, args=None, kwargs=None, item_arguments=None):
            _tl_pending[0] = _tl_record_before(items)
            return _tl_original_exports_menu(items, set, args, kwargs, item_arguments)

        _tl_exports_wrapper._tl_wrapped = True
        renpy.exports.menu = _tl_exports_wrapper

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
                        opt_index = target["option_index"]
                        opt_label = node["options"][opt_index] if opt_index < len(node["options"]) else None
                        _tl_log("TL replay: arrived at node={} option={}".format(n_index, opt_index))

                        persistent._tl_replaying     = False
                        persistent._tl_replay_path   = None
                        persistent._tl_replay_target = None
                        ## Always disable skip when replay ends — shadow_path stays set
                        ## for the "Autoplay from here?" button, but the player must
                        ## opt in manually. No automatic shadow replay activation.
                        config.skipping = None
                        renpy.game.preferences.skip_unseen = False
                        renpy.save_persistent()

                        ## Populate _choice_returns so get_chosen() works correctly
                        _tl_populate_choice_returns(node, items)

                        _choice_entry = _tl_choice_entry_for_index(items, opt_index)
                        if _choice_entry is not None:
                            _label, value = _choice_entry
                            _tl_pending[0] = None
                            ## Stamp divergence marker if the jump chose a different option.
                            ## node["chosen_index"] may be None when the save loaded is from
                            ## before this node existed, so read the original choice from
                            ## persistent._tl_replay_path which was snapshotted pre-load.
                            _orig_ci = None
                            for _pe in (path or []):
                                if _pe["index"] == n_index:
                                    _orig_ci = _pe["chosen_index"]
                                    break
                            _tl_record_after(node, chosen_index=opt_index)
                            if _orig_ci is not None and opt_index != _orig_ci:
                                node["_shadow_orig_chosen"] = _orig_ci
                            ## Call value() rather than reading .value directly so
                            ## ChoiceReturn.__call__ records this choice in
                            ## persistent._chosen — required for get_chosen() to
                            ## return True and dots to clear after replay.
                            return value() if hasattr(value, "value") else value

                    else:
                        chosen_index = None
                        for entry in path:
                            if entry["index"] == n_index:
                                chosen_index = entry["chosen_index"]
                                break

                        if chosen_index is not None and chosen_index < len(node["options"]):
                            ## Populate _choice_returns so dots work correctly
                            _tl_populate_choice_returns(node, items)

                            _choice_entry = _tl_choice_entry_for_index(items, chosen_index)
                            if _choice_entry is not None:
                                _label, value = _choice_entry
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
                    _cur_loc = node.get("_location")
                    _tl_log("TL shadow check: node={} sp_count={} cur_loc={} site={}".format(
                        node.get("index"),
                        len(store._tl_shadow_path) if isinstance(store._tl_shadow_path, list) else store._tl_shadow_path,
                        bool(_cur_loc), _tl_node_menu_site_key(node)))
                    if _cur_loc:
                        try:
                            _match_mode = _tl_shadow_match_mode(store._tl_shadow_path, node)
                            _new_sp, _div_ci = _tl_consume_shadow_path(
                                store._tl_shadow_path, node, node.get("chosen_index"))
                            if _new_sp != store._tl_shadow_path:  ## matched — update path
                                if _div_ci is not None:
                                    node["_shadow_orig_chosen"] = _div_ci
                                _tl_log("TL shadow match: node={} via={} site={} div={}".format(
                                    node.get("index"), _match_mode,
                                    _tl_node_menu_site_key(node), _div_ci))
                                store._tl_shadow_path = _new_sp
                            else:
                                _tl_log("TL shadow no-match: node={} sp_first={}".format(
                                    node.get("index"),
                                    store._tl_shadow_path[0] if store._tl_shadow_path else None))
                        except Exception as _sp_err:
                            _tl_log("TL shadow ERROR: node={} err={}".format(
                                node.get("index"), _sp_err))
                    else:
                        _tl_log("TL shadow skip: node={} no _location".format(node.get("index")))

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
            renpy.save("_ch_start")
        except Exception as e:
            _tl_log("TL ERROR initial save failed: {}".format(e))

    def _tl_on_load():
        ## Only clear if replaying is True but target is None — stale state
        ## from a crashed session. If both are set, this is a valid replay load
        ## and we must NOT clear or menus will fire with replaying=False and
        ## take fresh screenshots.
        if persistent._tl_replaying and persistent._tl_replay_target is None:
            _tl_log("TL stale replay state cleared on load")
            _tl_clear_replay_state()
        elif persistent._tl_replaying:
            _tl_log("TL replay resuming, target={}".format(persistent._tl_replay_target))
            ## Re-enable skip after load — config resets on load so we
            ## must set it again here. Not needed for rollback path since
            ## rollback doesn't trigger after_load_callbacks.
            config.skipping = "fast"
            renpy.game.preferences.skip_unseen = True
            ## Transfer shadow path from persistent staging into the store now that
            ## the checkpoint load is complete (store vars were overwritten by load).
            if persistent._tl_pending_shadow_path is not None:
                store._tl_shadow_path = persistent._tl_pending_shadow_path
                persistent._tl_pending_shadow_path = None
                renpy.save_persistent()
                _tl_log("TL on_load: store._tl_shadow_path set count={}".format(
                    len(store._tl_shadow_path) if isinstance(store._tl_shadow_path, list) else store._tl_shadow_path))
        ## Write _ch_start if it doesn't exist yet
        import os as _os
        start_file = _os.path.join(renpy.config.savedir, "_ch_start-LT1.save")
        if not _os.path.exists(start_file):
            try:
                renpy.save("_ch_start")
            except Exception as e:
                _tl_log("TL ERROR start save failed on load: {}".format(e))
        ## Backfill img_name on history nodes from the persistent scene map.
        _tl_migrate_img_names()

    def _tl_interact_callback():
        if not hasattr(store, "_tl_history"):
            return  ## store defaults not yet applied (pre-game-start interact)
        ## Checkpoint saves: skip during skip mode to avoid racing with image loading.
        ## Pending index is left set so the save fires at the next non-skip interaction.
        if not config.skipping and store._tl_pending_save_index is not None:
            idx = store._tl_pending_save_index
            store._tl_pending_save_index = None
            ## Save every choice for the first TL_DENSE_SAVES nodes (covers early
            ## mandatory inputs like name entry), then every TL_SAVE_EVERY after.
            if _tl_should_save(idx):
                try:
                    slot = _tl_save_slot(idx, list(_tl_context))
                    renpy.save(slot)
                    store._tl_early_save_idx = idx
                except Exception as e:
                    _tl_log("TL ERROR deferred save failed idx={}: {}".format(idx, e))

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
            _tl_seen = any(
                m["after_index"] == after_idx and m["chapter_name"] == chapter
                for m in store._tl_chapter_markers
            )
            if _tl_seen:
                return
            store._tl_chapter_markers = store._tl_chapter_markers + [
                {"chapter_name": chapter, "end_label": label_name, "after_index": after_idx}
            ]
            ## Mark the last history node — ties divider position to a specific node
            if store._tl_history:
                store._tl_history[-1]["chapter_end"] = chapter
            ## Save immediately — label callbacks fire between interactions so renpy.save()
            ## is safe here. Deferring to _tl_interact_callback would write at the START
            ## of the next interaction, overshooting into a menu if no dialog follows first.
            ## Existence check: same slot = same playthrough path already saved, skip write.
            _h6 = _tl_hashlib.md5(
                repr(tuple(store._tl_context[:after_idx])).encode("utf-8")
            ).hexdigest()[:6]
            _chap_slot = "_ch_chap_{}_{}".format(label_name, _h6)
            import os as _os
            _sd = renpy.config.savedir
            _slot_exists = (
                _os.path.exists(_os.path.join(_sd, "{}-LT1.save".format(_chap_slot))) or
                _os.path.exists(_os.path.join(_sd, "{}.save".format(_chap_slot)))
            )
            if _slot_exists:
                _tl_log("TL chapter-end save skipped (exists): {}".format(_chap_slot))
            else:
                try:
                    renpy.save(_chap_slot)
                    _tl_log("TL chapter-end save: {}".format(_chap_slot))
                except Exception as e:
                    _tl_log("TL ERROR chapter-end save failed: {}".format(e))
            _tl_log("TL chapter end: '{}' after_index={}".format(chapter, after_idx))
        config.label_callbacks.append(_tl_chapter_label_cb)
