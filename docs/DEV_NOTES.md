# Developer Notes

Function-level reference for the Chronology mod codebase. For the architecture overview and subsystem relationships, see [CODE_FLOW.md](CODE_FLOW.md).

---

## Backend Modules (`backend/`)

All backend files run at `init -2 python:` — before the top-level hooks.

---

### `backend/tl_saveload.rpy`

Checkpoint save/load logic, replay state management, and jump control.

**Store variables (saved with game):**
- `_tl_history` — rolled back during fallback label jumps
- `_tl_node_count` — rolled back during fallback label jumps
- `_tl_context` — rolled back during fallback label jumps
- `_tl_chapter_markers` — rolled back during fallback label jumps

**Store variables (transient):**
- `_tl_chap_end_slot` — slot name for a chapter-end load; cleared after use
- `_tl_label_jump` — label name for fallback jump; cleared after use
- `_tl_load_slot` — slot name to load via `_tl_do_load` label

**Persistent variables:**
- `persistent._tl_replaying` — bool; True during active replay
- `persistent._tl_recovery_slot` — save slot name to restore on cancel
- `persistent._tl_replay_path` — list of dicts; choice history snapshot at jump time
- `persistent._tl_replay_target` — dict `{node_index, option_index}`; jump destination
- `persistent._tl_prev_thumb` — bytes; thumbnail of the node before the jump target
- `persistent._tl_pending_shadow_path` — staged shadow-path entries; persisted across checkpoint load

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_should_save` | `(idx, dense=None, every=None) → bool` | Returns True if a checkpoint should be written for this node index; dense saves for first N nodes, sparse every M after. |
| `_tl_save_slot` | `(node_index, context) → str` | Returns `_ch_{NNNN}_{hash6}` slot name; hash is MD5[:6] of the context tuple. |
| `_tl_chap_end_slot_name` | `(label, context=None, after_index=None) → str` | Returns `_ch_chap_{label}` or `_ch_chap_{label}_{hash6}` when context is provided. |
| `_tl_find_nearest_save` | `(target_index, context, save_dir=None, start_exists=None, chap_candidates=None) → str or None` | Scans save dir for the chronology slot with highest index ≤ target_index that shares the same context prefix; falls back to `_ch_start` if present. |
| `_tl_clear_replay_state` | `() → None` | Clears all replay-related persistent variables and saves persistent data. |
| `_tl_begin_label_jump` | `(label) → None` | Initiates a chapter-end jump; loads chapter-end save slot if it exists on disk, otherwise rolls back history/context/markers and sets `_tl_label_jump` for fallback. |
| `_tl_begin_jump` | `(node_index, option_index) → str or None` | Initiates a timeline jump; saves recovery point, stages shadow path, finds nearest save; returns `"load"` if a save was found or None for fallback. |
| `_tl_cancel_replay` | `() → None` | Cancels an in-progress replay; snapshots current thumbnails to persistent cache before loading the recovery save. |

---

### `backend/tl_assets.rpy`

Asset/thumbnail resolution, image caching, and displayable creation.

**Persistent variables:**
- `persistent._tl_img_movie_cache` — `{img_name: bool}`; caches movie/webm detection results
- `persistent._tl_thumb_cache` — `{ast_key: bytes}`; screenshot fallback thumbnail cache
- `persistent._tl_asset_thumb_cache` — `{cache_key: bytes}`; persistent asset-derived thumbnail bytes

**Transient (module-level, not saved):**
- `_tl_asset_thumb_displayable_cache` — `{display_cache_key: Displayable}`; avoids rebuilding displayables each render
- `_tl_asset_thumb_file_cache` — `{img_name: path or None}`; avoids repeated asset file walks on misses

**Constants:**
- `TL_ASSET_THUMB_CACHE_MAX = 500`
- `TL_ASSET_THUMB_CACHE_VERSION = 1`
- `TL_LOG_ASSET_THUMB_HITS = False` — verbose logging toggle
- `_TL_LOCK_B64` — base64-encoded lock icon PNG
- `_TL_UNLOCK_B64` — base64-encoded unlock icon PNG

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_capture_thumbnail` | `() → bytes or None` | Captures current screen to bytes using `renpy.screenshot_to_bytes`; returns None on RenPy < 7.5 or failure. |
| `_tl_normalize_img_name` | `(value) → str or None` | Normalizes tuple/list/string image identifiers to space-separated string form. |
| `_tl_scene_stmt_img_name` | `(stmt) → str or None` | Returns a normalized image name from a Scene/Show-like AST node. |
| `_tl_stmt_ast_key` | `(stmt) → tuple or None` | Returns a normalized `(file, line)` key for a live AST node. |
| `_tl_live_scene_entry_img_name` | `(entry) → str or None` | Returns a normalized image name from a live scene-list entry. |
| `_tl_img_name_is_movie` | `(img_name) → bool` | Best-effort check for movie/webm-backed registered images; uses persistent cache. |
| `_tl_asset_thumb_cache_key` | `(img_name, width=None, height=None, fit_mode="cover") → str` | Builds a persistent cache key for a static thumbnail derived from an asset image. |
| `_tl_asset_thumb_display_id` | `(img_name) → str` | Returns a stable id string for img_name-derived static thumbnails. |
| `_tl_asset_thumb_display_cache_key` | `(img_name, width=None, height=None, fit_mode="cover") → str` | Builds a transient cache key for final asset-thumb displayables. |
| `_tl_is_supported_thumb_file` | `(path) → bool` | Returns True if path has a supported image extension (.png, .jpg, .jpeg, .webp, .bmp). |
| `_tl_resolve_asset_file` | `(img_name) → str or None` | Resolves a plain file-backed registered image path by walking the RenPy image registry tree. |
| `_tl_render_asset_thumb_bytes` | `(img_name, width=None, height=None, fit_mode="cover") → bytes or None` | Renders a plain file-backed asset to thumbnail bytes using pygame scaling. |
| `_tl_get_asset_thumb_bytes` | `(img_name, generate=False, width=None, height=None, fit_mode="cover") → bytes or None` | Returns cached static thumbnail bytes for an img_name; optionally generates them if missing. |
| `_tl_resolve_live_menu_img_name` | `() → str or None` | Resolves the best currently displayed gameplay image for a menu from live RenPy scene state; prefers background-tagged images. |
| `_tl_thumb_displayable` | `(thumb_bytes, index) → Displayable` | Creates a RenPy displayable from thumbnail bytes; detects WEBP/JPEG/PNG from magic bytes before creating `im.Data`. |
| `_tl_node_thumb` | `(node) → bytes or None` | Returns thumbnail bytes for a node, trying `node["thumb_bytes"]` then `persistent._tl_thumb_cache[node["ast_key"]]`. |
| `_tl_img_thumb_displayable` | `(img_name, width, height, fit_mode="cover") → Displayable or None` | Returns a cached displayable for an asset-backed timeline thumbnail; builds and caches if missing. |
| `_tl_clear_thumb_cache` | `() → None` | Clears all thumbnail caches (persistent and transient) and notifies the user. |

---

### `backend/tl_ghost_logic.rpy`

Ghost card synthesis. Monkey-patches `renpy.ast.If.execute` and `renpy.ast.Python.execute` to track branch conditions and route var changes at runtime.

