# Jump — Choice Replay and Shadow Path

## What This Subsystem Is

The jump feature lets players click any past choice in the timeline (or modal) and replay from that point with a different option. The game teleports to the exact game state captured just before the target menu, auto-selects the new option, and continues forward — all without leaving the game to the main menu or using RenPy's built-in load dialog.

**Shadow path** is a companion mechanism: when a player jumps to menu N, the choices they had originally made at menus N+1, N+2, … are remembered as a "shadow." Each shadow entry is consumed silently as the player plays forward. When the player reaches a menu that was in the shadow and makes the same choice, it auto-selects. When they choose differently, the old choice is marked with a divergence indicator (⎇) on that card. Shadow entries past the first divergence are discarded since the future is now unknown.

## Main Files

- `backend/tl_saveload.rpy` — `_tl_jump`, `_tl_cancel_jump`, `_find_slot`, `_tl_clear_replay_state`, slot-naming helpers
- `backend/tl_snapshot_cache.rpy` — `TLSnapshotCache`, `_tl_capture_snapshot`, `_tl_unfreeze_from_snapshot`, snapshot cache singleton on `renpy.game.log`
- `backend/tl_shadow_path.rpy` — `_tl_consume_shadow_path`, `_tl_shadow_match`
- `timeline_hooks.rpy` — `_tl_store_wrapper` (replay interception + shadow consumption), `_tl_on_load` (shadow reconstruction from persistent)
- `timeline_screen.rpy` — `_tl_do_load` label, `_tl_do_chap_end_jump` label
- `ui/tl_modal.rpy` — action that initiates a menu jump (`Function(_tl_jump, node_index, option_index)`)
- `timeline_screen.rpy` — `tl_chapter_divider` screen calls `Function(_tl_jump, chapter_label=end_label)`

## Jump Runtime Flow

```
Player clicks option button in card or modal
    -> action list fires:
        Function(_tl_jump, node_index, option_index)
        Hide("tl_modal") / Hide("timeline")
        Jump("_tl_do_load")

_tl_jump(node_index, option_index)
    -> _write_recovery()                      — escape hatch saved first
    -> _stage_menu_replay(hist, node_index, option_index)
        -> persistent._tl_replay_path   = [{"index", "chosen_index", "ast_key"}, ...]
        -> persistent._tl_replay_target = {node_index, option_index}
        -> persistent._tl_prev_thumb    = prev_node["thumb_bytes"]
        -> persistent._tl_replaying     = True
    -> renpy.save_persistent()
    -> _tl_get_menu_snapshot(node_index)      — look up in renpy.game.log._tl_snapshot_cache
        -> if valid: _dispatch_snap(snap)     [SNAPSHOT PATH — primary]
               persistent._tl_synthetic_jump = True
               renpy.game._tl_pending_snap = snap
               return
    -> _find_slot(node_index, hist, context)  [DISK FALLBACK — backward compat]
        -> Tier 1: exact pre-save at target index
        -> Tier 2: walk history downward — first hit (pre-save, _ch_* checkpoint,
                   chapter-end marker, or _ch_start) wins
        -> if found: store._tl_load_slot = slot; return
    -> if nothing found: _tl_clear_replay_state(); notify user

--- snapshot path ---
label _tl_do_load
    -> renpy.load(_tl_load_slot)  [but _tl_pending_snap is on renpy.game, survives load]
        -> config.after_load_callbacks fires: _tl_on_load()
            -> detects persistent._tl_synthetic_jump = True
            -> _tl_unfreeze_from_snapshot(renpy.game._tl_pending_snap)
                -> {"roots":..., "ctx":..., "rollback_limit":...} (current) -> deepcopy roots/ctx fresh (roots may share frozen references with other cached snapshots; the deepcopy on the way out means the live store never ends up aliased to cache-owned objects)
                -> {"roots":..., "context":...} (legacy pre-blob) -> _tl_unfreeze_legacy() -> deepcopy roots/ctx, rollback_limit falls back to config.hard_rollback_limit
                -> _tl_build_and_unfreeze(roots, ctx, ..., rollback_limit) builds synthetic RollbackLog
                -> copies snapshot cache to new_log before unfreeze
                -> calls unfreeze() — atomically teleports engine to capture point

--- disk fallback path ---
label _tl_do_load
    -> renpy.load(store._tl_load_slot)
        -> game state overwrites store, persistent survives
        -> config.after_load_callbacks: _tl_on_load()
            -> reconstructs store._tl_shadow_path from persistent._tl_replay_path

_tl_store_wrapper (intercepts renpy.store.menu / renpy.exports.menu)
    -> if persistent._tl_replaying:
        -> if current node == replay_target:
            -> [TARGET REACHED] auto-select target option, end replay
            -> config.skipping = None
        -> else:
            -> look up current node index in replay_path
            -> auto-select that index (skip node silently)
    -> if store._tl_shadow_path and not replaying:
        -> _tl_consume_shadow_path(shadow_path, node, chosen_index)
            -> returns (remaining_path, diverged_ci, match_mode)
            -> if diverged: stamp node["_shadow_orig_chosen"] = original_ci
            -> update store._tl_shadow_path (None when exhausted)
```

