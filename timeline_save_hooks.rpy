## =============================================================================
## TIMELINE MOD — timeline_save_hooks.rpy
## Graceful failure handling for save compatibility.
## =============================================================================
##
## Two failure cases handled here:
##
## Case 1 — Mod installed, save has NO timeline data (old save loaded):
##   The `default` statements in timeline_init.rpy already handle this.
##   _tl_history defaults to [], which shows the "No choices recorded yet"
##   empty state. The mod starts recording from the current session forward.
##   No special code needed — RenPy applies defaults for missing variables.
##
## Case 2 — Mod REMOVED, save HAS timeline data:
##   RenPy's save system ignores unknown variables in pickles by design —
##   the game loads fine and the _tl_* keys are simply unused. No crash.
##
## What we DO add: a post-load hook that validates _tl_history on load,
## so corrupted or partial saves degrade gracefully instead of crashing.

init python:
    def _tl_validate_on_load():
        """
        Called after every save load. Resets timeline state if loaded
        data is corrupt or an unexpected type.
        """
        import store as _store

        ## If _tl_history is missing or wrong type, reset to empty list
        history = getattr(_store, "_tl_history", None)
        if not isinstance(history, list):
            _tl_log("TL: _tl_history invalid on load ({}), resetting".format(type(history)))
            _store._tl_history = []

        ## Validate each node; drop malformed entries silently
        clean = []
        for node in getattr(_store, "_tl_history", []):
            if (isinstance(node, dict)
                    and "index" in node
                    and "options" in node
                    and isinstance(node["options"], list)):
                clean.append(node)
            else:
                _tl_log("TL: dropping malformed node: {}".format(repr(node)[:80]))
        _store._tl_history = clean

        ## Re-index nodes in case indices are stale
        for i, node in enumerate(_store._tl_history):
            node["index"] = i

        ## Initialize chapter markers for saves predating this feature; migrate old node tags
        if not isinstance(getattr(_store, "_tl_chapter_markers", None), list):
            _store._tl_chapter_markers = []
            for _node in _store._tl_history:
                if _node.get("chapter_start"):
                    _ch = _node["chapter_start"]
                    _ai = _node["index"]
                    _el = getattr(_store, "_tl_chapters", {}).get(_ch, "")
                    if not any(m["after_index"] == _ai for m in _store._tl_chapter_markers):
                        _store._tl_chapter_markers.append(
                            {"chapter_name": _ch, "end_label": _el, "after_index": _ai})

        ## Validate shadow path — must be a list or None
        if not isinstance(getattr(_store, "_tl_shadow_path", None), (list, type(None))):
            _store._tl_shadow_path = None

        ## Validate pending shadow path in persistent (transit variable, should always be list or None)
        if not isinstance(getattr(persistent, "_tl_pending_shadow_path", None), (list, type(None))):
            persistent._tl_pending_shadow_path = None

        ## Reset transient UI state — never safe to restore across sessions
        _store._tl_modal_node            = None
        _store._tl_ast_ready             = False
        _store._tl_ast_map               = {}
        _store._tl_pending_chap_end_save = None
        _store._tl_chap_end_slot         = ""
        _tl_log("TL: post-load validation complete ({} nodes)".format(
            len(_store._tl_history)))

    ## Register the validator as an after_load callback
    config.after_load_callbacks.append(_tl_validate_on_load)
