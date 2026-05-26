## =============================================================================
## CHRONOLOGY MOD — tl_coverage.rpy
## Coverage index: collect seen descriptors for all if-branch blocks in the AST.
## =============================================================================

init -2 python:

    def _tl_build_coverage_index(nodes):
        """
        Walk all Label blocks from game scripts and build:
            persistent._tl_all_branch_descs — picklable seen-descriptor tuple per
                if-branch block (all entries including else). Used at render time to
                count globally locked branches via _tl_eval_seen_fn.
        ("never",) descriptors are excluded — unresolvable branches would always
        count as locked and inflate the number permanently.
        """

        _game_file = lambda _f: (
            bool(_f)
            and not (_f or "").startswith("renpy/")
            and "renpy-chronology-mod" not in (_f or "")
        )

        _if_nodes = []
        _visited  = set()

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

                if _nt == "If":
                    _if_nodes.append(_node)
                    for _, _ib in (getattr(_node, "entries", None) or []):
                        if _ib:
                            _work.append(_ib)

                elif _nt == "Menu":
                    for _item in (getattr(_node, "items", None) or []):
                        _ib = _item[2] if isinstance(_item, (list, tuple)) and len(_item) > 2 else None
                        if _ib:
                            _work.append(_ib)

        _branch_descs = []
        for _node in _if_nodes:
            for _cond_str, _block in (getattr(_node, "entries", None) or []):
                if not _block:
                    continue
                _desc = _tl_make_seen_fn(_block)
                if _desc[0] != "never":
                    _branch_descs.append(_desc)

        persistent._tl_all_branch_descs = _branch_descs
        _tl_log("TL coverage index: {} branch descs".format(len(_branch_descs)))