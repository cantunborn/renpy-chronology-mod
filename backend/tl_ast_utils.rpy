## =============================================================================
## CHRONOLOGY MOD — tl_ast_utils.rpy
## Shared AST utilities used across multiple backend files.
## Loads before all other tl_*.rpy backend files (alphabetical sort at init -2).
## =============================================================================

init -2 python:

    import ast as _tl_pyast_util
    import re as _tl_re_util
    _tl_pyast_Constant_util = getattr(_tl_pyast_util, "Constant", None)

    def _tl_strip_renpy_tags(s):
        """Strip {tag} markup from s, leaving inner text."""
        return _tl_re_util.sub(r'\{[^}]*\}', '', s)

    def _tl_ast_literal_value(node):
        """
        Return the string value of an AST literal node (Python 2/3 compat).
        Handles Constant (Py 3.8+), Str, Num (Py 2/3), and True/False Names.
        Returns None if the node is not a recognized literal.
        """
        if _tl_pyast_Constant_util and isinstance(node, _tl_pyast_Constant_util):
            return str(node.value)
        if isinstance(node, _tl_pyast_util.Str):
            return str(node.s)
        if isinstance(node, _tl_pyast_util.Num):
            return str(node.n)
        if isinstance(node, _tl_pyast_util.Name) and node.id in ("True", "False"):
            return node.id
        return None

    def _tl_extract_compare_literals(cond_str):
        """
        Parse cond_str and return all comparator literal values (as strings)
        from Compare nodes. Works across all comparison operators (==, !=, >, <, etc.).
        Returns [] on parse error or if the string has no Compare nodes.
        """
        if not cond_str or cond_str in ("True", "False", "None", "else"):
            return []
        try:
            _tree = _tl_pyast_util.parse(cond_str, mode="eval")
        except SyntaxError:
            return []
        _results = []
        for _cnode in _tl_pyast_util.walk(_tree):
            if not isinstance(_cnode, _tl_pyast_util.Compare):
                continue
            for _comp in _cnode.comparators:
                _val = _tl_ast_literal_value(_comp)
                if _val is not None:
                    _results.append(_val)
        return _results

    def _tl_is_game_file(f):
        """
        True if f is a game script path — not a RenPy internal and not this mod.
        RenPy stores filenames relative to game/; internals start with 'renpy/'.
        All mod files (including timeline_*.rpy) live under renpy-chronology-mod/
        so the mod-dir check covers them too.
        Single canonical check: update here when the mod directory name changes.
        """
        return (
            bool(f)
            and not f.startswith("renpy/")
            and "renpy-chronology-mod" not in f
        )

    def _tl_walk_ast_blocks(nodes, visitor_fn, initial_state=None):
        """
        Walk all Label node blocks from game scripts, visiting every nested node.
        Recurses into If entries and Menu item blocks.
        Already-seen nodes (by identity) are skipped to prevent cycles.

        visitor_fn(node, state, current_label) -> new_state is called once per unique
        visited node. current_label is the name of the Label node whose block contains
        this node (propagates unchanged into If/Menu sub-blocks).
        State is threaded sequentially through each block; child blocks inherit the
        state at the point the branch is reached.
        initial_state defaults to None for stateless visitors (return state unchanged).
        """
        _visited = set()
        _work = []

        for _ln in nodes:
            if type(_ln).__name__ != "Label":
                continue
            if not _tl_is_game_file(getattr(_ln, "filename", "")):
                continue
            _lb = getattr(_ln, "block", None)
            if _lb:
                _work.append((list(_lb) if not isinstance(_lb, list) else _lb, initial_state, _ln.name))

        while _work:
            _block, _state, _cur_label = _work.pop()
            for _node in (_block or []):
                _nid = _tl_builtin_id(_node)
                if _nid in _visited:
                    continue
                _visited.add(_nid)
                _state = visitor_fn(_node, _state, _cur_label)

                _nt = type(_node).__name__
                if _nt == "If":
                    for _, _ib in (getattr(_node, "entries", None) or []):
                        if _ib:
                            _work.append((_ib, _state, _cur_label))
                elif _nt == "Menu":
                    for _item in (getattr(_node, "items", None) or []):
                        _ib = _item[2] if isinstance(_item, (list, tuple)) and len(_item) > 2 else None
                        if _ib:
                            _work.append((_ib, _state, _cur_label))

    def _tl_prettify_var(name):
        """Convert a snake_case variable name to a readable label."""
        _STRIP_PREFIXES = ("mc_", "flag_", "is_", "has_", "ch_")
        s = name
        for pfx in _STRIP_PREFIXES:
            if s.startswith(pfx):
                s = s[len(pfx):]
                break
        parts = s.split("_")
        return " ".join(p.capitalize() for p in parts if p)
