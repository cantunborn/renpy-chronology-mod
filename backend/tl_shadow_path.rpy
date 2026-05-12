## =============================================================================
## CHRONOLOGY MOD — tl_shadow_path.rpy
## Shadow path: replay-aid hint chain built from history after a jump target.
## Also: shadow match mode helper used by hooks.
## =============================================================================

init -2 python:

    def _tl_build_shadow_path(history, node_index):
        """Build replay-aid shadow entries from history nodes after node_index."""
        _path = []
        _past = False
        for _n in history or []:
            if _past:
                _site_key = _tl_node_menu_site_key(_n)
                _loc = _n.get("_location")
                _ci  = _n.get("chosen_index")
                if _ci is None:
                    continue
                if _site_key is None and _loc is None:
                    continue
                _entry = {"chosen_index": _ci}
                if _site_key is not None:
                    _entry["menu_site_key"] = list(_site_key)
                if _loc is not None:
                    _entry["location"] = _loc
                _path.append(_entry)
            elif _n["index"] == node_index:
                _past = True
        return _path

    def _tl_stage_shadow_path(history, node_index):
        """Return the staged shadow-path payload persisted across jump loads."""
        _path = _tl_build_shadow_path(history, node_index)
        return _path or None

    def _tl_shadow_match(shadow_path, node):
        """Return chosen_index from the first entry matching the current node."""
        _site_key = _tl_node_menu_site_key(node) if isinstance(node, dict) else None
        _location = node.get("_location") if isinstance(node, dict) else node
        for _entry in (shadow_path or []):
            _entry_site = _entry.get("menu_site_key")
            if isinstance(_entry_site, list):
                _entry_site = tuple(_entry_site)
            if _site_key is not None and _entry_site == _site_key:
                return _entry.get("chosen_index")
            if _site_key is None and _entry.get("location") == _location:
                return _entry.get("chosen_index")
        return None

    def _tl_consume_shadow_path(shadow_path, node, chosen_index):
        """
        Consume shadow path entries up to and including the first entry matching node.
        Returns (new_path_or_none, diverged_orig_ci_or_none).
        diverged_orig_ci is set only when the matched entry's chosen_index differs from
        chosen_index; None when choices match or no entry matched.
        """
        if not shadow_path:
            return shadow_path, None
        _site_key = _tl_node_menu_site_key(node) if isinstance(node, dict) else None
        _location = node.get("_location") if isinstance(node, dict) else node
        new_sp  = []
        matched = False
        orig_ci = None
        for e in shadow_path:
            _entry_site = e.get("menu_site_key")
            if isinstance(_entry_site, list):
                _entry_site = tuple(_entry_site)
            _site_match = (_site_key is not None and _entry_site == _site_key)
            _loc_match  = (_site_key is None and e.get("location") == _location)
            if not matched and (_site_match or _loc_match):
                matched = True
                orig_ci = e.get("chosen_index")
            elif matched:
                new_sp.append(e)
        if not matched:
            return shadow_path, None
        diverged_ci = orig_ci if orig_ci != chosen_index else None
        return new_sp or None, diverged_ci

    def _tl_shadow_match_mode(shadow_path, node):
        """Return which key type matched: 'menu_site_key', '_location', or None."""
        if not shadow_path or not isinstance(node, dict):
            return None
        site_key = _tl_node_menu_site_key(node)
        location = node.get("_location")
        for entry in shadow_path:
            entry_site = entry.get("menu_site_key")
            if isinstance(entry_site, list):
                entry_site = tuple(entry_site)
            if site_key is not None and entry_site == site_key:
                return "menu_site_key"
            if site_key is None and entry.get("location") == location:
                return "_location"
        return None
