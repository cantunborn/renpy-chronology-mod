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
            renpy.log("TL: _tl_history invalid on load ({}), resetting".format(type(history)))
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
                renpy.log("TL: dropping malformed node: {}".format(repr(node)[:80]))
        _store._tl_history = clean

        ## Re-index nodes in case indices are stale
        for i, node in enumerate(_store._tl_history):
            node["index"] = i

        ## Reset transient UI state — never safe to restore across sessions
        _store._tl_modal_node   = None
        _store._tl_ast_ready    = False
        _store._tl_ast_progress = 0.0
        _store._tl_ast_map      = {}
        _store._tl_global_new   = 0

        renpy.log("TL: post-load validation complete ({} nodes)".format(
            len(_store._tl_history)))

    ## Register the validator as an after_load callback
    config.after_load_callbacks.append(_tl_validate_on_load)
