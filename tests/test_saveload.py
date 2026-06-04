"""
Tests for tl_saveload.rpy — save slot, nearest-save, save decision, chapter-end slot.
Run: pytest tests/test_saveload.py -v
"""
import os, sys, hashlib, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns, _tl_validate_history

_tl_save_slot             = _rpy_ns["_tl_save_slot"]
_tl_find_nearest_save     = _rpy_ns["_tl_find_nearest_save"]
_tl_should_save           = _rpy_ns["_tl_should_save"]
_tl_pre_save_slot         = _rpy_ns.get("_tl_pre_save_slot")
_tl_find_pre_save         = _rpy_ns.get("_tl_find_pre_save")
_tl_find_nearest_pre_save = _rpy_ns.get("_tl_find_nearest_pre_save")
_tl_find_nearest_any_save = _rpy_ns.get("_tl_find_nearest_any_save")
_tl_path_has_danger       = _rpy_ns.get("_tl_path_has_danger")


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
            result = _tl_find_nearest_save(5, ctx, d, start_exists=False)
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

    def test_chap_candidate_beats_lower_checkpoint(self):
        """Chapter-end save at index 5 should beat checkpoint at index 2."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 0), ("C", 0), ("D", 0), ("E", 0), ("F", 0)]
            make_save_files(d, [(2, ctx[:3])])
            result = _tl_find_nearest_save(7, ctx, d,
                chap_candidates=[(5, "_ch_chap_end_abc123")])
            assert result == "_ch_chap_end_abc123"

    def test_chap_candidate_ignored_above_target(self):
        """Chapter-end save above target should be ignored."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 0), ("C", 0)]
            make_save_files(d, [(0, ctx[:1])])
            result = _tl_find_nearest_save(2, ctx, d,
                chap_candidates=[(5, "_ch_chap_end_abc123")])
            assert result == _tl_save_slot(0, ctx[:1])

    def test_chap_candidate_used_when_no_checkpoint(self):
        """Chapter-end save used as sole candidate when no checkpoints match."""
        with tempfile.TemporaryDirectory() as d:
            result = _tl_find_nearest_save(10, [], d,
                chap_candidates=[(8, "_ch_chap_myend_deadbe")])
            assert result == "_ch_chap_myend_deadbe"

    def test_checkpoint_beats_lower_chap_candidate(self):
        """Checkpoint at index 9 should beat chapter-end save at index 5."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 10
            make_save_files(d, [(9, ctx[:10])])
            result = _tl_find_nearest_save(10, ctx, d,
                chap_candidates=[(5, "_ch_chap_end_abc123")])
            assert result == _tl_save_slot(9, ctx[:10])

    def test_meta_index_populated(self):
        """_meta["index"] equals the index of the returned slot."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 0), ("C", 0)]
            make_save_files(d, [(2, ctx[:3])])
            meta = {}
            _tl_find_nearest_save(5, ctx, d, _meta=meta)
            assert meta["index"] == 2

    def test_meta_index_with_chap_candidate(self):
        """_meta["index"] reflects chapter-end save when it wins."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 0)]
            make_save_files(d, [(1, ctx[:2])])
            meta = {}
            _tl_find_nearest_save(10, ctx, d,
                chap_candidates=[(7, "_ch_chap_end_xyz")], _meta=meta)
            assert meta["index"] == 7

    def test_meta_index_minus1_when_none_found(self):
        """_meta["index"] is -1 when no slot is found."""
        with tempfile.TemporaryDirectory() as d:
            meta = {}
            _tl_find_nearest_save(5, [("A", 1)], d, start_exists=False, _meta=meta)
            assert meta["index"] == -1


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




# =============================================================================
# _tl_pre_save_slot
# =============================================================================

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
# _tl_find_nearest_pre_save
# =============================================================================

class TestFindNearestPreSave:
    def setup_method(self):
        assert _tl_find_nearest_pre_save is not None, "_tl_find_nearest_pre_save not found"

    def test_returns_none_when_empty(self):
        with tempfile.TemporaryDirectory() as d:
            assert _tl_find_nearest_pre_save(5, [("A", 0)], save_dir=d) is None

    def test_returns_none_when_only_above_target(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            make_pre_save_files(d, [(6, ctx)])
            assert _tl_find_nearest_pre_save(5, ctx, save_dir=d) is None

    def test_finds_exact_match(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            make_pre_save_files(d, [(5, ctx)])
            result = _tl_find_nearest_pre_save(5, ctx, save_dir=d)
            assert result == _tl_pre_save_slot(5, ctx)

    def test_finds_below_target(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1), ("C", 0)]
            make_pre_save_files(d, [(3, ctx)])
            result = _tl_find_nearest_pre_save(5, ctx, save_dir=d)
            assert result == _tl_pre_save_slot(3, ctx)

    def test_returns_highest_of_multiple_matches(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1), ("C", 0), ("D", 1), ("E", 0)]
            make_pre_save_files(d, [(1, ctx), (3, ctx), (5, ctx)])
            result = _tl_find_nearest_pre_save(4, ctx, save_dir=d)
            assert result == _tl_pre_save_slot(3, ctx)

    def test_wrong_hash_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            ctx_a = [("A", 0), ("B", 0)]
            ctx_b = [("A", 0), ("B", 1)]  ## different choice at index 1
            make_pre_save_files(d, [(3, ctx_a)])
            assert _tl_find_nearest_pre_save(5, ctx_b, save_dir=d) is None

    def test_handles_malformed_filename(self):
        with tempfile.TemporaryDirectory() as d:
            ## Write a malformed _pre_* file that doesn't parse cleanly
            open(os.path.join(d, "_pre_XXXX-LT1.save"), "w").close()
            open(os.path.join(d, "_pre_-LT1.save"), "w").close()
            ctx = [("A", 0)]
            result = _tl_find_nearest_pre_save(5, ctx, save_dir=d)
            assert result is None  ## no crash, no false positive

    def test_ignores_non_pre_files(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)]
            open(os.path.join(d, "_ch_0003_abc123-LT1.save"), "w").close()
            assert _tl_find_nearest_pre_save(5, ctx, save_dir=d) is None

    def test_returns_slot_not_path(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            make_pre_save_files(d, [(2, ctx)])
            result = _tl_find_nearest_pre_save(5, ctx, save_dir=d)
            assert result is not None
            assert os.sep not in result
            assert result.startswith("_pre_")

    def test_history_ast_key_used_for_hash(self):
        # File written with ast_key; scan finds it when history supplies matching ast_key
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            ak  = ("game/loc1.rpy", 42)
            make_pre_save_files(d, [(2, ctx, ak)])
            history = [{"index": 2, "ast_key": list(ak)}]
            result = _tl_find_nearest_pre_save(5, ctx, history=history, save_dir=d)
            assert result == _tl_pre_save_slot(2, ctx, ak)

    def test_history_ast_key_wrong_misses(self):
        # File written with ast_key; scan misses when history has different ast_key
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            make_pre_save_files(d, [(2, ctx, ("game/loc1.rpy", 42))])
            history = [{"index": 2, "ast_key": ["game/loc2.rpy", 42]}]
            result = _tl_find_nearest_pre_save(5, ctx, history=history, save_dir=d)
            assert result is None

    def test_no_history_falls_back_to_null_ast_key(self):
        # No history → ast_key=None; file written without ast_key is found
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            make_pre_save_files(d, [(2, ctx)])  # ast_key=None
            result = _tl_find_nearest_pre_save(5, ctx, save_dir=d)
            assert result == _tl_pre_save_slot(2, ctx)

    def test_meta_index_populated(self):
        """_meta["index"] equals the winning slot's node index."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1), ("C", 0)]
            make_pre_save_files(d, [(3, ctx)])
            meta = {}
            _tl_find_nearest_pre_save(5, ctx, save_dir=d, _meta=meta)
            assert meta["index"] == 3

    def test_meta_index_minus1_when_none_found(self):
        """_meta["index"] is -1 when no pre-save matches."""
        with tempfile.TemporaryDirectory() as d:
            meta = {}
            _tl_find_nearest_pre_save(5, [("A", 0)], save_dir=d, _meta=meta)
            assert meta["index"] == -1


