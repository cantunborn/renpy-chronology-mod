# Code Flow

This file is the cross-cutting map of how the main subsystems fit together. It is intentionally narrower than a full architecture doc.

## File Layout

The mod is split across three layers:

- **`timeline_*.rpy`** — top-level entry points: hooks, init, screen coordinator, save hooks, tests
- **`backend/`** — `init -2 python:` modules; subsystem logic extracted from the monolithic init/hooks files
- **`ui/`** — screen definitions only; no behavior logic

## Runtime Timeline Flow

The timeline runtime starts with menu interception.

`timeline_hooks.rpy` wraps `renpy.exports.menu` and `renpy.store.menu`. Before a menu is shown, `_tl_record_before()` evaluates each item's condition (`entry[1]`) to filter available options (prompt detected by `block is None`), then creates a history node with menu metadata, AST key, snapshot, and thumbnail context. After the player chooses an option, `_tl_record_after()` stores the chosen index, extends `_tl_context`, and queues checkpoint saving.

Checkpoint and chapter-end persistence hang off the same runtime layer. `_tl_interact_callback()` writes normal checkpoint saves after interactions. `_tl_chapter_label_cb()` records chapter-end markers and writes chapter-end saves at the label boundary. Both callbacks are registered in `timeline_hooks.rpy`.

`timeline_init.rpy` owns the top-level init: perf helpers, AST map build (`_tl_build_ast_map`), branch ID generation, and img-name migration. Subsystem helpers have been extracted to `backend/` (see Backend Modules below).

**Debug flags** (all `False` by default, set in `timeline_init.rpy`):

- `TL_PROFILE_TIMELINE` — log AST walk timing
- `TL_DEBUG_GHOST` — ghost synthesis detail (if-execute, clustering, branch-img tiers); gates ~12 high-volume logs in `tl_ghost_logic.rpy`
- `TL_DEBUG_SEEN` — seen-state resolution detail (opt_seen, peek_seen); gates per-option logs that fire O(options × cards) per timeline open
- `TL_DEBUG_ROUTE` — route tracker detail (var diff per Python block, chip filter stats)

`timeline_save_hooks.rpy` validates and repairs loaded state, cleans transient UI state, and keeps older saves compatible.

`timeline_screen.rpy` is a thin coordinator. It sets up the main timeline screen and delegates card, ghost-card, and modal rendering to `ui/` (see UI Modules below).

## Backend Modules

Each `backend/` file owns one subsystem. All run at `init -2 python:` so they are defined before the top-level hooks.

### `backend/tl_saveload.rpy`
Save-slot naming and jump mechanics.
- `_tl_save_slot(node_index, context)` — hashed slot name for checkpoint saves
- `_tl_chap_end_slot_name(label, context, after_index)` — slot name for chapter-end saves
- `_tl_find_nearest_save(target_index, context)` — scan save dir for the best matching checkpoint
- `_tl_begin_jump(node_index, option_index)` — load checkpoint and restore shadow path for a timeline jump
- `_tl_begin_label_jump(label)` — jump to a chapter-end save by label
- `_tl_cancel_replay()` — abort in-progress replay

### `backend/tl_assets.rpy`
Thumbnail capture and asset resolution.
- `_tl_capture_thumbnail()` — screenshot to bytes (WebP/JPEG/PNG)
- `_tl_resolve_live_menu_img_name()` — derive current scene image from live Ren'Py state
- `_tl_resolve_asset_file(img_name)` — locate the actual file backing an img_name
- `_tl_get_asset_thumb_bytes(img_name, generate)` — persistent asset-thumb cache lookup / generation
- `_tl_render_asset_thumb_bytes(img_name, width, height, fit_mode)` — render asset to bytes
- `_tl_thumb_displayable(thumb_bytes, index)` — build a Ren'Py displayable from cached thumb bytes
- `_tl_img_thumb_displayable(img_name, width, height, fit_mode)` — transient displayable cache for asset thumbs
- `_tl_node_thumb(node)` — resolve the best displayable for a history node

