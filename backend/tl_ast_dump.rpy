## =============================================================================
## CHRONOLOGY MOD — timeline_ast_dump.rpy
## CFG AST Dumper — dev-time tool, triggered by dev button.
## Walks renpy.game.script.namemap for the given labels and writes a
## structured JSON that gen_cfg.py (external Python tool) reads to build
## the DOT file.  No .rpy text parsing — uses the live RenPy AST.
## =============================================================================

init -2 python:

    def _tl_cfg_dump_ast(labels=None, outfile=None):
        """
        Dump AST for the given label names to a JSON file.
        If labels is None, dumps ALL labels in the namemap.
        outfile: absolute path; defaults to <moddir>/cfg/full_ast.json
        """
        import renpy.ast as _rast

        _moddir = os.path.join(renpy.config.gamedir, "renpy-chronology-mod")
        if outfile is None:
            outfile = os.path.join(_moddir, "cfg", "full_ast.json")

        _namemap = renpy.game.script.namemap

        if labels is None:
            labels = [
                k for k in _namemap.keys()
                if isinstance(k, str) and not k.startswith("_")
            ]

        def _img_str(stmt):
            imspec = getattr(stmt, "imspec", None)
            if imspec and imspec[0]:
                return " ".join(imspec[0])
            return None

        def _json_safe(val):
            """Recursively convert any Ren'Py AST value to a JSON-safe form."""
            if val is None or isinstance(val, (bool, int, float, str)):
                return val
            if isinstance(val, (list, tuple)):
                _items = list(val)
                ## A flat list of AST nodes is a block — serialize recursively.
                if _items and all(isinstance(_v, _rast.Node) for _v in _items):
                    return _serialize_block(_items)
                return [_json_safe(_v) for _v in _items]
            if isinstance(val, dict):
                return {str(_k): _json_safe(_v) for _k, _v in val.items()}
            if isinstance(val, _rast.Node):
                _n = getattr(val, "name", None)
                if _n is not None:
                    return {"__node__": list(_n)}
                return {"__type__": type(val).__name__}
            ## PyCode and similar objects with .source
            if hasattr(val, "source"):
                return val.source
            try:
                return str(val)
            except Exception:
                return None

        def _serialize_block(stmts):
            """Serialize a list of AST statements generically using Ren'Py's own attributes."""
            out = []
            for s in (stmts or []):
                t = type(s).__name__
                _name = list(s.name) if getattr(s, "name", None) is not None else None
                _next_lbl = _stmt_next_boundary(s)
                ## Dump all instance attributes generically; universal keys win at the end.
                d = {}
                for _a, _v in (vars(s) if hasattr(s, "__dict__") else {}).items():
                    if _a in ("name", "next", "linenumber"):
                        continue
                    try:
                        d[_a] = _json_safe(_v)
                    except Exception:
                        pass
                ## Targeted payload fields needed for formula traversal.
                if isinstance(s, _rast.Jump):
                    d["target"] = getattr(s, "target", None)
                elif isinstance(s, _rast.Call):
                    d["target"] = getattr(s, "label", None)
                elif isinstance(s, _rast.If):
                    d["entries"] = [
                        [str(cond), _serialize_block(block)]
                        for cond, block in (getattr(s, "entries", None) or [])
                    ]
                elif isinstance(s, _rast.Menu):
                    d["items"] = [
                        [text, str(cond) if cond else None, _serialize_block(block) if block else None]
                        for text, cond, block in (getattr(s, "items", None) or [])
                    ]
                elif t in ("Python", "EarlyPython"):
                    d["code"] = getattr(getattr(s, "code", None), "source", None)
                ## Universal keys always set last so they are never overwritten by vars(s).
                d["type"] = t
                d["name"] = _name
                d["linenumber"] = getattr(s, "linenumber", None)
                d["next"] = _next_lbl
                ## UserStatement: append computed screen_jumps for traversal.
                if t == "UserStatement":
                    _us_text = (getattr(s, "line", None) or "").strip()
                    _screen_jumps = []
                    import re as _re_us
                    _sm = _re_us.match(r'^call\s+screen\s+(\w+)', _us_text)
                    if _sm:
                        _sname = _sm.group(1)
                        try:
                            import renpy.display.screen as _rscr
                            _sobj = _rscr.screens.get((_sname, None)) or _rscr.screens.get((_sname,))
                            if _sobj and hasattr(_sobj, "ast"):
                                def _walk_sl_jumps(node):
                                    if node is None:
                                        return
                                    for _kv in (getattr(node, "keyword", None) or []):
                                        if len(_kv) >= 2 and "action" in str(_kv[0]).lower():
                                            _extract_sl_jump(_kv[1])
                                    for _v2 in (getattr(node, "positional", None) or []):
                                        _extract_sl_jump(_v2)
                                    for _an in ("children", "block", "body"):
                                        for _child in (getattr(node, _an, None) or []):
                                            _walk_sl_jumps(_child)
                                    for _entry in (getattr(node, "entries", None) or []):
                                        _eblock = _entry[1] if isinstance(_entry, (list, tuple)) and len(_entry) > 1 else getattr(_entry, "block", None)
                                        for _child in (_eblock or []):
                                            _walk_sl_jumps(_child)
                                def _extract_sl_jump(action):
                                    if hasattr(action, "target") and isinstance(getattr(action, "target", None), str):
                                        _screen_jumps.append(action.target)
                                        return
                                    if isinstance(action, (list, tuple)):
                                        for _a2 in action:
                                            _extract_sl_jump(_a2)
                                        return
                                    try:
                                        _s2 = str(action)
                                        for _m in _re_us.finditer(r'Jump\(["\'](\w+)["\']\)', _s2):
                                            _screen_jumps.append(_m.group(1))
                                    except Exception:
                                        pass
                                _walk_sl_jumps(_sobj.ast)
                        except Exception as _se:
                            _tl_log("TL cfg: screen jump extract failed for '{}': {}".format(_sname, _se))
                    d["screen_jumps"] = _screen_jumps if _screen_jumps else None
                out.append(d)
            return out

        def _find_next_label(node):
            cur = getattr(node, "next", None)
            while cur is not None:
                if isinstance(cur, _rast.Label):
                    return cur.name
                cur = getattr(cur, "next", None)
            return None

        def _stmt_next_boundary(s):
            nxt = getattr(s, "next", None)
            if nxt is None:
                return None
            if isinstance(nxt, _rast.Label):
                return nxt.name          # string  → label entry point
            _nxt_name = getattr(nxt, "name", None)
            if _nxt_name is not None:
                return list(_nxt_name)   # list    → statement node ID [file, serial, line]
            return None                  # no name → treat as in-block sequential

        result = {}

        for lname in labels:
            lnode = _namemap.get(lname)
            if lnode is None:
                _tl_log("TL cfg dump: label '{}' not found in namemap".format(lname))
                continue
            if isinstance(lnode, _rast.Label):
                block = list(getattr(lnode, "block", None) or [])
                if not block:
                    nxt = getattr(lnode, "next", None)
                    if nxt is not None and not isinstance(nxt, _rast.Label):
                        block = [nxt]
            else:
                block = [lnode]
            result[lname] = {
                "file": getattr(lnode, "filename", None),
                "line": getattr(lnode, "linenumber", None),
                "next_label": _find_next_label(lnode),
                "block": _serialize_block(block),
            }
            _tl_log("TL cfg dump: '{}' -> {} stmts".format(lname, len(block)))

        try:
            _outdir = os.path.dirname(outfile)
            if not os.path.exists(_outdir):
                os.makedirs(_outdir)
            with open(outfile, "w") as _f:
                _tl_json.dump(result, _f, indent=2)
            _tl_log("TL cfg dump: written to {}".format(outfile))
        except Exception as _e:
            _tl_log("TL cfg dump error: {}".format(_e))
            renpy.notify("CFG dump failed — see debug.txt")
            return

        _tl_log("TL cfg dump: {} labels written to {}".format(len(result), outfile))
        renpy.notify("CFG dumped: {} labels".format(len(result)))