# =============================================================================
# _tl_find_nearest_pre_save — history-first path
# =============================================================================

def _make_hist(index, ast_key=None):
    return {"index": index, "ast_key": list(ast_key) if ast_key else None,
            "_location": None}


class TestFindNearestPreSaveHistoryFirst:
    def setup_method(self):
        assert _tl_find_nearest_pre_save is not None

    def test_history_returns_highest_valid(self):
        """History entries at 1,3,5; files at 3 and 5; target=6 → slot at 5."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 6
            make_pre_save_files(d, [(3, ctx), (5, ctx)])
            history = [_make_hist(1), _make_hist(3), _make_hist(5)]
            result = _tl_find_nearest_pre_save(6, ctx, history=history, save_dir=d)
            assert result == _tl_pre_save_slot(5, ctx)

    def test_history_entry_with_no_file_falls_to_lower(self):
        """Entry at 7 has no file; entry at 4 does → slot at 4."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 8
            make_pre_save_files(d, [(4, ctx)])
            history = [_make_hist(4), _make_hist(7)]
            result = _tl_find_nearest_pre_save(8, ctx, history=history, save_dir=d)
            assert result == _tl_pre_save_slot(4, ctx)

    def test_history_ignores_entry_above_target(self):
        """Entry at 7 is above target=5; file at 4 → slot at 4."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 8
            make_pre_save_files(d, [(4, ctx)])
            history = [_make_hist(4), _make_hist(7)]
            result = _tl_find_nearest_pre_save(5, ctx, history=history, save_dir=d)
            assert result == _tl_pre_save_slot(4, ctx)

    def test_history_with_ast_key_computes_correct_slot(self):
        """Entry at 3 with ast_key; file written with same ast_key → found."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            ak  = ("game/loc.rpy", 42)
            make_pre_save_files(d, [(3, ctx, ak)])
            history = [_make_hist(3, ak)]
            result = _tl_find_nearest_pre_save(5, ctx, history=history, save_dir=d)
            assert result == _tl_pre_save_slot(3, ctx, ak)

    def test_history_wrong_ast_key_falls_to_lower(self):
        """Entry at 5 with wrong ast_key (file under different hash); entry at 3 correct → slot at 3."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 6
            ak_correct = ("game/loc.rpy", 10)
            ak_wrong   = ("game/loc.rpy", 99)
            make_pre_save_files(d, [(5, ctx, ak_correct), (3, ctx, ak_correct)])
            history = [_make_hist(3, ak_correct), _make_hist(5, ak_wrong)]
            result = _tl_find_nearest_pre_save(6, ctx, history=history, save_dir=d)
            assert result == _tl_pre_save_slot(3, ctx, ak_correct)


# =============================================================================
# _tl_find_nearest_any_save
# =============================================================================

class TestFindNearestAnySave:
    def setup_method(self):
        assert _tl_find_nearest_any_save is not None, "_tl_find_nearest_any_save not found"

    def test_ch_closer_than_pre_wins(self):
        """_ch_* at index 8 beats pre-save at index 3 when targeting index 9."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 10
            make_save_files(d,     [(8, ctx[:9])])   # _ch_* at 8
            make_pre_save_files(d, [(3, ctx)])        # _pre_* at 3
            result = _tl_find_nearest_any_save(9, ctx, save_dir=d)
            assert result == _tl_save_slot(8, ctx[:9])

    def test_pre_closer_than_ch_wins(self):
        """pre-save at index 7 beats _ch_* at index 2 when targeting index 9."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 10
            make_save_files(d,     [(2, ctx[:3])])   # _ch_* at 2
            make_pre_save_files(d, [(7, ctx)])        # _pre_* at 7
            result = _tl_find_nearest_any_save(9, ctx, save_dir=d)
            assert result == _tl_pre_save_slot(7, ctx)

    def test_only_ch_available(self):
        """Old-style save: only _ch_* present, no pre-saves → returns _ch_*."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 0), ("C", 0)]
            make_save_files(d, [(2, ctx[:3])])
            result = _tl_find_nearest_any_save(5, ctx, save_dir=d)
            assert result == _tl_save_slot(2, ctx[:3])

    def test_only_pre_available(self):
        """New-style save: only pre-saves present, no _ch_* → returns _pre_*."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0), ("B", 1)]
            make_pre_save_files(d, [(4, ctx)])
            result = _tl_find_nearest_any_save(6, ctx, save_dir=d)
            assert result == _tl_pre_save_slot(4, ctx)

    def test_chapter_end_beats_distant_pre(self):
        """Chapter-end save at index 9 beats pre-save at index 3."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 12
            make_pre_save_files(d, [(3, ctx)])
            result = _tl_find_nearest_any_save(11, ctx,
                chap_candidates=[(9, "_ch_chap_end_abc123")], save_dir=d)
            assert result == "_ch_chap_end_abc123"

    def test_pre_beats_distant_chapter_end(self):
        """Pre-save at index 8 beats chapter-end save at index 2."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 10
            make_pre_save_files(d, [(8, ctx)])
            result = _tl_find_nearest_any_save(9, ctx,
                chap_candidates=[(2, "_ch_chap_end_abc123")], save_dir=d)
            assert result == _tl_pre_save_slot(8, ctx)

    def test_nothing_found_returns_none(self):
        """No saves of any kind → None."""
        with tempfile.TemporaryDirectory() as d:
            result = _tl_find_nearest_any_save(5, [("A", 0)], save_dir=d)
            assert result is None

    def test_equal_index_prefers_pre(self):
        """When both pools return the same index, pre-save is preferred (>=)."""
        with tempfile.TemporaryDirectory() as d:
            ctx = [("A", 0)] * 6
            make_save_files(d,     [(5, ctx[:6])])   # _ch_* at 5
            make_pre_save_files(d, [(5, ctx)])        # _pre_* at 5
            result = _tl_find_nearest_any_save(5, ctx, save_dir=d)
            assert result == _tl_pre_save_slot(5, ctx)


# =============================================================================
# _tl_path_has_danger
# =============================================================================

import conftest as _cf

Jump   = _cf.Jump
Menu   = _cf.Menu
If     = _cf.If

class TestPathHasDanger:
    def setup_method(self):
        assert _tl_path_has_danger is not None, "_tl_path_has_danger not found"

    def _danger(self, block, roots=None, label_map=None, danger_labels=None):
        return _tl_path_has_danger(
            block,
            roots or {},
            label_map or {},
            danger_labels or set(),
        )

    def test_empty_block_is_safe(self):
        assert self._danger([]) is False

    def test_menu_stops_walk(self):
        assert self._danger([Menu()]) is False

    def test_jump_to_danger_label(self):
        assert self._danger([Jump("bad")], danger_labels={"bad"}) is True

    def test_jump_to_safe_label(self):
        assert self._danger([Jump("safe")], danger_labels=set()) is False

    def test_jump_to_unknown_label_is_safe(self):
        ## label not in label_map, not in danger — nothing to follow
        assert self._danger([Jump("unknown")]) is False

    def test_jump_then_menu_in_target(self):
        ## Jump to label whose block contains only a Menu → safe
        assert self._danger(
            [Jump("a")],
            label_map={"a": [Menu()]},
            danger_labels={"bad"},
        ) is False

    def test_jump_chain_reaches_danger(self):
        ## Jump → a → Jump → bad; "bad" in danger_labels
        assert self._danger(
            [Jump("a")],
            label_map={"a": [Jump("bad")]},
            danger_labels={"bad"},
        ) is True

    def test_jump_cycle_no_infinite_loop(self):
        ## a → a (cycle); must terminate
        assert self._danger(
            [Jump("a")],
            label_map={"a": [Jump("a")]},
            danger_labels=set(),
        ) is False

    def test_if_true_branch_follows_danger(self):
        if_node = If(entries=[("True", [Jump("bad")])])
        assert self._danger([if_node], danger_labels={"bad"}) is True

    def test_if_false_branch_skipped(self):
        ## "False" evaluates to False — branch not followed
        if_node = If(entries=[("False", [Jump("bad")])])
        assert self._danger([if_node], danger_labels={"bad"}) is False

    def test_if_eval_true_from_roots(self):
        if_node = If(entries=[("route == 'romance'", [Jump("bad")])])
        assert self._danger(
            [if_node],
            roots={"route": "romance"},
            danger_labels={"bad"},
        ) is True

    def test_if_eval_false_from_roots_skips_branch(self):
        if_node = If(entries=[("route == 'romance'", [Jump("bad")])])
        assert self._danger(
            [if_node],
            roots={"route": "friendship"},
            danger_labels={"bad"},
        ) is False

    def test_if_eval_error_conservative(self):
        ## Undefined name → NameError → conservative → follows branch → True
        if_node = If(entries=[("undefined_var_xyz + something", [Jump("bad")])])
        assert self._danger([if_node], danger_labels={"bad"}) is True

    def test_if_else_branch(self):
        ## "else" is treated same as "True"
        if_node = If(entries=[("else", [Jump("bad")])])
        assert self._danger([if_node], danger_labels={"bad"}) is True

    def test_node_before_menu_stops_at_menu(self):
        ## Say-like stub before Menu — should still stop at Menu, not danger beyond
        class Say(_cf._TLNode):
            def __init__(self): super().__init__("Say")
        assert self._danger([Say(), Menu(), Jump("bad")], danger_labels={"bad"}) is False


# =============================================================================
# _tl_salvage_history_ast_keys
# =============================================================================

import sys as _sys
import types as _types
import conftest as _cf
_renpy = _sys.modules["renpy"]
_salvage = _rpy_ns.get("_tl_salvage_history_ast_keys")

def _make_menu_stub(filename, linenumber, option_labels):
    """Build a Menu stub (type name 'Menu') with real option items."""
    m = _cf.Menu(items=[(lbl, "True", []) for lbl in option_labels])
    m.filename   = filename
    m.linenumber = linenumber
    return m

def _reset_lookup_cache():
    """Clear the runtime cache so _tl_live_menu_lookup() rebuilds from namemap."""
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
