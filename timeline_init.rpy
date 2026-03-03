## =============================================================================
## CHRONOLOGY MOD — timeline_init.rpy
## Store variables, persistent data, constants, and utility functions.
## =============================================================================

init -1 python:

    import os, uuid

    ## Thumbnail dimensions
    TL_THUMB_WIDTH  = 320
    TL_THUMB_HEIGHT = 180

    ## -------------------------------------------------------------------------
    ## Font size constants
    ## -------------------------------------------------------------------------
    TL_SIZE_BODY   = 21   ## all regular text — options, labels, buttons
    TL_SIZE_TITLE  = 38   ## "CHRONOLOGY" header
    TL_SIZE_DOT    = 14   ## ● indicator dots
    TL_SIZE_BADGE  = 12   ## small labels (unused for NOW badge which uses BODY)
    TL_SIZE_HEADER = 28   ## modal "All options" header


## Per-save variables — safe to load on saves that predate the mod
default _tl_history    = []   ## list of node dicts
default _tl_branch_id  = ""   ## unique branch ID, set on first menu
default _tl_context    = []   ## [(prompt, chosen_index), ...] unused currently
default _tl_node_count = 0

## UI state — not saved
default _tl_modal_node = None   ## node whose modal is currently open
default _tl_ast_ready  = False  ## True once AST map is built
default _tl_ast_map    = {}     ## {(filename, line): [seen_fn, ...]} — RenPy 7 fallback


init -1 python:

    def _tl_new_branch_id():
        return uuid.uuid4().hex[:12]

    def _tl_capture_thumbnail():
        try:
            return renpy.screenshot_to_bytes((TL_THUMB_WIDTH, TL_THUMB_HEIGHT))
        except Exception as e:
            renpy.log("TL screenshot failed: {}".format(e))
            return None

    def _tl_thumb_displayable(thumb_bytes, index):
        """
        im.Data is available in RenPy 7 and kept as a compat shim in RenPy 8.
        """
        try:
            return im.Data(thumb_bytes, "tl_t_{}.png".format(index))
        except Exception as e:
            renpy.log("TL thumb displayable failed: {}".format(e))
            return None

    ## -------------------------------------------------------------------------
    ## AST-based seen checking — RenPy 7 fallback only.
    ## RenPy 8 uses ChoiceReturn.get_chosen() instead (see _tl_option_seen).
    ## -------------------------------------------------------------------------

    def _tl_build_ast_map():
        """
        Walk renpy.game.script.namemap (flat dict of all named nodes) and build
        a map of seen-checker functions for each menu option.
        Only used on RenPy 7 where ChoiceReturn is unavailable.
        """
        try:
            namemap = renpy.game.script.namemap
        except Exception as e:
            renpy.log("TL AST: namemap not available: {}".format(e))
            store._tl_ast_ready = True
            return

        nodes = list(namemap.values())
        if not nodes:
            store._tl_ast_ready = True
            return

        renpy.log("TL AST: scanning {} named nodes".format(len(nodes)))
        ast_map = {}

        for node in nodes:
            if type(node).__name__ != "Menu":
                continue

            key      = (node.filename, node.linenumber)
            seen_fns = []

            for item in node.items:
                block = item[2] if len(item) > 2 else None
                if not block:
                    continue
                seen_fns.append(_tl_make_seen_fn(block))

            if seen_fns:
                ast_map[key] = seen_fns

        store._tl_ast_map   = ast_map
        store._tl_ast_ready = True
        renpy.log("TL AST done: {} menus".format(len(ast_map)))


    def _tl_make_seen_fn(block):
        """
        Given an option block (list of AST nodes), return a zero-arg callable
        that returns True if this branch has ever been visited.
        Walks .next pointers to find the first Say/Jump/Call.
        """
        if not block:
            return lambda: False

        def find_check(start_node, max_hops=40):
            node = start_node
            hops = 0
            while node is not None and hops < max_hops:
                stype = type(node).__name__

                if stype == "Say":
                    node_name = getattr(node, "name", None)
                    if node_name is not None:
                        return lambda n=node_name: n in (persistent._seen_ever or {})
                    return lambda: False

                elif stype == "Jump":
                    target = getattr(node, "target", None)
                    if target:
                        return lambda t=target: renpy.seen_label(t)
                    return lambda: False

                elif stype == "Call":
                    target = getattr(node, "label", None)
                    if target and isinstance(target, str):
                        return lambda t=target: renpy.seen_label(t)
                    return lambda: False

                elif stype == "Label":
                    target = getattr(node, "name", None)
                    if target and isinstance(target, str):
                        return lambda t=target: renpy.seen_label(t)
                    node = getattr(node, "next", None)
                    hops += 1
                    continue

                elif stype in ("Return", "Menu"):
                    return lambda: False

                node = getattr(node, "next", None)
                hops += 1

            return lambda: False

        for stmt in block:
            return find_check(stmt)

        return lambda: False


    def _tl_option_seen(node, option_index):
        """
        Returns True if this option has been chosen in any previous playthrough.

        RenPy 8: uses ChoiceReturn.get_chosen(), which checks persistent._chosen
        keyed by (location, label). Populated by RenPy itself on every choice.

        RenPy 7 fallback: AST walk to find first Say/Jump and check _seen_ever
        or seen_label.
        """
        ## RenPy 8 primary path
        crs = node.get("_choice_returns", [])
        if option_index < len(crs):
            cr = crs[option_index]
            if cr is not None:
                try:
                    return bool(cr.get_chosen())
                except Exception:
                    pass

        ## RenPy 7 fallback
        key      = node.get("ast_key")
        seen_fns = _tl_ast_map.get(key, []) if key else []
        if option_index < len(seen_fns):
            try:
                return seen_fns[option_index]()
            except Exception:
                return False
        return False


    def _tl_node_has_new(node):
        """True if any option in this node has never been seen."""
        for i in range(len(node.get("options", []))):
            if not _tl_option_seen(node, i):
                return True
        return False
