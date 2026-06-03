"""
test_ghost_logic.py — Unit tests for backend/tl_ghost_logic.rpy pure-logic functions.

Functions covered:
  _tl_extract_vars_from_conditions
  _tl_prettify_var
  _tl_prettify_condition
  _tl_parse_regions
  _tl_should_cluster
  _tl_get_taken_branch
  _tl_branch_exits_before_next
  _tl_collect_if_run
  _tl_partition_if_run
  _tl_extract_compare_literals  [Phase 0B — initially fails until tl_ast_utils.rpy created]
"""

import pytest
from conftest import (
    _rpy_ns as ns,
    If, Jump, Return, Say, Scene, Python,
    _renpy as _stub_renpy,
)

_extract    = ns["_tl_extract_vars_from_conditions"]
## Phase 0B: None until backend/tl_ast_utils.rpy is created
_extract_compare_literals = ns.get("_tl_extract_compare_literals")
_prettify_v = ns["_tl_prettify_var"]
_prettify_c = ns["_tl_prettify_condition"]
_parse      = ns["_tl_parse_regions"]
_cluster    = ns["_tl_should_cluster"]
_taken      = ns["_tl_get_taken_branch"]
_exits      = ns["_tl_branch_exits_before_next"]
_collect    = ns["_tl_collect_if_run"]
_partition  = ns["_tl_partition_if_run"]


# ---------------------------------------------------------------------------
# _tl_extract_vars_from_conditions
# ---------------------------------------------------------------------------

class TestExtractVarsFromConditions:
    def test_single_equality(self):
        assert _extract(["mom_bath_ten == 1"]) == {"mom_bath_ten"}

    def test_two_vars_and(self):
        result = _extract(["elin_intro_mood > 0 and tavernroad_end == 1"])
        assert result == {"elin_intro_mood", "tavernroad_end"}

    def test_true_sentinel_skipped(self):
        assert _extract(["True"]) == set()

    def test_false_sentinel_skipped(self):
        assert _extract(["False"]) == set()

    def test_multiple_conditions(self):
        result = _extract(["mom_bath == 1", "cass_promise == 0", "True"])
        assert result == {"mom_bath", "cass_promise"}

    def test_function_call_excluded(self):
        result = _extract(["renpy.seen_label('foo') and bar"])
        assert "bar" in result
        assert "seen_label" not in result

    def test_uppercase_excluded(self):
        result = _extract(["MyClass and my_var"])
        assert result == {"my_var"}

    def test_bare_truthy_var(self):
        assert _extract(["wendyRat"]) == {"wendyRat"}

    def test_camel_case_var(self):
        result = _extract(["wendyRat == 1 and katieSeduced"])
        assert result == {"wendyRat", "katieSeduced"}

    def test_bare_not_var(self):
        assert _extract(["not wendyRat"]) == {"wendyRat"}

    def test_string_literal_content_not_picked_up(self):
        result = _extract(["foo == 'bar_baz'"])
        assert result == {"foo"}
        assert "bar_baz" not in result

    def test_empty_conditions(self):
        assert _extract([]) == set()

    def test_renpy_builtins_excluded(self):
        result = _extract(["renpy.has_label('after_load')"])
        assert result == set()


# ---------------------------------------------------------------------------
# _tl_prettify_var
# ---------------------------------------------------------------------------

class TestPrettifyVar:
    def test_mc_prefix_stripped(self):
        assert _prettify_v("mc_viv_affection") == "Viv Affection"

    def test_flag_prefix_stripped(self):
        assert _prettify_v("flag_chose_honesty") == "Chose Honesty"

    def test_is_prefix_stripped(self):
        assert _prettify_v("is_route_a") == "Route A"

    def test_has_prefix_stripped(self):
        assert _prettify_v("has_key") == "Key"

    def test_no_prefix(self):
        assert _prettify_v("viv_trust") == "Viv Trust"

    def test_single_word(self):
        assert _prettify_v("route") == "Route"

    def test_mc_single_letter(self):
        assert _prettify_v("mc_x") == "X"


