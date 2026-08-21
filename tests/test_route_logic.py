"""
test_route_logic.py — Unit tests for backend/tl_route_logic_ren.py.

Functions covered:
  _tl_format_numeric_change
  _tl_flush_var_changes
  _tl_flush_menu_snap
  _tl_var_consumed
  _tl_build_route_chips
  _tl_python_execute_patched
  _tl_walk_ast_blocks  [Phase 0B — initially fails until tl_ast_utils.rpy created]
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns as ns, If, Label, Say, Return, Menu

_format_change    = ns["_tl_format_numeric_change"]
_flush_var_changes = ns["_tl_flush_var_changes"]
_flush_menu_snap  = ns["_tl_flush_menu_snap"]
_var_consumed     = ns["_tl_var_consumed"]
_build_chips      = ns["_tl_build_route_chips"]
## Phase 0B: None until backend/tl_ast_utils.rpy is created
_walk_ast_blocks  = ns.get("_tl_walk_ast_blocks")


# =============================================================================
# _tl_format_numeric_change
# =============================================================================

class TestFormatNumericChange:
    def test_increase_by_one_no_magnitude(self):
        assert _format_change("Affection", 0, 1) == "↑ Affection"

    def test_increase_by_three_shows_magnitude(self):
        result = _format_change("Affection", 0, 3)
        assert "↑3 Affection" == result

    def test_decrease_by_one_no_magnitude(self):
        assert _format_change("Trust", 5, 4) == "↓ Trust"

    def test_decrease_by_two_shows_magnitude(self):
        result = _format_change("Trust", 10, 8)
        assert "↓2 Trust" == result

    def test_integer_delta_no_decimal(self):
        ## delta of 3 should show as "3" not "3.0"
        result = _format_change("Score", 0, 3)
        assert "3.0" not in result
        assert "3 " in result

    def test_fractional_delta_preserved(self):
        result = _format_change("Score", 0, 2.5)
        assert "2.5" in result


# =============================================================================
# _tl_flush_var_changes
# =============================================================================

class TestFlushVarChanges:
    def setup_method(self):
        self._saved_pending  = getattr(ns["store"], "_tl_pending_var_changes", {})
        self._saved_numeric  = ns["persistent"]._tl_var_is_numeric
        self._saved_enabled  = getattr(ns["persistent"], "_tl_var_notifs_enabled", False)
        self._notify_calls   = []
        self._saved_show     = ns["renpy"].show_screen
        ns["renpy"].show_screen = lambda name, **kw: self._notify_calls.append(kw.get("message", ""))
        ns["store"]._tl_pending_var_changes = {}
        ns["persistent"]._tl_var_is_numeric = set()
        ns["persistent"]._tl_var_notifs_enabled = True

    def teardown_method(self):
        ns["store"]._tl_pending_var_changes       = self._saved_pending
        ns["persistent"]._tl_var_is_numeric       = self._saved_numeric
        ns["persistent"]._tl_var_notifs_enabled   = self._saved_enabled
        ns["renpy"].show_screen                    = self._saved_show

    def test_no_pending_is_noop(self):
        ns["store"]._tl_pending_var_changes = {}
        _flush_var_changes()
        assert self._notify_calls == []

    def test_shows_screen_when_enabled(self):
        ns["store"]._tl_pending_var_changes = {"affection": (0, 3)}
        _flush_var_changes()
        assert len(self._notify_calls) == 1
        assert "Affection" in self._notify_calls[0]

    def test_no_notification_when_flag_disabled(self):
        ## Regression: flag must be checked inside the function, not only at call sites.
        ## Without this guard, calls from tl_ghost_logic.rpy bypassed the flag entirely.
        ns["persistent"]._tl_var_notifs_enabled = False
        ns["store"]._tl_pending_var_changes = {"affection": (0, 3)}
        _flush_var_changes()
        assert self._notify_calls == []

    def test_clears_pending_when_disabled(self):
        ns["persistent"]._tl_var_notifs_enabled = False
        ns["store"]._tl_pending_var_changes = {"affection": (0, 3)}
        _flush_var_changes()
        assert ns["store"]._tl_pending_var_changes == {}

    def test_clears_pending_after_flush(self):
        ns["store"]._tl_pending_var_changes = {"affection": (0, 3)}
        _flush_var_changes()
        assert ns["store"]._tl_pending_var_changes == {}

    def test_numeric_var_uses_arrow_format(self):
        ns["persistent"]._tl_var_is_numeric = {"affection"}
        ns["store"]._tl_pending_var_changes = {"affection": (0, 3)}
        _flush_var_changes()
        assert len(self._notify_calls) == 1
        assert "↑" in self._notify_calls[0]

    def test_non_numeric_var_uses_arrow_format(self):
        ns["store"]._tl_pending_var_changes = {"route_id": ("neutral", "romance")}
        _flush_var_changes()
        assert len(self._notify_calls) == 1
        assert "→" in self._notify_calls[0]


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
        self._saved_numeric  = ns["persistent"]._tl_var_is_numeric
        self._saved_enabled  = getattr(ns["persistent"], "_tl_var_notifs_enabled", False)
        ns["persistent"]._tl_var_is_numeric = set()
        ns["persistent"]._tl_var_notifs_enabled = True

    def teardown_method(self):
        ns["store"]._tl_menu_var_snap = self._saved_snap
        ns["store"]._tl_recently_changed_vars = self._saved_rcv
        ns["renpy"].show_screen = self._saved_show
        ns["persistent"]._tl_var_is_numeric = self._saved_numeric
        ns["persistent"]._tl_var_notifs_enabled = self._saved_enabled
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

    def test_no_notification_when_flag_disabled(self):
        ## Regression: flag must be checked inside _tl_flush_menu_snap itself.
        ns["persistent"]._tl_var_notifs_enabled = False
        setattr(ns["store"], "route_id", "romance")
        ns["store"]._tl_menu_var_snap = {"route_id": None}
        _flush_menu_snap()
        assert self._notify_calls == []


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
        self._saved_defaults  = ns["persistent"]._tl_var_defaults
        self._saved_seen_keys = getattr(ns["store"], "_tl_var_if_seen_keys", {})
        self._saved_ghost     = getattr(ns["store"], "_tl_ghost_nodes", [])
        self._saved_rcv       = getattr(ns["store"], "_tl_recently_changed_vars", set())
        ns["persistent"]._tl_route_var_names  = []
        ns["persistent"]._tl_var_if_count     = {}
        ns["persistent"]._tl_var_defaults     = {}
        ns["persistent"]._tl_ghost_node_cache = {}
        ns["store"]._tl_var_if_seen_keys      = {}
        ns["store"]._tl_ghost_nodes           = []
        ns["store"]._tl_recently_changed_vars = set()

    def teardown_method(self):
        ns["persistent"]._tl_route_var_names = self._saved_names
        ns["persistent"]._tl_var_if_count    = self._saved_if_count
        ns["persistent"]._tl_var_defaults    = self._saved_defaults
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

    def test_var_with_none_value_excluded(self):
        ns["persistent"]._tl_route_var_names = ["myvar"]
        if hasattr(ns["store"], "myvar"):
            delattr(ns["store"], "myvar")
        chips = _build_chips()
        assert not any(c[0] == "myvar" for c in chips)

    def test_var_with_list_value_excluded(self):
        self._setup("myvar", [1, 2, 3])
        chips = _build_chips()
        assert not any(c[0] == "myvar" for c in chips)

    def test_var_at_default_hidden(self):
        ## Still at declared default → not yet touched by the story
        ns["persistent"]._tl_var_defaults = {"affection": 0}
        self._setup("affection", 0)
        chips = _build_chips()
        assert not any(c[0] == "affection" for c in chips)

    def test_var_changed_from_default_shown(self):
        ## Value differs from default → story has touched it
        ns["persistent"]._tl_var_defaults = {"affection": 0}
        self._setup("affection", 3)
        chips = _build_chips()
        assert any(c[0] == "affection" for c in chips)

    def test_var_no_default_shown_when_assigned(self):
        ## No default declaration → show whenever non-None
        self._setup("route_id", "romance")
        chips = _build_chips()
        assert any(c[0] == "route_id" for c in chips)

    def _ghost_node(self, ast_key, affecting_vars):
        """Populate cache and return slim ghost dict."""
        ns["persistent"]._tl_ghost_node_cache[str(ast_key)] = {
            "conditions": [], "seen_fns": [], "_regions": [],
            "affecting_vars": list(affecting_vars),
        }
        return {"ast_key": ast_key, "taken_index": 0, "branch_imgs": [], "cluster_with_prev": False}

    def test_var_at_default_but_ghost_highlighted_shown(self):
        ## At default value but highlighted as ghost var → still shown
        ns["persistent"]._tl_var_defaults = {"trust": "low"}
        self._setup("trust", "low")
        ns["store"]._tl_ghost_nodes = [self._ghost_node(("f.rpy", 1), ["trust"])]
        chips = _build_chips()
        assert any(c[0] == "trust" for c in chips)

    def test_var_at_default_but_recently_changed_shown(self):
        ## At default value but recently changed → still shown
        ns["persistent"]._tl_var_defaults = {"affection": 0}
        self._setup("affection", 0)
        ns["store"]._tl_recently_changed_vars = {"affection"}
        chips = _build_chips()
        assert any(c[0] == "affection" for c in chips)

    def test_var_with_if_count_zero_still_shown(self):
        ## if_count == 0 no longer hides — var with a value always shows
        ns["persistent"]._tl_route_var_names = ["myvar"]
        ns["persistent"]._tl_var_if_count = {}
        setattr(ns["store"], "myvar", "hello")
        chips = _build_chips()
        assert any(c[0] == "myvar" for c in chips)

    def test_assigned_var_always_shown(self):
        self._setup("route_id", "romance", if_count=2)
        chips = _build_chips()
        assert any(c[0] == "route_id" for c in chips)

    def test_ghost_var_shown(self):
        self._setup("trust", "high", if_count=1)
        ns["store"]._tl_ghost_nodes = [self._ghost_node(("f.rpy", 2), ["trust"])]
        chips = _build_chips()
        assert any(c[0] == "trust" for c in chips)

    def test_recently_changed_var_shown(self):
        self._setup("affection", 3, if_count=1)
        ns["store"]._tl_recently_changed_vars = {"affection"}
        chips = _build_chips()
        assert any(c[0] == "affection" for c in chips)

    def test_ghost_vars_ordered_before_non_ghost(self):
        self._setup("trust", "high", if_count=3)
        self._setup("route_id", "romance", if_count=5)
        ns["store"]._tl_ghost_nodes = [self._ghost_node(("f.rpy", 3), ["trust"])]
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

    def test_ghost_highlighting_reads_affecting_vars_from_cache(self):
        ## Regression: slim ghost dicts have no affecting_vars field.
        ## Before the fix, _tl_build_route_chips read _g.get("affecting_vars") → None,
        ## so ghost vars were never highlighted — vars at default stayed hidden and
        ## the ghost group didn't appear first in the sort order.
        ns["persistent"]._tl_var_defaults = {"trust": "low"}
        self._setup("trust", "low", if_count=1)    ## at default → hidden unless ghost-highlighted
        self._setup("route_id", "romance", if_count=1)  ## not a ghost var
        slim = {"ast_key": ("f.rpy", 1), "taken_index": 0, "branch_imgs": [], "cluster_with_prev": False}
        ns["persistent"]._tl_ghost_node_cache[str(("f.rpy", 1))] = {
            "conditions": ["trust == 'high'"], "seen_fns": [], "_regions": [],
            "affecting_vars": ["trust"],
        }
        ns["store"]._tl_ghost_nodes = [slim]
        chips = _build_chips()
        names = [c[0] for c in chips]
        ## trust must appear (default-hide overridden by ghost highlight)
        assert "trust" in names
        ## trust must sort before route_id (ghost bucket before non-ghost)
        assert names.index("trust") < names.index("route_id")


# ---------------------------------------------------------------------------
# _tl_py_pre_var_snap / _tl_py_post_var_diff — filename filter and co_names detection
# ---------------------------------------------------------------------------

_py_pre_var_snap  = ns["_tl_py_pre_var_snap"]
_py_post_var_diff = ns["_tl_py_post_var_diff"]


def _run_var_hooks(node):
    """Run pre+post var hooks with store.x mutated between them (simulates execution)."""
    snap = _py_pre_var_snap(node)
    setattr(ns["store"], "x", 1)   ## simulate Python block setting x=1
    _py_post_var_diff(snap)


class TestPythonExecutePatched:
    """
    Tests for the filename filter and co_names detection in the var-change hooks.
    We set _tl_route_var_names = ["x"], source "x = 1" compiles co_names with "x".
    Pre-hook snapshots x=0, post-hook sees x=1 → detectable via _tl_recently_changed_vars.
    """
    def setup_method(self):
        self._saved_rnames     = getattr(ns["persistent"], "_tl_route_var_names", [])
        self._saved_rcv        = getattr(ns["store"], "_tl_recently_changed_vars", set())
        self._saved_enabled    = getattr(ns["persistent"], "_tl_var_notifs_enabled", False)
        ns["persistent"]._tl_replaying = False
        ns["renpy"].config.skipping = False
        ns["persistent"]._tl_route_var_names = ["x"]
        ns["store"]._tl_recently_changed_vars = set()
        ns["persistent"]._tl_var_notifs_enabled = False
        setattr(ns["store"], "x", 0)

    def teardown_method(self):
        ns["persistent"]._tl_route_var_names = self._saved_rnames
        ns["store"]._tl_recently_changed_vars = self._saved_rcv
        ns["persistent"]._tl_replaying = False
        ns["persistent"]._tl_var_notifs_enabled = self._saved_enabled
        ns["renpy"].config.skipping = False
        if hasattr(ns["store"], "x"):
            delattr(ns["store"], "x")

    def _make_py(self, filename):
        from conftest import Python
        node = Python("x = 1")
        node.filename = filename
        return node

    def test_game_script_processing_happens(self):
        ## game script (no renpy/ prefix) with branch_id → var change detected, tinting updated
        node = self._make_py("game/scripts/intro.rpy")
        _run_var_hooks(node)
        assert "x" in ns["store"]._tl_recently_changed_vars

    def test_game_script_no_game_prefix_processing_happens(self):
        ## RenPy stores paths relative to game/ dir — scripts/ prefix with no game/ prefix
        ## is a valid game script (e.g. games that archive scripts in scripts.rpa)
        node = self._make_py("scripts/base/script.rpyc")
        _run_var_hooks(node)
        assert "x" in ns["store"]._tl_recently_changed_vars

    def test_mod_file_bypasses_processing(self):
        ## renpy-chronology-mod in filename → short-circuit before var processing
        node = self._make_py("game/renpy-chronology-mod/backend/tl_ghost_logic.rpy")
        _run_var_hooks(node)
        assert "x" not in ns["store"]._tl_recently_changed_vars

    def test_non_game_file_bypasses_processing(self):
        ## renpy/ prefix → RenPy internal, short-circuit before var processing
        node = self._make_py("renpy/common/_layout.rpym")
        _run_var_hooks(node)
        assert "x" not in ns["store"]._tl_recently_changed_vars

    def test_replaying_bypasses_processing(self):
        ns["persistent"]._tl_replaying = True
        node = self._make_py("game/scripts/intro.rpy")
        _run_var_hooks(node)
        assert "x" not in ns["store"]._tl_recently_changed_vars


# =============================================================================
# _tl_walk_ast_blocks  [Phase 0B — fails until backend/tl_ast_utils.rpy created]
# =============================================================================

class TestWalkAstBlocks:
    """
    Tests for _tl_walk_ast_blocks(nodes, visitor_fn, initial_state=None).

    visitor_fn(node, state) -> new_state is called once per unique visited node.
    The walker starts from Label nodes in game scripts, recurses into
    If entries and Menu item blocks. Already-seen nodes are skipped.
    """

    def _fn(self):
        assert _walk_ast_blocks is not None, (
            "_tl_walk_ast_blocks not found — create backend/tl_ast_utils.rpy first"
        )
        return _walk_ast_blocks

    def _visited_types(self, nodes):
        """Return list of node type names visited."""
        fn = self._fn()
        seen = []
        def v(n, s, _l=None): seen.append(type(n).__name__); return s
        fn(nodes, v)
        return seen

    def test_if_node_visited(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("x == 1", [say])])
        label = Label([if_node])
        types = self._visited_types([label])
        assert "If" in types

    def test_say_inside_if_visited(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("x == 1", [say])])
        label = Label([if_node])
        types = self._visited_types([label])
        assert "Say" in types

    def test_menu_node_visited(self):
        menu = Menu(items=[])
        label = Label([menu])
        types = self._visited_types([label])
        assert "Menu" in types

    def test_already_seen_node_not_revisited(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("x == 1", [say]), ("True", [say])])
        label = Label([if_node])
        fn = self._fn()
        count = [0]
        def visitor(n, s, _l=None):
            if type(n).__name__ == "Say":
                count[0] += 1
            return s
        fn([label], visitor)
        assert count[0] == 1

    def test_non_label_nodes_ignored(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("x == 1", [say])])
        fn = self._fn()
        visited = []
        def v(n, s, _l=None): visited.append(n); return s
        fn([if_node], v)
        assert visited == []

    def test_renpy_internal_label_excluded(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("x == 1", [say])])
        label = Label([if_node])
        label.filename = "renpy/common/00start.rpy"
        types = self._visited_types([label])
        assert "If" not in types

    def test_empty_nodes_list(self):
        fn = self._fn()
        visited = []
        def v(n, s, _l=None): visited.append(n); return s
        fn([], v)
        assert visited == []

    def test_multiple_labels_all_visited(self):
        say_a = Say("char", identifier="id_a")
        say_b = Say("char", identifier="id_b")
        if_a = If(entries=[("x == 1", [say_a])])
        if_b = If(entries=[("y == 2", [say_b])])
        label_a = Label([if_a])
        label_b = Label([if_b])
        fn = self._fn()
        count = [0]
        def visitor(n, s, _l=None):
            if type(n).__name__ == "If":
                count[0] += 1
            return s
        fn([label_a, label_b], visitor)
        assert count[0] == 2