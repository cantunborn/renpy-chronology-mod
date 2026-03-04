# Chronology Mod

A non-intrusive choice history tracker for RenPy visual novels. Records every decision you make, shows what you've seen and what's still unexplored, and lets you jump back to any past choice.

## Installation

Drop the contents of this folder into your game's `game/` directory and launch the game.

No save file editing required. Works on existing saves — the mod starts recording from the point you install it.

---

## Features

### Choice Timeline
Every menu choice you make is recorded as a card in the timeline. Each card shows:
- A thumbnail of the scene where the choice appeared
- The option you picked
- Whether any options in that menu lead to content you haven't seen yet (dot indicator)

### New Content Indicators
The mod automatically detects which options lead to unseen content by walking the game's script at startup. A dot (●) marks any option — or any past card — that still has unexplored paths.

The header shows a count of how many past choices have at least one new path available.

### All Options Modal
Click **All options** on any past card to see every choice that was available at that point:
- `→` marks the option you chose
- A dot marks options with unseen content

### Jump Back
In the modal, click any option to jump back to that point in the story and make a different choice. The mod saves a recovery point before jumping so you can return if needed.

Jumps use a save + skip approach: the mod loads the nearest checkpoint save and fast-forwards through dialogue to reach the target choice automatically.

### Thumbnail Cache
Scene screenshots are cached so the correct image appears on replay and across playthroughs. Up to 500 thumbnails are stored (~25 MB).

### Save Compatibility
- **Installing mid-playthrough:** the mod starts recording from that point. Earlier choices show no history, which is expected.
- **Removing the mod:** existing saves load normally. RenPy ignores the unused `_tl_*` variables.
- **Loading a corrupted save:** history is validated and any malformed entries are dropped silently.

---

## Controls

| Key | Action |
|-----|--------|
| **T** | Open / close timeline |
| **Esc** | Close timeline |

---

## RenPy Compatibility

Tested on **RenPy 7.5.3** and **RenPy 8.3.2**.

Compatibility holds across both versions for a few reasons:
- The mod hooks into `renpy.exports.menu` and `renpy.store.menu`, which have had a stable `(label, condition, value)` item tuple structure since RenPy 7.
- Save/load callbacks (`config.start_callbacks`, `config.after_load_callbacks`, `config.interact_callbacks`) are part of RenPy's public API and unchanged between major versions.
- The AST walker uses `type(node).__name__` string checks rather than importing RenPy AST classes directly, so it doesn't break if internal class paths change between 7 and 8.
- RenPy 8 is built on the same codebase as 7 with a Python 3 runtime; no API used here was removed in the transition.

---

<details>
<summary><strong>Developer notes — file reference</strong></summary>

### `timeline_init.rpy`
Core state and utilities. Runs at `init -2` (before hooks).

- Store variables: `_tl_history`, `_tl_context`, `_tl_branch_id`, `_tl_node_count`
- Persistent variables: `_tl_replaying`, `_tl_replay_target`, `_tl_replay_path`, `_tl_recovery_slot`, `_tl_thumb_cache`, `_tl_prev_thumb`
- Constants: `TL_SAVE_EVERY` (10), `TL_DENSE_SAVES` (5), `TL_THUMB_CACHE_MAX` (500)
- `_tl_save_slot(index, context)` — deterministic save slot name: `_ch_NNNN_HHHHHH`
- `_tl_should_save(idx)` — dense saves for first 5 nodes, sparse every 10 after
- `_tl_find_nearest_save(target, context, save_dir)` — finds highest valid checkpoint ≤ target
- `_tl_build_ast_map()` — walks RenPy AST to build `{(file, line): [descriptor, ...]}` map for seen detection; runs on a background thread
- `_tl_make_seen_fn(block)` — returns a picklable descriptor tuple: `("say", name)`, `("label", target)`, or `("never",)`
- `_tl_option_seen(node, i)` — resolves seen status via `get_chosen()` first, AST map as fallback
- `_tl_begin_jump(node_index, option_index)` — saves recovery, sets persistent replay state, loads nearest checkpoint
- `_tl_capture_thumbnail()` — screenshots current scene at `TL_THUMB_WIDTH × TL_THUMB_HEIGHT`
- `_tl_thumb_displayable(bytes, index)` — returns `im.Data` displayable from cached bytes

