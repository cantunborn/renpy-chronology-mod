"""
Tests for tools/cf_adapter.py — RenpyFlowGraph control-flow adapter.

Each test builds a RenpyFlowGraph from a minimal fixture dict and asserts
adapter methods return exact values. Tests are written against the design in
docs/FORMULA_SOLVER_DESIGN.md § "Traversal Strategy v2". They fail until the
adapter is implemented.

nid format: tuple(stmt["name"]) == (filename, serial, line)
next field:  None | [filename, serial, line] (in-block nid) | str (label name)
"""
import sys
import pytest

sys.path.insert(0, "tools")
from cf_adapter import RenpyFlowGraph  # noqa: E402 — not yet implemented


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def n(serial):
    """Shorthand: nid ("f", serial, serial)."""
    return ("f", serial, serial)


def stmt(serial, type_, **kwargs):
    """Build a minimal stmt dict with a name field."""
    return {"name": ["f", serial, serial], "type": type_, "next": None, **kwargs}


def nxt(serial):
    """next pointer to nid n(serial)."""
    return ["f", serial, serial]


def successors_of(g, serial):
    return g.successors(n(serial))


def predecessors_of(g, serial):
    return g.predecessors(n(serial))


def edge_targets(edges):
    return [nid for nid, _ in edges]


def edge_kinds(edges):
    return [k for _, k in edges]


# ---------------------------------------------------------------------------
# Fixture 1: Straight-line
# ---------------------------------------------------------------------------

STRAIGHT = {
    "main": {
        "block": [
            stmt(1, "Say", next=nxt(2)),
            stmt(2, "Say", next=None),
        ],
        "next_label": None,
    }
}


class TestStraightLine:
    def setup_method(self):
        self.g = RenpyFlowGraph(STRAIGHT, "main")

    def test_label_entry(self):
        assert self.g.label_entry["main"] == n(1)

    def test_n1_successor(self):
        assert successors_of(self.g, 1) == [(n(2), "sequential")]

    def test_n2_no_successors(self):
        assert successors_of(self.g, 2) == []

    def test_n2_predecessor(self):
        assert predecessors_of(self.g, 2) == [(n(1), "sequential")]

    def test_n1_no_predecessors(self):
        assert predecessors_of(self.g, 1) == []

    def test_no_back_edges(self):
        assert not self.g.is_back_edge(n(1), n(2))

    def test_no_cycle_headers(self):
        assert self.g.cycle_headers == set()


# ---------------------------------------------------------------------------
# Fixture 2: If with else (unconditional last arm)
# ---------------------------------------------------------------------------

IF_WITH_ELSE = {
    "main": {
        "block": [
            {
                "name": ["f", 1, 1], "type": "If", "next": nxt(4),
                "entries": [
                    ["x > 0", [stmt(2, "Say", next=nxt(4))]],
                    [None,    [stmt(3, "Say", next=nxt(4))]],
                ],
            },
            stmt(4, "Say", next=None),
        ],
        "next_label": None,
    }
}


class TestIfWithElse:
    def setup_method(self):
        self.g = RenpyFlowGraph(IF_WITH_ELSE, "main")

    def test_if_arm_edges(self):
        succs = successors_of(self.g, 1)
        assert (n(2), "if_arm") in succs
        assert (n(3), "if_arm") in succs

    def test_no_fallthrough_edge(self):
        kinds = edge_kinds(successors_of(self.g, 1))
        assert "if_fallthrough" not in kinds

    def test_post_if_predecessors(self):
        # n(4) is reached from n(2), n(3) via sequential
        preds = edge_targets(predecessors_of(self.g, 4))
        assert n(2) in preds
        assert n(3) in preds

    def test_if_node_has_two_successors(self):
        assert len(successors_of(self.g, 1)) == 2


# ---------------------------------------------------------------------------
# Fixture 3: If without else (fallthrough required)
# ---------------------------------------------------------------------------

IF_WITHOUT_ELSE = {
    "main": {
        "block": [
            {
                "name": ["f", 1, 1], "type": "If", "next": nxt(3),
                "entries": [
                    ["x > 0", [stmt(2, "Say", next=nxt(3))]],
                ],
            },
            stmt(3, "Say", next=None),
        ],
        "next_label": None,
    }
}


