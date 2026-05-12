## =============================================================================
## CHRONOLOGY MOD — tl_seen_check.rpy
## Seen-state tracking: descriptors, evaluation, and per-option seen checks.
## =============================================================================

init -2 python:

    def _tl_find_scene_seen_name(start_node, max_hops=80):
        """Find the first translated say-name reachable after a scene node."""
        try:
            _translator = renpy.game.script.translator
        except Exception:
            _translator = None
        node = start_node
        hops = 0
        while node is not None and hops < max_hops:
            stype = type(node).__name__
            if stype in ("Say", "TranslateSay"):
                ident = getattr(node, "identifier", None)
                tr = _translator.lookup_translate(ident) if (_translator and ident) else None
                return getattr(tr, "name", None) or getattr(node, "name", None)
            if stype in ("Jump", "Call", "Return", "Menu"):
                return None
            node = getattr(node, "next", None)
            hops += 1
        return None

    def _tl_first_scene_seen_name(block):
        """Return the first scene-backed seen identity for a branch block."""
        if not block:
            return None
        for node in block:
            if type(node).__name__ == "Scene":
                return _tl_find_scene_seen_name(getattr(node, "next", None))
            if type(node).__name__ in ("Jump", "Call", "Return", "Menu"):
                return None
        return None

    def _tl_scene_ast_id(stmt):
        """Stable structural id for a Scene AST node."""
        if stmt is None:
            return None
        try:
            return (stmt.filename, stmt.linenumber)
        except Exception:
            return None

    def _tl_make_seen_fn(block):
        ## Returns a picklable descriptor tuple, not a lambda.
        ## ("never",)        — always unseen
        ## ("say",  name)    — check persistent._seen_ever
        ## ("label", target) — check renpy.seen_label
        if not block:
            return ("never",)

        def find_check(start_node, max_hops=40):
            node = start_node
            hops = 0
            while node is not None and hops < max_hops:
                stype = type(node).__name__
                if stype == "Say":
                    node_name = getattr(node, "name", None)
                    if node_name is not None:
                        return ("say", node_name)
                    ## Narrator line (no name) — keep walking to find first named say
                elif stype == "Jump":
                    target = getattr(node, "target", None)
                    if target:
                        return ("label", target)
                    return ("never",)
                elif stype == "Call":
                    target = getattr(node, "label", None)
                    if target and isinstance(target, str):
                        return ("label", target)
                    return ("never",)
                elif stype == "Label":
                    target = getattr(node, "name", None)
                    if target and isinstance(target, str):
                        return ("label", target)
                    node = getattr(node, "next", None)
                    hops += 1
                    continue
                elif stype in ("Return", "Menu"):
                    return ("never",)
                node = getattr(node, "next", None)
                hops += 1
            return ("never",)

        for stmt in block:
            return find_check(stmt)
        return ("never",)

    def _tl_make_scene_seen_fn(block):
        """Build a scene-based seen descriptor for branch/ghost checks."""
        _seen_name = _tl_first_scene_seen_name(block)
        if _seen_name:
            return ("say", _seen_name)
        return ("never",)

    def _tl_eval_seen_fn(seen_fn):
        """Evaluate a seen_fn descriptor tuple against live RenPy state."""
        try:
            if seen_fn[0] == "say":
                return bool(seen_fn[1] in (persistent._seen_ever or {}))
            elif seen_fn[0] == "label":
                return renpy.seen_label(seen_fn[1])
        except Exception:
            pass
        return False

    def _tl_option_seen(node, option_index):
        ## Live-AST peek: walk the runtime menu block for the first meaningful
        ## seen target. More accurate than cached descriptors — handles script
        ## changes and correctly skips caption-only rows by visible index.
        try:
            _peek = _tl_option_peek_seen_fn(node, option_index)
            if _peek is not None:
                return _tl_eval_seen_fn(_peek)
        except Exception:
            pass

        ## Direct lookup in persistent._chosen — the authoritative live dict.
        ## ChoiceReturn writes (location, label) → True when any option is chosen.
        ## This is reliable across save/load; cr.chosen (below) is a stale pickle
        ## snapshot and diverges from the live dict after any save/load cycle.
        location = node.get("_location")
        if location is not None and option_index < len(node.get("options", [])):
            label = node["options"][option_index]
            if persistent._chosen and (location, label) in persistent._chosen:
                return True

        ## Legacy fallback: ChoiceReturn.get_chosen() — only reliable within the
        ## same session; kept for nodes where _location is absent (pre-mod saves).
        crs = _tl_runtime_choice_returns(node) or []
        if option_index < len(crs):
            cr = crs[option_index]
            if cr is not None:
                try:
                    return bool(cr.get_chosen())
                except Exception:
                    pass

        ## AST-map fallback (RenPy seen_ever / seen_label)
        key  = node.get("ast_key")
        desc = (_tl_ast_map.get(key, []) if key else [])
        if option_index < len(desc):
            try:
                d = desc[option_index]
                if d[0] == "say":
                    return d[1] in (persistent._seen_ever or {})
                elif d[0] == "label":
                    return renpy.seen_label(d[1])
            except Exception:
                pass
        return False

    def _tl_option_peek_seen_fn(node, option_index):
        """
        Return a live AST seen descriptor for the option's first meaningful content.

        Uses the runtime Ren'Py Menu node so we can inspect the option block directly
        without storing extra metadata on timeline nodes. Caption-only menu rows are
        skipped because they have no block.
        """
        _key = node.get("ast_key")
        if not isinstance(_key, (list, tuple)) or len(_key) != 2:
            return None

        _menu = (_tl_live_menu_lookup() or {}).get(tuple(_key))
        if _menu is None:
            return None

        _visible_index = 0
        for _item in (getattr(_menu, "items", None) or []):
            _block = _item[2] if len(_item) > 2 else None
            if not _block:
                continue
            if _visible_index == option_index:
                _desc = _tl_make_seen_fn(_block)
                if _desc and _desc[0] != "never":
                    return _desc
                return None
            _visible_index += 1
        return None

    def _tl_node_has_new(node):
        ## Skip the chosen option — it's definitively explored (you took that path).
        ## This mirrors the modal's logic (dots hidden for chosen option there too).
        chosen_idx = node.get("chosen_index")
        for i in range(len(node.get("options", []))):
            if i == chosen_idx:
                continue
            if not _tl_option_seen(node, i):
                return True
        return False