# ---------------------------------------------------------------------------
# _tl_prettify_condition
# ---------------------------------------------------------------------------

class TestPrettifyCondition:
    def test_true_becomes_else(self):
        assert _prettify_c("True") == "else"

    def test_snake_case_var_prettified(self):
        result = _prettify_c("route_id == 'romance'")
        assert "route_id" not in result
        assert "Route Id" in result

    def test_string_literal_value_unquoted(self):
        result = _prettify_c("route_id == 'cold_castle'")
        assert "cold_castle" in result          ## value preserved
        assert "Cold Castle" not in result      ## not prettified
        assert "'" not in result                ## quotes stripped

    def test_string_literal_value_unquoted_double_quotes(self):
        result = _prettify_c('route_id == "cold_castle"')
        assert "cold_castle" in result
        assert '"' not in result                ## quotes stripped

    def test_full_condition_format(self):
        assert _prettify_c("route_id == 'romance'") == "Route Id == romance"

    def test_keyword_not_prettified(self):
        result = _prettify_c("x == 1 and y == 2")
        assert "and" in result

    def test_uppercase_not_prettified(self):
        result = _prettify_c("MyClass == 1")
        assert "MyClass" in result


# ---------------------------------------------------------------------------
# _tl_parse_regions
# ---------------------------------------------------------------------------

class TestParseRegions:
    def test_simple_equality(self):
        result = _parse("x == 'a'")
        assert result == [{"x": frozenset(["a"])}]

    def test_numeric_equality(self):
        result = _parse("x == 1")
        assert result == [{"x": frozenset(["1"])}]

    def test_or_produces_two_regions(self):
        result = _parse("x == 'a' or x == 'b'")
        assert result is not None
        assert len(result) == 2
        assert {"x": frozenset(["a"])} in result
        assert {"x": frozenset(["b"])} in result

    def test_and_merges_region(self):
        result = _parse("x == 'a' and y == 'b'")
        assert result == [{"x": frozenset(["a"]), "y": frozenset(["b"])}]

    def test_non_equality_operator_returns_none(self):
        assert _parse("x > 1") is None

    def test_complex_expression_returns_none(self):
        assert _parse("len(items) > 0") is None

    def test_true_sentinel_returns_none(self):
        assert _parse("True") is None

    def test_else_sentinel_returns_none(self):
        assert _parse("else") is None

    def test_empty_string_returns_none(self):
        assert _parse("") is None

    def test_syntax_error_returns_none(self):
        assert _parse("x ==") is None

    ## Phase 0A: baseline — confirms literal extraction in _tl_parse_regions
    ## before it is refactored to use _tl_extract_compare_literals.
    def test_equality_string_comparator_captured(self):
        result = _parse("route == 'romance'")
        assert result is not None
        assert any("romance" in str(v) for r in result for v in r.values())

    def test_numeric_comparator_captured(self):
        result = _parse("affection == 3")
        assert result is not None
        assert any("3" in str(v) for r in result for v in r.values())


# ---------------------------------------------------------------------------
# _tl_extract_compare_literals  [Phase 0B — fails until tl_ast_utils.rpy created]
# ---------------------------------------------------------------------------

