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
                return _tl_say_seen_name(node)
            if stype in ("Jump", "Call", "Return", "Menu"):
                return None
            node = getattr(node, "next", None)
            hops += 1
        return None

    def _tl_say_seen_name(node):
        """Resolve the correct seen key for a Say or TranslateSay node.

        RenPy 8.5.2+: return identifier string; eval uses renpy.seen_translation().
        Older RenPy: return node.name tuple; eval checks _seen_ever directly.
        Translated games: resolve to TranslateSay node for old RenPy fallback.
        """
        _ident = getattr(node, "identifier", None)
        if _ident and getattr(renpy, "seen_translation", None):
            return _ident
        ## Old RenPy: resolve translator node for translated games, fall back to node.
        try:
            _translator = renpy.game.script.translator
        except Exception:
            _translator = None
        _tr = _translator.lookup_translate(_ident) if (_translator and _ident) else None
        _seen_node = _tr if (_tr is not None and not isinstance(_tr, tuple)) else node
        return getattr(_seen_node, "name", None) or getattr(node, "name", None)

    def _tl_follow_jump_seen_name(target, max_hops=30):
        """Follow a Jump/Call target label one hop and return the first Say's
        translator-resolved name, or None if no Say is found.

        Used so that option blocks that are purely Python + Jump can use a
        language-specific _seen_ever check instead of renpy.seen_label, which
        is language-agnostic and causes false positives when the player visited
        the target label in a different locale.
        """
        try:
            _namemap = renpy.game.script.namemap
            _label_node = _namemap.get(target)
            if _label_node is None:
                return None
            _node = getattr(_label_node, "next", None)
            _hops = 0
            while _node is not None and _hops < max_hops:
                _stype = type(_node).__name__
                if _stype in ("Say", "TranslateSay"):
                    return _tl_say_seen_name(_node)
                if _stype in ("Jump", "Call", "Return", "Menu", "Label"):
                    return None
                _node = getattr(_node, "next", None)
                _hops += 1
        except Exception:
            pass
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
        ## Iterates block directly — never walks via .next into post-menu shared code.
        ##
        ## Priority: Say/TranslateSay range > first Scene > first expr-Show > jump label > ("never",)
        ## Plain Show (character overlay, no expression args) is ignored — shared across branches.
        ## Show with expression args (ParameterizedText) IS branch-specific: _seen_images stores
        ## raw imspec parts as-is, so the tuple can be passed directly to renpy.seen_image.
        ##
        ## ("never",)                  — always unseen (fall through to persistent._chosen)
        ## ("say",  name)              — single translator-resolved name in _seen_ever
        ## ("say_range", first, last)  — first + last Say names; first=fast lock check,
        ##                               last=full-traversal confirmation
        ## ("image", name_tuple)       — Scene bg or expr-Show; renpy.seen_image with raw parts
        ## ("label", target)           — renpy.seen_label (no Say/Scene before Jump/Call)
        if not block:
            return ("never",)

        _say_first  = None   ## first Say/TranslateSay resolved name
        _say_last   = None   ## last Say/TranslateSay resolved name (overwritten each time)
        _scene_best = None   ## first Scene background — image fallback
        _show_best  = None   ## first expr-Show — ParameterizedText fallback

        def _make_say_result():
            if _say_first is None:
                return None
            if _say_last != _say_first:
                return ("say_range", _say_first, _say_last)
            return ("say", _say_first)

        for _node in block:
            _stype = type(_node).__name__
            if _stype in ("Say", "TranslateSay"):
                _key = _tl_say_seen_name(_node)
                if _key is not None:
                    if _say_first is None:
                        _say_first = _key
                    _say_last = _key
            elif _stype == "Scene" and _scene_best is None:
                _img = _tl_scene_stmt_img_name(_node)
                if _img:
                    _scene_best = ("image", tuple(_img.split()))
            elif _stype == "Show" and _show_best is None:
                _sp = getattr(_node, "imspec", None)
                if _sp and _sp[0]:
                    _parts = tuple(str(_p) for _p in _sp[0])
                    ## Only use for shows whose name contains expression args (has '(').
                    ## Plain shows like `show eileen happy` are character overlays shared
                    ## across many branches — branch-ambiguous, skip them.
                    ## _seen_images stores raw imspec parts as-is, so no eval needed.
                    if any("(" in _p for _p in _parts):
                        _show_best = ("image", _parts)
            elif _stype == "Jump":
                _target = getattr(_node, "target", None)
                _followed = _tl_follow_jump_seen_name(_target) if _target else None
                _lbl = ("say", _followed) if _followed else (("label", _target) if _target else ("never",))
                return _make_say_result() or _scene_best or _show_best or _lbl
            elif _stype == "Call":
                _target = getattr(_node, "label", None) if isinstance(getattr(_node, "label", None), str) else None
                _followed = _tl_follow_jump_seen_name(_target) if _target else None
                _lbl = ("say", _followed) if _followed else (("label", _target) if _target else ("never",))
                return _make_say_result() or _scene_best or _show_best or _lbl
            elif _stype in ("Return", "Menu"):
                return _make_say_result() or _scene_best or _show_best or ("never",)
            ## Python, If, With, plain Show, etc — skip
        return _make_say_result() or _scene_best or _show_best or ("never",)

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
                _key = seen_fn[1]
                if isinstance(_key, str):
                    return renpy.seen_translation(_key)
                return bool(_key in (persistent._seen_ever or {}))
            elif seen_fn[0] == "say_range":
                _k1, _k2 = seen_fn[1], seen_fn[2]
                if isinstance(_k1, str):
                    ## Fast path: first node not seen → definitely unseen.
                    if not renpy.seen_translation(_k1):
                        return False
                    ## First seen → confirm full traversal via last node.
                    return renpy.seen_translation(_k2)
                _ever = persistent._seen_ever or {}
                if _k1 not in _ever:
                    return False
                return bool(_k2 in _ever)
            elif seen_fn[0] == "image":
                return renpy.seen_image(seen_fn[1])
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
                _r = _tl_eval_seen_fn(_peek)
                if TL_DEBUG_SEEN:
                    _tl_log("TL opt_seen: node={} opt={} src=peek desc={} result={}".format(
                        node.get("index"), option_index, _peek, _r))
                return _r
        except Exception as _e:
            _tl_log("TL opt_seen peek_err: node={} opt={} err={}".format(node.get("index"), option_index, _e))

        ## Direct lookup in persistent._chosen — the authoritative live dict.
        ## ChoiceReturn writes (location, label) → True when any option is chosen.
        ## This is reliable across save/load; cr.chosen (below) is a stale pickle
        ## snapshot and diverges from the live dict after any save/load cycle.
        location = node.get("_location")
        if location is not None and option_index < len(node.get("options", [])):
            label = node["options"][option_index]
            if persistent._chosen and (location, label) in persistent._chosen:
                if TL_DEBUG_SEEN:
                    _tl_log("TL opt_seen: node={} opt={} src=chosen loc={} label={} result=True".format(
                        node.get("index"), option_index, location, repr(label)))
                return True

        ## Legacy fallback: ChoiceReturn.get_chosen() — only reliable within the
        ## same session; kept for nodes where _location is absent (pre-mod saves).
        crs = _tl_runtime_choice_returns(node) or []
        if option_index < len(crs):
            cr = crs[option_index]
            if cr is not None:
                try:
                    _r = bool(cr.get_chosen())
                    if _r and TL_DEBUG_SEEN:
                        _tl_log("TL opt_seen: node={} opt={} src=cr result=True".format(
                            node.get("index"), option_index))
                    return _r
                except Exception:
                    pass

        if TL_DEBUG_SEEN:
            _tl_log("TL opt_seen: node={} opt={} src=none result=False".format(
                node.get("index"), option_index))
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
            if TL_DEBUG_SEEN:
                _tl_log("TL peek_seen: node={} opt={} key={} menu_lookup=None".format(
                    node.get("index"), option_index, _key))
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
