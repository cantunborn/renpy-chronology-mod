"""
Tests for tl_seen_check.rpy — node-has-new, eval seen fn, make_seen_fn,
find_scene_seen_name, option_seen.
Run: pytest tests/test_seen_check.py -v
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns, Say, Jump, Call, Return, Scene, Label, If, Menu, Python

_tl_node_has_new       = _rpy_ns["_tl_node_has_new"]
_tl_eval_seen_fn       = _rpy_ns["_tl_eval_seen_fn"]
_tl_make_seen_fn       = _rpy_ns["_tl_make_seen_fn"]
_tl_find_scene_seen    = _rpy_ns["_tl_find_scene_seen_name"]
_tl_option_seen        = _rpy_ns["_tl_option_seen"]

# =============================================================================
# _tl_node_has_new
# =============================================================================

class TestNodeHasNew:
    _LOC = "test_loc_has_new"

    def _make(self, options, chosen_index=None):
        return {"index": 0, "options": options, "chosen_index": chosen_index,
                "prompt": "Test?", "_location": self._LOC}

    def _mark_seen(self, node, *indices):
        _p = _rpy_ns["persistent"]
        for i in indices:
            _p._chosen[(self._LOC, node["options"][i])] = True

    def setup_method(self):
        self._chosen_saved = _rpy_ns["persistent"]._chosen
        _rpy_ns["persistent"]._chosen = {}

    def teardown_method(self):
        _rpy_ns["persistent"]._chosen = self._chosen_saved

    def test_all_seen_returns_false(self):
        node = self._make(["A", "B", "C"])
        self._mark_seen(node, 0, 1, 2)
        assert _tl_node_has_new(node) is False

    def test_none_seen_returns_true(self):
        node = self._make(["A", "B"])
        assert _tl_node_has_new(node) is True

    def test_partial_seen_returns_true(self):
        node = self._make(["A", "B", "C"])
        self._mark_seen(node, 0)
        assert _tl_node_has_new(node) is True

    def test_single_option_seen(self):
        node = self._make(["A"])
        self._mark_seen(node, 0)
        assert _tl_node_has_new(node) is False

    def test_single_option_unseen(self):
        node = self._make(["A"])
        assert _tl_node_has_new(node) is True

    def test_empty_options(self):
        node = self._make([])
        assert _tl_node_has_new(node) is False

    def test_chosen_option_skipped_even_if_unseen(self):
        # Chosen (idx 2) is unseen; others are seen → no dot
        node = self._make(["A", "B", "C"], chosen_index=2)
        self._mark_seen(node, 0, 1)
        assert _tl_node_has_new(node) is False

    def test_unchosen_unseen_shows_dot(self):
        # Chosen (idx 0) is seen; options 1 and 2 are unseen → dot
        node = self._make(["A", "B", "C"], chosen_index=0)
        self._mark_seen(node, 0)
        assert _tl_node_has_new(node) is True

    def test_all_unchosen_seen_no_dot(self):
        # Chosen = 1; options 0 and 2 also seen → no dot
        node = self._make(["A", "B", "C"], chosen_index=1)
        self._mark_seen(node, 0, 1, 2)
        assert _tl_node_has_new(node) is False

    def test_no_chosen_index_checks_all(self):
        node = self._make(["A", "B"], chosen_index=None)
        assert _tl_node_has_new(node) is True       # none seen
        self._mark_seen(node, 0, 1)
        assert _tl_node_has_new(node) is False      # all seen



# =============================================================================
# _tl_eval_seen_fn
# =============================================================================

class TestEvalSeenFn:
    def setup_method(self):
        _p = _rpy_ns["persistent"]
        self._seen_ever_saved  = _p._seen_ever
        self._seen_label_saved = _rpy_ns["renpy"].seen_label

    def teardown_method(self):
        _rpy_ns["persistent"]._seen_ever = self._seen_ever_saved
        _rpy_ns["renpy"].seen_label      = self._seen_label_saved

    def test_never(self):
        assert _tl_eval_seen_fn(("never",)) == False

    def test_say_seen(self):
        _rpy_ns["persistent"]._seen_ever = {"abc123": True}
        assert _tl_eval_seen_fn(("say", "abc123")) == True

    def test_say_unseen(self):
        _rpy_ns["persistent"]._seen_ever = {"xyz": True}
        assert _tl_eval_seen_fn(("say", "abc123")) == False

    def test_say_no_seen_ever(self):
        _rpy_ns["persistent"]._seen_ever = None
        assert _tl_eval_seen_fn(("say", "abc123")) == False

    def test_label_seen(self):
        _rpy_ns["renpy"].seen_label = lambda l: l == "mom_crown_r"
        assert _tl_eval_seen_fn(("label", "mom_crown_r")) == True

    def test_label_unseen(self):
        _rpy_ns["renpy"].seen_label = lambda l: False
        assert _tl_eval_seen_fn(("label", "cass_crown_r")) == False

    def test_label_no_fn(self):
        _rpy_ns["renpy"].seen_label = None
        assert _tl_eval_seen_fn(("label", "foo")) == False




# =============================================================================
# _tl_make_seen_fn
# =============================================================================

def _link(*nodes):
    """Chain nodes via .next and return the first."""
    for a, b in zip(nodes, nodes[1:]):
        a.next = b
    return nodes[0]


class TestMakeSeenFn:
    def test_empty_block_returns_never(self):
        assert _tl_make_seen_fn([]) == ("never",)

    def test_named_say_returns_say_descriptor(self):
        node = Say("mc")
        assert _tl_make_seen_fn([node]) == ("say", "mc")

    def test_narrator_say_no_name_walks_forward(self):
        narrator = Say(None)
        named = Say("elin")
        _link(narrator, named)
        assert _tl_make_seen_fn([narrator]) == ("say", "elin")

    def test_jump_returns_label_descriptor(self):
        node = Jump("some_label")
        assert _tl_make_seen_fn([node]) == ("label", "some_label")

    def test_call_returns_label_descriptor(self):
        node = Call("subroutine")
        assert _tl_make_seen_fn([node]) == ("label", "subroutine")

    def test_return_returns_never(self):
        assert _tl_make_seen_fn([Return()]) == ("never",)

    def test_python_node_walks_to_say(self):
        py = Python("x = 1")
        say = Say("viv")
        _link(py, say)
        assert _tl_make_seen_fn([py]) == ("say", "viv")

    def test_hits_return_before_say_returns_never(self):
        ret = Return()
        say = Say("mc")
        _link(ret, say)
        assert _tl_make_seen_fn([ret]) == ("never",)

    def test_scene_node_walks_forward_to_say(self):
        scene = Scene()
        say = Say("viv")
        _link(scene, say)
        assert _tl_make_seen_fn([scene]) == ("say", "viv")


# =============================================================================
# _tl_find_scene_seen_name
# =============================================================================

class TestFindSceneSeenName:
    def test_say_node_directly_returns_name(self):
        node = Say("mc")
        assert _tl_find_scene_seen(node) == "mc"

    def test_say_after_python_returns_name(self):
        py = Python("x = 1")
        say = Say("elin")
        _link(py, say)
        assert _tl_find_scene_seen(py) == "elin"

    def test_hits_jump_before_say_returns_none(self):
        jmp = Jump("elsewhere")
        say = Say("mc")
        _link(jmp, say)
        assert _tl_find_scene_seen(jmp) is None

    def test_hits_return_before_say_returns_none(self):
        ret = Return()
        say = Say("mc")
        _link(ret, say)
        assert _tl_find_scene_seen(ret) is None

    def test_hits_menu_before_say_returns_none(self):
        menu_node = Menu()
        say = Say("mc")
        menu_node.next = say
        assert _tl_find_scene_seen(menu_node) is None

    def test_runs_out_of_nodes_returns_none(self):
        py = Python("x = 1")  # no .next → returns None after 1 hop
        assert _tl_find_scene_seen(py, max_hops=1) is None

    def test_max_hops_exceeded_returns_none(self):
        # Chain longer than max_hops
        nodes = [Python("x = {}".format(i)) for i in range(5)]
        say = Say("mc")
        nodes.append(say)
        for a, b in zip(nodes, nodes[1:]):
            a.next = b
        assert _tl_find_scene_seen(nodes[0], max_hops=3) is None

    def test_none_start_returns_none(self):
        assert _tl_find_scene_seen(None) is None


# =============================================================================
# _tl_option_seen
# =============================================================================

class TestOptionSeen:
    _LOC = ("test.rpy", 0, 10)

    def setup_method(self):
        p = _rpy_ns["persistent"]
        self._chosen_saved    = p._chosen
        self._seen_ever_saved = p._seen_ever
        self._ast_map_saved   = _rpy_ns.get("_tl_ast_map", {})
        p._chosen    = {}
        p._seen_ever = {}
        _rpy_ns["_tl_ast_map"] = {}

    def teardown_method(self):
        p = _rpy_ns["persistent"]
        p._chosen    = self._chosen_saved
        p._seen_ever = self._seen_ever_saved
        _rpy_ns["_tl_ast_map"] = self._ast_map_saved

    def _node(self, options, location=None, ast_key=None):
        n = {"index": 0, "options": options, "chosen_index": 0,
             "_location": location or self._LOC}
        if ast_key is not None:
            n["ast_key"] = ast_key
        return n

    def test_persistent_chosen_returns_true(self):
        node = self._node(["A", "B"])
        _rpy_ns["persistent"]._chosen[(self._LOC, "B")] = True
        assert _tl_option_seen(node, 1) is True

    def test_persistent_chosen_miss_returns_false(self):
        node = self._node(["A", "B"])
        assert _tl_option_seen(node, 1) is False

    def test_ast_map_say_seen(self):
        key = ("test.rpy", 99)
        node = self._node(["A", "B"], ast_key=key)
        _rpy_ns["_tl_ast_map"][key] = [("say", "x"), ("say", "y")]
        _rpy_ns["persistent"]._seen_ever = {"y": True}
        assert _tl_option_seen(node, 1) is True

    def test_ast_map_say_unseen(self):
        key = ("test.rpy", 99)
        node = self._node(["A", "B"], ast_key=key)
        _rpy_ns["_tl_ast_map"][key] = [("say", "x"), ("say", "y")]
        _rpy_ns["persistent"]._seen_ever = {}
        assert _tl_option_seen(node, 1) is False

    def test_ast_map_label_seen(self):
        key = ("test.rpy", 99)
        node = self._node(["A"], ast_key=key)
        _rpy_ns["_tl_ast_map"][key] = [("label", "my_label")]
        _rpy_ns["renpy"].seen_label = lambda l: l == "my_label"
        assert _tl_option_seen(node, 0) is True
        _rpy_ns["renpy"].seen_label = lambda l: False

    def test_no_location_no_ast_map_returns_false(self):
        node = {"index": 0, "options": ["A"], "chosen_index": 0}
        assert _tl_option_seen(node, 0) is False

    def test_index_out_of_range_returns_false(self):
        node = self._node(["A"])
        assert _tl_option_seen(node, 5) is False


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
