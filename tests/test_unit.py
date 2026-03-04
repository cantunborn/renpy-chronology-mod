"""
Chronology Mod — Unit Tests

Location: renpy-chronology-mod/tests/test_unit.py
Run from mod root: python3 tests/test_unit.py
Or with pytest:    pytest tests/test_unit.py -v

No RenPy dependency — runs anywhere with Python 3.7+.
"""
import os
import sys
import hashlib
import tempfile

try:
    import pytest
except ImportError:
    pytest = None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from timeline_init_latest import (
    _tl_save_slot,
    _tl_find_nearest_save,
    _tl_validate_history,
    _tl_node_has_new,
    _tl_should_save,
)


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


# =============================================================================
# _tl_find_nearest_save
# =============================================================================

def make_save_files(save_dir, entries):
    """
    entries: list of (node_index, context_up_to_that_node)
    Creates _ch_NNNN_HHHHHH-LT1.save files in save_dir.
    """
    for idx, ctx in entries:
        slot = _tl_save_slot(idx, ctx)
        open(os.path.join(save_dir, slot + "-LT1.save"), "w").close()


class TestFindNearestSave:
    def test_finds_exact_match(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            make_save_files(d, [(0, ctx)])
            result = _tl_find_nearest_save(0, ctx, d)
            assert result == _tl_save_slot(0, ctx)

    def test_finds_closest_below_target(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1), ("C", 0), ("D", 1)]
            # saves at 0 and 2
            make_save_files(d, [(0, ctx[:1]), (2, ctx[:3])])
            # looking for target=3, nearest should be 2
            result = _tl_find_nearest_save(3, ctx, d)
            assert result == _tl_save_slot(2, ctx[:3])

    def test_ignores_saves_above_target(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            make_save_files(d, [(0, ctx[:1]), (1, ctx)])
            # target=0, save at 1 should be ignored
            result = _tl_find_nearest_save(0, ctx, d)
            assert result == _tl_save_slot(0, ctx[:1])

    def test_ignores_wrong_branch_hash(self):
        with tempfile.TemporaryDirectory() as d:
            ctx_a = [("A", 0)]
            ctx_b = [("A", 1)]  # different branch
            make_save_files(d, [(0, ctx_a)])
            # searching with ctx_b should not find ctx_a's save
            result = _tl_find_nearest_save(0, ctx_b, d)
            assert result is None

    def test_falls_back_to_ch_start(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 1)]
            result = _tl_find_nearest_save(0, ctx, d, start_exists=True)
            assert result == "_ch_start"

    def test_no_saves_no_start_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            result = _tl_find_nearest_save(5, [("A", 0)], d, start_exists=False)
            assert result is None

    def test_ignores_recovery_and_start_files(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "_ch_recovery-LT1.save"), "w").close()
            open(os.path.join(d, "_ch_start-LT1.save"), "w").close()
            ctx = [("A", 0)]
            result = _tl_find_nearest_save(5, ctx, d)
            assert result is None

    def test_picks_highest_valid_index(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 0), ("C", 0), ("D", 0), ("E", 0)]
            make_save_files(d, [(0, ctx[:1]), (2, ctx[:3]), (4, ctx[:5])])
            result = _tl_find_nearest_save(4, ctx, d)
            assert result == _tl_save_slot(4, ctx[:5])

    def test_context_prefix_must_match(self):
        """Save at index 2 with ctx A,B,C should not match search with ctx A,B,X."""
        with tempfile.TemporaryDirectory() as d:
            ctx_saved  = [("A", 0), ("B", 1), ("C", 0)]
            ctx_search = [("A", 0), ("B", 1), ("X", 0)]  # diverged at node 2
            make_save_files(d, [(2, ctx_saved)])
            result = _tl_find_nearest_save(2, ctx_search, d)
            assert result is None


# =============================================================================
# _tl_validate_history
# =============================================================================

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


# =============================================================================
# _tl_node_has_new
# =============================================================================

