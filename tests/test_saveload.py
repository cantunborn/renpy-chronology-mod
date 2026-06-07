"""
Tests for tl_saveload.rpy — save slot, pre-save slot, find_pre_save, find_slot, validate history.
Run: pytest tests/test_saveload.py -v
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns, _tl_validate_history, _store as _conftest_store

_tl_save_slot          = _rpy_ns["_tl_save_slot"]
_tl_pre_save_slot      = _rpy_ns["_tl_pre_save_slot"]
_tl_find_pre_save      = _rpy_ns["_tl_find_pre_save"]
_find_slot             = _rpy_ns["_find_slot"]
_tl_chap_end_slot_name = _rpy_ns["_tl_chap_end_slot_name"]
_renpy                 = _rpy_ns["renpy"]


# =============================================================================
# _tl_save_slot
# =============================================================================

class TestSaveSlot:
    def test_format(self):
        slot = _tl_save_slot(0, [])
        assert slot.startswith("_ch_0000_")
        assert len(slot) == len("_ch_0000_") + 6

    def test_index_padded(self):
        assert _tl_save_slot(1, []  ).startswith("_ch_0001_")
        assert _tl_save_slot(99, [] ).startswith("_ch_0099_")
        assert _tl_save_slot(999, []).startswith("_ch_0999_")

    def test_same_context_same_hash(self):
        ctx = [("Do you trust her?", 1), ("Strike?", 0)]
        assert _tl_save_slot(2, ctx) == _tl_save_slot(2, ctx)

    def test_different_context_different_hash(self):
        ctx_a = [("Do you trust her?", 0)]
        ctx_b = [("Do you trust her?", 1)]
        assert _tl_save_slot(0, ctx_a) != _tl_save_slot(0, ctx_b)

    def test_different_index_different_slot(self):
        ctx = [("X", 0)]
        assert _tl_save_slot(0, ctx) != _tl_save_slot(1, ctx)

    def test_hash_length_is_6(self):
        slot = _tl_save_slot(5, [("a", 0)])
        hash_part = slot.split("_")[-1]
        assert len(hash_part) == 6

    def test_empty_context(self):
        # Should not raise
        slot = _tl_save_slot(0, [])
        assert "_ch_0000_" in slot

    def test_large_index(self):
        slot = _tl_save_slot(9999, [])
        assert slot.startswith("_ch_9999_")


def make_node(index, options=None):
    if options is None:
        options = ["A", "B"]
    return {
        "index": index,
        "options": options,
        "chosen_index": None,
        "prompt": "Test?",
    }


class TestValidateHistory:
    def test_valid_history_unchanged(self):
        h = [make_node(0), make_node(1)]
        result = _tl_validate_history(h)
        assert len(result) == 2

    def test_drops_non_dict(self):
        h = [make_node(0), "garbage", 42, None, make_node(1)]
        result = _tl_validate_history(h)
        assert len(result) == 2

    def test_drops_missing_index_key(self):
        bad = {"options": ["A"], "prompt": "?"}
        h = [make_node(0), bad]
        result = _tl_validate_history(h)
        assert len(result) == 1

    def test_drops_missing_options_key(self):
        bad = {"index": 1, "prompt": "?"}
        h = [make_node(0), bad]
        result = _tl_validate_history(h)
        assert len(result) == 1

    def test_drops_options_not_list(self):
        bad = {"index": 1, "options": "A,B", "prompt": "?"}
        h = [make_node(0), bad]
        result = _tl_validate_history(h)
        assert len(result) == 1

    def test_reindexes_after_drop(self):
        bad = {"index": 1, "prompt": "?"}  # missing options
        h = [make_node(0), bad, make_node(2)]
        result = _tl_validate_history(h)
        assert result[0]["index"] == 0
        assert result[1]["index"] == 1  # was 2, reindexed to 1

    def test_not_a_list_returns_empty(self):
        assert _tl_validate_history(None) == []
        assert _tl_validate_history({}) == []
        assert _tl_validate_history("oops") == []

    def test_empty_list_ok(self):
        assert _tl_validate_history([]) == []

    def test_empty_options_list_ok(self):
        node = make_node(0, options=[])
        result = _tl_validate_history([node])
        assert len(result) == 1


class TestTwoPhaseSlotConsistency:
    """Early save and refresh must produce the same filename."""

    def test_same_slot_before_and_after_next_node(self):
        # ctx after node 0 choice is made: [(prompt0, 0)]
        ctx = [("Which path?", 0)]
        # Early write: save slot for node 0 with ctx[:1]
        early = _tl_save_slot(0, ctx[:1])
        # Refresh write: fires at start of node 1's record_before.
        # Context is still ctx[:1] — node 1 choice hasn't happened yet.
        refresh = _tl_save_slot(0, ctx[:1])
        assert early == refresh

    def test_refresh_does_not_use_next_choice(self):
        ctx_before = [("A?", 1)]
        ctx_after  = [("A?", 1), ("B?", 0)]  # node 1 choice added
        # Refresh fires BEFORE node 1 choice, so it must not include ctx[1]
        assert _tl_save_slot(0, ctx_before) != _tl_save_slot(0, ctx_after)

    def test_multiple_nodes_same_slot_pattern(self):
        ctx = [("X", 0), ("Y", 1), ("Z", 0)]
        for idx in range(len(ctx)):
            # Save at node idx uses context up to and including that node's choice
            early   = _tl_save_slot(idx, ctx[:idx + 1])
            refresh = _tl_save_slot(idx, ctx[:idx + 1])
            assert early == refresh, "Mismatch at node {}".format(idx)


class TestPreSaveSlot:
    def setup_method(self):
        assert _tl_pre_save_slot is not None, "_tl_pre_save_slot not found in namespace"

    def test_format(self):
        slot = _tl_pre_save_slot(0, [])
        assert slot.startswith("_pre_0000_")

    def test_index_padded(self):
        assert _tl_pre_save_slot(1,    []).startswith("_pre_0001_")
        assert _tl_pre_save_slot(99,   []).startswith("_pre_0099_")
        assert _tl_pre_save_slot(9999, []).startswith("_pre_9999_")

    def test_hash_length_is_6(self):
        slot = _tl_pre_save_slot(5, [("a", 0)])
        suffix = slot.split("_")[-1]
        assert len(suffix) == 6

    def test_deterministic(self):
        ctx = [("Choose", 0), ("Attack?", 1)]
        assert _tl_pre_save_slot(2, ctx) == _tl_pre_save_slot(2, ctx)

    def test_context_sensitive(self):
        # Different choice at index 1 → different hash at node 2
        ctx_a = [("Choose", 0), ("Attack?", 0)]
        ctx_b = [("Choose", 0), ("Attack?", 1)]
        assert _tl_pre_save_slot(2, ctx_a) != _tl_pre_save_slot(2, ctx_b)

    def test_index_sensitive(self):
        ctx = [("Choose", 0)]
        assert _tl_pre_save_slot(0, ctx) != _tl_pre_save_slot(1, ctx)

    def test_different_from_post_choice(self):
        # Pre-save hashes context[:N], post-choice hashes full context — must differ
        ctx = [("Choose", 0), ("Attack?", 1)]
        assert _tl_pre_save_slot(2, ctx) != _tl_save_slot(2, ctx)

    def test_menu0_empty_context_is_constant(self):
        # context[:0] == [] for all playthroughs — menu 0 always same hash
        assert _tl_pre_save_slot(0, []) == _tl_pre_save_slot(0, [("any", 99)])

    def test_uses_only_context_up_to_n(self):
        # context[N:] is irrelevant — same prefix → same slot
        ctx_short = [("A", 0)]
        ctx_long  = [("A", 0), ("B", 1), ("C", 2)]
        assert _tl_pre_save_slot(1, ctx_short) == _tl_pre_save_slot(1, ctx_long)

    def test_ast_key_affects_hash(self):
        # Different ast_key → different slot (sandbox disambiguator)
        ctx = [("A", 0)]
        slot_a = _tl_pre_save_slot(3, ctx, ast_key=("game/loc1.rpy", 10))
        slot_b = _tl_pre_save_slot(3, ctx, ast_key=("game/loc2.rpy", 10))
        assert slot_a != slot_b

    def test_ast_key_none_differs_from_given(self):
        ctx = [("A", 0)]
        assert _tl_pre_save_slot(3, ctx, ast_key=None) != _tl_pre_save_slot(3, ctx, ast_key=("game/foo.rpy", 5))

    def test_ast_key_deterministic(self):
        ctx = [("A", 0)]
        ak = ("game/loc1.rpy", 42)
        assert _tl_pre_save_slot(3, ctx, ast_key=ak) == _tl_pre_save_slot(3, ctx, ast_key=ak)


# =============================================================================
# _tl_find_pre_save
# =============================================================================

def make_pre_save_files(save_dir, entries):
    """entries: list of (node_index, context) or (node_index, context, ast_key)."""
    for entry in entries:
        idx, ctx = entry[0], entry[1]
        ak = entry[2] if len(entry) > 2 else None
        slot = _tl_pre_save_slot(idx, ctx, ast_key=ak)
        open(os.path.join(save_dir, slot + "-LT1.save"), "w").close()


class TestFindPreSave:
    def setup_method(self):
        assert _tl_find_pre_save is not None, "_tl_find_pre_save not found in namespace"

    def test_returns_none_when_no_file(self):
        with tempfile.TemporaryDirectory() as d:
            assert _tl_find_pre_save(3, [("A", 0)], save_dir=d) is None

    def test_finds_lt1_extension(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            make_pre_save_files(d, [(3, ctx)])
            result = _tl_find_pre_save(3, ctx, save_dir=d)
            assert result == _tl_pre_save_slot(3, ctx)

    def test_finds_plain_extension(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            slot = _tl_pre_save_slot(3, ctx)
            open(os.path.join(d, slot + ".save"), "w").close()
            assert _tl_find_pre_save(3, ctx, save_dir=d) == slot

    def test_wrong_hash_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            # File exists but with wrong context hash
            ctx_a = [("A", 0)]
            ctx_b = [("A", 1)]
            make_pre_save_files(d, [(3, ctx_a)])
            assert _tl_find_pre_save(3, ctx_b, save_dir=d) is None

    def test_wrong_index_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            make_pre_save_files(d, [(4, ctx)])
            assert _tl_find_pre_save(3, ctx, save_dir=d) is None

    def test_returns_slot_not_path(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            make_pre_save_files(d, [(3, ctx)])
            result = _tl_find_pre_save(3, ctx, save_dir=d)
            assert result is not None
            assert not os.sep in result
            assert result.startswith("_pre_")

    def test_ast_key_match_finds_file(self):
        # File written with ast_key; lookup with same ast_key finds it
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            ak  = ("game/loc1.rpy", 42)
            make_pre_save_files(d, [(3, ctx, ak)])
            assert _tl_find_pre_save(3, ctx, ast_key=ak, save_dir=d) == _tl_pre_save_slot(3, ctx, ak)

    def test_ast_key_mismatch_returns_none(self):
        # File written with ast_key; lookup with None misses it
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            ak  = ("game/loc1.rpy", 42)
            make_pre_save_files(d, [(3, ctx, ak)])
            assert _tl_find_pre_save(3, ctx, ast_key=None, save_dir=d) is None

    def test_ast_key_wrong_file_returns_none(self):
        # File written for loc1; lookup for loc2 misses it
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            make_pre_save_files(d, [(3, ctx, ("game/loc1.rpy", 42))])
            assert _tl_find_pre_save(3, ctx, ast_key=("game/loc2.rpy", 42), save_dir=d) is None


# =============================================================================
# _tl_salvage_history_ast_keys helpers
# =============================================================================

import conftest as _cf
_salvage = _rpy_ns.get("_tl_salvage_history_ast_keys")

def _make_menu_stub(filename, linenumber, option_labels):
    m = _cf.Menu(items=[(lbl, "True", []) for lbl in option_labels])
    m.filename   = filename
    m.linenumber = linenumber
    return m

def _reset_lookup_cache():
    _renpy.game.script._tl_runtime_cache_store = {}


class TestSalvageAstKeys:
    """_tl_salvage_history_ast_keys: re-match stale ast_keys after game script updates."""

    def setup_method(self):
        _renpy.game.script.namemap = {}
        _reset_lookup_cache()
        _rpy_ns["store"]._tl_history = []
        _renpy.game.script._tl_runtime_cache_store = {}

    def teardown_method(self):
        _renpy.game.script.namemap = {}
        _reset_lookup_cache()

    def test_stale_node_gets_rematched(self):
        """Stale ast_key → matched to nearby live menu with same options."""
        m = _make_menu_stub("script.rpy", 100, ["Option A", "Option B"])
        _renpy.game.script.namemap = {"k": m}
        _reset_lookup_cache()

        node = {"index": 0, "ast_key": ("script.rpy", 95),
                "options": ["Option A", "Option B"], "img_name": "bg noon"}
        _rpy_ns["store"]._tl_history = [node]

        r = _salvage()
        assert r["matched"] == 1
        assert r["skipped"] == 0
        assert r["unmatched"] == 0

    def test_valid_node_is_skipped(self):
        """Node whose ast_key is already valid in the live lookup is skipped untouched."""
        m = _make_menu_stub("script.rpy", 42, ["Yes", "No"])
        _renpy.game.script.namemap = {"k": m}
        _reset_lookup_cache()

        node = {"index": 0, "ast_key": ("script.rpy", 42),
                "options": ["Yes", "No"], "img_name": "bg room"}
        _rpy_ns["store"]._tl_history = [node]

        r = _salvage()
        assert r["skipped"] == 1
        assert r["matched"] == 0
        assert node["ast_key"] == ("script.rpy", 42)  ## untouched
        assert node["img_name"] == "bg room"           ## untouched

    def test_no_candidate_is_unmatched(self):
        """Stale node with no overlapping live menu options stays unmatched."""
        m = _make_menu_stub("script.rpy", 100, ["Alpha", "Beta"])
        _renpy.game.script.namemap = {"k": m}
        _reset_lookup_cache()

        node = {"index": 0, "ast_key": ("script.rpy", 90),
                "options": ["Gamma", "Delta"], "img_name": "bg noon"}
        _rpy_ns["store"]._tl_history = [node]

        r = _salvage()
        assert r["unmatched"] == 1
        assert r["matched"] == 0
        assert node["ast_key"] == ("script.rpy", 90)  ## unchanged

    def test_restamp_clears_img_name_and_updates_ast_key(self):
        """Matched node gets new ast_key and img_name cleared for re-migration."""
        m = _make_menu_stub("script.rpy", 200, ["Stay", "Leave"])
        _renpy.game.script.namemap = {"k": m}
        _reset_lookup_cache()

        node = {"index": 0, "ast_key": ("script.rpy", 185),
                "options": ["Stay", "Leave"], "img_name": "bg old"}
        _rpy_ns["store"]._tl_history = [node]

        _salvage()
        assert node["ast_key"] == ("script.rpy", 200)
        assert node["img_name"] is None


# =============================================================================
# _find_slot
# =============================================================================

def _set_savedir(path):
    _renpy.config.savedir = path


def _touch(directory, filename):
    open(os.path.join(directory, filename), "w").close()


def _make_hist_node(index, ast_key=None):
    return {"index": index, "options": ["A", "B"], "chosen_index": 0,
            "ast_key": ast_key, "_location": "loc{}".format(index)}


class TestFindSlot:
    """_find_slot: Tier 1 = exact pre-save, Tier 2 = downward walk, first hit wins."""

    def setup_method(self):
        self._old_savedir = _renpy.config.savedir
        self._old_markers = getattr(_conftest_store, "_tl_chapter_markers", [])
        _conftest_store._tl_chapter_markers = []

    def teardown_method(self):
        _set_savedir(self._old_savedir)
        _conftest_store._tl_chapter_markers = self._old_markers

    def test_tier1_exact_pre_save_at_target(self):
        with tempfile.TemporaryDirectory() as d:
            _set_savedir(d)
            ctx  = [("Q0", 0), ("Q1", 1), ("Q2", 0)]
            hist = [_make_hist_node(0), _make_hist_node(1), _make_hist_node(2)]
            slot = _tl_pre_save_slot(2, ctx, None)
            _touch(d, slot + "-LT1.save")
            assert _find_slot(2, hist, ctx) == slot

    def test_tier2_pre_save_at_lower_index(self):
        with tempfile.TemporaryDirectory() as d:
            _set_savedir(d)
            ctx  = [("Q0", 0), ("Q1", 1), ("Q2", 0)]
            hist = [_make_hist_node(0), _make_hist_node(1), _make_hist_node(2)]
            slot = _tl_pre_save_slot(1, ctx, None)
            _touch(d, slot + "-LT1.save")
            assert _find_slot(2, hist, ctx) == slot

    def test_tier2_checkpoint_save_at_lower_index(self):
        with tempfile.TemporaryDirectory() as d:
            _set_savedir(d)
            ctx  = [("Q0", 0), ("Q1", 1)]
            hist = [_make_hist_node(0), _make_hist_node(1)]
            slot = _tl_save_slot(0, ctx)
            _touch(d, slot + "-LT1.save")
            assert _find_slot(1, hist, ctx) == slot

    def test_tier2_closest_wins_over_farther_pre_save(self):
        """Pre-save at idx=1 wins over pre-save at idx=0 when jumping to idx=2."""
        with tempfile.TemporaryDirectory() as d:
            _set_savedir(d)
            ctx  = [("Q0", 0), ("Q1", 1), ("Q2", 0)]
            hist = [_make_hist_node(0), _make_hist_node(1), _make_hist_node(2)]
            slot0 = _tl_pre_save_slot(0, ctx, None)
            slot1 = _tl_pre_save_slot(1, ctx, None)
            _touch(d, slot0 + "-LT1.save")
            _touch(d, slot1 + "-LT1.save")
            assert _find_slot(2, hist, ctx) == slot1

    def test_tier2_chapter_end_save(self):
        with tempfile.TemporaryDirectory() as d:
            _set_savedir(d)
            ctx  = [("Q0", 0)]
            hist = [_make_hist_node(0)]
            _conftest_store._tl_chapter_markers = [
                {"end_label": "ch1_end", "after_index": 0}
            ]
            slot = _tl_chap_end_slot_name("ch1_end", ctx, 0)
            _touch(d, slot + "-LT1.save")
            assert _find_slot(1, hist, ctx) == slot

    def test_tier2_ch_start_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            _set_savedir(d)
            ctx  = [("Q0", 0)]
            hist = [_make_hist_node(0)]
            _touch(d, "_ch_start-LT1.save")
            assert _find_slot(1, hist, ctx) == "_ch_start"

    def test_no_saves_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            _set_savedir(d)
            ctx  = [("Q0", 0)]
            hist = [_make_hist_node(0)]
            assert _find_slot(1, hist, ctx) is None

    def test_checkpoint_beats_lower_pre_save(self):
        """_ch_ checkpoint at idx=1 beats pre-save at idx=0 (higher index wins)."""
        with tempfile.TemporaryDirectory() as d:
            _set_savedir(d)
            ctx  = [("Q0", 0), ("Q1", 1), ("Q2", 0)]
            hist = [_make_hist_node(0), _make_hist_node(1), _make_hist_node(2)]
            pre0 = _tl_pre_save_slot(0, ctx, None)
            chk1 = _tl_save_slot(1, ctx)
            _touch(d, pre0 + "-LT1.save")
            _touch(d, chk1 + "-LT1.save")
            assert _find_slot(2, hist, ctx) == chk1


if __name__ == "__main__":
    passed = failed = 0
    for cls_name, cls in sorted(globals().items()):
        if not (isinstance(cls, type) and cls_name.startswith("Test")):
            continue
        print("\n── {} ──".format(cls_name))
        inst = cls()
        for method_name in sorted(dir(inst)):
            if not method_name.startswith("test_"):
                continue
            try:
                getattr(inst, method_name)()
                print("  PASS  {}".format(method_name))
                passed += 1
            except Exception as e:
                print("  FAIL  {}  →  {}".format(method_name, e))
                failed += 1
    print("\n─────────────────────────────")
    print("Results: {} passed, {} failed".format(passed, failed))
    import sys; sys.exit(0 if failed == 0 else 1)
