## =============================================================================
## CHRONOLOGY MOD — tl_snapshot_cache.rpy
## Snapshot cache: capture, store, retrieve, and transfer game state snapshots.
## Snapshots live on renpy.game.log._tl_snapshot_cache — not in the store —
## so they are pickled into the save's log entry automatically and never appear
## in get_roots(), eliminating the recursive cycle from the old per-node approach.
##
## IMPORTANT: All cache and snap dicts must be plain builtins.dict, NOT
## RevertableDict. In Ren'Py init python blocks, {} literals are transformed
## to __renpy__dict__() which creates RevertableDict — tracked by the rollback
## system and reverted on rollback. _TL_PLAIN_DICT bypasses this.
## =============================================================================

init -2 python:

    import builtins as _tl_builtins
    _TL_PLAIN_DICT = _tl_builtins.dict

    def _tl_make_cache():
        c = _TL_PLAIN_DICT()
        c["menu"]    = _TL_PLAIN_DICT()
        c["chapter"] = _TL_PLAIN_DICT()
        return c

    def _tl_get_snapshot_cache():
        if not hasattr(renpy.game.log, "_tl_snapshot_cache"):
            renpy.game.log._tl_snapshot_cache = _tl_make_cache()
        return renpy.game.log._tl_snapshot_cache

    def _tl_init_snapshot_cache():
        """Ensure cache exists on the loaded log. Called by _tl_on_load."""
        if not hasattr(renpy.game.log, "_tl_snapshot_cache"):
            renpy.game.log._tl_snapshot_cache = _tl_make_cache()

    def _tl_capture_snapshot():
        """
        Capture full game state as a snapshot dict {"roots": ..., "context": ctx}.

        ctx.info (scene list, music) is deep-copied at capture time because rollback_copy()
        is shallow — ctx.info is a live reference that mutates as the game continues.
        All other ctx fields are isolated at unfreeze time via deepcopy in _tl_unfreeze_from_snapshot.

        In compiled .rpyc files ctx.current is a (filename, serial, linenumber) tuple that
        has_label() cannot resolve. Patched to the enclosing label so RollbackLog.rollback()
        stops correctly at our synthetic entry.
        """
        import copy as _copy
        renpy.game.log.complete(False)  # flush pending store deltas into the log
        ctx = renpy.game.context().rollback_copy()
        try:
            ctx.info = _copy.deepcopy(ctx.info)
        except Exception as e:
            _tl_log("TL snapshot: deepcopy info failed: {}".format(e))
        snap = _TL_PLAIN_DICT()
        snap["roots"]   = renpy.game.log.get_roots()
        snap["context"] = ctx
        # patch ctx.current for compiled .rpyc files where the label is a tuple
        ctx_cur = getattr(ctx, "current", None)
        if ctx_cur is not None and not renpy.game.script.has_label(ctx_cur):
            if isinstance(ctx_cur, tuple) and len(ctx_cur) >= 3:
                target_file, target_line = ctx_cur[0], ctx_cur[2]
                best_label, best_line = None, -1
                for lname, lnode in renpy.game.script.namemap.items():
                    if (isinstance(lname, str)
                            and type(lnode).__name__ == "Label"
                            and getattr(lnode, "filename", None) == target_file
                            and getattr(lnode, "linenumber", -1) <= target_line
                            and lnode.linenumber > best_line):
                        best_line = lnode.linenumber
                        best_label = lname
                if best_label:
                    ctx.current = best_label
                    _tl_log("TL snapshot: patched current {} → {}".format(ctx_cur, best_label))
                else:
                    _tl_log("TL snapshot: WARNING no enclosing label for {}".format(ctx_cur))
        return snap

    def _tl_cache_menu_snapshot(node_index, snap):
        """Write snap to cache["menu"][node_index]. Called after history append."""
        cache = _tl_get_snapshot_cache()
        cache["menu"][node_index] = snap
        _tl_log("TL snapshot: cached idx={} cache_menu_total={}".format(
            node_index, len(cache["menu"])))

    def _tl_cache_chapter_snapshot(label_name, snap):
        """Write snap to cache["chapter"][label_name]."""
        cache = _tl_get_snapshot_cache()
        cache["chapter"][label_name] = snap
        _tl_log("TL snapshot: chapter cached label={} cache_chapter_total={}".format(
            label_name, len(cache["chapter"])))

    def _tl_get_menu_snapshot(node_index):
        """Return cache["menu"].get(node_index) or None."""
        return _tl_get_snapshot_cache()["menu"].get(node_index)

    def _tl_get_chapter_snapshot(label_name):
        """Return cache["chapter"].get(label_name) or None."""
        return _tl_get_snapshot_cache()["chapter"].get(label_name)

    def _tl_transfer_snapshot_cache(new_log):
        """Copy cache from current renpy.game.log to new_log."""
        old_cache = getattr(renpy.game.log, "_tl_snapshot_cache", None)
        if old_cache is not None:
            new_log._tl_snapshot_cache = old_cache
            _tl_log("TL unfreeze: cache copied menu={} chapter={}".format(
                len(old_cache.get("menu", {})), len(old_cache.get("chapter", {}))))
        else:
            _tl_log("TL unfreeze: no cache to copy (old_log had none)")

    def _tl_unfreeze_from_snapshot(snap):
        """
        Build a single-entry RollbackLog from snap and call unfreeze(). Never returns.
        Caller is responsible for writing the recovery save and staging persistent vars
        before calling this. snap must have 'roots' and 'context' keys.
        """
        try:
            import renpy.rollback as rb_mod
        except ImportError:
            import renpy.python as rb_mod

        roots = snap["roots"]
        # deepcopy ctx so Ren'Py's post-unfreeze mutations don't corrupt the stored snapshot.
        # also reset interacting to heal saves made before this fix was applied.
        try:
            import copy as _copy
            ctx = _copy.deepcopy(snap["context"])
        except Exception as e:
            _tl_log("TL unfreeze: ctx deepcopy failed: {}".format(e))
            ctx = snap["context"]
        ctx.interacting = False

        # Build synthetic RollbackLog with one entry at the target context.
        # Rollback() __init__ reads renpy.game.log — construct BEFORE unfreeze replaces it.
        # stores={} and objects=[] means no state changes on rollback; roots handles that.
        # not_greedy=True stops the greedy pass immediately at this entry.
        new_log             = rb_mod.RollbackLog()
        rb                  = rb_mod.Rollback()
        rb.context          = ctx
        rb.stores           = {}
        rb.objects          = []
        rb.checkpoint       = True
        rb.hard_checkpoint  = True
        rb.purged           = False
        rb.retain_after_load = False
        rb.random           = []
        rb.forward          = None
        if hasattr(rb, "not_greedy"):
            rb.not_greedy = True
        new_log.log            = [rb]
        new_log.rollback_limit = 1

        _tl_transfer_snapshot_cache(new_log)

        _tl_log("TL unfreeze: ctx={} roots_keys={}".format(
            getattr(ctx, "current", "?"), len(roots)))

        ## Never returns — execution resumes via _after_load label.
        new_log.unfreeze(roots, label="_after_load")