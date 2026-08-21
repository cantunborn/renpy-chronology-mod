## =============================================================================
## CHRONOLOGY MOD — tl_ghost_logic_ren.py
## Ghost card runtime logic: If-node hook, payload building, clustering.
## =============================================================================

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Tuple, List, Set, Any
    import renpy
    from renpy import persistent, config, store
    from tl_ast_utils_ren import _tl_prettify_var, _tl_ast_literal_value, _tl_strip_renpy_tags, _tl_is_game_file  # type-check-only; injected into store namespace at runtime
    from tl_seen_check_ren import _tl_make_seen_fn, _tl_eval_seen_fn  # type-check-only; injected into store namespace at runtime
    from tl_route_logic_ren import _tl_flush_var_changes  # type-check-only; injected into store namespace at runtime
    from tl_assets_ren import _tl_resolve_live_menu_img_name, _tl_img_name_is_movie  # type-check-only; injected into store namespace at runtime
    from timeline_init_ren import _tl_log, TL_DEBUG_GHOST, _tl_builtin_id  # type-check-only; injected into store namespace at runtime

"""renpy
init -2 python:
"""

import ast as _tl_ast_mod

def _collect_branch_imgs(block, max_images=5):  # type: (Optional[list], int) -> Tuple[list, set]
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
            namemap = renpy.game.script.namemap
            for node in block:
                if type(node).__name__ in ("Jump", "Call"):
                    target = getattr(node, "target", None)
                    if not target:
                        continue
                    label_node = namemap.get(target)
                    sub_block = getattr(label_node, "block", None)
                    if sub_block:
                        visited.add(target)
                        ## Walk .next chain — covers all sequential scenes in
                        ## the label, not just the flat block list.
                        ## Stop at Label nodes to avoid crossing into the next label.
                        snode = sub_block[0]
                        walked = 0
                        while snode is not None and len(collected) < max_images:
                            stype = type(snode).__name__
                            if stype == "Label":
                                break
                            if stype in ("Scene", "Show"):
                                sp = getattr(snode, "imspec", None)
                                if sp and sp[0] and tuple(sp[0]) in renpy.display.image.images:
                                    collected.append((" ".join(sp[0]), target))
                            snode = getattr(snode, "next", None)
                            walked += 1
                        if TL_DEBUG_GHOST:
                            _tl_log("TL collect_branch_imgs hop {}: walked={} imgs={}".format(
                                target, walked, [i for i, _ in collected]))
                    break  ## one hop only
        except Exception as e:
            _tl_log("TL collect_branch_imgs hop failed: {}".format(e))

    return collected, visited


"""renpy
init python:
"""

import renpy.ast as _tl_renpy_ast
_tl_orig_if_execute = _tl_renpy_ast.If.execute

## seen_fn descriptor cache: _tl_builtin_id(branch_block) → seen_fn tuple.
## Branch block objects are stable Python objects for the session lifetime
## (RenPy AST is built once at startup and never replaced). Module-level dict
## is invisible to the rollback system — correct, since AST doesn't change on
## rollback. Not persistent — descriptors are session-derived from AST.
_TL_SEEN_FN_CACHE = {}

def _tl_ghost_ast(ast_key):  # type: (Any) -> dict
    """Return persistent AST-derived data for a ghost cluster by its ast_key."""
    return (persistent._tl_ghost_node_cache or {}).get(str(ast_key)) or {}

def _tl_make_seen_fn_cached(blk):  # type: (Optional[list]) -> tuple
    if blk is None:
        return ("never",)
    cache_key = _tl_builtin_id(blk)
    if cache_key not in _TL_SEEN_FN_CACHE:
        _TL_SEEN_FN_CACHE[cache_key] = _tl_make_seen_fn(blk)
    return _TL_SEEN_FN_CACHE[cache_key]

## ── Var / condition helpers (restored from deleted tl_var_delta.rpy) ─────

import re as _tl_re

_TL_VAR_RE     = _tl_re.compile(r'\b([a-z_][a-z0-9_]*)\b(?!\s*\()')
_TL_STR_LIT_RE = _tl_re.compile(r'"[^"]*"|\'[^\']*\'')
_TL_KW_SKIP    = frozenset([
    "and","or","not","in","is","True","False","None",
    "if","else","elif","return","renpy","store","persistent",
    "len","range","int","str","float","bool","list","dict","set",
])

## _tl_prettify_var — defined in tl_ast_utils_ren.py (loads before this file)