**Store variables (transient):**
- `_tl_ghost_highlight` — `(ast_key, branch_idx)` tuple or None; which ghost row is highlighted
- `_tl_ghost_nodes` — list of ghost card dicts built during gameplay
- `_tl_skip_ghost_ifs` — set of ast_keys; If nodes whose sibling rows are already emitted

**Constants:**
- `_TL_KW_SKIP` — set of Python keyword strings to skip during condition prettification
- `_TL_STR_LIT_RE` — compiled regex for string literals
- `_TL_VAR_RE` — compiled regex for variable identifiers

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_branch_img` | `(block, context_img=None) → str or None` | Resolves the best thumbnail image for a ghost branch using 3-tier search: local Scene/Show, Jump/Call follow, context fallback. |
| `_tl_first_scene_img` | `(block) → str or None` | Shim calling `_tl_branch_img(block, context_img=None)`. |
| `_collect_branch_imgs` | `(block, max_images=5) → (list, set)` | Collects up to max_images Scene/Show images from a branch block with flat scan and one Jump/Call hop; returns `(images, visited_labels)`. |
| `_tl_parse_regions` | `(cond_str) → list or None` | Parses a condition string to DNF regions for mutual exclusivity checks. |
| `_tl_should_cluster` | `(prev_ghost, new_conds) → bool` | Returns True if new_conds are mutually exclusive with prev_ghost's conditions (safe to group visually). |
| `_tl_branch_exits_before_next` | `(block) → bool` | Returns True when a taken branch clearly exits before sibling ifs can run (explicit Jump/Return). |
| `_tl_extend_ghost_rows` | `(ghost, ast_key, conditions, seen_fns, branch_imgs, regions, affecting_vars=None) → None` | Appends hidden sibling-if rows into an existing ghost card dict. |
| `_tl_toggle_ghost_highlight` | `(ast_key, branch_idx) → None` | Toggles ghost branch row highlight on/off in `_tl_ghost_highlight`. |
| `_tl_extract_vars_from_conditions` | `(conditions) → set` | Extracts variable names from a list of condition strings via regex. Filters out Python builtins and names starting with `_`. Used to populate `affecting_vars` in ghost payloads and to build the route index. |
| `_tl_prettify_var` | `(name) → str` | Converts a snake_case var name to a readable label. Strips common prefixes (`mc_`, `flag_`, `is_`, `has_`, `ch_`), splits on `_`, and title-cases each word. Example: `mc_affection_bonus` → `Affection Bonus`. |
| `_tl_prettify_condition` | `(cond) → str` | Prettifies snake_case var names and strips quotes from string values using `ast.parse`. `Name` nodes → `_tl_prettify_var`; `Constant` string nodes → bare value (no quotes); numeric constants left as-is. Applies replacements right-to-left by `col_offset`. Falls back to regex on parse failure. Example: `route_id == "romance"` → `Route Id == romance`. |
| `_tl_get_taken_branch` | `(if_node) → int` | Evaluates conditions in order and returns the index of the first True one. |
| `_tl_build_ghost_payload` | `(if_node, taken_index, context_img=None) → dict or None` | Builds one ghost payload dict for a single If node with conditions, seen_fns, branch_imgs. Returns None when all entries collapse to a single `"True"` condition (no branching content). |
| `_tl_resolve_cluster_imgs` | `(if_node, context_img) → list` | Resolves per-branch thumbnail images for one If node using cross-branch comparison. |
| `_tl_collect_if_run` | `(start_if_node) → list` | Collects a sequential run of player-relevant sibling If nodes with payload building. |
| `_tl_partition_if_run` | `(run) → list` | Partitions a sequential If run into mutually-exclusive cluster groups. |
| `_tl_emit_ghost_cluster` | `(group, cluster_with_prev) → None` | Emits one ghost card object from a clustered group of If payloads into `_tl_ghost_nodes`. |
| `_tl_on_if_execute` | `(if_node, taken_index, pre_taken_seen=None) → None` | Callback after If.execute; orchestrates ghost synthesis, visited-node marking, and branch notification via `_tl_notify_branch`. |
| `_tl_should_track_if_node` | `(if_node) → bool` | Returns True if the If node is from a game script (not timeline internals). |
| `_tl_if_execute_patched` | `(self) → None` | Replacement for `renpy.ast.If.execute`; evaluates taken branch descriptor **before** executing (pre-execute snapshot) and calls `_tl_on_if_execute`. |
| `_tl_notify_branch` | `(run, taken_index, pre_taken_seen=None) → None` | Three-tier branch notification: suppress (all branches seen), icon-only `⎇` (taken seen, ≥1 alternative unseen), or "New path" (taken branch itself was never taken before). Uses index-based comparison so equal tuples from different branches are correctly distinguished. |
| `_tl_python_execute_patched` | `(self) → None` | Replacement for `renpy.ast.Python.execute`; filename-filtered to game scripts only (`game/` prefix, not mod files); guards on `persistent._tl_replaying` and `config.skipping`; calls snapshot → original → diff → flush for route var change detection. |

---

### `backend/tl_route_logic.rpy`

Route tracker backend: AST index build, chip filtering/ordering, snapshot/diff/flush pipeline, and notification formatting. Runs at `init -2`.

**Persistent variables (survive reloads):**
- `persistent._tl_route_var_names` — list of var names assigned anywhere in game scripts
- `persistent._tl_var_if_count` — `{var_name: int}`; total If-entries referencing each var across the whole game
- `persistent._tl_if_key_to_vars` — `{(file, line): [var_names]}`; reverse map from If AST key to vars it tests
- `persistent._tl_var_domain` — `{var_name: sorted_list_of_str}`; all known literal values a var takes
- `persistent._tl_var_is_numeric` — `set`; var names classified as numeric (assigned via arithmetic)

**Store variables (transient):**
- `store._tl_pending_var_changes` — `{var_name: (old_val, new_val)}`; accumulated since last flush
- `store._tl_recently_changed_vars` — `set`; vars changed since last menu; cleared at each `_tl_record_before`
- `store._tl_menu_var_snap` — `{var: value}`; snapshot taken at menu-present time for init-assign detection
- `store._tl_var_if_seen_keys` — `{var_name: set(ast_key)}`; tracks which If-node AST keys have been executed this session per var; used by `_tl_var_consumed` to determine whether all branches referencing a var have been hit
- `store._tl_var_defaults` — `{var_name: scalar}`; declared default values from `default` AST nodes (scalar only: bool/int/float/str); rebuilt each session; used by `_tl_build_route_chips` to hide vars still at their declared default

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_build_route_index` | `(nodes) → None` | Full iterative block walk from Label entry points. Three passes: Python-node (collect var names, numeric detection, domain literals), Default-node (capture scalar declared defaults into `store._tl_var_defaults`), and If-node (accumulate `if_count`, build seen descriptors per branch). Writes all five persistent keys listed above plus `store._tl_var_defaults`. |
| `_tl_var_consumed` | `(var_name) → bool` | True if `len(_tl_var_if_seen_keys[var]) >= _tl_var_if_count[var]` — every If-entry referencing this var has been visited this session. Returns False when `if_count == 0`. |
| `_tl_build_route_chips` | `() → list[(str, Any)]` | Filter and sort route vars for chip bar display. Hides vars with None values, non-scalar values, and vars still at their declared default (from `store._tl_var_defaults`) unless ghost-highlighted or recently-changed. Sorts highlighted (ghost/recently-changed) vars first by `if_count` desc, then remaining by `if_count` desc. |
| `_tl_snapshot_route_vars` | `() → dict` | Returns `{var: getattr(store, var, None)}` for all `persistent._tl_route_var_names`. |
| `_tl_diff_route_vars` | `(snap) → None` | Compares current store values against snapshot. Skips unchanged and init vars (old was None). Accumulates into `store._tl_pending_var_changes`; keeps original `old_val` if var already pending. Adds changed vars to `_tl_recently_changed_vars`. |
| `_tl_format_numeric_change` | `(label, old_val, new_val) → str` | Returns `"↑N Label"` or `"↓N Label"`. Omits magnitude when delta is exactly 1. Strips `.0` from integer deltas. Uses DejaVuSans font tags for arrow glyphs. |
| `_tl_flush_var_changes` | `() → None` | Emits one `renpy.show_screen("_tl_notify", message=...)` for all pending changes, then clears `store._tl_pending_var_changes`. No-op if nothing pending. Multiple changes joined with ` · `. |
| `_tl_flush_menu_snap` | `() → None` | Handles vars that were `None` at menu-present time but now have a value (first assignment inside menu arm). Non-init vars (old was non-None) are skipped — already handled by the Python.execute patch. Adds emitted vars to `_tl_recently_changed_vars`. Clears `store._tl_menu_var_snap`. |

