# Changelog

All changes are listed by commit, most recent first. The Unreleased section covers work
that is present in the codebase but not yet committed.

---

## Unreleased

### Refactor: Remove dead functions `_tl_branch_img` and `_tl_first_scene_img`

- **`backend/tl_ghost_logic.rpy`** — removed `_tl_branch_img` (old single-image branch resolver, superseded by `_collect_branch_imgs`) and its shim `_tl_first_scene_img`. Both had zero callers outside each other. Current image pipeline: `_tl_resolve_cluster_imgs` → `_collect_branch_imgs` → `branch_img_seqs`.

### Refactor: Logging audit — per-subsystem debug flags, missing observability, noise reduction

- **`timeline_init.rpy`** — added three opt-in debug flags: `TL_DEBUG_GHOST` (ghost synthesis detail), `TL_DEBUG_SEEN` (seen-state resolution), `TL_DEBUG_ROUTE` (var diff per Python block). Pattern identical to existing `TL_PROFILE_TIMELINE`.
- **`backend/tl_ghost_logic.rpy`** — gated 12 high-volume logs behind `TL_DEBUG_GHOST`: `TL if execute`, branch-img tier 1/2/3, `TL collect_branch_imgs hop`, all four `TL cluster:` decision logs, `TL ghost _regions`, `TL ghost cluster_imgs` (×2). Added `TL notify: tier=...` to `_tl_notify_branch` (always-on, fires once per If-run).
- **`backend/tl_seen_check.rpy`** — gated 4 high-volume logs behind `TL_DEBUG_SEEN`: `TL opt_seen src=ast_map` (×2), `TL opt_seen src=none`, `TL peek_seen menu_lookup=None`. These fired O(options × cards) per timeline open.
- **`backend/tl_route_logic.rpy`** — added always-on `TL var notify` and `TL menu_snap notify` to flush functions; added `TL_DEBUG_ROUTE`-gated `TL route chips: N/M vars shown` and `TL var diff` per detected change in `_tl_diff_route_vars`.
- **`backend/tl_chapter.rpy`** — added `TL chapters: loaded N from path` success log to `_tl_load_chapters`.

### Fix: Ghost cards — ParameterizedText Show branches always locked

- **`backend/tl_seen_check.rpy`** — `_tl_make_seen_fn`: Show nodes whose imspec contains expression arguments (e.g. `show bottom_text012 _("кошмар")`) are now captured as `("image", raw_parts_tuple)` rather than falling through to `("never",)`. RenPy stores raw imspec parts directly in `_seen_images` (no evaluation), so passing the parts tuple to `renpy.seen_image` correctly resolves seen state. Plain Show nodes (only simple identifiers like `show eileen happy`) remain excluded — they are character overlays shared across many branches and are branch-ambiguous in `_seen_images`.

### Feature: Header coverage bars — Dialogue % and Scenes %

- **`backend/tl_coverage.rpy`** (new): `_tl_build_coverage_index(nodes)` — standalone AST walk (same label-block iterative pattern) that collects unique Scene/Show image name tuples and reads `len(translator.default_translates)`; writes `store._tl_total_image_count` and `store._tl_total_say_count`. Called from `_tl_build_ast_map` immediately after `_tl_build_route_index`. Kept separate from route logic so the two concerns don't mix.
- **`timeline_init.rpy`** — added `_tl_build_coverage_index(nodes)` call; added `default _tl_total_say_count = 0` and `default _tl_total_image_count = 0`.
- **`timeline_screen.rpy`** — replaced the "N choices with new paths" hbox with a `vbox` containing two coverage bar rows (Dialogue and Scenes) and a `~ approx` disclaimer. Each row has a label, a thin accent-fill bar (`StaticValue`), and an integer percentage. The block is hidden until the AST is ready and at least one denominator is non-zero; each row is individually hidden when its denominator is zero.
- **`ui/tl_theme.rpy`** — added `style tl_coverage_bar` (90×6 px, accent left-fill, btn_bg right-fill, no thumb).

### Fix: Ghost card condition display — string values unquoted and not prettified

- **`backend/tl_ghost_logic.rpy`** — `_tl_prettify_condition`: replaced regex-based substitution with `ast.parse(cond, mode="eval")` + `ast.walk`. `Name` nodes are prettified via `_tl_prettify_var`; `Constant` string nodes have their quotes stripped and value emitted bare; numeric constants are left as-is. Replacements applied right-to-left by `col_offset`. Regex path kept as fallback (also fixed: now correctly strips string literals before matching). Result: `route_id == "cold_castle"` now shows as `Route Id == cold_castle`.

### Tests + docs: route tracker, non-intrusiveness audit, seen-check and ghost-logic coverage

- **`tests/test_route_logic.py`** (new): 34 tests covering `_tl_format_numeric_change`, `_tl_diff_route_vars`, `_tl_flush_menu_snap`, `_tl_var_consumed`, `_tl_build_route_chips`.
- **`tests/test_seen_check.py`**: added 18 tests covering `_tl_say_seen_name` (translator lookup and fallbacks), `_tl_follow_jump_seen_name` (jump target hop), `_tl_make_seen_fn` Show exclusion and `say_range` descriptor, and `_tl_eval_seen_fn` `say_range` fast-fail. Fixed 3 pre-existing tests whose expectations were stale after `_tl_make_seen_fn` was refactored to iterate block lists directly rather than walk `.next` links.
- **`tests/test_ghost_logic.py`**: added 11 tests covering `_tl_notify_branch` three-tier logic (suppress / icon-only / new-path, standalone if, index-based comparison) and `_tl_python_execute_patched` filename filter (game script / mod file / non-game file / replaying guard).
- **`tests/conftest.py`**: added `show_screen` to renpy stub; added `_TranslatorStub` and `TranslateSay` node stub; extended `persistent` with route-tracker keys; added `backend/tl_ghost_logic.rpy` and `backend/tl_route_logic.rpy` to the shared load list.
- **`docs/ROUTE_TRACKER.md`** (new): full feature doc for the route tracker subsystem — data pipeline, chip filtering/ordering rules, var change notification flow, store/persistent variable reference, files.
- **`docs/NON_INTRUSIVENESS.md`** (new): patch surface audit — monkey-patches, store replacements, config mutations, namespace safety, save/load compatibility, and known ecosystem risk.
- **`docs/CODE_FLOW.md`**: updated Backend Modules (added `tl_route_logic.rpy`, updated `tl_ghost_logic.rpy` and `tl_seen_check.rpy` function lists, added `ui/tl_route_screen.rpy`); rewrote Seen-State Flow; added Route Tracker Flow and Var Change Notification Flow sections.
- **`docs/DEV_NOTES.md`**: added `backend/tl_route_logic.rpy` section; updated `tl_seen_check.rpy` section (new descriptor types, new functions); updated `tl_ghost_logic.rpy` section (new functions); added `ui/tl_route_screen.rpy` UI section; updated `ui/tl_ghost_cards.rpy` (`reverse_clusters` param); updated `timeline_screen.rpy` (route tab, `_tl_toggle(view)`, `_tl_capture_hover_pos`); updated conftest load order; added `test_route_logic.py` entry; updated `test_seen_check.py` and `test_ghost_logic.py` entries.
- **`docs/SESSION_GUIDE.md`**: added route tracker to subsystem list, UI list, task routing table, and common follow-up docs.

### Feature: Chip view — dynamic rows for highlighted vars + recently-changed var highlighting

- **`ui/tl_route_screen.rpy`**: `_TL_ROUTE_FOLD` is now computed dynamically instead of being a fixed constant. After counting highlighted chips (`_tl_hl_count`), the visible row budget is `max(3, ceil(_tl_hl_count / _tl_chips_per_row))` rows, so all highlighted chips are always visible without requiring the "N more" expand. When no chips are highlighted the default is 3 rows. Highlighted set now unions ghost vars and recently-changed vars: `_tl_highlighted = _tl_ghost_vars | (store._tl_recently_changed_vars or set())`.
- **`backend/tl_route_logic.rpy`**: `_tl_diff_route_vars` and `_tl_flush_menu_snap` both populate `store._tl_recently_changed_vars` for every changed or newly-assigned var, so vars that just received a change notification are immediately tinted in the chip bar. `_tl_build_route_chips` sort key and consumed-filter exemption updated to use `highlighted = ghost_vars | recently_changed`.
- **`timeline_hooks.rpy`**: `_tl_record_before` clears `store._tl_recently_changed_vars = set()` at the start of each menu so the highlight decays at the next choice point.
- **`timeline_init.rpy`**: added `default _tl_recently_changed_vars = set()`.

### Fix: Seen-check — `say_range` descriptor and jump-follow for language-specific seen check

- **`backend/tl_seen_check.rpy`** — `_tl_make_seen_fn`: when multiple Say/TranslateSay nodes are found in a branch block, returns `("say_range", first_name, last_name)` instead of only the last. The first node is used as a fast lock check — if it is absent from `_seen_ever`, the branch is guaranteed unseen. The last node confirms the whole block was traversed. This eliminates false "unlocked" states for branches that were partially seen in a prior session.
- **`backend/tl_seen_check.rpy`** — `_tl_eval_seen_fn`: added `"say_range"` case: returns `False` immediately if `seen_fn[1]` (first Say) is not in `_seen_ever`; otherwise returns `bool(seen_fn[2] in _seen_ever)` (last Say).
- **`backend/tl_seen_check.rpy`** — added `_tl_follow_jump_seen_name(target, max_hops=30)`: follows a Jump target one hop through the namemap to find the first Say/TranslateSay, resolves its `_seen_ever` key via `_tl_say_seen_name`. Used as a fallback in `_tl_make_seen_fn` when a branch block ends in a Jump with no Say/Scene found before it. Fixes menus like `cold_castle` where option blocks are pure `$ var = …; jump label` — previously these fell back to `renpy.seen_label` which is language-agnostic and reported True for labels visited in a different locale.

### Fix: Icon-only notification — index-based comparison, standalone locked if

- **`backend/tl_ghost_logic.rpy`** — `_tl_notify_branch`: the non-taken branch seen check now iterates using `_i != _taken_glob_i` (flat index) instead of `_sfn is not _taken_fn` (object identity). Two independently built equal tuples were not `is`-equal, causing all-seen branches to fire spurious icon-only notifications.
- **`backend/tl_ghost_logic.rpy`** — `_tl_notify_branch`: removed the early return on `_taken_glob_i is None`. Standalone `if` conditions that are not satisfied (locked card, `taken_index=None`) still have a locked branch — the icon-only notification fires if any branch is locked, signaling that something is missable here.
- **`backend/tl_ghost_logic.rpy`** — `_tl_on_if_execute`: passes `pre_taken_seen` to `_tl_notify_branch`; "New path" tier fires only when `pre_taken_seen is False` (explicit pre-execute False from a resolvable descriptor). `None` (indeterminate, `("never",)` descriptor) suppresses.

### Fix: Numeric var change notification — show delta magnitude

- **`backend/tl_route_logic.rpy`** — added `_tl_format_numeric_change(label, old_val, new_val)`: formats numeric var changes as `↑N Label` or `↓N Label`. When the delta is exactly 1, the magnitude is omitted (`↑ Label`). Arrows use `{font=DejaVuSans.ttf}` for correct Unicode rendering. `_tl_flush_var_changes` and `_tl_flush_menu_snap` both use this helper for vars in `persistent._tl_var_is_numeric`.

### Fix: Python.execute patch — restrict to game scripts, guard post-processing

- **`backend/tl_ghost_logic.rpy`** — `_tl_python_execute_patched`: added filename filter matching `_tl_should_track_if_node` — only intercepts nodes where `filename.startswith("game/")` and `"renpy-chronology-mod" not in filename`. Previously the patch ran on all Python nodes including Ren'Py internals (e.g. `screen_load_save.rpym`), causing pickle failures when the save screen's `$ ui.interact()` triggered a route-var snapshot that captured `store.json` (the json module). Wrapped post-processing (`_tl_diff_route_vars`, `_tl_flush_var_changes`) in try/except with log so any failure there cannot propagate and block the original execution returning.

### Fix: Ghost cards missing for non-equality conditions (`>`, `<`, compound `and`)

