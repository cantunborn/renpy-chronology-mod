"""
conftest.py — Ren'Py stub + .rpy loader for unit tests.

Replaces the manually-maintained _latest.py files.
The Ren'Py stub is installed into sys.modules before any test file is imported,
so .rpy files can be exec'd directly without modification.
"""

import os
import re
import sys
import types
import textwrap
import hashlib

# ---------------------------------------------------------------------------
# Ren'Py stub — installed before any test imports
# ---------------------------------------------------------------------------

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _noop(*a, **kw):
    pass

# persistent stub
_persistent = types.SimpleNamespace(
    _tl_replaying=False,
    _tl_thumb_cache={},
    _tl_asset_thumb_cache={},
    _tl_img_movie_cache={},
    _tl_menu_scene_map={},
    _tl_scene_map_version=3,
    _tl_recovery_slot=None,
    _seen_ever={},
    _seen_translates=set(),
    _chosen={},
    # route tracker keys
    _tl_route_var_names=[],
    _tl_var_if_count={},
    _tl_if_key_to_vars={},
    _tl_var_domain={},
    _tl_var_is_numeric=set(),
    _tl_var_defaults={},
    _tl_ghost_node_cache={},
)

# store stub — wraps persistent for attribute delegation
_store = types.SimpleNamespace()
_store.persistent = _persistent

# renpy stub
_renpy = types.ModuleType("renpy")
_renpy.config = types.SimpleNamespace(
    gamedir=_root,
    savedir=_root,
    skipping=False,
    game_main_transition=None,
    save_directory="saves",
    start_callbacks=[],
    after_load_callbacks=[],
    interact_callbacks=[],
    label_callbacks=[],
    statement_callbacks=[],
    quit_callbacks=[],
)
class _TranslatorStub:
    """Minimal translator stub for seen-check tests."""
    def __init__(self):
        self._map = {}   # {identifier: TranslateSay-like object}

    def lookup_translate(self, identifier):
        return self._map.get(identifier)

_renpy.game = types.SimpleNamespace(
    script=types.SimpleNamespace(
        namemap={},
        translator=_TranslatorStub(),
    ),
    context=lambda: types.SimpleNamespace(
        scene_lists=types.SimpleNamespace(layers={})
    ),
)
_renpy.python = types.SimpleNamespace(py_eval=eval)
_store.menu = None
_renpy.store = _store
_renpy.exports = types.SimpleNamespace(menu=None)
_renpy.save = _noop
_renpy.load = _noop
_renpy.notify = _noop
_renpy.show_screen = _noop
_renpy.save_persistent = _noop
_renpy.seen_label = lambda label: False
_renpy.seen_translation = lambda tlid: tlid in (_persistent._seen_translates or set())
_renpy.screenshot_to_bytes = lambda *a, **kw: b""
_renpy.loadable = lambda f: False
_renpy.version_tuple = (8, 1, 3, 0, 0)

# renpy.display sub-stub — enough for tl_assets_ren.py to load
import threading as _threading
_renpy.display = types.SimpleNamespace(
    im=types.SimpleNamespace(Data=None),
    image=types.SimpleNamespace(images={}),
    pgrender=types.SimpleNamespace(
        load_image=lambda *a, **kw: None,
        surface=lambda *a, **kw: None,
    ),
    render=types.SimpleNamespace(blit_lock=_threading.Lock()),
    scale=types.SimpleNamespace(smoothscale=lambda *a, **kw: None),
)

sys.modules.setdefault("renpy", _renpy)
sys.modules.setdefault("renpy.python", _renpy.python)

# Make store/persistent available at module level (some .rpy code reads
# them as bare names via Ren'Py's implicit store injection).
_STUB_GLOBALS = {
    "renpy":      _renpy,
    "store":      _store,
    "persistent": _persistent,
    "config":     _renpy.config,
    "_tl_log":    _noop,
}


# ---------------------------------------------------------------------------
# .rpy loader
# ---------------------------------------------------------------------------

