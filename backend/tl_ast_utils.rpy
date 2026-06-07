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
            tree = _tl_pyast_util.parse(cond_str, mode="eval")
        except SyntaxError:
            return []
        results = []
        for compare_node in _tl_pyast_util.walk(tree):
            if not isinstance(compare_node, _tl_pyast_util.Compare):
                continue
            for comparator in compare_node.comparators:
                val = _tl_ast_literal_value(comparator)
                if val is not None:
                    results.append(val)
        return results

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
        visited = set()
        work = []

        for label_node in nodes:
            if type(label_node).__name__ != "Label":
                continue
            if not _tl_is_game_file(getattr(label_node, "filename", "")):
                continue
            label_block = getattr(label_node, "block", None)
            if label_block:
                work.append((list(label_block) if not isinstance(label_block, list) else label_block, initial_state, label_node.name))

        while work:
            block, state, cur_label = work.pop()
            for node in (block or []):
                node_id = _tl_builtin_id(node)
                if node_id in visited:
                    continue
                visited.add(node_id)
                state = visitor_fn(node, state, cur_label)

                node_type = type(node).__name__
                if node_type == "If":
                    for _, item_block in (getattr(node, "entries", None) or []):
                        if item_block:
                            work.append((item_block, state, cur_label))
                elif node_type == "Menu":
                    for item in (getattr(node, "items", None) or []):
                        item_block = item[2] if isinstance(item, (list, tuple)) and len(item) > 2 else None
                        if item_block:
                            work.append((item_block, state, cur_label))

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