- **`backend/tl_ghost_logic.rpy`** — `_tl_build_ghost_payload`: removed the `_any_parsed` gate that returned `None` when no condition string could be parsed by `_tl_parse_regions`. `_tl_parse_regions` only handles `==`-based conditions for clustering; conditions using `>`, `<`, `>=`, `<=`, or compound `and`/`or` mixing relational operators all returned `None`, silently dropping the ghost card. Now payloads are built regardless — `_regions = None` on the resulting payload already signals `_tl_should_cluster` to leave these cards unclustered.

### Fix: Seen-state — TranslateSay support, correct priority, and pre-execute notification snapshot

**`backend/tl_seen_check.rpy`**:

- Added `_tl_say_seen_name(node)` helper: resolves the correct `_seen_ever` key for a `Say` or `TranslateSay` node by looking up the node's `identifier` through the Ren'Py translator. For translated games, `_seen_ever` is keyed by the `TranslateSay` node name from the translation file, not the original `Say` node name; the translator lookup gets the right key. Falls back to `node.name` when no translation exists.
- `_tl_make_seen_fn`: rewrote priority model. Now tracks `_say_best` (last Say/TranslateSay, via `_tl_say_seen_name`) and `_scene_best` (first `Scene` node only) separately. `Show` nodes are intentionally excluded — character sprite overlays are shared across branches and cause false positives via `renpy.seen_image`. Return order: `_say_best or _scene_best or ("label", target) or ("never",)`. Previously the function used a single `_best` that could be overwritten by a later `Show` after a Say, and also checked `("Say",)` without translator resolution so all checks returned False on translated games.

**`backend/tl_ghost_logic.rpy`**:

- `_tl_if_execute_patched`: evaluates `_tl_make_seen_fn` + `_tl_eval_seen_fn` on the taken branch's block **before** `_tl_orig_if_execute` runs. `Scene.execute` is called synchronously inside `If.execute` and updates `_seen_images`, so any post-execute eval of image-based descriptors is a false positive. Stores result as `_pre_taken_seen` (`False` = branch was locked, `True` = already seen, `None` = descriptor was `("never",)` — indeterminate). Passes `_pre_taken_seen` to `_tl_on_if_execute`.
- `_tl_notify_branch`: "New path" notification now fires only when `pre_taken_seen is False` — an explicit pre-execution False from a resolvable descriptor. `None` (indeterminate) suppresses. The `⎇` (alternatives unseen) tier is unchanged.

### Fix: Conditional menu options — exclude locked options, align `_option_conditions`

**`timeline_hooks.rpy`** — `_tl_record_before`:

- `valid_items` filter changed from `else:` to `elif value is not False:`. Ren'Py passes locked options (condition evaluated False) to the menu wrapper with `value=False`; they were previously collected into `node["options"]` alongside available choices. Now excluded.
- `_option_conditions` alignment fixed: the AST item loop now skips any item whose label is not in `valid_items` (locked at runtime), so `_option_conditions[i]` always corresponds to `options[i]`.

### Fix: Ghost card seen-state — use `persistent._seen_images` instead of `renpy.seen_label`

- **`backend/tl_seen_check.rpy`** — `_tl_make_seen_fn`: added `Scene`/`Show` case in `find_check` before the Jump/Call cases. When the first meaningful node in a branch block is a `scene` or `show`, resolves the image name via `_tl_scene_stmt_img_name` and returns `("image", tuple(name.split()))`. This takes priority over the convergence-label fallback.
- **`backend/tl_seen_check.rpy`** — `_tl_eval_seen_fn`: added `"image"` case that calls `renpy.seen_image(name_tuple)`, which checks `persistent._seen_images` — Ren'Py's native per-image display tracker. Unlike `renpy.seen_label`, this is branch-specific: `scene ch8_cho1` only sets `("ch8_cho1",)`, so two branches jumping to the same convergence label are no longer both marked seen.
- Jump/Call cases unchanged — branches with no scene/show/say before a jump still use `("label", target)` as a conservative fallback.
- Docstring updated to document the `("image", name_tuple)` descriptor.

### Fix: Route tooltip — numeric var suppression, anchor freeze, styling

- **`backend/tl_route_logic.rpy`**: Numeric var detection based on write patterns instead of relational operators. `AugAssign` (`+=`/`-=`) and `Assign` with arithmetic RHS (`var = var + n`) mark a var as numeric in `persistent._tl_var_is_numeric`. This avoids false-positives on int-valued enum vars that game authors check with `>` or `<`. Removed `_TL_ROUTE_SKIP_NAMES` frozenset (could false-positive real route vars now that the label-based AST walk is the primary collector).
- **`timeline_screen.rpy`**: Tooltip suppressed for numeric vars and vars with empty domain (`if _tt_domain:` gate). Position frozen at hover-start via `store._tl_route_hover_pos` captured by `Function(_tl_capture_hover_pos)` in the chip's `hovered` action — no longer follows the mouse. Arrow `→` uses the same color as the current-route text (not accent). Current-route text uses `tl_base` (not bold). Tooltip `xsize 220`. All ternary expressions in the for-loop precomputed in a `python:` block to avoid Ren'Py parse errors.
- **`ui/tl_route_screen.rpy`**: Chip `hovered` action also calls `Function(_tl_capture_hover_pos)` to freeze the tooltip anchor.

### Feature: Ghost card cluster reversal in Route Tracker

- **`ui/tl_ghost_cards.rpy`**: `screen tl_ghost_rows` accepts a new `reverse_clusters=False` parameter. When `True`, ghost nodes are grouped into clusters (consecutive nodes with `cluster_with_prev == True`) and the cluster list is reversed before flattening, so the most-recent cluster appears top-left. Card order within each cluster is preserved.
- **`ui/tl_route_screen.rpy`**: Call site passes `True` for `reverse_clusters`.

### Feature: Route chip tooltip — domain display + var domain calculation

- `config.keymap["chronology_route"] = ["r"]` registered alongside the existing `chronology_toggle` (`t`) keymap.
- `_tl_toggle(view=None)` now accepts an optional `view` argument. When the timeline is closed, it opens on the requested tab. When already open, pressing the same tab's key closes it; pressing the other tab's key switches views. Esc always closes.
- `screen _tl_keylistener` and the in-screen `key` bindings updated: `T` calls `_tl_toggle("cards")`, `R` calls `_tl_toggle("route")`.

### Feature: Route chip tooltip — domain display + chip accent highlight

- **`backend/tl_route_logic.rpy`**: Extended `_tl_build_route_index` to collect literal domain values into `persistent._tl_var_domain = {var: sorted_list_of_strings}`. Two sources: (1) Python-node pass captures RHS literals from `Assign` nodes (`Constant`/`Str`/`Num`); (2) If-node pass parses each condition string with `ast.parse` and captures `Eq`/`NotEq` comparator literals. Domain sets per var are unioned across both passes and stored sorted.
- **`ui/tl_route_screen.rpy`**: Ghost-active chips (var appears in a current ghost card cluster) now receive a faint accent tint (`TL["accent"] + "44"`) on the key-half background instead of the `●` dot indicator. The dot and its wrapper hbox are removed.
- **`timeline_screen.rpy`**: Route chip tooltip replaced with a domain panel: "Possible Routes" header, 1 px faint divider, then one row per known value. Current value gets `→` prefix (accent color, bold); non-current values are muted. If `_tl_var_domain` has no values for a var, only the header and divider render (no crash).

### Feature: Route Tracker — var filtering, ordering, ghost cards, and UI polish

Full Route Tracker implementation built on top of the initial stable-UI chip bar.

**Backend — `backend/tl_route_logic.rpy`** (new, `init -2`):
- `_tl_build_route_index(nodes)`: walks all If and Python nodes from game scripts (game scripts only: `filename.startswith("game/")` and `"renpy-chronology-mod" not in filename`). Python-node walk collects bare `Name` assignment targets into `persistent._tl_route_var_names`. If-node walk builds `persistent._tl_var_if_count = {var: int}` (total If-entries referencing each var across the whole game) and `store._tl_var_seen_descs = {var: [descriptor_tuple, ...]}` (seen descriptors per var, rebuilt each AST walk so never stale).
- `_tl_var_consumed(var_name)`: returns True when every If-branch descriptor for a var evaluates True via `_tl_eval_seen_fn`.
- `_tl_build_route_chips()`: filters vars — hides if `if_count == 0` (never gates content) or if consumed and `if_count <= 5` (player is past all decision points and the var is not globally important); orders ghost vars first by `if_count` desc, then remaining vars by `if_count` desc.
- `_TL_ROUTE_HIGH_THRESHOLD = 5`: vars tested in more than 5 If-branches are always shown even if consumed (globally significant vars like `perk`).

**`timeline_init.rpy`**: replaced the inline Python-node var collection block in `_tl_build_ast_map` with a single `_tl_build_route_index(nodes)` call. `persistent._tl_route_var_names` (was `store`) so it survives save/load cycles.

**`ui/tl_route_screen.rpy`**: `_tl_build_route_chips()` moved to backend. Screen now accepts `tl_route_expanded` and `tl_route_hover` as parameters from `screen timeline()` and uses `SetScreenVariable` to update them. Key/value chip design: each chip is a fixed-width button with two frames — key half (`btn_hover_bg`, 55% width) and value half (`btn_bg`, 45% width); widths computed from available screen width with dynamic column count (same formula as the cards grid). `key "rollback"/"rollforward" action NullAction()` suppresses scroll-triggered rollback. Content wrapped in `viewport: mousewheel True draggable True`. Ghost card cluster appended below chip bar via `use tl_ghost_rows(...)` with 24 px breathing room above and `spacing` px between the divider and first ghost row.

**`ui/tl_ghost_cards.rpy`**: `screen tl_ghost_rows` content wrapped in an outer `vbox: spacing spacing` so the divider-to-first-card gap is always `spacing` px regardless of the parent container's own spacing. Previously the divider and ghost card vbox were inlined as separate siblings into the parent vbox, so the gap was controlled by the parent's spacing (16 px in the cards screen, 4 px in the route screen).

**`timeline_screen.rpy`**: `tl_route_expanded` and `tl_route_hover` defined as `default` at screen level and passed as parameters to `use tl_route(...)`. Route tooltip moved to screen top level and positioned absolutely at `renpy.get_mouse_pos() + (14, 14)` so it floats near the cursor instead of appearing inline at the bottom of the vbox. Ghost card rows removed from the History cards view (route screen only). Subtitle text switches between "Choice History" (History tab) and "Route Tracker" (Route tab).

### Feature: Route screen stable UI

First milestone of the route screen: chip bar showing current store values for tracked vars, toggled from the timeline header.

- `timeline_init.rpy`: extended `_tl_build_ast_map` to parse Python nodes with the stdlib `ast` module and collect bare `Name` assignment targets into `store._tl_route_var_names`; filters `_`-prefixed names and a builtin skiplist; added `default _tl_route_var_names = set()`
- `ui/tl_route_screen.rpy` (new): `screen tl_route()` with a flow-layout chip bar; chips ordered by ghost-var relevance then alphabetically; "N more" expand/collapse for overflow; empty tooltip placeholder (styled frame, body deferred); `_tl_build_route_chips()` helper
- `timeline_screen.rpy`: added History/Route toggle buttons to the header hbox; `default tl_view = "cards"`; route view replaces cards body via `use tl_route()`

Domain inference, seen/unseen logic, and var categorization are deferred to the next milestone.

---

### Fix: jump-back no longer forces skip_unseen

Removed the two lines that set `renpy.game.preferences.skip_unseen` during replay. The mod now leaves the player's preference untouched — fast-forward still fires (`config.skipping = "fast"`), but whether unseen content is skipped depends on whatever the player has set in RenPy's preferences.

- `timeline_hooks.rpy`: removed `skip_unseen = True` in `_tl_on_load` and `skip_unseen = False` in the replay-end cleanup

---

### Fix: remove dead var delta references after tl_var_delta.rpy deletion

Removed all references to the deleted `backend/tl_var_delta.rpy` approach:

- `ui/tl_cards.rpy`: removed `_tl_reachable_data`, `_tl_delta_is_shown`, `_tl_format_delta` usage and the delta rendering rows from `tl_card_option_row`; kept `_option_conditions` display
- `timeline_hooks.rpy`: removed `_var_deltas` node field and `_tl_extract_var_deltas` call from the option extraction loop; kept `_option_conditions` extraction; updated comment and log message
- `timeline_init.rpy`: removed `default _tl_reachable_map` and orphaned `import ast as _tl_python_ast`
- `timeline_save_hooks.rpy`: updated comment to drop `_tl_reachable_map` reference
- `docs/DEV_NOTES.md`: removed `_tl_reachable_map` from store defaults list

