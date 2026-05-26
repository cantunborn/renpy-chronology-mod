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
"""

import pytest
from conftest import (
    _rpy_ns as ns,
    If, Jump, Return, Say, Scene, Python,
    _renpy as _stub_renpy,
)

_extract    = ns["_tl_extract_vars_from_conditions"]
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
_python_patched = ns["_tl_python_execute_patched"]


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
# _tl_python_execute_patched — filename filter
# ---------------------------------------------------------------------------

class TestPythonExecutePatched:
    def setup_method(self):
        self._orig_calls = []
        self._branch_id_saved = ns.get("_tl_branch_id", "")
        ns["store"]._tl_branch_id = "test_branch_abc"
        ns["persistent"]._tl_replaying = False
        ns["renpy"].config.skipping = False
        self._diff_calls = []
        self._orig_diff = ns["_tl_diff_route_vars"]
        def _capture_diff(snap):
            self._diff_calls.append(snap)
        ns["_tl_diff_route_vars"] = _capture_diff

    def teardown_method(self):
        ns["store"]._tl_branch_id = self._branch_id_saved
        ns["persistent"]._tl_replaying = False
        ns["renpy"].config.skipping = False
        ns["_tl_diff_route_vars"] = self._orig_diff

    def _make_py(self, filename):
        from conftest import Python
        node = Python("x = 1")
        node.filename = filename
        return node

    def test_game_script_diff_called(self):
        ## game script (no renpy/ prefix) with branch_id → diff IS called
        node = self._make_py("game/scripts/intro.rpy")
        _python_patched(node)
        assert len(self._diff_calls) == 1

    def test_game_script_no_game_prefix_diff_called(self):
        ## RenPy stores paths relative to game/ dir — scripts/ prefix with no game/ prefix
        ## is a valid game script (e.g. games that archive scripts in scripts.rpa)
        node = self._make_py("scripts/base/script.rpyc")
        _python_patched(node)
        assert len(self._diff_calls) == 1

    def test_mod_file_bypasses_diff(self):
        ## renpy-chronology-mod in filename → short-circuit, no diff
        node = self._make_py("game/renpy-chronology-mod/backend/tl_ghost_logic.rpy")
        _python_patched(node)
        assert self._diff_calls == []

    def test_non_game_file_bypasses_diff(self):
        ## renpy/ prefix → RenPy internal, short-circuit, no diff
        node = self._make_py("renpy/common/_layout.rpym")
        _python_patched(node)
        assert self._diff_calls == []

    def test_replaying_bypasses_diff(self):
        ns["persistent"]._tl_replaying = True
        node = self._make_py("game/scripts/intro.rpy")
        _python_patched(node)
        assert self._diff_calls == []