class TestIfWithoutElse:
    def setup_method(self):
        self.g = RenpyFlowGraph(IF_WITHOUT_ELSE, "main")

    def test_if_arm_edge(self):
        succs = successors_of(self.g, 1)
        assert (n(2), "if_arm") in succs

    def test_fallthrough_edge_present(self):
        succs = successors_of(self.g, 1)
        assert (n(3), "if_fallthrough") in succs

    def test_if_node_has_two_successors(self):
        assert len(successors_of(self.g, 1)) == 2

    def test_post_if_has_two_predecessors(self):
        # n(3) reached from n(2) sequential and n(1) fallthrough
        preds = predecessors_of(self.g, 3)
        assert len(preds) == 2
        kinds = edge_kinds(preds)
        assert "sequential" in kinds        # from n(2)
        assert "if_fallthrough" in kinds    # from n(1)


# ---------------------------------------------------------------------------
# Fixture 4: Menu
# ---------------------------------------------------------------------------

MENU = {
    "main": {
        "block": [
            {
                "name": ["f", 1, 1], "type": "Menu", "next": nxt(4),
                "items": [
                    ["Option A", "True", [stmt(2, "Say", next=nxt(4))]],
                    ["Option B", "True", [stmt(3, "Say", next=nxt(4))]],
                ],
            },
            stmt(4, "Say", next=None),
        ],
        "next_label": None,
    }
}


class TestMenu:
    def setup_method(self):
        self.g = RenpyFlowGraph(MENU, "main")

    def test_menu_arm_edges(self):
        succs = successors_of(self.g, 1)
        assert (n(2), "menu_arm") in succs
        assert (n(3), "menu_arm") in succs

    def test_no_other_edges_from_menu(self):
        kinds = edge_kinds(successors_of(self.g, 1))
        assert all(k == "menu_arm" for k in kinds)

    def test_menu_has_two_successors(self):
        assert len(successors_of(self.g, 1)) == 2

    def test_post_menu_predecessors(self):
        preds = edge_targets(predecessors_of(self.g, 4))
        assert n(2) in preds
        assert n(3) in preds


# ---------------------------------------------------------------------------
# Fixture 5: Empty arm block
# ---------------------------------------------------------------------------

EMPTY_ARM = {
    "main": {
        "block": [
            {
                "name": ["f", 1, 1], "type": "If", "next": nxt(3),
                "entries": [
                    ["x > 0", [stmt(2, "Say", next=nxt(3))]],
                    [None, []],   # empty else arm
                ],
            },
            stmt(3, "Say", next=None),
        ],
        "next_label": None,
    }
}


class TestEmptyArm:
    def setup_method(self):
        self.g = RenpyFlowGraph(EMPTY_ARM, "main")

    def test_non_empty_arm_edge(self):
        succs = successors_of(self.g, 1)
        assert (n(2), "if_arm") in succs

    def test_empty_arm_deposits_to_post_if(self):
        # Empty else arm has no entry nid — adapter emits edge directly to post-If nid
        succs = successors_of(self.g, 1)
        targets = edge_targets(succs)
        assert n(3) in targets

    def test_empty_arm_edge_kind(self):
        succs = successors_of(self.g, 1)
        kinds = {nid: k for nid, k in succs}
        assert kinds[n(3)] == "if_arm"

    def test_post_if_has_two_predecessors(self):
        # n(3) reached from n(2) sequential AND from If empty-arm edge
        preds = predecessors_of(self.g, 3)
        assert len(preds) == 2


# ---------------------------------------------------------------------------
# Fixture 6: Jump cross-label
# ---------------------------------------------------------------------------

JUMP_CROSS = {
    "main": {
        "block": [
            stmt(1, "Say", next=nxt(2)),
            stmt(2, "Jump", target="other", next=None),
        ],
        "next_label": None,
    },
    "other": {
        "block": [
            stmt(3, "Say", next=None),
        ],
        "next_label": None,
    },
}


class TestJumpCrossLabel:
    def setup_method(self):
        self.g = RenpyFlowGraph(JUMP_CROSS, "main")

    def test_label_entry_other(self):
        assert self.g.label_entry["other"] == n(3)

    def test_jump_successor(self):
        assert successors_of(self.g, 2) == [(n(3), "jump")]

    def test_jump_predecessor(self):
        assert predecessors_of(self.g, 3) == [(n(2), "jump")]

    def test_no_sequential_from_jump(self):
        kinds = edge_kinds(successors_of(self.g, 2))
        assert "sequential" not in kinds


# ---------------------------------------------------------------------------
# Fixture 7: String next (label boundary crossing via next field)
# ---------------------------------------------------------------------------

STRING_NEXT = {
    "main": {
        "block": [
            stmt(1, "Say", next="other"),   # next is a label name string
        ],
        "next_label": None,
    },
    "other": {
        "block": [
            stmt(2, "Say", next=None),
        ],
        "next_label": None,
    },
}