---

### `backend/tl_seen_check.rpy`

Seen-state tracking using descriptor tuples, evaluation against live RenPy state, and per-option seen checks.

**Reads (does not own):**
- `persistent._seen_ever` — RenPy's native seen-script tracker
- `persistent._chosen` — RenPy's native choice tracker
- `persistent._seen_images` — RenPy's native displayed-image tracker (via `renpy.seen_image`)

**Descriptor tuple types:**
- `("never",)` — no checkable content found; always evaluates False
- `("say", name)` — check `name in persistent._seen_ever`
- `("say_range", first, last)` — multi-Say block; fast-fail if `first` absent, confirm with `last`
- `("image", name_tuple)` — check `renpy.seen_image(name_tuple)`; used for Scene-started branches and Show nodes with expression args (ParameterizedText). RenPy stores raw imspec parts in `_seen_images`, so the tuple is passed directly without evaluation.
- `("label", target)` — check `renpy.seen_label(target)` as last resort

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_find_scene_seen_name` | `(start_node, max_hops=80) → str or None` | Walks the AST forward from a scene node to find the first translated say-name, used to key seen state to actual scene content. |
| `_tl_say_seen_name` | `(node) → str or None` | Resolves the `_seen_ever` key for a Say node through the Ren'Py translator (`translator.lookup_translate(identifier)`); falls back to `node.name` if lookup returns None or raises. |
| `_tl_follow_jump_seen_name` | `(target, max_hops=30) → str or None` | Hops one level into a jump target label to find the first Say seen name; skips Python/Scene/Show prefix nodes; returns None if no Say found before a Menu/Jump/Return. |
| `_tl_first_scene_seen_name` | `(block) → str or None` | Returns the first scene-backed seen identity for a branch block. |
| `_tl_scene_ast_id` | `(stmt) → tuple or None` | Returns a stable structural `(file, line)` id for a Scene AST node. |
| `_tl_make_seen_fn` | `(block) → tuple` | Returns a picklable descriptor tuple for a branch block. Iterates the block list directly (not `.next` links). Priority: Say/TranslateSay range → Scene → expr-Show → Jump follow → `("never",)`. Plain Show nodes (all-identifier imspec, e.g. `show eileen happy`) are excluded — character sprites appear in many branches and are branch-ambiguous in `_seen_images`. Show nodes with expression args (e.g. `show txt _("кошмар")`) ARE captured as `("image", raw_parts)` because RenPy stores raw imspec parts in `_seen_images`, making them branch-specific. Multiple Says return `("say_range", first, last)`. |
| `_tl_make_scene_seen_fn` | `(block) → tuple` | Scene-only variant of `_tl_make_seen_fn`; misses branches that start with plain dialogue, jumps, or calls. |
| `_tl_eval_seen_fn` | `(seen_fn) → bool` | Evaluates a descriptor tuple against live RenPy state. `say_range`: fast-fails if `first` not in `_seen_ever`, confirms with `last`. `image`: uses `renpy.seen_image`. |
| `_tl_option_seen` | `(node, option_index) → bool` | Returns True if an option has been seen; checks live AST, `persistent._chosen`, `ChoiceReturn`, and AST map in order. |
| `_tl_option_peek_seen_fn` | `(node, option_index) → tuple or None` | Returns a live AST seen descriptor for the option's first meaningful content using runtime Menu node inspection. |
| `_tl_node_has_new` | `(node) → bool` | Returns True if a node has at least one unseen unchosen option. |

---

### `backend/tl_shadow_path.rpy`

Shadow path: the replay-aid hint chain built from history after a jump target.

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_build_shadow_path` | `(history, node_index) → list` | Extracts replay-aid shadow entries from history nodes after node_index; each entry has `chosen_index`, optional `_location`, and `menu_site_key` derived from `ast_key`. |
| `_tl_stage_shadow_path` | `(history, node_index) → list or None` | Returns the shadow-path payload to persist across a checkpoint load; returns None when the path would be empty. |
| `_tl_shadow_match` | `(shadow_path, node) → int or None` | Returns the `chosen_index` from the first entry matching the current node, using `menu_site_key` or `_location`; returns None if no match. |
| `_tl_consume_shadow_path` | `(shadow_path, node, chosen_index) → (list or None, int or None)` | Consumes shadow path entries up to and including the first match for node; returns `(remaining_path_or_none, diverged_orig_ci_or_none)`; `diverged_orig_ci` is set only when the player's choice differs from the original. |
| `_tl_shadow_match_mode` | `(shadow_path, node) → str or None` | Returns which key type matched: `'menu_site_key'`, `'_location'`, or None. |

---

### `backend/tl_chapter.rpy`

Chapter metadata loading, deduplication, marker tracking, and timeline rollback.

**Store variables:**
- `_tl_chapter_markers` — list of `{chapter_name, end_label, after_index}` dicts

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_load_chapters` | `() → dict` | Loads `chapters.json` from the mod directory; skips `_`-prefixed keys; deduplicates labels (first occurrence wins); returns `{chapter_name: end_label}`. |
| `_tl_dedup_chapters` | `(raw) → dict` | Deduplicates a `{chapter_name: end_label}` dict by dropping any chapter whose label has already appeared. |
| `_tl_chapter_marker_exists` | `(markers, chapter, after_idx) → bool` | Returns True if a marker for `(chapter_name, after_index)` already exists in the list. |
| `_tl_rollback_timeline` | `(history, context, markers, label, chapters) → (list, list, list)` | Rolls back history/context/markers to the state at the chapter end identified by label; returns originals unchanged if label not found. |

---

### `backend/tl_menu_location.rpy`

Stable menu site identity keys used to match history nodes across save/load.

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_normalize_script_path` | `(path) → str` | Normalizes script paths so runtime and dumped AST paths can be compared (adds `game/` prefix if missing, strips `.rpyc`). |
| `_tl_menu_site_key` | `(file_path, line_no) → str` | Builds a normalized `"{file}:{line}"` menu site identity key. |
| `_tl_location_menu_ast_key` | `(location) → tuple or None` | Resolves a runtime `_location` tuple to the real Menu `(file, line)` key by walking the live AST namemap. |
| `_tl_location_menu_site_key` | `(location) → str or None` | Returns the normalized menu-site key from a runtime `_location` tuple. |
| `_tl_derive_node_menu_site_key` | `(node) → str or None` | Best-effort stable menu-site identity for a history node; uses `ast_key` first, `_location` as fallback. |
| `_tl_node_menu_site_key` | `(node) → str or None` | Returns the preferred stable menu-site key for a history node. |
| `_tl_live_menu_lookup` | `() → dict` | Returns a lazy `(file, line) → live Menu node` map from RenPy namemap; result cached in runtime store. |

