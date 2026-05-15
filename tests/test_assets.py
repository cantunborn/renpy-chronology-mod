"""
Tests for tl_assets.rpy — node thumb, asset thumb display cache key, asset file resolution.
Run: pytest tests/test_assets.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns, _tl_node_thumb

_tl_asset_thumb_display_cache_key = _rpy_ns["_tl_asset_thumb_display_cache_key"]
_tl_resolve_asset_file            = _rpy_ns["_tl_resolve_asset_file"]
_tl_asset_thumb_file_cache        = _rpy_ns["_tl_asset_thumb_file_cache"]

class TestNodeThumb:
    def test_returns_thumb_bytes_when_present(self):
        node = {"thumb_bytes": b"img", "ast_key": ("f.rpy", 1)}
        assert _tl_node_thumb(node, {}) == b"img"

    def test_falls_back_to_persistent_when_none(self):
        node = {"thumb_bytes": None, "ast_key": ("f.rpy", 1)}
        cache = {str(("f.rpy", 1)): b"cached"}
        assert _tl_node_thumb(node, cache) == b"cached"

    def test_returns_none_when_no_key_and_no_bytes(self):
        node = {"thumb_bytes": None, "ast_key": None}
        assert _tl_node_thumb(node, {}) is None

    def test_bytes_takes_priority_over_cache(self):
        node = {"thumb_bytes": b"direct", "ast_key": ("f.rpy", 1)}
        cache = {str(("f.rpy", 1)): b"cached"}
        assert _tl_node_thumb(node, cache) == b"direct"

    def test_cache_miss_with_key_returns_none(self):
        node = {"thumb_bytes": None, "ast_key": ("f.rpy", 1)}
        assert _tl_node_thumb(node, {}) is None


class TestAssetThumbDisplayCacheKey:
    def test_includes_render_dimensions(self):
        assert _tl_asset_thumb_display_cache_key("bg room", 400, 225, "contain") == (
            "bg room", 400, 225, "contain"
        )

    def test_defaults_dimensions(self):
        assert _tl_asset_thumb_display_cache_key("bg room") == (
            "bg room", 320, 180, "cover"
        )


import renpy as _renpy


def _make_atl_displayable(expressions):
    """Build a minimal ATLTransform stub with the given (expr_str, with_clause) expressions."""
    class _Stmt:
        def __init__(self, exprs):
            self.expressions = exprs
            self.filename = None

    class _RawBlock:
        def __init__(self, stmts):
            self.statements = stmts

    class _ATLTransform:
        def __init__(self, exprs):
            self.atl = _RawBlock([_Stmt(exprs)])

    return _ATLTransform(expressions)


class TestResolveAssetFileATL:
    def setup_method(self):
        _tl_asset_thumb_file_cache.clear()
        _renpy.display.image.images.clear()
        _renpy.loadable = lambda f: False

    def teardown_method(self):
        _renpy.loadable = lambda f: False
        _renpy.display.image.images.clear()
        _tl_asset_thumb_file_cache.clear()

    def test_atl_single_frame_resolves_first_image(self):
        path = "images/chapter1/scene.jpg"
        _renpy.display.image.images[("scene_atl",)] = _make_atl_displayable(
            [(repr(path), None)]
        )
        _renpy.loadable = lambda f: f == path
        assert _tl_resolve_asset_file("scene_atl") == path

    def test_atl_multi_frame_resolves_first_image(self):
        path_a = "images/chapter1/frame_a.jpg"
        path_b = "images/chapter1/frame_b.jpg"
        _renpy.display.image.images[("scene_multi",)] = _make_atl_displayable(
            [(repr(path_a), None), (repr(path_b), "dissolve")]
        )
        _renpy.loadable = lambda f: f in (path_a, path_b)
        assert _tl_resolve_asset_file("scene_multi") == path_a

    def test_atl_skips_non_loadable_expression(self):
        _renpy.display.image.images[("scene_skip",)] = _make_atl_displayable(
            [("'not_a_real_file.jpg'", None)]
        )
        _renpy.loadable = lambda f: False
        assert _tl_resolve_asset_file("scene_skip") is None

    def test_atl_result_is_cached(self):
        path = "images/chapter1/cached.jpg"
        _renpy.display.image.images[("scene_cached",)] = _make_atl_displayable(
            [(repr(path), None)]
        )
        _renpy.loadable = lambda f: f == path
        _tl_resolve_asset_file("scene_cached")
        _renpy.display.image.images.clear()   ## image gone — must hit cache
        assert _tl_resolve_asset_file("scene_cached") == path

    def test_plain_image_still_resolves(self):
        """Non-ATL path (filename attr) still works after ATL addition."""
        class _PlainImg:
            filename = "images/plain.jpg"
        _renpy.display.image.images[("plain",)] = _PlainImg()
        _renpy.loadable = lambda f: f == "images/plain.jpg"
        assert _tl_resolve_asset_file("plain") == "images/plain.jpg"


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