Existing saves retain `_var_deltas` in their nodes as inert dead data; no migration needed since the UI no longer reads the field.

### Stash: Flowchart approach

Stashed `tools/parse_svg.py`, `tools/build_presentation.py`, `tools/build_vis.py`,
`timeline_flowchart.rpy`, and `tests/experiments/test_flowchart.py`.

Design doc: `docs/Experiments/UI_GRAPH_APPROACH.md`, `docs/Experiments/CFG_BUILDER_NOTES.md`.
Stash message: `flowchart clean bucket`.

### Stash: Causal analysis approach

Stashed `tools/experiments/causal_analysis.py`, `gen_cfg.py` (experiment copy), and
`tests/experiments/test_causal.py`.

Design docs: `docs/Experiments/CAUSAL_DAG_Z3.md`, `docs/Experiments/CAUSAL_ANALYSIS_STATUS.md`.
Stash message: `Experiment: Causal analysis approach (see docs/Experiments/CAUSAL_DAG_Z3.md, CAUSAL_ANALYSIS_STATUS.md)`.

### Stash: Formula ITE solver approach

Stashed `tools/experiments/formula_solver.py`, `formula_bfs.py`, and
`tests/experiments/test_formula_bfs.py`, `test_formula_integration.py`.

Design doc: `docs/Experiments/FORMULA_SOLVER_DESIGN.md`.
Stash message: `Experiment: Formula ITE solver approach (see docs/Experiments/FORMULA_SOLVER_DESIGN.md)`.

### Stash: Z3 causal slice approach

Stashed `tools/experiments/causal_slice.py`, `causal_verify.py`, and
`tests/experiments/test_causal_slice_l2–l5.py`, `test_causal_verify.py`.

Design doc: `docs/Experiments/CAUSAL_DAG_Z3.md`.
Stash message: `Experiment: Z3 causal slice approach (see docs/Experiments/CAUSAL_DAG_Z3.md)`.

### Fix: refresh save blocked by skip guard when player resumes skip after blocking input

Removed `not config.skipping` from the refresh save condition in `_tl_record_before`.

The skip guard was added when thumbnails were captured via live screenshot — saving during
fast skip caused WebP decode races in RenPy 7.5.x. Thumbnails now come from game assets,
so that race no longer exists. The guard was left on the refresh path by mistake.

Effect of the bug: if a player pressed skip → hit a blocking input → pressed enter →
resumed skip immediately, `_tl_record_before` fired for the next menu while `config.skipping`
was True. The refresh was suppressed, leaving the checkpoint at the blocking input instead
of advancing it to menu entry. Jumping back to that menu then loaded the pre-blocking-input
save and stalled.

Also removed diagnostic log lines added during the investigation (`find_nearest SKIP`,
`deferred save`, `refresh save`).

### Single-variable route idea doc

Added `docs/SINGLE_VAR_ROUTE_IDEA.md` to capture the current variable-local
route direction separately from the older causal/Z3 notes.

- defines write frontiers, evolution dependencies, co-read dependencies, and
  versioned writes
- records the intended frontier-to-frontier route model
- documents what the `coronation` prototype has already validated
- explicitly notes that later co-read vars should not be folded into a target
  variable's evolution model

### Single-variable frontier prototype for `coronation`

Added `tools/experiments/coronation_var_frontiers.py`, a narrow offline
diagnostic for the single-variable route idea.

- Uses `tools/cf_adapter.py` over `cfg/full_ast.json`.
- Recursively collects writes and reads for one target variable.
- Finds nearest owner-frontier candidates for writes by backward slicing over
  the CF adapter and checking which decision-surface successors can still reach
  the write before another write to the same variable intervenes.
- Prints first-layer dependency vars from both owner-frontier guards and later
  read conditions.
- Also prints one-level dependency summaries using the same logic for each
  dependency var discovered from the target-var frontiers/reads.

This is intentionally diagnostic only. It does not solve hubs, propagate value
domains, or attempt full route solving.

### Codebase Modularization — Ghost logic, CFG dump, icon embed

**`backend/timeline_ghost_logic.rpy`** (new, 589 lines): extracted ghost card runtime logic
from two files into one backend module.
- Ghost card image extraction (`_tl_branch_img`, `_tl_first_scene_img`, `_collect_branch_imgs`,
  `import ast as _tl_ast_mod`) moved from `timeline_init.rpy` (`init -2 python:`).
- If-node monkey-patch and clustering logic (`_tl_parse_regions`, `_tl_should_cluster`,
  `_tl_build_ghost_payload`, `_tl_collect_if_run`, `_tl_partition_if_run`,
  `_tl_emit_ghost_cluster`, `_tl_on_if_execute`, `_tl_if_execute_patched`, et al.)
  moved from `ui/tl_ghost_cards.rpy` (`init python:`).
- `ui/tl_ghost_cards.rpy` now contains only screen definitions (140 lines).
- `timeline_init.rpy`: 1194 → 874 lines.

**`backend/timeline_ast_dump.rpy`** (new): `_tl_cfg_dump_ast` (live AST → JSON exporter
for `gen_cfg.py`) extracted from `timeline_init.rpy` into its own backend file.

**Icon embed** (`backend/timeline_assets.rpy`): replaced `images/lock.png` +
`matrixcolor InvertMatrix()` (broken on Ren'Py 7.4) with pre-whitened 64×64 PNG bytes
embedded as base64 constants `_TL_LOCK_B64` / `_TL_UNLOCK_B64`, decoded at init time
via `_tl_im_Data` into `_tl_lock_displayable` / `_tl_unlock_displayable`. Removes
dependency on `images/` folder entirely.

### Codebase Modularization — Split 1: `backend/timeline_assets.rpy`

Extracted all asset/thumbnail helpers from `timeline_init.rpy` and `timeline_screen.rpy`
into a new `backend/tl_assets.rpy` module (`init -2 python:`).

Moved functions: `_tl_capture_thumbnail`, `_tl_normalize_img_name`, `_tl_scene_stmt_img_name`,
`_tl_stmt_ast_key`, `_tl_live_scene_entry_img_name`, `_tl_img_name_is_movie`,
`_tl_asset_thumb_cache_key`, `_tl_asset_thumb_display_id`, `_tl_asset_thumb_display_cache_key`,
`_tl_is_supported_thumb_file`, `_tl_resolve_asset_file`, `_tl_render_asset_thumb_bytes`,
`_tl_get_asset_thumb_bytes`, `_tl_resolve_live_menu_img_name`, `_tl_thumb_displayable`,
`_tl_node_thumb`, `_tl_img_thumb_displayable`.

Moved constants/caches: `TL_ASSET_THUMB_CACHE_MAX`, `TL_ASSET_THUMB_CACHE_VERSION`,
`TL_LOG_ASSET_THUMB_HITS`, `_tl_asset_thumb_displayable_cache`, `_tl_asset_thumb_file_cache`,
`_tl_im_Data`, `_tl_text_types`.

`timeline_init.rpy`: 1585 → 1194 lines. `timeline_screen.rpy`: 1449 → 1321 lines.
All 250 unit tests pass after the move.

### Causal Slice — Layers 2–5 + 7: backward walk, hub enumerator, Z3 model, Z3 optimize, verifier

Full implementation of the counterfactual hint system in `tools/causal_slice.py`.

**Layer 2 — `build_causal_slice`**: backward walk from a ghost card condition If-node to collect all write sites for relevant variables. Two-phase approach: forward BFS pre-computes guard frozensets per write node (with intersection at merge points), backward BFS attaches pre-computed guards. Supports `if`, `menu`, and `screen_jump` guard kinds. Guard-var expansion auto-adds transitively referenced variables to the DAG.

**Layer 3 — `enumerate_hub_paths`**: forward BFS through a cycle SCC (hub), forking at If/Menu branches, counting back-edge traversals as rounds, collecting exit paths (nodes outside the hub SCC). Parameterized by `max_rounds`.

**Layer 4 — `build_z3_model`**: builds Z3 formulas from a causal slice DAG. Int vars use ITE chains in program order; string vars use EUF `DeclareSort` + `Distinct`; choice vars (`z3.Int`) are created per menu/screen_jump guard source with bounds `[0, N)`. Augmented assigns resolve RHS against the current formula for that var.

**Layer 5 — `find_minimal_solutions`**: given formulas and choice vars from Layer 4, finds all minimum-cost choice assignments satisfying a condition string. Cost is Hamming distance from `player_history` (only menus the player actually reached). Uses `z3.Optimize` to find min cost, then enumerates all solutions at that cost via blocking clauses.

**Layer 7 — `verify`** (`tools/causal_verify.py`): live gameplay simulator. Walks CF graph from `start_label` using `graph.successors`, maintaining `live_vars`. Executes Python writes, evaluates If conditions against live vars, follows Menu/screen_jump arms via `solution` (fallback: `player_history`). Hubs run via `_run_hub` up to `max_rounds` back-edge traversals; force-exit picks the exit node reachable toward `target_nid`. Returns `bool` from evaluating `condition_str` against live vars at `target_nid`.

- 79 tests pass across Layers 2–5 + 7

### Ghost Card — Jump-exit clustering + taken-index + image fixes

**Jump-exit clustering heuristic**

Sequential `if` nodes whose every branch ends with `Jump` or `Return` are now clustered together even when their conditions use different variables (and therefore fail the DNF disjointness check). Once any branch fires and jumps, subsequent sibling `if`s in that run are unreachable — making them structurally exclusive.

- `_tl_collect_if_run` annotates each payload with `all_branches_exit` (bool) using the existing `_tl_branch_exits_before_next` helper.
- `_tl_partition_if_run` widens its cluster condition: `_tl_should_cluster(...) or _jump_cluster`, where `_jump_cluster` is True when both the current group and the incoming payload are all-branches-exit.

**taken_index first-wins fix**

`_tl_emit_ghost_cluster` was overwriting `taken_index` for every payload that had one, so in a multi-payload cluster the last payload's taken branch "won." For jump-exit clusters this is wrong — the second if-node was never reached at runtime, but its condition can still evaluate True against live store state at collection time. Fixed to take the first non-None `taken_index` and ignore subsequent ones.

**Cluster separator — left border removed**

The 3 px left border on cluster-start cards is removed. The accent-colored gap fill between same-cluster cards (and transparent gap between clusters) already communicates grouping clearly without the extra border.

**Ghost card branch image — movie fallback**

When the differentiating branch image resolves to a movie-backed displayable, the image selection now falls back to the previous non-movie image in the branch sequence. If the entire branch sequence is movies, `context_img` is used. Previously, movie-backed images rendered as blank (0×0) since Movie displayables only produce frames when actively playing.

### Codebase Modularization — Partial (Splits 2, 3, 4)

Three new files extracted from the monolithic `timeline_init.rpy` / `timeline_hooks.rpy` / `timeline_screen.rpy` trio, per the plan in `docs/Codebase Modularization Review.md`.

- `timeline_causal.rpy` (~439 lines) — causal hint backend: `_tl_load_causal_graph`, state snapshot, `_tl_causal_hint`, and related helpers moved out of `timeline_init.rpy`.
- `timeline_var_delta.rpy` (~332 lines) — var-delta formatting and reachable map: `_tl_build_reachable_map` and the full delta/prettify cluster moved out of `timeline_init.rpy`. Uses `init -1 python:` so the reachable map is defined before `timeline_hooks.rpy` captures it as a default arg.
- `ui/tl_ghost_cards.rpy` (~594 lines) — ghost card subsystem consolidated into one file: helpers from `timeline_init.rpy`, emission logic from `timeline_hooks.rpy`, and the `tl_ghost_rows` screen from `timeline_screen.rpy`.

Splits 1 (assets), 5 (screen/cards), and 6 (tests) remain to be done.

### Ghost Card Fixes

**Bug fixes**

- `_tl_record_after` parameter order: `chosen_label` was positionally swapped with `chosen_index` after a signature change, causing a `str < int` crash in the record pipeline test and in real choice recording.
- `_tl_runtime_choice_returns` now falls back to `node.get("_choice_returns")` so test-injected nodes (and any node without a live runtime cache entry) resolve correctly instead of returning `None`.
- `_tl_make_seen_fn` narrator-line skip: the inner walk was short-circuiting on nameless `Say` nodes (narrator lines) instead of continuing to the first named-character say. All branches whose first dialogue is narrator text were returning `("never",)`.
- `_tl_build_ghost_payload` now calls `_tl_make_seen_fn` instead of `_tl_make_scene_seen_fn`. The scene-only variant missed branches that start with a plain say, jump, or call — those branches were locked incorrectly.

**UI fixes**

- Divider width between timeline rows and ghost rows corrected to `cols * card_w + (cols - 1) * spacing` (was one `spacing` too wide).
- Visual type indicators replaced: arrow `→` and dot `●` removed from the bottom bar. Type-2 (seen, not this play) now gets a lighter semi-transparent overlay on the thumbnail. Type-3 (never seen) keeps the dark overlay and lock icon. Type-1 (taken this play) shows no overlay.
- Cluster separator overflow fixed: the standalone 4 px separator frame (which added layout width per cluster boundary) is replaced by a 3 px left border rendered inside the first card of each cluster. Zero layout-width impact; row width is always `cols * card_w + (cols - 1) * spacing`.
- Cluster gap fill: inter-card gaps within a cluster are filled with a faint accent-colored `frame`. Inter-cluster gaps use a transparent `frame`. (`null` does not participate in layout when nested inside `if`/`for` inside an `hbox` in RenPy screen language.)

### Traversal Strategy v2 — Control-flow adapter + formula BFS

Clean-room redesign of the formula solver traversal layer, replacing the
`_build_graph` / `_process_node` / `exec_hub` interleaving in
`tools/formula_solver.py` with a strict two-layer architecture. Described in
`docs/FORMULA_SOLVER_DESIGN.md` § "Traversal Strategy v2".

#### Layer 1 — `RenpyFlowGraph` (`tools/cf_adapter.py`) — **Complete**

Thin control-flow adapter built once from the JSON AST dump. No Z3 dependency.

- Node identity: primary `tuple(stmt["name"])` = `(filename, serial, line)`;
  fallback `(filename, line)`; last resort sequential counter. No node is
  silently dropped.
- Single DFS pass emits all typed successor edges: `sequential`, `if_arm`,
  `if_fallthrough`, `menu_arm`, `jump`, `call`, `return`, `screen_jump`.
- `Call` / `Return` wiring: pass 2 BFS from each callee entry (excluding call
  edges) wires every reachable `Return` nid back to the post-Call nid.
- Back-edge detection via DFS grey/black colouring. Back-edge targets become
  `cycle_headers`.
- Tarjan's SCC (iterative) computes `hub_scc[hub_nid]` — the full set of nids
  in the SCC rooted at each cycle header, used during hub arm walks to
  distinguish hub-internal inter-labels from true exits.
- Public API: `successors(nid)`, `predecessors(nid)`, `label_entry[label]`,
  `is_back_edge(src, dst)`, `cycle_headers`, `hub_scc[hub_nid]`.

**Tests** (`tests/test_cf_adapter.py`): 55 tests, all passing. Covers 11
fixtures: straight-line, `If` with/without else, `Menu`, empty arm block,
`Jump` cross-label, string `next` boundary, `Call`/`Return`, simple cycle,
multi-label cycle, `UserStatement` hub (screen_jumps → arm labels both looping
back).

#### Layer 2 — DAG formula BFS (`tools/formula_bfs.py`) — **In progress**

`build_formulas(ast, start, stop=None)` — BFS over the non-back-edge DAG.
Returns `(formulas, choice_vars, str_registries)`.

Design rules implemented:
- `PathState = (formulas_snapshot, predicate, return_cont)` — no global call
  stack; `return_cont` travels with each path state independently.
- Firing condition: `required == deposited` where `required` is the set of
  non-back-edge predecessor nids. Nodes are enqueued only once all required
  deposits have arrived (checked inside `deposit()`).
- `Python` writes: parses `code` field via `ast.parse`; handles `=` and `op=`
  augmented assignment; evaluates RHS as Z3 expression against current
  `formulas` namespace via `eval()`.
- `If`: takes pre-branch snap, evaluates each arm condition via `eval_z3_bool`,
  deposits `(snap, AND(pred, arm_pred), return_cont)` to arm entry nids. Empty
  arm deposits directly to post-If nid. No-else arm emits
  `NOT(OR(all arm_preds))` fallthrough deposit.
- `Menu`: introduces `z3.Int` choice var bounded `[0, N)`, registered in
  `choice_vars[nid]`. Deposits `(snap, pred AND c==i, return_cont)` per item.
  Empty item arm deposits to post-Menu nid via raw `stmt["next"]` field.
- `Jump`: deposits to successor nid; silently skips cycle headers (hub
  boundary — Layer 3).
- `Call`: deposits `(formulas, pred, post_call_nid)` to callee entry; `return_cont`
  set to `tuple(stmt["next"])`.
- `Return`: deposits to `return_cont` from incoming path state; top-level return
  is terminal.
- `UserStatement`: deposits to each `screen_jump` target; skips cycle headers.
- String literals in assignments: interned into an uninterpreted Z3 sort per
  variable (`DeclareSort`, `Const`, `Distinct` assertions). Registered in
  `str_registries[sort_name]`.
- Join merge: ITE chain built from all arriving path states. Vars missing from
  some paths use the pre-branch snap value as fallback; vars not in the snap
  either are simply absent from those paths (user guarantee: uninitialized vars
  never appear in conditions).

Known bugs at pause — DAG tests not yet all passing:
- `_ite_merge` `all_same` check crashes on non-Z3 Python values (e.g. plain
  `int` from `eval()`); Z3 `simplify` requires a Z3 expression.
- `TestSeqWrites` / `TestCallReturn`: formula grounds correctly but `int_val()`
  fails — likely `eval()` returning a plain Python int rather than `z3.IntVal`.
- `TestStringMenu`: two string constants not detected as distinct — `Distinct`
  assertion not propagating correctly through `str_registries` across two
  separate `_intern_string` calls in the same `build_formulas` invocation.

`exec_hub` is a stub (`raise NotImplementedError`) — Layer 3 not started.

**Tests** (`tests/test_formula_bfs.py`): 49 tests written. DAG group (13
classes, ~33 tests) failing due to above bugs. `exec_hub` unit group (4
classes, ~16 tests) failing with `NotImplementedError`.

Additional test fixtures added beyond the design doc's table: `Menu-If` (If
nested inside Menu arm), `If-Menu` (Menu nested inside If arm),
`TestFixpointHubWrite` (pre-formula var written in one fixpoint-hub arm).

