"""
Tests for tl_assets.rpy — node thumb, asset thumb display cache key.
Run: pytest tests/test_assets.py -v
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns, _tl_node_thumb

_tl_asset_thumb_display_cache_key = _rpy_ns["_tl_asset_thumb_display_cache_key"]

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