## Snapshot System (Primary Path)

A **snapshot** is captured in `_tl_record_before` immediately before each menu fires, via `TLSnapshotCache.capture()` (the free function `_tl_capture_snapshot()` is a thin wrapper delegating to the singleton instance at `renpy.game.log._tl_snapshot_cache`):

1. Calls `renpy.game.log.complete(False)` to flush any pending store deltas into the rollback log
2. Takes `context().rollback_copy()` to get the current execution context (this unconditionally forces `interacting = False`, matching what Ren'Py's own rollback copies always have)
3. Patches `ctx.current` to an enclosing label name when needed so `RollbackLog.rollback()` stops correctly at the synthetic entry in compiled `.rpyc` files
4. Records `renpy.game.log.get_roots()` — the full Python object graph needed for rollback
5. Reads `renpy.game.log.rollback_limit` — the live log's rollback allowance at this exact point in time, i.e. what a real save made right here would carry
6. Passes `get_roots()`'s result through `self._freeze_roots(live_roots)` and returns `{"roots": frozen_roots, "ctx": ctx, "rollback_limit": rollback_limit}`

**Reference-sharing freeze (current design):** `_freeze_roots` is the core of the cache. For every key in the live roots, it compares the live value against the value frozen at the *previous* capture using `_tl_values_equal(a, b)` — a single generic comparator used uniformly regardless of value type (`a is b` fast path, else `pickle.dumps(a) == pickle.dumps(b)`; deliberately not type-specialized, since the design must not assume anything about which game vars do or don't mutate). If equal, the frozen roots dict reuses the *previous* frozen reference for that key (not the live object); if changed or new, it gets a fresh `copy.deepcopy`. The result: every mutable value is deep-copied exactly once, ever, and every snapshot that captures it unchanged shares that same frozen object by reference. Because unchanged values across dozens of cached menus now point at the *same* Python object, Ren'Py's own single combined save pickle dedupes them for free via its normal memo table when the whole `renpy.game.log` (cache included) is serialized in one `pickle.dump()` call — no manual compression needed. `self._last_roots` tracks the most recently frozen roots dict so the next capture has something to diff against; it starts `None`, so the very first capture ever made has nothing to compare against and deep-copies everything.

Snapshots are stored on `TLSnapshotCache.menu` / `.chapter` (both plain `builtins.dict`, keyed by `node_index` for menus and `label_name` for chapters), an instance living at `renpy.game.log._tl_snapshot_cache`. Storing on `renpy.game.log` means:
- The cache is outside `store`, so it never appears in `get_roots()` — no recursive cycle
- Loading a save replaces `renpy.game.log`, so the cache comes back with it automatically
- `TLSnapshotCache.transfer_to(new_log)` (via `_tl_transfer_snapshot_cache`) copies the whole cache instance to the new log during `_tl_unfreeze_from_snapshot` before the unfreeze replaces the current log

**Restoration**: `_tl_unfreeze_from_snapshot` dispatches on snap shape:
- `{"roots": ..., "ctx": ..., "rollback_limit": ...}` (current live shape, written by every capture since the reference-sharing redesign): deep-copies `roots` and `ctx` fresh before use — necessary because `roots` may still be sharing frozen references with other entries still sitting in the cache; the live store must never end up aliased to a cache-owned object, or a later jump to a *different* cached node could observe mutations made by ordinary forward gameplay after this jump.
- `{"roots": ..., "context": ...}` (legacy pre-blob format — still present inside saves made before the reference-sharing redesign, until each cached node is naturally re-captured by being revisited): routed to `_tl_unfreeze_legacy()`, which `copy.deepcopy`s both `roots` and `context` before use, for the same live-aliasing reason as above. Legacy snaps never captured a historical `rollback_limit`, so this path falls back to `renpy.config.hard_rollback_limit`. (An intermediate pickled-blob format — `{"blob": bytes}`, compressed with a shared zlib dictionary in one iteration — existed briefly during development but was never committed/released, so no read-compat path exists for it.)

Both paths converge on the shared `_tl_build_and_unfreeze(roots, ctx, log_prefix, rollback_limit)`, which forces `ctx.interacting = False`, builds the synthetic single-entry `RollbackLog`, sets `new_log.rollback_limit = rollback_limit`, copies the snapshot cache, and calls `unfreeze()` — atomically replacing the live game state with the captured state.

**Verification note:** a real 68-menu save was inspected directly (raw `zipfile`/`pickle` read of the on-disk file, bypassing `renpy.load()`) to confirm the design holds up under actual gameplay: exactly one `TLSnapshotCache` instance, 872 distinct objects backing 32,120 snapshot-root references (97.3% reference-sharing), and — checked explicitly — no object shared across multiple cached snapshots ever carried different content at different appearances (which would indicate something mutated a supposedly-frozen value in place). `_tl_test_snapshot_cache_save_round_trip` in `timeline_tests.rpy` automates this same check via a real `renpy.save()` to a private slot followed by a raw read-back — deliberately never calling `renpy.load()`, which would replace the live store and jump execution mid-test-run.

**Rollback allowance (`rollback_limit`)**: the synthetic log's `rollback_limit` is set to the value captured at snapshot time, not hardcoded. `RollbackLog.rollback()` (called from inside `unfreeze()`) decrements it by 1 while consuming the synthetic entry — the same cost a real `renpy.load()` pays against the save's own `rollback_limit`. Passing the historical value straight through therefore reproduces exactly what "made a save right before the menu, then loaded it" would look like, rather than resetting the player's rollback depth to near-zero.

**Overlay screens after unfreeze**: `_tl_on_load` hides all `config.overlay_screens` when `persistent._tl_synthetic_jump` is True. Ren'Py's `before_restart()` (called inside `unfreeze()`) marks the current session's overlay `ScreenDisplayable` objects as `restarting=True`; these stale objects end up in the live `scene_lists` after rollback. `show_overlay_screens` finds them via `get_screen()` and skips recreation, leaving broken screens that drop all input. Hiding them forces fresh recreation.

## Disk Save Fallback (Backward Compat)

For sessions that predate snapshot capture (e.g. saves from before the mod was updated), `_find_slot` walks downward:

- **Tier 1** — exact `_pre_*` pre-save at the target index
- **Tier 2** — walk history descending from `target-1`; for each history node: check pre-save, then `_ch_*` checkpoint; also check chapter-end markers at each step
- **Tier 3** — `_ch_start` fallback

No new pre-saves or `_ch_*` checkpoints are written by the mod. Existing files on disk remain readable.

Pre-save slot format: `_pre_{NNNN}_{h6}` where `h6 = md5(repr((tuple(context[:N]), ast_key)))[:6]`.

After loading a fallback save, `_tl_store_wrapper` is in replay mode and auto-selects recorded choices until reaching the target.

## Shadow Path

Shadow path represents the player's **original future** — the choices they would have made had they not jumped. It drives the divergence indicator (↺) on post-jump cards.

**Staging (pre-jump):** `_stage_menu_replay` stores the full `_replay_entries(hist)` list in `persistent._tl_replay_path`. Each entry has `{index, chosen_index, ast_key}`. The `ast_key` field matches `_tl_node_menu_site_key()` — the same tuple used for shadow matching.

**Transfer (post-load):** `_tl_on_load` reconstructs `store._tl_shadow_path` from `persistent._tl_replay_path`:
- Menu jump (`_tl_replaying=True`): entries with `index > target_index` become the shadow
- Chapter jump (`_tl_replaying=False`, `_tl_replay_target=None`): all entries used as shadow directly; `_tl_replay_path` cleared

**Consumption:** After each normal (non-replay) menu choice, `_tl_store_wrapper` calls `_tl_consume_shadow_path(shadow_path, node, chosen_index)`. It scans for an entry matching the current node by `ast_key`. When found:
- All entries before the match are discarded
- The matched entry is consumed; returns `(new_path, diverged_ci, match_mode)` 3-tuple
- If `diverged_ci` is set (player chose differently), `node["_shadow_orig_chosen"]` is stamped — this drives the ↺ indicator in the card UI

**Chapter jumps:** `_stage_chapter_shadow` stores post-chapter entries with `replaying=False` and `replay_target=None`. `_tl_on_load` recognizes this pattern and uses all entries as shadow without entering replay mode.

## Persistent State During a Jump

| Key | Set when | Cleared when |
|-----|----------|--------------|
| `persistent._tl_replaying` | `_stage_menu_replay` | Target menu reached |
| `persistent._tl_recovery_slot` | `_write_recovery` | `_tl_clear_replay_state` |
| `persistent._tl_replay_path` | `_stage_menu_replay` / `_stage_chapter_shadow` | Target menu reached (menu) or `_tl_on_load` (chapter) |
| `persistent._tl_replay_target` | `_stage_menu_replay` | Target menu reached |
| `persistent._tl_prev_thumb` | `_stage_menu_replay` | `_tl_clear_replay_state` |
| `persistent._tl_synthetic_jump` | `_dispatch_snap` | `_tl_on_load` after unfreeze |

`store._tl_shadow_path` is set by `_tl_on_load` and consumed down to `None` as the player plays forward. Cancel restores from `_ch_recovery`, which overwrites store — `_tl_shadow_path` is restored to the value it had when the recovery save was written (before the jump).

## Cancel Jump

`_tl_cancel_jump()` (triggered by the cancel button in the timeline):
1. Snapshots all current node thumbnails into `renpy.game._tl_thumb_cache` (they would be lost when the recovery save is loaded, since `_tl_history` reverts)
2. Calls `_tl_clear_replay_state()` — zeroes all persistent replay keys
3. Sets `store._tl_load_slot = _ch_recovery` and triggers a load

After the recovery load, the game is back at the exact point where the player opened the timeline and clicked jump, with full history intact.

## Important Invariants

- Recovery save is always written **before** any other state is mutated in `_tl_jump`. If anything fails after that point, cancel still works.
- Snapshots are stored on `renpy.game.log`, not in `store` or `persistent`, so they never appear in `get_roots()` — no O(N²) recursive cycle.
- `persistent._tl_replay_path` (not `store._tl_shadow_path`) is used to transport shadow entries across a load because store vars are overwritten by `renpy.load`. Reconstruction happens in `_tl_on_load`.
- `_tl_consume_shadow_path` matches by `ast_key` (AST-stable tuple); list-form `ast_key` from old saves is coerced to tuple for backward compat.
- `config.skipping` is cleared unconditionally when the target menu is reached, even if the player had skip mode active before the jump.

## Known Limits

- If no snapshot exists and no disk save exists for a node, the jump fails with a notify to the player. Snapshots are only available for menus played in the current session (the log is reset on load). The disk fallback covers saves written before the snapshot system.
- Shadow path entries are not retroactively validated against the game AST. If a jump crosses a chapter boundary where options have changed, a shadow entry may not match any live menu — it is silently skipped.
- Skip mode during replay fast-forwards all dialogue. If a game script has a blocking interaction between two menus that is not itself a menu, replay may stall.

## Where To Edit

| Task | File |
|------|------|
| Jump initiation, slot lookup, cancel | `backend/tl_saveload.rpy` |
| Snapshot capture and restore | `backend/tl_snapshot_cache.rpy` |
| Shadow path match and consume | `backend/tl_shadow_path.rpy` |
| Replay interception, shadow consumption at menus | `timeline_hooks.rpy` — `_tl_store_wrapper` |
| Shadow reconstruction after load | `timeline_hooks.rpy` — `_tl_on_load` |
| Jump label, load call | `timeline_screen.rpy` — `_tl_do_load` |
| Option button action (trigger) | `ui/tl_modal.rpy`, `timeline_screen.rpy` — `tl_chapter_divider` |