def load_rpy(rel_path, ns=None):
    """
    Exec all `init [priority] python:` blocks from a .rpy file into ns.

    rel_path is relative to the project root (renpy-chronology-mod/).
    Returns the namespace dict.
    """
    if ns is None:
        ns = {}
    ns.update(_STUB_GLOBALS)
    ns.setdefault("__builtins__", __builtins__)

    abs_path = os.path.join(_root, rel_path)
    src = open(abs_path, encoding="utf-8").read()

    if rel_path.endswith("_ren.py"):
        # Already plain Python (the """renpy ... """ marker is an inert string
        # statement) — exec the whole file directly, no extraction needed.
        exec(compile(src, abs_path, "exec"), ns)
        return ns

    # Match `init [±N] python:` blocks; capture indented body (including blank lines).
    pattern = re.compile(
        r'^init(?:\s+-?\d+)?\s+python:\s*\n'
        r'((?:(?:    [^\n]*|[ \t]*)\n)*)',
        re.MULTILINE,
    )
    for m in pattern.finditer(src):
        block = m.group(1)
        code = textwrap.dedent(block)
        exec(compile(code, abs_path, "exec"), ns)

    return ns


# ---------------------------------------------------------------------------
# Ren'Py AST node stubs (test infrastructure — not production code)
# ---------------------------------------------------------------------------

class _TLNode:
    """Minimal stub for a Ren'Py AST node."""
    def __init__(self, ntype, **kwargs):
        self._ntype = ntype
        self.__dict__.update(kwargs)
        if "next" not in self.__dict__:
            self.next = None

class Python(_TLNode):
    def __init__(self, source):
        super().__init__("Python")
        class _Code:
            pass
        self.code = _Code()
        self.code.source = source
        try:
            self.code.bytecode = compile(source, "<test>", "exec")
        except Exception:
            self.code.bytecode = None
    def execute(self):
        pass

class Jump(_TLNode):
    def __init__(self, target):
        super().__init__("Jump")
        self.target = target

class Call(_TLNode):
    def __init__(self, label):
        super().__init__("Call")
        self.label = label

class Menu(_TLNode):
    def __init__(self, items=None):
        super().__init__("Menu")
        self.filename = "test.rpy"
        self.linenumber = 1
        self.items = items or []

class Scene(_TLNode):
    def __init__(self):
        super().__init__("Scene")

class Show(_TLNode):
    def __init__(self, *name_parts):
        super().__init__("Show")
        if name_parts:
            self.imspec = (list(name_parts),)

class Say(_TLNode):
    def __init__(self, name, identifier=None):
        super().__init__("Say")
        self.name = name
        self.identifier = identifier

class TranslateSay(_TLNode):
    def __init__(self, name, identifier=None):
        super().__init__("TranslateSay")
        self.name = name
        self.identifier = identifier

class Return(_TLNode):
    def __init__(self):
        super().__init__("Return")

class If(_TLNode):
    def __init__(self, entries=None):
        super().__init__("If")
        self.entries = entries or []  # [(cond_str, [nodes]), ...]
        self.filename = "test.rpy"
        self.linenumber = 1
    def execute(self):
        pass

class Label(_TLNode):
    def __init__(self, block, name="test_label"):
        super().__init__("Label")
        self.block = block
        self.name = name
        self.filename = "test.rpy"
        self.linenumber = 1

# Aliases for test imports
_TLPythonNode      = Python
_TLJumpNode        = Jump
_TLCallNode        = Call
_TLMenuNode        = Menu
_TLSceneNode       = Scene
_TLSayNode         = Say
_TLTranslateSayNode = TranslateSay
_TLReturnNode      = Return
_TLIfNode          = If
_TLLabelNode       = Label

# renpy.ast stub — must come after If is defined; used by tl_ghost_logic_ren.py
_renpy_ast_mod = types.ModuleType("renpy.ast")
_renpy_ast_mod.If = If
_renpy_ast_mod.Python = Python
_renpy.ast = _renpy_ast_mod
sys.modules.setdefault("renpy.ast", _renpy_ast_mod)


# ---------------------------------------------------------------------------
# Shared production namespace — all backend feature files loaded in order
# ---------------------------------------------------------------------------

_rpy_ns = {}
for _f in [
    "backend/tl_ast_utils_ren.py",
    "backend/tl_chapter_ren.py",
    "backend/tl_menu_location_ren.py",
    "backend/tl_menu_options_ren.py",
    "backend/tl_shadow_path_ren.py",
    "backend/tl_seen_check_ren.py",
    "backend/tl_saveload_ren.py",
    "backend/tl_assets_ren.py",
    "backend/tl_ghost_logic_ren.py",
    "backend/tl_route_logic_ren.py",
    "backend/tl_coverage_ren.py",
    "backend/tl_snapshot_cache_ren.py",
    "timeline_init_ren.py",
]:
    load_rpy(_f, _rpy_ns)