---

### `backend/tl_menu_options.rpy`

Choice menu entry filtering, indexing, and choice-return population.

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_valid_choice_entries` | `(items) → list` | Filters menu items to choosable entries (non-None values); returns list of `(label, value)` tuples with caption-only rows excluded. |
| `_tl_choice_entry_for_index` | `(items, choice_index) → tuple or None` | Returns the `(label, value)` tuple for a given valid choice_index; returns None if out of range. |
| `_tl_choice_index_from_return_value` | `(items, rv) → int or None` | Searches valid items to find the choice_index matching a return value using identity, equality, and `.value` attribute fallback. |
| `_tl_populate_choice_returns` | `(node, items) → None` | Populates the node's `ChoiceReturn` list from valid menu items using the transient runtime cache. |

---

### `backend/tl_ast_dump.rpy`

Development-time tool: walks the live RenPy AST and writes structured JSON for offline analysis tools.

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_cfg_dump_ast` | `(labels=None, outfile=None) → None` | Dumps AST for given label names (or all labels if None) to `cfg/full_ast.json`; serializes Jump, Call, If, Menu, Python, UserStatement nodes with screen jump extraction. |

Internal helpers defined inside `_tl_cfg_dump_ast` (not part of public API): `_img_str`, `_json_safe`, `_serialize_block`, `_find_next_label`, `_stmt_next_boundary`, `_walk_sl_jumps`, `_extract_sl_jump`.

---

## Top-Level Files (`timeline_*.rpy`)

---

### `timeline_hooks.rpy`

Menu interception, save callbacks, replay wrapper, and ghost card hook. Runs at `init -1`.

**Store variables (saved with game):**
- `_tl_history` — list of node dicts; one per menu encounter
- `_tl_branch_id` — unique hex ID for current playthrough branch
- `_tl_node_count` — count of menu nodes encountered
- `_tl_context` — list of `(prompt, chosen_index)` tuples

**Store variables (transient):**
- `_tl_ghost_nodes` — ghost card list (see `backend/tl_ghost_logic.rpy`)
- `_tl_ghost_highlight` — highlighted ghost row `(ast_key, branch_idx)` or None
- `_tl_skip_ghost_ifs` — set of ast_keys to skip during ghost lookahead
- `_tl_early_save_idx` — index of save needing refresh after untracked menus
- `_tl_pending_save_index` — node index to write checkpoint for after next interact
- `_tl_shadow_path` — list of shadow path entries or None

**Persistent variables:**
- `persistent._tl_replaying` — bool; True during active replay
- `persistent._tl_replay_target` — dict or None; `{node_index, option_index}` jump destination
- `persistent._tl_replay_path` — list or None; branch choices at jump time
- `persistent._tl_prev_thumb` — bytes or None; N-1 thumbnail for restore during replay
- `persistent._tl_recovery_slot` — save slot for cancel-replay restore

**Module-level:**
- `_tl_pending` — `[node or None]`; holds pending node between before/after hooks

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_record_before` | `(items) → dict or None` | Fires before each menu: evaluates each item's condition (`entry[1]`) to filter available options into `node["options"]` (prompt detected by `block is None`), creates/reuses node with location/AST key/thumbnail, handles replay reuse; called by menu wrappers. |
| `_tl_record_after` | `(node, chosen_label=None, chosen_index=None) → None` | Fires after choice: records chosen index (prefers index identity over label), extends `_tl_context`, queues deferred save via `_tl_pending_save_index`. |
| `_tl_exports_wrapper` | `(items, set=None, args=None, kwargs=None, item_arguments=None) → choice` | Wraps `renpy.exports.menu`; calls `_tl_record_before`, delegates to original, calls `_tl_record_after`. |
| `_tl_store_wrapper` | `(items) → choice` | Wraps `renpy.store.menu`; handles replay interception (auto-pick at target, skip through path), shadow path match/consume, choice recording. |
| `_tl_on_game_start` | `() → None` | Registered `start_callback`; clears replay state; writes `_ch_start` save. |
| `_tl_on_load` | `() → None` | Registered `after_load_callback`; clears stale replay state or resumes valid replay; re-enables skip; restores shadow path from `persistent._tl_pending_shadow_path`; migrates img_names. |
| `_tl_interact_callback` | `() → None` | Registered `interact_callback`; writes deferred checkpoint save if `_tl_pending_save_index` is set and not currently skipping. |
| `_tl_chapter_label_cb` | `(label_name, abnormal) → None` | Registered `label_callback`; fires when any chapter end label is reached; records `{chapter_name, end_label, after_index}` marker; writes `_ch_chap_{label}_{hash}` save if it doesn't exist on disk. |

---

### `timeline_init.rpy`

Store/persistent initialization, constants, logging, AST map build, and utility functions. Runs at `init -2`.

**Store variables (saved with game):**
- `_tl_history` (default `[]`)
- `_tl_branch_id` (default `""`)
- `_tl_context` (default `[]`)
- `_tl_node_count` (default `0`)

**Store variables (transient, not saved):**
- `_tl_modal_node` (default `None`) — node whose modal is open
- `_tl_load_slot` (default `""`) — slot for `_tl_do_load` label
- `_tl_label_jump` (default `""`) — label for fallback chapter jump
- `_tl_chapter_markers` (default `[]`)
- `_tl_pending_save_index` (default `None`)
- `_tl_early_save_idx` (default `None`)
- `_tl_chap_end_slot` (default `""`)
- `_tl_ast_ready` (default `False`) — True after background AST build completes
- `_tl_shadow_path` (default `None`)
- `_tl_ghost_nodes` (default `[]`)
- `_tl_ghost_highlight` (default `None`)

**Persistent variables (initialized once):**
- `persistent._tl_replaying` (init `False`)
- `persistent._tl_thumb_cache` (init `{}`)
- `persistent._tl_asset_thumb_cache` (init `{}`)
- `persistent._tl_img_movie_cache` (init `{}`)
- `persistent._tl_pending_shadow_path` (init `None`)
- `persistent._tl_menu_scene_map` (init `{}`, version 3) — primary persistent thumbnail identity store
- `persistent._tl_scene_map_version` (init `3`)

**Constants:**
- `TL_THUMB_WIDTH = 320`
- `TL_THUMB_HEIGHT = 180`
- `TL_SAVE_EVERY = 10` — checkpoint every N choices past the dense zone
- `TL_DENSE_SAVES = 5` — save every choice for first N nodes
- `TL_THUMB_CACHE_MAX = 500` — max cached screenshot thumbnails
- `TL_PROFILE_TIMELINE = False` — coarse timeline-screen profiling toggle
- `TL_SIZE_BODY = 21`, `TL_SIZE_TITLE = 38`, `TL_SIZE_DOT = 14`, `TL_SIZE_BADGE = 12`, `TL_SIZE_HEADER = 28`, `TL_SIZE_SUBTITLE = 17`

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_log` | `(msg) → None` | Appends msg with timestamp to `debug.txt` in the mod directory. |
| `_tl_runtime_cache_store` | `() → dict` | Returns the transient runtime cache dict hung on `renpy.game.script`; avoids polluting saveable store. |
| `_tl_runtime_choice_returns` | `(node, create=False) → list or None` | Returns transient `ChoiceReturn` slots for a node keyed by `id(node)`; creates list if `create=True`. |
| `_tl_perf_mark` | `() → float or None` | Returns `time.perf_counter()` if `TL_PROFILE_TIMELINE` is True, else None. |
| `_tl_perf_add` | `(label, started_at) → None` | Accumulates elapsed time for a profiling label. |
| `_tl_perf_reset` | `(scope) → float or None` | Clears profiling stats for a scope and returns a new mark. |
| `_tl_perf_dump` | `(scope, started_at=None) → None` | Logs accumulated profiling stats via `_tl_log`. |
| `_tl_new_branch_id` | `() → str` | Returns a 12-character UUID hex string for a new branch. |
| `_tl_build_ast_map` | `() → None` | Entry point for the background AST walk; sets `_tl_ast_ready = True`, then calls `_tl_build_route_index` and `_tl_build_coverage_index`. |
| `_tl_migrate_img_names` | `() → None` | Stamps `img_name` onto history nodes missing it using `persistent._tl_menu_scene_map`; runs once per load. |