def _tl_extract_vars_from_conditions(conditions):  # type: (List[str]) -> Set[str]
    """Return the set of game-variable names referenced across all condition strings."""
    import ast
    out = set()
    for cond in conditions:
        if cond in ("True", "False", "None"):
            continue
        try:
            tree = ast.parse(cond, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                name = node.id
                if name not in _TL_KW_SKIP and not name[0].isupper():
                    out.add(name)
    return out

## ── Mutual exclusivity clustering ────────────────────────────────────────

def _tl_parse_regions(cond_str):  # type: (str) -> Optional[list]
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
                    cond_regions = _node_to_regions(v)
                    if cond_regions is None:
                        return None
                    result.extend(cond_regions)
                return result
            elif isinstance(n.op, _tl_ast_mod.And):
                result = [{}]
                for v in n.values:
                    cond_regions = _node_to_regions(v)
                    if cond_regions is None:
                        return None
                    new_result = []
                    for existing in result:
                        for clause in cond_regions:
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
                lit = _tl_ast_literal_value(comp)
                if lit is not None:
                    return [{var: frozenset([lit])}]
        return None

    return _node_to_regions(tree.body)

def _tl_should_cluster(prev_ghost, new_conds):  # type: (dict, List[str]) -> bool
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

def _tl_branch_exits_before_next(block):  # type: (Optional[list]) -> bool
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
        regions, affecting_vars=None):  # type: (dict, tuple, Optional[list], Optional[list], Optional[list], Optional[list], Optional[list]) -> dict
    """Append hidden sibling-if rows into an existing ghost card."""
    ghost["conditions"] = list(ghost.get("conditions") or []) + list(conditions or [])
    ghost["seen_fns"] = list(ghost.get("seen_fns") or []) + list(seen_fns or [])
    ghost["branch_imgs"] = list(ghost.get("branch_imgs") or []) + list(branch_imgs or [])
    ghost["_regions"] = list(ghost.get("_regions") or []) + list(regions or [])
    if affecting_vars:
        ghost["affecting_vars"] = sorted(set(ghost.get("affecting_vars") or []) | set(affecting_vars))
    ghost.setdefault("member_ast_keys", []).append(ast_key)
    return ghost

def _tl_prettify_condition(cond):  # type: (str) -> str
    """Prettify var names and strip quotes from string values; numeric values left as-is."""
    if cond == "True":
        return "else"
    try:
        import ast
        tree = ast.parse(cond, mode="eval")
        repls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                name = node.id
                if name not in _TL_KW_SKIP and not name[0].isupper():
                    col = node.col_offset
                    repls.append((col, col + len(name), _tl_prettify_var(name)))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                repls.append((node.col_offset, node.end_col_offset, str(node.value)))
        repls.sort(key=lambda x: x[0], reverse=True)
        result = cond
        for start, end, pretty in repls:
            result = result[:start] + pretty + result[end:]
        return _tl_strip_renpy_tags(result)
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

def _tl_get_taken_branch(if_node):  # type: (Any) -> Optional[int]
    """Evaluate conditions in order and return index of first True one."""
    try:
        for i, (cond, blk) in enumerate(if_node.entries):
            cond_str = str(cond)
            if cond_str == "True":
                return i
            if renpy.python.py_eval(cond_str):
                return i
    except Exception:
        pass
    return None

def _tl_build_ghost_payload(if_node, taken_index, context_img=None):  # type: (Any, Optional[int], Optional[str]) -> Optional[dict]
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
    for cond in conditions:
        if cond in ("True", "else", ""):
            continue
        cond_regions = _tl_parse_regions(cond)
        if cond_regions is not None:
            regions.extend(cond_regions)
        else:
            regions = None
            break
    if TL_DEBUG_GHOST:
        _tl_log("TL ghost _regions: {}".format(
            len(regions) if regions is not None else "None"))

    seen_fns = []
    for cond, blk in entries:
        seen_fns.append(_tl_make_seen_fn_cached(blk))

    return {
        "ast_key":        (if_node.filename, if_node.linenumber),
        "conditions":     conditions,
        "seen_fns":       seen_fns,
        "taken_index":    taken_index,
        "affecting_vars": list(affecting_vars),
        "branch_imgs":    branch_imgs,
        "_regions":       regions,
    }

def _tl_collect_if_run(start_if_node):  # type: (Any) -> list
    """Collect a sequential run of player-relevant sibling If nodes."""
    context_img = _tl_resolve_live_menu_img_name()
    run = []
    node = start_if_node
    while node is not None and isinstance(node, _tl_renpy_ast.If):
        payload = _tl_build_ghost_payload(node, _tl_get_taken_branch(node), context_img)
        if payload is None:
            break
        run.append((payload, node))
        node = getattr(node, "next", None)
    ## Collect raw image sequences per branch; selection deferred to
    ## _tl_emit_ghost_cluster so cross-payload differentiation is possible.
    for payload, if_node in run:
        entries = getattr(if_node, "entries", [])
        seqs = []
        for cond, blk in entries:
            imgs, vis = _collect_branch_imgs(blk) if blk else ([], set())
            seqs.append((imgs, vis))
        payload["branch_img_seqs"] = seqs
        payload["context_img"] = context_img
        payload["all_branches_exit"] = all(
            _tl_branch_exits_before_next(blk)
            for _, blk in entries if blk
        )
    return [p for p, _ in run]