#### Layer 3 — Hub execution (`tools/formula_bfs.py :: exec_hub`) — **Not started**

`exec_hub(hub_nid, graph, formulas, choice_vars, solver, str_registries)`
returns `(exit_deposits, hub_choice_vars)`. Design is complete in
`docs/FORMULA_SOLVER_DESIGN.md` § "Layer 3 — Hub execution" including:

- Var classification per write site (hub-local concrete vs. pre-formula).
- Iterative round loop with round-indexed choice vars `c_{hub_nid}_r{round}`.
- `hub_arm_walk` with SCC-aware LOOP sentinel.
- Three termination criteria: fixpoint, concrete exit condition, formula-var
  exit condition (Z3 query).
- Fold-back ITE chain for hub-local vars.
- Three hub archetypes: Counter (dedicated exit arm), Conditional
  (If guard each round, concrete or formula-var), Fixpoint (no exit arm,
  terminates when `hub_concrete` unchanged).

**Tests** (`tests/test_formula_bfs.py` exec_hub group + `tests/test_formula_integration.py`):
tests written for all three archetypes plus integration end-to-end fixtures;
all failing with `NotImplementedError`.

---

### Timeline Save Safety — Transient Runtime Caches

- moved the live causal / AST / menu lookup caches off store state and onto
  transient runtime cache storage on `renpy.game.script`
- stopped keeping flowchart cache data, background thread handles, and captured
  `namemap` references in saveable store globals
- stopped recording `_state_snapshot` on new history nodes
- load validation now strips old transient `_state_snapshot` and
  `_choice_returns` payloads from `_tl_history` entries so older saves recover
  into plain-data history nodes instead of retaining live runtime objects

### Timeline Dot Logic — Live Option-Block Peek Fallback

- tightened non-structural timeline option dots in `timeline_init.rpy`
- `_tl_option_has_new_scene(...)` now inspects the live Ren'Py `Menu` AST block
  for the option's first meaningful seen target before falling back to
  `_tl_option_seen(...)`
- this keeps the old chosen / seen fallback semantics intact when no live peek
  target can be derived, but stops treating every never-chosen option as new by
  default
- implementation stays runtime-native: no extra timeline node metadata was
  added, and caption-only menu rows are skipped while mapping option indices to
  live menu blocks
- corrected non-structural past-card aggregation so `_tl_node_has_new_scene(...)`
  now aggregates per-option peek results instead of the older local
  `_tl_node_has_new(...)` check

### Hint Engine — Segment-Chain State Reduction (2026-04-25)

- diagnosed that `solve_segment_chain` was burning ~6,500 states per terminal
  segment by running an unconstrained transport pass to find write frontiers
  that were not forward-reachable from the current node — the pass exhausted
  the full structural-reachable subgraph before returning empty
- root cause: `remaining_writes` filtered only by `consumed_writes`, not by
  forward-reachability from the current node; writes on already-taken branches
  stayed in the set and drove a useless transport pass each terminal segment
- fix: in both `discover_state_graph` and `explore_lineage`, compute
  `_fwd_remaining = remaining_writes & future_tracked_write_sets.get(node_id)`
  and use it as the gate and argument to `frontier_hits_for_state`; if no
  remaining writes are forward-reachable, skip the transport pass entirely
- added fast-path in both terminal blocks: if env has exact values for all
  tracked vars, evaluate target directly without launching `_run_solve_pass`
- result for `perk == "strength" and rosa_sex == 1`: 13,287 → 108 states,
  same 1 path; terminal segment states 6,589 → 0
- added targeted debug prints (to stderr) in `discover_state_graph` to expose
  remaining vs forward-reachable write counts and transport states per node
- known open issue: `_choose_root_label` may pick a label on a side branch
  (e.g. `siscon`) when a write to a tracked var appears there earlier than on
  the main path from `start_label`; this was masked before by the broad
  transport pass accidentally covering the correct path

### Hint Engine Prototype

- added `tools/hint_engine.py` as a separate solve-first prototype, intentionally
  independent from `tools/causal_analysis.py`
- the prototype:
  - walks `full_ast.json` symbolically from a start label
  - supports an optional stop label for chapter-bounded solves
  - tracks abstract state on condition-relevant vars
  - collects raw unlock paths for one target condition
  - groups raw paths by shared branch skeleton for compact hint output
- added `tests/test_hint_engine.py` as a direct-run synthetic test file covering:
  - grouping of equivalent menu alternatives
  - numeric split behavior on a threshold condition
  - preservation of guarded branch steps on the way to a downstream condition
- replaced the old nesting-only guard-chain index with a structural guard index
  on the compressed graph:
  - a guard must dominate the target from the solve root
  - the target must be reachable from its satisfying branch
  - the target must not be reachable from that entry's non-satisfying
    continuation
- fixed tracked-var state snapshots so exact multi-value states remain hashable
  inside grouped solver provenance
- condition propagation now collapses unrelated non-target `if` branches when
  they converge to the same target-relevant successor state, reducing solve
  blowup from irrelevant guard checks in late intro targets
- choice propagation now includes future reachable tracked-write signatures in
  its grouping key, so options that only differ by irrelevant routing can
  collapse without losing delayed tracked-write distinctions
- compressed-graph label compilation and solve-scope discovery now honor
  implicit label-end fallthrough, fixing nested branch writes that previously
  became false dead ends
- write frontiers are now modeled as frontier families:
  - one real decision surface
  - the write outcomes under that surface
  - prerequisite control context when an outer gate must hold before the
    frontier exists
- segment chaining now advances per lineage instead of one global wave, so
  early and late write families are no longer mixed into the same segment step
- segment chaining now filters boundary transitions by future satisfiability of
  the post-write state, so direct satisfying paths are not forced through later
  write families
- compressed graph now skips caption-only menu rows with `block == null`, so
  menu prompt text no longer renders as fake selectable options
