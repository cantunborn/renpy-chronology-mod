"""
test_coverage.py — Unit tests for backend/tl_coverage.rpy.

Functions covered:
  _tl_build_coverage_index
"""

import pytest
from conftest import (
    _rpy_ns as ns,
    If, Label, Say, Return, Python,
)

_build_coverage = ns["_tl_build_coverage_index"]


def _descs():
    return getattr(ns["persistent"], "_tl_all_branch_descs", [])


# =============================================================================
# _tl_build_coverage_index
# =============================================================================

class TestBuildCoverageIndex:
    def setup_method(self):
        self._saved = getattr(ns["persistent"], "_tl_all_branch_descs", [])
        ns["persistent"]._tl_all_branch_descs = []

    def teardown_method(self):
        ns["persistent"]._tl_all_branch_descs = self._saved

    # ------------------------------------------------------------------
    # Basic descriptor collection
    # ------------------------------------------------------------------

    def test_single_entry_with_say_produces_one_descriptor(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("route == 'a'", [say])])
        _build_coverage([Label([if_node])])
        assert len(_descs()) == 1

    def test_two_entries_produce_two_descriptors(self):
        say_a = Say("char", identifier="id_a")
        say_b = Say("char", identifier="id_b")
        if_node = If(entries=[
            ("route == 'a'", [say_a]),
            ("True",         [say_b]),
        ])
        _build_coverage([Label([if_node])])
        assert len(_descs()) == 2

    def test_descriptor_is_not_never(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("route == 'a'", [say])])
        _build_coverage([Label([if_node])])
        assert _descs()[0][0] != "never"

    def test_descriptor_is_tuple(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("route == 'a'", [say])])
        _build_coverage([Label([if_node])])
        assert isinstance(_descs()[0], tuple)

    # ------------------------------------------------------------------
    # "never" exclusion
    # ------------------------------------------------------------------

    def test_never_descriptor_excluded(self):
        # Block with only a Return node — _tl_make_seen_fn returns ("never",)
        ret = Return()
        if_node = If(entries=[("route == 'a'", [ret])])
        _build_coverage([Label([if_node])])
        assert len(_descs()) == 0

    def test_empty_block_skipped(self):
        # Empty block list — also skipped before make_seen_fn
        if_node = If(entries=[("route == 'a'", [])])
        _build_coverage([Label([if_node])])
        assert len(_descs()) == 0

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_no_nodes_produces_empty(self):
        _build_coverage([])
        assert _descs() == []

    def test_non_label_nodes_ignored(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("x == 1", [say])])
        # Pass the If node directly (not wrapped in Label) — should be ignored
        _build_coverage([if_node])
        assert _descs() == []

    def test_renpy_internal_file_excluded(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("x == 1", [say])])
        label = Label([if_node])
        label.filename = "renpy/common/00start.rpy"
        _build_coverage([label])
        assert _descs() == []

    def test_mod_file_excluded(self):
        say = Say("char", identifier="id_a")
        if_node = If(entries=[("x == 1", [say])])
        label = Label([if_node])
        label.filename = "game/renpy-chronology-mod/timeline_init.rpy"
        _build_coverage([label])
        assert _descs() == []

    def test_nested_if_inside_if_block(self):
        # If inside another If's block — inner If's descriptors should also appear
        say_inner = Say("char", identifier="id_inner")
        inner_if = If(entries=[("trust > 3", [say_inner])])
        say_outer = Say("char", identifier="id_outer")
        outer_if = If(entries=[("route == 'a'", [say_outer, inner_if])])
        _build_coverage([Label([outer_if])])
        # outer entry + inner entry = 2 descriptors
        assert len(_descs()) == 2

    def test_multiple_labels_accumulate(self):
        say_a = Say("char", identifier="id_a")
        say_b = Say("char", identifier="id_b")
        if_a = If(entries=[("x == 1", [say_a])])
        if_b = If(entries=[("y == 2", [say_b])])
        _build_coverage([Label([if_a]), Label([if_b])])
        assert len(_descs()) == 2