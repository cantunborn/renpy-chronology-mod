## =============================================================================
## CHRONOLOGY MOD — timeline_ghost_logic.rpy
## Ghost card runtime logic: If-node hook, payload building, clustering.
## =============================================================================

init -2 python:

    import ast as _tl_ast_mod

    def _tl_branch_img(block, context_img=None):
        """
        Resolve the best thumbnail image for a ghost branch block.

        Tier 1 — local walk: first Scene/Show in the branch block.
        Tier 2 — jump/call follow: if tier 1 misses, follow the first Jump or
            Call target one hop via namemap and repeat the scene walk.
        Tier 3 — context fallback: return context_img (the live scene image at
            the moment the if-node executed), which may be None.
        """
        if not block:
            return context_img

        ## Tier 1: local Scene/Show
        for node in block:
            t = type(node).__name__
            if t in ("Scene", "Show"):
                sp = getattr(node, "imspec", None)
                if sp and sp[0] and tuple(sp[0]) in renpy.display.image.images:
                    _tl_log("TL branch_img tier1: {}".format(" ".join(sp[0])))
                    return " ".join(sp[0])

        ## Tier 2: follow first Jump or Call one hop
        try:
            _namemap = renpy.game.script.namemap
            for node in block:
                t = type(node).__name__
                if t in ("Jump", "Call"):
                    _target = getattr(node, "target", None)
                    if not _target:
                        continue
                    _label_node = _namemap.get(_target)
                    _sub = getattr(_label_node, "block", None)
                    if not _sub:
                        break
                    for snode in _sub:
                        st = type(snode).__name__
                        if st in ("Scene", "Show"):
                            sp = getattr(snode, "imspec", None)
                            if sp and sp[0] and tuple(sp[0]) in renpy.display.image.images:
                                _tl_log("TL branch_img tier2 via {}: {}".format(
                                    _target, " ".join(sp[0])))
                                return " ".join(sp[0])
                    break  ## one hop only
        except Exception as _e:
            _tl_log("TL branch_img tier2 failed: {}".format(_e))

        ## Tier 3: context fallback
        _tl_log("TL branch_img tier3 context: {}".format(context_img))
        return context_img

    def _tl_first_scene_img(block):
        """Shim — use _tl_branch_img for new call sites."""
        return _tl_branch_img(block, None)

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
                            _tl_log("TL collect_branch_imgs hop {}: walked={} imgs={}".format(
                                _target, _walked, [i for i, _ in collected]))
                        break  ## one hop only
            except Exception as _e:
                _tl_log("TL collect_branch_imgs hop failed: {}".format(_e))

        return collected, visited


