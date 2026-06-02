"""
test_ast_walk.py — Unit tests for backend/tl_ast_utils.rpy.

Functions covered:
  _tl_walk_ast_blocks  (stateful signature: visitor_fn(node, state) -> state)
  _tl_build_menu_scene_index
"""

import pytest
from conftest import (
    _rpy_ns as ns,
    If, Label, Say, Return, Menu, Show, Scene,
)

_walk_ast_blocks     = ns.get("_tl_walk_ast_blocks")
_build_menu_scene    = ns.get("_tl_build_menu_scene_index")
_menu_site_key       = ns.get("_tl_menu_site_key")


# =============================================================================
# _tl_walk_ast_blocks — stateful behaviour
# =============================================================================

class TestWalkAstBlocksStateful:
    """
    Verify that state threads correctly through the worklist walk.
    visitor_fn(node, state) -> new_state; child blocks inherit state at the
    branch point; state in a branch does not affect the parent flow.
    """

    def _walk(self, nodes, visitor, initial_state=None):
        assert _walk_ast_blocks is not None, "_tl_walk_ast_blocks not found"
        _walk_ast_blocks(nodes, visitor, initial_state)

    def test_initial_state_passed_to_first_node(self):
        say = Say("char")
        label = Label([say])
        received = []
        def v(n, s, _l=None): received.append(s); return s
        self._walk([label], v, initial_state="start")
        assert received == ["start"]

    def test_initial_state_defaults_to_none(self):
        say = Say("char")
        label = Label([say])
        received = []
        def v(n, s, _l=None): received.append(s); return s
        self._walk([label], v)
        assert received == [None]

    def test_state_threads_sequentially_through_block(self):
        # Each node in a block receives the state returned by the previous node.
        say_a = Say("char", identifier="a")
        say_b = Say("char", identifier="b")
        label = Label([say_a, say_b])
        order = []
        def v(n, s, _l=None):
            new_s = (s or 0) + 1
            order.append(new_s)
            return new_s
        self._walk([label], v, initial_state=0)
        assert order == [1, 2]

    def test_child_block_inherits_state_at_branch_point(self):
        # State is "bg_room" when If is reached; the Say inside the branch
        # should receive "bg_room".
        show = Show("bg_room")
        say = Say("char")
        if_node = If(entries=[("x==1", [say])])
        label = Label([show, if_node])
        child_states = []
        def v(n, s, _l=None):
            if type(n).__name__ == "Show":
                return "bg_room"
            if type(n).__name__ == "Say":
                child_states.append(s)
            return s
        self._walk([label], v, initial_state=None)
        assert child_states == ["bg_room"]

    def test_branch_state_does_not_affect_main_flow_after_if(self):
        # Show inside a branch must not change state seen by nodes after the If
        # in the parent block (the If visitor itself returns state unchanged).
        if_node = If(entries=[("x==1", [Show("bg_branch")])])
        say = Say("char")
        label = Label([if_node, say])
        after_if_states = []
        def v(n, s, _l=None):
            if type(n).__name__ == "Show":
                return "bg_branch"
            if type(n).__name__ == "Say":
                after_if_states.append(s)
            return s
        self._walk([label], v, initial_state=None)
        # If node visitor returns None (falls through to `return s`); Say gets None
        assert after_if_states == [None]

    def test_multiple_if_branches_each_inherit_same_state(self):
        # Both branches of an If receive the state at the branch point.
        show = Show("bg_room")
        say_a = Say("char", identifier="a")
        say_b = Say("char", identifier="b")
        if_node = If(entries=[("x==1", [say_a]), ("True", [say_b])])
        label = Label([show, if_node])
        child_states = []
        def v(n, s, _l=None):
            if type(n).__name__ == "Show":
                return "bg_room"
            if type(n).__name__ == "Say":
                child_states.append(s)
            return s
        self._walk([label], v, initial_state=None)
        assert child_states == ["bg_room", "bg_room"]


# =============================================================================
# _tl_walk_ast_blocks — current_label (3rd visitor arg)
# =============================================================================

class TestWalkAstBlocksCurrentLabel:
    """
    Verifies that _tl_walk_ast_blocks passes the correct label name as the
    third argument to visitors. The label name is seeded from each Label node's
    .name attribute and propagates unchanged into If/Menu sub-blocks.
    """

    def _fn(self):
        return _walk_ast_blocks

    def test_visitor_receives_label_name(self):
        say = Say("char")
        label = Label([say], name="prologue")
        labels_seen = []
        def v(n, s, cur_label=None): labels_seen.append(cur_label); return s
        self._fn()([label], v)
        assert "prologue" in labels_seen

    def test_two_labels_give_correct_names(self):
        say_a = Say("char", identifier="a")
        say_b = Say("char", identifier="b")
        label_a = Label([say_a], name="chap1")
        label_b = Label([say_b], name="chap2")
        collected = []
        def v(n, s, cur_label=None):
            if type(n).__name__ == "Say":
                collected.append((getattr(n, "identifier", None), cur_label))
            return s
        self._fn()([label_a, label_b], v)
        assert ("a", "chap1") in collected
        assert ("b", "chap2") in collected

    def test_if_branch_inherits_label_name(self):
        say = Say("char", identifier="inner")
        if_node = If(entries=[("True", [say])])
        label = Label([if_node], name="my_label")
        collected = []
        def v(n, s, cur_label=None):
            if type(n).__name__ == "Say":
                collected.append(cur_label)
            return s
        self._fn()([label], v)
        assert collected == ["my_label"]

    def test_menu_option_block_inherits_label_name(self):
        say = Say("char", identifier="opt_say")
        menu = Menu(items=[("Choice", None, [say])])
        label = Label([menu], name="scene_label")
        collected = []
        def v(n, s, cur_label=None):
            if type(n).__name__ == "Say":
                collected.append(cur_label)
            return s
        self._fn()([label], v)
        assert collected == ["scene_label"]


