"""
Tests for tl_seen_check.rpy — node-has-new, eval seen fn, make_seen_fn,
find_scene_seen_name, option_seen.
Run: pytest tests/test_seen_check.py -v
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns, Say, Jump, Call, Return, Scene, Label, If, Menu, Python, TranslateSay

_tl_node_has_new          = _rpy_ns["_tl_node_has_new"]
_tl_eval_seen_fn          = _rpy_ns["_tl_eval_seen_fn"]
_tl_make_seen_fn          = _rpy_ns["_tl_make_seen_fn"]
_tl_find_scene_seen       = _rpy_ns["_tl_find_scene_seen_name"]
_tl_option_seen           = _rpy_ns["_tl_option_seen"]
_tl_say_seen_name         = _rpy_ns["_tl_say_seen_name"]
_tl_follow_jump_seen_name = _rpy_ns["_tl_follow_jump_seen_name"]

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
        self._seen_ever_saved       = _p._seen_ever
        self._seen_translates_saved = _p._seen_translates
        self._seen_label_saved      = _rpy_ns["renpy"].seen_label
        _p._seen_translates = set()

    def teardown_method(self):
        _p = _rpy_ns["persistent"]
        _p._seen_ever       = self._seen_ever_saved
        _p._seen_translates = self._seen_translates_saved
        _rpy_ns["renpy"].seen_label = self._seen_label_saved

    def test_never(self):
        assert _tl_eval_seen_fn(("never",)) == False

    ## String keys → renpy.seen_translation() (new RenPy path)
    def test_say_seen_string_key(self):
        _rpy_ns["persistent"]._seen_translates = {"abc123"}
        assert _tl_eval_seen_fn(("say", "abc123")) == True

    def test_say_unseen_string_key(self):
        _rpy_ns["persistent"]._seen_translates = {"xyz"}
        assert _tl_eval_seen_fn(("say", "abc123")) == False

    ## Tuple keys → _seen_ever dict (old RenPy path)
    def test_say_seen_tuple_key(self):
        _key = ("script.rpy", 42, "hash")
        _rpy_ns["persistent"]._seen_ever = {_key: True}
        assert _tl_eval_seen_fn(("say", _key)) == True

    def test_say_unseen_tuple_key(self):
        _rpy_ns["persistent"]._seen_ever = {}
        assert _tl_eval_seen_fn(("say", ("script.rpy", 42, "hash"))) == False

    def test_say_no_seen_ever_tuple_key(self):
        _rpy_ns["persistent"]._seen_ever = None
        assert _tl_eval_seen_fn(("say", ("script.rpy", 1, "x"))) == False

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

    def test_narrator_say_no_name_skipped_next_say_used(self):
        ## _tl_make_seen_fn iterates the block list, not .next links.
        ## Narrator Say (name=None) yields no key; the next Say in the block does.
        narrator = Say(None)
        named = Say("elin")
        assert _tl_make_seen_fn([narrator, named]) == ("say", "elin")

    def test_jump_returns_label_descriptor(self):
        node = Jump("some_label")
        assert _tl_make_seen_fn([node]) == ("label", "some_label")

    def test_call_returns_label_descriptor(self):
        node = Call("subroutine")
        assert _tl_make_seen_fn([node]) == ("label", "subroutine")

    def test_return_returns_never(self):
        assert _tl_make_seen_fn([Return()]) == ("never",)

    def test_python_node_skipped_say_in_block_used(self):
        ## Python nodes are skipped; the Say later in the same block is used.
        py = Python("x = 1")
        say = Say("viv")
        assert _tl_make_seen_fn([py, say]) == ("say", "viv")

    def test_hits_return_before_say_returns_never(self):
        ret = Return()
        say = Say("mc")
        _link(ret, say)
        assert _tl_make_seen_fn([ret]) == ("never",)

    def test_scene_then_say_returns_say_descriptor(self):
        ## Say takes priority over Scene in the same block.
        scene = Scene()
        say = Say("viv")
        assert _tl_make_seen_fn([scene, say]) == ("say", "viv")

    def test_scene_alone_returns_image_descriptor(self):
        ## Scene with no Say → returns ("image", ...) from the scene image name.
        scene = Scene()
        result = _tl_make_seen_fn([scene])
        assert result[0] == "image"


# =============================================================================
# _tl_say_seen_name — translator resolution
# =============================================================================

class TestSaySeenName:
    def setup_method(self):
        self._translator    = _rpy_ns["renpy"].game.script.translator
        self._orig_map      = dict(self._translator._map)
        self._seen_tl_saved = _rpy_ns["renpy"].seen_translation

    def teardown_method(self):
        self._translator._map              = self._orig_map
        _rpy_ns["renpy"].seen_translation  = self._seen_tl_saved

    def _remove_seen_translation(self):
        """Simulate old RenPy that lacks renpy.seen_translation."""
        try:
            del _rpy_ns["renpy"].seen_translation
        except AttributeError:
            pass

    ## New RenPy (seen_translation present): identifier returned directly
    def test_say_with_no_identifier_returns_node_name(self):
        node = Say("mc_name")
        assert _tl_say_seen_name(node) == "mc_name"

    def test_say_with_identifier_new_renpy_returns_identifier(self):
        node = Say("mc_name", identifier="id_001")
        assert _tl_say_seen_name(node) == "id_001"

    def test_translate_say_with_identifier_new_renpy_returns_identifier(self):
        node = TranslateSay("elin_orig", identifier="id_002")
        assert _tl_say_seen_name(node) == "id_002"

    ## Old RenPy (no seen_translation): resolve via translator, fall back to node.name
    def test_old_renpy_identifier_no_translator_entry_returns_node_name(self):
        self._remove_seen_translation()
        node = Say("mc_name", identifier="id_001")
        assert _tl_say_seen_name(node) == "mc_name"

    def test_old_renpy_identifier_translator_entry_returns_translated_name(self):
        self._remove_seen_translation()
        tr_node = TranslateSay("tl_mc_name", identifier="id_001")
        self._translator._map["id_001"] = tr_node
        node = Say("mc_name", identifier="id_001")
        assert _tl_say_seen_name(node) == "tl_mc_name"

    def test_old_renpy_translate_say_uses_translated_name(self):
        self._remove_seen_translation()
        tr_node = TranslateSay("tl_elin", identifier="id_002")
        self._translator._map["id_002"] = tr_node
        node = TranslateSay("elin_orig", identifier="id_002")
        assert _tl_say_seen_name(node) == "tl_elin"


# =============================================================================
# _tl_follow_jump_seen_name — jump-hop for cold_castle-style blocks
# =============================================================================

class TestFollowJumpSeenName:
    def setup_method(self):
        self._namemap_saved = dict(_rpy_ns["renpy"].game.script.namemap)
        _rpy_ns["renpy"].game.script.namemap.clear()

    def teardown_method(self):
        _rpy_ns["renpy"].game.script.namemap.clear()
        _rpy_ns["renpy"].game.script.namemap.update(self._namemap_saved)

    def _add_label(self, name, first_node):
        lbl = Label([])
        lbl.next = first_node
        _rpy_ns["renpy"].game.script.namemap[name] = lbl

    def test_unknown_target_returns_none(self):
        assert _tl_follow_jump_seen_name("nonexistent_label") is None

    def test_label_with_say_returns_say_name(self):
        say = Say("elin")
        self._add_label("cold_lab", say)
        assert _tl_follow_jump_seen_name("cold_lab") == "elin"

    def test_label_with_python_then_say_returns_say_name(self):
        py = Python("x = 1")
        say = Say("viv")
        _link(py, say)
        self._add_label("lab_py_say", py)
        assert _tl_follow_jump_seen_name("lab_py_say") == "viv"

    def test_label_with_jump_before_say_returns_none(self):
        jmp = Jump("elsewhere")
        say = Say("mc")
        _link(jmp, say)
        self._add_label("lab_jump", jmp)
        assert _tl_follow_jump_seen_name("lab_jump") is None

    def test_label_with_no_content_returns_none(self):
        self._add_label("empty_lab", None)
        assert _tl_follow_jump_seen_name("empty_lab") is None


# =============================================================================
# _tl_make_seen_fn — say_range and Show exclusion
# =============================================================================

class TestMakeSeenFnExtended:
    def test_multiple_say_nodes_returns_say_range(self):
        s1 = Say("elin_1")
        s2 = Say("elin_2")
        s3 = Say("elin_3")
        result = _tl_make_seen_fn([s1, s2, s3])
        assert result == ("say_range", "elin_1", "elin_3")

    def test_two_say_nodes_returns_say_range(self):
        s1 = Say("a")
        s2 = Say("b")
        assert _tl_make_seen_fn([s1, s2]) == ("say_range", "a", "b")

    def test_show_node_excluded_say_survives(self):
        from conftest import Show
        show = Show()
        say = Say("mc")
        result = _tl_make_seen_fn([say, show])
        assert result == ("say", "mc")

    def test_show_only_block_returns_never(self):
        ## Plain Show with no imspec — nothing to check, falls through to ("never",).
        from conftest import Show
        result = _tl_make_seen_fn([Show(), Show()])
        assert result == ("never",)

    def test_show_plain_imspec_returns_never(self):
        ## Plain shows like `show eileen happy` — all simple identifiers, no expression args.
        from conftest import Show
        result = _tl_make_seen_fn([Show("eileen", "happy")])
        assert result == ("never",)

    def test_show_expr_imspec_returns_image(self):
        ## Show nodes with expression args (ParameterizedText) produce ("image", raw_parts).
        ## _seen_images stores raw imspec parts, so no eval is needed at check time.
        from conftest import Show
        result = _tl_make_seen_fn([Show("bottom_text012", "_", "('кошмар')")])
        assert result == ("image", ("bottom_text012", "_", "('кошмар')"))

    def test_show_expr_imspec_lower_priority_than_say(self):
        from conftest import Show
        result = _tl_make_seen_fn([Say("mc"), Show("txt", "_", "('hi')")])
        assert result == ("say", "mc")

    def test_scene_then_say_say_takes_priority(self):
        result = _tl_make_seen_fn([Scene(), Say("mc")])
        assert result == ("say", "mc")

    def test_jump_with_no_jump_follow_returns_label(self):
        jmp = Jump("far_label")
        result = _tl_make_seen_fn([jmp])
        assert result == ("label", "far_label")

    def test_jump_with_prior_say_returns_say(self):
        say = Say("mc")
        jmp = Jump("far_label")
        result = _tl_make_seen_fn([say, jmp])
        assert result == ("say", "mc")


# =============================================================================
# _tl_eval_seen_fn — say_range descriptor
# =============================================================================

class TestEvalSeenFnSayRange:
    def setup_method(self):
        _p = _rpy_ns["persistent"]
        self._seen_ever_saved       = _p._seen_ever
        self._seen_translates_saved = _p._seen_translates
        _p._seen_translates = set()

    def teardown_method(self):
        _p = _rpy_ns["persistent"]
        _p._seen_ever       = self._seen_ever_saved
        _p._seen_translates = self._seen_translates_saved

    ## String keys → seen_translation() (new RenPy path)
    def test_say_range_first_absent_returns_false(self):
        _rpy_ns["persistent"]._seen_translates = {"last_name"}
        assert _tl_eval_seen_fn(("say_range", "first_name", "last_name")) is False

    def test_say_range_first_seen_last_absent_returns_false(self):
        _rpy_ns["persistent"]._seen_translates = {"first_name"}
        assert _tl_eval_seen_fn(("say_range", "first_name", "last_name")) is False

    def test_say_range_both_seen_returns_true(self):
        _rpy_ns["persistent"]._seen_translates = {"first_name", "last_name"}
        assert _tl_eval_seen_fn(("say_range", "first_name", "last_name")) is True

    def test_say_range_single_name_both_same(self):
        _rpy_ns["persistent"]._seen_translates = {"only_name"}
        assert _tl_eval_seen_fn(("say_range", "only_name", "only_name")) is True

    ## Tuple keys → _seen_ever (old RenPy path)
    def test_say_range_tuple_keys_both_seen(self):
        _k1, _k2 = ("a.rpy", 1, "h1"), ("a.rpy", 2, "h2")
        _rpy_ns["persistent"]._seen_ever = {_k1: True, _k2: True}
        assert _tl_eval_seen_fn(("say_range", _k1, _k2)) is True

    def test_say_range_tuple_keys_first_absent(self):
        _k1, _k2 = ("a.rpy", 1, "h1"), ("a.rpy", 2, "h2")
        _rpy_ns["persistent"]._seen_ever = {_k2: True}
        assert _tl_eval_seen_fn(("say_range", _k1, _k2)) is False


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
        p._chosen    = {}
        p._seen_ever = {}

    def teardown_method(self):
        p = _rpy_ns["persistent"]
        p._chosen    = self._chosen_saved
        p._seen_ever = self._seen_ever_saved

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

    def test_no_location_returns_false(self):
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
