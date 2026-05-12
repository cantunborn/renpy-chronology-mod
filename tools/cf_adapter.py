"""
Control-flow adapter for Ren'Py AST.

Builds a statement-level directed graph from a JSON AST dump, with explicit
typed successor/predecessor edges, back-edge detection, and Tarjan SCC
computation for hub (cycle) identification.

Design: docs/FORMULA_SOLVER_DESIGN.md § "Traversal Strategy v2 — Layer 1"
"""

from collections import defaultdict, deque


class RenpyFlowGraph:
    """
    Thin control-flow adapter over a Ren'Py JSON AST.

    Build once from (ast, start_label). Query via:
        successors(nid)       -> list[(nid, edge_kind)]
        predecessors(nid)     -> list[(nid, edge_kind)]
        label_entry[label]    -> nid
        stmt_at[nid]          -> stmt dict
        is_back_edge(src,dst) -> bool
        cycle_headers         -> set[nid]
        hub_scc[hub_nid]      -> set[nid]
    """

    def __init__(self, ast: dict, start: str, stop: str | None = None):
        self._label_entry: dict = {}
        self._stmt_at: dict = {}
        self._succ: dict = {}
        self._pred: dict = {}
        self._back_edges: set = set()
        self._cycle_headers: set = set()
        self._hub_scc: dict = {}
        self._stop = stop
        self._build(ast, start)

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def successors(self, nid) -> list:
        return list(self._succ.get(nid, []))

    def predecessors(self, nid) -> list:
        return list(self._pred.get(nid, []))

    @property
    def label_entry(self) -> dict:
        return self._label_entry

    @property
    def stmt_at(self) -> dict:
        return self._stmt_at

    def is_back_edge(self, src, dst) -> bool:
        return (src, dst) in self._back_edges

    @property
    def cycle_headers(self) -> set:
        return self._cycle_headers

    @property
    def hub_scc(self) -> dict:
        return self._hub_scc

    # ---------------------------------------------------------------------------
    # Graph construction — fully iterative, no recursion
    # ---------------------------------------------------------------------------

    def _build(self, ast: dict, start: str):
        label_entry = self._label_entry
        _nid_memo: dict = {}   # id(stmt_dict) -> nid, ensures idempotency
        _seq = [0]

        def node_id(s) -> tuple:
            sid = id(s)
            if sid in _nid_memo:
                return _nid_memo[sid]
            name = s.get("name")
            if name:
                nid = tuple(name)
            else:
                line = s.get("linenumber") or s.get("line")
                filename = s.get("filename", "_unknown")
                if line is not None:
                    nid = (filename, line)
                else:
                    _seq[0] += 1
                    nid = ("_seq", _seq[0])
            _nid_memo[sid] = nid
            return nid

        def resolve_next(nv) -> tuple | None:
            if nv is None:
                return None
            if isinstance(nv, list):
                return tuple(nv)
            if isinstance(nv, str):
                return label_entry.get(nv)
            return None

        # ---- Pass 1: discover all reachable labels, populate label_entry --------

        def _block_label_targets(block) -> list:
            """Collect all label-name targets within a block and its arm sub-blocks."""
            out = []
            work = list(block)
            while work:
                s = work.pop()
                t = s.get("type")
                nv = s.get("next")
                if t in ("Jump", "Call"):
                    tgt = s.get("target")
                    if tgt:
                        out.append(tgt)
                elif t == "UserStatement":
                    out.extend(j for j in (s.get("screen_jumps") or []) if j)
                if isinstance(nv, str):
                    out.append(nv)
                if t == "If":
                    for e in (s.get("entries") or []):
                        arm = (e[1] if isinstance(e, list) else e.get("block")) or []
                        work.extend(arm)
                elif t == "Menu":
                    for item in (s.get("items") or []):
                        arm = (item[2] if isinstance(item, list) and len(item) > 2
                               else item.get("block")) or []
                        work.extend(arm)
            return out

        visited_labels: set = set()
        lq: deque = deque([start])
        while lq:
            lname = lq.popleft()
            if lname in visited_labels:
                continue
            if self._stop and lname == self._stop:
                continue
            if lname not in ast:
                continue
            visited_labels.add(lname)
            ldata = ast[lname]
            block = ldata.get("block") or []
            nl = ldata.get("next_label")
            if block:
                label_entry[lname] = node_id(block[0])
                for tgt in _block_label_targets(block):
                    lq.append(tgt)
            if nl:
                lq.append(nl)

        # Resolve empty-block labels: follow next_label chain to first real entry
        for lname in list(visited_labels):
            if lname in label_entry:
                continue
            seen_chain: set = set()
            cur = ast[lname].get("next_label")
            while cur and cur not in seen_chain and cur in ast:
                seen_chain.add(cur)
                if cur in label_entry:
                    label_entry[lname] = label_entry[cur]
                    break
                ldata = ast[cur]
                block = ldata.get("block") or []
                if block:
                    entry_nid = node_id(block[0])
                    label_entry[cur] = entry_nid
                    label_entry[lname] = entry_nid
                    break
                cur = ldata.get("next_label")

        # ---- Pass 2: collect edges and stmt_at ----------------------------------

        stmt_at: dict = {}
        edges: list = []
        all_nids: set = set()
        return_nids: set = set()
        call_sites: dict = {}

        # Each work item is a block (list of stmts) to process.
        # Arm sub-blocks are pushed as separate items — no recursion.
        work: list = []
        for lname in visited_labels:
            block = (ast[lname].get("block") or [])
            if block:
                work.append(block)

        while work:
            block = work.pop()
            for s in block:
                nid = node_id(s)
                all_nids.add(nid)
                stmt_at[nid] = s
                t = s.get("type")
                nv = s.get("next")

                if t == "If":
                    entries = s.get("entries") or []
                    has_else = any(
                        (e[0] if isinstance(e, list) else e.get("condition")) is None
                        for e in entries
                    )
                    post_nid = resolve_next(nv)
                    for e in entries:
                        arm_block = (e[1] if isinstance(e, list)
                                     else e.get("block")) or []
                        if arm_block:
                            arm_nid = node_id(arm_block[0])
                            edges.append((nid, arm_nid, "if_arm"))
                            work.append(arm_block)
                        elif post_nid:
                            edges.append((nid, post_nid, "if_arm"))
                    if not has_else and post_nid:
                        edges.append((nid, post_nid, "if_fallthrough"))

                elif t == "Menu":
                    items = s.get("items") or []
                    post_nid = resolve_next(nv)
                    for item in items:
                        arm_block = (item[2] if isinstance(item, list) and len(item) > 2
                                     else item.get("block")) or []
                        if arm_block:
                            arm_nid = node_id(arm_block[0])
                            edges.append((nid, arm_nid, "menu_arm"))
                            work.append(arm_block)
                        elif post_nid:
                            edges.append((nid, post_nid, "menu_arm"))

                elif t == "Jump":
                    tgt = s.get("target")
                    tgt_nid = label_entry.get(tgt) if tgt else None
                    if tgt_nid:
                        edges.append((nid, tgt_nid, "jump"))

                elif t == "Call":
                    tgt = s.get("target")
                    post_nid = tuple(nv) if isinstance(nv, list) else None
                    callee_nid = label_entry.get(tgt) if tgt else None
                    if callee_nid:
                        edges.append((nid, callee_nid, "call"))
                    if post_nid:
                        all_nids.add(post_nid)
                        call_sites.setdefault(tgt, []).append(post_nid)

                elif t == "Return":
                    return_nids.add(nid)

                elif t == "UserStatement":
                    jumps = [j for j in (s.get("screen_jumps") or [])
                             if j in label_entry]
                    if jumps:
                        for tgt in jumps:
                            tgt_nid = label_entry.get(tgt)
                            if tgt_nid:
                                edges.append((nid, tgt_nid, "screen_jump"))
                    else:
                        seq_nid = resolve_next(nv)
                        if seq_nid:
                            edges.append((nid, seq_nid, "sequential"))

                else:
                    seq_nid = resolve_next(nv)
                    if seq_nid:
                        edges.append((nid, seq_nid, "sequential"))

        self._stmt_at = stmt_at

        # ---- Pass 3: wire Return → post-call ------------------------------------
        adj_no_call = defaultdict(list)
        for src, dst, kind in edges:
            if kind != "call":
                adj_no_call[src].append(dst)

        for callee_label, post_call_nids in call_sites.items():
            callee_entry = label_entry.get(callee_label)
            if not callee_entry:
                continue
            seen: set = set()
            queue = [callee_entry]
            while queue:
                cur = queue.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                if cur in return_nids:
                    for post_nid in post_call_nids:
                        edges.append((cur, post_nid, "return"))
                for nxt in adj_no_call.get(cur, []):
                    if nxt not in seen:
                        queue.append(nxt)

        # ---- Pass 4: back-edge detection (iterative DFS) ------------------------
        succ_map: dict = defaultdict(list)
        for src, dst, kind in edges:
            succ_map[src].append((dst, kind))

        color: dict = {}
        back_edges: set = set()

        def dfs_color(start_nid):
            stack = [(start_nid, iter(succ_map[start_nid]))]
            color[start_nid] = 1
            while stack:
                nid, children = stack[-1]
                try:
                    dst, _ = next(children)
                    if dst not in color:
                        color[dst] = 1
                        stack.append((dst, iter(succ_map[dst])))
                    elif color[dst] == 1:
                        back_edges.add((nid, dst))
                except StopIteration:
                    color[nid] = 2
                    stack.pop()

        start_nid = label_entry.get(start)
        if start_nid:
            dfs_color(start_nid)
        for nid in all_nids:
            if nid not in color:
                dfs_color(nid)

        self._back_edges = back_edges

        # ---- Pass 5: Tarjan SCC (iterative) -------------------------------------
        idx_ctr = [0]
        index: dict = {}
        lowlink: dict = {}
        on_stack: dict = {}
        t_stack: list = []
        sccs: list = []
        scc_of: dict = {}

        def strongconnect(v):
            stack = [(v, iter(succ_map[v]))]
            index[v] = lowlink[v] = idx_ctr[0]
            idx_ctr[0] += 1
            t_stack.append(v)
            on_stack[v] = True
            while stack:
                node, children = stack[-1]
                found = False
                for w, _ in children:
                    found = True
                    if w not in index:
                        index[w] = lowlink[w] = idx_ctr[0]
                        idx_ctr[0] += 1
                        t_stack.append(w)
                        on_stack[w] = True
                        stack.append((w, iter(succ_map[w])))
                    elif on_stack.get(w):
                        lowlink[node] = min(lowlink[node], index[w])
                    break
                if not found:
                    stack.pop()
                    if stack:
                        parent = stack[-1][0]
                        lowlink[parent] = min(lowlink[parent], lowlink[node])
                    if lowlink[node] == index[node]:
                        scc: set = set()
                        while True:
                            w = t_stack.pop()
                            on_stack[w] = False
                            scc.add(w)
                            if w == node:
                                break
                        scc_id = len(sccs)
                        sccs.append(scc)
                        for n in scc:
                            scc_of[n] = scc_id

        for nid in all_nids:
            if nid not in index:
                strongconnect(nid)

        self._cycle_headers = {dst for _, dst in back_edges}
        for ch in self._cycle_headers:
            sid = scc_of.get(ch)
            if sid is not None:
                self._hub_scc[ch] = sccs[sid]

        # ---- Build final succ/pred maps -----------------------------------------
        for src, dst, kind in edges:
            self._succ.setdefault(src, []).append((dst, kind))
            self._pred.setdefault(dst, []).append((src, kind))