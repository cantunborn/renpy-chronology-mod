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
        import ast as _pyast
        _route_vars   = set()
        _numeric_vars = set()
        _if_nodes     = []

        def _visitor(_node, _state, _label=None):
            _nt = type(_node).__name__
            if _nt == "Python":
                _code = getattr(_node, "code", None)
                _src  = getattr(_code, "source", None) if _code else None
                if not _src:
                    return _state
                try:
                    _tree = _pyast.parse(_src, mode="exec")
                except SyntaxError:
                    return _state
                for _stmt in _pyast.walk(_tree):
                    if isinstance(_stmt, _pyast.Assign):
                        for _t in _stmt.targets:
                            if isinstance(_t, _pyast.Name):
                                _n = _t.id
                                if not _n.startswith("_"):
                                    _route_vars.add(_n)
                                    _rv = _stmt.value
                                    ## Arithmetic RHS (var = var + n) → numeric counter
                                    if (isinstance(_rv, _pyast.BinOp) and
                                            isinstance(_rv.left, _pyast.Name) and
                                            _rv.left.id == _n):
                                        _numeric_vars.add(_n)
                                    else:
                                        _lit = _tl_ast_literal_value(_rv)
                                        if _lit is not None:
                                            domain.setdefault(_n, set()).add(_lit)
                    elif isinstance(_stmt, _pyast.AugAssign):
                        _t = _stmt.target
                        if isinstance(_t, _pyast.Name):
                            _n = _t.id
                            if not _n.startswith("_"):
                                _route_vars.add(_n)
                                _numeric_vars.add(_n)   ## += / -= always a counter
            elif _nt == "If":
                _if_nodes.append(_node)
            return _state

        _tl_walk_ast_blocks(nodes, _visitor)
        _tl_log("TL route index: {} assigned vars".format(len(_route_vars)))
        return _route_vars, _numeric_vars, _if_nodes


    def _tl_ri_collect_defaults(nodes, route_vars, domain):
        """
        Phase 2: Walk Default nodes, eval bytecode for scalar defaults.
        Mutates route_vars and domain in place.
        Returns defaults dict.
        """
        _defaults = {}
        _found = 0
        for _dn in nodes:
            if type(_dn).__name__ != "Default":
                continue
            _found += 1
            _vn = getattr(_dn, "varname", None)
            _store_attr = getattr(_dn, "store", "store")
            _code = getattr(_dn, "code", None)
            _bc = getattr(_code, "bytecode", None)
            if _store_attr != "store":
                if TL_DEBUG_ROUTE:
                    _tl_log("TL default skip {}: store={}".format(_vn, _store_attr))
                continue
            if not _vn or _vn.startswith("_"):
                continue
            if _bc is None:
                _tl_log("TL default skip {}: bytecode=None code={}".format(_vn, _code))
                continue
            try:
                _dv = renpy.python.py_eval_bytecode(_bc)
                if isinstance(_dv, (bool, int, float, str)):
                    _defaults[_vn] = _dv
                elif TL_DEBUG_ROUTE:
                    _tl_log("TL default skip {}: non-scalar type={}".format(_vn, type(_dv).__name__))
            except Exception as _e:
                _tl_log("TL default skip {}: eval error {}".format(_vn, _e))
        _tl_log("TL default walk: found {} Default nodes, captured {}".format(_found, len(_defaults)))
        route_vars.update(_defaults.keys())
        for _vn, _dv in _defaults.items():
            domain.setdefault(_vn, set()).add(str(_dv))
        return _defaults


    def _tl_ri_build_if_counts(if_nodes, route_vars, domain):
        """
        Phase 3: Scan collected If nodes for var references and condition domain literals.
        Counts per If NODE (not per entry): consumed = len(seen_keys) >= if_count.
        Mutates domain in place with condition literal values.
        Returns (if_count, if_key_to_vars).
        """
        import ast as _pyast
        _if_count      = {}
        _if_key_to_vars = {}

        for _node in if_nodes:
            _entries = getattr(_node, "entries", None)
            if not _entries:
                continue
            _ast_key  = (getattr(_node, "filename", ""), getattr(_node, "linenumber", 0))
            _node_vars = set()

            for _cond_str, _block in _entries:
                _cond_s = str(_cond_str)
                if _cond_s in ("True", "False"):
                    continue
                for _v in _tl_extract_vars_from_conditions([_cond_s]):
                    if _v in route_vars:
                        _node_vars.add(_v)
                try:
                    _ctree = _pyast.parse(_cond_s, mode="eval")
                except SyntaxError:
                    _ctree = None
                if _ctree:
                    for _cnode in _pyast.walk(_ctree):
                        if not isinstance(_cnode, _pyast.Compare):
                            continue
                        if not isinstance(_cnode.left, _pyast.Name):
                            continue
                        _cv = _cnode.left.id
                        if _cv not in route_vars:
                            continue
                        for _op, _comp in zip(_cnode.ops, _cnode.comparators):
                            if not isinstance(_op, (_pyast.Eq, _pyast.NotEq)):
                                continue
                            _cl = _tl_ast_literal_value(_comp)
                            if _cl is not None:
                                domain.setdefault(_cv, set()).add(_cl)

            if _node_vars:
                _if_key_to_vars[_ast_key] = list(_node_vars)
                for _v in _node_vars:
                    _if_count[_v] = _if_count.get(_v, 0) + 1

        return _if_count, _if_key_to_vars


    def _tl_build_route_index(nodes):
        """
        Build the route tracker index from game script AST nodes.
        Three phases: Python/If walk → Default walk → If-count walk.
        Writes results into persistent.
        """
        _domain = {}

        _route_vars, _numeric_vars, _if_nodes = _tl_ri_collect_assigned(nodes, _domain)
        _defaults = _tl_ri_collect_defaults(nodes, _route_vars, _domain)
        _if_count, _if_key_to_vars = _tl_ri_build_if_counts(_if_nodes, _route_vars, _domain)

        persistent._tl_route_var_names = list(_route_vars)
        persistent._tl_var_defaults    = _defaults
        persistent._tl_var_if_count    = _if_count
        persistent._tl_if_key_to_vars  = _if_key_to_vars
        persistent._tl_var_domain      = {_v: sorted(_vals) for _v, _vals in _domain.items()}
        persistent._tl_var_is_numeric  = _numeric_vars
        _tl_log("TL route index: {} total route vars, {} with if-conditions (max={})".format(
            len(_route_vars),
            len(_if_count),
            max(_if_count.values()) if _if_count else 0,
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
        for _g in ghost_nodes:
            for _v in (_g.get("affecting_vars") or []):
                ghost_vars.add(_v)

        recently_changed = getattr(store, "_tl_recently_changed_vars", None) or set()
        highlighted = ghost_vars | recently_changed

        var_defaults = getattr(persistent, "_tl_var_defaults", None) or {}

        ## Highlighted vars that are in defaults but not in route_var_names get a chip too.
        ## (declared via `default`, only read in conditions, never $-assigned)
        _var_name_set = set(var_names)
        _extra = [v for v in sorted(highlighted) if v not in _var_name_set and v in var_defaults]
        if TL_DEBUG_ROUTE and _extra:
            _tl_log("TL chips: highlighted vars added from defaults only: {}".format(_extra))
        _all_names = list(var_names) + _extra

        chips = []
        for name in _all_names:
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
        _f_new = float(new_val)
        _f_old = float(old_val)
        _delta = abs(_f_new - _f_old)
        _arrow = "↑" if _f_new > _f_old else "↓"
        if _delta != 1:
            _mag = int(_delta) if _delta == int(_delta) else _delta
            return _arrow + str(_mag) + " " + label
        return _arrow + " " + label

    def _tl_flush_var_changes():
        """
        Emit one renpy.notify for all accumulated var changes, then clear the dict.
        No-op if nothing is pending.
        """
        if not getattr(persistent, "_tl_var_notifs_enabled", False):
            store._tl_pending_var_changes = {}
            return
        _pending = getattr(store, "_tl_pending_var_changes", None) or {}
        if not _pending:
            return
        store._tl_pending_var_changes = {}
        _numeric = getattr(persistent, "_tl_var_is_numeric", None) or set()
        _parts = []
        for _n in sorted(_pending):
            _old, _new = _pending[_n]
            _label = _tl_prettify_var(_n)
            if _n in _numeric:
                try:
                    _parts.append(_tl_format_numeric_change(_label, _old, _new))
                except (ValueError, TypeError):
                    _parts.append(_label + " → " + _tl_strip_renpy_tags(str(_new)))
            else:
                _parts.append(_label + " → " + _tl_strip_renpy_tags(str(_new)))
        if _parts:
            _lines = [" · ".join(_parts[_i:_i+3]) for _i in range(0, len(_parts), 3)]
            _msg = "\n".join(_lines)
            _tl_log("TL var notify: {}".format(_msg))
            renpy.show_screen("_tl_notify", message=_msg)

    def _tl_flush_menu_snap():
        """
        Emit notifications for vars that were None at menu-present time but now have
        a value — i.e. first assignments made inside a menu arm. Non-init changes are
        already handled immediately by the Python.execute patch.
        """
        if not getattr(persistent, "_tl_var_notifs_enabled", False):
            store._tl_menu_var_snap = None
            return
        _snap = getattr(store, "_tl_menu_var_snap", None)
        if _snap is None:
            return
        store._tl_menu_var_snap = None
        _numeric = getattr(persistent, "_tl_var_is_numeric", None) or set()
        _parts = []
        for _n in sorted(_snap):
            _old = _snap[_n]
            if _old is not None:
                continue   ## non-init — already emitted immediately by Python.execute patch
            _new = getattr(store, _n, None)
            if _new is None:
                continue
            _rcv = getattr(store, "_tl_recently_changed_vars", None)
            if isinstance(_rcv, set):
                _rcv.add(_n)
            _label = _tl_prettify_var(_n)
            if _n in _numeric:
                try:
                    _parts.append(_tl_format_numeric_change(_label, _old or 0, _new))
                except (ValueError, TypeError):
                    _parts.append(_label + " → " + _tl_strip_renpy_tags(str(_new)))
            else:
                _parts.append(_label + " → " + _tl_strip_renpy_tags(str(_new)))
        if _parts:
            _lines = [" · ".join(_parts[_i:_i+3]) for _i in range(0, len(_parts), 3)]
            _msg = "\n".join(_lines)
            _tl_log("TL menu_snap notify: {}".format(_msg))
            renpy.show_screen("_tl_notify", message=_msg)

    ## ── Python.execute patch — route var change detection ────────────────────

    import renpy.ast as _tl_route_renpy_ast

    _tl_route_orig_python_execute = _tl_route_renpy_ast.Python.execute

    def _tl_py_pre_var_snap(node, _cache=[None, None]):
        _filename = getattr(node, "filename", None) or ""
        if not (_tl_is_game_file(_filename) and
                getattr(store, "_tl_branch_id", "") and
                not getattr(persistent, "_tl_replaying", False) and
                not config.skipping):
            return None

        ## hide-mode blocks write to a local dict, not the store — skip
        if getattr(node, "hide", False):
            return None

        ## Intersect this block's co_names with the route var set to find vars to watch.
        ## co_names contains all names referenced by STORE_NAME/LOAD_NAME in exec-mode
        ## bytecode — typically 0–5 names per block vs snapshotting all ~1000+ route vars.
        ## _cache is a function-level mutable default — invisible to Ren'Py rollback/save,
        ## so it survives native rollback and save loads without clearing.
        _rnames = getattr(persistent, "_tl_route_var_names", None)
        if _rnames is not _cache[0]:
            _cache[0] = _rnames
            _cache[1] = frozenset(_rnames) if _rnames else frozenset()
        _rset   = _cache[1]
        _bc     = getattr(getattr(node, "code", None), "bytecode", None)
        if TL_DEBUG_ROUTE and _bc is None:
            _tl_log("TL co_names diag: bc=None file={} code_type={}".format(
                _filename, type(getattr(node, "code", None)).__name__))
        _cnames = set(getattr(_bc, "co_names", ())) if _bc else set()
        _watch  = _rset & _cnames
        if TL_DEBUG_ROUTE and not _watch:
            _tl_log("TL co_names miss: file={} rset_size={} cnames={}".format(
                _filename, len(_rset), sorted(_cnames)[:10]))
        if not _watch:
            return None

        if TL_DEBUG_ROUTE:
            _tl_log("TL co_names hit: {} watching={}".format(_filename, sorted(_watch)))

        return {_n: getattr(store, _n, None) for _n in _watch}

    def _tl_py_post_var_diff(snap):
        if not snap:
            return
        _notifs  = getattr(persistent, "_tl_var_notifs_enabled", False)
        _rcv     = getattr(store, "_tl_recently_changed_vars", None)
        _pend    = getattr(store, "_tl_pending_var_changes", None) if _notifs else None
        _changed = False
        for _n, _old in snap.items():
            _new = getattr(store, _n, None)
            if _new == _old:
                continue
            ## Tinting — always, independent of notifs flag
            if isinstance(_rcv, set):
                _rcv.add(_n)
            if TL_DEBUG_ROUTE:
                _tl_log("TL co_names change: {} {} → {} (notifs={})".format(_n, _old, _new, _notifs))
            ## Pending delta — only when notifs enabled and not an init assignment
            if _notifs and _old is not None:
                if not isinstance(_pend, dict):
                    _pend = {}
                    store._tl_pending_var_changes = _pend
                if _n in _pend:
                    _pend[_n] = (_pend[_n][0], _new)
                else:
                    _pend[_n] = (_old, _new)
                _changed = True
                if TL_DEBUG_ROUTE:
                    _tl_log("TL var diff: {} {} → {}".format(_n, _old, _new))
        if _changed:
            _tl_flush_var_changes()

    def _tl_python_execute_patched(self):
        _snap = _tl_py_pre_var_snap(self)
        _tl_route_orig_python_execute(self)
        _tl_py_post_var_diff(_snap)

    _tl_route_renpy_ast.Python.execute = _tl_python_execute_patched
