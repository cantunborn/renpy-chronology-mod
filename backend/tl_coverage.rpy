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

        _if_nodes = []

        def _tl_cov_visitor(_node, _state, _label=None):
            if type(_node).__name__ == "If":
                _if_nodes.append(_node)
            return _state

        _tl_walk_ast_blocks(nodes, _tl_cov_visitor)

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