class TestStringNext:
    def setup_method(self):
        self.g = RenpyFlowGraph(STRING_NEXT, "main")

    def test_string_next_resolves_to_label_entry(self):
        assert successors_of(self.g, 1) == [(n(2), "sequential")]

    def test_predecessor_from_string_next(self):
        assert predecessors_of(self.g, 2) == [(n(1), "sequential")]


# ---------------------------------------------------------------------------
# Fixture 8: Call / Return
# ---------------------------------------------------------------------------

CALL_RETURN = {
    "main": {
        "block": [
            stmt(1, "Call", target="sub", next=nxt(2)),
            stmt(2, "Say", next=None),
        ],
        "next_label": None,
    },
    "sub": {
        "block": [
            stmt(3, "Say", next=nxt(4)),
            stmt(4, "Return", next=None),
        ],
        "next_label": None,
    },
}


class TestCallReturn:
    def setup_method(self):
        self.g = RenpyFlowGraph(CALL_RETURN, "main")

    def test_call_successor_is_callee_entry(self):
        assert successors_of(self.g, 1) == [(n(3), "call")]

    def test_return_successor_is_post_call(self):
        assert successors_of(self.g, 4) == [(n(2), "return")]

    def test_post_call_predecessor_is_return(self):
        assert predecessors_of(self.g, 2) == [(n(4), "return")]

    def test_no_sequential_from_call(self):
        # Call does not emit a sequential edge to n(2); only a call edge to callee
        kinds = edge_kinds(successors_of(self.g, 1))
        assert "sequential" not in kinds


# ---------------------------------------------------------------------------
# Fixture 9: Simple cycle (hub)
# ---------------------------------------------------------------------------

SIMPLE_CYCLE = {
    "hub": {
        "block": [
            {
                "name": ["f", 1, 1], "type": "Menu", "next": nxt(4),
                "items": [
                    ["Loop", "True", [stmt(2, "Jump", target="hub", next=None)]],
                    ["Exit", "True", [stmt(3, "Jump", target="end", next=None)]],
                ],
            },
        ],
        "next_label": None,
    },
    "end": {
        "block": [
            stmt(4, "Say", next=None),
        ],
        "next_label": None,
    },
}


class TestSimpleCycle:
    def setup_method(self):
        self.g = RenpyFlowGraph(SIMPLE_CYCLE, "hub")

    def test_hub_nid_is_cycle_header(self):
        assert n(1) in self.g.cycle_headers

    def test_back_edge_detected(self):
        # n(2) jumps to hub entry n(1) — that is a back-edge
        assert self.g.is_back_edge(n(2), n(1))

    def test_forward_edge_not_back_edge(self):
        assert not self.g.is_back_edge(n(1), n(2))

    def test_hub_scc_contains_hub_nid(self):
        assert n(1) in self.g.hub_scc[n(1)]

    def test_hub_scc_contains_back_edge_source(self):
        # n(2) is the jump-back node — inside the SCC
        assert n(2) in self.g.hub_scc[n(1)]

    def test_exit_nid_not_in_hub_scc(self):
        # n(4) is outside the cycle
        assert n(4) not in self.g.hub_scc[n(1)]

    def test_exit_jump_nid_not_in_hub_scc(self):
        # n(3) jumps to "end" — cannot reach hub, not in SCC
        assert n(3) not in self.g.hub_scc[n(1)]


# ---------------------------------------------------------------------------
# Fixture 10: Multi-label cycle (hub → inter_label → hub)
# ---------------------------------------------------------------------------

MULTI_LABEL_CYCLE = {
    "hub": {
        "block": [
            {
                "name": ["f", 1, 1], "type": "Menu", "next": None,
                "items": [
                    ["Loop", "True", [stmt(2, "Jump", target="arm", next=None)]],
                    ["Exit", "True", [stmt(3, "Jump", target="end", next=None)]],
                ],
            },
        ],
        "next_label": None,
    },
    "arm": {
        "block": [
            stmt(4, "Say", next=nxt(5)),
            stmt(5, "Jump", target="hub", next=None),
        ],
        "next_label": None,
    },
    "end": {
        "block": [
            stmt(6, "Say", next=None),
        ],
        "next_label": None,
    },
}


