## =============================================================================
## TIMELINE MOD — timeline_save_hooks_ren.py
## Graceful failure handling for save compatibility.
## =============================================================================
##
## Two failure cases handled here:
##
## Case 1 — Mod installed, save has NO timeline data (old save loaded):
##   The `default` statements in timeline_init_ren.py already handle this.
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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import renpy  # type-check-only; injected into store namespace at runtime
    from renpy import config  # type-check-only; injected into store namespace at runtime
    from timeline_init_ren import _tl_log, _tl_runtime_cache_store  # type-check-only; injected into store namespace at runtime

"""renpy
init python:
"""

def _tl_validate_on_load():  # type: () -> None
    """
    Called after every save load. Resets timeline state if loaded
    data is corrupt or an unexpected type.
    """
    import store as _store
    _tl_runtime_cache_store().pop("choice_returns", None)

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
            ## Old saves may contain transient runtime-only payloads.
            node.pop("_state_snapshot", None)
            node.pop("_choice_returns", None)
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

    ## Reset transient UI state — never safe to restore across sessions
    _store._tl_modal_node       = None
    _store._tl_chap_end_slot    = ""
    _store._tl_ghost_nodes      = []

    ## Drop test runner result object if present — _TLTestResults is a class instance
    ## and cannot be unpickled without the mod. Clearing it here fixes any saves
    ## that were contaminated before this was caught.
    if hasattr(_store, "_tl_test_results"):
        del _store._tl_test_results
    ## NOTE: _tl_ast_ready and _tl_ast_map are derived from the
    ## static game script (never changes between loads) — do NOT reset them here.
    _tl_log("TL: post-load validation complete ({} nodes)".format(
        len(_store._tl_history)))

def _tl_heal_restarting_screens():  # type: () -> None
    """
    Called after every save load. Ren'Py's before_restart() (fired inside
    unfreeze()/rollback) marks the live ScreenDisplayable of any currently
    shown screen as restarting=True. Because scene_lists layer entries are
    shared by reference between rollback_copy() contexts (see JUMP.md /
    DEV_NOTES.md — ctx.scene_lists is not deep-copied at capture time), a
    dormant cached snapshot or an already-written save can end up carrying
    that flag on ANY currently-shown screen, mod or base-game (e.g.
    quick_menu), which then loads back in a broken state that drops all
    input. Not scoped to mod screens: config.overlay_screens/
    always_shown_screens entries are the ones actually stuck forever
    (show_overlay_screens() only recreates a screen if get_screen() is
    None, so a stale-but-referenced object never gets replaced); ordinary
    on-demand screens get recreated unconditionally on next display
    regardless, so healing them too is at worst a no-op. Heal
    unconditionally on every load, not just right after a synthetic jump,
    so saves made before this fix also recover automatically.
    """
    healed = []
    try:
        for layer in renpy.config.layers:
            for tag in renpy.get_showing_tags(layer):
                scr = renpy.get_screen(tag, layer)
                if scr is not None and getattr(scr, "restarting", False):
                    scr.restarting = False
                    healed.append(tag)
    except Exception as e:
        _tl_log("TL: heal restarting screens failed: {}".format(e))
        return

    if healed:
        _tl_log("TL: healed restarting screens on load: {}".format(healed))
        renpy.restart_interaction()

## Register the validator as an after_load callback
config.after_load_callbacks.append(_tl_validate_on_load)
config.after_load_callbacks.append(_tl_heal_restarting_screens)