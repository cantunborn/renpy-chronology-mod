# Session Guide

This is the primary entrypoint for new AI sessions in this repo. Its job is to route a session to the right files quickly, not to explain the whole codebase.

## Read This First

1. `docs/AGENTS.md`
2. this file
3. the relevant feature doc in `docs/`
4. the target code files

## Project Purpose

This project is a Ren'Py chronology mod. It tracks player choices, builds a timeline UI, supports jump-back replay, and synthesizes ghost cards for if branches by monkey-patching renpy If.

## Runtime File Layout

The mod is split across three layers:

**Top-level entry points (`timeline_*.rpy`)**
- `timeline_init_ren.py` — core state defaults, constants, logging, AST map build, branch ID, img-name migration, thumb cache load/save lifecycle
- `timeline_hooks_ren.py` — menu interception, save triggers, chapter-end hooks, option-condition extraction
- `timeline_screen.rpy` — thin coordinator; delegates card/ghost/modal rendering to `ui/`
- `timeline_save_hooks_ren.py` — post-load validation and save compatibility
- `timeline_tests_ren.py` — in-game test runner (Shift+F9)

**Subsystem modules (`backend/`)** — all run at `init -2 python:`
- `tl_saveload_ren.py` — jump control: `_tl_jump`, `_tl_cancel_jump`, `_find_slot` (disk fallback), slot-naming helpers, recovery save write
- `tl_snapshot_cache_ren.py` — snapshot capture (`_tl_capture_snapshot`), cache on `renpy.game.log`, restore via `_tl_unfreeze_from_snapshot`
- `tl_assets_ren.py` — thumbnail capture, asset resolution, displayable creation, caching
- `tl_ghost_logic_ren.py` — ghost card synthesis; monkey-patches `renpy.ast.If.execute` and `Python.execute`
- `tl_route_logic_ren.py` — route tracker: AST index build, chip filtering/ordering, var change detection pipeline
- `tl_seen_check_ren.py` — seen-state tracking, descriptors, option-seen checks
- `tl_shadow_path_ren.py` — replay-aid shadow path: match and consume (3-tuple return); shadow entries transported via `persistent._tl_replay_path`
- `tl_chapter_ren.py` — chapter metadata loading, rollback
- `tl_menu_location_ren.py` — stable menu site identity keys
- `tl_menu_options_ren.py` — choice entry/index helpers
- `tl_coverage_ren.py` — coverage index: collect seen descriptors for all if-branch blocks
- `tl_ast_dump_ren.py` — live AST → JSON dump for offline tools

**UI screens (`ui/`)** — screen definitions only, no behavior logic
- `tl_cards.rpy` — past and current choice card screens
- `tl_ghost_cards.rpy` — ghost branch card screens
- `tl_route_screen.rpy` — route tracker chip bar (`tl_route`) and mod notification (`_tl_notify`)
- `tl_modal.rpy` — option modal screen
- `tl_debug.rpy` — debug overlay screen
- `tl_theme.rpy` — shared styling constants and theme helpers

## Live Tooling

- `tools/cf_adapter.py` — control-flow graph adapter (`RenpyFlowGraph` API); used with `cfg/full_ast.json`

Everything else in `tools/` (gen_cfg.py, causal_analysis.py, build_vis.py, etc.) is stashed and not in the working tree.

## Where To Look By Task

### Ghost cards

- `docs/GHOST_CARDS.md`
- `backend/tl_ghost_logic_ren.py`
- `ui/tl_ghost_cards.rpy`

### Route tracker / var change notifications

- `docs/ROUTE_TRACKER.md`
- `backend/tl_route_logic_ren.py`
- `ui/tl_route_screen.rpy`
- `timeline_screen.rpy` (tab toggle, tooltip, `_tl_capture_hover_pos`)

### Jump back / replay aid / shadow path

- `docs/JUMP.md`
- `backend/tl_saveload_ren.py`
- `backend/tl_snapshot_cache_ren.py`
- `backend/tl_shadow_path_ren.py`
- `timeline_hooks_ren.py`

### Thumbnails / asset images

- `backend/tl_assets_ren.py`
- `docs/DEV_NOTES.md` (assets section)

### Seen state / unseen dots

- `backend/tl_seen_check_ren.py`
- `docs/DEV_NOTES.md` (seen_check section)

### Chapter markers / jump to chapter

- `backend/tl_chapter_ren.py`
- `timeline_hooks_ren.py` (`_tl_chapter_label_cb`)
- `game-chapters/*.json`

### Docs / recent changes

- `docs/changelog.md`
- `docs/DEV_NOTES.md` — full function reference
- `docs/CODE_FLOW.md` — subsystem architecture and flow

## Process Rules

- Inspect before editing.
- Explain intended changes before patching.
- Prefer small scoped changes.
- Verify behavior after changes.
- Update the relevant doc after successful work.

## Current Active Constraints

- Ren'Py compatibility matters. Do not casually introduce version-specific assumptions.
- Installed game-mod dir for live verification:
  - `/Users/divyjain/Games/Personal/Imperial Chronicles.app/Contents/Resources/autorun/game/renpy-chronology-mod`
- Do not push files into that installed directory during implementation. Only copy files there after the user says the implementation is satisfactory and wants to move on to live verification.
- `cfg/full_ast.json` is the main offline AST source artifact.

## Common Follow-Up Docs

- `docs/GHOST_CARDS.md`
- `docs/ROUTE_TRACKER.md`
- `docs/NON_INTRUSIVENESS.md`
- `docs/DEV_NOTES.md`
- `docs/CODE_FLOW.md`
- `docs/changelog.md`

## Stashed / Experimental Docs

If a task touches an approach that was explored but not shipped (causal analysis, CFG flowchart, formula solver, Z3 slice, hub cards, route reachability, WP solver), check `docs/Experiments/` first. Those docs describe the design and why the approach was stashed, which is useful context before deciding whether to revive or replace it.