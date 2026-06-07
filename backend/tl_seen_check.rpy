## =============================================================================
## CHRONOLOGY MOD — tl_seen_check.rpy
## Seen-state tracking: descriptors, evaluation, and per-option seen checks.
## =============================================================================

init -2 python:

    def _tl_find_scene_seen_name(start_node, max_hops=80):
        """Find the first translated say-name reachable after a scene node."""
        try:
            translator = renpy.game.script.translator
        except Exception as e:
            _tl_log("TL find_scene_seen_name: translator unavailable: {}".format(e))
            translator = None
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
        ident = getattr(node, "identifier", None)
        if ident and getattr(renpy, "seen_translation", None):
            return ident
        ## Old RenPy: resolve translator node for translated games, fall back to node.
        try:
            translator = renpy.game.script.translator
        except Exception as e:
            _tl_log("TL say_seen_name: translator unavailable: {}".format(e))
            translator = None
        translated_node = translator.lookup_translate(ident) if (translator and ident) else None
        seen_node = translated_node if (translated_node is not None and not isinstance(translated_node, tuple)) else node
        return getattr(seen_node, "name", None) or getattr(node, "name", None)

    def _tl_follow_jump_seen_name(target, max_hops=30):
        """Follow a Jump/Call target label one hop and return the first Say's
        translator-resolved name, or None if no Say is found.

        Used so that option blocks that are purely Python + Jump can use a
        language-specific _seen_ever check instead of renpy.seen_label, which
        is language-agnostic and causes false positives when the player visited
        the target label in a different locale.
        """
        try:
            namemap = renpy.game.script.namemap
            label_node = namemap.get(target)
            if label_node is None:
                return None
            node = getattr(label_node, "next", None)
            hops = 0
            while node is not None and hops < max_hops:
                node_type = type(node).__name__
                if node_type in ("Say", "TranslateSay"):
                    return _tl_say_seen_name(node)
                if node_type in ("Jump", "Call", "Return", "Menu", "Label"):
                    return None
                node = getattr(node, "next", None)
                hops += 1
        except Exception as e:
            _tl_log("TL follow_jump_seen_name failed for '{}': {}".format(target, e))
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

        say_first  = None   ## first Say/TranslateSay resolved name
        say_last   = None   ## last Say/TranslateSay resolved name (overwritten each time)
        scene_best = None   ## first Scene background — image fallback
        show_best  = None   ## first expr-Show — ParameterizedText fallback

        def _make_say_result():
            if say_first is None:
                return None
            if say_last != say_first:
                return ("say_range", say_first, say_last)
            return ("say", say_first)

        for node in block:
            node_type = type(node).__name__
            if node_type in ("Say", "TranslateSay"):
                seen_key = _tl_say_seen_name(node)
                if seen_key is not None:
                    if say_first is None:
                        say_first = seen_key
                    say_last = seen_key
            elif node_type == "Scene" and scene_best is None:
                img = _tl_scene_stmt_img_name(node)
                if img:
                    scene_best = ("image", tuple(img.split()))
            elif node_type == "Show" and show_best is None:
                imspec = getattr(node, "imspec", None)
                if imspec and imspec[0]:
                    parts = tuple(str(p) for p in imspec[0])
                    ## Only use for shows whose name contains expression args (has '(').
                    ## Plain shows like `show eileen happy` are character overlays shared
                    ## across many branches — branch-ambiguous, skip them.
                    ## _seen_images stores raw imspec parts as-is, so no eval needed.
                    if any("(" in p for p in parts):
                        show_best = ("image", parts)
            elif node_type == "Jump":
                target = getattr(node, "target", None)
                followed = _tl_follow_jump_seen_name(target) if target else None
                result_lbl = ("say", followed) if followed else (("label", target) if target else ("never",))
                return _make_say_result() or scene_best or show_best or result_lbl
            elif node_type == "Call":
                target = getattr(node, "label", None) if isinstance(getattr(node, "label", None), str) else None
                followed = _tl_follow_jump_seen_name(target) if target else None
                result_lbl = ("say", followed) if followed else (("label", target) if target else ("never",))
                return _make_say_result() or scene_best or show_best or result_lbl
            elif node_type in ("Return", "Menu"):
                return _make_say_result() or scene_best or show_best or ("never",)
            ## Python, If, With, plain Show, etc — skip
        return _make_say_result() or scene_best or show_best or ("never",)

    def _tl_make_scene_seen_fn(block):
        """Build a scene-based seen descriptor for branch/ghost checks."""
        seen_name = _tl_first_scene_seen_name(block)
        if seen_name:
            return ("say", seen_name)
        return ("never",)

    def _tl_eval_seen_fn(seen_fn):
        """Evaluate a seen_fn descriptor tuple against live RenPy state."""
        try:
            if seen_fn[0] == "say":
                seen_key = seen_fn[1]
                if isinstance(seen_key, str):
                    return renpy.seen_translation(seen_key)
                return bool(seen_key in (persistent._seen_ever or {}))
            elif seen_fn[0] == "say_range":
                first_key, last_key = seen_fn[1], seen_fn[2]
                if isinstance(first_key, str):
                    ## Fast path: first node not seen → definitely unseen.
                    if not renpy.seen_translation(first_key):
                        return False
                    ## First seen → confirm full traversal via last node.
                    return renpy.seen_translation(last_key)
                seen_ever = persistent._seen_ever or {}
                if first_key not in seen_ever:
                    return False
                return bool(last_key in seen_ever)
            elif seen_fn[0] == "image":
                return renpy.seen_image(seen_fn[1])
            elif seen_fn[0] == "label":
                return renpy.seen_label(seen_fn[1])
        except Exception as e:
            _tl_log("TL eval_seen_fn failed: desc={} err={}".format(seen_fn, e))
        return False

    def _tl_option_seen(node, option_index):
        ## Live-AST peek: walk the runtime menu block for the first meaningful
        ## seen target. More accurate than cached descriptors — handles script
        ## changes and correctly skips caption-only rows by visible index.
        try:
            peek = _tl_option_peek_seen_fn(node, option_index)
            if peek is not None:
                result = _tl_eval_seen_fn(peek)
                if TL_DEBUG_SEEN:
                    _tl_log("TL opt_seen: node={} opt={} src=peek desc={} result={}".format(
                        node.get("index"), option_index, peek, result))
                return result
        except Exception as e:
            _tl_log("TL opt_seen peek_err: node={} opt={} err={}".format(node.get("index"), option_index, e))

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
                    result = bool(cr.get_chosen())
                    if result and TL_DEBUG_SEEN:
                        _tl_log("TL opt_seen: node={} opt={} src=cr result=True".format(
                            node.get("index"), option_index))
                    return result
                except Exception as e:
                    _tl_log("TL opt_seen cr.get_chosen failed: node={} opt={} err={}".format(
                        node.get("index"), option_index, e))

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
        ast_key = node.get("ast_key")
        if not isinstance(ast_key, (list, tuple)) or len(ast_key) != 2:
            return None

        menu = (_tl_live_menu_lookup() or {}).get(tuple(ast_key))
        if menu is None:
            if TL_DEBUG_SEEN:
                _tl_log("TL peek_seen: node={} opt={} key={} menu_lookup=None".format(
                    node.get("index"), option_index, ast_key))
            return None

        visible_index = 0
        for item in (getattr(menu, "items", None) or []):
            block = item[2] if len(item) > 2 else None
            if not block:
                continue
            if visible_index == option_index:
                desc = _tl_make_seen_fn(block)
                if desc and desc[0] != "never":
                    return desc
                return None
            visible_index += 1
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
