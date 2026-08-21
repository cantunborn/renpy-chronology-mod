# Non-Intrusiveness Audit

This document records every place the mod touches shared Ren'Py state: monkey-patches, store/config mutations, and persistent key usage. The findings are clean — no action items, only documentation.

## Monkey-patches

### `renpy.ast.If.execute`

**File:** `backend/tl_ghost_logic_ren.py`

```python
_tl_orig_if_execute = _tl_renpy_ast.If.execute

def _tl_if_execute_patched(self):
    ...
    _tl_orig_if_execute(self)   # always called
    ...

_tl_renpy_ast.If.execute = _tl_if_execute_patched
```

- Saves original before replacing.
- Evaluates the taken branch descriptor **before** calling the original (snapshot pre-execute state for seen-check accuracy).
- Calls original unconditionally — game logic is unchanged.
- Work done after original: ghost synthesis and notification, both side-effect-only (no return value to preserve).
- Guard: `_tl_should_track_if_node(if_node)` skips mod files and Ren'Py internals.

### `renpy.ast.Python.execute`

**File:** `backend/tl_route_logic_ren.py`

```python
_tl_orig_python_execute = _tl_route_renpy_ast.Python.execute

def _tl_python_execute_patched(self):
    if renpy.is_init_phase() or not _tl_is_game_file(getattr(self, "filename", None) or ""):
        return _tl_orig_python_execute(self)
    snap = _tl_py_pre_var_snap(self)
    _tl_orig_python_execute(self)   # always called
    _tl_py_post_var_diff(snap)

_tl_route_renpy_ast.Python.execute = _tl_python_execute_patched
```

- Saves original before replacing.
- Guard conditions (any true → no mod work, just call original):
  - `renpy.is_init_phase()` — skips all init-phase execution
  - `_tl_is_game_file(filename)` false — skips Ren'Py internals and mod files
- `_tl_py_pre_var_snap`: intersects `co_names` with route var frozenset; snapshots only vars this block might touch (~0–5). Returns `None` if intersection empty, hide-mode block, or route vars not yet built.
- `_tl_py_post_var_diff`: diffs snapshotted vars; updates `_tl_recently_changed_vars` always; emits pending delta only when `_tl_var_notifs_enabled`.
- Calls original unconditionally in both paths.
- No modification to the return value (Python.execute returns None).

## Store function replacements

### `renpy.exports.menu` and `renpy.store.menu`

**File:** `timeline_hooks_ren.py`

```python
_tl_orig_exports_menu = renpy.exports.menu
_tl_orig_store_menu   = store.menu

renpy.exports.menu = _tl_exports_wrapper
store.menu         = _tl_store_wrapper
```

- Both originals are saved before replacement.
- `_tl_exports_wrapper` calls `_tl_orig_exports_menu(...)` and returns its result unchanged.
- `_tl_store_wrapper` calls `_tl_orig_store_menu(...)` and returns its result unchanged.
- The `hooks` in-game test suite verifies both wrappers are applied exactly once.

## Config mutations

### `config.skipping`

**File:** `timeline_hooks_ren.py` / `backend/tl_saveload_ren.py`

Temporarily set to `True` during replay to enable fast-forward through the shadow path. Cleared after replay ends (`_tl_cancel_replay()` / load callback). This is the minimum intrusion needed for the replay feature — no alternative exists in the Ren'Py API.

### `config.keymap`

**Files:** `timeline_screen.rpy`, `ui/tl_debug.rpy`

```python
config.keymap["chronology_toggle"] = ["t"]
config.keymap["chronology_route"]  = ["r"]
config.keymap["tl_debug_toggle"]   = ["K_BACKQUOTE"]
```

Three new keymap entries. Keys `t`, `r`, and backtick are not used by standard Ren'Py. Games that already bind these would conflict, but this is a standard Ren'Py extension pattern.

### `config.start_callbacks`, `config.after_load_callbacks`, etc.

The mod appends its own callbacks:
- `config.start_callbacks.append(_tl_on_game_start)`
- `config.after_load_callbacks.append(_tl_on_load)`
- `config.after_load_callbacks.append(_tl_validate_on_load)`
- `config.interact_callbacks.append(_tl_interact_callback)`
- `config.label_callbacks.append(_tl_chapter_label_cb)`

These are append-only — existing callbacks are unaffected.

## Namespace safety

**`default` declarations (21 total)**: all use `_tl_` prefix.

**`persistent.*` keys**: all use `_tl_` prefix. Full list:
`_tl_replaying`, `_tl_thumb_cache`, `_tl_asset_thumb_cache`, `_tl_img_movie_cache`, `_tl_pending_shadow_path`, `_tl_menu_scene_map`, `_tl_scene_map_version`, `_tl_recovery_slot`, `_tl_replay_slot`, `_tl_replay_path`, `_tl_replay_target`, `_tl_prev_thumb`, `_tl_route_var_names`, `_tl_var_if_count`, `_tl_if_key_to_vars`, `_tl_var_domain`, `_tl_var_is_numeric`.

**Store vars**: all use `_tl_` prefix. Transient vars are re-initialized each session and do not appear in save data.

## Save/load compatibility

**Defensive initialization pattern**: persistent keys are only written if absent or None:
```python
if not hasattr(persistent, "_tl_route_var_names"):
    persistent._tl_route_var_names = []
```

**History node access**: all new optional fields accessed with `.get(key) or default` so old saves (missing the key) behave identically to before:
```python
node.get("_locked_options") or []
node.get("affecting_vars") or []
```

**`default` declarations**: Ren'Py's `default` statement fills missing store vars from saves that predate them, so all transient store vars are safe across version upgrades.

**Mod added to existing save**: state starts empty, recording begins from the installation point forward. No crash, no corruption.

**Mod removed from save with data**: Ren'Py ignores unknown `_tl_*` persistent/store keys. No crash.

## Known ecosystem risk

If another mod also monkey-patches `If.execute` or `Python.execute`, both mods must use the "save original and call it" pattern. This mod uses the correct pattern. Whether other mods do is outside this mod's control — this is an unavoidable Ren'Py ecosystem constraint with no mitigation available at the mod level.