---

### `timeline_save_hooks.rpy`

Post-load validation and save compatibility. Runs at `init -1`.

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_validate_on_load` | `() → None` | Registered `after_load_callback`; resets `_tl_history` if wrong type; drops malformed nodes; re-indexes; migrates pre-v1.1 `chapter_start` tags to `_tl_chapter_markers`; clears transient UI state (`_tl_modal_node`, `_tl_ast_*`, `_tl_pending_chap_end_save`, `_tl_chap_end_slot`). |

**Compatibility cases handled:**
- Mod installed on existing save → graceful empty state, recording starts from installation point
- Mod removed from save with data → RenPy ignores unknown `_tl_*` variables

---

### `timeline_screen.rpy`

Main timeline screen coordinator, keybindings, and jump labels.

**Constants:**
- `config.keymap["chronology_toggle"] = ["t"]` — T to toggle timeline (cards view)
- `config.keymap["chronology_route"] = ["r"]` — R to toggle timeline (route view)

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_tl_toggle` | `(view=None) → None` | Toggles the timeline screen. When timeline is closed: opens on `view` tab (or cards if None). When open on same tab: closes. When open on different tab: switches to `view`. |
| `_tl_capture_hover_pos` | `() → None` | Stores `renpy.get_mouse_pos()` into `store._tl_route_hover_pos`; called via `Function(...)` in chip `hovered` action to freeze the tooltip anchor at hover-start. |

**Labels:**

| Label | Description |
|-------|-------------|
| `_tl_do_load` | Exits screen context and loads `_tl_load_slot` via `renpy.load`. |
| `_tl_do_chap_end_jump` | Exits screen and loads `_tl_chap_end_slot` if set, otherwise jumps to `_tl_label_jump` (fallback for sessions without a chapter-end save). |

**Screens:**

| Screen | Parameters | Description |
|--------|-----------|-------------|
| `timeline()` | none | Root screen; blur layer + dark overlay + header + scrollable body. Header has "History" / "Route" tab buttons. Body switches between card grid (cards view) and `use tl_route(...)` (route view). Default screen vars: `tl_view = "cards"`, `tl_route_expanded = False`, `tl_route_hover = None`. Route tooltip rendered at top level as absolute-positioned frame at `_tl_route_hover_pos + 14px`, clamped to screen bounds. Shows "Possible Routes" header + domain values with `→` current indicator. |
| `tl_chapter_divider(chapter_name, end_label)` | `(str, str)` | Centered `—— End of {chapter} ——` divider between chapter sections; clicking calls `_tl_begin_label_jump` then jumps to `_tl_do_chap_end_jump`. |
| `_tl_keylistener()` | none | Overlay screen; maps keybinds for `chronology_toggle`, `chronology_route`, and `tl_debug_toggle`. |

---

## UI Modules (`ui/`)

Screen definitions only — no behavior logic. All logic lives in `backend/`.

---

### `ui/tl_theme.rpy`

Design tokens, color contrast helpers, styles, and hover gradient generation.

**Color palette (`TL` dict):**
- `accent` — dynamically chosen via `pick_accent_color`; contrast-checked against header/footer
- `overlay_bg = "#00000099"`
- `noise_alpha = "#ffffff0c"`
- `header_bg = "#000000bb"`, `header_text = "#f0ece4"`, `header_sub = "#9a9183"`
- `new_dot` — accent color
- `card_bg = "#00000000"`, `thumb_bg = "#0a0a0a"`, `divider` — accent at 55% transparency
- `opt_chosen_fg = "#f0ece4"`, `opt_fg = "#f0ece4"`, `opt_new_dot` — accent
- `footer_bg = "#00000055"`, `footer_text = "#9a9183"`, `btn_bg = "#ffffff14"`, `btn_hover_bg = "#ffffff28"`, `hover_bg` — accent at 30%, `btn_text = "#c8c0b4"`
- `modal_bg = "#1a1814ee"`, `modal_header = "#f0ece4"`

**Font size constants** (also defined in `timeline_init.rpy` for backend use):
- `TL_SIZE_BODY = 21`, `TL_SIZE_TITLE = 38`, `TL_SIZE_DOT = 14`, `TL_SIZE_BADGE = 12`, `TL_SIZE_HEADER = 28`, `TL_SIZE_SUBTITLE = 17`

**Font paths:**
- `_tl_font_reg` — Inter-Regular.ttf path or RenPy default fallback
- `_tl_font_bold` — Inter-Bold.ttf path or RenPy default fallback

**Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `hex_to_rgb` | `(hex_color) → tuple` | Converts `#rrggbb` to `(r, g, b)` 0–255. |
| `relative_luminance` | `(rgb) → float` | WCAG relative luminance 0–1 from an RGB tuple. |
| `contrast_ratio` | `(rgb1, rgb2) → float` | WCAG contrast ratio 1–21 between two RGB tuples. |
| `pick_accent_color` | `(bg_colors, fallback="#e8c97e") → str` | Chooses a readable accent from gui color attributes; contrast-checks against backgrounds; returns `#rrggbb`. |
| `_tl_make_hover_gradient` | `(color_hex, center_w=100, edge_w=50, base_hex=None) → Frame` | Generates a horizontal gradient displayable; center is solid, edges fade; `base_hex` triggers Porter-Duff pre-blending so edges match the button's normal background. |
| `_tl_noise_bg` | `() → Solid` | Returns the noise overlay displayable. |

**Styles:**

