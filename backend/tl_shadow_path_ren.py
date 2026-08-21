## =============================================================================
## CHRONOLOGY MOD — tl_shadow_path_ren.py
## Shadow path: replay-aid hint chain and divergence detection after a jump.
## Entries are built from persistent._tl_replay_path in _tl_on_load.
## Entry format: {"index": N, "chosen_index": CI, "ast_key": (file, line)}
## Backward compat: old entries with "menu_site_key" (list or tuple) still match.
## =============================================================================

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Tuple
    from tl_menu_location_ren import _tl_node_menu_site_key  # type-check-only; injected into store namespace at runtime
    from timeline_init_ren import _tl_log  # type-check-only; injected into store namespace at runtime

"""renpy
init -2 python:
"""

def _entry_key(entry):  # type: (dict) -> Optional[tuple]
    """Return normalized site key from a shadow path entry (tuple or None)."""
    key = entry.get("ast_key") or entry.get("menu_site_key")
    return tuple(key) if isinstance(key, list) else key

def _tl_shadow_match(shadow_path, node):  # type: (Optional[list], Optional[dict]) -> Optional[int]
    """Return chosen_index from the first entry matching the current node, or None."""
    site_key = _tl_node_menu_site_key(node) if isinstance(node, dict) else None
    for entry in (shadow_path or []):
        if site_key is not None and _entry_key(entry) == site_key:
            return entry.get("chosen_index")
    return None

def _tl_consume_shadow_path(shadow_path, node, chosen_index):  # type: (Optional[list], Optional[dict], Optional[int]) -> Tuple[Optional[list], Optional[int], Optional[str]]
    """
    Consume shadow path entries up to and including the first entry matching node.
    Returns (new_path_or_none, diverged_orig_ci_or_none, match_mode_or_none).

    On match: discards all entries before and including the match; returns the
    tail as the new path (None when exhausted). If the player chose differently
    from the shadow, returns the original chosen_index as diverged_orig_ci.
    Backward compat: old entries with "menu_site_key" (list or tuple) match via ast_key.
    """
    if not shadow_path:
        return shadow_path, None, None
    site_key = _tl_node_menu_site_key(node) if isinstance(node, dict) else None
    for i, entry in enumerate(shadow_path):
        if site_key is not None and _entry_key(entry) == site_key:
            orig_chosen = entry.get("chosen_index")
            remaining   = shadow_path[i + 1:] or None
            diverged    = orig_chosen if orig_chosen != chosen_index else None
           
            _tl_log("TL shadow match: node={} via=ast_key site={} div={}".format(
                node.get("index") if isinstance(node, dict) else "?",
                site_key, diverged))
            return remaining, diverged, "ast_key"
    
    _tl_log("TL shadow no-match: node={} sp_first={}".format(
        node.get("index") if isinstance(node, dict) else "?",
        _entry_key(shadow_path[0]) if shadow_path else None))
    return shadow_path, None, None
