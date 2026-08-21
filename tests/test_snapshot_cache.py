"""
Tests for tl_snapshot_cache_ren.py — TLSnapshotCache class.
Run: pytest tests/test_snapshot_cache.py -v

Only the engine-independent parts of the class (construction, the
value-freeze/reuse decision) are covered here. capture()/unfreeze() need a
real renpy.game.log / renpy.rollback environment and are covered by the
in-game suite (timeline_tests_ren.py) instead.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns

_tl_make_cache  = _rpy_ns["_tl_make_cache"]
TLSnapshotCache = _rpy_ns["TLSnapshotCache"]
_TL_PLAIN_DICT  = _rpy_ns["_TL_PLAIN_DICT"]


class TestMakeCache:
    def test_returns_snapshot_cache_instance(self):
        assert isinstance(_tl_make_cache(), TLSnapshotCache)

    def test_menu_and_chapter_are_plain_dict_not_revertable(self):
        cache = _tl_make_cache()
        assert type(cache.menu) is _TL_PLAIN_DICT
        assert type(cache.chapter) is _TL_PLAIN_DICT

    def test_menu_and_chapter_start_empty(self):
        cache = _tl_make_cache()
        assert cache.menu == {}
        assert cache.chapter == {}

    def test_last_roots_starts_none(self):
        assert _tl_make_cache()._last_roots is None


class TestFreezeRoots:
    """
    _freeze_roots is the core of the reference-sharing design: for each key
    it decides whether to reuse the previously frozen reference (unchanged
    value) or make a fresh deep copy (changed or new value). Exercised
    directly with plain dicts as stand-ins for get_roots()'s output — no
    live Ren'Py store needed.
    """

    def test_immutable_values_are_shared_by_reference(self):
        cache = _tl_make_cache()
        live = {"a": "hello", "b": 42, "c": None}
        frozen = cache._freeze_roots(live)
        assert frozen["a"] is live["a"]
        assert frozen["b"] is live["b"]
        assert frozen["c"] is live["c"]

    def test_unchanged_mutable_value_reuses_prior_frozen_copy(self):
        cache = _tl_make_cache()
        first_live = {"char": {"name": "Alice", "hp": 10}}
        first_frozen = cache._freeze_roots(first_live)
        cache._last_roots = first_frozen

        # A distinct live object (different id) with equal content — this is
        # what a stable define-time object looks like across two captures,
        # but the dedup must hold on content equality alone, not identity.
        second_live = {"char": {"name": "Alice", "hp": 10}}
        second_frozen = cache._freeze_roots(second_live)

        assert second_frozen["char"] is first_frozen["char"]
        assert second_frozen["char"] is not second_live["char"]

    def test_changed_mutable_value_gets_its_own_frozen_copy(self):
        cache = _tl_make_cache()
        first_live = {"char": {"name": "Alice", "hp": 10}}
        first_frozen = cache._freeze_roots(first_live)
        cache._last_roots = first_frozen

        second_live = {"char": {"name": "Alice", "hp": 5}}  # hp changed
        second_frozen = cache._freeze_roots(second_live)

        assert second_frozen["char"] is not first_frozen["char"]
        assert second_frozen["char"] == {"name": "Alice", "hp": 5}

    def test_frozen_copy_never_aliases_the_live_object(self):
        cache = _tl_make_cache()
        live_char = {"a": 1}
        frozen = cache._freeze_roots({"char": live_char})
        assert frozen["char"] is not live_char
        live_char["a"] = 999  # simulate later gameplay mutating the live store
        assert frozen["char"]["a"] == 1

    def test_new_key_not_in_prior_snapshot_gets_frozen(self):
        cache = _tl_make_cache()
        cache._last_roots = {"a": {"x": 1}}
        live = {"a": {"x": 1}, "b": {"y": 2}}
        frozen = cache._freeze_roots(live)
        assert frozen["b"] is not live["b"]
        assert frozen["b"] == {"y": 2}

    def test_first_ever_capture_has_no_prior_snapshot(self):
        cache = _tl_make_cache()
        assert cache._last_roots is None
        frozen = cache._freeze_roots({"char": {"name": "Alice"}})
        assert frozen["char"] == {"name": "Alice"}