# Globals that timeline_init_ren.py sets via `default` (not in init python: blocks)
_rpy_ns.setdefault("_tl_history", [])
_rpy_ns.setdefault("_tl_context", [])
_rpy_ns.setdefault("_tl_ghost_nodes", [])
_rpy_ns.setdefault("_tl_pending_var_changes", {})
_rpy_ns.setdefault("_tl_recently_changed_vars", set())
_rpy_ns.setdefault("_tl_menu_var_snap", None)
_rpy_ns.setdefault("_tl_var_if_seen_keys", {})
_rpy_ns.setdefault("_tl_var_defaults", {})

load_rpy("timeline_hooks_ren.py", _rpy_ns)


# ---------------------------------------------------------------------------
# Test-only helpers (not in production .rpy files)
# ---------------------------------------------------------------------------

import ast as _tl_python_ast

def _tl_validate_history(history):
    """Extracted from _tl_validate_on_load for unit testing."""
    if not isinstance(history, list):
        return []
    clean = []
    for node in history:
        if (isinstance(node, dict)
                and "index" in node
                and "options" in node
                and isinstance(node["options"], list)):
            clean.append(node)
    for i, node in enumerate(clean):
        node["index"] = i
    return clean

def _tl_node_thumb(node, cache):
    """Return thumbnail bytes for a node: from the node itself or the persistent cache."""
    b = node.get("thumb_bytes")
    if b:
        return b
    key = str(node["ast_key"]) if node.get("ast_key") else None
    return cache.get(key) if key else None

def _tl_extract_var_deltas_from_source(src):
    """Testable helper: extract var deltas from a Python source string."""
    from conftest import _rpy_ns as _ns
    _op = _ns["_tl_op_symbol"]
    _vs = _ns["_tl_val_str"]
    _nb = _ns["_tl_normalize_binop_assign"]
    deltas = []
    if not src:
        return deltas
    try:
        tree = _tl_python_ast.parse(src.strip(), mode="exec")
        for stmt in tree.body:
            if isinstance(stmt, _tl_python_ast.AugAssign):
                name = getattr(stmt.target, "id", None)
                if name:
                    deltas.append((name, _op(type(stmt.op).__name__), _vs(stmt.value)))
            elif isinstance(stmt, _tl_python_ast.Assign):
                for t in stmt.targets:
                    name = getattr(t, "id", None)
                    if name:
                        norm = _nb(name, stmt.value)
                        if norm:
                            deltas.append(norm)
                        else:
                            deltas.append((name, "=", _vs(stmt.value)))
    except Exception:
        pass
    return deltas

_TL_CMP_MAP = {"Eq": "==", "NotEq": "!=", "Gt": ">", "GtE": ">=", "Lt": "<", "LtE": "<="}

def _tl_literal_str_test(node):
    ntype = type(node).__name__
    if ntype == "Constant": return repr(node.value)
    if ntype == "Num": return repr(node.n)
    if ntype == "Str": return repr(node.s)
    return None

def _tl_walk_compare(node, result):
    ntype = type(node).__name__
    if ntype == "BoolOp":
        for value in node.values:
            _tl_walk_compare(value, result)
    elif ntype == "Compare" and len(node.ops) == 1:
        lhs = getattr(node.left, "id", None)
        if lhs and lhs[0].islower():
            cmp_str = _TL_CMP_MAP.get(type(node.ops[0]).__name__)
            rhs_val = _tl_literal_str_test(node.comparators[0])
            if cmp_str and rhs_val is not None and lhs not in result:
                result[lhs] = (cmp_str, rhs_val)

def _tl_extract_condition_values(conditions):
    result = {}
    for cond in conditions:
        if cond in ("True", "False", "None"):
            continue
        try:
            tree = _tl_python_ast.parse(cond, mode="eval")
            _tl_walk_compare(tree.body, result)
        except Exception:
            pass
    return result

def _tl_delta_satisfies(op, delta_val, cmp, required_val):
    if op != "=": return True
    if cmp is None or cmp == "any": return True
    try:
        dv, rv = int(delta_val), int(required_val)
    except (ValueError, TypeError):
        dv = str(delta_val).strip("'\"")
        rv = str(required_val).strip("'\"") if required_val is not None else None
    if rv is None: return True
    return {"==": dv==rv, "!=": dv!=rv, ">": dv>rv, ">=": dv>=rv, "<": dv<rv, "<=": dv<=rv}.get(cmp, True)

def _tl_build_var_setters(data):
    result = {}
    for ast_key, opts in data.items():
        for opt_idx, opt_deltas in enumerate(opts):
            for vname, op, val in opt_deltas:
                result.setdefault(vname, []).append((ast_key, opt_idx, op, val))
    return result