class TestExtractCompareLiterals:
    """
    Tests for _tl_extract_compare_literals(cond_str) -> list[str].

    This function is extracted from _tl_parse_regions and _tl_build_route_index.
    It lives in backend/tl_ast_utils.rpy (created in Step 1).
    These tests FAIL until that file is created.
    """

    def _fn(self):
        assert _extract_compare_literals is not None, (
            "_tl_extract_compare_literals not found — create backend/tl_ast_utils.rpy first"
        )
        return _extract_compare_literals

    def test_equality_string_literal(self):
        fn = self._fn()
        result = fn("route == 'romance'")
        assert "romance" in result

    def test_equality_numeric_literal(self):
        fn = self._fn()
        result = fn("affection == 3")
        assert "3" in result

    def test_greater_than_numeric(self):
        fn = self._fn()
        result = fn("affection > 3")
        assert "3" in result

    def test_compound_and_extracts_both(self):
        fn = self._fn()
        result = fn("route == 'A' and trust >= 2")
        assert "A" in result
        assert "2" in result

    def test_no_compare_node_returns_empty(self):
        fn = self._fn()
        assert fn("flag_seen") == []

    def test_malformed_returns_empty_no_exception(self):
        fn = self._fn()
        assert fn("x ==") == []

    def test_true_sentinel_returns_empty(self):
        fn = self._fn()
        assert fn("True") == []

    def test_else_sentinel_returns_empty(self):
        fn = self._fn()
        assert fn("else") == []

    def test_returns_list(self):
        fn = self._fn()
        assert isinstance(fn("x == 'a'"), list)

    def test_empty_string_returns_empty(self):
        fn = self._fn()
        assert fn("") == []


# ---------------------------------------------------------------------------
# _tl_should_cluster
# ---------------------------------------------------------------------------

class TestShouldCluster:
    def _ghost(self, cond_str):
        regions = _parse(cond_str) or []
        return {"_regions": regions}

    def test_disjoint_values_same_var(self):
        prev = self._ghost("x == 'a'")
        assert _cluster(prev, ["x == 'b'"]) is True

    def test_overlapping_values_no_cluster(self):
        prev = self._ghost("x == 'a'")
        assert _cluster(prev, ["x == 'a'"]) is False

    def test_no_shared_vars_no_cluster(self):
        prev = self._ghost("x == 'a'")
        assert _cluster(prev, ["y == 'b'"]) is False

    def test_no_regions_in_prev_no_cluster(self):
        assert _cluster({"_regions": []}, ["x == 'a'"]) is False

    def test_unparseable_new_cond_no_cluster(self):
        prev = self._ghost("x == 'a'")
        assert _cluster(prev, ["x > 0"]) is False

    def test_true_sentinel_in_new_conds_no_cluster(self):
        prev = self._ghost("x == 'a'")
        assert _cluster(prev, ["True"]) is False


# ---------------------------------------------------------------------------
# _tl_get_taken_branch
# ---------------------------------------------------------------------------

class TestGetTakenBranch:
    def test_first_entry_true_literal(self):
        node = If([("True", []), ("1 == 2", [])])
        assert _taken(node) == 0

    def test_first_true_condition_wins(self):
        node = If([("1 == 1", []), ("2 == 2", [])])
        assert _taken(node) == 0

    def test_second_entry_taken_when_first_false(self):
        node = If([("1 == 2", []), ("1 == 1", [])])
        assert _taken(node) == 1

    def test_all_false_returns_none(self):
        node = If([("1 == 2", []), ("3 == 4", [])])
        assert _taken(node) is None

    def test_empty_entries_returns_none(self):
        node = If([])
        assert _taken(node) is None

    def test_exception_in_eval_returns_none(self):
        node = If([("this is not valid python !!!@#", [])])
        assert _taken(node) is None


# ---------------------------------------------------------------------------
# _tl_branch_exits_before_next
# ---------------------------------------------------------------------------

class TestBranchExitsBeforeNext:
    def test_jump_at_end_returns_true(self):
        assert _exits([Python("x = 1"), Jump("label_a")]) is True

    def test_return_at_end_returns_true(self):
        assert _exits([Python("x = 1"), Return()]) is True

    def test_non_exit_node_returns_false(self):
        assert _exits([Python("x = 1"), Say("mc")]) is False

    def test_empty_block_returns_false(self):
        assert _exits([]) is False

    def test_single_jump_returns_true(self):
        assert _exits([Jump("label_a")]) is True


# ---------------------------------------------------------------------------
# _tl_collect_if_run
# ---------------------------------------------------------------------------

