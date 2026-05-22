# Route Tracker

The route tracker is a second tab in the timeline UI (key `R`) that shows which story route the player is on. It displays a chip bar of tracked route variables and their current values, highlights variables that gate upcoming ghost-card branches, and fires in-game notifications when variables change.

## What it is

- **Chip bar**: one chip per tracked variable showing `VarName: value`. Variables that gate upcoming branches (ghost vars) and recently-changed variables are always shown and sorted first.
- **Domain tooltip**: hovering a chip shows all known values for that variable with the current value marked `→`.
- **Var change notifications**: when a Python block in the game changes a tracked variable, a toast (`_tl_notify` screen) fires immediately: `↑ Affection` or `Route → romance`, or batched: `↑ Affection · Route → romance`.

## Data pipeline

### 1. AST walk → persistent index

`_tl_build_route_index(nodes)` is called at the end of `_tl_build_ast_map()` in `timeline_init.rpy`. It receives the list of all label nodes from `renpy.game.script.namemap`. It runs a full iterative block walk from all Label entry points (covering anonymous nodes inside If/Menu arms) using a work queue.

**Python-node pass** (during the walk):
- Parses `.code.source` with the Python `ast` module
- Collects `Name` assignment targets from `Assign` and `AugAssign` nodes
- Skips `_`-prefixed vars, Python builtins, and a skiplist (`True`, `False`, `None`, `renpy`, `store`, `persistent`, etc.)
- Tracks numeric detection: `AugAssign` with arithmetic ops → marks var numeric
- Collects `Constant` RHS literals → `persistent._tl_var_domain`

**If-node pass** (second pass over collected If nodes):
- Extracts var names from condition strings via `_tl_extract_vars_from_conditions()`
- Builds seen descriptors via `_tl_make_seen_fn()` for each branch block
- Accumulates `if_count` and `_if_key_to_vars` mappings
- Collects domain values from `==`/`!=` comparisons in condition strings

**Outputs (persistent — survive reloads):**
- `persistent._tl_route_var_names` — list of all tracked var names
- `persistent._tl_var_if_count` — `{var_name: int}` total If-entries referencing each var
- `persistent._tl_if_key_to_vars` — `{(file, line): [var_names]}` reverse mapping
- `persistent._tl_var_domain` — `{var_name: sorted_list_of_value_strings}` all known values
- `persistent._tl_var_is_numeric` — set of var names classified as numeric

### 2. Chip filtering and ordering (render time)

`_tl_build_route_chips()` runs at render time inside the route screen. It filters and orders chips from `persistent._tl_route_var_names`.

**Show/hide rules:**
1. `if_count == 0` → **hide** (never gates any content)
2. Value is `None` → **hide** (var not yet set in this save)
3. Value is not a scalar (`bool`, `int`, `float`, `str`) → **hide** (lists, dicts, etc.)
4. Consumed AND `if_count ≤ 5` AND not highlighted → **hide** (player is past all branches; 5 = `_TL_ROUTE_HIGH_THRESHOLD`)
5. Otherwise → **show**

A var is *consumed* (`_tl_var_consumed(name)`) when `len(_tl_var_if_seen_keys[name]) >= _tl_var_if_count[name]` — every If-entry referencing it has been executed this session.

**`_tl_highlighted`** = `ghost_vars ∪ recently_changed_vars`. Highlighted vars always show regardless of consumed state.

**Ordering:**
1. Highlighted vars (ghost or recently changed), by `if_count` desc
2. Non-highlighted vars, by `if_count` desc

**Return value:** `list[(var_name, current_value)]`

### 3. Var change detection

`_tl_python_execute_patched` (in `backend/tl_ghost_logic.rpy`) wraps `renpy.ast.Python.execute`:

1. **Filename filter**: only intercepts game scripts (`filename.startswith("game/")` and `"renpy-chronology-mod" not in filename`). Mod files and Ren'Py internals bypass the patch.
2. **Guards**: no-ops if `persistent._tl_replaying` or `config.skipping`.
3. **Pattern**: snapshot → execute original → diff.