| Style | Base | Description |
|-------|------|-------------|
| `tl_base` | `text` | Inter-Regular or fallback; size 21; color `#f0ece4`; no bold/italic/outline |
| `tl_base_bold` | `text` | Inter-Bold or fallback; size 21; color `#f0ece4` |
| `tl_icon` | `text` | DejaVuSans; size 14; color `#f0ece4`; no italic/outline |
| `tl_frame_base` | `_default` | Frame base; no background, no padding |

---

### `ui/tl_cards.rpy`

Past and current choice card screens.

**Screens:**

| Screen | Parameters | Description |
|--------|-----------|-------------|
| `tl_thumbnail_frame(cw, th, img_disp=None, locked=False, taken=True, highlighted=False, fallback_text=None)` | `(int, int, Displayable or None, bool, bool, bool, str or None)` | Shared thumbnail frame with lock overlay (unseen), dark overlay (not-taken), or fallback text; used by cards and ghost cards. |
| `tl_card(node, cw=300)` | `(dict, int)` | Dispatches to `tl_card_current` if no chosen_index yet, else `tl_card_past`; resolves thumbnail displayable and "has new" flag. |
| `tl_card_past(node, chosen_label, has_new, cw=300)` | `(dict, str or None, bool, int)` | Past card body: thumbnail + chosen option text + footer (`⎇` when `node["_shadow_orig_chosen"]` is set, `●` when unexplored paths exist, "All options" button). |
| `tl_card_option_row(node, i, opt, cw, shadow_ci)` | `(dict, int, str, int, int or None)` | Single option row in current card; shows unseen/replay-aid indicator, option text, var deltas, conditions. |
| `tl_card_current(node, cw=300)` | `(dict, int)` | Current (unseen) card body: lists all options as rows with "NOW" badge. |

---

### `ui/tl_ghost_cards.rpy`

Ghost branch card screens. Synthesis logic lives in `backend/tl_ghost_logic.rpy`.

**Screens:**

| Screen | Parameters | Description |
|--------|-----------|-------------|
| `tl_ghost_card(ghost, bi, cw, th, hl)` | `(dict, int, int, int, bool)` | Single ghost branch card: thumbnail, lock/taken state, condition text; clickable to toggle highlight. |
| `tl_ghost_rows(ghost_nodes, ghost_highlight, card_w, cols, spacing, reverse_clusters=False)` | `(list, tuple or None, int, int, int, bool)` | Renders all ghost nodes as clustered rows; flattens branches into a flat list, chunks into rows; inserts separator frames between clusters. When `reverse_clusters=True`, clusters are reversed before flattening so the most-recent cluster appears top-left (used in route view). |

---

### `ui/tl_route_screen.rpy`

Route tracker chip bar and mod notification screen.

**Screens:**

| Screen | Parameters | Description |
|--------|-----------|-------------|
| `_tl_notify(message)` | `(str)` | Mod notification toast; zorder 100, auto-dismisses after 3.25 s. Separate from the game's `notify` screen so mod alerts don't interfere with game notifications. |
| `tl_route(tl_route_expanded, tl_route_hover)` | `(bool, str or None)` | Route tracker body: chip bar + ghost card rows. Chip layout computed from `_tl_build_route_chips()`. Dynamic fold row count (`_TL_ROUTE_FOLD`) ensures all highlighted chips are visible. Ghost card rows appended below with `reverse_clusters=True`. Chip tint: `TL["accent"] + "44"` on key half for highlighted vars. |

---

### `ui/tl_modal.rpy`

Full-screen modal showing all options for a single choice node.

**Screens:**

| Screen | Parameters | Description |
|--------|-----------|-------------|
| `tl_modal_option_row(node, i, opt, m_w, opt_count)` | `(dict, int, str, int, int)` | Single option row in modal: chosen/replay-aid/unseen indicator, option text; clicking jumps to and loads that choice. |
| `tl_modal(node)` | `(dict)` | Full modal overlay: node thumbnail (or fallback to thumb bytes), "All options" header, scrollable option list; dismissible via ESC or background click. |

---

### `ui/tl_debug.rpy`

Debug overlay showing game/mod state.

**Store variables (transient):**
- `_tl_debug_visible` (default `False`) — show/hide debug overlay

**Constants:**
- `config.keymap["tl_debug_toggle"] = ["K_BACKQUOTE"]` — backtick to toggle

**Screens:**

| Screen | Parameters | Description |
|--------|-----------|-------------|
| `_tl_debug_overlay()` | none | Conditional wrapper; shows `tl_debug` if `_tl_debug_visible`. |
| `tl_debug()` | none | Draggable panel: RenPy version, branch_id, node/history counts, AST status, last node details (prompt, chosen, options, thumb size, ast_key), CFG dump button. |
| `tl_dbrow(label, value)` | `(str, str)` | Two-column label/value row for the debug panel. |

---

## Python Test Suite (`tests/`)

Run all Python tests: `python3 -m pytest tests/ -q`

---

### `tests/conftest.py`

RenPy stub, `.rpy` loader, and shared production namespace for all test files.

**Key components:**
- **RenPy stub**: mock `renpy`, `store`, `persistent` modules with minimal AST node classes; includes `show_screen`, `seen_image`, translator stub, and `renpy.ast` module stub
- **`.rpy` loader**: `load_rpy(rel_path, ns)` extracts and executes all `init [priority] python:` blocks from a `.rpy` file; requires trailing newline on last block line
- **Shared namespace (`_rpy_ns`)**: loads backend files in this order:
  1. `backend/tl_chapter.rpy`
  2. `backend/tl_menu_location.rpy`
  3. `backend/tl_menu_options.rpy`
  4. `backend/tl_shadow_path.rpy`
  5. `backend/tl_seen_check.rpy`
  6. `backend/tl_saveload.rpy`
  7. `backend/tl_assets.rpy`
  8. `backend/tl_ghost_logic.rpy`
  9. `backend/tl_route_logic.rpy`
  10. `timeline_init.rpy`
  11. `timeline_hooks.rpy`

**Test helpers exported to tests:**
- `_tl_validate_history(history)` — cleans malformed history nodes
- `_tl_node_thumb(node, cache)` — retrieves thumbnail bytes from node or cache
- `_tl_extract_var_deltas_from_source(src)` — parses Python variable assignments
- `_tl_extract_condition_values(conditions)` — extracts variable comparisons from condition strings
- `_tl_build_var_setters(data)` — builds a mapping of variable names to their setters

---

### `tests/test_saveload.py`

**What it tests:** Save slot naming, nearest-save lookup, history validation, context accumulation, save frequency, and two-phase slot consistency.

**Run:** `pytest tests/test_saveload.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestSaveSlot` | 8 | Slot format `_ch_{NNNN}_{hash6}`, zero-padding, determinism, context/index sensitivity, empty context, large index |
| `TestFindNearestSave` | 12 | Exact match, highest-below-target, ignores above-target, context hash must match, fallback to `_ch_start`, ignores recovery/start files, max valid index, context prefix divergence, chapter-end candidate beats lower checkpoint |
| `TestValidateHistory` | 7 | Valid history unchanged, drops non-dict/missing-key/invalid-options entries, reindexes after drop, non-list input returns `[]` |
| `TestContextAccumulation` | 3 | Context grows per choice, slot consistent with context prefix, diverged branch gets different slot |
| `TestSaveDecision` | 7 | Dense saves for indices 0–4, first sparse milestone at index 9, gaps between milestones, custom dense/every params |
| `TestTwoPhaseSlotConsistency` | 3 | Same slot before/after next node, refresh uses only context up to current node, consistency across multiple nodes |
| `TestFindNearestSaveDensePattern` | 2 | Dense+sparse save pattern; target between milestones finds nearest lower save |

