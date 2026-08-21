"""
Tests for tl_shadow_path_ren.py — shadow-path match and consume.

v1 tests (TestBuildShadowPath, TestStageShadowPath, TestConsumeShadowPath) are
skipped because the functions they test were removed or changed in v2.
v2 tests (TestConsumeShadowPathV2) cover the new 3-tuple / ast_key API.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns

_tl_shadow_match        = _rpy_ns["_tl_shadow_match"]
_tl_consume_shadow_path = _rpy_ns["_tl_consume_shadow_path"]


def _make_node(index, location, chosen_index):
    return {"index": index, "_location": location, "chosen_index": chosen_index,
            "options": ["a", "b"]}


class TestShadowMatch:
    def test_match_at_index_0(self):
        path = [{"ast_key": ("a.rpy", 10), "chosen_index": 1}]
        assert _tl_shadow_match(path, {"ast_key": ("a.rpy", 10)}) == 1

    def test_match_at_index_gt_0(self):
        path = [{"ast_key": ("a.rpy", 10), "chosen_index": 0},
                {"ast_key": ("a.rpy", 20), "chosen_index": 2}]
        assert _tl_shadow_match(path, {"ast_key": ("a.rpy", 20)}) == 2

    def test_no_match_returns_none(self):
        path = [{"ast_key": ("a.rpy", 10), "chosen_index": 1}]
        assert _tl_shadow_match(path, {"ast_key": ("a.rpy", 99)}) is None

    def test_empty_path_returns_none(self):
        assert _tl_shadow_match([], {"ast_key": ("a.rpy", 10)}) is None

    def test_first_match_wins_on_duplicate_key(self):
        path = [{"ast_key": ("a.rpy", 10), "chosen_index": 1},
                {"ast_key": ("a.rpy", 10), "chosen_index": 2}]
        assert _tl_shadow_match(path, {"ast_key": ("a.rpy", 10)}) == 1

    def test_chosen_index_zero_is_valid(self):
        path = [{"ast_key": ("a.rpy", 10), "chosen_index": 0}]
        assert _tl_shadow_match(path, {"ast_key": ("a.rpy", 10)}) == 0

    def test_bw_compat_menu_site_key_list_matches_ast_key_node(self):
        path = [
            {"menu_site_key": ["hub.rpy", 10], "chosen_index": 1},
            {"menu_site_key": ["hub.rpy", 20], "chosen_index": 0},
        ]
        node = {"ast_key": ("hub.rpy", 20)}
        assert _tl_shadow_match(path, node) == 0

    def test_bw_compat_menu_site_key_tuple_matches_ast_key_node(self):
        path = [{"menu_site_key": ("hub.rpy", 20), "chosen_index": 0}]
        node = {"ast_key": ("hub.rpy", 20)}
        assert _tl_shadow_match(path, node) == 0


class TestConsumeShadowPathV2:
    """v2 API: 3-tuple (new_sp, diverged_ci, match_mode), ast_key matching."""

    def _sp(self, *ast_keys):
        """Build shadow path entries; each arg is a full ast_key tuple, chosen_index defaults to 0."""
        return [{"ast_key": ak, "chosen_index": 0} for ak in ast_keys]

    def _node(self, ast_key):
        return {"ast_key": ast_key, "options": ["a", "b"]}

    def test_no_match_returns_original(self):
        sp = self._sp(("a.rpy", 10), ("b.rpy", 20))
        node = self._node(("c.rpy", 30))
        new_sp, div, mode = _tl_consume_shadow_path(sp, node, 0)
        assert new_sp is sp
        assert div is None
        assert mode is None

    def test_match_first_entry_tail_returned(self):
        sp = self._sp(("a.rpy", 10), ("b.rpy", 20))
        node = self._node(("a.rpy", 10))
        new_sp, _, _ = _tl_consume_shadow_path(sp, node, 0)
        assert new_sp == [{"ast_key": ("b.rpy", 20), "chosen_index": sp[1]["chosen_index"]}]

    def test_match_last_entry_returns_none(self):
        sp = self._sp(("a.rpy", 10),)
        node = self._node(("a.rpy", 10))
        new_sp, _, _ = _tl_consume_shadow_path(sp, node, 0)
        assert new_sp is None

    def test_same_choice_div_is_none(self):
        sp = self._sp(("a.rpy", 10),)
        sp[0]["chosen_index"] = 1
        node = self._node(("a.rpy", 10))
        _, div, _ = _tl_consume_shadow_path(sp, node, 1)
        assert div is None

    def test_different_choice_div_is_orig(self):
        sp = self._sp(("a.rpy", 10),)
        sp[0]["chosen_index"] = 1
        node = self._node(("a.rpy", 10))
        _, div, _ = _tl_consume_shadow_path(sp, node, 0)
        assert div == 1

    def test_match_mode_is_ast_key(self):
        sp = self._sp(("a.rpy", 10),)
        node = self._node(("a.rpy", 10))
        _, _, mode = _tl_consume_shadow_path(sp, node, 0)
        assert mode == "ast_key"

    def test_no_match_mode_is_none(self):
        sp = self._sp(("a.rpy", 10),)
        node = self._node(("z.rpy", 99))
        _, _, mode = _tl_consume_shadow_path(sp, node, 0)
        assert mode is None

    def test_tail_preserved_in_order(self):
        sp = self._sp(("a.rpy", 10), ("b.rpy", 20), ("c.rpy", 30))
        node = self._node(("a.rpy", 10))
        new_sp, _, _ = _tl_consume_shadow_path(sp, node, 0)
        assert [e["ast_key"] for e in new_sp] == [("b.rpy", 20), ("c.rpy", 30)]

    def test_empty_path_returns_unchanged(self):
        new_sp, div, mode = _tl_consume_shadow_path([], {"ast_key": ("a.rpy", 1)}, 0)
        assert new_sp == []
        assert div is None
        assert mode is None

    def test_none_path_returns_unchanged(self):
        new_sp, div, mode = _tl_consume_shadow_path(None, {"ast_key": ("a.rpy", 1)}, 0)
        assert new_sp is None
        assert div is None
        assert mode is None

    def test_bw_compat_menu_site_key_list_matches_ast_key_node(self):
        """Old entries with menu_site_key as list still match ast_key node."""
        sp = [{"menu_site_key": ["hub.rpy", 10], "chosen_index": 1}]
        node = {"ast_key": ("hub.rpy", 10), "options": ["a", "b"]}
        new_sp, div, mode = _tl_consume_shadow_path(sp, node, 0)
        assert new_sp is None   # consumed
        assert div == 1
        assert mode == "ast_key"

    def test_bw_compat_menu_site_key_tuple_matches_ast_key_node(self):
        sp = [{"menu_site_key": ("hub.rpy", 10), "chosen_index": 0}]
        node = {"ast_key": ("hub.rpy", 10), "options": ["a", "b"]}
        new_sp, div, mode = _tl_consume_shadow_path(sp, node, 0)
        assert new_sp is None
        assert div is None   # same choice
        assert mode == "ast_key"

    def test_chosen_index_zero_same_no_div(self):
        sp = [{"ast_key": ("a.rpy", 1), "chosen_index": 0}]
        node = self._node(("a.rpy", 1))
        _, div, _ = _tl_consume_shadow_path(sp, node, 0)
        assert div is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])