`_tl_snapshot_route_vars()` returns `{var: getattr(store, var, None)}` for all `_tl_route_var_names`.

`_tl_diff_route_vars(snap)` compares store values against the snapshot and writes changes into `store._tl_pending_var_changes = {var: (old_val, new_val)}`. Key rules:
- Skip if `old_val is None` (init — var didn't exist before this block)
- Skip if `new_val == old_val`
- If already pending: keep original `old_val`, update `new_val`
- Also adds changed var to `store._tl_recently_changed_vars`

`_tl_flush_var_changes()` emits one `renpy.show_screen("_tl_notify", message=...)` for all accumulated changes and clears the dict. Called immediately after each `_tl_diff_route_vars`.

`_tl_flush_menu_snap()` handles the complement case: vars that were `None` at menu-present time (not yet set), first assigned inside a menu arm. Called by `_tl_record_before` at the next menu boundary.

### 4. Notification format

- Numeric var: `{font=DejaVuSans.ttf}↑{/font}N Label` or `↓N Label`; magnitude omitted when delta is exactly 1
- Non-numeric var: `Label {font=DejaVuSans.ttf}→{/font} newvalue`
- Multiple vars: joined with ` · `

### 5. Recently-changed tracking

`store._tl_recently_changed_vars` is a transient `set()` accumulating vars changed since the last menu. It is:
- Populated by `_tl_diff_route_vars` and `_tl_flush_menu_snap`
- Cleared at the start of `_tl_record_before` (each new menu)
- Used by `_tl_build_route_chips` to keep recently-changed vars pinned to the top of the chip bar

## Store and persistent variables

**Persistent (survive reloads):**
- `persistent._tl_route_var_names` — tracked var list
- `persistent._tl_var_if_count` — per-var If-entry count
- `persistent._tl_if_key_to_vars` — If AST key → var names
- `persistent._tl_var_domain` — per-var sorted domain values
- `persistent._tl_var_is_numeric` — set of numeric-classified vars

**Transient (rebuilt each session):**
- `store._tl_pending_var_changes` — `{var: (old, new)}`; cleared after each flush
- `store._tl_recently_changed_vars` — `set`; cleared at each menu
- `store._tl_menu_var_snap` — snapshot taken at menu-present time for init-assign detection
- `store._tl_var_if_seen_keys` — `{var: set((file, line))}` If-key visit tracker

## Files

| File | Role |
|------|------|
| `backend/tl_route_logic.rpy` | AST index build, chip filtering/ordering, snapshot/diff/flush, notification format |
| `backend/tl_ghost_logic.rpy` | `_tl_python_execute_patched` registration, `_tl_notify_branch` tier logic |
| `ui/tl_route_screen.rpy` | `tl_route` chip bar screen, `_tl_notify` notification screen |
| `timeline_screen.rpy` | `_tl_toggle` routing, route tab header button, tooltip rendering, `_tl_capture_hover_pos` |
| `timeline_init.rpy` | Calls `_tl_build_route_index`, initializes route store defaults |

## Key layout variables (ui/tl_route_screen.rpy)

- `_tl_chip_w`, `_tl_key_w`, `_tl_val_w` — chip width split
- `_tl_chips_per_row` — number of chips per row (computed from screen width)
- `_TL_ROUTE_FOLD` — visible rows before fold: `max(3, ceil(_tl_hl_count / _tl_chips_per_row)) * _tl_chips_per_row`; ensures all highlighted chips are visible without folding
- `_tl_highlighted` — `ghost_vars ∪ recently_changed` (per-render set)

Ghost card rows appear below the chip bar in the route view, with clusters in reverse order (most recent cluster at top-left) via `reverse_clusters=True` passed to `use tl_ghost_rows(...)`.

## Toggle and keybinding

- `T` — toggle timeline (opens on last-viewed tab or cards tab)
- `R` — toggle timeline, switching to route tab; or close if already on route tab
- `Esc` — close timeline

`_tl_toggle(view=None)`: when `view` is given and timeline is closed → opens on that tab; when already open and same tab → closes; when already open and different tab → switches tab.