class TestMultiLabelCycle:
    def setup_method(self):
        self.g = RenpyFlowGraph(MULTI_LABEL_CYCLE, "hub")

    def test_hub_nid_is_cycle_header(self):
        assert n(1) in self.g.cycle_headers

    def test_back_edge_is_inter_label_jump(self):
        # n(5) in arm label jumps back to hub — that is the back-edge
        assert self.g.is_back_edge(n(5), n(1))

    def test_hub_scc_contains_inter_label_nids(self):
        scc = self.g.hub_scc[n(1)]
        assert n(4) in scc   # arm body
        assert n(5) in scc   # jump-back in arm

    def test_hub_scc_contains_loop_arm_entry(self):
        # n(2) is reachable from hub and can reach hub via arm
        assert n(2) in self.g.hub_scc[n(1)]

    def test_exit_jump_not_in_hub_scc(self):
        # n(3) jumps to "end" — not in SCC
        assert n(3) not in self.g.hub_scc[n(1)]

    def test_end_label_not_in_hub_scc(self):
        assert n(6) not in self.g.hub_scc[n(1)]

    def test_arm_label_entry(self):
        assert self.g.label_entry["arm"] == n(4)


# ---------------------------------------------------------------------------
# Fixture 11: UserStatement hub (screen_jumps → arm labels, both loop back)
# ---------------------------------------------------------------------------

USERSTATEMENT_HUB = {
    "hub": {
        "block": [
            {
                "name": ["f", 1, 1], "type": "UserStatement",
                "next": None,
                "screen_jumps": ["arm_a", "arm_b"],
            },
        ],
        "next_label": None,
    },
    "arm_a": {
        "block": [
            stmt(2, "Jump", target="hub"),
        ],
        "next_label": None,
    },
    "arm_b": {
        "block": [
            stmt(3, "Jump", target="hub"),
        ],
        "next_label": None,
    },
}


class TestUserStatementHub:
    def setup_method(self):
        self.g = RenpyFlowGraph(USERSTATEMENT_HUB, "hub")

    def test_hub_nid_is_cycle_header(self):
        assert n(1) in self.g.cycle_headers

    def test_back_edge_from_arm_a(self):
        assert self.g.is_back_edge(n(2), n(1))

    def test_back_edge_from_arm_b(self):
        assert self.g.is_back_edge(n(3), n(1))

    def test_hub_scc_contains_hub_nid(self):
        assert n(1) in self.g.hub_scc[n(1)]

    def test_hub_scc_contains_arm_a_jump(self):
        assert n(2) in self.g.hub_scc[n(1)]

    def test_hub_scc_contains_arm_b_jump(self):
        assert n(3) in self.g.hub_scc[n(1)]

    def test_screen_jump_edges_from_hub(self):
        kinds = [k for _, k in self.g.successors(n(1))]
        assert all(k == "screen_jump" for k in kinds)

    def test_hub_has_two_successors(self):
        assert len(self.g.successors(n(1))) == 2


# ---------------------------------------------------------------------------
# Fixture 12: Named empty-block label
# (Ren'Py `menu perk_s:` — label has empty block, next_label points to the
#  actual Menu statement label)
# ---------------------------------------------------------------------------

NAMED_EMPTY_LABEL = {
    "main": {
        "block": [
            stmt(1, "Jump", target="hub_menu"),
        ],
        "next_label": None,
    },
    "hub_menu": {
        "block": [],
        "next_label": "hub_menu_impl",
    },
    "hub_menu_impl": {
        "block": [
            {
                "name": ["f", 2, 2], "type": "Menu", "next": None,
                "items": [
                    ["Option", "True", [stmt(3, "Say", next=None)]],
                ],
            },
        ],
        "next_label": None,
    },
}


class TestNamedEmptyBlockLabel:
    def setup_method(self):
        self.g = RenpyFlowGraph(NAMED_EMPTY_LABEL, "main")

    def test_empty_label_resolves_through_chain(self):
        # hub_menu has no block — label_entry must follow next_label to hub_menu_impl
        assert self.g.label_entry["hub_menu"] == n(2)

    def test_impl_label_entry(self):
        assert self.g.label_entry["hub_menu_impl"] == n(2)

    def test_jump_to_empty_label_reaches_menu(self):
        # Jump n(1) → hub_menu should resolve to n(2), not be dropped
        assert (n(2), "jump") in self.g.successors(n(1))

    def test_menu_is_predecessor_of_option_arm(self):
        assert (n(2), "menu_arm") in self.g.predecessors(n(3))


# ---------------------------------------------------------------------------
# Fixture 13: Nested If inside Menu arm
# ---------------------------------------------------------------------------

