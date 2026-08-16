## =============================================================================
## CHRONOLOGY MOD — tl_snapshot_cache.rpy
## Snapshot cache: capture, store, retrieve, and transfer game state snapshots.
## Snapshots live on renpy.game.log._tl_snapshot_cache — not in the store —
## so they are pickled into the save's log entry automatically and never appear
## in get_roots(), eliminating the recursive cycle from the old per-node approach.
##
## The cache owns exactly one frozen (deep-copied-once) reference for every
## distinct mutable value ever captured. Unchanged values across snapshots
## share the same frozen object; changed values get their own fresh deep
## copy. This lets Ren'Py's own single combined save pickle (which memoizes
## by object identity within one dumps() call) dedupe repeated structure
## across every cached menu/chapter snapshot, instead of each snapshot
## paying its own independent copy of unchanged state.
##
## IMPORTANT: All cache and snap dicts must be plain builtins.dict, NOT
## RevertableDict. In Ren'Py init python blocks, {} literals are transformed
## to __renpy__dict__() which creates RevertableDict — tracked by the rollback
## system and reverted on rollback. _TL_PLAIN_DICT bypasses this.
## =============================================================================

init -2 python:

    import builtins as _tl_builtins
    _TL_PLAIN_DICT = _tl_builtins.dict

    def _tl_values_equal(a, b):
        """
        Generic "is this the same content" check for any value, used to decide
        whether _freeze_roots can reuse a prior frozen copy. Plain == is not
        enough on its own: it's correct for dict/list/etc, but custom classes
        without their own __eq__ fall back to identity, which would always be
        False between a live value and its previously frozen (deep-copied)
        counterpart — permanently defeating reuse for those objects. Comparing
        pickled bytes works uniformly across every value type, no per-type
        special-casing required.
        """
        if a is b:
            return True
        import pickle as _tl_std_pickle
        try:
            return _tl_std_pickle.dumps(a) == _tl_std_pickle.dumps(b)
        except Exception:
            return False

    class TLSnapshotCache(object):
        """
        Snapshot cache: owns frozen menu/chapter snapshots and the shared
        pool of frozen root values they reference. See module docstring above.
        """

        def __init__(self):
            self.menu        = _TL_PLAIN_DICT()
            self.chapter     = _TL_PLAIN_DICT()
            self._last_roots = None

        def _freeze_roots(self, live_roots):
            """
            For each key in live_roots: reuse the previously frozen reference
            if the value is unchanged since the last capture (per
            _tl_values_equal), otherwise deep-copy it fresh. The frozen result
            never aliases a live store object — every value handed back here
            is either a reused prior frozen copy or a fresh deep copy.
            """
            import copy as _copy
            frozen = _TL_PLAIN_DICT()
            prev   = self._last_roots or _TL_PLAIN_DICT()
            for key, value in live_roots.items():
                if key in prev and _tl_values_equal(value, prev[key]):
                    frozen[key] = prev[key]
                else:
                    frozen[key] = _copy.deepcopy(value)
            self._last_roots = frozen
            return frozen

        def capture(self):
            """
            Capture full game state as a snapshot dict
            {"roots": ..., "ctx": ..., "rollback_limit": ...}.

            ctx comes from renpy.game.context().rollback_copy() — the same
            copy Ren'Py's own rollback machinery relies on, which already
            guarantees an independent Context object with interacting forced
            False.

            roots comes from renpy.game.log.get_roots(), passed through
            _freeze_roots so unchanged values are shared with the cache's
            existing frozen pool rather than re-copied.

            rollback_limit is the live log's value at this exact point in
            time — capturing it lets a later jump to this snapshot reproduce
            "made a save right here, then loaded it" instead of resetting the
            player's rollback allowance.

            In compiled .rpyc files ctx.current is a (filename, serial,
            linenumber) tuple that has_label() cannot resolve. Patched to the
            enclosing label before returning so RollbackLog.rollback() stops
            correctly at our synthetic entry.
            """
            renpy.game.log.complete(False)  # flush pending store deltas into the log
            ctx = renpy.game.context().rollback_copy()

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

            live_roots     = renpy.game.log.get_roots()
            frozen_roots   = self._freeze_roots(live_roots)
            rollback_limit = renpy.game.log.rollback_limit

            snap = _TL_PLAIN_DICT()
            snap["roots"]          = frozen_roots
            snap["ctx"]            = ctx
            snap["rollback_limit"] = rollback_limit
            return snap

        def cache_menu(self, node_index, snap):
            """Write snap to self.menu[node_index]. Called after history append."""
            self.menu[node_index] = snap
            _tl_log("TL snapshot: cached idx={} cache_menu_total={}".format(
                node_index, len(self.menu)))

        def cache_chapter(self, label_name, snap):
            """Write snap to self.chapter[label_name]."""
            self.chapter[label_name] = snap
            _tl_log("TL snapshot: chapter cached label={} cache_chapter_total={}".format(
                label_name, len(self.chapter)))

        def get_menu(self, node_index):
            """Return self.menu.get(node_index) or None."""
            return self.menu.get(node_index)

        def get_chapter(self, label_name):
            """Return self.chapter.get(label_name) or None."""
            return self.chapter.get(label_name)

        def transfer_to(self, new_log):
            """Attach this cache to new_log (used when a synthetic jump replaces the log)."""
            new_log._tl_snapshot_cache = self
            _tl_log("TL unfreeze: cache copied menu={} chapter={}".format(
                len(self.menu), len(self.chapter)))

    def _tl_make_cache():
        return TLSnapshotCache()

    def _tl_get_snapshot_cache():
        if not hasattr(renpy.game.log, "_tl_snapshot_cache"):
            renpy.game.log._tl_snapshot_cache = _tl_make_cache()
        return renpy.game.log._tl_snapshot_cache

    def _tl_init_snapshot_cache():
        """Ensure cache exists on the loaded log. Called by _tl_on_load."""
        if not hasattr(renpy.game.log, "_tl_snapshot_cache"):
            renpy.game.log._tl_snapshot_cache = _tl_make_cache()

    def _tl_capture_snapshot():
        return _tl_get_snapshot_cache().capture()

    def _tl_cache_menu_snapshot(node_index, snap):
        _tl_get_snapshot_cache().cache_menu(node_index, snap)

    def _tl_cache_chapter_snapshot(label_name, snap):
        _tl_get_snapshot_cache().cache_chapter(label_name, snap)

    def _tl_get_menu_snapshot(node_index):
        return _tl_get_snapshot_cache().get_menu(node_index)

    def _tl_get_chapter_snapshot(label_name):
        return _tl_get_snapshot_cache().get_chapter(label_name)

    def _tl_transfer_snapshot_cache(new_log):
        """Copy cache from current renpy.game.log to new_log."""
        old_cache = getattr(renpy.game.log, "_tl_snapshot_cache", None)
        if old_cache is not None:
            old_cache.transfer_to(new_log)
        else:
            _tl_log("TL unfreeze: no cache to copy (old_log had none)")

    def _tl_build_and_unfreeze(roots, ctx, log_prefix, rollback_limit):
        """
        Shared tail end of both the live and legacy unfreeze paths: build a
        single-entry RollbackLog at (roots, ctx) and call unfreeze(). Never returns.

        rollback_limit is set to the value captured at snapshot time (what a real
        save made at that point would have carried). RollbackLog.rollback() — called
        from inside unfreeze() — decrements it by 1 while consuming the synthetic
        entry, exactly as a real load costs -1 against the save's own rollback_limit.
        So passing the captured value straight through (no extra offset) costs the
        same -1 a real load costs against the save's own rollback_limit, matching a
        real save-then-load rather than resetting the allowance.
        """
        try:
            import renpy.rollback as rb_mod
        except ImportError:
            import renpy.python as rb_mod

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
        new_log.rollback_limit = rollback_limit

        _tl_transfer_snapshot_cache(new_log)

        _tl_log("{}: ctx={} roots_keys={}".format(
            log_prefix, getattr(ctx, "current", "?"), len(roots)))

        ## Never returns — execution resumes via _after_load label.
        new_log.unfreeze(roots, label="_after_load")

    def _tl_unfreeze_legacy(snap):
        """
        Legacy path: consumes a snap in the pre-blob {"roots": ..., "context": ...}
        shape — the only legacy shape that ever shipped to players. Kept for
        snapshots cached inside saves made under an older mod version and not
        yet re-captured under the current code — every menu revisit naturally
        replaces the cache entry with the current shape, so this path only
        ever serves stale, not-yet-revisited nodes. Never returns.

        deepcopy roots and ctx so Ren'Py's post-unfreeze mutations don't corrupt the
        stored snapshot. Ren'Py's real unfreeze() aliases roots values directly into
        store_dicts (store[name] = value, no copy) — without this, any store var
        mutated in place after this jump (dict[key]=x, list.append) would silently
        corrupt this cached snapshot for every future jump to the same node.

        A deepcopy failure is not caught here: the snapshot either successfully
        deep-copies or the unfreeze fails outright — never falls back to handing
        out the original live/aliased reference (the exact bug fixed for the
        capture path in commit 5327730; this closes the matching hole on read).

        These pre-upgrade snaps never captured a historical rollback_limit, so there
        is no "value at that point in time" to reproduce. Fall back to the engine's
        configured ceiling (config.hard_rollback_limit) — never worse than the old
        hardcoded 1, and self-corrects to the real captured value the next time this
        node's snapshot is recaptured under the current format.
        """
        import copy as _copy
        roots = _copy.deepcopy(snap["roots"])
        ctx   = _copy.deepcopy(snap["context"])

        fallback_rollback_limit = getattr(renpy.config, "hard_rollback_limit", 1) or 1
        _tl_build_and_unfreeze(roots, ctx, "TL unfreeze legacy", fallback_rollback_limit)

    def _tl_unfreeze_from_snapshot(snap):
        """
        Dispatch on shape and unfreeze. Never returns. Caller is responsible for
        writing the recovery save and staging persistent vars before calling this.

        - {"roots": ..., "ctx": ..., "rollback_limit": ...} (current format): the
            cache-owned frozen roots/ctx are deep-copied fresh before being handed
            to Ren'Py's real unfreeze() — without this, the cache's own frozen
            objects (which may be shared by other cached snapshots) would get
            mutated in place by later gameplay, corrupting every snapshot that
            shares them.
        - {"roots": ..., "context": ...} (pre-blob legacy format, still present
            inside saves that haven't had every cached node re-visited yet):
            routed to _tl_unfreeze_legacy, unchanged from the original
            deepcopy-based behavior.
        """
        if "context" in snap:
            _tl_unfreeze_legacy(snap)
            return

        import copy as _copy
        roots          = _copy.deepcopy(snap["roots"])
        ctx            = _copy.deepcopy(snap["ctx"])
        rollback_limit = snap["rollback_limit"]

        _tl_build_and_unfreeze(roots, ctx, "TL unfreeze", rollback_limit)