---

### `tests/test_chapter.py`

**What it tests:** Chapter deduplication, marker existence, timeline rollback, chapter-end slot naming.

**Run:** `pytest tests/test_chapter.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestChapterDedup` | 6 | Clean dict unchanged, duplicate label keeps first, empty, single entry, three entries with one duplicate |
| `TestChapterMarkerExists` | 6 | Exact match, wrong index, wrong chapter, empty markers, multiple markers, after_idx zero |
| `TestRollbackTimeline` | 8 | Trims to after_index, keeps matching marker, drops later markers, unknown/no-marker label returns originals, rollback to zero, empty chapters dict, history/context sliced consistently |
| `TestChapEndSlotName` | 9 | Plain format `_ch_chap_{label}`, hashed format with context, different context → different slot, same context → same hash |

---

### `tests/test_shadow_path.py`

**What it tests:** Shadow path building, staging, matching, and consumption.

**Run:** `pytest tests/test_shadow_path.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestBuildShadowPath` | 9 | Nodes after target only, target excluded, skips None location/chosen_index, empty tail, invalid index, order preserved, `menu_site_key` derived from `ast_key` |
| `TestStageShadowPath` | 2 | Returns None when empty, preserves `menu_site_key` payload |
| `TestShadowMatch` | 8 | Match at index 0 and mid-path, no match, empty path, first match wins on duplicates, chosen_index zero valid, `ast_key` match preferred over `_location`, site key match without location |
| `TestConsumeShadowPath` | 11 | No match unchanged, first/middle/last entry consumed, no divergence on same choice, divergence on different choice, empty/None path, tail preserved, `menu_site_key` preferred |

---

### `tests/test_seen_check.py`

**What it tests:** New-content detection, seen-function descriptor evaluation, translator lookup, jump follow, Show exclusion, and say_range descriptor.

**Run:** `pytest tests/test_seen_check.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestNodeHasNew` | 11 | All seen → False, none seen → True, partial → True, single option seen/unseen, empty options, chosen option skipped even if unseen, unchosen unseen triggers dot, no chosen_index checks all |
| `TestEvalSeenFn` | 7 | `("never",)` → False, `("say", key)` checks `_seen_ever`, key not in `_seen_ever` → False, None `_seen_ever` → False, `("label", name)` checks `renpy.seen_label`, label unseen, no fn |
| `TestSaySeenName` | 4 | Translator resolves to TranslateSay name; translator returns None → fallback to node.name; no identifier → node.name; lookup raises → node.name |
| `TestFollowJumpSeenName` | 4 | Jump to Say → returns say name; non-Say prefix nodes skipped; no Say before Menu/Return → None; unknown target → None |
| `TestMakeSeenFnExtended` | 7 | Show nodes excluded; multiple Says → say_range; Scene then Say → say descriptor; Scene alone → image descriptor; block ending in Jump with no Say uses jump follow |
| `TestEvalSeenFnSayRange` | 4 | say_range: first not in seen → False; first in seen, last not → False; both in seen → True; fast-fail path verified |

---

### `tests/test_ghost_logic.py`

**What it tests:** Ghost card synthesis, branch notification tiers, and Python.execute filename filter.

**Run:** `pytest tests/test_ghost_logic.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestNotifyBranch` | 7 | All seen → suppress; pre_taken_seen=False → "New path"; taken seen + locked alt → icon-only ⎇; standalone if (taken_index=None) + locked branch → icon-only; standalone if, all seen → suppress; index-based comparison (equal tuples at different indices) correctly excludes only taken branch |
| `TestPythonExecutePatched` | 4 | game/ file → diff called; mod file → diff bypassed; non-game/ file → diff bypassed; replaying=True → diff bypassed |

---

### `tests/test_route_logic.py`

**What it tests:** Route var formatting, diff accumulation, menu-snap flush, consumed check, and chip filtering/ordering.

**Run:** `pytest tests/test_route_logic.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestFormatNumericChange` | 6 | Increase by 1 (no magnitude); increase by 3 (shows magnitude); decrease by 1; decrease by 2; integer delta strips `.0`; fractional delta preserved |
| `TestDiffRouteVars` | 6 | Unchanged var not in pending; changed var added as `(old, new)`; already-pending var keeps original old, updates new; None in snap (init) skipped; changed var added to `_tl_recently_changed_vars`; unchanged var not in recently_changed |
| `TestFlushMenuSnap` | 6 | No snap → no-op; init var (was None) → emits notification + adds to recently_changed; non-init var (was non-None) → skipped; numeric var → arrow format; snap cleared after flush |
| `TestVarConsumed` | 5 | if_count 0 → False; seen below total → False; seen equals total → True; seen exceeds total → True; var not in if_count → False |
| `TestBuildRouteChips` | 11 | if_count 0 → excluded; None value → excluded; list value → excluded; consumed + low count → excluded; consumed + high count → shown; unconsumed → shown; ghost var shown even if consumed; recently-changed shown even if consumed; ghost vars ordered before non-ghost; within group ordered by if_count desc; chip value matches store |

---

### `tests/test_assets.py`

**What it tests:** Node thumbnail retrieval priority and asset thumb cache key generation.

**Run:** `pytest tests/test_assets.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestNodeThumb` | 5 | `thumb_bytes` on node takes priority, falls back to persistent cache by `ast_key`, returns None when both missing, bytes preferred over cache, cache miss with key returns None |
| `TestAssetThumbDisplayCacheKey` | 2 | Key includes img_name/width/height/fit_mode, defaults to 320×180 cover |

---

### `tests/test_menu_location.py`

**What it tests:** Menu site key derivation from history nodes.

**Run:** `pytest tests/test_menu_location.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestNodeMenuSiteKey` | 2 | Prefers `ast_key` tuple, falls back to `_location` file/line |

---

### `tests/test_menu_options.py`

**What it tests:** Choice entry filtering, index resolution, return value lookup, choice-return population, and `record_after` identity.

**Run:** `pytest tests/test_menu_options.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestValidChoiceEntries` | 1 | Caption-only (None value) entries filtered, order preserved |
| `TestChoiceEntryForIndex` | 2 | Valid index retrieves entry, out-of-range returns None |
| `TestChoiceIndexFromReturnValue` | 2 | Index-based match preferred with duplicate labels, `ChoiceReturn.value` attribute fallback |
| `TestPopulateChoiceReturns` | 1 | Fills array with `ChoiceReturn` objects by valid index |
| `TestRecordAfter` | 2 | Index preferred when labels repeat, legacy label fallback still works |

---

### `tests/test_cf_adapter.py`

**What it tests:** `RenpyFlowGraph` control-flow graph: edge types, successors/predecessors, cycle detection, SCC computation. 55 tests.

**Run:** `pytest tests/test_cf_adapter.py -v`