def _tl_partition_if_run(run):  # type: (list) -> list
    """Partition a sequential If run into mutually-exclusive cluster components."""
    if not run:
        return []
    groups = []
    current = [run[0]]
    for payload in run[1:]:
        prev = {"_regions": []}
        for m in current:
            prev["_regions"].extend(m.get("_regions") or [])
        jump_cluster = (
            payload.get("all_branches_exit") and
            all(p.get("all_branches_exit") for p in current)
        )
        if _tl_should_cluster(prev, payload.get("conditions") or []) or jump_cluster:
            current.append(payload)
        else:
            groups.append(current)
            current = [payload]
    groups.append(current)
    return groups

def _tl_emit_ghost_cluster(group, cluster_with_prev):  # type: (list, bool) -> None
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
    all_seqs = []
    context_img = None

    for payload in group:
        member_ast_keys.append(payload["ast_key"])
        conditions.extend(payload.get("conditions") or [])
        seen_fns.extend(payload.get("seen_fns") or [])
        all_seqs.extend(payload.get("branch_img_seqs") or [])
        context_img = payload.get("context_img") or context_img
        affecting_vars |= set(payload.get("affecting_vars") or [])
        regions.extend(payload.get("_regions") or [])
        taken_idx = payload.get("taken_index")
        if taken_idx is not None and taken_index is None:
            taken_index = row_offset + taken_idx
        row_offset += len(payload.get("conditions") or [])

    ## Differentiating-image selection across all branches in the merged cluster.
    ## Convergence truncation: drop images from labels visited by every branch.
    all_vis = [vis for _, vis in all_seqs if vis]
    shared_labels = (
        set.intersection(*[set(v) for v in all_vis])
        if len(all_vis) >= 2 else set()
    )
    trunc = [
        [item for item in imgs if item[1] not in shared_labels]
        for imgs, _ in all_seqs
    ]
    img_sets = [set(img for img, _ in imgs) for imgs in trunc]
    for branch_idx, imgs in enumerate(trunc):
        if not imgs:
            branch_imgs.append(context_img)
        else:
            sibling_imgs = set().union(*(img_sets[j] for j in range(len(trunc)) if j != branch_idx))
            cands = [(img, lbl) for img, lbl in imgs if not _tl_img_name_is_movie(img)]
            chosen = next((img for img, _ in cands if img not in sibling_imgs), None)
            branch_imgs.append(chosen or (cands[0][0] if cands else context_img))
    if TL_DEBUG_GHOST:
        _tl_log("TL ghost cluster_imgs: {}".format(branch_imgs))

    cache_key = str(group[0]["ast_key"])
    existing  = (persistent._tl_ghost_node_cache or {}).get(cache_key)
    if existing is None or existing.get("conditions") != conditions:
        persistent._tl_ghost_node_cache[cache_key] = {
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

def _tl_on_if_execute(if_node, taken_index, pre_taken_seen=None):  # type: (Any, Optional[int], Optional[bool]) -> None
    if not _tl_is_game_file(getattr(if_node, "filename", None) or ""):
        return

    ## Track which If nodes have been executed for per-session consumed detection.
    try:
        if_ast_key   = (if_node.filename, if_node.linenumber)
        key_to_vars  = getattr(persistent, "_tl_if_key_to_vars", None) or {}
        vars_for_key = key_to_vars.get(if_ast_key) or []
        if vars_for_key:
            seen = getattr(store, "_tl_var_if_seen_keys", None)
            if not isinstance(seen, dict):
                seen = {}
                store._tl_var_if_seen_keys = seen
            for var in vars_for_key:
                if var not in seen:
                    seen[var] = set()
                seen[var].add(if_ast_key)
    except Exception as e:
        _tl_log("TL if_execute var tracking failed: {}".format(e))

    ## Ghost tracking (branch UI): only during active gameplay.
    if getattr(persistent, "_tl_replaying", False) or config.skipping:
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

        run = _tl_collect_if_run(if_node)
        if not run:
            return
        groups = _tl_partition_if_run(run)
        for group in groups:
            _tl_emit_ghost_cluster(group, False)
        for payload in run[1:]:
            store._tl_skip_ghost_ifs.add(payload["ast_key"])
        _tl_flush_var_changes()
        _tl_notify_branch(run, taken_index, pre_taken_seen)
    except Exception as e:
        _tl_log("TL ghost If error: {}".format(e))


def _tl_if_execute_patched(self):  # type: (Any) -> None
    if renpy.is_init_phase() or not _tl_is_game_file(getattr(self, "filename", None) or ""):
        return _tl_orig_if_execute(self)
    ## Evaluate which branch will be taken BEFORE executing so condition
    ## state is captured cleanly (branch body may modify the same vars).
    taken = _tl_get_taken_branch(self)
    if _tl_is_game_file(getattr(self, "filename", None) or "") and TL_DEBUG_GHOST:
        try:
            conds = [str(e[0]) for e in (getattr(self, "entries", None) or [])]
            _tl_log("TL if execute: file={} line={} taken={} conds={}".format(
                getattr(self, "filename", None),
                getattr(self, "linenumber", None),
                taken,
                conds,
            ))
        except Exception as e:
            _tl_log("TL if execute log failed: {}".format(e))

    ## Snapshot the taken branch's seen state BEFORE execute. Scene.execute
    ## runs synchronously inside If.execute and updates _seen_images, so
    ## any post-execute eval of image descriptors would be a false positive.
    pre_taken_seen = None
    try:
        entries = getattr(self, "entries", None) or []
        if taken is not None and taken < len(entries):
            blk = entries[taken][1]
            seen_fn = _tl_make_seen_fn_cached(blk)
            if seen_fn[0] != "never":
                pre_taken_seen = _tl_eval_seen_fn(seen_fn)
    except Exception as e:
        _tl_log("TL if execute pre_taken_seen failed: {}".format(e))

    result = _tl_orig_if_execute(self)
    ## Visited-node marking: always run (no skip/replay guard — we want to
    ## mark nodes visited even during fast-forward or before first menu choice).
    _tl_on_if_execute(self, taken, pre_taken_seen)
    return result

_tl_renpy_ast.If.execute = _tl_if_execute_patched

## ── Branch notification ───────────────────────────────────────────────────

def _tl_notify_branch(run, taken_index, pre_taken_seen=None):  # type: (Optional[list], Optional[int], Optional[bool]) -> None
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
        all_seen_fns    = []
        taken_global_idx = None   ## flat index of taken branch; None if not taken
        offset           = 0
        for payload in (run or []):
            seen_fns = payload.get("seen_fns") or []
            taken_idx = payload.get("taken_index")
            all_seen_fns.extend(seen_fns)
            if taken_idx is not None and taken_idx < len(seen_fns) and taken_global_idx is None:
                taken_global_idx = offset + taken_idx
            offset += len(seen_fns)

        if not all_seen_fns:
            return

        ## Use the pre-execution snapshot for "New path" so image-based
        ## descriptors aren't polluted by Scene updates from this very execution.
        if pre_taken_seen is False:
            if TL_DEBUG_GHOST:
                _tl_log("TL notify: tier=new_path taken_seen=False")
            renpy.show_screen("_tl_notify", message="⎇ New path")
            return

        ## ⎇ icon-only: at least one non-taken branch in the cluster is locked.
        ## When taken_global_idx is None (no branch taken, e.g. unsatisfied standalone
        ## if), all branches are candidates — still notify if any are locked.
        locked = sum(
            1 for i, seen_fn in enumerate(all_seen_fns)
            if i != taken_global_idx and not _tl_eval_seen_fn(seen_fn)
        )
        if locked > 0:
            if TL_DEBUG_GHOST:
                _tl_log("TL notify: tier=icon locked={}".format(locked))
            renpy.show_screen("_tl_notify", message="⎇")
        elif TL_DEBUG_GHOST:
            _tl_log("TL notify: tier=suppress")
        ## all branches seen — suppress
    except Exception as e:
        _tl_log("TL notify_branch failed: {}".format(e))

## ── screen-navigate callback — sandbox location-navigation ghost node clear ─
##
## config.statement_callbacks fires before every named statement with the
## statement name string. Both "call screen" and "show screen" cover sandbox
## games that navigate via screen statements (PhotoHunt uses `show screen locN`).
## Menus already clear ghost nodes in _tl_record_before; this covers the
## between-menu navigation that happens in sandbox games.
## Note: renpy.show_screen() from Python does NOT fire statement_callbacks,
## so mod-internal notify calls are unaffected.

def _tl_on_screen_navigate(name):  # type: (str) -> None
    if name not in ("call screen", "show screen"):
        return
    if getattr(persistent, "_tl_replaying", False) or config.skipping:
        return
    if store._tl_ghost_nodes or store._tl_skip_ghost_ifs:
        if TL_DEBUG_GHOST:
            _tl_log("TL screen_navigate: cleared ghost={}".format(len(store._tl_ghost_nodes)))
        store._tl_ghost_nodes    = []
        store._tl_skip_ghost_ifs = set()

config.statement_callbacks.append(_tl_on_screen_navigate)