- `segment-chain` no longer emits solve-to-target grouped paths from
  intermediate lineage states; this removes the old hybrid behavior, though the
  current terminal emission is still over-collapsed and not final
- `segment-chain` now keeps viable frontier exits that bypass the current
  family's writes, so direct-write options and delayed-write options can both
  survive from the same decision surface instead of truncating the later
  lineage
- `segment-chain` now filters frontier hits down to the earliest non-label
  frontier layer per lineage segment, so later frontiers no longer compete with
  the current segment's frontier and fallback label frontiers do not duplicate
  decision-surface work
- `segment-chain` now builds a discovered segment-state graph and computes
  backward viability on that graph, replacing the earlier repeated
  solve-to-target viability probes from intermediate frontier states
- `segment-chain` now caches terminal suffix solves by terminal control/state
  and prunes final grouped outputs by subset subsumption, which removes the
  extra narrower terminal path variant in cases like the local `intro13:811`
  slice

### Timeline Hub Cards

- added `docs/TIMELINE_HUB_CARDS.md` with a concrete hub-UX proposal focused on
  grouped old cards and a widened modal payload
- documented the bounded grouped-card body:
  - one row per chosen option
  - collapse long/cyclical hub runs with an ellipsis row
- documented the minimal modal direction:
  - keep one modal shell
  - widen `_tl_modal_node` from raw node to a payload object that can represent
    either a normal node or a grouped hub run

### Timeline Dot Mode Flag

- added `TL_USE_STRUCTURAL_SCENE_DOTS` in `timeline_init.rpy`
- default runtime dot behavior now uses the older local seen-based logic:
  - option dots come from `not _tl_option_seen(...)`
  - past-card dots come from `_tl_node_has_new(...)`
- structural scene-reach dots remain available behind the flag for later
  verification work

### Timeline Screen Profiling

- added a disabled-by-default `TL_PROFILE_TIMELINE` flag for coarse timeline
  screen profiling in `debug.txt`
- timeline profiling now aggregates:
  - full timeline screen pass duration
  - playthrough new-path summary time
  - `_tl_items` list construction time
  - scene-dot helper time for node and option checks
  - asset-thumb displayable preparation time
- profiling uses aggregate counters instead of per-call spam so live runs can
  show where open-time is going without changing screen behavior
- live profiling showed the structural scene-dot path dominated timeline-open
  cost, so normal runtime should keep profiling off and local dot mode on

### Timeline Option Identity Tightening

- replay and post-menu recording now prefer valid-option indices instead of
  visible label text when resolving the chosen branch
- duplicate visible labels in one menu no longer collapse choice-return
  population or replay selection onto the first matching text entry
- added standalone `tests/timeline_hooks_latest.py` and
  `tests/test_runtime_option_identity.py` for direct-run verification of the
  hook-layer option-identity logic
- added focused `debug.txt` logs for live verification:
  - menu entry now logs node / `ast_key` / derived site / option count /
    runtime current-node type
  - mismatch-only log now reports when stored `ast_key` and derived
    menu-site identity differ on a live menu node
  - mismatch-only log now also reports when `_tl_record_before(...)` is running
    on a runtime `current` node whose AST type is not actually `Menu`
  - choice recording now logs chosen index and whether index or label fallback
    was used
  - shadow-path consumption now logs whether the match used `menu_site_key` or
    `_location`

### Timeline Asset Thumb Optimization

- added transient displayable caching for asset-backed timeline thumbnails so
  repeated screen renders reuse final displayables, not just cached thumb bytes
- added transient resolved-file caching for `img_name` asset resolution
- moved noisy `asset thumb hit` logging behind `TL_LOG_ASSET_THUMB_HITS`

### Timeline Menu Identity Tightening

Added the first backward-compatible menu-identity tightening layer for the
runtime base:

- new history nodes now carry `menu_site_key`, a best-effort stable menu-site
  identity derived from the real menu AST site when possible

Later cleanup removed stored `menu_site_key` from history nodes after live
verification showed `_tl_record_before(...)` was already recording the real
menu `ast_key` on the tested paths. The runtime now derives menu-site identity
from `ast_key` first and falls back to `_location` only for legacy nodes.

This is intentionally a narrow first step. It does not yet change checkpoint
hashing, replay loading, or save-slot naming.

To support layer-by-layer verification, the menu-identity / shadow-path tests
now also live in a standalone `tests/test_runtime_identity.py` file that depends
only on `tests/timeline_init_latest.py`, so this base layer can be tested
without the broader tooling imports.

### Timeline Presentation Ideas

- added `docs/TIMELINE_PRESENTATION_IDEAS.md` to capture future UI direction for
  a clue-first, mystery-preserving hunt layer over timeline cards
- documented cards-as-primary, journal-as-secondary, and
  graph-as-advanced/optional positioning

### Timeline Thumbnail Safety

Timeline card rendering now avoids direct `img_name` fallback for dynamic image
definitions. When static asset-thumb generation misses, the screen only falls
back to raw `img_name` rendering for plain file-backed assets. Dynamic images
such as `ConditionSwitch` / composite-style definitions now stay on the
existing thumbnail/plain-background path instead of being rendered directly
inside the timeline screen.

The same thumbnail-safety path exposed a separate Ren'Py store-shadowing bug:
runtime walkers in `timeline_init.rpy` were using bare `id(...)`, which breaks
on games that define a store variable named `id`. Those walkers now use a
builtin-safe object-id helper instead.

That thumbnail-safety change also needed a follow-up screen guard: when a
dynamic `img_name` is suppressed and no screenshot thumb exists, the card now
checks for an actual thumbnail displayable before trying to `add` it.

### Timeline Dot Reachability

Added a temporary offline reroute probe to test the runtime model against a
real saved history before touching UI/runtime code:

- `tools/gen_cfg.py`
  - `build_graph_structural(..., include_show=True)` can now preserve `Show`
    statements as `scene` nodes tagged with `origin="show"`
- `tools/causal_analysis.py`
  - added menu extraction and stale-history matching against current AST menus
  - added an offline reroute probe that:
    - consumes as much stored choice history as the current CFG can support
    - falls back to the last useful matched choice when full replay drifts
    - reports which next options still reach a future `Show` node
- `tests/test_unit.py`
  - added regression coverage for show-node inclusion and the reroute probe on
    a synthetic AST

Real sample result with `tmp_history.json`:

- `125/138` history entries match current menus
- full ordered replay no longer lands on a live frontier, so the probe uses a
  backtracked matched-choice anchor
- from that anchor, two next options still lead to future `Show` targets in
  `recure_eva2`

Updated the timeline-dot design doc to state the runtime model more explicitly:

- dots are now described as rerouting/replanning from the player's current run
  state, not as literal preservation of one offline causal chain
- offline causal analysis remains the candidate generator
- runtime is the truth layer for whether unseen territory is still reachable
  from here

This clarifies the intended split between:

- offline candidate discovery
- runtime reroute validation
  for unseen-scene guidance

### Causal Analysis

Restored the causal-analysis text-report path after lineful `reach_guards`
support broke legacy intro-report rendering:

- `tools/causal_analysis.py`
  - text rendering now accepts both `(label, opt_idx)` and
    `(label, line, opt_idx)` guard tuples
  - readable reports collapse exact guard identities back to the legacy display
    shape and dedupe repeated guards deterministically
- `tests/test_unit.py`
  - added regression coverage for legacy reach-guard formatting and text rendering

This isolates the remaining intro causal-report drift to the deeper transitive
propagation layer instead of the text/reporting path.

Added the next offline verification base on top of the existing condition-side
causal logic:

- `tools/causal_analysis.py`
  - `_build_choice_condition_chain_objects(...)`
    - produces machine-readable causal chains that preserve `choice`, `assign`,
      and `condition` steps from the existing explanation logic
  - `_verify_choice_condition_chain(...)`
    - verifies one chain with both:
      - CFG witness search for structural order/reachability
      - abstract assignment replay for target-condition satisfiability
- `tests/test_unit.py`
  - added direct and transitive chain-object coverage
  - added verification coverage for both satisfiable and unsatisfiable chains

This layer is still offline and condition-targeted only. It does not yet bridge
scenes into causal verification.

Added a second verifier mode better aligned with replay semantics:

- `tools/causal_analysis.py`
  - `_verify_choice_condition_chain_bfs(...)`
    - runs BFS over CFG with abstract state on relevant vars only
    - treats chain choices and required guarded writes as obligations
    - refines feasibility at condition nodes instead of forcing every
      explanatory condition site to become a strict CFG waypoint
- `tests/test_unit.py`
  - added coverage showing BFS can pick a later preserving branch on the same
    relevant variable instead of failing on an arbitrary witness

Real intro-condition spot checks now show the intended behavior:

- `mage_perk -> intro_magic_trigger == 1` verifies under BFS replay
- the impossible `intelligence` chain that tries to use the mage-gated
  choice-init path still fails

Added a history-conditioned condition-reroute probe on top of the existing DAG
and CFG layers:

- `tools/causal_analysis.py`
  - added `render_history_condition_reroute_text(...)`
  - it matches stale menu history to current AST menus
  - derives relevant vars from the target condition's causal DAG ancestry
  - replays matched choice writes into a prefix abstract env
  - runs CFG BFS from the history anchor using only those relevant vars
- `tests/test_unit.py`
  - added a synthetic regression showing truthy-guard vars now participate in
    reroute pruning

Current intro-slice sample result:

- `cond:intro13:811:tavergirlmood > 0`
  - now yields a non-empty reroute set from the stored history
- `cond:intro10:313:intro_magic_trigger == 1`
  - still yields no surviving reroute from the same sample anchor

### Timeline Dot Reachability

Added a dedicated design doc for the planned timeline-dot redesign:

- `docs/TIMELINE_DOT_REACHABILITY.md`

The doc records the intended shift from local option-history dots to scene-reachability
dots, keeps `persistent._seen_ever` as the seen-content source of truth, and documents
the intended static-vs-runtime split:

- static structural scene reachability built from AST/CFG
- runtime player-specific dot derivation from unseen scene identities

It also captures the intended later refinement path using snapshots and causal analysis
for guarded and numeric consequences without overstating current runtime capabilities.

Started the first implementation layer for that redesign:

- added a structural scene-reach builder in `timeline_init.rpy`
- added a mirrored pure-Python implementation in `tests/timeline_init_latest.py`
- added unit coverage for direct scenes, jump/call reachability, later-menu propagation,
  common continuation after later menus, branch unions, and cycle safety

This layer does not change timeline UI yet. It only establishes the structural
reachability helper and its tests.

Added the second implementation layer:

- new runtime dot helpers in `timeline_init.rpy`
  - `_tl_option_has_new_scene(node, option_index)`
  - `_tl_node_has_new_scene(node)`
- these helpers read structural scene reachability and `persistent._seen_ever`
- when no scene-reach data exists yet, they fall back to the current local dot logic
- chosen options are not skipped in the new scene-based helper model

This layer still does not change timeline UI yet. It only adds the new runtime
helper API and pure unit coverage for unseen-scene hits, all-seen clears, chosen
option behavior, and fallback semantics.

Added the third implementation layer:

- runtime population of the structural scene-reach cache in `timeline_hooks.rpy`
- JSON cache file support for that map, parallel to the existing reachable-var cache
- a small in-engine sanity test in `timeline_tests.rpy` that verifies the runtime
  cache exists and has the expected dict/list shape

This layer still does not change timeline UI yet. It only wires the structural
scene-reach data into runtime so the new scene-based dot helpers can be exercised
before any screen call-site swap.

Adjusted that structural scene-reach backend after live verification exposed hub /
re-entry recursion in Imperial Chronicles:

- replaced the recursive statement/label walker with an iterative queue-based traversal
- the scene-reach builder now treats jumps, calls, `if` branches, later menus, and
  common continuation as queue work instead of recursive descent
- this keeps the layer-2 helper API unchanged while making the backend safer for
  hub-style menu loops seen during CFG work

Completed the next layer by wiring timeline UI dot call sites to the new scene-based
helpers:

- `timeline_screen.rpy` now uses `_tl_node_has_new_scene(...)` for card-level dots and
  history counts
- current-card and modal option rows now use `_tl_option_has_new_scene(...)` for dot
  visibility
- replay-aid and chosen-arrow precedence were left unchanged; only dot semantics changed

