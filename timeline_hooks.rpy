## =============================================================================
## CHRONOLOGY MOD — timeline_hooks.rpy
## =============================================================================

init -1 python:

    def _tl_record_before(items):
        global _tl_branch_id, _tl_node_count, _tl_history, _tl_context

        ## Refresh any early save now that we're past any untracked menus
        ## (image menus, call screens) that may have fired since the save was written.
        if store._tl_early_save_idx is not None and not persistent._tl_replaying:
            try:
                slot = _tl_save_slot(store._tl_early_save_idx, list(_tl_context))
                renpy.save(slot)
                _tl_log("TL save refreshed: {}".format(slot))
            except Exception as e:
                _tl_log("TL save refresh error: {}".format(e))
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
                    _tl_log("TL _ch_start written before first menu")
            except Exception as e:
                _tl_log("TL _ch_start error: {}".format(e))

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
        rollback_id = None
        try:
            current = renpy.game.context().current
            if current is not None:
                location = current
                node_obj = renpy.game.script.namemap.get(current)
                if node_obj is not None:
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
            "index"          : _tl_node_count,
            "prompt"         : prompt,
            "options"        : valid_items,
            "chosen_index"   : None,
            "thumb_bytes"    : None,
            "ast_key"        : ast_key,
            "_location"      : location,
            "_choice_returns": [None] * len(valid_items),
            "_rollback_id"   : rollback_id,
        }

        ## Thumbnail: use persistent cache keyed by ast_key so the correct
        ## scene screenshot is available on replay and across playthroughs.
        cache_key = str(ast_key) if ast_key else None
        cached_thumb = persistent._tl_thumb_cache.get(cache_key) if cache_key else None

        if persistent._tl_replaying:
            ## During replay, always restore from cache — never take screenshot
            node["thumb_bytes"] = cached_thumb
        elif cached_thumb:
            ## Already seen this menu before — reuse cached thumbnail
            node["thumb_bytes"] = cached_thumb
        else:
            ## First time seeing this menu — capture and cache
            thumb = _tl_capture_thumbnail()
            node["thumb_bytes"] = thumb
            if cache_key and thumb:
                persistent._tl_thumb_cache[cache_key] = thumb
                while len(persistent._tl_thumb_cache) > TL_THUMB_CACHE_MAX:
                    persistent._tl_thumb_cache.pop(next(iter(persistent._tl_thumb_cache)))

        _tl_history    = _tl_history + [node]
        _tl_node_count += 1
        return node


    def _tl_record_after(node, chosen_label):
        global _tl_context

        if node is None:
            return

        for i, label in enumerate(node["options"]):
            if label == chosen_label:
                node["chosen_index"] = i
                _tl_context = _tl_context + [(node["prompt"], i)]

                if not persistent._tl_replaying:
                    _tl_log("TL recorded: node={} option={}".format(node["index"], i))
                    ## Cannot save here — mid-interaction saves capture rollback
                    ## state from before this interaction, so _tl_history and
                    ## _tl_context would be missing the current node.
                    ## Defer to _tl_interact_callback which fires after interact ends.
                    store._tl_pending_save_index = node["index"]
                else:
                    _tl_log("TL replay context rebuild: node={} option={}".format(node["index"], i))
                return

        _tl_log("TL NO MATCH: chosen_label={}".format(repr(chosen_label)))


    _tl_pending = [None]

    if not getattr(renpy.exports.menu, "_tl_wrapped", False):
        _tl_original_exports_menu = renpy.exports.menu

        def _tl_exports_wrapper(items, set=None, args=None, kwargs=None, item_arguments=None):
            _tl_pending[0] = _tl_record_before(items)
            return _tl_original_exports_menu(items, set, args, kwargs, item_arguments)

        _tl_exports_wrapper._tl_wrapped = True
        renpy.exports.menu = _tl_exports_wrapper
        _tl_log("TL: exports.menu wrapped")
    else:
        _tl_log("TL: exports.menu already wrapped")

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
                        _tl_log("TL replay: reached target node={} picking option={}".format(n_index, opt_index))

                        persistent._tl_replaying     = False
                        persistent._tl_replay_path   = None
                        persistent._tl_replay_target = None
                        renpy.save_persistent()
                        config.skipping = None
                        renpy.game.preferences.skip_unseen = False

                        ## Populate _choice_returns so get_chosen() works correctly
                        for i, lbl in enumerate(node["options"]):
                            for label, value in items:
                                if label == lbl and value is not None and hasattr(value, "get_chosen"):
                                    node["_choice_returns"][i] = value
                                    break

                        if opt_label:
                            for label, value in items:
                                if label == opt_label:
                                    _tl_pending[0] = None
                                    _tl_record_after(node, opt_label)
                                    return value.value if hasattr(value, "value") else value

                    else:
                        chosen_index = None
                        for entry in path:
                            if entry["index"] == n_index:
                                chosen_index = entry["chosen_index"]
                                break

                        if chosen_index is not None and chosen_index < len(node["options"]):
                            opt_label = node["options"][chosen_index]
                            _tl_log("TL replay: auto-pick node={} option={}".format(n_index, chosen_index))

                            ## Populate _choice_returns so dots work correctly
                            for i, lbl in enumerate(node["options"]):
                                for label, value in items:
                                    if label == lbl and value is not None and hasattr(value, "get_chosen"):
                                        node["_choice_returns"][i] = value
                                        break

                            for label, value in items:
                                if label == opt_label:
                                    _tl_pending[0] = None
                                    _tl_record_after(node, opt_label)
                                    return value.value if hasattr(value, "value") else value

            ## ── Normal flow ───────────────────────────────────────────────────
            node = _tl_pending[0]
            if node is not None:
                for i, opt_label in enumerate(node["options"]):
                    for label, value in items:
                        if label == opt_label and value is not None and hasattr(value, "get_chosen"):
                            node["_choice_returns"][i] = value
                            break

            rv = _tl_original_store_menu(items)

            node = _tl_pending[0]
            if node is not None and rv is not None:
                chosen_label = None
                for label, value in items:
                    if value is None:
                        continue
                    if value is rv or value == rv:
                        chosen_label = label
                        break
                    try:
                        if value.value == rv:
                            chosen_label = label
                            break
                    except AttributeError:
                        pass

                if chosen_label is not None:
                    _tl_record_after(node, chosen_label)
                else:
                    _tl_log("TL: no label match for rv={} type={}".format(
                        repr(rv)[:60], type(rv).__name__))

                _tl_pending[0] = None

            return rv

        _tl_store_wrapper._tl_wrapped = True
        renpy.store.menu = _tl_store_wrapper
        _tl_log("TL: store.menu wrapped (RenPy {}.{})".format(
            renpy.version_tuple[0], renpy.version_tuple[1]))
    else:
        _tl_log("TL: store.menu already wrapped")


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
            _tl_log("TL initial save written")
        except Exception as e:
            _tl_log("TL initial save error: {}".format(e))

    def _tl_on_load():
        ## Only clear if replaying is True but target is None — stale state
        ## from a crashed session. If both are set, this is a valid replay load
        ## and we must NOT clear or menus will fire with replaying=False and
        ## take fresh screenshots.
        if persistent._tl_replaying and persistent._tl_replay_target is None:
            _tl_log("TL clearing stale replay state on load")
            _tl_clear_replay_state()
        elif persistent._tl_replaying:
            _tl_log("TL resuming replay, target={}".format(persistent._tl_replay_target))
            ## Re-enable skip after load — config resets on load so we
            ## must set it again here. Not needed for rollback path since
            ## rollback doesn't trigger after_load_callbacks.
            config.skipping = "fast"
            renpy.game.preferences.skip_unseen = True
        ## Write _ch_start if it doesn't exist yet
        import os as _os
        start_file = _os.path.join(renpy.config.savedir, "_ch_start-LT1.save")
        if not _os.path.exists(start_file):
            try:
                renpy.save("_ch_start")
                _tl_log("TL start save written on load")
            except Exception as e:
                _tl_log("TL start save error: {}".format(e))

    def _tl_clear_replay_state():
        persistent._tl_replaying     = False
        persistent._tl_replay_path   = None
        persistent._tl_replay_target = None
        persistent._tl_recovery_slot = None
        persistent._tl_prev_thumb    = None
        renpy.save_persistent()

    def _tl_interact_callback():
        if store._tl_pending_save_index is not None:
            idx = store._tl_pending_save_index
            store._tl_pending_save_index = None
            ## Save every choice for the first TL_DENSE_SAVES nodes (covers early
            ## mandatory inputs like name entry), then every TL_SAVE_EVERY after.
            if idx < TL_DENSE_SAVES or idx % TL_SAVE_EVERY == (TL_SAVE_EVERY - 1):
                try:
                    slot = _tl_save_slot(idx, list(_tl_context))
                    renpy.save(slot)
                    store._tl_early_save_idx = idx
                    _tl_log("TL saved (early): {}".format(slot))
                except Exception as e:
                    _tl_log("TL deferred save error: {}".format(e))

    config.start_callbacks.append(_tl_on_game_start)
    config.after_load_callbacks.append(_tl_on_load)
    config.interact_callbacks.append(_tl_interact_callback)