NESTED_IF_IN_MENU = {
    "main": {
        "block": [
            {
                "name": ["f", 1, 1], "type": "Menu", "next": nxt(5),
                "items": [
                    ["Option A", "True", [
                        {
                            "name": ["f", 2, 2], "type": "If", "next": nxt(5),
                            "entries": [
                                ["x > 0", [stmt(3, "Say", next=nxt(5))]],
                                [None,    [stmt(4, "Say", next=nxt(5))]],
                            ],
                        }
                    ]],
                    ["Option B", "True", [stmt(6, "Say", next=nxt(5))]],
                ],
            },
            stmt(5, "Say", next=None),
        ],
        "next_label": None,
    }
}


class TestNestedIfInMenuArm:
    def setup_method(self):
        self.g = RenpyFlowGraph(NESTED_IF_IN_MENU, "main")

    def test_menu_arm_to_if(self):
        assert (n(2), "menu_arm") in self.g.successors(n(1))

    def test_menu_arm_to_option_b(self):
        assert (n(6), "menu_arm") in self.g.successors(n(1))

    def test_if_arm_edges(self):
        succs = self.g.successors(n(2))
        assert (n(3), "if_arm") in succs
        assert (n(4), "if_arm") in succs

    def test_no_if_fallthrough(self):
        kinds = [k for _, k in self.g.successors(n(2))]
        assert "if_fallthrough" not in kinds

    def test_inner_arm_reaches_post_menu(self):
        targets = [nid for nid, _ in self.g.successors(n(3))]
        assert n(5) in targets

    def test_post_menu_has_three_predecessors(self):
        # n(3), n(4), n(6) all reach n(5) via sequential
        preds = self.g.predecessors(n(5))
        assert len(preds) == 3

    def test_stmt_at_if_node(self):
        s = self.g.stmt_at[n(2)]
        assert s["type"] == "If"

    def test_stmt_at_inner_say(self):
        s = self.g.stmt_at[n(3)]
        assert s["type"] == "Say"

    def test_stmt_at_menu(self):
        s = self.g.stmt_at[n(1)]
        assert s["type"] == "Menu"


# ---------------------------------------------------------------------------
# Fixture 14: Call with multiple Return paths (if-else inside callee)
# ---------------------------------------------------------------------------

CALL_MULTI_RETURN = {
    "main": {
        "block": [
            stmt(1, "Call", target="sub", next=nxt(2)),
            stmt(2, "Say", next=None),
        ],
        "next_label": None,
    },
    "sub": {
        "block": [
            {
                "name": ["f", 3, 3], "type": "If", "next": None,
                "entries": [
                    ["cond", [stmt(4, "Return", next=None)]],
                    [None,   [stmt(5, "Return", next=None)]],
                ],
            },
        ],
        "next_label": None,
    },
}


class TestCallMultipleReturns:
    def setup_method(self):
        self.g = RenpyFlowGraph(CALL_MULTI_RETURN, "main")

    def test_return_in_if_arm_wired_to_post_call(self):
        assert (n(2), "return") in self.g.successors(n(4))

    def test_return_in_else_arm_wired_to_post_call(self):
        assert (n(2), "return") in self.g.successors(n(5))

    def test_post_call_has_two_return_predecessors(self):
        preds = self.g.predecessors(n(2))
        return_preds = [(src, k) for src, k in preds if k == "return"]
        assert len(return_preds) == 2

    def test_post_call_predecessor_nids(self):
        src_nids = {src for src, _ in self.g.predecessors(n(2))}
        assert n(4) in src_nids
        assert n(5) in src_nids


# ---------------------------------------------------------------------------
# stmt_at — spot checks across fixtures
# ---------------------------------------------------------------------------

class TestStmtAt:
    def test_straight_line_all_nids_in_stmt_at(self):
        g = RenpyFlowGraph(STRAIGHT, "main")
        assert n(1) in g.stmt_at
        assert n(2) in g.stmt_at

    def test_stmt_type_correct(self):
        g = RenpyFlowGraph(STRAIGHT, "main")
        assert g.stmt_at[n(1)]["type"] == "Say"

    def test_jump_node_in_stmt_at(self):
        g = RenpyFlowGraph(JUMP_CROSS, "main")
        assert g.stmt_at[n(2)]["type"] == "Jump"

    def test_menu_node_in_stmt_at(self):
        g = RenpyFlowGraph(MENU, "main")
        assert g.stmt_at[n(1)]["type"] == "Menu"

    def test_return_node_in_stmt_at(self):
        g = RenpyFlowGraph(CALL_RETURN, "main")
        assert g.stmt_at[n(4)]["type"] == "Return"

    def test_hub_nid_in_stmt_at(self):
        g = RenpyFlowGraph(SIMPLE_CYCLE, "hub")
        assert n(1) in g.stmt_at
        assert g.stmt_at[n(1)]["type"] == "Menu"