### `timeline_hooks.rpy`
Menu interception and save callbacks. Runs at `init -1`.

- Wraps `renpy.exports.menu` and `renpy.store.menu` once at init (idempotent guard)
- `_tl_record_before(items)` — fires before each menu: refreshes early save, creates node dict with thumbnail and AST key, handles replay reuse
- `_tl_record_after(node, chosen_label)` — fires after choice: updates `chosen_index`, extends `_tl_context`, queues deferred save
- `_tl_store_wrapper` — replay interception: at target node, auto-picks option and exits skip mode; at intermediate nodes, auto-picks from stored replay path
- `_tl_interact_callback` — deferred save trigger: fires after each interaction, writes checkpoint if `_tl_should_save(idx)`, also sets `_tl_early_save_idx` for the refresh pass
- `_tl_on_game_start` — writes `_ch_start` save at game start (ultimate fallback for jumping to node 0)
- `_tl_on_load` — resumes skip mode on load if mid-replay; writes `_ch_start` if missing

### `timeline_screen.rpy`
All UI. No game logic.

- `TL` dict — all colours, derived from `header_bg` and a computed accent colour
- `_tl_make_hover_gradient(color_hex, center_w, edge_w, base_hex)` — builds a `Frame`-wrapped 1px PNG gradient for button hover backgrounds; `base_hex` triggers Porter-Duff pre-blending so edges match the button's normal background exactly
- `screen timeline()` — root screen; blur layer + dark overlay + header + scrollable card list
- `screen tl_card(node, cw)` — dispatches to `tl_card_past` or `tl_card_current`
- `screen tl_card_past(node, chosen_label, has_new, cw)` — thumbnail + chosen option + footer (New dot, All options button)
- `screen tl_card_current(node, cw)` — thumbnail + full option list with seen indicators
- `screen tl_modal(node)` — full-screen modal with all options, chosen marker, seen dots, jump actions

### `timeline_save_hooks.rpy`
Save compatibility and validation.

- `_tl_validate_on_load()` — registered as `after_load_callback`; drops malformed nodes, re-indexes, resets transient UI state
- Documents the two compatibility cases: mod installed on old save (graceful empty state), mod removed from save with data (RenPy ignores unknown keys)

### `tests/timeline_init_latest.py`
Pure-Python mirror of the testable functions from `timeline_init.rpy`. Keep in sync manually when logic changes. No RenPy dependency — runs with Python 3.7+.

### `timeline_tests.rpy`
In-game test runner for RenPy-dependent behaviour that can't be tested outside the engine. Press **Shift+F9** during gameplay to run. Results are written to `debug.txt` and shown as an in-game notification.

Suites: hook wiring (single-wrap guard), persistent state init, store defaults, `_tl_save_slot` stability, thumbnail capture, thumbnail cache read/write/eviction, `_tl_record_before` → `_tl_record_after` pipeline, `_tl_node_has_new` via `get_chosen()`, `_tl_validate_on_load` history cleaning.

### `tests/test_unit.py`
47 unit tests covering `_tl_save_slot`, `_tl_find_nearest_save`, `_tl_validate_history`, `_tl_node_has_new`, `_tl_should_save`, context accumulation, two-phase save consistency, and dense/sparse save patterns.

Run with: `python3 tests/test_unit.py` or `pytest tests/test_unit.py -v`

### `debug.txt`
Runtime log written by `_tl_log()`. Appended to on each session. Contains errors, key state transitions (jump start/load, replay resume, AST map build), and save failures. Safe to delete.

</details>
