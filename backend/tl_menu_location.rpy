## =============================================================================
## CHRONOLOGY MOD — tl_menu_location.rpy
## Menu location resolution: stable identity keys for history nodes.
## =============================================================================

init -2 python:

    def _tl_normalize_script_path(path):
        """Normalize script paths so runtime and dumped AST paths can be joined."""
        if not isinstance(path, str):
            return path
        if not path.startswith("game/") and "/" in path:
            path = "game/" + path
        if path.endswith(".rpyc"):
            return path[:-1]
        return path

    def _tl_menu_site_key(file_path, line_no):
        """Build a normalized persistent menu-image key from file/line data."""
        if not file_path or not line_no:
            return None
        return (_tl_normalize_script_path(file_path), line_no)

    def _tl_location_menu_ast_key(location):
        """Resolve a runtime `_location` tuple to the real Menu `(file, line)` key when possible."""
        if not isinstance(location, tuple):
            return None
        try:
            node = renpy.game.script.namemap.get(location)
            if node is not None and type(node).__name__ == "Menu":
                return _tl_menu_site_key(getattr(node, "filename", None), getattr(node, "linenumber", None))
        except Exception as e:
            _tl_log("TL menu_ast_key lookup failed: {}".format(e))
        return None

    def _tl_location_menu_site_key(location):
        """Return the normalized menu-site key from a runtime `_location` tuple."""
        menu_key = _tl_location_menu_ast_key(location)
        if menu_key is not None:
            return menu_key
        if not isinstance(location, tuple) or len(location) < 3:
            return None
        return _tl_menu_site_key(location[0], location[2])

    def _tl_node_menu_site_key(node):
        """Best-effort stable menu-site identity for a history node."""
        if not isinstance(node, dict):
            return None
        ast_key = node.get("ast_key")
        if isinstance(ast_key, (list, tuple)) and len(ast_key) == 2:
            return _tl_menu_site_key(ast_key[0], ast_key[1])
        return _tl_location_menu_site_key(node.get("_location"))

    def _tl_live_menu_lookup():
        """Return a lazy `(file, line) -> live Menu node` map from Ren'Py namemap."""
        rt_cache = _tl_runtime_cache_store()
        if "live_menu_lookup" in rt_cache:
            return rt_cache["live_menu_lookup"]
        lookup = {}
        try:
            namemap = renpy.game.script.namemap
        except Exception as e:
            _tl_log("TL option peek: namemap not available: {}".format(e))
            rt_cache["live_menu_lookup"] = {}
            return rt_cache["live_menu_lookup"]

        for node in namemap.values():
            if type(node).__name__ != "Menu":
                continue
            key = _tl_stmt_ast_key(node)
            if key and key not in lookup:
                lookup[key] = node

        rt_cache["live_menu_lookup"] = lookup
        return rt_cache["live_menu_lookup"]
