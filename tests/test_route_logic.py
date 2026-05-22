"""
test_route_logic.py — Unit tests for backend/tl_route_logic.rpy.

Functions covered:
  _tl_format_numeric_change
  _tl_diff_route_vars
  _tl_flush_menu_snap
  _tl_var_consumed
  _tl_build_route_chips
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns as ns

_format_change   = ns["_tl_format_numeric_change"]
_diff_route_vars = ns["_tl_diff_route_vars"]
_flush_menu_snap = ns["_tl_flush_menu_snap"]
_var_consumed    = ns["_tl_var_consumed"]
_build_chips     = ns["_tl_build_route_chips"]


# =============================================================================
# _tl_format_numeric_change
# =============================================================================

class TestFormatNumericChange:
    def test_increase_by_one_no_magnitude(self):
        assert _format_change("Affection", 0, 1) == "{font=DejaVuSans.ttf}↑{/font} Affection"

    def test_increase_by_three_shows_magnitude(self):
        result = _format_change("Affection", 0, 3)
        assert "{font=DejaVuSans.ttf}↑{/font}3 Affection" == result

    def test_decrease_by_one_no_magnitude(self):
        assert _format_change("Trust", 5, 4) == "{font=DejaVuSans.ttf}↓{/font} Trust"

    def test_decrease_by_two_shows_magnitude(self):
        result = _format_change("Trust", 10, 8)
        assert "{font=DejaVuSans.ttf}↓{/font}2 Trust" == result

    def test_integer_delta_no_decimal(self):
        ## delta of 3 should show as "3" not "3.0"
        result = _format_change("Score", 0, 3)
        assert "3.0" not in result
        assert "3 " in result

    def test_fractional_delta_preserved(self):
        result = _format_change("Score", 0, 2.5)
        assert "2.5" in result


# =============================================================================
# _tl_diff_route_vars
# =============================================================================

class TestDiffRouteVars:
    def setup_method(self):
        self._saved_pending = getattr(ns["store"], "_tl_pending_var_changes", {})
        self._saved_rcv     = getattr(ns["store"], "_tl_recently_changed_vars", set())
        ns["store"]._tl_pending_var_changes = {}
        ns["store"]._tl_recently_changed_vars = set()
        self._saved_route_names = ns["persistent"]._tl_route_var_names
        ns["persistent"]._tl_route_var_names = ["affection", "route_id", "trust"]

    def teardown_method(self):
        ns["store"]._tl_pending_var_changes = self._saved_pending
        ns["store"]._tl_recently_changed_vars = self._saved_rcv
        ns["persistent"]._tl_route_var_names = self._saved_route_names
        for v in ("affection", "route_id", "trust"):
            if hasattr(ns["store"], v):
                delattr(ns["store"], v)

    def _set_var(self, name, value):
        setattr(ns["store"], name, value)

    def test_unchanged_var_not_in_pending(self):
        self._set_var("affection", 3)
        snap = {"affection": 3}
        _diff_route_vars(snap)
        assert "affection" not in ns["store"]._tl_pending_var_changes

    def test_changed_var_added_to_pending(self):
        self._set_var("affection", 5)
        snap = {"affection": 3}
        _diff_route_vars(snap)
        assert "affection" in ns["store"]._tl_pending_var_changes
        assert ns["store"]._tl_pending_var_changes["affection"] == (3, 5)

    def test_changed_var_already_pending_keeps_original_old(self):
        self._set_var("affection", 7)
        ns["store"]._tl_pending_var_changes = {"affection": (1, 5)}
        snap = {"affection": 5}
        _diff_route_vars(snap)
        old, new = ns["store"]._tl_pending_var_changes["affection"]
        assert old == 1   ## original old preserved
        assert new == 7   ## new value updated

    def test_none_in_snap_init_skipped(self):
        self._set_var("route_id", "romance")
        snap = {"route_id": None}
        _diff_route_vars(snap)
        assert "route_id" not in ns["store"]._tl_pending_var_changes

    def test_changed_var_added_to_recently_changed(self):
        self._set_var("trust", 2)
        snap = {"trust": 0}
        _diff_route_vars(snap)
        assert "trust" in ns["store"]._tl_recently_changed_vars

    def test_unchanged_var_not_in_recently_changed(self):
        self._set_var("affection", 3)
        snap = {"affection": 3}
        _diff_route_vars(snap)
        assert "affection" not in ns["store"]._tl_recently_changed_vars


# =============================================================================
# _tl_flush_menu_snap
# =============================================================================

class TestFlushMenuSnap:
    def setup_method(self):
        self._saved_snap    = getattr(ns["store"], "_tl_menu_var_snap", None)
        self._saved_rcv     = getattr(ns["store"], "_tl_recently_changed_vars", set())
        self._notify_calls  = []
        self._saved_show    = ns["renpy"].show_screen
        ns["renpy"].show_screen = lambda name, **kw: self._notify_calls.append(kw.get("message", ""))
        ns["store"]._tl_recently_changed_vars = set()
        self._saved_numeric = ns["persistent"]._tl_var_is_numeric
        ns["persistent"]._tl_var_is_numeric = set()

    def teardown_method(self):
        ns["store"]._tl_menu_var_snap = self._saved_snap
        ns["store"]._tl_recently_changed_vars = self._saved_rcv
        ns["renpy"].show_screen = self._saved_show
        ns["persistent"]._tl_var_is_numeric = self._saved_numeric
        for v in ("new_var", "route_id"):
            if hasattr(ns["store"], v):
                delattr(ns["store"], v)

    def test_no_snap_is_noop(self):
        ns["store"]._tl_menu_var_snap = None
        _flush_menu_snap()
        assert self._notify_calls == []

    def test_init_var_none_in_snap_now_assigned_emits_notification(self):
        setattr(ns["store"], "route_id", "romance")
        ns["store"]._tl_menu_var_snap = {"route_id": None}
        _flush_menu_snap()
        assert len(self._notify_calls) == 1
        assert "Route Id" in self._notify_calls[0] or "route_id" in self._notify_calls[0].lower()

    def test_non_init_var_skipped(self):
        ## old was non-None → already handled by Python.execute patch, skip here
        setattr(ns["store"], "route_id", "romance")
        ns["store"]._tl_menu_var_snap = {"route_id": "neutral"}
        _flush_menu_snap()
        assert self._notify_calls == []

    def test_init_var_adds_to_recently_changed(self):
        setattr(ns["store"], "new_var", 1)
        ns["store"]._tl_menu_var_snap = {"new_var": None}
        _flush_menu_snap()
        assert "new_var" in ns["store"]._tl_recently_changed_vars

    def test_numeric_var_uses_arrow_format(self):
        ns["persistent"]._tl_var_is_numeric = {"affection"}
        setattr(ns["store"], "affection", 3)
        ns["store"]._tl_menu_var_snap = {"affection": None}
        _flush_menu_snap()
        assert len(self._notify_calls) == 1
        assert "↑" in self._notify_calls[0]

    def test_snap_cleared_after_flush(self):
        setattr(ns["store"], "route_id", "romance")
        ns["store"]._tl_menu_var_snap = {"route_id": None}
        _flush_menu_snap()
        assert ns["store"]._tl_menu_var_snap is None


# =============================================================================
# _tl_var_consumed
# =============================================================================

class TestVarConsumed:
    def setup_method(self):
        self._saved_if_count    = ns["persistent"]._tl_var_if_count
        self._saved_seen_keys   = getattr(ns["store"], "_tl_var_if_seen_keys", {})
        ns["persistent"]._tl_var_if_count = {}
        ns["store"]._tl_var_if_seen_keys  = {}

    def teardown_method(self):
        ns["persistent"]._tl_var_if_count  = self._saved_if_count
        ns["store"]._tl_var_if_seen_keys    = self._saved_seen_keys

    def test_if_count_zero_returns_false(self):
        assert _var_consumed("unknown_var") is False

    def test_seen_count_below_total_returns_false(self):
        ns["persistent"]._tl_var_if_count = {"route_id": 3}
        ns["store"]._tl_var_if_seen_keys  = {"route_id": {("f.rpy", 1), ("f.rpy", 2)}}
        assert _var_consumed("route_id") is False

    def test_seen_count_equals_total_returns_true(self):
        ns["persistent"]._tl_var_if_count = {"route_id": 2}
        ns["store"]._tl_var_if_seen_keys  = {"route_id": {("f.rpy", 1), ("f.rpy", 2)}}
        assert _var_consumed("route_id") is True

    def test_seen_count_exceeds_total_returns_true(self):
        ns["persistent"]._tl_var_if_count = {"route_id": 1}
        ns["store"]._tl_var_if_seen_keys  = {"route_id": {("f.rpy", 1), ("f.rpy", 2)}}
        assert _var_consumed("route_id") is True

    def test_var_not_in_if_count_returns_false(self):
        ns["persistent"]._tl_var_if_count = {"other_var": 2}
        assert _var_consumed("route_id") is False


# =============================================================================
# _tl_build_route_chips
# =============================================================================

class TestBuildRouteChips:
    def setup_method(self):
        self._saved_names     = ns["persistent"]._tl_route_var_names
        self._saved_if_count  = ns["persistent"]._tl_var_if_count
        self._saved_seen_keys = getattr(ns["store"], "_tl_var_if_seen_keys", {})
        self._saved_ghost     = getattr(ns["store"], "_tl_ghost_nodes", [])
        self._saved_rcv       = getattr(ns["store"], "_tl_recently_changed_vars", set())
        ns["persistent"]._tl_route_var_names = []
        ns["persistent"]._tl_var_if_count    = {}
        ns["store"]._tl_var_if_seen_keys      = {}
        ns["store"]._tl_ghost_nodes           = []
        ns["store"]._tl_recently_changed_vars = set()

    def teardown_method(self):
        ns["persistent"]._tl_route_var_names = self._saved_names
        ns["persistent"]._tl_var_if_count    = self._saved_if_count
        ns["store"]._tl_var_if_seen_keys      = self._saved_seen_keys
        ns["store"]._tl_ghost_nodes           = self._saved_ghost
        ns["store"]._tl_recently_changed_vars = self._saved_rcv
        for v in ("myvar", "route_id", "affection", "trust", "perk"):
            if hasattr(ns["store"], v):
                delattr(ns["store"], v)

    def _setup(self, var, value, if_count=1, seen_keys=None):
        """Register a var with given store value and if_count."""
        names = list(ns["persistent"]._tl_route_var_names)
        if var not in names:
            names.append(var)
        ns["persistent"]._tl_route_var_names = names
        ns["persistent"]._tl_var_if_count[var] = if_count
        setattr(ns["store"], var, value)
        if seen_keys is not None:
            ns["store"]._tl_var_if_seen_keys[var] = seen_keys

    def test_var_with_if_count_zero_excluded(self):
        ns["persistent"]._tl_route_var_names = ["myvar"]
        ns["persistent"]._tl_var_if_count = {}   ## not present → 0
        setattr(ns["store"], "myvar", "hello")
        chips = _build_chips()
        assert not any(c[0] == "myvar" for c in chips)

    def test_var_with_none_value_excluded(self):
        ns["persistent"]._tl_route_var_names = ["myvar"]
        ns["persistent"]._tl_var_if_count = {"myvar": 2}
        if hasattr(ns["store"], "myvar"):
            delattr(ns["store"], "myvar")
        chips = _build_chips()
        assert not any(c[0] == "myvar" for c in chips)

    def test_var_with_list_value_excluded(self):
        self._setup("myvar", [1, 2, 3], if_count=2)
        chips = _build_chips()
        assert not any(c[0] == "myvar" for c in chips)

    def test_consumed_low_count_var_excluded(self):
        ## Consumed + if_count <= 5 → hidden
        self._setup("route_id", "romance", if_count=2,
                    seen_keys={("f.rpy", 1), ("f.rpy", 2)})
        chips = _build_chips()
        assert not any(c[0] == "route_id" for c in chips)

    def test_consumed_high_count_var_shown(self):
        ## Consumed + if_count > 5 → always shown (globally important)
        self._setup("perk", "combat", if_count=6,
                    seen_keys={("f.rpy", i) for i in range(6)})
        chips = _build_chips()
        assert any(c[0] == "perk" for c in chips)

    def test_unconsumed_var_shown(self):
        self._setup("affection", 4, if_count=3, seen_keys={("f.rpy", 1)})  ## only 1 of 3 seen
        chips = _build_chips()
        assert any(c[0] == "affection" for c in chips)

    def test_ghost_var_shown_even_if_consumed(self):
        self._setup("trust", "high", if_count=1,
                    seen_keys={("f.rpy", 1)})  ## consumed
        ns["store"]._tl_ghost_nodes = [{"affecting_vars": ["trust"]}]
        chips = _build_chips()
        assert any(c[0] == "trust" for c in chips)

    def test_recently_changed_var_shown_even_if_consumed(self):
        self._setup("affection", 3, if_count=1,
                    seen_keys={("f.rpy", 1)})  ## consumed
        ns["store"]._tl_recently_changed_vars = {"affection"}
        chips = _build_chips()
        assert any(c[0] == "affection" for c in chips)

    def test_ghost_vars_ordered_before_non_ghost(self):
        self._setup("trust", "high", if_count=3)
        self._setup("route_id", "romance", if_count=5)
        ns["store"]._tl_ghost_nodes = [{"affecting_vars": ["trust"]}]
        chips = _build_chips()
        names = [c[0] for c in chips]
        assert names.index("trust") < names.index("route_id")

    def test_within_group_ordered_by_if_count_desc(self):
        self._setup("affection", 3, if_count=2)
        self._setup("route_id", "romance", if_count=8)
        chips = _build_chips()
        names = [c[0] for c in chips]
        assert names.index("route_id") < names.index("affection")

    def test_chip_value_matches_store(self):
        self._setup("affection", 42, if_count=2)
        chips = _build_chips()
        match = next((c for c in chips if c[0] == "affection"), None)
        assert match is not None
        assert match[1] == 42