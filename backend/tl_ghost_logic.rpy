## =============================================================================
## CHRONOLOGY MOD — timeline_ghost_logic.rpy
## Ghost card runtime logic: If-node hook, payload building, clustering.
## =============================================================================

init -2 python:

    import ast as _tl_ast_mod

    def _collect_branch_imgs(block, max_images=5):
        """
        Collect up to max_images Scene/Show images from a branch block.
        Tier 1: flat block scan. Tier 2: follow first Jump/Call one hop.
        Returns (images, visited_labels) where images is [(img_str, source_label)].
        source_label is None for images from the direct block, label name for hop images.
        """
        collected = []
        visited = set()
        if not block:
            return collected, visited

        ## Tier 1: flat block scan
        for node in block:
            if len(collected) >= max_images:
                break
            t = type(node).__name__
            if t in ("Scene", "Show"):
                sp = getattr(node, "imspec", None)
                if sp and sp[0] and tuple(sp[0]) in renpy.display.image.images:
                    collected.append((" ".join(sp[0]), None))

        ## Tier 2: follow first Jump or Call one hop
        if len(collected) < max_images:
            try:
                _nm = renpy.game.script.namemap
                for node in block:
                    if type(node).__name__ in ("Jump", "Call"):
                        _target = getattr(node, "target", None)
                        if not _target:
                            continue
                        _ln = _nm.get(_target)
                        _sub = getattr(_ln, "block", None)
                        if _sub:
                            visited.add(_target)
                            ## Walk .next chain — covers all sequential scenes in
                            ## the label, not just the flat block list.
                            ## Stop at Label nodes to avoid crossing into the next label.
                            _snode = _sub[0]
                            _walked = 0
                            while _snode is not None and len(collected) < max_images:
                                _stype = type(_snode).__name__
                                if _stype == "Label":
                                    break
                                if _stype in ("Scene", "Show"):
                                    sp = getattr(_snode, "imspec", None)
                                    if sp and sp[0] and tuple(sp[0]) in renpy.display.image.images:
                                        collected.append((" ".join(sp[0]), _target))
                                _snode = getattr(_snode, "next", None)
                                _walked += 1
                            if TL_DEBUG_GHOST:
                                _tl_log("TL collect_branch_imgs hop {}: walked={} imgs={}".format(
                                    _target, _walked, [i for i, _ in collected]))
                        break  ## one hop only
            except Exception as _e:
                _tl_log("TL collect_branch_imgs hop failed: {}".format(_e))

        return collected, visited