class TestNodeHasNew:
    def all_seen(self, node, i):
        return True

    def none_seen(self, node, i):
        return False

    def first_seen(self, node, i):
        return i == 0

    def test_all_seen_returns_false(self):
        node = make_node(0, ["A", "B", "C"])
        assert _tl_node_has_new(node, self.all_seen) is False

    def test_none_seen_returns_true(self):
        node = make_node(0, ["A", "B"])
        assert _tl_node_has_new(node, self.none_seen) is True

    def test_partial_seen_returns_true(self):
        node = make_node(0, ["A", "B", "C"])
        assert _tl_node_has_new(node, self.first_seen) is True

    def test_single_option_seen(self):
        node = make_node(0, ["A"])
        assert _tl_node_has_new(node, self.all_seen) is False

    def test_single_option_unseen(self):
        node = make_node(0, ["A"])
        assert _tl_node_has_new(node, self.none_seen) is True

    def test_empty_options(self):
        node = make_node(0, [])
        assert _tl_node_has_new(node, self.none_seen) is False


# =============================================================================
# Context accumulation (simulated)
# =============================================================================

class TestContextAccumulation:
    """Simulate the _tl_context += [(prompt, i)] pattern."""

    def test_context_grows_per_choice(self):
        ctx = []
        ctx = ctx + [("Choose side", 0)]
        ctx = ctx + [("Attack?", 1)]
        assert len(ctx) == 2
        assert ctx[0] == ("Choose side", 0)
        assert ctx[1] == ("Attack?", 1)

    def test_save_slot_consistent_with_context_prefix(self):
        ctx = [("A", 0), ("B", 1), ("C", 0)]
        # save at node 1 uses ctx[:2]
        slot_at_1 = _tl_save_slot(1, ctx[:2])
        # find_nearest with full ctx should find it
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, slot_at_1 + "-LT1.save"), "w").close()
            result = _tl_find_nearest_save(2, ctx, d)
            assert result == slot_at_1

    def test_diverged_branch_gets_different_slot(self):
        ctx_main   = [("A", 0), ("B", 0)]
        ctx_branch = [("A", 0), ("B", 1)]
        assert _tl_save_slot(1, ctx_main) != _tl_save_slot(1, ctx_branch)


# =============================================================================
# _tl_should_save
# =============================================================================

class TestSaveDecision:
    def test_dense_saves_idx_0_to_4(self):
        for i in range(5):
            assert _tl_should_save(i) is True, "idx={} should be dense-saved".format(i)

    def test_last_dense_boundary(self):
        assert _tl_should_save(4) is True

    def test_first_past_dense_no_sparse(self):
        assert _tl_should_save(5) is False

    def test_first_sparse_milestone(self):
        assert _tl_should_save(9) is True   # idx 9 → 9 % 10 == 9 == 10-1

    def test_between_sparse_milestones(self):
        for i in [10, 11, 14, 15, 18]:
            assert _tl_should_save(i) is False, "idx={} should not save".format(i)

    def test_second_sparse_milestone(self):
        assert _tl_should_save(19) is True

    def test_custom_dense_and_every(self):
        assert _tl_should_save(2, dense=3, every=5) is True   # dense zone
        assert _tl_should_save(3, dense=3, every=5) is False  # past dense, not sparse
        assert _tl_should_save(4, dense=3, every=5) is True   # 4 % 5 == 4 == 5-1


# =============================================================================
# Two-phase save slot consistency
# =============================================================================

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


# =============================================================================
# Additional _tl_find_nearest_save cases
# =============================================================================

class TestFindNearestSaveDensePattern:
    def test_dense_pattern_finds_highest(self):
        """Saves at 0,1,2,3,4,9,19 — target 7 should return save 4."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 0), ("C", 0), ("D", 0), ("E", 0),
                   ("F", 1), ("G", 0), ("H", 1), ("I", 0), ("J", 1)]
            for i in [0, 1, 2, 3, 4, 9]:
                make_save_files(d, [(i, ctx[:i + 1])])
            result = _tl_find_nearest_save(7, ctx, d)
            assert result == _tl_save_slot(4, ctx[:5])

    def test_sparse_gap_returns_lower_save(self):
        """Saves at 9 and 19 — target 15 should return save 9, not 19."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("Q{}".format(i), 0) for i in range(20)]
            make_save_files(d, [(9, ctx[:10]), (19, ctx[:20])])
            result = _tl_find_nearest_save(15, ctx, d)
            assert result == _tl_save_slot(9, ctx[:10])


if __name__ == "__main__":
    # Run all test methods directly without pytest
    import inspect
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
    sys.exit(0 if failed == 0 else 1)
