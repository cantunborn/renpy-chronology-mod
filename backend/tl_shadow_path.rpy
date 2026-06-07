## =============================================================================
## CHRONOLOGY MOD — tl_shadow_path.rpy
## Shadow path: replay-aid hint chain and divergence detection after a jump.
## Entries are built from persistent._tl_replay_path in _tl_on_load.
## Entry format: {"index": N, "chosen_index": CI, "ast_key": (file, line)}
## Backward compat: old entries with "menu_site_key" (list or tuple) still match.
## =============================================================================

init -2 python:

    def _tl_shadow_match(shadow_path, node):
        """Return chosen_index from the first entry matching the current node."""
        site_key = _tl_node_menu_site_key(node) if isinstance(node, dict) else None
        for entry in (shadow_path or []):
            entry_sk = entry.get("ast_key") or entry.get("menu_site_key")
            if isinstance(entry_sk, list):
                entry_sk = tuple(entry_sk)
            if site_key is not None and entry_sk == site_key:
                return entry.get("chosen_index")
        return None

    def _tl_consume_shadow_path(shadow_path, node, chosen_index):
        """
        Consume shadow path entries up to and including the first entry matching node.
        Returns (new_path_or_none, diverged_orig_ci_or_none, match_mode_or_none).
        Breaks on first match; tail is a slice. Replaces _tl_shadow_match_mode.
        Backward compat: entries with "menu_site_key" (list or tuple) match via ast_key node.
        """
        if not shadow_path:
            return shadow_path, None, None
        site_key = _tl_node_menu_site_key(node) if isinstance(node, dict) else None
        for i, entry in enumerate(shadow_path):
            entry_sk = entry.get("ast_key") or entry.get("menu_site_key")
            if isinstance(entry_sk, list):
                entry_sk = tuple(entry_sk)
            if site_key is not None and entry_sk == site_key:
                orig_ci  = entry.get("chosen_index")
                new_sp   = shadow_path[i + 1:] or None
                diverged = orig_ci if orig_ci != chosen_index else None
                return new_sp, diverged, "ast_key"
        return shadow_path, None, None
