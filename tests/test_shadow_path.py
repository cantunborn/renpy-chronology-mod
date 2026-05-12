"""
Tests for tl_shadow_path.rpy — shadow-path build, stage, match, and consume.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns

_tl_build_shadow_path   = _rpy_ns["_tl_build_shadow_path"]
_tl_stage_shadow_path   = _rpy_ns["_tl_stage_shadow_path"]
_tl_shadow_match        = _rpy_ns["_tl_shadow_match"]
_tl_consume_shadow_path = _rpy_ns["_tl_consume_shadow_path"]


def _make_node(index, location, chosen_index):
    return {"index": index, "_location": location, "chosen_index": chosen_index,
            "options": ["a", "b"]}


class TestBuildShadowPath:
    def test_basic(self):
        history = [_make_node(0, "loc0", 0), _make_node(1, "loc1", 1), _make_node(2, "loc2", 0)]
        path = _tl_build_shadow_path(history, node_index=0)
        assert path == [{"location": "loc1", "chosen_index": 1},
                        {"location": "loc2", "chosen_index": 0}]

    def test_target_excluded(self):
        history = [_make_node(0, "loc0", 1), _make_node(1, "loc1", 0)]
        path = _tl_build_shadow_path(history, node_index=0)
        assert not any(e["location"] == "loc0" for e in path)

    def test_nodes_before_target_excluded(self):
        history = [_make_node(0, "before", 0), _make_node(1, "target", 1), _make_node(2, "after", 0)]
        path = _tl_build_shadow_path(history, node_index=1)
        assert len(path) == 1
        assert path[0]["location"] == "after"

    def test_skips_none_location(self):
        n0 = _make_node(0, "loc0", 0)
        n1 = {"index": 1, "_location": None, "chosen_index": 0, "options": ["a"]}
        n2 = _make_node(2, "loc2", 1)
        path = _tl_build_shadow_path([n0, n1, n2], node_index=0)
        assert not any(e.get("location") is None and "menu_site_key" not in e for e in path)
        assert any(e.get("location") == "loc2" for e in path)

    def test_skips_none_chosen_index(self):
        n0 = _make_node(0, "loc0", 0)
        n1 = {"index": 1, "_location": "loc1", "chosen_index": None, "options": ["a"]}
        path = _tl_build_shadow_path([n0, n1], node_index=0)
        assert path == []

    def test_empty_after_target(self):
        history = [_make_node(0, "loc0", 0)]
        assert _tl_build_shadow_path(history, node_index=0) == []

    def test_target_not_in_history(self):
        history = [_make_node(0, "loc0", 0), _make_node(1, "loc1", 1)]
        assert _tl_build_shadow_path(history, node_index=99) == []

    def test_preserves_order(self):
        history = [_make_node(i, "loc{}".format(i), 0) for i in range(5)]
        path = _tl_build_shadow_path(history, node_index=0)
        locs = [e["location"] for e in path]
        assert locs == ["loc1", "loc2", "loc3", "loc4"]

    def test_carries_derived_site_key_when_ast_key_present(self):
        n0 = {"index": 0, "ast_key": ("f.rpy", 10), "_location": "loc0", "chosen_index": 0, "options": ["a"]}
        n1 = {"index": 1, "ast_key": ("f.rpy", 20), "_location": "loc1", "chosen_index": 1, "options": ["a"]}
        path = _tl_build_shadow_path([n0, n1], node_index=0)
        assert path == [{"menu_site_key": ["f.rpy", 20], "location": "loc1", "chosen_index": 1}]


class TestStageShadowPath:
    def test_returns_none_when_empty(self):
        history = [_make_node(0, "loc0", 0)]
        assert _tl_stage_shadow_path(history, 0) is None

    def test_preserves_menu_site_key_payload(self):
        n0 = {"index": 0, "ast_key": ("hub.rpy", 10), "_location": "loc0", "chosen_index": 0, "options": ["a"]}
        n1 = {"index": 1, "ast_key": ("hub.rpy", 20), "_location": "loc1", "chosen_index": 1, "options": ["a"]}
        assert _tl_stage_shadow_path([n0, n1], 0) == [
            {"menu_site_key": ["hub.rpy", 20], "location": "loc1", "chosen_index": 1}
        ]


class TestShadowMatch:
    def test_match_at_index_0(self):
        path = [{"location": "locA", "chosen_index": 1}]
        assert _tl_shadow_match(path, {"_location": "locA"}) == 1

    def test_match_at_index_gt_0(self):
        path = [{"location": "locX", "chosen_index": 0},
                {"location": "locA", "chosen_index": 2}]
        assert _tl_shadow_match(path, {"_location": "locA"}) == 2

    def test_no_match_returns_none(self):
        path = [{"location": "locA", "chosen_index": 1}]
        assert _tl_shadow_match(path, {"_location": "locB"}) is None

    def test_empty_path_returns_none(self):
        assert _tl_shadow_match([], {"_location": "locA"}) is None

    def test_first_match_wins_on_duplicate_location(self):
        path = [{"location": "locA", "chosen_index": 1},
                {"location": "locA", "chosen_index": 2}]
        assert _tl_shadow_match(path, {"_location": "locA"}) == 1

    def test_chosen_index_zero_is_valid(self):
        path = [{"location": "locA", "chosen_index": 0}]
        assert _tl_shadow_match(path, {"_location": "locA"}) == 0

    def test_uses_derived_site_key_over_shared_location(self):
        path = [
            {"menu_site_key": ["hub.rpy", 10], "location": "hub", "chosen_index": 1},
            {"menu_site_key": ["hub.rpy", 20], "location": "hub", "chosen_index": 0},
        ]
        node = {"ast_key": ("hub.rpy", 20), "_location": "hub"}
        assert _tl_shadow_match(path, node) == 0

    def test_site_key_match_works_without_location(self):
        path = [{"menu_site_key": ["hub.rpy", 20], "chosen_index": 0}]
        node = {"ast_key": ("hub.rpy", 20)}
        assert _tl_shadow_match(path, node) == 0


class TestConsumeShadowPath:
    def _sp(self, *pairs):
        return [{"location": loc, "chosen_index": ci} for loc, ci in pairs]

    def test_no_match_returns_original(self):
        sp = self._sp(("locA", 1), ("locB", 0))
        new_sp, div = _tl_consume_shadow_path(sp, {"_location": "locX"}, 0)
        assert new_sp is sp
        assert div is None

    def test_match_first_entry_consumed(self):
        sp = self._sp(("locA", 1), ("locB", 0))
        new_sp, div = _tl_consume_shadow_path(sp, {"_location": "locA"}, 0)
        assert new_sp == [{"location": "locB", "chosen_index": 0}]

    def test_match_middle_entry_discards_preceding(self):
        sp = self._sp(("locA", 1), ("locB", 0), ("locC", 1))
        new_sp, div = _tl_consume_shadow_path(sp, {"_location": "locB"}, 0)
        assert new_sp == [{"location": "locC", "chosen_index": 1}]

    def test_match_last_entry_returns_none(self):
        sp = self._sp(("locA", 1))
        new_sp, div = _tl_consume_shadow_path(sp, {"_location": "locA"}, 0)
        assert new_sp is None

    def test_same_choice_div_is_none(self):
        sp = self._sp(("locA", 1))
        new_sp, div = _tl_consume_shadow_path(sp, {"_location": "locA"}, 1)
        assert div is None

    def test_different_choice_div_is_orig(self):
        sp = self._sp(("locA", 1))
        new_sp, div = _tl_consume_shadow_path(sp, {"_location": "locA"}, 0)
        assert div == 1

    def test_chosen_index_zero_same_no_div(self):
        sp = self._sp(("locA", 0))
        new_sp, div = _tl_consume_shadow_path(sp, {"_location": "locA"}, 0)
        assert div is None

    def test_empty_path_returns_unchanged(self):
        new_sp, div = _tl_consume_shadow_path([], {"_location": "locA"}, 0)
        assert new_sp == []
        assert div is None

    def test_none_path_returns_unchanged(self):
        new_sp, div = _tl_consume_shadow_path(None, {"_location": "locA"}, 0)
        assert new_sp is None
        assert div is None

    def test_tail_preserved_in_order(self):
        sp = self._sp(("locA", 0), ("locB", 1), ("locC", 0))
        new_sp, _ = _tl_consume_shadow_path(sp, {"_location": "locA"}, 0)
        assert [e["location"] for e in new_sp] == ["locB", "locC"]

    def test_menu_site_key_beats_shared_location(self):
        sp = [
            {"menu_site_key": ["hub.rpy", 10], "location": "hub", "chosen_index": 1},
            {"menu_site_key": ["hub.rpy", 20], "location": "hub", "chosen_index": 0},
            {"menu_site_key": ["hub.rpy", 30], "location": "next", "chosen_index": 1},
        ]
        node = {"ast_key": ("hub.rpy", 20), "_location": "hub"}
        new_sp, div = _tl_consume_shadow_path(sp, node, 0)
        assert new_sp == [{"menu_site_key": ["hub.rpy", 30], "location": "next", "chosen_index": 1}]
        assert div is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])