# =============================================================================
# _tl_build_menu_scene_index
# =============================================================================

class TestBuildMenuSceneIndex:
    """
    Tests for _tl_build_menu_scene_index(nodes).

    Builds persistent._tl_menu_scene_map: {(file, line) -> img_name}.
    Only fills missing entries (runtime-captured values are authoritative).
    """

    def setup_method(self):
        self._saved = dict(ns["persistent"]._tl_menu_scene_map)
        ns["persistent"]._tl_menu_scene_map = {}

    def teardown_method(self):
        ns["persistent"]._tl_menu_scene_map = self._saved

    def _map(self):
        return ns["persistent"]._tl_menu_scene_map

    def _key(self, f, ln):
        return _menu_site_key(f, ln)

    def _build(self, nodes):
        assert _build_menu_scene is not None, "_tl_build_menu_scene_index not found"
        _build_menu_scene(nodes)

    # ------------------------------------------------------------------
    # Basic scene recording
    # ------------------------------------------------------------------

    def test_show_before_menu_recorded(self):
        show = Show("bg_room")
        menu = Menu(items=[])
        menu.filename = "script.rpy"
        menu.linenumber = 10
        self._build([Label([show, menu])])
        assert self._map().get(self._key("script.rpy", 10)) == "bg_room"

    def test_no_scene_before_menu_not_recorded(self):
        menu = Menu(items=[])
        menu.filename = "script.rpy"
        menu.linenumber = 10
        self._build([Label([menu])])
        assert self._map() == {}

    def test_scene_updates_between_menus(self):
        show1 = Show("bg_room")
        menu1 = Menu(items=[])
        menu1.filename = "script.rpy"
        menu1.linenumber = 10
        show2 = Show("bg_park")
        menu2 = Menu(items=[])
        menu2.filename = "script.rpy"
        menu2.linenumber = 20
        self._build([Label([show1, menu1, show2, menu2])])
        assert self._map().get(self._key("script.rpy", 10)) == "bg_room"
        assert self._map().get(self._key("script.rpy", 20)) == "bg_park"

    def test_say_between_show_and_menu_does_not_reset_scene(self):
        show = Show("bg_room")
        say = Say("char")
        menu = Menu(items=[])
        menu.filename = "script.rpy"
        menu.linenumber = 10
        self._build([Label([show, say, menu])])
        assert self._map().get(self._key("script.rpy", 10)) == "bg_room"

    # ------------------------------------------------------------------
    # Branch isolation
    # ------------------------------------------------------------------

    def test_scene_in_if_branch_does_not_affect_menu_after_if(self):
        # Show is only inside the If branch; the Menu after the If has no scene
        # in the main flow, so it should not be recorded.
        if_node = If(entries=[("x==1", [Show("bg_branch")])])
        menu = Menu(items=[])
        menu.filename = "script.rpy"
        menu.linenumber = 30
        self._build([Label([if_node, menu])])
        assert self._key("script.rpy", 30) not in self._map()

    def test_scene_before_if_carries_into_menu_after_if(self):
        show = Show("bg_room")
        if_node = If(entries=[("x==1", [Say("char")])])
        menu = Menu(items=[])
        menu.filename = "script.rpy"
        menu.linenumber = 30
        self._build([Label([show, if_node, menu])])
        assert self._map().get(self._key("script.rpy", 30)) == "bg_room"

    def test_menu_inside_if_branch_gets_branch_scene(self):
        show = Show("bg_room")
        inner_show = Show("bg_branch")
        inner_menu = Menu(items=[])
        inner_menu.filename = "script.rpy"
        inner_menu.linenumber = 40
        if_node = If(entries=[("x==1", [inner_show, inner_menu])])
        self._build([Label([show, if_node])])
        assert self._map().get(self._key("script.rpy", 40)) == "bg_branch"

    # ------------------------------------------------------------------
    # Backfill semantics: existing entries not overwritten
    # ------------------------------------------------------------------

    def test_existing_entry_not_overwritten(self):
        key = self._key("script.rpy", 10)
        ns["persistent"]._tl_menu_scene_map[key] = "existing"
        show = Show("bg_room")
        menu = Menu(items=[])
        menu.filename = "script.rpy"
        menu.linenumber = 10
        self._build([Label([show, menu])])
        assert self._map().get(key) == "existing"

    # ------------------------------------------------------------------
    # File filtering
    # ------------------------------------------------------------------

    def test_renpy_internal_label_excluded(self):
        show = Show("bg_room")
        menu = Menu(items=[])
        menu.filename = "renpy/test.rpy"
        menu.linenumber = 10
        label = Label([show, menu])
        label.filename = "renpy/test.rpy"
        self._build([label])
        assert self._map() == {}

    def test_mod_file_excluded(self):
        show = Show("bg_room")
        menu = Menu(items=[])
        menu.filename = "game/renpy-chronology-mod/timeline_init.rpy"
        menu.linenumber = 10
        label = Label([show, menu])
        label.filename = "game/renpy-chronology-mod/timeline_init.rpy"
        self._build([label])
        assert self._map() == {}