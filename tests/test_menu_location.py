"""
Tests for tl_menu_location.rpy — menu site key derivation.
Run: pytest tests/test_menu_location.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns

_normalize        = _rpy_ns["_tl_normalize_script_path"]
_menu_site_key    = _rpy_ns["_tl_menu_site_key"]
_location_ast_key = _rpy_ns["_tl_location_menu_ast_key"]
_location_site    = _rpy_ns["_tl_location_menu_site_key"]
_node_site        = _rpy_ns["_tl_node_menu_site_key"]


# ---------------------------------------------------------------------------
# _tl_normalize_script_path
# ---------------------------------------------------------------------------

class TestNormalizeScriptPath:
    def test_already_prefixed_unchanged(self):
        assert _normalize("game/script/intro.rpy") == "game/script/intro.rpy"

    def test_no_prefix_with_slash_gets_prefix(self):
        assert _normalize("script/intro.rpy") == "game/script/intro.rpy"

    def test_rpyc_suffix_stripped(self):
        assert _normalize("game/script/intro.rpyc") == "game/script/intro.rpy"

    def test_both_prefix_and_rpyc(self):
        assert _normalize("script/intro.rpyc") == "game/script/intro.rpy"

    def test_bare_filename_no_slash_unchanged(self):
        # No '/' in path → prefix not added
        assert _normalize("intro.rpy") == "intro.rpy"

    def test_non_string_returned_as_is(self):
        assert _normalize(None) is None
        assert _normalize(42) == 42


# ---------------------------------------------------------------------------
# _tl_menu_site_key
# ---------------------------------------------------------------------------

class TestMenuSiteKey:
    def test_returns_normalized_tuple(self):
        result = _menu_site_key("script/intro.rpy", 42)
        assert result == ("game/script/intro.rpy", 42)

    def test_already_prefixed_path(self):
        result = _menu_site_key("game/script/intro.rpy", 10)
        assert result == ("game/script/intro.rpy", 10)

    def test_missing_file_path_returns_none(self):
        assert _menu_site_key(None, 10) is None
        assert _menu_site_key("", 10) is None

    def test_missing_line_no_returns_none(self):
        assert _menu_site_key("game/intro.rpy", None) is None
        assert _menu_site_key("game/intro.rpy", 0) is None


# ---------------------------------------------------------------------------
# _tl_location_menu_ast_key
# ---------------------------------------------------------------------------

class TestLocationMenuAstKey:
    def test_non_tuple_returns_none(self):
        assert _location_ast_key("not_a_tuple") is None
        assert _location_ast_key(None) is None

    def test_namemap_miss_returns_none(self):
        # Stub namemap is empty — any location returns None
        assert _location_ast_key(("game/intro.rpy", "label", 10)) is None


# ---------------------------------------------------------------------------
# _tl_location_menu_site_key
# ---------------------------------------------------------------------------

class TestLocationMenuSiteKey:
    def test_falls_back_to_location_file_line(self):
        # Namemap is empty → ast_key lookup returns None → falls back to location[0,2]
        loc = ("script/intro.rpy", "label", 15)
        result = _location_site(loc)
        assert result == ("game/script/intro.rpy", 15)

    def test_short_location_tuple_returns_none(self):
        assert _location_site(("only_one",)) is None

    def test_non_tuple_returns_none(self):
        assert _location_site(None) is None


# ---------------------------------------------------------------------------
# _tl_node_menu_site_key
# ---------------------------------------------------------------------------

class TestNodeMenuSiteKey:
    def test_uses_ast_key(self):
        node = {"ast_key": ("b.rpy", 20), "_location": ("c.rpy", "lbl", 30)}
        assert _node_site(node) == ("b.rpy", 20)

    def test_falls_back_to_location(self):
        node = {"_location": ("c.rpy", "lbl", 30)}
        assert _node_site(node) == ("c.rpy", 30)

    def test_non_dict_returns_none(self):
        assert _node_site(None) is None
        assert _node_site("string") is None

    def test_no_ast_key_no_location_returns_none(self):
        assert _node_site({}) is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])