### `backend/tl_ghost_logic.rpy`
Ghost card synthesis. Monkey-patches `renpy.ast.If.execute` and `renpy.ast.Python.execute`.
- `_tl_get_taken_branch(if_node)` — evaluate which branch index will be taken
- `_tl_build_ghost_payload(if_node, taken_index, context_img)` — build one payload dict per sibling If
- `_tl_collect_if_run(start_if_node)` — collect the full sequential sibling If run
- `_tl_partition_if_run(run)` — partition siblings into mutually exclusive clusters
- `_tl_emit_ghost_cluster(group, cluster_with_prev)` — append one cluster to `_tl_ghost_nodes`
- `_tl_on_if_execute(if_node, taken_index, pre_taken_seen)` — orchestrate ghost synthesis and visited-node marking
- `_tl_if_execute_patched(self)` — monkey-patch replacement for `If.execute`
- `_tl_notify_branch(run, taken_index, pre_taken_seen)` — fire tiered branch notification (suppress / icon-only / new-path)
- `_tl_python_execute_patched(self)` — monkey-patch replacement for `Python.execute`; filename-filtered; calls snapshot/diff/flush for route var detection

### `backend/tl_seen_check.rpy`
Seen-state helpers shared by ghost cards and the main timeline.
- `_tl_say_seen_name(node)` — resolve the `_seen_ever` key for a Say node via the Ren'Py translator (for translated games)
- `_tl_follow_jump_seen_name(target, max_hops)` — hop one level into a jump target to find the first Say seen name (for blocks ending in `jump label` with no prior Say)
- `_tl_make_seen_fn(block)` — build a picklable descriptor tuple for a branch block; handles Say, Scene/image, Jump-follow, and never cases
- `_tl_eval_seen_fn(seen_fn)` — evaluate a descriptor tuple against live Ren'Py state
- `_tl_option_seen(node, option_index)` — check if a menu option has been seen
- `_tl_option_peek_seen_fn(node, option_index)` — live AST peek for option seen state

### `backend/tl_route_logic.rpy`
Route tracker backend. Runs at `init -2`.
- `_tl_build_route_index(nodes)` — full AST walk; writes `persistent._tl_route_var_names`, `_tl_var_if_count`, `_tl_if_key_to_vars`, `_tl_var_domain`, `_tl_var_is_numeric`
- `_tl_var_consumed(var_name)` — True if every If-entry referencing this var has been visited this session
- `_tl_build_route_chips()` — filter and order vars for chip bar display
- `_tl_snapshot_route_vars()` — snapshot current store values for all route vars
- `_tl_diff_route_vars(snap)` — accumulate changes into `store._tl_pending_var_changes`; skips inits; populates `_tl_recently_changed_vars`
- `_tl_flush_var_changes()` — emit one `_tl_notify` for all pending changes and clear dict
- `_tl_format_numeric_change(label, old_val, new_val)` — format `↑N Label` / `↓N Label`; omits magnitude when delta is 1
- `_tl_flush_menu_snap()` — emit notifications for vars first-assigned inside a menu arm (init case)

### `backend/tl_shadow_path.rpy`
Shadow path / replay aid.
- `_tl_build_shadow_path(history, node_index)` — extract the original choice sequence after a jump point
- `_tl_stage_shadow_path(history, node_index)` — write shadow path to persistent before loading a save
- `_tl_shadow_match(shadow_path, node)` — check if current menu matches next shadow entry
- `_tl_consume_shadow_path(shadow_path, node, chosen_index)` — consume one shadow entry, stamp divergence marker
- `_tl_shadow_match_mode(shadow_path, node)` — determine match mode (site key vs location fallback)

### `backend/tl_chapter.rpy`
Chapter loading helpers.
- `_tl_load_chapters()` — load chapter definitions from JSON
- `_tl_dedup_chapters(raw)` — deduplicate chapter list
- `_tl_chapter_marker_exists(markers, chapter, after_idx)` — check if a chapter-end marker exists
- `_tl_rollback_timeline(history, context, markers, label, chapters)` — trim history to a chapter boundary

### `backend/tl_menu_location.rpy`
Menu site identity helpers.
- `_tl_menu_site_key(file_path, line_no)` — stable string key for a menu AST site
- `_tl_location_menu_ast_key(location)` — derive ast_key from a `_location` tuple
- `_tl_node_menu_site_key(node)` — derive menu site key from a history node
- `_tl_live_menu_lookup()` — look up current live menu in the AST