init python:
    import renpy.ast as _tl_renpy_ast
    _tl_orig_if_execute = _tl_renpy_ast.If.execute

    ## ── Var / condition helpers (restored from deleted tl_var_delta.rpy) ─────

    import re as _tl_re

    _TL_VAR_RE     = _tl_re.compile(r'\b([a-z_][a-z0-9_]*)\b(?!\s*\()')
    _TL_STR_LIT_RE = _tl_re.compile(r'"[^"]*"|\'[^\']*\'')
    _TL_KW_SKIP    = frozenset([
        "and","or","not","in","is","True","False","None",
        "if","else","elif","return","renpy","store","persistent",
        "len","range","int","str","float","bool","list","dict","set",
    ])

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

    def _tl_extract_vars_from_conditions(conditions):
        """Return the set of game-variable names referenced across all condition strings."""
        out = set()
        for cond in conditions:
            if cond in ("True", "False", "None"):
                continue
            cleaned = _TL_STR_LIT_RE.sub('', cond)
            for m in _TL_VAR_RE.finditer(cleaned):
                name = m.group(1)
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
                    ## Handle both Python 2 (ast.Str) and Python 3 (ast.Constant)
                    if hasattr(_tl_ast_mod, "Constant") and isinstance(comp, _tl_ast_mod.Constant):
                        return [{var: frozenset([str(comp.value)])}]
                    elif hasattr(_tl_ast_mod, "Str") and isinstance(comp, _tl_ast_mod.Str):
                        return [{var: frozenset([str(comp.s)])}]
                    elif isinstance(comp, _tl_ast_mod.Num):
                        return [{var: frozenset([str(comp.n)])}]
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
        prev_regions = prev_ghost.get("_regions")
        if not prev_regions:
            return False

        new_regions = []
        for cond in new_conds:
            if cond in ("True", "else", ""):
                continue
            r = _tl_parse_regions(cond)
            if r is None:
                _tl_log("TL cluster: parse failed for '{}' → no cluster".format(cond))
                return False
            new_regions.extend(r)
        if not new_regions:
            return False

        for ra in prev_regions:
            for rb in new_regions:
                shared_vars = set(ra) & set(rb)
                if not shared_vars:
                    _tl_log("TL cluster: no shared vars {} vs {} → no cluster".format(
                        set(ra), set(rb)))
                    return False
                overlap = all(ra[v] & rb[v] for v in shared_vars)
                if overlap:
                    _tl_log("TL cluster: regions overlap {} & {} → no cluster".format(
                        dict(ra), dict(rb)))
                    return False

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

    def _tl_toggle_ghost_highlight(ast_key, branch_idx):
        """Toggle ghost branch row highlight on/off."""
        key = (ast_key, branch_idx)
        if store._tl_ghost_highlight == key:
            store._tl_ghost_highlight = None
        else:
            store._tl_ghost_highlight = key

    def _tl_prettify_condition(cond):
        """Replace bare snake_case identifiers in a condition string with pretty names."""
        if cond == "True":
            return "else"
        def _repl(m):
            name = m.group(1)
            if name in _TL_KW_SKIP or name[0].isupper():
                return name
            return _tl_prettify_var(name)
        cleaned = _TL_STR_LIT_RE.sub(lambda m: m.group(0), cond)
        return _TL_VAR_RE.sub(lambda m: _repl(m), cond)

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

        _any_parsed = any(
            _tl_parse_regions(c) is not None
            for c in conditions if c != "True"
        )
        if not _any_parsed:
            return None

        affecting_vars = _tl_extract_vars_from_conditions(conditions)

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
        _tl_log("TL ghost _regions: {}".format(
            len(regions) if regions is not None else "None"))

        seen_fns = []
        for _cond, _blk in entries:
            seen_fns.append(_tl_make_seen_fn(_blk) if _blk else ("never",))

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
        _tl_log("TL ghost cluster_imgs: {}".format(branch_imgs))

        store._tl_ghost_nodes = store._tl_ghost_nodes + [{
            "type":              "branch",
            "ast_key":           group[0]["ast_key"],
            "conditions":        conditions,
            "seen_fns":          seen_fns,
            "taken_index":       taken_index,
            "affecting_vars":    sorted(affecting_vars),
            "branch_imgs":       branch_imgs,
            "cluster_with_prev": cluster_with_prev,
            "_regions":          regions,
            "member_ast_keys":   member_ast_keys,
        }]
        _tl_log("TL ghost appended cluster: root_ast={} members={} rows={} cluster={}".format(
            group[0]["ast_key"], member_ast_keys, len(conditions), cluster_with_prev))

    def _tl_on_if_execute(if_node, taken_index):
        if not _tl_should_track_if_node(if_node):
            return

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
            renpy.notify("Branch detected — open timeline (T)")
        except Exception as _e:
            _tl_log("TL ghost If error: {}".format(_e))

    def _tl_should_track_if_node(if_node):
        _filename = getattr(if_node, "filename", None) or ""
        if not _filename.startswith("game/"):
            return False
        _base = _filename.rsplit("/", 1)[-1]
        if _base.startswith("timeline_") and _base.endswith(".rpy"):
            return False
        return True

    def _tl_if_execute_patched(self):
        ## Evaluate which branch will be taken BEFORE executing so condition
        ## state is captured cleanly (branch body may modify the same vars).
        _taken = _tl_get_taken_branch(self)
        if _tl_should_track_if_node(self):
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
        result = _tl_orig_if_execute(self)
        ## Visited-node marking: always run (no skip/replay guard — we want to
        ## mark nodes visited even during fast-forward or before first menu choice).
        _tl_on_if_execute(self, _taken)
        return result

    _tl_renpy_ast.If.execute = _tl_if_execute_patched