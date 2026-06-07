## =============================================================================
## CHRONOLOGY MOD — tl_route_logic.rpy
## Route screen backend: AST index build, var filtering, chip ordering.
## =============================================================================

init -2 python:

    _TL_ROUTE_HIGH_THRESHOLD = 5   ## if_count above this → always show even if consumed

    ## Python 2 (RenPy 7) has a separate unicode type; Python 3 str covers both.
    try:
        _TL_SCALAR_TYPES = (bool, int, float, str, unicode)
    except NameError:
        _TL_SCALAR_TYPES = (bool, int, float, str)

    def _tl_ri_collect_assigned(nodes, domain):
        """
        Phase 1: Walk Python and If nodes via shared block walker.
        Returns (route_vars, numeric_vars, if_nodes).
        Mutates domain in place with assignment literal values.
        """
        import ast
        route_vars   = set()
        numeric_vars = set()
        if_nodes     = []

        def _visitor(node, state, _label=None):
            node_type = type(node).__name__
            if node_type == "Python":
                code = getattr(node, "code", None)
                src  = getattr(code, "source", None) if code else None
                if not src:
                    return state
                try:
                    tree = ast.parse(src, mode="exec")
                except SyntaxError:
                    return state
                for stmt in ast.walk(tree):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name):
                                var_name = target.id
                                if not var_name.startswith("_"):
                                    route_vars.add(var_name)
                                    rhs = stmt.value
                                    ## Arithmetic RHS (var = var + n) → numeric counter
                                    if (isinstance(rhs, ast.BinOp) and
                                            isinstance(rhs.left, ast.Name) and
                                            rhs.left.id == var_name):
                                        numeric_vars.add(var_name)
                                    else:
                                        lit = _tl_ast_literal_value(rhs)
                                        if lit is not None:
                                            domain.setdefault(var_name, set()).add(lit)
                    elif isinstance(stmt, ast.AugAssign):
                        target = stmt.target
                        if isinstance(target, ast.Name):
                            var_name = target.id
                            if not var_name.startswith("_"):
                                route_vars.add(var_name)
                                numeric_vars.add(var_name)   ## += / -= always a counter
            elif node_type == "If":
                if_nodes.append(node)
            return state

        _tl_walk_ast_blocks(nodes, _visitor)
        _tl_log("TL route index: {} assigned vars".format(len(route_vars)))
        return route_vars, numeric_vars, if_nodes


    def _tl_ri_collect_defaults(nodes, route_vars, domain):
        """
        Phase 2: Walk Default nodes, eval bytecode for scalar defaults.
        Mutates route_vars and domain in place.
        Returns defaults dict.
        """
        defaults = {}
        found = 0
        for node in nodes:
            if type(node).__name__ != "Default":
                continue
            found += 1
            var_name   = getattr(node, "varname", None)
            store_attr = getattr(node, "store", "store")
            code       = getattr(node, "code", None)
            bytecode   = getattr(code, "bytecode", None)
            if store_attr != "store":
                if TL_DEBUG_ROUTE:
                    _tl_log("TL default skip {}: store={}".format(var_name, store_attr))
                continue
            if not var_name or var_name.startswith("_"):
                continue
            if bytecode is None:
                if TL_DEBUG_ROUTE:
                    _tl_log("TL default skip {}: bytecode=None code={}".format(var_name, code))
                continue
            try:
                default_val = renpy.python.py_eval_bytecode(bytecode)
                if isinstance(default_val, (bool, int, float, str)):
                    defaults[var_name] = default_val
                elif TL_DEBUG_ROUTE:
                    _tl_log("TL default skip {}: non-scalar type={}".format(var_name, type(default_val).__name__))
            except Exception as e:
                if TL_DEBUG_ROUTE:
                    _tl_log("TL default skip {}: eval error {}".format(var_name, e))
        _tl_log("TL default walk: found {} Default nodes, captured {}".format(found, len(defaults)))
        route_vars.update(defaults.keys())
        for var_name, default_val in defaults.items():
            domain.setdefault(var_name, set()).add(str(default_val))
        return defaults


    def _tl_ri_build_if_counts(if_nodes, route_vars, domain):
        """
        Phase 3: Scan collected If nodes for var references and condition domain literals.
        Counts per If NODE (not per entry): consumed = len(seen_keys) >= if_count.
        Mutates domain in place with condition literal values.
        Returns (if_count, if_key_to_vars).
        """
        import ast
        if_count       = {}
        if_key_to_vars = {}

        for node in if_nodes:
            entries = getattr(node, "entries", None)
            if not entries:
                continue
            ast_key   = (getattr(node, "filename", ""), getattr(node, "linenumber", 0))
            node_vars = set()

            for cond_str, _ in entries:
                cond_str = str(cond_str)
                if cond_str in ("True", "False"):
                    continue
                for var_name in _tl_extract_vars_from_conditions([cond_str]):
                    if var_name in route_vars:
                        node_vars.add(var_name)
                try:
                    cond_tree = ast.parse(cond_str, mode="eval")
                except SyntaxError:
                    cond_tree = None
                if cond_tree:
                    for cnode in ast.walk(cond_tree):
                        if not isinstance(cnode, ast.Compare):
                            continue
                        if not isinstance(cnode.left, ast.Name):
                            continue
                        cond_var = cnode.left.id
                        if cond_var not in route_vars:
                            continue
                        for op, comp in zip(cnode.ops, cnode.comparators):
                            if not isinstance(op, (ast.Eq, ast.NotEq)):
                                continue
                            lit = _tl_ast_literal_value(comp)
                            if lit is not None:
                                domain.setdefault(cond_var, set()).add(lit)

            if node_vars:
                if_key_to_vars[ast_key] = list(node_vars)
                for var_name in node_vars:
                    if_count[var_name] = if_count.get(var_name, 0) + 1

        return if_count, if_key_to_vars


    def _tl_build_route_index(nodes):
        """
        Build the route tracker index from game script AST nodes.
        Three phases: Python/If walk → Default walk → If-count walk.
        Writes results into persistent.
        """
        domain = {}

        route_vars, numeric_vars, if_nodes = _tl_ri_collect_assigned(nodes, domain)
        defaults = _tl_ri_collect_defaults(nodes, route_vars, domain)
        if_count, if_key_to_vars = _tl_ri_build_if_counts(if_nodes, route_vars, domain)

        persistent._tl_route_var_names = list(route_vars)
        persistent._tl_var_defaults    = defaults
        persistent._tl_var_if_count    = if_count
        persistent._tl_if_key_to_vars  = if_key_to_vars
        persistent._tl_var_domain      = {var: sorted(vals) for var, vals in domain.items()}
        persistent._tl_var_is_numeric  = numeric_vars
        _tl_log("TL route index: {} total route vars, {} with if-conditions (max={})".format(
            len(route_vars),
            len(if_count),
            max(if_count.values()) if if_count else 0,
        ))


    def _tl_var_consumed(var_name):
        """True if every If node referencing this var has been executed this session."""
        total = (getattr(persistent, "_tl_var_if_count", None) or {}).get(var_name, 0)
        if total == 0:
            return False
        seen = (getattr(store, "_tl_var_if_seen_keys", None) or {}).get(var_name, set())
        return len(seen) >= total


    def _tl_build_route_chips():
        """
        Return ordered list of (var_name, current_value) chips for the route screen.

        Show/hide rules:
            val is None or non-scalar → hide
            otherwise                 → show

        Ordering:
            1. Ghost vars (in current ghost nodes), by if_count desc
            2. Non-ghost vars, by if_count desc
        """
        var_names   = getattr(persistent, "_tl_route_var_names", None) or []
        if_count    = getattr(persistent, "_tl_var_if_count",    None) or {}
        ghost_nodes = getattr(store, "_tl_ghost_nodes", [])

        ghost_vars = set()
        for ghost in ghost_nodes:
            affecting_vars = _tl_ghost_ast(ghost["ast_key"]).get("affecting_vars") or ghost.get("affecting_vars") or []
            ghost_vars.update(affecting_vars)

        recently_changed = getattr(store, "_tl_recently_changed_vars", None) or set()
        highlighted = ghost_vars | recently_changed

        var_defaults = getattr(persistent, "_tl_var_defaults", None) or {}

        ## Highlighted vars that are in defaults but not in route_var_names get a chip too.
        ## (declared via `default`, only read in conditions, never $-assigned)
        var_name_set = set(var_names)
        extra = [v for v in sorted(highlighted) if v not in var_name_set and v in var_defaults]
        if TL_DEBUG_ROUTE and extra:
            _tl_log("TL chips: highlighted vars added from defaults only: {}".format(extra))
        all_names = list(var_names) + extra

        chips = []
        for name in all_names:
            val = getattr(store, name, None)
            if val is None:
                continue
            if not isinstance(val, _TL_SCALAR_TYPES):
                continue
            if name in var_defaults and val == var_defaults[name] and name not in highlighted:
                continue   ## still at declared default, story hasn't touched it
            chips.append((name, val))

        chips.sort(key=lambda c: (
            0 if c[0] in highlighted else 1,
            -(if_count.get(c[0], 0)),
            c[0],
        ))
        if TL_DEBUG_ROUTE:
            _tl_log("TL route chips: {}/{} vars shown (ghost={} hl={})".format(
                len(chips), len(var_names), len(ghost_vars), len(highlighted)))
        return chips


    def _tl_format_numeric_change(label, old_val, new_val):
        """Format a numeric var change as '↑N Label' or '↓N Label', omitting N when delta is 1."""
        new_val = float(new_val)
        old_val = float(old_val)
        delta = abs(new_val - old_val)
        arrow = "↑" if new_val > old_val else "↓"
        if delta != 1:
            mag = int(delta) if delta == int(delta) else delta
            return arrow + str(mag) + " " + label
        return arrow + " " + label

    def _tl_flush_var_changes():
        """
        Emit one renpy.notify for all accumulated var changes, then clear the dict.
        No-op if nothing is pending.
        """
        if not getattr(persistent, "_tl_var_notifs_enabled", False):
            store._tl_pending_var_changes = {}
            return
        pending = getattr(store, "_tl_pending_var_changes", None) or {}
        if not pending:
            return
        store._tl_pending_var_changes = {}
        numeric_vars = getattr(persistent, "_tl_var_is_numeric", None) or set()
        parts = []
        for var_name in sorted(pending):
            old, new = pending[var_name]
            label = _tl_prettify_var(var_name)
            if var_name in numeric_vars:
                try:
                    parts.append(_tl_format_numeric_change(label, old, new))
                except (ValueError, TypeError):
                    parts.append(label + " → " + _tl_strip_renpy_tags(str(new)))
            else:
                parts.append(label + " → " + _tl_strip_renpy_tags(str(new)))
        if parts:
            lines = [" · ".join(parts[i:i+3]) for i in range(0, len(parts), 3)]
            msg = "\n".join(lines)
            _tl_log("TL var notify: {}".format(msg))
            renpy.show_screen("_tl_notify", message=msg)

    def _tl_flush_menu_snap():
        """
        Emit notifications for vars that were None at menu-present time but now have
        a value — i.e. first assignments made inside a menu arm. Non-init changes are
        already handled immediately by the Python.execute patch.
        """
        if not getattr(persistent, "_tl_var_notifs_enabled", False):
            store._tl_menu_var_snap = None
            return
        snap = getattr(store, "_tl_menu_var_snap", None)
        if snap is None:
            return
        store._tl_menu_var_snap = None
        numeric_vars = getattr(persistent, "_tl_var_is_numeric", None) or set()
        parts = []
        for var_name in sorted(snap):
            old = snap[var_name]
            if old is not None:
                continue   ## non-init — already emitted immediately by Python.execute patch
            new = getattr(store, var_name, None)
            if new is None:
                continue
            recently_changed = getattr(store, "_tl_recently_changed_vars", None)
            if isinstance(recently_changed, set):
                recently_changed.add(var_name)
            label = _tl_prettify_var(var_name)
            if var_name in numeric_vars:
                try:
                    parts.append(_tl_format_numeric_change(label, old or 0, new))
                except (ValueError, TypeError):
                    parts.append(label + " → " + _tl_strip_renpy_tags(str(new)))
            else:
                parts.append(label + " → " + _tl_strip_renpy_tags(str(new)))
        if parts:
            lines = [" · ".join(parts[i:i+3]) for i in range(0, len(parts), 3)]
            msg = "\n".join(lines)
            _tl_log("TL menu_snap notify: {}".format(msg))
            renpy.show_screen("_tl_notify", message=msg)

    ## ── Python.execute patch — route var change detection ────────────────────

    import renpy.ast as _tl_route_renpy_ast

    _tl_route_orig_python_execute = _tl_route_renpy_ast.Python.execute

    def _tl_py_pre_var_snap(node, _cache=[None, None]):
        filename = getattr(node, "filename", None) or ""
        if not _tl_is_game_file(filename):
            return None
        if getattr(persistent, "_tl_replaying", False) or config.skipping:
            return None

        ## hide-mode blocks write to a local dict, not the store — skip
        if getattr(node, "hide", False):
            return None

        ## Intersect this block's co_names with the route var set to find vars to watch.
        ## co_names contains all names referenced by STORE_NAME/LOAD_NAME in exec-mode
        ## bytecode — typically 0–5 names per block vs snapshotting all ~1000+ route vars.
        ## _cache is a function-level mutable default — invisible to Ren'Py rollback/save,
        ## so it survives native rollback and save loads without clearing.
        route_names = getattr(persistent, "_tl_route_var_names", None)
        if route_names is not _cache[0]:
            _cache[0] = route_names
            _cache[1] = frozenset(route_names) if route_names else frozenset()
        route_set = _cache[1]
        bytecode  = getattr(getattr(node, "code", None), "bytecode", None)
        if TL_DEBUG_ROUTE and bytecode is None:
            _tl_log("TL co_names diag: bc=None file={} code_type={}".format(
                filename, type(getattr(node, "code", None)).__name__))
        co_names = set(getattr(bytecode, "co_names", ())) if bytecode else set()
        watch    = route_set & co_names
        if TL_DEBUG_ROUTE and not watch:
            _tl_log("TL co_names miss: file={} rset_size={} cnames={}".format(
                filename, len(route_set), sorted(co_names)[:10]))
        if not watch:
            return None

        if TL_DEBUG_ROUTE:
            _tl_log("TL co_names hit: {} watching={}".format(filename, sorted(watch)))

        return {var_name: getattr(store, var_name, None) for var_name in watch}

    def _tl_py_post_var_diff(snap):
        if not snap:
            return
        notifs_enabled  = getattr(persistent, "_tl_var_notifs_enabled", False)
        recently_changed = getattr(store, "_tl_recently_changed_vars", None)
        pending          = getattr(store, "_tl_pending_var_changes", None) if notifs_enabled else None
        changed = False
        for var_name, old in snap.items():
            new = getattr(store, var_name, None)
            if new == old:
                continue
            ## Tinting — always, independent of notifs flag
            if isinstance(recently_changed, set):
                recently_changed.add(var_name)
            if TL_DEBUG_ROUTE:
                _tl_log("TL co_names change: {} {} → {} (notifs={})".format(var_name, old, new, notifs_enabled))
            ## Pending delta — only when notifs enabled and not an init assignment
            if notifs_enabled and old is not None:
                if not isinstance(pending, dict):
                    pending = {}
                    store._tl_pending_var_changes = pending
                if var_name in pending:
                    pending[var_name] = (pending[var_name][0], new)
                else:
                    pending[var_name] = (old, new)
                changed = True
                if TL_DEBUG_ROUTE:
                    _tl_log("TL var diff: {} {} → {}".format(var_name, old, new))
        if changed:
            _tl_flush_var_changes()

    def _tl_python_execute_patched(self):
        snap = _tl_py_pre_var_snap(self)
        _tl_route_orig_python_execute(self)
        _tl_py_post_var_diff(snap)

    _tl_route_renpy_ast.Python.execute = _tl_python_execute_patched