| Class | Tests | Covers |
|-------|-------|--------|
| `TestStraightLine` | 7 | Sequential edges, entry points, terminal nodes |
| `TestIfWithElse` | 4 | `if_arm` edges for both arms, no `if_fallthrough` when else present |
| `TestIfWithoutElse` | 4 | `if_arm` + `if_fallthrough` to post-if |
| `TestMenu` | 4 | `menu_arm` edges, post-menu predecessors |
| `TestEmptyArm` | 4 | Empty arm edge deposits directly to post-if |
| `TestJumpCrossLabel` | 4 | `jump` edge to target label entry, no sequential after jump |
| `TestStringNext` | 2 | String `next` field resolves to label entry |
| `TestCallReturn` | 4 | `call` to callee entry, `return` wired to post-call, no sequential after call |
| `TestSimpleCycle` | 7 | Cycle header detection, back-edge marking, forward edges not marked, hub SCC membership |
| `TestMultiLabelCycle` | 6 | Inter-label cycle, back-edge from arm back to hub, SCC contains arm statements, exit not in SCC |
| `TestUserStatementHub` | 8 | `screen_jump` edge type, back-edges from both arms, hub SCC membership |
| `TestNamedEmptyBlockLabel` | 4 | Empty label resolves through `next_label` chain; jumps to empty label reach menu |
| `TestNestedIfInMenuArm` | 8 | If inside menu option, multi-path post-menu predecessors, `stmt_at` population |
| `TestCallMultipleReturns` | 4 | Multiple return paths wired to same post-call |
| `TestStmtAt` | 5 | All nids in `stmt_at`, types correct for all statement types |

---

## RenPy In-Game Test Runner (`timeline_tests.rpy`)

Tests RenPy-dependent behavior that cannot be run outside the engine.

**Trigger:** Press **Shift+F9** during gameplay.

**Output:** Written to `renpy-chronology-mod/debug.txt` via `_tl_log()`; in-game toast shows pass/fail count.

**Suites (19 total):**

| Suite | Tests | Covers |
|-------|-------|--------|
| `persistent` | 3 | Persistent state initialized as correct types |
| `store_defaults` | 6 | Store variables exist with correct types |
| `hooks` | 3 | `exports.menu` and `store.menu` wrapped exactly once |
| `save_slot` | 5 | Slot format, determinism, context/index sensitivity |
| `thumbnail` | 4 | Returns bytes or None, valid PNG header, non-empty bytes |
| `thumb_cache` | 4 | Write/read-back, eviction keeps at max, newest entries preserved |
| `record_pipeline` | 10 | `_tl_record_before` → `_tl_record_after` full flow: node dict, options, index, context |
| `node_has_new` | 3 | New content detection via `ChoiceReturn` (live and crash-safe fallback) |
| `validate_history` | 3 | Malformed entries dropped, reindexed |
| `chapter_store_defaults` | 3 | Chapter feature store variables exist with correct types |
| `chapter_marker_dedup` | 4 | Duplicate marker at same position detected; different position not seen |
| `label_jump_rollback` | 6 | Fallback rollback when chapter-end save missing: history/context/count trimmed, label_jump set |
| `chap_end_slot_name` | 4 | Hashed format, prefix, context-sensitive, deterministic |
| `shadow_path_defaults` | 2 | Shadow path store/persistent vars initialized |
| `shadow_path_jump` | 6 | Shadow path staged correctly after jump: entries, location, chosen_index |
| `shadow_path_empty_tail` | 1 | None when no nodes after target |
| `shadow_path_consume` | 2 | `_shadow_orig_chosen` stamped on divergence; path trimmed |
| `shadow_path_no_diverge` | 3 | No divergence flag when same choice made; path consumed to None |
| `shadow_path_validate` | 3 | Corrupted shadow path reset to None; valid list and None preserved |

---

## Tools

### `tools/cf_adapter.py`

Builds a statement-level directed graph from the Ren'Py JSON AST dump with typed edges, back-edge detection, and Tarjan SCC for cycle identification. Used as a foundation for offline analysis tools.

**Class:** `RenpyFlowGraph(ast: dict, start: str, stop: str | None = None)`

**Public API:**

| Member | Type | Description |
|--------|------|-------------|
| `successors(nid)` | method | Returns `list[(nid, edge_kind)]` — outgoing edges from `nid`. |
| `predecessors(nid)` | method | Returns `list[(nid, edge_kind)]` — incoming edges to `nid`. |
| `label_entry` | property (dict) | Maps label name → first statement's nid. |
| `stmt_at` | property (dict) | Maps nid → statement dict. |
| `is_back_edge(src, dst)` | method | Returns True if `(src, dst)` is a back-edge (detected via DFS coloring). |
| `cycle_headers` | property (set) | Nids that are destinations of back-edges (cycle entry points). |
| `hub_scc` | property (dict) | Maps each cycle header nid → set of nids in its strongly connected component. |

**Edge kinds:**
- `"sequential"` — normal statement-to-statement control flow
- `"if_arm"` — If node to a condition arm entry
- `"if_fallthrough"` — If node directly to post-If when no else arm
- `"menu_arm"` — Menu node to an option arm entry
- `"jump"` — Jump statement to target label entry
- `"call"` — Call statement to callee label entry
- `"return"` — Return statement to post-Call node (computed in pass 3)
- `"screen_jump"` — UserStatement to screen-targeted label

**Build passes (all iterative, no recursion):**
1. **Pass 1 — label discovery:** BFS from `start`; resolves empty-block labels by following `next_label` chains
2. **Pass 2 — edge collection:** walks all reachable blocks; collects typed edges and populates `stmt_at`
3. **Pass 3 — Return wiring:** BFS from each callee entry finds all reachable Return nodes and links them to post-Call nids
4. **Pass 4 — back-edge detection:** iterative DFS with grey/black coloring; grey→grey edge is a back-edge
5. **Pass 5 — Tarjan SCC:** iterative Tarjan algorithm; cycle headers are destinations of back-edges

**nid format:** Derived from `tuple(stmt["name"])` when present (gives `(filename, serial, line)`); falls back to `(filename, line)` from `linenumber`/`line` fields; last resort is a sequential counter `("_seq", n)`.

---

## Supporting Files

### `game-chapters/`

Per-game chapter definition files. The file named in the mod config is loaded at startup by `_tl_load_chapters()`.

**JSON format:**
```json
{
    "_comment": "Ignored — any key starting with _ is skipped",
    "Chapter Display Name": "renpy_end_label",
    "Another Chapter": "another_end_label"
}
```

**Rules:**
- Keys starting with `_` are ignored (metadata/comments)
- Values are RenPy label names at the chapter's narrative end
- Duplicate labels are silently dropped; first occurrence wins
- Absent or unparseable file disables chapter indicators gracefully

**To find a label name:** Open the RenPy console (Shift+O) and run `renpy.game.context().current`.

**Shipped files:**
- `sample.json` — template shipped with base releases
- `imperial-chronicles.json` — Imperial Chronicles chapter mapping
- `shutupanddance.json` — ShutUpAndDance chapter mapping

---

### `cfg/full_ast.json`

Full game AST in JSON form. Generated by calling `_tl_cfg_dump_ast()` from the debug overlay or in-game console. Source of truth for offline analysis tools.

---

### `debug.txt`

Runtime log written by `_tl_log()`. Appended to each session. Contains errors, key state transitions (jump start/load, replay resume, AST map build, save failures), and profiling output when `TL_PROFILE_TIMELINE = True`. Safe to delete — recreated on next session.