### `backend/tl_menu_options.rpy`
Choice entry and index helpers.
- `_tl_valid_choice_entries(items)` — filter caption-only items, return choosable entries
- `_tl_choice_entry_for_index(items, choice_index)` — resolve a choice index to its menu item
- `_tl_choice_index_from_return_value(items, rv)` — map Ren'Py return value back to a choice index
- `_tl_populate_choice_returns(node, items)` — populate `_choice_returns` on a history node

### `backend/tl_ast_dump.rpy`
Live AST → JSON dump for offline tools.
- `_tl_cfg_dump_ast(labels, outfile)` — serialize the live Ren'Py AST to `cfg/full_ast.json`

## UI Modules

Each `ui/` file contains screen definitions only. Behavior logic lives in `backend/`.

- `ui/tl_cards.rpy` — past card and current card screen definitions (extracted from `timeline_screen.rpy`)
- `ui/tl_ghost_cards.rpy` — `tl_ghost_rows` screen definition; ghost card synthesis logic lives in `backend/tl_ghost_logic.rpy`
- `ui/tl_route_screen.rpy` — route tracker chip bar (`tl_route` screen) and mod notification screen (`_tl_notify`)
- `ui/tl_modal.rpy` — modal screen definition
- `ui/tl_debug.rpy` — debug overlay screen
- `ui/tl_theme.rpy` — shared styling constants and theme helpers

## Timeline Thumbnail Flow

Timeline thumbnails are now on an asset-first path with screenshot fallback still present as a backstop.

The current intended order is:

1. `_tl_record_before()` creates the history node before the menu is shown.
2. `_tl_resolve_live_menu_img_name()` (in `backend/tl_assets.rpy`) resolves the actual current gameplay image from live Ren'Py scene state.
3. If a runtime image is found, it is stamped onto the node as `img_name` and written into `persistent._tl_menu_scene_map` for that menu `ast_key`.
4. If runtime capture misses, the persistent menu-scene map provides a backfill image for that menu site.
5. Only if both asset-based paths miss does the system fall back to `_tl_capture_thumbnail()`.
6. Rendering prefers `img_name`. Screenshot bytes are only used when no asset image is available.

This keeps screenshots demoted to explicit fallback status while still preserving compatibility and coverage during the port.

### Storage model

- transient per-node field
  - `node["img_name"]`
- transient per-node fallback field
  - `node["thumb_bytes"]`
- persistent cache
  - `persistent._tl_menu_scene_map`
- persistent asset-thumb cache
  - `persistent._tl_asset_thumb_cache`
- persistent screenshot fallback cache
  - `persistent._tl_thumb_cache`
- previous-node thumbnail staging for replay/jump UX
  - `persistent._tl_prev_thumb`

The menu-scene map is now the primary persistent thumbnail identity store for the timeline. The screenshot cache remains a fallback store.

The screen layer also keeps a transient in-memory displayable cache for asset thumbnails so repeated `img_name` renders do not rebuild the same transformed displayable every time the timeline opens. In addition, asset-backed thumbs now have their own persistent static-thumb cache: the screen first tries to use a generated thumbnail bytes payload derived from `img_name`, and only falls back to live asset rendering for plain file-backed assets. Dynamic image definitions do not get rendered directly inside the timeline screen; those cards stay on the existing screenshot/plain-background fallback path.

### Limits and compatibility

- capture size
  - `320 x 180`
- cache cap
  - `TL_THUMB_CACHE_MAX = 500`
- expected upper bound
  - about 25 MB persistent storage at roughly 50 KB per thumbnail

Compatibility constraints:

- thumbnail capture depends on `renpy.screenshot_to_bytes`
- on Ren'Py versions older than 7.5, `_tl_capture_thumbnail()` returns `None`
- cards still work on those versions, but use a plain background instead of a captured scene image

`_tl_thumb_displayable()` (in `backend/tl_assets.rpy`) detects WEBP / JPEG / PNG from magic bytes before creating the Ren'Py image object so cached thumbnails decode correctly across supported Ren'Py versions.

### Operational notes

- runtime-captured menu images are authoritative
- AST walk backfill is best-effort and only fills missing menu-image entries
- the menu-scene map currently backfills from structural `Scene` / `Show` flow and explicit `Jump` traversal
- the cache is persistent, so asset-backed menu images and screenshot fallbacks survive mod reinstalls and save reloads
- there is explicit cache-clear functionality in runtime helpers
- before some load/jump flows, current node thumbnails may be snapshotted into the persistent cache so the loaded save can still display them even if node-local bytes are lost with the load