Tightened scene-dot helper semantics after first live verification:

- scene-reach identities loaded from JSON cache are now normalized back into hashable
  tuple-like keys before comparison against `persistent._seen_ever`
- old local `_tl_option_seen()` fallback was removed from the scene-dot path; when no
  structural scene-reach data exists for an option, it now shows no scene dot instead of
  reverting to the pre-feature semantics

Corrected the underlying identity model for the scene-dot cache:

- the structural scene-reach cache now stores scene AST ids `(filename, linenumber)`
  instead of translated seen identities
- a separate runtime map resolves `scene_ast_id -> seen_identity`
- only that final seen identity is compared against `persistent._seen_ever`
- the scene-reach cache JSON format was updated accordingly and old cache files now
  rebuild automatically

Added a repo/process guardrail after repeated scene-dot identity failures:

- prefer working with Ren'Py-native semantics, identities, and persistence first
- avoid introducing a parallel identity/seen-state layer unless Ren'Py-native state is
  proven insufficient and the replacement boundary is explicitly documented

Refined the timeline-dot design doc after live verification showed that broad structural
scene reach was the wrong foundation:

- the doc now states explicitly that dots are only for options relevant to unlocking
  scenes never seen in any playthrough
- it defines guarded conditions and branch points as the meaningful unlock hotspots
- it positions a compressed verification graph as the foundation beneath runtime dot
  logic, with causal analysis proposing candidates and verification proving that at
  least one valid path exists to the later guarded scene/chunk

Started the verification-foundation pass for that model:

- added offline CFG-backed verification helpers in `tools/causal_analysis.py`
- the new helpers can:
  - build a compact verification graph from CFG structure
  - map current causal `choice` / `condition` ids onto CFG nodes
  - derive ordered verification series from `reach_guards`
  - find one witness CFG path consistent with that causal series
- added unit coverage for alias resolution, series construction, witness success
  with unrelated intermediate choices, and witness failure when order is impossible

This pass is offline-only. Runtime timeline dots still do not consume the
verification layer yet.

Extended that verification foundation with scene-hotspot extraction:

- added `_build_scene_hotspot_map(...)` in `tools/causal_analysis.py`
- scene hotspots are defined as the nearest reverse CFG frontier of controlling
  nodes for each scene
- hotspots now support both:
  - condition nodes for guarded scene entry
  - choice nodes for directly option-gated scenes without an intervening condition
- if multiple hotspots sit on the same nearest frontier, all are retained

Added unit coverage for:

- nearest-condition hotspot extraction
- multiple same-frontier hotspots for one scene
- direct-choice hotspot fallback
- nearest-choice preference without conditions
- condition-frontier precedence over farther choices

Added the next combination layer on top of the verification foundation:

- added `_verified_relevant_choices_for_scene(...)` in `tools/causal_analysis.py`
- this helper combines:
  - target scene
  - controlling hotspot(s)
  - causal candidate choices from those hotspots
  - witness-path verification
- output is a verified set of relevant causal choice ids for one scene

Added unit coverage for:

- condition-gated scene -> verified relevant choice
- directly option-gated scene -> verified relevant choice
- filtering out causal candidates that have no structural witness path to the scene

Refined hotspot output after running the current verification foundation on
`cfg/full_ast.json`:

- unmapped raw CFG condition hotspots are now omitted from `scene -> hotspot`
  results
- this removes hotspot noise that cannot participate in the causal candidate step
  anyway
- verified choice output for sampled full-game scenes stays the same while the
  hotspot set becomes cleaner

Refined hotspot extraction again after validating a real merge-back spine case in
`after_party`:

- switched hotspot detection from plain nearest reverse frontier to controlling
  hotspot detection on the reduced verification graph
- conditions/choices now need to dominate the target scene before they can be
  assigned as hotspots
- this fixes the concrete false positive where `tavern_fuck_v == 1` incorrectly
  appeared as a hotspot for `after_party8`; it now remains correctly attached to
  the guarded `after_party3` branch only

Refined hotspot extraction further to respect cross-label jump boundaries:

- hotspot extraction is now label-local for scene ownership
- reverse traversal stops at cross-label jump edges instead of pulling in distant
  dominators from earlier labels
- on full-game verification this removes the broad cross-label `ballday5_d`
  condition hotspot from `after_party8`
- current real-data result:
  - `after_party3` keeps hotspot `cond:after_party:937:tavern_fuck_v == 1`
  - `after_party8` now has no local hotspot

Added local forward propagation of verified relevance within a label chunk:

- added `_propagate_verified_choices_within_labels(...)` in `tools/causal_analysis.py`
- propagation uses:
  - same-label, non-jump edges only
  - intersection across incoming paths at merges
- this keeps local consequences alive after a hotspot while preserving the stricter
  control/jump-boundary ownership rules

Verified on real `after_party` scenes:

- `after_party3` keeps its guarded-condition relevance
- `after_party8` stays empty after the merge
- `after_party9` and `after_party12` correctly retain the local `Drink the white blood`
  choice relevance

Added causal reach-guard lifting on top of the verified scene-choice layer:

- added `_lift_choice_ids_via_reach_guards(...)`
- added `_verified_relevant_choices_for_scene_with_reach_guards(...)`
- verified scene-local choices can now be expanded transitively through causal
  `reach_guards`

Added unit coverage for:

- transitive prerequisite lifting
- ambiguous reach-guard matches
- scene-level lifting of already verified local choices
- the final per-scene offline relevance view built by
  `_build_scene_choice_relevance_map(...)`, including:
  - direct verified choices
  - label-local propagated choices
  - lifted prerequisite choices
  - the final combined choice set per scene
- hotspot-local necessity checking of verified scene choices via
  `_necessary_relevant_choices_for_scene(...)`
  - necessary choices now survive only when no alternative verified choice in
    the same hotspot context can still witness the scene without them
- propagated exact causal `choice:` ids through reach guards:
  - reach-guard collection now preserves exact menu site identity
  - choice nodes now carry `reach_guard_choice_ids` alongside legacy
    compatibility `reach_guards`
- added `_candidate_causal_series_for_scene(...)`:
  - returns hotspot-anchored candidate verification series in existing causal-id
    form
  - this is intended as the verification-layer input object for later full-chain
    checking
- deepened transitive scene candidate series by reusing causal-analysis condition
  explanation structure:
  - `_build_choice_condition_serieses(...)` now emits causal-id serieses for
    transitive condition links
  - `_candidate_causal_series_for_scene(...)` now uses those deeper serieses for
    condition hotspots instead of only one-hop guard prefixes
- propagated choice-side option guards into the causal graph:
  - choice nodes now carry `option_cond_ids` in the existing causal `cond:` id
    format
  - `_build_causal_verification_series(...)` now inserts those condition steps
    before the guarded choice when present
- added `_candidate_causal_series_for_hotspot(...)` as the causal-analysis-side
  bridge:
  - hotspot is now treated as the local anchor only
  - candidate chains come from existing causal-analysis logic and are then
    wrapped by scene-level helpers for verification
- added first-class choice-side chain emission in causal analysis:
  - `_build_choice_guard_serieses(...)` now explains how guarded choices become
    available from upstream option conditions
  - `_build_choice_condition_serieses(...)` now reuses that choice-side base
    instead of starting from a bare choice id

### Documentation / Session Workflow

Added a lightweight session operating system for future AI chats and project memory:

- new `AGENTS.md` for repo-local guardrails
- new `SESSION_GUIDE.md` as the short session entrypoint
- new `docs/CODE_FLOW.md` as the cross-subsystem map

The intent is to make new sessions read less, explain changes before coding, and leave behind consistent subsystem docs instead of only chat-local context.

Also added a dedicated thumbnail/storage note to `docs/CODE_FLOW.md` so screenshot capture, persistent cache ownership, compatibility limits, and storage bounds are documented in one place instead of only being implied by scattered README bullets and old changelog entries.

### Timeline Thumbnails

Timeline thumbnails are now on an asset-first path.

Runtime menu capture now resolves the current live gameplay image and writes that `img_name`
into the persistent menu-scene map, which is now authoritative for menus the player has
actually reached. The AST walk remains as a backfill path only and was tightened to track
`Scene` and `Show` updates plus explicit `Jump` traversal instead of broad label-order carry.

Screenshot capture was kept, but demoted to explicit fallback status when both runtime
asset resolution and the persistent menu-scene map miss.

Asset-backed thumbnails now also have their own persistent static-thumb cache keyed by
`img_name`. The timeline screen first tries to use those generated thumb bytes and only
falls back to live asset rendering if a static asset thumb is not cached yet. This keeps
`img_name` as the source-of-truth mapping while making repeated timeline opens cheaper.

The asset-thumb generator now uses the underlying file-backed image path for ordinary
registered image assets instead of trying to serialize Ren'Py render objects. This avoids
renderer-specific texture/surface differences across Ren'Py 7 and 8. Runtime logging for
`TL asset thumb generated` and `TL asset thumb hit` was used to verify cache population
during rollout. The final runtime keeps the persistent asset-thumb cache, without the
temporary card-level diagnostic logging or the reverted in-memory displayable cache layer.

Temporary thumbnail-debug logging used during the asset-port investigation has also been
removed from the runtime and screen layers. The cache/display path remains in place; only
the ad hoc `TL menu ctx` and `TL thumb source` tracing was dropped.

### Ghost Cards

Ghost cards are ephemeral timeline cards that appear below the last timeline row whenever
the game evaluates a player-relevant `if` condition between menu choices. They show every
branch of that statement — not just the one taken — so the player can see what paths exist
and whether they have seen each branch before.

**Sibling-run synthesis**
Ghost cards are now synthesized from the full sequential sibling `if` run starting at the
first executed `If` node. The hook walks that AST run, partitions it into mutually
exclusive groups, emits one ghost cluster per group immediately, and records later
sibling `(filename, linenumber)` keys in `_tl_skip_ghost_ifs` so runtime does not append
duplicates when those sibling `if`s execute later.

**Current layout and indicators**
Ghost rows render below the main timeline with a thicker divider above them and a thicker
cluster separator pipe between independent groups. A taken branch shows `→` only.
Untaken branches are checked against scene-based persistent seen state: if the branch's
first scene has never been seen in any playthrough, the row shows `●` and the thumbnail
gets a dark lock overlay with a white lock icon. If the branch has been seen before, it
shows no arrow, no dot, and no lock overlay.

**Live branch image extraction (`_tl_first_scene_img`)**
At `if`-node execution time, walks each branch's AST block to find the first `Show` or
`Scene` statement. Validates the image name against `renpy.display.image.images` before
returning it. Returns `None` if no valid image is found in the branch.

**Mutual exclusivity clustering (`_tl_parse_regions`, `_tl_should_cluster`)**
Condition strings are parsed to DNF (disjunctive normal form) regions using Python's
`ast.parse`. Each region is a `{var: frozenset(values)}` dict representing one disjunct.
Two sibling payloads are shown as one cluster when all parsed regions that overlap on a
variable are disjoint. Clustering now runs over the collected sibling run instead of only
between the previously appended ghost and the current `if`.

**Shared scene-based seen helper**
Ghost cards no longer use `seen_label` for branch seen state. Ghost branches and the
flowchart now share the same helper: find the first scene in the branch, resolve the
first translated say-name reachable from that scene, then check that identity against
`persistent._seen_ever`.

**DNF-based gate replaces `affecting_vars` heuristic**
Previously, a ghost node was created only if `_tl_extract_vars_from_conditions` returned
a non-empty set. This silently dropped valid conditions like `perk == "intelligence"` in
some cases. The gate now uses the DNF parser: a ghost node is created only if at least
one non-`True` condition parses to a valid DNF region. System and built-in `if` nodes
(which use attribute lookups, function calls, or non-equality operators) return `None`
from the parser and are correctly filtered.

**Runtime `If.execute` filter**
The `renpy.ast.If.execute` monkey patch now tracks only real game scripts under `game/`
and ignores the mod's own `timeline_*.rpy` files. This prevents branch logging and ghost
logic from firing on Ren'Py common/framework `if` nodes or recursively on the mod's own
runtime code.

### Offline CFG and Causal Analysis (`tools/`)

A full offline analysis pipeline for building chapter control-flow graphs and explaining
why conditions are true or false in terms of upstream menu choices.