class TestCollectIfRun:
    def _make_if(self, conds, next_node=None):
        entries = [(c, []) for c in conds]
        node = If(entries)
        node.next = next_node
        return node

    def test_single_parseable_if(self):
        node = self._make_if(["x == 'a'", "x == 'b'"])
        run = _collect(node)
        assert len(run) == 1
        assert run[0]["conditions"] == ["x == 'a'", "x == 'b'"]

    def test_chained_parseable_ifs(self):
        node2 = self._make_if(["y == '1'", "y == '2'"])
        node1 = self._make_if(["x == 'a'", "x == 'b'"], next_node=node2)
        run = _collect(node1)
        assert len(run) == 2

    def test_stops_at_non_if_next(self):
        node = self._make_if(["x == 'a'", "x == 'b'"])
        node.next = Say("mc")  # non-If node
        run = _collect(node)
        assert len(run) == 1

    def test_stops_when_payload_is_none(self):
        # Only "True" condition → _tl_build_ghost_payload returns None → stop
        node2 = self._make_if(["True"])
        node1 = self._make_if(["x == 'a'", "x == 'b'"], next_node=node2)
        run = _collect(node1)
        assert len(run) == 1

    def test_run_payload_has_ast_key(self):
        node = self._make_if(["x == 'a'", "x == 'b'"])
        run = _collect(node)
        assert run[0]["ast_key"] == ("test.rpy", 1)

    def test_run_payload_has_affecting_vars(self):
        node = self._make_if(["x == 'a'", "x == 'b'"])
        run = _collect(node)
        assert "x" in run[0]["affecting_vars"]


# ---------------------------------------------------------------------------
# _tl_partition_if_run
# ---------------------------------------------------------------------------

class TestPartitionIfRun:
    def _payload(self, conds, all_exit=False):
        regions = []
        for c in conds:
            r = _parse(c)
            if r:
                regions.extend(r)
        return {
            "conditions": conds,
            "seen_fns": [("never",)] * len(conds),
            "taken_index": 0,
            "affecting_vars": [],
            "branch_imgs": [],
            "branch_img_seqs": [[] for _ in conds],
            "context_img": None,
            "_regions": regions,
            "all_branches_exit": all_exit,
            "ast_key": ("test.rpy", 1),
        }

    def test_empty_run(self):
        assert _partition([]) == []

    def test_single_payload_one_group(self):
        groups = _partition([self._payload(["x == 'a'", "x == 'b'"])])
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_mutually_exclusive_payloads_cluster(self):
        p1 = self._payload(["x == 'a'", "x == 'b'"])
        p2 = self._payload(["x == 'c'"])
        groups = _partition([p1, p2])
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_non_exclusive_payloads_split(self):
        p1 = self._payload(["x == 'a'", "x == 'b'"])
        p2 = self._payload(["y == '1'", "y == '2'"])  # different var — no shared vars → no cluster
        groups = _partition([p1, p2])
        assert len(groups) == 2

    def test_all_branches_exit_forces_cluster(self):
        p1 = self._payload(["y == '1'", "y == '2'"], all_exit=True)
        p2 = self._payload(["z == 'a'", "z == 'b'"], all_exit=True)
        groups = _partition([p1, p2])
        assert len(groups) == 1

# ---------------------------------------------------------------------------
# _tl_notify_branch — notification tier logic
# ---------------------------------------------------------------------------

_notify_branch = ns["_tl_notify_branch"]


