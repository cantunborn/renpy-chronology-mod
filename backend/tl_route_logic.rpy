## =============================================================================
## CHRONOLOGY MOD — tl_route_logic.rpy
## Route screen backend: AST index build, var filtering, chip ordering.
## =============================================================================

init -2 python:

    _TL_ROUTE_HIGH_THRESHOLD = 5   ## if_count above this → always show even if consumed

    def _tl_build_route_index(nodes):
        """
        Walk all If and Python nodes from game scripts and build:
            persistent._tl_route_var_names  — vars assigned anywhere (for chip display)
            persistent._tl_var_if_count     — total If-entries referencing each var
            store._tl_var_seen_descs        — seen descriptors per var (rebuilt each session)
        """
        import ast as _pyast

        _game_file = lambda _f: (
            (_f or "").startswith("game/")
            and "renpy-chronology-mod" not in (_f or "")
        )

        ## ── Full iterative block walk from Label entry points ─────────────────
        ## Covers all nodes including anonymous ones inside If/Menu arm blocks
        ## that are not in namemap. Work queue holds blocks (lists of AST nodes).
        _route_vars   = set()
        _numeric_vars = set()   ## vars assigned via arithmetic (+=, var = var + n)
        _if_nodes     = []      ## game If nodes collected for the second pass
        _visited      = set()   ## object ids to avoid re-visiting shared nodes
        _domain       = {}      ## {var_name: set(str(literal_values))}

        _work = []
        for _ln in nodes:
            if type(_ln).__name__ != "Label":
                continue
            if not _game_file(getattr(_ln, "filename", "")):
                continue
            _lb = getattr(_ln, "block", None)
            if _lb:
                _work.append(list(_lb) if not isinstance(_lb, list) else _lb)

        while _work:
            _block = _work.pop()
            for _node in (_block or []):
                _nid = _tl_builtin_id(_node)
                if _nid in _visited:
                    continue
                _visited.add(_nid)
                _nt = type(_node).__name__

                if _nt == "Python":
                    _code = getattr(_node, "code", None)
                    _src  = getattr(_code, "source", None) if _code else None
                    if _src:
                        try:
                            _tree = _pyast.parse(_src, mode="exec")
                        except SyntaxError:
                            _tree = None
                        if _tree:
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
                                                    _lit = (
                                                        _rv.s if isinstance(_rv, _pyast.Str) else
                                                        _rv.n if isinstance(_rv, _pyast.Num) else
                                                        _rv.value if isinstance(_rv, _pyast.Constant) else
                                                        None
                                                    )
                                                    if _lit is not None:
                                                        _domain.setdefault(_n, set()).add(str(_lit))
                                elif isinstance(_stmt, _pyast.AugAssign):
                                    _t = _stmt.target
                                    if isinstance(_t, _pyast.Name):
                                        _n = _t.id
                                        if not _n.startswith("_"):
                                            _route_vars.add(_n)
                                            _numeric_vars.add(_n)   ## += / -= always a counter

                elif _nt == "If":
                    _if_nodes.append(_node)
                    for _, _ib in (getattr(_node, "entries", None) or []):
                        if _ib:
                            _work.append(_ib)

                elif _nt == "Menu":
                    for _item in (getattr(_node, "items", None) or []):
                        _ib = _item[2] if isinstance(_item, (list, tuple)) and len(_item) > 2 else None
                        if _ib:
                            _work.append(_ib)

        persistent._tl_route_var_names = list(_route_vars)
        _tl_log("TL route index: {} assigned vars".format(len(_route_vars)))

        ## ── Default node walk — capture declared default values ───────────────
        ## `default varname = expr` creates a Default AST node with .varname and
        ## .code.bytecode. We eval the bytecode to get the actual default value.
        ## Only store-namespace defaults; skips vars starting with _.
        _defaults = {}
        for _dn in nodes:
            if type(_dn).__name__ != "Default":
                continue
            if getattr(_dn, "store", "store") != "store":
                continue
            _vn = getattr(_dn, "varname", None)
            if not _vn or _vn.startswith("_"):
                continue
            _bc = getattr(getattr(_dn, "code", None), "bytecode", None)
            if _bc is None:
                continue
            try:
                _dv = renpy.python.py_eval_bytecode(_bc)
            except Exception:
                continue
            if isinstance(_dv, (bool, int, float, str)):
                _defaults[_vn] = _dv
        store._tl_var_defaults = _defaults
        _tl_log("TL route index: {} scalar default values captured".format(len(_defaults)))

        ## ── If-node condition walk (uses nodes collected above) ───────────────
        ## Counts per If NODE (not per entry) so the runtime seen-key set can be
        ## compared directly: consumed = len(seen_keys) >= if_count.
        _if_count      = {}   ## {var_name: int} — number of distinct If nodes referencing it
        _if_key_to_vars = {}  ## {(filename, linenumber): [var_name, ...]} — reverse map

        for _node in _if_nodes:
            _entries = getattr(_node, "entries", None)
            if not _entries:
                continue
            _ast_key  = (getattr(_node, "filename", ""), getattr(_node, "linenumber", 0))
            _node_vars = set()   ## vars referenced by any entry of this node

            for _cond_str, _block in _entries:
                _cond_s = str(_cond_str)
                if _cond_s in ("True", "False"):
                    continue
                _vars = _tl_extract_vars_from_conditions([_cond_s])
                for _v in _vars:
                    if _v not in _route_vars:
                        continue
                    _node_vars.add(_v)

                ## Collect literal values from equality comparisons for domain
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
                        if _cv not in _route_vars:
                            continue
                        for _op, _comp in zip(_cnode.ops, _cnode.comparators):
                            if not isinstance(_op, (_pyast.Eq, _pyast.NotEq)):
                                continue
                            _cl = (
                                _comp.s if isinstance(_comp, _pyast.Str) else
                                _comp.n if isinstance(_comp, _pyast.Num) else
                                _comp.value if isinstance(_comp, _pyast.Constant) else
                                None
                            )
                            if _cl is not None:
                                _domain.setdefault(_cv, set()).add(str(_cl))

            ## One count per If node per var (not per entry)
            if _node_vars:
                _if_key_to_vars[_ast_key] = list(_node_vars)
                for _v in _node_vars:
                    _if_count[_v] = _if_count.get(_v, 0) + 1

        persistent._tl_var_if_count    = _if_count
        persistent._tl_if_key_to_vars  = _if_key_to_vars
        persistent._tl_var_domain      = {_v: sorted(_vals) for _v, _vals in _domain.items()}
        persistent._tl_var_is_numeric  = _numeric_vars
        _tl_log("TL route index: {} vars with if-conditions (max={})".format(
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

        var_defaults = getattr(store, "_tl_var_defaults", None) or {}

        chips = []
        for name in var_names:
            val = getattr(store, name, None)
            if val is None:
                continue
            if not isinstance(val, (bool, int, float, str)):
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


    def _tl_snapshot_route_vars():
        """Return current store values for all known route vars."""
        return {
            _n: getattr(store, _n, None)
            for _n in (getattr(persistent, "_tl_route_var_names", None) or [])
        }

    def _tl_diff_route_vars(snap):
        """
        Compare current store values against snap and accumulate changes into
        store._tl_pending_var_changes.  Skips inits (old was None) and unchanged vars.
        Preserves original old value if a var is already pending from an earlier block.
        """
        _pending = getattr(store, "_tl_pending_var_changes", None)
        if _pending is None:
            _pending = {}
            store._tl_pending_var_changes = _pending
        for _n, _old in snap.items():
            if _old is None:
                continue   ## skip inits — var didn't exist before this block
            _new = getattr(store, _n, None)
            if _new == _old:
                continue
            if _n in _pending:
                _pending[_n] = (_pending[_n][0], _new)   ## keep original old, update new
            else:
                _pending[_n] = (_old, _new)
            if TL_DEBUG_ROUTE:
                _tl_log("TL var diff: {} {} → {}".format(_n, _old, _new))
            _rcv = getattr(store, "_tl_recently_changed_vars", None)
            if isinstance(_rcv, set):
                _rcv.add(_n)

    def _tl_format_numeric_change(label, old_val, new_val):
        """Format a numeric var change as '↑N Label' or '↓N Label', omitting N when delta is 1."""
        _f_new = float(new_val)
        _f_old = float(old_val)
        _delta = abs(_f_new - _f_old)
        _arrow = "{font=DejaVuSans.ttf}↑{/font}" if _f_new > _f_old else "{font=DejaVuSans.ttf}↓{/font}"
        if _delta != 1:
            _mag = int(_delta) if _delta == int(_delta) else _delta
            return _arrow + str(_mag) + " " + label
        return _arrow + " " + label

    def _tl_flush_var_changes():
        """
        Emit one renpy.notify for all accumulated var changes, then clear the dict.
        No-op if nothing is pending.
        """
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
                    _parts.append(_label + " {font=DejaVuSans.ttf}→{/font} " + str(_new))
            else:
                _parts.append(_label + " {font=DejaVuSans.ttf}→{/font} " + str(_new))
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
                    _parts.append(_label + " {font=DejaVuSans.ttf}→{/font} " + str(_new))
            else:
                _parts.append(_label + " {font=DejaVuSans.ttf}→{/font} " + str(_new))
        if _parts:
            _lines = [" · ".join(_parts[_i:_i+3]) for _i in range(0, len(_parts), 3)]
            _msg = "\n".join(_lines)
            _tl_log("TL menu_snap notify: {}".format(_msg))
            renpy.show_screen("_tl_notify", message=_msg)