**`tools/gen_cfg.py`** — CFG builder. Reads a full AST JSON (generated via RenPy's AST
export) and emits a Graphviz DOT file and a meta JSON. Passes applied in order:
1. Structural AST walk (`build_graph_structural`) — stable production mode
2. `normalize_if_ladders` — groups sequential same-variable if branches into one node
3. `compress_scene_chains` — collapses scene→scene chains, keeps nodes adjacent to choices
4. `filter_junction_scenes` — removes pure flow-through scene nodes (skipped with `TL_NO_FILTER=1`)
5. Prune pass (`prune_impossible_edges`) — removes provably unreachable edges via abstract
   state execution (only with `TL_PRUNE_IMPOSSIBLE=1`, slower)

Controlled via env vars: `TL_LABEL` (required, start label), `TL_STOP` (stop label),
`TL_TRAVERSAL=structural` (stable production mode), `TL_GROUP_IFS=1` (normalize ladders),
`TL_PRUNE_IMPOSSIBLE=1`, `TL_NO_FILTER=1`.

**`tools/causal_analysis.py`** — Offline causal analysis layer. Builds a dependency graph
over four entity types: choices, assignments, variables, and conditions. Graph links:
choice→assignment, assignment→variable, variable→condition, condition→guarded assignment.
Computes reach guards: earlier choices that must already have happened before a candidate
choice is even reachable. Handles numeric variables via finite fixed-point abstract
interpretation (extracts threshold representatives, tracks abstract values, applies
`set`/`+=`/`-=` transfers until stable). Emits:
- Causal graph JSON (`cfg/intro_causal_graph.json`)
- Per-condition text report (`cfg/intro_causal_graph.txt`)
- Grouped-by-condition-string report (`cfg/intro_causal_graph_grouped.txt`)

The entry points in `gen_cfg.py` are thin wrappers that call into this module.

**Runtime hint path now reads the dependency graph directly**
Runtime hints no longer read the old `write_map`/`cond_map` cache shape. The online hint
path loads `causal_graph.json`, matches condition nodes directly, and returns paired diff
records shaped for replay aid and ghost cards:

```python
{
    "kind": "direct" | "path",
    "menu_ast_key": ...,
    "original_idx": ...,
    "required_idx": ...,
}
```

`direct` means a choice at that menu directly contributes to satisfying the target
condition. `path` means the choice is a prerequisite split/reach-guard diff needed to
enter the path where a direct satisfier exists.

Current limits: not yet a true minimal-diff solver from concrete save history; numeric
reasoning is abstract rather than fully path-sensitive; path diffs are still prerequisite
surfacing, not a full replay-aid divergence plan.

**`tools/build_vis.py`** — Visualization builder. Reads meta JSON from `gen_cfg.py`,
emits a DOT file, a `plain` geometry file (used by the flowchart screen for node positions
and edge polylines), and a PNG preview. Node sizes match the RenPy UI footprint
(`fixedsize=true`) so Graphviz layout reflects actual on-screen geometry.

Never overwrite base `cfg/*.plain` or `cfg/*.dot` files — always write to a new output path.

**`tools/build_presentation.py`** — Presentation-layer transform applied after CFG
construction. Implements round-lane layout for repeatable hub menus and local loop events,
ensuring hub nodes don't collapse into the main flow lane.

**`tools/parse_svg.py`** — Parses Graphviz SVG output to extract node/edge geometry.
Used by the `build_vis.py` pipeline.

**`cfg/`** — Generated artifacts (not overwritten in place):
- `full_ast.json` — full RenPy AST export
- DOT files, `plain` geometry files, PNG previews
- `intro_causal_graph.json` — causal graph for the intro chapter slice

**`timeline_flowchart.rpy`** — In-game flowchart screen. Reads `cfg/*.plain` geometry
files and renders the chapter CFG as an interactive map. Condition lock/unlock state now
uses the same shared scene-based seen helper as ghost cards.

**`images/`** — `lock.png` lock icon for ghost card overlays.

### Imperial Chronicles chapter map
- Arc 3 (`new_aud`) added between Arc 2 and Arc 4 in `game-chapters/imperial-chronicles.json`.

---

## `0428fef` · 2026-04-07 · Fix: correct Chapter 1 Finale label in imperial-chronicles.json

The Chapter 1 Finale end label was set to the wrong label name. Corrected to `ending_CH1`.

---

## `b79d0aa` · 2026-04-07 · Optimize: use chapter-end saves as jump checkpoints

`_tl_find_nearest_save` previously only scanned `_ch_NNNN_*` checkpoint files.
Chapter-end saves (`_ch_chap_*`) are now also considered when jumping to a node. If a
chapter-end save's `after_index` is closer to the target than the nearest checkpoint, it
is used instead, reducing skip-replay distance.

Candidates are pre-validated at the call site in `_tl_begin_jump` using
`_tl_chapter_markers` (which already stores `after_index` for each chapter) and an
existence check, then passed into `_tl_find_nearest_save` for the unified best-index
comparison.

---

## `39fc5a8` · 2026-04-06 · Fix: chapter-end save written at label, not first subsequent interact

The deferred `_tl_pending_chap_end_save` mechanism wrote the save at the start of the
next RenPy interaction. When no dialogue follows a chapter end label (e.g. Arc 8 goes
straight to a menu), the save captured state at that menu — loading it overshot by 1+
menus instead of landing at the chapter end.

Label callbacks fire between interactions so `renpy.save()` is safe to call directly in
`_tl_chapter_label_cb`. Also added an existence check: same slot = same playthrough path
already saved cleanly, so skip the write. This eliminates the 50+ redundant saves seen
in `debug.txt` when the chapter end label was re-entered during replay skip.

---

## `20b9de9` · 2026-04-04 · Docs: update dev notes for hashed chapter-end save slots

---

## `fdbe162` · 2026-04-04 · Tests: chapter-end slot name hashed form

`_tl_chap_end_slot_name` now accepts `(label, context, after_index)` and returns the
hashed slot name. Four new unit tests: same context → same slot, different context →
different slot, label preserved, prefix format. In-game test updated. 109 unit tests pass.

---

## `4432072` · 2026-04-04 · Fix: chapter-end saves scoped per playthrough via context hash

`_ch_chap_{label}` was a global slot — all playthroughs wrote to the same file. A forked
save reaching the same chapter end would overwrite it, causing the chapter divider in the
original save to load the fork's state.

Slot is now `_ch_chap_{label}_{hash}` where `hash = MD5[:6]` of
`_tl_context[:after_index]`, matching the checkpoint save scheme. Same choices → same
hash (correct dedup); different choices → different hashes (no collision). Old saves fall
through to the rollback-jump fallback unchanged.

---

## `396a3f5` · 2026-04-03 · CI: update actions/checkout to v6.0.2 (Node 24)

v4.2.2 runs on Node 20 which is deprecated on GitHub Actions runners (forced to Node 24
from June 2026, removed September 2026).

---

## `ef100d6` · 2026-04-03 · Tests: shadow path consumption, divergence, and forking

Unit tests (`tests/test_unit.py` + `tests/timeline_init_latest.py`):
- `_tl_build_shadow_path` (8 tests): nodes after target included, target excluded, None
  location/chosen_index skipped, empty tail, target not found, order preserved.
- `_tl_shadow_match` (6 tests): first match wins, no match returns None, zero
  `chosen_index` is valid, duplicate location.
- `_tl_consume_shadow_path` (10 tests): no match, first/middle/last entry consumed,
  tail preserved, same choice yields no `diverge_ci`, different choice yields `orig_ci`.

In-game tests (`timeline_tests.rpy`): `shadow_path_defaults`, `shadow_path_set_on_jump`,
`shadow_path_empty_tail`, `shadow_path_consume_and_diverge`,
`shadow_path_same_choice_no_diverge`, `validate_shadow_path_corruption`.