class TestNotifyBranch:
    def setup_method(self):
        self._seen_ever_saved       = ns["persistent"]._seen_ever
        self._seen_translates_saved = ns["persistent"]._seen_translates
        self._show_screen_calls = []
        def _capture_show_screen(name, **kwargs):
            self._show_screen_calls.append((name, kwargs))
        ns["renpy"].show_screen = _capture_show_screen
        self._show_screen_saved = ns["renpy"].show_screen
        ns["persistent"]._seen_translates = set()

    def teardown_method(self):
        ns["persistent"]._seen_ever       = self._seen_ever_saved
        ns["persistent"]._seen_translates = self._seen_translates_saved
        ns["renpy"].show_screen = lambda *a, **kw: None

    def _payload(self, seen_fns, taken_index=None):
        return {"seen_fns": seen_fns, "taken_index": taken_index,
                "conditions": [], "affecting_vars": set()}

    def test_all_branches_seen_suppresses(self):
        ns["persistent"]._seen_translates = {"a", "b"}
        run = [self._payload([("say", "a"), ("say", "b")], taken_index=0)]
        _notify_branch(run, 0, pre_taken_seen=True)
        assert self._show_screen_calls == []

    def test_new_path_fires_when_pre_taken_seen_false(self):
        run = [self._payload([("say", "x"), ("say", "y")], taken_index=0)]
        _notify_branch(run, 0, pre_taken_seen=False)
        assert len(self._show_screen_calls) == 1
        assert "New path" in self._show_screen_calls[0][1]["message"]

    def test_icon_only_when_taken_seen_alternative_locked(self):
        ns["persistent"]._seen_translates = {"taken"}
        run = [self._payload([("say", "taken"), ("say", "unseen_alt")], taken_index=0)]
        _notify_branch(run, 0, pre_taken_seen=True)
        assert len(self._show_screen_calls) == 1
        msg = self._show_screen_calls[0][1]["message"]
        assert "New path" not in msg
        assert "⎇" in msg

    def test_standalone_if_not_taken_alternative_locked_fires_icon_only(self):
        ## taken_glob_i=None (unsatisfied standalone if); alternative is locked → ⎇
        run = [self._payload([("say", "locked_branch")], taken_index=None)]
        _notify_branch(run, None, pre_taken_seen=None)
        assert len(self._show_screen_calls) == 1
        assert "⎇" in self._show_screen_calls[0][1]["message"]
        assert "New path" not in self._show_screen_calls[0][1]["message"]

    def test_standalone_if_all_alternatives_seen_suppresses(self):
        ns["persistent"]._seen_translates = {"branch"}
        run = [self._payload([("say", "branch")], taken_index=None)]
        _notify_branch(run, None, pre_taken_seen=None)
        assert self._show_screen_calls == []

    def test_index_based_comparison_correct_branch_excluded(self):
        ## Two branches with identical tuples; only the one at taken_glob_i is excluded.
        ## If comparison were identity-based, equal tuples would both be "not taken".
        sfn = ("say", "shared_name")
        ns["persistent"]._seen_translates = {"shared_name"}
        run = [self._payload([sfn, sfn], taken_index=0)]
        _notify_branch(run, 0, pre_taken_seen=True)
        ## Branch 0 is taken (excluded). Branch 1 has same sfn but IS checked.
        ## seen_translates has the name → both seen → suppress.
        assert self._show_screen_calls == []

    def test_new_path_takes_priority_over_icon_only(self):
        ## pre_taken_seen=False → "New path" returned before ⎇ check
        run = [self._payload([("say", "new"), ("say", "also_unseen")], taken_index=0)]
        _notify_branch(run, 0, pre_taken_seen=False)
        assert len(self._show_screen_calls) == 1
        assert "New path" in self._show_screen_calls[0][1]["message"]


# ---------------------------------------------------------------------------
# _tl_make_seen_fn_cached — seen_fn descriptor cache
# ---------------------------------------------------------------------------

_make_cached = ns["_tl_make_seen_fn_cached"]
_seen_fn_cache = ns["_TL_SEEN_FN_CACHE"]


