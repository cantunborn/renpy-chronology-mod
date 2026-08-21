"""
Tests for tl_menu_options_ren.py — choice entry identity, index resolution, and recording.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns

_tl_choice_entry_for_index         = _rpy_ns["_tl_choice_entry_for_index"]
_tl_choice_index_from_return_value = _rpy_ns["_tl_choice_index_from_return_value"]
_tl_populate_choice_returns        = _rpy_ns["_tl_populate_choice_returns"]
_tl_record_after                   = _rpy_ns["_tl_record_after"]
_tl_valid_choice_entries           = _rpy_ns["_tl_valid_choice_entries"]


class _ChoiceReturn:
    def __init__(self, value, marker=None):
        self.value = value
        self.marker = marker

    def get_chosen(self):
        return self.marker


class _EqValue:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return other == self.value


class TestValidChoiceEntries:
    def test_skips_prompt_entries_and_preserves_order(self):
        items = [("Prompt", None), ("A", object()), ("B", object())]
        entries = _tl_valid_choice_entries(items)
        assert [label for label, _value in entries] == ["A", "B"]


class TestChoiceEntryForIndex:
    def test_uses_valid_option_index_not_label(self):
        first = object()
        second = object()
        items = [("Prompt", None), ("Same", first), ("Same", second)]
        assert _tl_choice_entry_for_index(items, 1) == ("Same", second)

    def test_out_of_range_returns_none(self):
        items = [("Prompt", None), ("Only", object())]
        assert _tl_choice_entry_for_index(items, 5) is None


class TestChoiceIndexFromReturnValue:
    def test_prefers_valid_option_index_with_duplicate_labels(self):
        first = _EqValue("same-result")
        second = _EqValue("same-result")
        items = [("Prompt", None), ("Same", first), ("Same", second)]
        assert _tl_choice_index_from_return_value(items, second) == 1

    def test_matches_choice_return_value_attribute(self):
        items = [("Prompt", None), ("A", _ChoiceReturn("rv-a")), ("B", _ChoiceReturn("rv-b"))]
        assert _tl_choice_index_from_return_value(items, "rv-b") == 1


class TestPopulateChoiceReturns:
    def test_populates_by_valid_index(self):
        first = _ChoiceReturn("rv-a", marker="first")
        second = _ChoiceReturn("rv-b", marker="second")
        node = {"_choice_returns": [None, None]}
        items = [("Prompt", None), ("Same", first), ("Same", second)]
        _tl_populate_choice_returns(node, items)
        assert node["_choice_returns"] == [first, second]


class TestRecordAfter:
    def setup_method(self):
        self._ctx_saved = _rpy_ns["_tl_context"]
        _rpy_ns["_tl_context"] = []

    def teardown_method(self):
        _rpy_ns["_tl_context"] = self._ctx_saved

    def test_prefers_chosen_index_when_labels_repeat(self):
        node = {"index": 0, "prompt": "Hub", "options": ["Same", "Same"], "chosen_index": None}
        _tl_record_after(node, chosen_index=1)
        assert node["chosen_index"] == 1
        assert _rpy_ns["_tl_context"] == [("Hub", 1)]

    def test_legacy_label_fallback_still_works(self):
        node = {"index": 0, "prompt": "Hub", "options": ["A", "B"], "chosen_index": None}
        _tl_record_after(node, chosen_label="B")
        assert node["chosen_index"] == 1
        assert _rpy_ns["_tl_context"] == [("Hub", 1)]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])