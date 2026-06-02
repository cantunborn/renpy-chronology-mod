# Jump — Choice Replay and Shadow Path

## What This Subsystem Is

The jump feature lets players click any past choice in the timeline (or modal) and replay from that point with a different option. The game rewinds to a save just before the target menu, auto-selects the new option, and continues forward — all without leaving the game to the main menu or using RenPy's built-in load dialog.

**Shadow path** is a companion mechanism: when a player jumps to menu N, the choices they had originally made at menus N+1, N+2, … are remembered as a "shadow." Each shadow entry is consumed silently as the player replays forward. When the player reaches a menu that was in the shadow and makes the same choice, it auto-selects. When they choose differently, the old choice is marked with a divergence indicator (↺) on that card. Shadow entries past the first divergence are discarded since the future is now unknown.

## Main Files

- `backend/tl_saveload.rpy` — `_tl_begin_jump`, `_tl_begin_label_jump`, `_tl_find_pre_save`, `_tl_find_nearest_save`, `_tl_cancel_replay`, `_tl_clear_replay_state`
- `backend/tl_shadow_path.rpy` — `_tl_stage_shadow_path`, `_tl_build_shadow_path`, `_tl_consume_shadow_path`, `_tl_shadow_match`, `_tl_shadow_match_mode`
- `timeline_hooks.rpy` — `_tl_store_wrapper` (replay interception + shadow consumption), `_tl_on_load` (shadow transfer from persistent)
- `timeline_screen.rpy` — `_tl_do_load` label (calls `renpy.load`), `_tl_do_chap_end_jump` label
- `ui/tl_cards.rpy`, `ui/tl_modal.rpy` — action that initiates the jump

## Jump Runtime Flow

```
Player clicks option button in card or modal
    -> action list fires:
        Function(_tl_begin_jump, node_index, option_index)
        Hide("tl_modal") / Hide("timeline")
        Jump("_tl_do_load")

_tl_begin_jump(node_index, option_index)
    -> _tl_save_no_screenshot("_ch_recovery")   — escape hatch saved first (no screenshot, no dir scan)
    -> persistent._tl_recovery_slot = "_ch_recovery"
    -> persistent._tl_replay_path = [current history choices snapshot]
    -> persistent._tl_replay_target = {node_index, option_index}
    -> persistent._tl_replaying = True
    -> _tl_stage_shadow_path(history, node_index)
        -> stored in persistent._tl_pending_shadow_path
    -> renpy.save_persistent()
    -> [Tier 1] _tl_find_pre_save(node_index, context, ast_key)
        -> if found: store._tl_load_slot = slot; return "load"    [EXACT PRE-SAVE]
    -> [Tier 2] _tl_find_nearest_pre_save(node_index - 1, context, history)
        -> if found: store._tl_load_slot = slot; return "load"    [NEAREST PRE-SAVE + SKIP]
    -> [Tier 3] _tl_find_nearest_save(node_index - 1, context, chap_candidates)
        -> if found: store._tl_load_slot = slot; return "load"    [CH_* CHECKPOINT + SKIP]
        -> if not found: clear replay state, notify user, return None

label _tl_do_load
    -> renpy.load(_tl_load_slot)
        -> game state overwrites store, but persistent survives
        -> config.after_load_callbacks fires: _tl_on_load()
            -> store._tl_shadow_path = persistent._tl_pending_shadow_path
            -> persistent._tl_pending_shadow_path = None

_tl_store_wrapper (intercepts renpy.store.menu / renpy.exports.menu)
    -> if persistent._tl_replaying:
        -> if current node == replay_target:
            -> [TARGET REACHED] auto-select target option, end replay
            -> config.skipping = None
            -> stamp node["_shadow_orig_chosen"] if option differs from original
        -> else:
            -> look up current node index in replay_path
            -> auto-select that index (skip node silently)
    -> if store._tl_shadow_path and not replaying:
        -> _tl_consume_shadow_path(shadow_path, node, chosen_index)
            -> if match: discard entries up to and including match
            -> if diverged: stamp node["_shadow_orig_chosen"] = original_ci
            -> update store._tl_shadow_path (None when exhausted)
```