class TestSeenFnCache:
    def setup_method(self):
        _seen_fn_cache.clear()

    def test_none_block_returns_never(self):
        assert _make_cached(None) == ("never",)

    def test_none_does_not_populate_cache(self):
        _make_cached(None)
        assert len(_seen_fn_cache) == 0

    def test_result_matches_underlying_fn(self):
        blk = [Say("hello world")]
        result = _make_cached(blk)
        expected = ns["_tl_make_seen_fn"](blk)
        assert result == expected

    def test_cache_populated_after_first_call(self):
        blk = [Say("hello")]
        _make_cached(blk)
        key = ns["_tl_builtin_id"](blk)
        assert key in _seen_fn_cache

    def test_underlying_fn_called_only_once_for_same_block(self):
        blk = [Say("hello")]
        call_count = [0]
        orig = ns["_tl_make_seen_fn"]
        def counting_fn(_b):
            call_count[0] += 1
            return orig(_b)
        ns["_tl_make_seen_fn"] = counting_fn
        try:
            _make_cached(blk)
            _make_cached(blk)
            _make_cached(blk)
        finally:
            ns["_tl_make_seen_fn"] = orig
        assert call_count[0] == 1

    def test_different_blocks_get_separate_entries(self):
        blk_a = [Say("path a")]
        blk_b = [Say("path b")]
        _make_cached(blk_a)
        _make_cached(blk_b)
        assert len(_seen_fn_cache) == 2

    def test_same_block_object_returns_cached_value(self):
        blk = [Say("hello")]
        first = _make_cached(blk)
        orig = ns["_tl_make_seen_fn"]
        ns["_tl_make_seen_fn"] = lambda _b: ("poisoned",)
        try:
            second = _make_cached(blk)
        finally:
            ns["_tl_make_seen_fn"] = orig
        assert second == first

    def test_empty_block_returns_never(self):
        blk = []
        result = _make_cached(blk)
        assert result == ("never",)


# ---------------------------------------------------------------------------
# _tl_ghost_ast / _tl_emit_ghost_cluster — persistent AST cache
# ---------------------------------------------------------------------------

_ghost_ast    = ns["_tl_ghost_ast"]
_emit_cluster = ns["_tl_emit_ghost_cluster"]


def _make_group(ast_key, conditions, seen_fns=None, affecting_vars=None):
    """Minimal payload group for _tl_emit_ghost_cluster."""
    return [{
        "ast_key":        ast_key,
        "conditions":     conditions,
        "seen_fns":       seen_fns or [None] * len(conditions),
        "affecting_vars": set(affecting_vars or []),
        "branch_img_seqs": [([], None)] * len(conditions),
        "context_img":    None,
        "_regions":       [],
        "taken_index":    0,
        "all_branches_exit": False,
    }]


class TestGhostNodeCache:
    def setup_method(self):
        # Reset store and persistent between tests.
        ns["store"]._tl_ghost_nodes = []
        ns["persistent"]._tl_ghost_node_cache = {}

    def test_ast_cache_written_after_emit(self):
        group = _make_group(("f.rpy", 10), ["x > 0", "True"])
        _emit_cluster(group, cluster_with_prev=False)
        cache = ns["persistent"]._tl_ghost_node_cache
        assert str(("f.rpy", 10)) in cache

    def test_store_dict_has_only_slim_fields(self):
        group = _make_group(("f.rpy", 20), ["a == 1", "True"])
        _emit_cluster(group, cluster_with_prev=False)
        node = ns["store"]._tl_ghost_nodes[0]
        assert set(node.keys()) == {"ast_key", "taken_index", "branch_imgs", "cluster_with_prev"}

    def test_ghost_ast_returns_correct_data(self):
        group = _make_group(("f.rpy", 30), ["score > 5", "True"], affecting_vars=["score"])
        _emit_cluster(group, cluster_with_prev=False)
        cached = _ghost_ast(("f.rpy", 30))
        assert cached.get("conditions") == ["score > 5", "True"]
        assert "score" in (cached.get("affecting_vars") or [])

    def test_second_emit_same_key_does_not_overwrite(self):
        group = _make_group(("f.rpy", 40), ["y > 0", "True"])
        _emit_cluster(group, cluster_with_prev=False)
        # Mutate the cache entry directly to confirm it is NOT overwritten.
        ns["persistent"]._tl_ghost_node_cache[str(("f.rpy", 40))]["_sentinel"] = True
        _emit_cluster(group, cluster_with_prev=False)
        cached = ns["persistent"]._tl_ghost_node_cache[str(("f.rpy", 40))]
        assert cached.get("_sentinel") is True

