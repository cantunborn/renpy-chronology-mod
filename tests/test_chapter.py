"""
Tests for tl_chapter_ren.py — chapter dedup, marker existence, rollback, chapter-end slot.
Run: pytest tests/test_chapter.py -v
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _rpy_ns

_tl_dedup_chapters       = _rpy_ns["_tl_dedup_chapters"]
_tl_chapter_marker_exists = _rpy_ns["_tl_chapter_marker_exists"]
_tl_rollback_timeline    = _rpy_ns["_tl_rollback_timeline"]
_tl_chap_end_slot_name   = _rpy_ns["_tl_chap_end_slot_name"]

def make_marker(chapter, after_idx, end_label=None):
    return {
        "chapter_name": chapter,
        "after_index":  after_idx,
        "end_label":    end_label or "{}_end".format(chapter.lower().replace(" ", "_")),
    }


class TestChapterDedup:
    def test_no_duplicates_unchanged(self):
        raw = {"Prologue": "prologue_end", "Chapter 1": "ch1_end"}
        assert _tl_dedup_chapters(raw) == raw

    def test_duplicate_label_first_wins(self):
        # Both chapters map to same label; first occurrence wins
        raw = {"Prologue": "shared_end", "Arc 1": "shared_end"}
        result = _tl_dedup_chapters(raw)
        assert "Prologue" in result
        assert "Arc 1" not in result

    def test_empty_returns_empty(self):
        assert _tl_dedup_chapters({}) == {}

    def test_single_entry(self):
        raw = {"Ch": "ch_end"}
        assert _tl_dedup_chapters(raw) == raw

    def test_three_with_one_duplicate_label(self):
        raw = {"A": "lbl_a", "B": "lbl_b", "C": "lbl_a"}
        result = _tl_dedup_chapters(raw)
        assert len(result) == 2
        assert "A" in result
        assert "C" not in result
        assert "B" in result

    def test_unique_labels_all_kept(self):
        raw = {"X": "x_end", "Y": "y_end", "Z": "z_end"}
        result = _tl_dedup_chapters(raw)
        assert len(result) == 3


class TestChapterMarkerExists:
    def test_exact_match_found(self):
        markers = [make_marker("Prologue", 16, "prologue_end")]
        assert _tl_chapter_marker_exists(markers, "Prologue", 16) is True

    def test_wrong_after_idx_not_found(self):
        markers = [make_marker("Prologue", 16, "prologue_end")]
        assert _tl_chapter_marker_exists(markers, "Prologue", 20) is False

    def test_wrong_chapter_not_found(self):
        markers = [make_marker("Prologue", 16, "prologue_end")]
        assert _tl_chapter_marker_exists(markers, "Chapter 1", 16) is False

    def test_empty_markers_returns_false(self):
        assert _tl_chapter_marker_exists([], "Prologue", 0) is False

    def test_multiple_markers_finds_correct(self):
        markers = [
            make_marker("Prologue", 16, "prologue_end"),
            make_marker("Chapter 1", 30, "ch1_end"),
        ]
        assert _tl_chapter_marker_exists(markers, "Chapter 1", 30) is True
        assert _tl_chapter_marker_exists(markers, "Chapter 1", 16) is False

    def test_after_idx_zero(self):
        markers = [make_marker("Intro", 0, "intro_end")]
        assert _tl_chapter_marker_exists(markers, "Intro", 0) is True


class TestRollbackTimeline:
    def _make_history(self, n):
        return [{"index": i, "options": ["A", "B"]} for i in range(n)]

    def _make_context(self, n):
        return [("Q{}".format(i), 0) for i in range(n)]

    def test_rollback_trims_to_after_index(self):
        chapters = {"Prologue": "prologue_end"}
        markers  = [make_marker("Prologue", 5, "prologue_end")]
        history  = self._make_history(10)
        context  = self._make_context(10)
        h2, c2, m2 = _tl_rollback_timeline(history, context, markers, "prologue_end", chapters)
        assert len(h2) == 5
        assert len(c2) == 5

    def test_rollback_keeps_marker_with_matching_after_idx(self):
        chapters = {"Prologue": "prologue_end"}
        markers  = [make_marker("Prologue", 5, "prologue_end")]
        history  = self._make_history(10)
        context  = self._make_context(10)
        _, _, m2 = _tl_rollback_timeline(history, context, markers, "prologue_end", chapters)
        assert len(m2) == 1
        assert m2[0]["chapter_name"] == "Prologue"

    def test_rollback_drops_later_markers(self):
        chapters = {"Prologue": "prologue_end", "Chapter 1": "ch1_end"}
        markers  = [
            make_marker("Prologue", 5, "prologue_end"),
            make_marker("Chapter 1", 20, "ch1_end"),
        ]
        history = self._make_history(25)
        context = self._make_context(25)
        _, _, m2 = _tl_rollback_timeline(history, context, markers, "prologue_end", chapters)
        names = [m["chapter_name"] for m in m2]
        assert "Prologue" in names
        assert "Chapter 1" not in names

    def test_unknown_label_returns_originals(self):
        chapters = {"Prologue": "prologue_end"}
        markers  = [make_marker("Prologue", 5, "prologue_end")]
        history  = self._make_history(10)
        context  = self._make_context(10)
        h2, c2, m2 = _tl_rollback_timeline(history, context, markers, "no_such_label", chapters)
        assert h2 is history
        assert c2 is context
        assert m2 is markers

    def test_no_marker_returns_originals(self):
        chapters = {"Prologue": "prologue_end"}
        markers  = []   # label registered but no marker recorded yet
        history  = self._make_history(5)
        context  = self._make_context(5)
        h2, c2, m2 = _tl_rollback_timeline(history, context, markers, "prologue_end", chapters)
        assert h2 is history
        assert len(m2) == 0

    def test_rollback_to_zero_empties_history(self):
        chapters = {"Intro": "intro_end"}
        markers  = [make_marker("Intro", 0, "intro_end")]
        history  = self._make_history(8)
        context  = self._make_context(8)
        h2, c2, _ = _tl_rollback_timeline(history, context, markers, "intro_end", chapters)
        assert h2 == []
        assert c2 == []

    def test_empty_chapters_returns_originals(self):
        history = self._make_history(5)
        context = self._make_context(5)
        markers = [make_marker("X", 3, "x_end")]
        h2, c2, m2 = _tl_rollback_timeline(history, context, markers, "x_end", {})
        assert h2 is history

    def test_context_and_history_sliced_consistently(self):
        chapters = {"Ch": "ch_end"}
        markers  = [make_marker("Ch", 3, "ch_end")]
        history  = self._make_history(6)
        context  = self._make_context(6)
        h2, c2, _ = _tl_rollback_timeline(history, context, markers, "ch_end", chapters)
        assert len(h2) == len(c2) == 3


class TestChapEndSlotName:
    def test_basic_label(self):
        assert _tl_chap_end_slot_name("prologue_end") == "_ch_chap_prologue_end"

    def test_prefix(self):
        slot = _tl_chap_end_slot_name("intro_consequences")
        assert slot.startswith("_ch_chap_")

    def test_label_preserved(self):
        slot = _tl_chap_end_slot_name("crown_intro_end")
        assert "crown_intro_end" in slot

    def test_different_labels_different_slots(self):
        assert (_tl_chap_end_slot_name("label_a") !=
                _tl_chap_end_slot_name("label_b"))

    def test_no_spaces_or_special_chars(self):
        slot = _tl_chap_end_slot_name("my_chapter_end")
        assert " " not in slot

    # Hashed form tests
    def test_hashed_same_context_same_slot(self):
        ctx = [("q", 0), ("r", 1)]
        assert (_tl_chap_end_slot_name("ch_end", ctx, 2) ==
                _tl_chap_end_slot_name("ch_end", ctx, 2))

    def test_hashed_different_context_different_slot(self):
        ctx_a = [("q", 0), ("r", 0)]
        ctx_b = [("q", 0), ("r", 1)]
        assert (_tl_chap_end_slot_name("ch_end", ctx_a, 2) !=
                _tl_chap_end_slot_name("ch_end", ctx_b, 2))

    def test_hashed_label_in_slot(self):
        ctx = [("q", 0)]
        slot = _tl_chap_end_slot_name("my_label", ctx, 1)
        assert "my_label" in slot

    def test_hashed_prefix(self):
        ctx = [("q", 0)]
        slot = _tl_chap_end_slot_name("lbl", ctx, 1)
        assert slot.startswith("_ch_chap_lbl_")




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