init python:
    import renpy.ast as _tl_renpy_ast
    _tl_orig_if_execute = _tl_renpy_ast.If.execute

    ## seen_fn descriptor cache: _tl_builtin_id(branch_block) → seen_fn tuple.
    ## Branch block objects are stable Python objects for the session lifetime
    ## (RenPy AST is built once at startup and never replaced). Module-level dict
    ## is invisible to the rollback system — correct, since AST doesn't change on
    ## rollback. Not persistent — descriptors are session-derived from AST.
    _TL_SEEN_FN_CACHE = {}

    def _tl_ghost_ast(ast_key):
        """Return persistent AST-derived data for a ghost cluster by its ast_key."""
        return (persistent._tl_ghost_node_cache or {}).get(str(ast_key)) or {}

    def _tl_make_seen_fn_cached(_blk):
        if _blk is None:
            return ("never",)
        _key = _tl_builtin_id(_blk)
        if _key not in _TL_SEEN_FN_CACHE:
            _TL_SEEN_FN_CACHE[_key] = _tl_make_seen_fn(_blk)
        return _TL_SEEN_FN_CACHE[_key]

    ## ── Var / condition helpers (restored from deleted tl_var_delta.rpy) ─────

    import re as _tl_re

    _TL_VAR_RE     = _tl_re.compile(r'\b([a-z_][a-z0-9_]*)\b(?!\s*\()')
    _TL_STR_LIT_RE = _tl_re.compile(r'"[^"]*"|\'[^\']*\'')
    _TL_KW_SKIP    = frozenset([
        "and","or","not","in","is","True","False","None",
        "if","else","elif","return","renpy","store","persistent",
        "len","range","int","str","float","bool","list","dict","set",
    ])

    ## _tl_prettify_var — defined in tl_ast_utils.rpy (loads before this file)

    def _tl_extract_vars_from_conditions(conditions):
        """Return the set of game-variable names referenced across all condition strings."""
        import ast as _ast
        out = set()
        for cond in conditions:
            if cond in ("True", "False", "None"):
                continue
            try:
                tree = _ast.parse(cond, mode="eval")
            except SyntaxError:
                continue
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Name):
                    name = node.id
                    if name not in _TL_KW_SKIP and not name[0].isupper():
                        out.add(name)
        return out

    ## ── Mutual exclusivity clustering ────────────────────────────────────────

    def _tl_parse_regions(cond_str):
        """
        Parse a condition string to DNF regions for mutual exclusivity checks.
        A region is a dict {var: frozenset({val, ...})}.
        Returns a list of region dicts, or None if the condition can't be parsed
        (non-equality operators, complex expressions) — caller treats None as
        'unknown, don't cluster'.
        """
        if not cond_str or cond_str in ("True", "else", ""):
            return None
        try:
            tree = _tl_ast_mod.parse(cond_str, mode="eval")
        except SyntaxError:
            return None

        def _node_to_regions(n):
            if isinstance(n, _tl_ast_mod.BoolOp):
                if isinstance(n.op, _tl_ast_mod.Or):
                    result = []
                    for v in n.values:
                        r = _node_to_regions(v)
                        if r is None:
                            return None
                        result.extend(r)
                    return result
                elif isinstance(n.op, _tl_ast_mod.And):
                    result = [{}]
                    for v in n.values:
                        r = _node_to_regions(v)
                        if r is None:
                            return None
                        new_result = []
                        for existing in result:
                            for clause in r:
                                merged = dict(existing)
                                ok = True
                                for var, vals in clause.items():
                                    if var in merged:
                                        combined = merged[var] & vals
                                        if not combined:
                                            ok = False
                                            break
                                        merged[var] = combined
                                    else:
                                        merged[var] = vals
                                if ok:
                                    new_result.append(merged)
                        result = new_result
                    return result if result else None
            elif isinstance(n, _tl_ast_mod.Compare):
                if (len(n.ops) == 1 and isinstance(n.ops[0], _tl_ast_mod.Eq) and
                        isinstance(n.left, _tl_ast_mod.Name)):
                    var = n.left.id
                    comp = n.comparators[0]
                    _lit = _tl_ast_literal_value(comp)
                    if _lit is not None:
                        return [{var: frozenset([_lit])}]
            return None

        return _node_to_regions(tree.body)

    def _tl_should_cluster(prev_ghost, new_conds):
        """
        Returns True if new_conds are mutually exclusive with prev_ghost's conditions —
        safe to group into the same visual cluster (no │ separator).

        Two condition sets are mutually exclusive when every pair of regions (one from
        each set) is disjoint. Two regions are disjoint when at least one shared variable
        has non-overlapping value sets. If they share no variables, they are NOT disjoint
        (could both be true simultaneously) — no clustering.
        """
        prev_regions = _tl_ghost_ast(prev_ghost.get("ast_key")).get("_regions") or prev_ghost.get("_regions")
        if not prev_regions:
            return False

        new_regions = []
        for cond in new_conds:
            if cond in ("True", "else", ""):
                continue
            r = _tl_parse_regions(cond)
            if r is None:
                if TL_DEBUG_GHOST:
                    _tl_log("TL cluster: parse failed for '{}' → no cluster".format(cond))
                return False
            new_regions.extend(r)
        if not new_regions:
            return False

        for ra in prev_regions:
            for rb in new_regions:
                shared_vars = set(ra) & set(rb)
                if not shared_vars:
                    if TL_DEBUG_GHOST:
                        _tl_log("TL cluster: no shared vars {} vs {} → no cluster".format(
                            set(ra), set(rb)))
                    return False
                overlap = all(ra[v] & rb[v] for v in shared_vars)
                if overlap:
                    if TL_DEBUG_GHOST:
                        _tl_log("TL cluster: regions overlap {} & {} → no cluster".format(
                            dict(ra), dict(rb)))
                    return False

        if TL_DEBUG_GHOST:
            _tl_log("TL cluster: all regions disjoint → cluster with prev")
        return True

    def _tl_branch_exits_before_next(block):
        """
        Return True when a taken branch clearly exits before sibling ifs can run.
        Minimal runtime heuristic: explicit Jump/Return at the end of the branch.
        """
        if not block:
            return False
        _last = block[-1]
        return type(_last).__name__ in ("Jump", "Return")

    def _tl_extend_ghost_rows(
            ghost, ast_key, conditions, seen_fns, branch_imgs,
            regions, affecting_vars=None):
        """Append hidden sibling-if rows into an existing ghost card."""
        ghost["conditions"] = list(ghost.get("conditions") or []) + list(conditions or [])
        ghost["seen_fns"] = list(ghost.get("seen_fns") or []) + list(seen_fns or [])
        ghost["branch_imgs"] = list(ghost.get("branch_imgs") or []) + list(branch_imgs or [])
        ghost["_regions"] = list(ghost.get("_regions") or []) + list(regions or [])
        if affecting_vars:
            ghost["affecting_vars"] = sorted(set(ghost.get("affecting_vars") or []) | set(affecting_vars))
        ghost.setdefault("member_ast_keys", []).append(ast_key)
        return ghost

    def _tl_prettify_condition(cond):
        """Prettify var names and strip quotes from string values; numeric values left as-is."""
        if cond == "True":
            return "else"
        try:
            import ast as _ast
            _tree = _ast.parse(cond, mode="eval")
            _repls = []
            for _node in _ast.walk(_tree):
                if isinstance(_node, _ast.Name):
                    _n = _node.id
                    if _n not in _TL_KW_SKIP and not _n[0].isupper():
                        _col = _node.col_offset
                        _repls.append((_col, _col + len(_n), _tl_prettify_var(_n)))
                elif isinstance(_node, _ast.Constant) and isinstance(_node.value, str):
                    _repls.append((_node.col_offset, _node.end_col_offset, str(_node.value)))
            _repls.sort(key=lambda x: x[0], reverse=True)
            _result = cond
            for _s, _e, _pretty in _repls:
                _result = _result[:_s] + _pretty + _result[_e:]
            return _tl_strip_renpy_tags(_result)
        except Exception:
            def _repl(m):
                name = m.group(1)
                if name in _TL_KW_SKIP or name[0].isupper():
                    return name
                return _tl_prettify_var(name)
            return _tl_strip_renpy_tags(
                _TL_VAR_RE.sub(_repl, _TL_STR_LIT_RE.sub(lambda m: m.group(0), cond))
            )

    ## ── If-node ghost tracking ───────────────────────────────────────────────
    ## Monkey-patch renpy.ast.If.execute so we can record branch conditions
    ## in real time as the game evaluates them.  taken_index is evaluated BEFORE
    ## calling the original so condition state is unaffected by branch side-effects.

    def _tl_get_taken_branch(if_node):
        """Evaluate conditions in order and return index of first True one."""
        try:
            for _i, (_cond, _blk) in enumerate(if_node.entries):
                _cond_s = str(_cond)
                if _cond_s == "True":
                    return _i
                if renpy.python.py_eval(_cond_s):
                    return _i
        except Exception:
            pass
        return None

    def _tl_build_ghost_payload(if_node, taken_index, context_img=None):
        """Build one ghost payload dict for a single If node."""
        entries = getattr(if_node, "entries", None)
        if not entries:
            return None

        conditions = [str(e[0]) for e in entries]
        if conditions == ["True"]:
            return None

        affecting_vars = _tl_extract_vars_from_conditions(conditions)
        if not affecting_vars and any(c not in ("True", "False", "None") for c in conditions):
            _tl_log("TL ghost payload: no vars extracted from conditions={} key=({},{})".format(
                conditions,
                getattr(if_node, "filename", "?"),
                getattr(if_node, "linenumber", "?")))

        ## branch_imgs resolved cluster-wide in _tl_collect_if_run after payload build
        branch_imgs = []

        regions = []
        for _cond in conditions:
            if _cond in ("True", "else", ""):
                continue
            _r = _tl_parse_regions(_cond)
            if _r is not None:
                regions.extend(_r)
            else:
                regions = None
                break
        if TL_DEBUG_GHOST:
            _tl_log("TL ghost _regions: {}".format(
                len(regions) if regions is not None else "None"))

        seen_fns = []
        for _cond, _blk in entries:
            seen_fns.append(_tl_make_seen_fn_cached(_blk))

        return {
            "ast_key":        (if_node.filename, if_node.linenumber),
            "conditions":     conditions,
            "seen_fns":       seen_fns,
            "taken_index":    taken_index,
            "affecting_vars": list(affecting_vars),
            "branch_imgs":    branch_imgs,
            "_regions":       regions,
        }

    def _tl_resolve_cluster_imgs(if_node, context_img):
        """
        Resolve per-branch thumbnail images for one If node using cross-branch
        comparison. Prefers the first image that distinguishes a branch from its
        siblings. Falls back to first image in sequence, or context_img for
        dialogue-only (empty) branches.
        """
        entries = getattr(if_node, "entries", [])
        ## Collect (images, visited_labels) per branch
        per_branch = []
        for _cond, _blk in entries:
            _imgs, _vis = _collect_branch_imgs(_blk) if _blk else ([], set())
            per_branch.append((_imgs, _vis))

        ## Convergence truncation: images from labels visited by ALL branches
        ## are post-convergence — drop them so we only diff the unique portion.
        _all_vis = [_vis for _, _vis in per_branch if _vis]
        if len(_all_vis) >= 2:
            _shared = set.intersection(*[set(_v) for _v in _all_vis])
            per_branch = [
                ([_item for _item in _imgs if _item[1] not in _shared], _vis)
                for _imgs, _vis in per_branch
            ]

        ## Build per-branch image sets for sibling comparison
        _all_img_sets = [set(_img for _img, _ in _imgs) for _imgs, _ in per_branch]

        result = []
        for _bi, (_imgs, _) in enumerate(per_branch):
            if not _imgs:
                result.append(context_img)
                continue
            _sibling_imgs = set().union(*(
                _all_img_sets[_j] for _j in range(len(per_branch)) if _j != _bi
            ))
            ## First image unique to this branch; fall back to first image if all shared
            _chosen = next((_img for _img, _ in _imgs if _img not in _sibling_imgs), None)
            result.append(_chosen or _imgs[0][0])
        if TL_DEBUG_GHOST:
            _tl_log("TL ghost cluster_imgs: {}".format(result))
        return result

    def _tl_collect_if_run(start_if_node):
        """Collect a sequential run of player-relevant sibling If nodes."""
        _context_img = _tl_resolve_live_menu_img_name()
        run = []
        _node = start_if_node
        while _node is not None and isinstance(_node, _tl_renpy_ast.If):
            _payload = _tl_build_ghost_payload(_node, _tl_get_taken_branch(_node), _context_img)
            if _payload is None:
                break
            run.append((_payload, _node))
            _node = getattr(_node, "next", None)
        ## Collect raw image sequences per branch; selection deferred to
        ## _tl_emit_ghost_cluster so cross-payload differentiation is possible.
        for _payload, _if_node in run:
            _entries = getattr(_if_node, "entries", [])
            _seqs = []
            for _cond, _blk in _entries:
                _imgs, _vis = _collect_branch_imgs(_blk) if _blk else ([], set())
                _seqs.append((_imgs, _vis))
            _payload["branch_img_seqs"] = _seqs
            _payload["context_img"] = _context_img
            _payload["all_branches_exit"] = all(
                _tl_branch_exits_before_next(_blk)
                for _, _blk in _entries if _blk
            )
        return [_p for _p, _ in run]

    def _tl_partition_if_run(run):
        """Partition a sequential If run into mutually-exclusive cluster components."""
        if not run:
            return []
        _groups = []
        _current = [run[0]]
        for _payload in run[1:]:
            _prev = {"_regions": []}
            for _m in _current:
                _prev["_regions"].extend(_m.get("_regions") or [])
            _jump_cluster = (
                _payload.get("all_branches_exit") and
                all(_p.get("all_branches_exit") for _p in _current)
            )
            if _tl_should_cluster(_prev, _payload.get("conditions") or []) or _jump_cluster:
                _current.append(_payload)
            else:
                _groups.append(_current)
                _current = [_payload]
        _groups.append(_current)
        return _groups

    def _tl_emit_ghost_cluster(group, cluster_with_prev):
        """Emit one ghost-card object from a clustered group of If payloads."""
        if not group:
            return
        conditions = []
        seen_fns = []
        branch_imgs = []
        affecting_vars = set()
        regions = []
        member_ast_keys = []
        taken_index = None
        row_offset = 0
        _all_seqs = []
        _context_img = None

        for _payload in group:
            member_ast_keys.append(_payload["ast_key"])
            conditions.extend(_payload.get("conditions") or [])
            seen_fns.extend(_payload.get("seen_fns") or [])
            _all_seqs.extend(_payload.get("branch_img_seqs") or [])
            _context_img = _payload.get("context_img") or _context_img
            affecting_vars |= set(_payload.get("affecting_vars") or [])
            regions.extend(_payload.get("_regions") or [])
            _ti = _payload.get("taken_index")
            if _ti is not None and taken_index is None:
                taken_index = row_offset + _ti
            row_offset += len(_payload.get("conditions") or [])

        ## Differentiating-image selection across all branches in the merged cluster.
        ## Convergence truncation: drop images from labels visited by every branch.
        _all_vis = [_vis for _, _vis in _all_seqs if _vis]
        _shared_labels = (
            set.intersection(*[set(_v) for _v in _all_vis])
            if len(_all_vis) >= 2 else set()
        )
        _trunc = [
            [_item for _item in _imgs if _item[1] not in _shared_labels]
            for _imgs, _ in _all_seqs
        ]
        _img_sets = [set(_img for _img, _ in _imgs) for _imgs in _trunc]
        for _bi, _imgs in enumerate(_trunc):
            if not _imgs:
                branch_imgs.append(_context_img)
            else:
                _siblings = set().union(*(_img_sets[_j] for _j in range(len(_trunc)) if _j != _bi))
                _cands = [(_img, _lbl) for _img, _lbl in _imgs if not _tl_img_name_is_movie(_img)]
                _chosen = next((_img for _img, _ in _cands if _img not in _siblings), None)
                branch_imgs.append(_chosen or (_cands[0][0] if _cands else _context_img))
        if TL_DEBUG_GHOST:
            _tl_log("TL ghost cluster_imgs: {}".format(branch_imgs))

        _cache_key = str(group[0]["ast_key"])
        _existing  = (persistent._tl_ghost_node_cache or {}).get(_cache_key)
        if _existing is None or _existing.get("conditions") != conditions:
            persistent._tl_ghost_node_cache[_cache_key] = {
                "conditions":     conditions,
                "seen_fns":       seen_fns,
                "affecting_vars": sorted(affecting_vars),
                "_regions":       regions,
            }
        store._tl_ghost_nodes.append({
            "ast_key":           group[0]["ast_key"],
            "taken_index":       taken_index,
            "branch_imgs":       branch_imgs,
            "cluster_with_prev": cluster_with_prev,
        })
        if TL_DEBUG_GHOST:
            _tl_log("TL ghost appended cluster: root_ast={} members={} conditions={} affecting_vars={} cluster={}".format(
                group[0]["ast_key"], member_ast_keys, conditions,
                sorted(affecting_vars), cluster_with_prev))

    def _tl_on_if_execute(if_node, taken_index, pre_taken_seen=None):
        if not _tl_is_game_file(getattr(if_node, "filename", None) or ""):
            return

        ## Track which If nodes have been executed for per-session consumed detection.
        try:
            _if_ast_key   = (if_node.filename, if_node.linenumber)
            _key_to_vars  = getattr(persistent, "_tl_if_key_to_vars", None) or {}
            _vars_for_key = _key_to_vars.get(_if_ast_key) or []
            if _vars_for_key:
                _seen = getattr(store, "_tl_var_if_seen_keys", None)
                if not isinstance(_seen, dict):
                    _seen = {}
                    store._tl_var_if_seen_keys = _seen
                for _v in _vars_for_key:
                    if _v not in _seen:
                        _seen[_v] = set()
                    _seen[_v].add(_if_ast_key)
        except Exception:
            pass

        ## Ghost tracking (branch UI): only during active gameplay.
        if not (getattr(store, "_tl_branch_id", "") and
                not getattr(persistent, "_tl_replaying", False) and
                not config.skipping):
            return

        try:
            if not hasattr(store, "_tl_skip_ghost_ifs") or store._tl_skip_ghost_ifs is None:
                store._tl_skip_ghost_ifs = set()

            ## Skip ifs already synthesized by the lookahead pass.
            if (if_node.filename, if_node.linenumber) in store._tl_skip_ghost_ifs:
                if TL_DEBUG_GHOST:
                    _tl_log("TL ghost skip (lookahead-synthesized): {}".format(
                        (if_node.filename, if_node.linenumber)))
                return

            _run = _tl_collect_if_run(if_node)
            if not _run:
                return
            _groups = _tl_partition_if_run(_run)
            _prev_ghost = store._tl_ghost_nodes[-1] if store._tl_ghost_nodes else None
            for _gi, _group in enumerate(_groups):
                _cluster = False
                if _gi == 0 and _prev_ghost:
                    _cluster = _tl_should_cluster(_prev_ghost, _group[0].get("conditions") or [])
                _tl_emit_ghost_cluster(_group, _cluster)
            for _payload in _run[1:]:
                store._tl_skip_ghost_ifs.add(_payload["ast_key"])
            _tl_flush_var_changes()
            _tl_notify_branch(_run, taken_index, pre_taken_seen)
        except Exception as _e:
            _tl_log("TL ghost If error: {}".format(_e))


    def _tl_if_execute_patched(self):
        ## Evaluate which branch will be taken BEFORE executing so condition
        ## state is captured cleanly (branch body may modify the same vars).
        _taken = _tl_get_taken_branch(self)
        if _tl_is_game_file(getattr(self, "filename", None) or "") and TL_DEBUG_GHOST:
            try:
                _conds = [str(e[0]) for e in (getattr(self, "entries", None) or [])]
                _tl_log("TL if execute: file={} line={} taken={} conds={}".format(
                    getattr(self, "filename", None),
                    getattr(self, "linenumber", None),
                    _taken,
                    _conds,
                ))
            except Exception as _ife_log_e:
                _tl_log("TL if execute log failed: {}".format(_ife_log_e))

        ## Snapshot the taken branch's seen state BEFORE execute. Scene.execute
        ## runs synchronously inside If.execute and updates _seen_images, so
        ## any post-execute eval of image descriptors would be a false positive.
        _pre_taken_seen = None
        try:
            _entries = getattr(self, "entries", None) or []
            if _taken is not None and _taken < len(_entries):
                _blk = _entries[_taken][1]
                _sfn = _tl_make_seen_fn_cached(_blk)
                if _sfn[0] != "never":
                    _pre_taken_seen = _tl_eval_seen_fn(_sfn)
        except Exception:
            pass

        result = _tl_orig_if_execute(self)
        ## Visited-node marking: always run (no skip/replay guard — we want to
        ## mark nodes visited even during fast-forward or before first menu choice).
        _tl_on_if_execute(self, _taken, _pre_taken_seen)
        return result

    _tl_renpy_ast.If.execute = _tl_if_execute_patched

    ## ── Branch notification ───────────────────────────────────────────────────

    def _tl_notify_branch(run, taken_index, pre_taken_seen=None):
        """
        Emit a tiered branch notification for a full If-run (cluster).
        The root payload may have taken_index=None when its condition didn't match
        and the actual taken branch lives in a downstream lookahead payload.

            suppress   — taken branch seen AND all alternatives across entire run seen
            ⎇          — taken branch seen, at least one alternative unseen
            ⎇ New path — taken branch was unseen before being taken (pre_taken_seen=False)

        pre_taken_seen is the seen state of the root if's taken branch evaluated
        BEFORE If.execute ran — so image descriptors are correct (Scene.execute
        updates _seen_images synchronously inside If.execute).
        None means indeterminate (descriptor was "never") — suppress New path.
        """
        try:
            _all_fns      = []
            _taken_glob_i = None   ## flat index of taken branch in _all_fns; None if not taken
            _offset       = 0
            for _payload in (run or []):
                _sfns = _payload.get("seen_fns") or []
                _ti   = _payload.get("taken_index")
                _all_fns.extend(_sfns)
                if _ti is not None and _ti < len(_sfns) and _taken_glob_i is None:
                    _taken_glob_i = _offset + _ti
                _offset += len(_sfns)

            if not _all_fns:
                return

            ## Use the pre-execution snapshot for "New path" so image-based
            ## descriptors aren't polluted by Scene updates from this very execution.
            if pre_taken_seen is False:
                if TL_DEBUG_GHOST:
                    _tl_log("TL notify: tier=new_path taken_seen=False")
                renpy.show_screen("_tl_notify", message="⎇ New path")
                return

            ## ⎇ icon-only: at least one non-taken branch in the cluster is locked.
            ## When _taken_glob_i is None (no branch taken, e.g. unsatisfied standalone
            ## if), all branches are candidates — still notify if any are locked.
            _locked = sum(
                1 for _i, _sfn in enumerate(_all_fns)
                if _i != _taken_glob_i and not _tl_eval_seen_fn(_sfn)
            )
            if _locked > 0:
                if TL_DEBUG_GHOST:
                    _tl_log("TL notify: tier=icon locked={}".format(_locked))
                renpy.show_screen("_tl_notify", message="⎇")
            elif TL_DEBUG_GHOST:
                _tl_log("TL notify: tier=suppress")
            ## all branches seen — suppress
        except Exception:
            pass

    ## ── screen-navigate callback — sandbox location-navigation ghost node clear ─
    ##
    ## config.statement_callbacks fires before every named statement with the
    ## statement name string. Both "call screen" and "show screen" cover sandbox
    ## games that navigate via screen statements (PhotoHunt uses `show screen locN`).
    ## Menus already clear ghost nodes in _tl_record_before; this covers the
    ## between-menu navigation that happens in sandbox games.
    ## Note: renpy.show_screen() from Python does NOT fire statement_callbacks,
    ## so mod-internal notify calls are unaffected.

    def _tl_on_screen_navigate(name):
        if name not in ("call screen", "show screen"):
            return
        if not (getattr(store, "_tl_branch_id", "") and
                not getattr(persistent, "_tl_replaying", False) and
                not config.skipping):
            return
        if store._tl_ghost_nodes or store._tl_skip_ghost_ifs:
            if TL_DEBUG_GHOST:
                _tl_log("TL screen_navigate: cleared ghost={}".format(len(store._tl_ghost_nodes)))
            store._tl_ghost_nodes    = []
            store._tl_skip_ghost_ifs = set()

    config.statement_callbacks.append(_tl_on_screen_navigate)