## Replay Aid / Shadow Path Flow

When a player jumps back to replay from an old menu, `backend/tl_shadow_path.rpy` builds a shadow path from the original history after the jump point. That shadow path is staged in persistent state before loading a checkpoint save, then restored into store state after load.

As later menus are reached, `_tl_record_before()` compares the current menu against the shadow path via `_tl_shadow_match()`. Matching entries are consumed by `_tl_consume_shadow_path()`. If the player chooses differently from the original path, `_shadow_orig_chosen` is stamped on the node so the UI can show divergence markers even after the shadow entry is consumed.

## Ghost Card Flow

Ghost cards are driven by a monkey-patch on `renpy.ast.If.execute` in `backend/tl_ghost_logic.rpy`.

At `If.execute` time:

1. `_tl_get_taken_branch()` evaluates which branch index will be taken.
2. The original Ren'Py `If.execute` runs.
3. `_tl_on_if_execute()` performs:
   - visited-node marking
   - ghost-card synthesis for active gameplay

Ghost synthesis does not just append one card per executed `if`. The hook now collects the full sequential sibling `If` run starting at the current AST node, builds one payload per sibling `if`, partitions the run into mutually exclusive groups, emits one ghost cluster per group, and records later sibling keys in `_tl_skip_ghost_ifs` so runtime does not append duplicates when those siblings execute later.

Each payload includes:

- condition strings
- taken branch index
- first branch image
- scene-based seen descriptors

Rendering happens in `ui/tl_ghost_cards.rpy`. The UI flattens each cluster into branch rows. Taken branches show `→`. Untaken unseen branches get a dark overlay and lock icon. Untaken previously seen branches get a lighter semi-transparent overlay; no lock.

## Seen-State Flow

There are two related seen systems.

For menu options and normal timeline dots, `_tl_option_seen()` (in `backend/tl_seen_check.rpy`) checks the AST-based seen-map and history.

For ghost cards and condition/scene visibility, `_tl_make_seen_fn(block)` builds a picklable descriptor tuple for a branch block:

- `("never",)` — no checkable content found; branch treated as unseen
- `("say", name)` — check `name in persistent._seen_ever`
- `("say_range", first, last)` — multi-Say block; fast-fail if `first` not in `_seen_ever`, confirm with `last`
- `("image", name_tuple)` — check `renpy.seen_image(name_tuple)` against `persistent._seen_images`; used when branch starts with a Scene/Show
- `("label", target)` — check `renpy.seen_label(target)` as last resort

`_tl_eval_seen_fn(seen_fn)` evaluates the descriptor tuple against live Ren'Py state.

**Translator lookup**: `_tl_say_seen_name(node)` resolves the `_seen_ever` key through the Ren'Py translator (`renpy.game.script.translator.lookup_translate(identifier)`) for translated games. Falls back to `node.name` if translation lookup returns None or raises.

**Jump follow**: `_tl_follow_jump_seen_name(target, max_hops)` hops one level into a jump target to find the first Say. This fixes labels reached by `$ var = …; jump label` blocks where no Say appears in the branch body before the jump.

**Show exclusion**: Show nodes are intentionally excluded from `_tl_make_seen_fn` descriptor resolution. Character sprites (`show eileen happy`) fire on many branches simultaneously and are branch-ambiguous in `persistent._seen_images`, causing false "already seen" state if used as the primary descriptor. Scene nodes (background changes) are still used via `("image", ...)`.

**Pre-execute snapshot**: `_tl_if_execute_patched` evaluates the taken branch descriptor *before* calling `_tl_orig_if_execute`. This avoids `_seen_images` pollution from synchronous `Scene.execute` calls that happen during the original execute.

## Route Tracker Flow

The route tracker shows which story variables gate upcoming content and what their current values are.

**Init (background thread, after game load)**:
1. `_tl_build_ast_map()` calls `_tl_build_route_index(nodes)` with all label nodes from `renpy.game.script.namemap`.
2. `_tl_build_route_index` does a full iterative block walk (work-queue from Label entry points) and three passes:
   - Python-node pass: collect var names, detect numeric classification, collect domain literals
   - Default-node pass: eval bytecode of `default` AST nodes; store scalar defaults in `store._tl_var_defaults` (non-scalars skipped to avoid persistence errors)
   - If-node pass: accumulate `if_count` per var, build seen descriptors per branch