## Pre-menu Save (Fast Path)

A **pre-menu save** (`_pre_{NNNN}_{h6}`) is written in `_tl_record_before` immediately before each menu fires — before the choice is recorded. Hash input is `context[:N]` (the path up to but not including menu N's choice), so the slot is path-specific but does not depend on what option is chosen at N.

When `_tl_begin_jump` finds a pre-save for the target node, it loads it directly. Since the save lands the player exactly at the menu, `_tl_store_wrapper` intercepts the very first `menu()` call, matches `persistent._tl_replay_target.node_index`, and auto-selects the new option. No skip phase runs.

Pre-saves are written via `_tl_save_no_screenshot`: no screenshot (1×1 black PNG on RenPy 7, `include_screenshot=False` on RenPy 8), `mutate_flag=False` (skips save-dir scan), and the rollback log is truncated to 1 entry for the duration of the save then restored. Typical size: 35–55 KB vs 150–400 KB for a full checkpoint save.

Pre-save slot format: `_pre_{NNNN}_{h6}` where `h6 = md5(repr((tuple(context[:N]), ast_key)))[:6]`. The `ast_key` disambiguates sandbox games where the same context prefix reaches multiple menus (e.g. PhotoHunt revisit loops).

## Nearest-save Fallback (Skip Path)

There are now two tiers of fallback before the old `_ch_*` checkpoint path:

**Tier 2 — nearest pre-save:** `_tl_find_nearest_pre_save(N-1, context, history)` scans all `_pre_*` files and returns the one with the highest index ≤ N-1 that matches the context prefix and recorded `ast_key`. This is better than a `_ch_*` checkpoint because pre-saves are written before every menu, so the skip phase is shorter (lands at a menu, not mid-dialogue).

**Tier 3 — nearest checkpoint:** When no earlier pre-save exists, `_tl_find_nearest_save(N-1, context)` scans the root savedir for `_ch_*` files, validates each against the current `context` (hash check), and returns the one with the highest index ≤ N-1. Chapter-end saves (`_ch_chap_*`) are also eligible as jump checkpoints and are passed in as pre-validated `chap_candidates`.

After loading the nearest save, `_tl_store_wrapper` is in replay mode. For each menu encountered before reaching node N, it looks up the node's index in `persistent._tl_replay_path` and auto-selects the recorded choice. RenPy's skip mode (`config.skipping`) is used to fast-forward dialogue between menus. When node N is finally reached, the target option is selected, replay ends, and skip is cleared.

## Shadow Path

Shadow path represents the player's **original future** — the choices they would have made had they not jumped. It allows the timeline to display a divergence marker (↺) on any post-jump card where the player chose differently, giving a visual record of how this playthrough diverged from the previous one.

**Staging (pre-load):** `_tl_stage_shadow_path(history, node_index)` collects every history node after `node_index` that has a `chosen_index`. Each entry records:
- `menu_site_key` — AST-stable `(filename, lineno)` identifier for the menu
- `location` — fallback `(filename, checksum, line)` used when site key is unavailable
- `chosen_index` — which option was originally taken

This list is stored in `persistent._tl_pending_shadow_path` **before** `renpy.load` is called, because `renpy.load` overwrites all store vars. Persistent vars survive the load.

**Transfer (post-load):** `_tl_on_load` (registered in `config.after_load_callbacks`) moves the list from `persistent._tl_pending_shadow_path` into `store._tl_shadow_path` and clears the persistent slot.

**Consumption:** After each normal (non-replay) menu choice, `_tl_store_wrapper` calls `_tl_consume_shadow_path`. It scans the shadow list for an entry matching the current node (site_key match preferred, location match as fallback). When found:
- All entries before the match are discarded (convergence path skipped)
- The matched entry is consumed
- If `chosen_index` in the entry differs from what the player just chose, `node["_shadow_orig_chosen"]` is stamped with the original index — this drives the ↺ divergence indicator in the card UI
- `store._tl_shadow_path` is set to the remaining entries (or `None` if exhausted)

Shadow path is also consumed silently during replay: `_tl_store_wrapper` calls `_tl_consume_shadow_path` as part of the target-menu handling so the stamp is applied at exactly the right node.

## Persistent State During a Jump

| Key | Set when | Cleared when |
|-----|----------|--------------|
| `persistent._tl_replaying` | `_tl_begin_jump` | Target menu reached |
| `persistent._tl_recovery_slot` | `_tl_begin_jump` | `_tl_clear_replay_state` |
| `persistent._tl_replay_path` | `_tl_begin_jump` | Target menu reached |
| `persistent._tl_replay_target` | `_tl_begin_jump` | Target menu reached |
| `persistent._tl_prev_thumb` | `_tl_begin_jump` | `_tl_clear_replay_state` |
| `persistent._tl_pending_shadow_path` | `_tl_begin_jump` | `_tl_on_load` (transferred to store) |

`store._tl_shadow_path` is set by `_tl_on_load` and consumed down to `None` as the player plays forward. Cancel restores from `_ch_recovery`, which overwrites store — `_tl_shadow_path` is restored to the value it had when the recovery save was written (i.e., before the jump).

## Cancel Replay

`_tl_cancel_replay()` (triggered by the cancel button in the timeline):
1. Snapshots all current node thumbnails into `renpy.game._tl_thumb_cache` (they would be lost when the recovery save is loaded, since `_tl_history` reverts)
2. Calls `_tl_clear_replay_state()` — zeroes all persistent replay keys
3. Sets `store._tl_load_slot = _ch_recovery` and triggers a load

After the recovery load, the game is back at the exact point where the player opened the timeline and clicked jump, with full history intact.

## Important Invariants

- Recovery save is always written **before** any other state is mutated in `_tl_begin_jump`. If anything fails after that point, cancel still works.
- `persistent._tl_pending_shadow_path` is used (not `store._tl_shadow_path`) because store vars are overwritten by `renpy.load`. The transfer happens in `_tl_on_load` before any game code runs.
- Pre-saves use `context[:N]` as hash input (not `context[:N+1]`). This makes the slot path-specific but option-agnostic — the same pre-save covers all possible choices at menu N.
- `config.skipping` is cleared unconditionally when the target menu is reached, even if the player had skip mode active before the jump.
- Shadow path entries are consumed by site_key if available; location is a fallback for menus where site_key could not be resolved at record time. Site_key is preferred because it is AST-stable across loads; location can shift if the file is edited.

## Known Limits

- If no pre-save and no checkpoint save exists for a node, the jump fails with a notify to the player. This can happen for very early menus if the player hasn't reached them since the mod was installed.
- Shadow path entries are not retroactively validated against the game AST. If a jump crosses a chapter boundary where options have changed, a shadow entry may not match any real menu site — it is silently skipped.
- Skip mode during replay fast-forwards all dialogue. If a game script has a blocking interaction (input, imagemap) between two menus that is not itself a menu, replay may stall.

## Where To Edit

| Task | File |
|------|------|
| Jump initiation, save lookup, cancel | `backend/tl_saveload.rpy` |
| Shadow path build, match, consume | `backend/tl_shadow_path.rpy` |
| Replay interception, shadow consumption at menus | `timeline_hooks.rpy` — `_tl_store_wrapper` |
| Shadow transfer after load | `timeline_hooks.rpy` — `_tl_on_load` |
| Jump label, load call | `timeline_screen.rpy` — `_tl_do_load` |
| Option button action (trigger) | `ui/tl_cards.rpy`, `ui/tl_modal.rpy` |