Notification messages changed from Unicode symbols to plain ASCII (rendering issues in
RenPy's notification overlay).

---

## `8812989` · 2026-04-03 · Add replay aid / save forking with divergence markers

**Shadow path:** after jumping back, the mod builds a list of original-path choices
(location + `chosen_index`) for all menus after the jump target. Stored as a save
variable so it persists across loads and carries over in duplicated/forked saves.

**Jump flow:** shadow path staged in `persistent._tl_pending_shadow_path` before
checkpoint load (store vars would be overwritten), then transferred into
`store._tl_shadow_path` by `_tl_on_load`.

**Consumption:** each time the player makes a choice at a matching location,
`_tl_consume_shadow_path` consumes entries up to and including that match. When the
player chose differently from the original, `_shadow_orig_chosen` is stamped on the node
so the divergence marker survives after the entry is consumed.

**Display:**
- Current choice card: muted `→` on the option originally chosen on the shadow path.
- Past cards: `⎇` in footer when the card's chosen option differs from the original.
- All Options modal: muted `→` on the originally chosen option for past diverged nodes
  (`_shadow_orig_chosen`) and the current unresolved node (live shadow path scan).
- Jump target node itself gets `_shadow_orig_chosen` from `persistent._tl_replay_path`.

**Chapter end marker fix:** removed the `if persistent._tl_replaying: return` guard from
`_tl_chapter_label_cb`. The existing `(after_index, chapter_name)` dedup check prevents
double-recording; this fixes markers disappearing after a jump whose checkpoint predates
the chapter end.

---

## `f36fc28` · 2026-04-02 · Guard callbacks and toggle against pre-game-start access

Store defaults are applied only when a new game starts or a save is loaded, not during
the main menu. Any callback or keybind firing before game start would crash with
`AttributeError` on `store._tl_*` attributes.

- `_tl_toggle`: return early if store not initialized; keybind is a no-op at main menu.
- `_tl_interact_callback`: single `hasattr` guard at top.
- `_tl_record_before`: same guard; silently ignores menus that appear before game start.

---

## `186759d` · 2026-04-01 · Tests: sync mirror + chosen-skip coverage for `_tl_node_has_new`

`timeline_init_latest.py`: updated `_tl_node_has_new` to skip `chosen_index`, matching
the fix applied to the real implementation. `test_unit.py`: 9 new cases covering chosen
option excluded from dot check, unchosen unseen options trigger dot, no `chosen_index`
checks all options.

---

## `20610cb` · 2026-04-01 · Fix dot logic: stale `cr.chosen` after save/load, chosen option excluded

- `_tl_option_seen` now checks `persistent._chosen` directly using `node["_location"]` +
  option label as the primary lookup. `ChoiceReturn` objects serialized with saves carry a
  stale snapshot of `_chosen` that diverges after any save/load cycle, causing dots to
  persist on fully-explored cards.
- `_tl_node_has_new` skips the chosen option when checking for unseen paths. The chosen
  option is always explored by definition; card and modal dot logic are now consistent.

---

## `641f7f6` · 2026-04-01 · Fix replay dot recording, RenPy 7.4 thumbnail crash, `min()` shadowing

- Replay now calls `value()` instead of `value.value` so `ChoiceReturn.__call__` records
  the explored option to `persistent._chosen`; dots clear correctly after jump + replay.
- `_tl_capture_thumbnail` returns `None` immediately on RenPy < 7.5 (no
  `screenshot_to_bytes`); removes the broken fallback that produced black images on 7.4.x.
- `_tl_thumb_displayable` detects WEBP/JPEG/PNG from magic bytes so `im.Data` decodes
  correctly across RenPy versions.
- `min()`/`max()` in screen python blocks replaced with `if/else` (avoids conflict with
  games that define a Character named `min`).
- Removed "New" / "All seen" labels from past card footer (dot alone signals unexplored
  paths; header already shows the count).
- IC: Arc 13 end label (`ending013`) added.

---

## `b6934de` · 2026-03-12 · Fix: chapter-end save skipped during skip mode

`_tl_interact_callback` had a blanket `if config.skipping: return` that prevented
`_tl_pending_chap_end_save` from ever firing during fast-forward. The save was deferred
to the next non-skip interaction — potentially deep into the next chapter — causing
chapter-end jumps to land at the first menu of the following chapter.

Fix: only the checkpoint save (`_tl_pending_save_index`) is guarded by the skip check;
chapter-end saves now always fire.

---

## `37d8fa8` · 2026-03-12 · Fix save bloat (complete) + skip mode guards

The previous `thumb_bytes` fix only cleared it in the "first time" branch. On any
subsequent playthrough (cache already populated), every node landed in the
`elif cached_thumb` branch and got `thumb_bytes` set — same bloat as before. Fix: never
set `thumb_bytes` from cache onto the node; `_tl_node_thumb()` resolves it at display
time. `thumb_bytes` is kept on the node only as a fallback when the cache write fails or
`ast_key` is unavailable.

Skip mode guards: screenshot capture and all `renpy.save()` calls skipped when
`config.skipping` is set. Pending save indices are left intact so the save fires at the
first non-skip interaction.

---

## `9aeb624` · 2026-03-12 · Release workflow: fixed tags, versioned zip filenames

- Tag is now fixed (`stable` / `stable-{game}`) — one permanent release per target,
  replaced in place on each run instead of accumulating versioned tags.
- `version` input controls only the zip filename (`chronology-mod-v1.2.zip`).
- Zip filename includes game suffix when applicable.

---

## `2657193` · 2026-03-12 · Fix save file bloat: clear `thumb_bytes` after caching

`thumb_bytes` (~50 KB PNG) was kept on every `_tl_history` node permanently, causing
checkpoint saves to grow by ~1 MB per 10 choices. Fix: clear `node["thumb_bytes"] = None`
after successful write to `persistent._tl_thumb_cache`. Added `_tl_node_thumb(node)`
helper that falls back to the persistent cache when `thumb_bytes` is `None`; used in
`tl_card`, `tl_modal`, and debug panel. Backwards compatible with old saves.

---

## `345432d` · 2026-03-08 · Chapter end compatibility fix, pycache cleanup

Guard `config.label_callbacks` with `hasattr` — silently disables chapter end indicators
on RenPy < 7.6/8.1 instead of crashing.

---

## `0edca70` · 2026-03-07 · Replace root `chapters.json` with `game-chapters/` directory

`game-chapters/sample.json` is the default for base releases.
`game-chapters/imperial-chronicles.json` is selected by the release workflow for IC builds.
Release workflow updated: picks `game-chapters/${GAME:-sample}.json`, fails clearly if
the named file does not exist.

---

## `da48762` · 2026-03-07 · `chapters.json` sample template, `_`-prefix skip

`_tl_load_chapters` now skips keys starting with `_` (used for comments/metadata).
`chapters.json` ships as a sample file with `_comment` and `_sample_chapter` entries.

---

## `fa312c3` · 2026-03-07 · v1.1: Chapter end indicators, save/load path, redundancy fixes

**Chapter end dividers:** reads `chapters.json` mapping chapter names to end labels;
dividers appear between cards at the correct position; clicking loads the chapter-end save
or falls back to jump + rollback for first-time sessions. `_tl_chapter_markers` records
`{chapter_name, end_label, after_index}` when a chapter end label is reached.
`_tl_begin_label_jump` handles both paths.

**Chapter-end checkpoint saves:** written at the first interaction after the chapter end
label fires. Slot name `_ch_chap_{label}`.

**Quality fixes:** thumbnail cache write wrapped in `try/except`; `im.Data` replaced with
`renpy.display.im.Data` alias (deprecation warning); dead code removed (`_tl_mod_abs`
## Unreleased

### Hint engine design

- Added [docs/HINT_ENGINE_DESIGN.md](/Users/divyjain/Development/renpy-timeline-mod/renpy-chronology-mod/docs/HINT_ENGINE_DESIGN.md) as the reference for the intended hint-engine architecture.
- Documented the required layer order explicitly:
  compressed graph, target-stop condition solves, target-driven abstraction,
  solve-time path collapse, guard-frontier reuse, then scene-local locks.
- Documented that solve-time BFS must stop at the target condition and that
  grouped-path collapse is part of propagation, not a post-processing step.

### Hint engine prototype

- Layer 1 is now implemented in `tools/hint_engine.py`:
  explicit compressed graph plus one target-stop condition solve.
- Layer 2 is now implemented:
  target-local numeric representatives plus exact handling for equality-sensitive
  vars.
- Added backward numeric demand computation on the compressed graph. This is
  currently exposed for debugging and tests, but not yet applied as a general
  forward-prune rule because raw node-entry pruning was unsound.
- Layer 3 is now implemented in the narrow solver sense:
  grouped provenance is propagated during the solve, and equivalent choice
  outcomes collapse before enqueue when they hit the same successor state.
- Added backward structural target reachability as the first live enqueue prune.
- Backward numeric demand now prunes only at stabilized branch outcomes:
  a choice option or true condition branch is advanced through its local
  deterministic successor chain first, then demand is checked on the resulting
  successor state.
- Target-local numeric representatives now keep one value on each side of
  strict compare boundaries, so `-1` and `0` no longer collapse together for
  targets where later writes can separate them.
- Added a conservative tail short-circuit for the hint-engine solver:
  when no future tracked-var write is reachable and the tracked env is exact,
  the solver resolves target truth immediately instead of traversing the suffix.
- Fixed the hint-engine “future tracked write” frontier to use forward
  reachability to later tracked writes, instead of a backward-from-write set
  that overkept nodes alive.
- Added lineage-aware cycle pruning to the hint-engine solver: a branch is
  dropped when it revisits the same abstract solver state already present in its
  own ancestry, which stops loop-heavy perk-selection paths from unrolling.
- Fixed exact-value normalization in the hint-engine solver so nested singleton
  wrappers are flattened before refinement. This restores satisfiable exact
  targets such as `perk == "strength" and rosa_sex == 1` that were previously
  failing due to corrupted env values.
- Added tracked-var state snapshots to hint-engine path output so each rendered
  branch alternative can show the post-branch state that leads toward the
  target.
- On the real `intro13:811 tavergirlmood > 0` target, this drops explored states
  from `8,266` to `40`, which confirms that dead structural branches were the
  dominant remaining waste.
- Added guard/root narrowing in `tools/hint_engine.py` so condition solves start
  from the nearest enclosing guard or first relevant write instead of the whole
  chapter by default.
- Added `UserStatement(screen_jumps)` traversal to the prototype so the IC perk
  screen behaves like a choice surface during solves.
- Fixed a branch-frame bug where advancing inside `menu`/`if` blocks dropped the
  embedded block and truncated multi-statement branches after the first
  statement.
- Fixed `Jump` handling in the prototype so jumped-to labels do not fall back
  into the caller when they exhaust.
- Tightened grouped-path rendering so alternatives only merge when their
  remaining suffix is identical, which avoids fake cartesian combinations in the
  printed unlock paths.
- The real `intro13:811 tavergirlmood > 0` prototype solve now drops from the old
  50k-state cap path walk to:
  - 15,768 states after the compressed-graph refactor
  - 8,634 states after target-local numeric representatives
  - 8,266 states after solve-time grouped propagation
  - 40 states after structural target-reachability pruning
- Added direct-run regression coverage in `tests/test_hint_engine.py` for:
  multi-statement menu branches, conservative grouped-path rendering, stop-label
  scoping, screen-jump traversal, root/guard reporting, target-stop behavior,
  local prior-guard selection, equality-safe numeric canonicalization, and
  backward demand for equality-style numeric targets.

duplicate, unused `_tl_renpy_major/minor`, stale `_tl_ast_progress` reset).

**Tests:** 25 new Python unit tests (72 total): chapter dedup, marker existence, timeline
rollback, chapter-end slot naming. 4 new RenPy in-game test suites. CI now runs unit
tests before building the zip.

---

## `d3b080c` · 2026-03-04 · Tests, logging, and cosmetic refinements

---

## `17c39ff` · 2026-03-04 · Jump-back and revert via dense saves

Jump-back to any past choice using dense checkpoint saves (every choice for the first 5
nodes, every 10th after). Includes revert (cancel jump and return to original position).

---

## `62da5b2` · 2026-03-03 · Initial working commit

**Choice timeline.** A scrollable card list (opened with `T`, closed with `Esc` or `T`)
showing every menu decision in play order. Each past card has: a scene thumbnail (captured
at menu entry with `renpy.screenshot_to_bytes`, stored in a persistent cache of up to 500
entries); the chosen option text; a `●` dot in the footer when unexplored paths exist; an
All Options button that opens the modal. The current card shows the full option list with
seen indicators. Cards are `_tl_cols`-wide, scrollable horizontally.

**New content detection.** `_tl_build_ast_map` walks the full RenPy AST at game start on
a background thread and builds a `{(file, line): [descriptor, ...]}` map. Each descriptor
is a picklable tuple (`("say", name)`, `("label", target)`, or `("never",)`) produced by
`_tl_make_seen_fn`. At render time, `_tl_option_seen` evaluates descriptors against live
RenPy state (`persistent._seen_ever`, `renpy.seen_label`) to decide whether to show a dot.

**All Options modal.** Full-screen overlay with every option in the menu, the chosen
marker `→`, seen dots `●`, and jump actions (calls `_tl_begin_jump` → loads checkpoint →
auto-replays via skip mode to the target menu).

**Jump-back via checkpoint saves.** `_tl_save_slot(index, context)` produces
`_ch_NNNN_HHHHHH` slot names (deterministic from node index and context hash).
`_tl_should_save` writes dense saves for the first `TL_DENSE_SAVES` (5) nodes and every
`TL_SAVE_EVERY` (10) nodes after. `_tl_find_nearest_save` finds the highest valid
checkpoint ≤ the target index. A recovery slot (`_ch_recovery`) is written before each
jump so the player can cancel and return to their original position.

**Menu hook.** `renpy.exports.menu` and `renpy.store.menu` are wrapped once at init
(idempotent guard). `_tl_record_before` fires before each menu (builds node dict with
thumbnail and AST key). `_tl_record_after` fires after choice (records `chosen_index`,
extends `_tl_context`, queues deferred save). `_tl_interact_callback` is registered in
`config.interact_callbacks` and fires the deferred checkpoint save.

**Persistent thumbnail cache.** `persistent._tl_thumb_cache` maps `ast_key` →
compressed image bytes (WEBP/JPEG/PNG). `_tl_node_thumb(node)` resolves at display time,
falling back to `persistent._tl_thumb_cache` when `thumb_bytes` is `None` on the node.
Magic-byte detection in `_tl_thumb_displayable` ensures correct `im.Data` decode across
RenPy versions.

**Save compatibility.** History is validated and malformed entries dropped on each load
(`_tl_validate_on_load`). Mod installed mid-playthrough: recording starts from install
point. Mod removed from save: RenPy ignores unknown `_tl_*` keys.

**Hint engine frontier inspection.** Removed the old `segmented-debug`
traversal scaffold from `tools/hint_engine.py`. The first segment-solving layer
is now frontier inspection only: relevant writes, their assigned decision
surface frontiers, and grouped write families per frontier. This keeps base
solver behavior unchanged while making frontier behavior explicit and testable.

**Hint engine first segment pass.** Added `solve_first_write_segment(...)` and
CLI strategy `segment-first`. This is the first real segmented traversal layer:
it runs from the solve root to the first reachable write-family frontier, then
stops at the writes in that family and reports post-write boundary hits. It is
kept separate from the base solver and is covered by tests that later menus are
not carried past the write boundary.

**Hint engine segment chaining.** Added `solve_segment_chain(...)` and CLI
strategy `segment-chain`. It chains segments by carrying `(next_node,
tracked_env, grouped_path_prefix)` forward from each boundary hit, uses a
transport pass with no provenance growth to the next reachable frontier family,
then solves frontier-to-write again. Chaining is now lineage-local rather than
one global segment wave. Tests now cover multi-segment accumulation and keeping
same-env / different-location continuations separate.

**Hint engine guard memoization.** `solve_condition_paths(...)` now memoizes
true-branch frontier states for structural guards, keyed by guard site and
tracked-var set. Repeated guarded target solves can reuse those frontiers
instead of replaying the guard condition solve from scratch.

**Hint engine branch ownership.** Compressed-graph nodes now preserve their
enclosing menu-option / condition-branch ownership chain. Write-frontier
calculation uses that ownership to stop at the outer gameplay decision surface
instead of a nested local branch node inside a chosen option body.

**Hint engine label fallthrough.** Compressed-graph label compilation now keeps
implicit fallthrough to the next in-scope label, and solve-scope discovery now
includes those fallthrough labels too. This fixes nested branches that ended in
a write with no explicit `jump`, such as the missing `intro9:171
elin_intro_mood -= 1` path under the named `intro9:145` menu.
