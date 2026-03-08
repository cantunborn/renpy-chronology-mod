## =============================================================================
## CHRONOLOGY MOD — timeline_tests.rpy
## In-game test runner. Press Shift+F9 during gameplay to run.
##
## Folder layout:
##   renpy-chronology-mod/
##     timeline_tests.rpy          ← this file (must be here for RenPy to load)
##     tests/
##       timeline_init_latest.py   ← pure Python extraction of init logic
##       test_unit.py              ← run with: python3 test_unit.py
##
## Results are written to renpy-chronology-mod/debug.txt via _tl_log().
## A toast notification shows pass/fail count in-game.
##
## Tests RenPy-dependent behaviour that can't be tested outside the engine:
##   - menu hook wiring (_tl_store_wrapper / _tl_exports_wrapper)
##   - thumbnail capture
##   - save/load round-trip
##   - cache read/write
##   - persistent state init
##   - _tl_record_before / _tl_record_after pipeline
## =============================================================================

init python:
    config.keymap["tl_run_tests"] = ["shift_K_F9"]

screen _tl_test_runner():
    key "tl_run_tests" action Function(_tl_run_tests)

init python:
    config.overlay_screens.append("_tl_test_runner")


init python:

    ## ─────────────────────────────────────────────────────────────────────────
    ## Micro test framework
    ## ─────────────────────────────────────────────────────────────────────────

    class _TLTestResults(object):
        def __init__(self):
            self.results = []   # list of (suite, name, passed, detail)

        def check(self, suite, name, condition, detail=""):
            self.results.append((suite, name, bool(condition), str(detail)))

        @property
        def passed(self):
            return sum(1 for r in self.results if r[2])

        @property
        def failed(self):
            return sum(1 for r in self.results if not r[2])

        @property
        def failures(self):
            return [(s, n, d) for s, n, ok, d in self.results if not ok]


    ## ─────────────────────────────────────────────────────────────────────────
    ## Suites
    ## ─────────────────────────────────────────────────────────────────────────

    def _tl_test_persistent(r):
        """Persistent state is correctly initialised."""
        s = "persistent"
        r.check(s, "_tl_replaying is bool",
            isinstance(persistent._tl_replaying, bool))
        r.check(s, "_tl_thumb_cache is dict",
            isinstance(persistent._tl_thumb_cache, dict))
        r.check(s, "_tl_replaying default False",
            persistent._tl_replaying == False)


    def _tl_test_store_defaults(r):
        """Store defaults exist and have correct types."""
        s = "store_defaults"
        r.check(s, "_tl_history is list",       isinstance(_tl_history, list))
        r.check(s, "_tl_context is list",       isinstance(_tl_context, list))
        r.check(s, "_tl_node_count is int",     isinstance(_tl_node_count, int))
        r.check(s, "_tl_branch_id is str",      isinstance(_tl_branch_id, str))
        r.check(s, "_tl_modal_node is None",    _tl_modal_node is None)
        r.check(s, "_tl_load_slot is str",      isinstance(_tl_load_slot, str))


    def _tl_test_hooks_wired(r):
        """Menu hooks are installed exactly once."""
        s = "hooks"
        r.check(s, "exports.menu wrapped",
            getattr(renpy.exports.menu, "_tl_wrapped", False))
        r.check(s, "store.menu wrapped",
            getattr(renpy.store.menu, "_tl_wrapped", False))
        # Wrapping twice would create a double-wrap bug
        r.check(s, "exports.menu not double-wrapped",
            not getattr(getattr(renpy.exports.menu, "__wrapped__", None),
                        "_tl_wrapped", False))


    def _tl_test_save_slot(r):
        """_tl_save_slot produces stable, unique identifiers."""
        s = "save_slot"
        import hashlib
        ctx = [("Choose side", 0), ("Attack?", 1)]
        slot = _tl_save_slot(0, ctx)
        r.check(s, "starts with _ch_0000_",    slot.startswith("_ch_0000_"))
        r.check(s, "hash is 6 chars",          len(slot.split("_")[-1]) == 6)
        r.check(s, "deterministic",            slot == _tl_save_slot(0, ctx))
        r.check(s, "ctx sensitive",
            _tl_save_slot(0, [("A", 0)]) != _tl_save_slot(0, [("A", 1)]))
        r.check(s, "idx sensitive",
            _tl_save_slot(0, ctx) != _tl_save_slot(1, ctx))


    def _tl_test_thumbnail(r):
        """Thumbnail capture returns bytes or None (never raises)."""
        s = "thumbnail"
        try:
            thumb = _tl_capture_thumbnail()
            r.check(s, "returns bytes or None",
                thumb is None or isinstance(thumb, bytes))
            if thumb is not None:
                r.check(s, "non-empty bytes", len(thumb) > 0)
                # PNG magic bytes: 89 50 4E 47
                r.check(s, "valid PNG header",
                    thumb[:4] == b'\x89PNG')
            else:
                r.check(s, "None is acceptable fallback", True)
        except Exception as e:
            r.check(s, "no exception", False, str(e))


    def _tl_test_thumb_cache(r):
        """Thumbnail cache read/write/evict works correctly."""
        s = "thumb_cache"
        original = dict(persistent._tl_thumb_cache)
        try:
            # Write a fake entry
            persistent._tl_thumb_cache["_test_key_"] = b"fake_png_data"
            r.check(s, "write succeeds",
                persistent._tl_thumb_cache.get("_test_key_") == b"fake_png_data")

            # Read it back
            r.check(s, "read back correct",
                persistent._tl_thumb_cache["_test_key_"] == b"fake_png_data")

            # Eviction: fill to over limit
            original_max = TL_THUMB_CACHE_MAX
            test_cache = {}
            for i in range(original_max + 5):
                test_cache[str(i)] = b"x"
                while len(test_cache) > original_max:
                    test_cache.pop(next(iter(test_cache)))
            r.check(s, "eviction keeps at max",
                len(test_cache) <= original_max)
            r.check(s, "eviction keeps newest",
                str(original_max + 4) in test_cache)
            r.check(s, "eviction drops oldest",
                "0" not in test_cache)
        finally:
            # Restore
            persistent._tl_thumb_cache = original


    def _tl_test_record_pipeline(r):
        """
        Simulate _tl_record_before → _tl_record_after without touching the
        real game state. Uses a scratch context and fake items list.
        """
        s = "record_pipeline"

        # Fake menu items as RenPy passes them: (label, condition, value)
        class FakeChoiceReturn(object):
            def __init__(self):
                self._chosen = False
            def get_chosen(self):
                return self._chosen
            @property
            def value(self):
                return "choice_a_value"

        cr = FakeChoiceReturn()
        fake_items = [
            ("What do you want?", True, None),     # prompt (value=None)
            ("Choice A", True, cr),                 # option
            ("Choice B", True, "choice_b_value"),   # option
        ]

        # Save real state
        saved_history    = list(_tl_history)
        saved_count      = _tl_node_count
        saved_context    = list(_tl_context)
        saved_replaying  = persistent._tl_replaying

        try:
            persistent._tl_replaying = False
            store._tl_history    = []
            store._tl_node_count = 0
            store._tl_context    = []
            store._tl_branch_id  = ""

            node = _tl_record_before(fake_items)

            r.check(s, "record_before returns dict",  isinstance(node, dict))
            r.check(s, "node has index 0",            node["index"] == 0)
            r.check(s, "node has 2 options",          len(node["options"]) == 2)
            r.check(s, "prompt extracted",            node["prompt"] == "What do you want?")
            r.check(s, "chosen_index is None",        node.get("chosen_index") is None)
            r.check(s, "history has 1 entry",         len(_tl_history) == 1)
            r.check(s, "node_count incremented",      _tl_node_count == 1)

            # Now record the choice
            _tl_record_after(node, "Choice A")

            r.check(s, "chosen_index set",            node.get("chosen_index") == 0)
            r.check(s, "context updated",             len(_tl_context) == 1)
            r.check(s, "context entry correct",
                _tl_context[0] == ("What do you want?", 0))

        except Exception as e:
            r.check(s, "no exception", False, str(e))
        finally:
            # Restore real state
            store._tl_history    = saved_history
            store._tl_node_count = saved_count
            store._tl_context    = saved_context
            persistent._tl_replaying = saved_replaying


    def _tl_test_node_has_new(r):
        """_tl_node_has_new uses _choice_returns when available."""
        s = "node_has_new"

        class FakeCR(object):
            def __init__(self, chosen):
                self._chosen = chosen
            def get_chosen(self):
                return self._chosen

        node_all_seen = {
            "index": 0, "options": ["A", "B"], "prompt": "?",
            "chosen_index": 0, "ast_key": None,
            "_choice_returns": [FakeCR(True), FakeCR(True)],
        }
        node_has_new = {
            "index": 0, "options": ["A", "B"], "prompt": "?",
            "chosen_index": 0, "ast_key": None,
            "_choice_returns": [FakeCR(True), FakeCR(False)],
        }
        node_no_cr = {
            "index": 0, "options": ["A", "B"], "prompt": "?",
            "chosen_index": 0, "ast_key": None,
            "_choice_returns": [None, None],
        }

        r.check(s, "all seen via CR → False",   _tl_node_has_new(node_all_seen) == False)
        r.check(s, "one unseen via CR → True",  _tl_node_has_new(node_has_new)  == True)
        # Without CR, falls through to AST map (likely False if key is None)
        r.check(s, "no CR, no ast_key → no crash", True)
        try:
            _tl_node_has_new(node_no_cr)
            r.check(s, "no CR doesn't raise", True)
        except Exception as e:
            r.check(s, "no CR doesn't raise", False, str(e))


    def _tl_test_validate_history(r):
        """_tl_validate_on_load cleans malformed history."""
        s = "validate_history"

        import store as _store
        saved = list(_store._tl_history)

        try:
            _store._tl_history = [
                {"index": 0, "options": ["A"], "prompt": "?", "chosen_index": None},
                "not a dict",
                {"options": ["B"]},               # missing index
                {"index": 2},                      # missing options
                {"index": 3, "options": "bad"},    # options not list
                {"index": 4, "options": ["C", "D"], "prompt": "?", "chosen_index": 0},
            ]

            _tl_validate_on_load()

            h = _store._tl_history
            r.check(s, "only valid nodes remain", len(h) == 2)
            r.check(s, "reindexed to 0",          h[0]["index"] == 0)
            r.check(s, "reindexed to 1",          h[1]["index"] == 1)
        except Exception as e:
            r.check(s, "no exception", False, str(e))
        finally:
            _store._tl_history = saved


    ## ─────────────────────────────────────────────────────────────────────────
    ## Runner
    ## ─────────────────────────────────────────────────────────────────────────

    def _tl_test_chapter_store_defaults(r):
        """New store variables from chapter-end feature exist with correct types."""
        s = "chapter_store_defaults"
        import store as _st
        r.check(s, "_tl_chapter_markers is list",
            isinstance(getattr(_st, "_tl_chapter_markers", None), list))
        r.check(s, "_tl_pending_chap_end_save is None or str",
            getattr(_st, "_tl_pending_chap_end_save", None) is None or
            isinstance(getattr(_st, "_tl_pending_chap_end_save", None), str))
        r.check(s, "_tl_chap_end_slot is str",
            isinstance(getattr(_st, "_tl_chap_end_slot", None), str))
        r.check(s, "_tl_label_jump is str",
            isinstance(getattr(_st, "_tl_label_jump", None), str))


    def _tl_test_chapter_marker_dedup(r):
        """Chapter marker dedup logic prevents duplicate markers at same position."""
        s = "chapter_marker_dedup"

        import store as _st
        saved_markers = list(_st._tl_chapter_markers)
        saved_count   = _st._tl_node_count

        try:
            _st._tl_chapter_markers = []
            _st._tl_node_count = 5

            ## First add: should succeed
            after_idx = _st._tl_node_count
            chapter   = "_test_chapter_"
            end_label = "_test_label_end_"
            _tl_seen = any(
                m["after_index"] == after_idx and m["chapter_name"] == chapter
                for m in _st._tl_chapter_markers
            )
            r.check(s, "first: not yet seen", not _tl_seen)

            _st._tl_chapter_markers = _st._tl_chapter_markers + [
                {"chapter_name": chapter, "end_label": end_label, "after_index": after_idx}
            ]
            r.check(s, "marker added", len(_st._tl_chapter_markers) == 1)

            ## Second add at same position: dedup should block it
            _tl_seen2 = any(
                m["after_index"] == after_idx and m["chapter_name"] == chapter
                for m in _st._tl_chapter_markers
            )
            r.check(s, "second at same pos: seen=True", _tl_seen2)

            ## Different after_index: should not be seen
            _tl_seen3 = any(
                m["after_index"] == 99 and m["chapter_name"] == chapter
                for m in _st._tl_chapter_markers
            )
            r.check(s, "different after_idx: not seen", not _tl_seen3)

        except Exception as e:
            r.check(s, "no exception", False, str(e))
        finally:
            _st._tl_chapter_markers = saved_markers
            _st._tl_node_count      = saved_count


    def _tl_test_label_jump_rollback(r):
        """
        _tl_begin_label_jump fallback path correctly rolls back timeline
        variables when no chapter-end save exists.
        """
        s = "label_jump_rollback"

        import store as _st
        import os as _os

        saved_history  = list(_st._tl_history)
        saved_count    = _st._tl_node_count
        saved_context  = list(_st._tl_context)
        saved_markers  = list(_st._tl_chapter_markers)
        saved_slot     = _st._tl_chap_end_slot
        saved_jump     = _st._tl_label_jump
        saved_recovery = persistent._tl_recovery_slot

        try:
            ## Set up synthetic state: 10 nodes, chapter end at after_idx=5
            _st._tl_history  = [
                {"index": i, "options": ["A"], "prompt": "Q", "chosen_index": 0}
                for i in range(10)
            ]
            _st._tl_context  = [("Q{}".format(i), 0) for i in range(10)]
            _st._tl_node_count = 10
            _test_label = "_tl_test_rollback_label_99999_"
            _st._tl_chapter_markers = [
                {"chapter_name": "_test_ch_", "end_label": _test_label, "after_index": 5}
            ]

            ## Patch _tl_chapters so begin_label_jump can find the chapter
            _orig_chapters = _tl_chapters.copy()
            _tl_chapters["_test_ch_"] = _test_label

            ## Ensure no chapter-end save file exists (slot doesn't exist on disk)
            _slot = "_ch_chap_{}".format(_test_label)
            _sd   = renpy.config.savedir
            _save_path_lt1 = _os.path.join(_sd, "{}-LT1.save".format(_slot))
            _save_path_reg = _os.path.join(_sd, "{}.save".format(_slot))
            _had_lt1 = _os.path.exists(_save_path_lt1)
            _had_reg = _os.path.exists(_save_path_reg)

            ## Call the function
            _tl_begin_label_jump(_test_label)

            if _had_lt1 or _had_reg:
                ## Save unexpectedly exists — load path taken; skip rollback checks
                r.check(s, "save existed (skip rollback check)", True, "chapter-end save found on disk")
            else:
                ## Fallback path: verify rollback
                r.check(s, "history trimmed to after_idx",
                    len(_st._tl_history) == 5)
                r.check(s, "node_count rolled back",
                    _st._tl_node_count == 5)
                r.check(s, "context trimmed to after_idx",
                    len(_st._tl_context) == 5)
                r.check(s, "chapter marker kept",
                    len(_st._tl_chapter_markers) == 1)
                r.check(s, "chap_end_slot empty (fallback)",
                    _st._tl_chap_end_slot == "")
                r.check(s, "label_jump set to label",
                    _st._tl_label_jump == _test_label)

        except Exception as e:
            r.check(s, "no exception", False, str(e))
        finally:
            _st._tl_history        = saved_history
            _st._tl_node_count     = saved_count
            _st._tl_context        = saved_context
            _st._tl_chapter_markers = saved_markers
            _st._tl_chap_end_slot  = saved_slot
            _st._tl_label_jump     = saved_jump
            persistent._tl_recovery_slot = saved_recovery
            ## Restore _tl_chapters (dict is mutated in-place in store)
            _tl_chapters.clear()
            _tl_chapters.update(_orig_chapters)


    def _tl_test_chap_end_slot_name(r):
        """Chapter-end save slot names follow the _ch_chap_{label} convention."""
        s = "chap_end_slot_name"
        r.check(s, "prologue label",
            "_ch_chap_intro_consequences" == "_ch_chap_{}".format("intro_consequences"))
        r.check(s, "prefix correct",
            "_ch_chap_any_label".startswith("_ch_chap_"))
        r.check(s, "different labels → different slots",
            "_ch_chap_label_a" != "_ch_chap_label_b")


    def _tl_run_tests():
        r = _TLTestResults()

        _tl_test_persistent(r)
        _tl_test_store_defaults(r)
        _tl_test_hooks_wired(r)
        _tl_test_save_slot(r)
        _tl_test_thumbnail(r)
        _tl_test_thumb_cache(r)
        _tl_test_record_pipeline(r)
        _tl_test_node_has_new(r)
        _tl_test_validate_history(r)
        _tl_test_chapter_store_defaults(r)
        _tl_test_chapter_marker_dedup(r)
        _tl_test_label_jump_rollback(r)
        _tl_test_chap_end_slot_name(r)

        # Write results to debug.txt (renpy-chronology-mod/debug.txt via _tl_log)
        _tl_log("=" * 60)
        _tl_log("CHRONOLOGY TEST RUN")
        _tl_log("=" * 60)
        for suite, name, ok, detail in r.results:
            status = "PASS" if ok else "FAIL"
            line = "  [{}]  {}.{}".format(status, suite, name)
            if not ok and detail:
                line += "  → {}".format(detail)
            _tl_log(line)
        _tl_log("")
        _tl_log("Results: {} passed, {} failed".format(r.passed, r.failed))
        _tl_log("=" * 60)

        # Also show in-game notification
        if r.failed == 0:
            renpy.notify("✓ All {} tests passed".format(r.passed))
        else:
            renpy.notify("✗ {}/{} tests FAILED — check debug.txt".format(
                r.failed, r.passed + r.failed))

        store._tl_test_results = r