3. Results written to `persistent.*` keys — survives reloads. `store._tl_var_defaults` is transient and rebuilt each session.

**Render time**:
`_tl_build_route_chips()` reads persistent index and current store values. Hides vars with None values, non-scalar values, or values still at declared default (from `store._tl_var_defaults`) unless ghost-highlighted or recently-changed. Returns `list[(var_name, current_value)]` sorted: highlighted (ghost/recently-changed) first by `if_count` desc, then rest by `if_count` desc.

`_tl_highlighted = ghost_vars ∪ recently_changed_vars` where `ghost_vars` comes from `_tl_ghost_nodes[*]["affecting_vars"]` and `recently_changed_vars` is `store._tl_recently_changed_vars`.

Dynamic fold row count: `_TL_ROUTE_FOLD = max(3, ceil(_tl_hl_count / _tl_chips_per_row)) * _tl_chips_per_row` ensures all highlighted chips are visible without being folded.

Domain tooltip is rendered at the top level as an absolute-positioned frame at `_tl_route_hover_pos + 14px`, clamped to screen bounds. Frozen at hover-start via `Function(_tl_capture_hover_pos)` in the chip's `hovered` action.

## Var Change Notification Flow

**Detection**: `_tl_python_execute_patched` wraps `renpy.ast.Python.execute`. Only active for `game/` files that are not mod files, and only when not replaying or skipping.

1. `_tl_snapshot_route_vars()` — record current store values
2. `_tl_orig_python_execute(self)` — run original Python block
3. `_tl_diff_route_vars(snap)` — find changes, accumulate into `store._tl_pending_var_changes`
4. `_tl_flush_var_changes()` — emit one `renpy.show_screen("_tl_notify", message=...)`, clear dict

The emit is immediate after each Python block. Back-to-back Python blocks produce a sequence of notifications each replacing the previous — the player always sees the latest complete picture.

**Safety flush**: `_tl_record_before` calls `_tl_flush_var_changes()` at the top of each menu, catching any changes not already flushed.

**Menu-arm inits**: vars first assigned inside a menu arm (value was None at menu-present time) are handled by `_tl_flush_menu_snap()`, called by `_tl_record_before`. The `_tl_menu_var_snap` is taken at menu-present time and compared against store values after arm execution.

## Source Of Truth Notes

- Runtime behavior: `timeline_*.rpy`, `backend/`, `ui/`
- Offline AST source: `cfg/full_ast.json` (generated by `_tl_cfg_dump_ast`)
- Feature-level behavior docs: `docs/*.md`
- Short session entrypoint: `docs/SESSION_GUIDE.md`

When there is conflict, prefer code over docs, and prefer subsystem docs over changelog text.

## Stashed / Not Live

These approaches are preserved in git stashes but are not present in the current working tree.

- **Flowchart** — `timeline_flowchart.rpy`, `tools/gen_cfg.py`, `tools/build_vis.py`, `tools/build_presentation.py`. Stash: `flowchart clean bucket`. Full offline CFG render + in-game flowchart screen.
- **Causal analysis** — `tools/experiments/causal_analysis.py`. Dependency graph across choices, assignments, variables, and conditions. Emitted `cfg/intro_causal_graph.json` for runtime hint lookup via `_tl_choice_diff_hints()`.
- **Formula ITE solver / DAG BFS** — `tools/formula_solver.py`, `tools/formula_bfs.py`. Traversal strategy v2 with Z3-backed formula propagation over the control-flow graph. DAG layer partially implemented; hub execution layer not started.
- **Z3 causal slice** — `tools/experiments/causal_slice.py`, `causal_verify.py`. Z3-backed backward slice for condition satisfiability.
- **Hint engine** — `tools/hint_engine.py`. Standalone solve-first prototype; symbolic walk from start label, grouped path output.
- **CF delta attribution** — `backend/tl_cf_delta.rpy`. Guard-aware CFG-based variable delta attribution per menu arm. Approach abandoned.
- **Var delta reachable map** — `backend/tl_var_delta.rpy`. Offline reachable-write map builder. Approach abandoned.
