# Changelog

All changes are listed by commit, most recent first. The Unreleased section covers work
that is present in the codebase but not yet committed.

---

## Unreleased

### Tooling: PEP 484 type comments added to all top-level functions across the mod's `.py` files

Added a Python-2-safe (Ren'Py 7) `# type: (ParamType, ...) -> ReturnType` trailing comment to every module-level (`^def `) function across 16 files (136 functions total), so LSP hover, `findReferences`, and `goToDefinition` work without changing runtime behavior. Nested/closure functions and class methods were left untyped — they get no cross-file `findReferences` benefit. Every parameter got a real inferred type (never the `...` shorthand), cross-checked against `docs/DEV_NOTES.md`'s function tables and, where the docs table did not match the code, against the code directly.

- Files typed: `timeline_hooks_ren.py`, `timeline_init_ren.py`, `timeline_save_hooks_ren.py`, `timeline_tests_ren.py`, and `backend/tl_assets_ren.py`, `tl_ast_dump_ren.py`, `tl_ast_utils_ren.py`, `tl_chapter_ren.py`, `tl_coverage_ren.py`, `tl_ghost_logic_ren.py`, `tl_menu_location_ren.py`, `tl_menu_options_ren.py`, `tl_route_logic_ren.py`, `tl_saveload_ren.py`, `tl_seen_check_ren.py`, `tl_snapshot_cache_ren.py`.
- Three doc-vs-code return-type mismatches found while typing (docs table said one thing, code does another — typed from code, docs not yet corrected):
  - `tl_menu_location_ren.py`: one function's documented return type does not match its actual `str`-vs-`tuple` return.
  - `backend/tl_ghost_logic_ren.py`: `_tl_get_taken_branch` and `_tl_build_ghost_payload` are documented as returning `int`/`dict`, but both have early-return `None` paths in the code — typed as `Optional[int]`/`Optional[dict]`.
- Two pre-existing (not introduced by this pass) runtime None-safety gaps surfaced by accurate typing, left as-is since fixing them would change runtime logic, out of scope for a type-comment-only pass:
  - `backend/tl_saveload_ren.py`: `_tl_jump`'s public signature allows `node_index=None`/`option_index=None`, but its non-chapter branch passes them into `_stage_menu_replay`/`_find_slot` (and, transitively, `_tl_get_menu_snapshot` in `tl_snapshot_cache_ren.py`), all of which assume real `int`s with no runtime guard.
  - `backend/tl_saveload_ren.py`: `_valid_snap(snap)` is a plain `bool` check, not a type-narrowing guard, so Pyright cannot narrow `Optional[dict]` to `dict` after `if _valid_snap(snap): _dispatch_snap(snap)` — `_dispatch_snap` still shows `snap` as possibly `None`.
- No test impact — type comments are invisible to the CPython interpreter; full suite unaffected.

### Docs: `docs/DEV_NOTES.md` and `docs/CODE_FLOW.md` synced with the current code

- **`docs/DEV_NOTES.md` test-suite tables** — audited against actual test code via LSP. **Python test tables** (`tests/*.py`, 12 files): corrected class/test counts, removed phantom classes (`TestFindNearestSaveDensePattern`, misattributed `TestPythonExecutePatched`), added undocumented classes, and added three fully missing file tables (`test_ast_walk.py`, `test_coverage.py`, `test_snapshot_cache.py`). **In-game test runner table** (`timeline_tests_ren.py`): replaced the stale 19-suite table (which listed 3 nonexistent suites and was missing 18 real ones) with all 47 actual suites, verified counts, and correct suite names (`pre_save_slot_format` → `pre_save_slot`); added the previously undocumented `heal_restarting_screens` suite; removed the obsolete "out of sync" note.
- **`docs/CODE_FLOW.md` file references** — updated every `.rpy` reference for a file already converted to `_ren.py` (`timeline_hooks_ren.py`, `timeline_init_ren.py`, `timeline_save_hooks_ren.py`, and all listed `backend/tl_*_ren.py` modules). Corrected the `ui/` layer description: `ui/tl_cards.rpy`'s `tl_card` screen still holds a `python:` block for display-only decisions, so `ui/` is not behavior-logic-free. Updated `_tl_walk_ast_blocks()`'s documented signature to match the code: it now takes `initial_state` and threads state through `visitor_fn(node, state, current_label)`.

### Tooling: `tl_ast_dump.rpy` converted to `_ren.py`; fixed dead `_tl_ast_map` reference in the debug overlay

- **`backend/tl_ast_dump_ren.py`** (new; `tl_ast_dump.rpy` left in place, untouched, per project convention) — single `init -2 python:` block, content-exact conversion of `_tl_cfg_dump_ast`. `TYPE_CHECKING` header imports `os`, `renpy`, `_tl_log`/`_tl_json` (`timeline_init_ren`).
- **`ui/tl_debug.rpy`** — the `ast_menus` debug row still read `_tl_ast_map`, a field the "Remove dead `_tl_ast_map` fallback" refactor deleted earlier without updating this one leftover reference, causing a `NameError` on open. Replaced with `len(_tl_live_menu_lookup())`, confirmed via LSP to draw from the same `namemap` source `_tl_ast_map` used to.

### Tooling: minimal-change pyright error fixes across mod-owned `_ren.py` files

Triaged the remaining full-project pyright error list for mod-owned `_ren.py` files and fixed every error that had a low-risk, minimal fix, deferring anything that would require a larger design change (e.g. `timeline_hooks.rpy`, not yet converted).

- **`typings/renpy-stubs/rollback.pyi`** — added `_tl_snapshot_cache: Incomplete` to `RollbackLog` (attached at runtime by `tl_snapshot_cache_ren.py`; kept `Incomplete` rather than importing the mod's `TLSnapshotCache` class, to avoid a base-SDK stub depending on mod code).
- **`typings/renpy-stubs/persistent.pyi`** — added `_seen_ever: dict` and `_chosen: dict`, core RenPy fields lazily created in `renpy/persistent.py` and missed by the SDK's own stub generator (same gap category as `config.after_load_callbacks`).
- **`typings/renpy-stubs/game.pyi`** — added a mod-registry section for `_tl_thumb_cache`, `_tl_asset_thumb_cache`, `_tl_pending_snap`.
- **`typings/store.pyi`** — added `_tl_pending_save_index: int | None` (a genuine `default`-declared field missing from the registry).
- **`backend/tl_route_logic_ren.py`** — added `store` to the existing `TYPE_CHECKING` import line.
- **`backend/tl_assets_ren.py`** — added `os`, `hashlib as _tl_hashlib`, and `Transform` (`renpy.display.transform`) under `TYPE_CHECKING`.
- **`backend/tl_saveload_ren.py`** — added `hashlib as _tl_hashlib` under `TYPE_CHECKING`; added `assert iface is not None` after `iface = renpy.game.interface` (the stub's `Interface | None` type is accurate — `interface` can genuinely be `None` before init).
- **`backend/tl_ast_utils_ren.py`** — extended the existing `getattr`-fallback compat pattern (already used for `ast.Constant`) to `ast.Str`/`ast.Num`, which the bundled typeshed no longer declares; behavior is unchanged on both Ren'Py 7 (Python 2, where `Str`/`Num` still exist) and Ren'Py 8.
- **`timeline_tests_ren.py`** — fixed `_TLMockedUnfreeze.mock_unfreeze`'s signature (`self_` → `self`, added `label=None` default) to match `RollbackLog.unfreeze`'s real signature; added `assert self._saved is not None` in `__exit__`, needed once the signature fix made `_saved`'s type strict; added the `store.` prefix to bare reads of `_tl_*` fields already registered in `store.pyi` (`_tl_history`, `_tl_context`, `_tl_node_count`, `_tl_modal_node`, `_tl_load_slot`, `_tl_ast_ready`, `_tl_ghost_nodes`, `_tl_pending_save_index`) — bare access to a `default`-declared global can never resolve under the current architecture, only `store.`-prefixed access can.
- Not fixed (deferred, needs `timeline_hooks.rpy` conversion first): bare calls to `_tl_record_before`, `_tl_record_after`, `_tl_on_game_start`, `_tl_on_load`, `_tl_interact_callback` in `timeline_tests_ren.py` — these are functions defined inside `timeline_hooks.rpy`'s still-unconverted marker block, so no `TYPE_CHECKING` import or `store.` prefix can resolve them yet.
- Confirmed out of scope by design (not fixable via minimal changes): `unicode`/`basestring`/`__builtin__` Python 2/3 compat detection patterns, and the `pygame` import (compiled C extension with no derivable stub source).
- No test impact — full suite still 485/485, since all changes are stub-only or type-narrowing assertions that don't alter runtime logic.

### Tooling: narrowed `persistent`/`store` `_tl_*` stub fields from `Incomplete` to concrete types

The `persistent`/`store` custom-field registry (see below) declared all 36 `_tl_*` fields as `Incomplete`, which suppresses attribute/type-mismatch checking on every read and write — a typo'd key or wrong-shape assignment wouldn't be caught. Types inferred by reading each field's `default`/init-site value and its actual usage across all call sites (LSP `findReferences` where the field is imported/typed, direct `grep` for the handful reached only through dynamic `getattr(store, ...)`/`_st.*` access that LSP can't resolve statically).

- **`typings/store.pyi`** — all 20 fields given concrete types (`list[dict]`, `dict[str, tuple]`, `set[str]`, `tuple[int, int]`, `dict \| None`, etc.) except the 4 test-only scratch fields (`_tl_test_capture_probe`, `_tl_test_results`, `_tl_test_reuse_changing`, `_tl_test_reuse_probe`), whose shape varies per test and which are typed `Any` instead. Unused `from _typeshed import Incomplete` import replaced with `from typing import Any`.
- **`typings/renpy-stubs/persistent.pyi`** — all 21 mod-owned fields given concrete types (`dict[str, bool]`, `list[str]`, `dict[tuple[str, int], list[str]]`, etc.); the file's other (non-mod) `Incomplete` fields (`backup`, `registry`, `MP_instances`) are untouched.
- Verified via `pyright typings/store.pyi typings/renpy-stubs/persistent.pyi` (0 errors) and a full project `pyright` pass — no new errors introduced on any `_tl_*` field; all remaining errors are the same pre-existing gaps documented in the entries below. No test impact — full suite still 485/485, since `.pyi` files carry no runtime code.

### Tooling: `timeline_save_hooks.rpy` and `timeline_init.rpy` converted to `_ren.py`, closing the last major cross-file stub gaps

`timeline_init.rpy` (386 lines) owns most of the mod's shared constants, `_tl_log`, the runtime caches, the AST-map builders, and the per-save `default` globals — nearly every other converted file calls into it, so until now those calls were undefined to pyright regardless of how many other files got converted. Structurally harder than prior single-block conversions: it has three separate `init` blocks (`init -2 python:`, `init python:`, `init -2 python:`) plus ~20 bare `default` statements sitting outside any python block, between the first two. `_ren.py` files support multiple sequential `"""renpy\n...\n"""` markers (already proven in `tl_ghost_logic_ren.py`); the `default` statements got their own dedicated marker with no attached Python body, since they're literal Ren'Py script statements, not Python. `timeline_save_hooks.rpy` converted the same session as a smaller single-block precursor, and surfaced two related stub gaps that had to close first.

- **`timeline_init_ren.py`** (new; `timeline_init.rpy` left in place, untouched, per project convention) — four marker blocks in original order: `init -2 python:` body (constants, `_tl_log`, `_tl_runtime_cache_store`/`_tl_runtime_choice_returns`, `_tl_chapters = _tl_load_chapters()`, `_tl_load_thumb_dict`), the bare `default` statements verbatim, `init python:` body (persistent-state setup, thumbnail cache load/migration, `_tl_save_thumbs`), `init -2 python:` body (`_tl_count_locked_branches`, `_tl_build_ast_map`, `_tl_salvage_history_ast_keys`, `_tl_migrate_img_names`). `TYPE_CHECKING` header imports `_tl_load_chapters` (`tl_chapter_ren`), `_tl_eval_seen_fn` (`tl_seen_check_ren`), `_tl_build_route_index` (`tl_route_logic_ren`), `_tl_build_coverage_index` (`tl_coverage_ren`), `_tl_build_menu_scene_index`/`_tl_live_menu_lookup`/`_tl_menu_site_key`/`_tl_location_menu_site_key` (`tl_assets_ren`/`tl_menu_location_ren`) — all already converted, so no new forward stub gaps.
- **`timeline_save_hooks_ren.py`** (new; `timeline_save_hooks.rpy` left in place) — single `init python:` block, content-exact, defines `_tl_validate_on_load` and `_tl_heal_restarting_screens`, both registered via `config.after_load_callbacks.append(...)`.
- Content fidelity for both verified byte-for-byte against the originals: `timeline_init_ren.py` via a line-by-line diff of each marker block's body against the corresponding dedented original range (only cosmetic differences survived — blank-line spacing matching `ren_py_to_rpy`'s own insertion behavior, trailing newline); `timeline_save_hooks_ren.py` via `difflib.unified_diff` against the dedented original body.
- **`typings/renpy-stubs/config.pyi`** — added `after_load_callbacks: list`, needed by `timeline_save_hooks_ren.py`. The real declaration isn't in `renpy/config.py`; it's a game-script-level default in the SDK's `renpy/common/00start.rpy:57` (`config.after_load_callbacks = [ ]`), the same category of gap as the pre-existing `statement_callbacks: Incomplete` line.
- **`typings/renpy-stubs/__init__.pyi`** — added `from .exports import *` after `from . import exports as exports`, so `renpy.exports.*` functions (e.g. `show_screen`, used by `timeline_save_hooks_ren.py`) resolve as top-level `renpy.*` attributes, matching the real runtime behavior (`renpy/defaultstore.py:469`: `globals()["renpy"] = renpy.exports`, merged into `renpy.store` via `post_import()`). This surfaced a `version` naming collision — `renpy.version: str` (the package version string) vs. `renpy.exports.version()` (a function) — resolved by commenting out the now-unreachable `version: str` line with an explanatory comment (kept, not deleted, since it's never referenced anywhere in the codebase but has reference value for the stub's accuracy).
- Retroactively added `TYPE_CHECKING` imports to every file that already called into `timeline_init_ren`: `tl_coverage_ren.py`, `tl_chapter_ren.py`, `tl_assets_ren.py`, `tl_ghost_logic_ren.py`, `tl_menu_location_ren.py`, `tl_saveload_ren.py`, `tl_seen_check_ren.py`, `tl_shadow_path_ren.py`, `tl_route_logic_ren.py`, `tl_snapshot_cache_ren.py`, `tl_menu_options_ren.py`, `tl_ast_utils_ren.py` (which had no `TYPE_CHECKING` block at all before this), `timeline_save_hooks_ren.py`, and `timeline_tests_ren.py` (also gained the `timeline_save_hooks_ren` import for `_tl_validate_on_load`/`_tl_heal_restarting_screens`).
- Remaining pyright noise is pre-existing and out of scope for this conversion: `renpy.game._tl_thumb_cache`/`_tl_asset_thumb_cache` (the `game.pyi` stub doesn't declare arbitrary custom attrs — same gap already present in `tl_assets_ren.py`/`tl_saveload_ren.py`), the Python-2 `__builtin__` compat shim (unresolvable under a Python 3 stub environment by design), and bare-name access to `default`-declared globals (`_tl_history`, `_tl_context`, etc.) in `timeline_tests_ren.py` — `default` statements live inside the `"""renpy...` marker, which pyright sees as a string literal, not a declaration, so they never become real Python names; only `store.`-prefixed access resolves. Only `timeline_hooks.rpy` remains unconverted. No test impact — full suite still 485/485, since the transform never changes executed script logic.

### Tooling: `backend/` fully converted to `_ren.py` for pyright/Pylance navigation

`.rpy` files are opaque to static analysis — Ren'Py's `init python:` blocks aren't valid standalone Python, so pyright/Pylance can't parse them at all, leaving every backend function invisible to goToDefinition, findReferences, and hover, and forcing grep/Read as the only way to navigate cross-file calls. `_ren.py` is Ren'Py's own native mechanism for the reverse: a file that's simultaneously a valid `.rpy`-equivalent script (Ren'Py extracts the code between `"""renpy\n...\n"""` markers and re-indents it into the named `init` block at transform time) and valid standalone Python (everything outside those markers, including a `TYPE_CHECKING`-guarded header importing `renpy`/`persistent`/`store` and any cross-file `_tl_*` symbols the file calls, which Ren'Py itself ignores). Converting a file to this form is a mechanical, content-preserving transform — the executed script logic never changes — that switches it from invisible to fully navigable.

Every `backend/*.rpy` file has now been converted this way; this batch was the last 3. Old `.rpy` originals are left on disk untouched per project convention (never removed unless explicitly asked). Only `timeline_init.rpy` and `timeline_hooks.rpy` remain in `.rpy` form (both root-level, out of scope for this pass) — once those convert too, the regex-based `.rpy`-block extraction branch in `tests/conftest.py`'s `load_rpy()` becomes fully dead code and can be deleted (it exists solely to load raw `.rpy` files into the pytest harness).

- **`backend/tl_assets_ren.py`** (was `tl_assets.rpy`) — single `init -2 python:` block, content-exact. Forward `TYPE_CHECKING` imports for `_tl_menu_site_key` (`tl_menu_location_ren`) and `_tl_walk_ast_blocks` (`tl_ast_utils_ren`). Retroactively added `TYPE_CHECKING` imports to `backend/tl_menu_location_ren.py` (for `_tl_stmt_ast_key`) and `backend/tl_seen_check_ren.py` (for `_tl_scene_stmt_img_name`), both of which already called into this file before it was navigable.
- **`backend/tl_ghost_logic_ren.py`** (was `tl_ghost_logic.rpy`) — has two separate init blocks (`init -2 python:` then `init python:`, so the monkey-patch on `renpy.ast.If.execute` runs after RenPy's AST classes exist); `_ren.py` files support multiple sequential `"""renpy\n...\n"""` markers, one per block, confirmed against `renpy/lexer.py`'s `ren_py_to_rpy` state machine. Forward `TYPE_CHECKING` imports for `_tl_prettify_var`/`_tl_ast_literal_value`/`_tl_strip_renpy_tags`/`_tl_is_game_file` (`tl_ast_utils_ren`), `_tl_make_seen_fn`/`_tl_eval_seen_fn` (`tl_seen_check_ren`), `_tl_flush_var_changes` (`tl_route_logic_ren`), `_tl_resolve_live_menu_img_name`/`_tl_img_name_is_movie` (`tl_assets_ren`). Retroactively added a `TYPE_CHECKING` import to `backend/tl_route_logic_ren.py` (for `_tl_ghost_ast`, `_tl_extract_vars_from_conditions`).
- **`backend/tl_snapshot_cache_ren.py`** (was `tl_snapshot_cache.rpy`) — single `init -2 python:` block, content-exact, no forward cross-file dependencies. Retroactively added a `TYPE_CHECKING` import to `backend/tl_saveload_ren.py` (for `_tl_get_menu_snapshot`, `_tl_get_chapter_snapshot`).
- **`tests/conftest.py`** — updated the 3 corresponding entries in the `_rpy_ns` loader list from `.rpy` to `_ren.py`.
- **`timeline_tests_ren.py`** (the RenPy in-game test runner, triggered via Shift+F9 during gameplay — separate from the `tests/` pytest suite) already existed in `_ren.py` form from an earlier session, but it exercises functions from all 3 files converted this batch (`_tl_capture_thumbnail`; `_tl_on_if_execute`; and the snapshot-cache API — `_tl_make_cache`, `_tl_get_snapshot_cache`, `_tl_capture_snapshot`, `_tl_get_menu_snapshot`, `_tl_transfer_snapshot_cache`, `_tl_unfreeze_legacy`, `_tl_unfreeze_from_snapshot`, `_TL_PLAIN_DICT`), which pyright flagged as undefined until this batch made them resolvable. Added the retroactive `TYPE_CHECKING` imports for all of them (137 → 105 pyright errors); the remaining 105 all trace to the still-unconverted `timeline_init.rpy`/`timeline_hooks.rpy`/`timeline_save_hooks.rpy`.
- Symbols still owned by the not-yet-converted `timeline_init.rpy` (`_tl_log`, `TL_THUMB_WIDTH`, `TL_DEBUG_ASSET`, `TL_DEBUG_GHOST`, `_tl_hashlib`, `_tl_builtin_id`, etc.) are left undeclared in every converted file's header, matching the existing pattern — they'll resolve once that file converts too. No test impact — full suite still 485/485, since the transform never changes executed script logic.

### Tooling: `persistent`/`store` custom-field registry in the pyright stubs (local-only, not committed)

`typings/renpy-stubs` types `renpy.persistent` as the real module (functions like `save()`/`load()`) and `renpy.store` as bare `Any` — neither gave pyright any way to catch a typo'd `persistent._tl_*`/`store._tl_*` field name, and the mod has no other central listing of which custom fields it actually uses. `typings/` is gitignored (`.gitignore:6`), so this is local-only tooling, not shipped or version-controlled.

- **`typings/renpy-stubs/persistent.pyi`** — appended module-level declarations for all 21 `persistent._tl_*` fields found in use (`backend/*.rpy`/`*_ren.py`, `timeline_init.rpy`, `timeline_tests.rpy`), typed from their `default`/init-site values where obvious (`bool`, `int`) and `Incomplete` otherwise.
- **`typings/store.pyi`** — new top-level file (none existed before; `renpy.store` was previously typed as bare `Any`, which suppressed all attribute checks). Declares the 20 `store._tl_*` fields found in use, gathered via a string-literal-excluding scan across all `store`/`_store`/`_st` import aliases. Bare `import store` (used by real executed code, distinct from `renpy.store`) had zero stub support until this file existed — `renpy.store` and bare `store` are the literal same module object at runtime (`renpy/__init__.py`: `sys.modules['store'] = sys.modules['renpy.store']`), so `typings/renpy-stubs/__init__.pyi`'s `store: Any` line was changed to `import store as store`, aliasing both names to this one file. All fields live here directly (no re-export) since wildcard-import silently drops `_`-prefixed names.
- Verified: pyright errors on `persistent._tl_*`/`store._tl_*` access dropped from ~41 to 0 across the fields now declared; a deliberately misspelled field (`_tl_replayingg`) still errors, confirming the registry actually catches typos/undeclared access rather than just silencing everything. `typings/` changes are inert at runtime (pyright-only), so no test impact — full suite still 485/485.

### Test: generic live-reference-leak regression guard for cached snapshots

The ctx-aliasing bug fixed below was found by manually auditing one field at a time (`scene_lists`, then `ctx` itself) — there was no way to know whether some other field aliased live state without guessing. Added a type-agnostic check that catches any future instance of this bug class automatically, on real snapshots, without per-field knowledge.

- **`timeline_tests.rpy`** — added `_tl_reachable_ids(root, exclude_types)`, a `gc.get_referents()`-based recursive walk collecting `id()` of every object reachable from a root (the same primitive Python's own cycle collector uses internally, so it needs no per-class/per-field enumeration). Safe shared singletons (`str`/`bytes`/`int`/`float`/`bool`/`None`/`type`/functions/modules) are excluded to avoid false positives from ordinary interpreter-level sharing. Added `_tl_test_snapshot_no_live_aliasing`, registered in `_tl_run_tests()` after `_tl_test_cache_not_in_get_roots`: builds the live-reachable id set from `renpy.game.context()`, `renpy.game.log.get_roots()`, and currently-shown screens (deliberately not `renpy.game.log` itself, which would also walk into the cache under test and trivially self-intersect), then asserts every real accumulated `cache.menu`/`cache.chapter` snapshot's `roots` shares no id with it. Scoped to current-shape entries only (legacy `"context"`-key entries, possible only if an old save was loaded this session, are skipped — they predate this check and can't be retroactively validated). `ctx` itself isn't walked: it's pickled bytes, which can't alias anything by construction. Dev-time only (run via Shift+F9 before release); not a production safeguard and not a substitute for `_tl_heal_restarting_screens()`, which heals saves already corrupted before this fix shipped.

### Fix: ctx snapshots aliased live scene_lists screens, corrupting screens across jumps and saves

The reference-sharing redesign below (previous Unreleased entry) closed the live-aliasing hole for `roots`, but `ctx` (`renpy.game.context().rollback_copy()`) was still stored live. `rollback_copy()` only shallow-copies `scene_lists` (`SceneLists.__init__` does `self.layers[i] = oldsl.layers[i][:]` — same `ScreenDisplayable` objects, new list), so every cached snapshot's `ctx` aliased the live session's screen objects. Because `TLSnapshotCache` deliberately keeps snapshots alive across multiple `unfreeze()` calls, Ren'Py's `before_restart()` (fired inside every `unfreeze()`) marking a currently-shown screen `restarting=True` could leak into other cached snapshots sharing that same live object — and since the whole cache rides inside real save files (`renpy.game.log` is pickled whole on every save), the corruption could be written to disk. A stuck `restarting=True` screen drops all input for that screen — reported by a player whose save had 3 mod screens (and the base game's `quick_menu`) stuck this way.

- **`backend/tl_snapshot_cache.rpy`** — `capture()` now pickles `ctx` to bytes via `renpy.compat.pickle.dumps` (the same wrapper `renpy/loadsave.py` itself uses for real saves, chosen over stdlib `pickle` because this blob rides inside save files and must stay readable across a future Ren'Py/Python version bump) instead of storing the live object. `_tl_unfreeze_from_snapshot`'s current-shape path now does `renpy.compat.pickle.loads(snap["ctx"])` instead of `copy.deepcopy` — unpickling always constructs a fresh, independent object graph, so no separate deepcopy is needed. The legacy pre-blob path (`_tl_unfreeze_legacy`, `"context"` key) is unchanged.
- **`timeline_save_hooks.rpy`** — added `_tl_heal_restarting_screens()`, registered on `config.after_load_callbacks`, as a one-time safety net for saves already corrupted before this fix (the pickle change only prevents *new* corruption). Runs on every load, clearing `.restarting` on any currently-shown screen that carries it and calling `renpy.restart_interaction()` if anything was healed. Intentionally not scoped to `_tl`-prefixed screens — the bug affects any `config.overlay_screens` entry (including the base game's `quick_menu`), and healing an ordinary on-demand screen that happens to carry the flag is harmless since those get recreated unconditionally on next display regardless.
- **`timeline_tests.rpy`** — updated every test that hand-builds a live-shaped `{"ctx": ...}` snap to pass `renpy.compat.pickle.dumps(...)` instead of a live `_TLFakeCtx()` (`_tl_test_cache_not_in_get_roots`, `_tl_test_capture_snapshot_contract`, `_tl_test_unfreeze_live_path`, `_tl_test_unfreeze_live_repeat_isolation`, `_tl_test_unfreeze_dispatch_routes_by_shape`, `_tl_test_snapshot_cache_mixed_shapes`); `_tl_test_valid_snap_shapes` unchanged since `_valid_snap` only checks key presence, never the value.
- **`docs/JUMP.md`** — updated capture/restoration sections for the pickled-ctx shape, documented the heal hook, and corrected a stale flow-diagram claim that the snapshot jump path goes through `renpy.load()` (it calls `_tl_unfreeze_from_snapshot` directly; `config.after_load_callbacks` still fires via the same `label="_after_load"` mechanism `renpy.load()` itself uses).

### Change: snapshot cache redesigned around reference-sharing, replacing per-snapshot blob/zdict compression

The zdict-compressed-blob approach below (never committed/released) fixed the immediate size blowup but still pickled each snapshot as its own independent `bytes` value — the shared zlib dictionary papered over the loss of pickle's own cross-object memoization instead of restoring it. It also meant every snapshot paid a compress/decompress cost and carried a bespoke on-disk format that needed its own dispatch logic.

Replaced with a `TLSnapshotCache` class that owns exactly one frozen (deep-copied-once) reference for every distinct mutable value ever captured. On each capture, `_freeze_roots` compares every live root value against the value frozen in the *previous* capture using a single generic comparator, `_tl_values_equal(a, b)` (`a is b` fast path, else `pickle.dumps(a) == pickle.dumps(b)`, no per-type special-casing since the design must not assume anything about which game vars do or don't mutate) — unchanged values reuse the prior frozen reference, changed or new values get a fresh `copy.deepcopy`. Snapshots are stored as plain `{"roots": ..., "ctx": ..., "rollback_limit": ...}` dicts (no blob/compression step at all). Because unchanged values across many cached menus now point at the *same* object, Ren'Py's own single combined save pickle dedupes them for free via its normal memo table — the mechanism the blob/zdict approach was trying to reconstruct manually, restored by not breaking it in the first place. Verified against a real 68-menu save: 872 distinct objects backing 32,120 snapshot-root references (97.3% dedup), file size 1.7MB.

- **`backend/tl_snapshot_cache.rpy`** — full rewrite. `TLSnapshotCache.__init__` sets `self.menu`, `self.chapter` (both `_TL_PLAIN_DICT`) and `self._last_roots = None`. `_freeze_roots(live_roots)` implements the reuse/copy decision described above. `capture()` replaces `_tl_capture_snapshot`'s old body (unchanged: `log.complete(False)`, `rollback_copy()`, `.rpyc` label patching, `rollback_limit` capture) but now calls `_freeze_roots(get_roots())` instead of pickling to a blob. `cache_menu`/`cache_chapter`/`get_menu`/`get_chapter`/`transfer_to` replace the old dict-based cache access. All free-function wrappers (`_tl_capture_snapshot`, `_tl_cache_menu_snapshot`, `_tl_get_menu_snapshot`, `_tl_transfer_snapshot_cache`, etc.) are preserved, delegating to the singleton instance at `renpy.game.log._tl_snapshot_cache` — no caller outside this file changed its call signature. `_tl_unfreeze_from_snapshot` dispatches on shape: `"context"` key present → legacy pre-blob shape (`_tl_unfreeze_legacy`, unchanged deepcopy-based path, still the fallback for snapshots cached inside very old saves); otherwise the current live shape, deep-copies `roots`/`ctx` fresh and calls `_tl_build_and_unfreeze`. The blob/zdict shape is dropped entirely — it never shipped, so no read-compat path is needed for it. `_tl_unfreeze_legacy` no longer catches deepcopy failures and falls back to live/aliased references; exceptions now propagate, matching the same all-or-nothing principle already applied to the capture side (closing the read-path half of the bug fixed in *"Fix: jump-back snapshots corrupted by shared live store references"* below).
- **`backend/tl_saveload.rpy`** — `_valid_snap` updated to accept both the live shape (`"roots"` + `"ctx"`) and the legacy shape (`"roots"` + `"context"`, rejecting `context: None`); the blob shape's `"blob"` key check is gone.
- **`timeline_hooks.rpy`** — both debug-logging sites (menu-snapshot capture, chapter-snapshot capture) simplified to read `snap["ctx"]`/`snap["roots"]` directly — no decode step needed now that snapshots aren't compressed blobs.
- **`tests/test_snapshot_cache.py`** — rewritten for the class: construction (`TestMakeCache`) and the `_freeze_roots` reuse/copy contract (`TestFreezeRoots` — immutable values shared by reference, unchanged mutable values reuse the prior frozen copy by content equality not identity, changed values get their own copy, frozen copies never alias the live object, new keys get frozen, first-ever capture has no prior snapshot to compare against).
- **`timeline_tests.rpy`** — snapshot suite rewritten around the class and the live/legacy shape dispatch (`_tl_test_snapshot_capture_isolation`, `_tl_test_capture_snapshot_contract`, `_tl_test_capture_snapshot_reuses_unchanged_values`, `_tl_test_unfreeze_live_path`, `_tl_test_unfreeze_live_repeat_isolation`, `_tl_test_unfreeze_legacy_direct`, `_tl_test_unfreeze_dispatch_routes_by_shape`, `_tl_test_valid_snap_shapes`, `_tl_test_snapshot_cache_mixed_shapes`), all using `.menu`/`.chapter` attribute access instead of dict subscripting. Added `_tl_test_snapshot_cache_save_round_trip`: writes a real save to a private disk slot via `renpy.save()`, reads the file back directly with `zipfile`/`pickle` (never `renpy.load()`, which would replace the live store and jump execution mid-test), and asserts the unpickled cache is a single `TLSnapshotCache` with matching menu/chapter counts, well-formed snapshots, and no object shared across snapshots that carries different content at different appearances (the automated form of the manual save-file forensic check that validated the 97.3% dedup figure above).
- A live in-game run surfaced 4 stale `cache["chapter"]`/`cache["menu"]` dict-subscript call sites outside the originally-rewritten scope (`_tl_test_jump_chapter_staging`, a "v2 tests" function) — the class only supports `.menu`/`.chapter` attribute access. Fixed all 4, then swept the full repo for any other occurrence; none found.

### Fix: snapshot cache blob size grows unbounded with menu count

The blob-per-snapshot migration made each captured snapshot an independently pickled `bytes` value, which lost pickle's own cross-object memoization (previously free when the whole cache was serialized in one call as part of `renpy.game.log`). Save size grew linearly with the number of distinct menus visited (~5MB at 74 menus observed in testing).

- **`backend/tl_snapshot_cache.rpy`** — added `_tl_zdict_compress`/`_tl_zdict_decompress`, thin wrappers around `zlib.compressobj`/`decompressobj` with a preset dictionary (`zdict`). `_tl_make_cache()` now includes a `"zdict"` field, `None` until the first `_tl_capture_snapshot()` call, which bootstraps it with that capture's own raw (pre-compression) pickle bytes; every later capture in the same cache compresses against that shared dictionary instead of storing a fully independent blob. `_tl_unfreeze_from_snapshot` decompresses against the cache's `"zdict"` before unpickling. No change to the aliasing-safety guarantee — each snapshot is still captured as an independent `bytes` value at capture time; only the compression of that value changed. No new hook into Ren'Py's save/load machinery — the dictionary rides inside the same cache dict that already gets pickled as part of `renpy.game.log`, and is rebuilt automatically for every playthrough via the same bootstrap-on-first-capture logic (no persistence-format migration needed since the blob format itself is unreleased).
- **`tests/conftest.py`** — added `backend/tl_snapshot_cache.rpy` to the shared `_rpy_ns` load list so pytest can reach its functions.
- **`tests/test_snapshot_cache.py`** (new) — unit tests for `_tl_zdict_compress`/`_tl_zdict_decompress` in isolation: bootstrap-blob decodes correctly once a dictionary exists, normal round-trip, compressed-with-dict is smaller than plain `zlib.compress` on similar payloads, and decompressing with the wrong dictionary does not silently succeed.
- **`timeline_tests.rpy`** — `_tl_test_capture_snapshot_blob_contract` now decodes through `_tl_zdict_decompress` and asserts the cache's `"zdict"` is set after a capture. Added `_tl_test_capture_snapshot_zdict_bootstrap` (first capture sets the dictionary, later captures reuse it) and `_tl_test_capture_unfreeze_zdict_round_trip` (full capture→unfreeze pipeline against the real engine). `_tl_test_cache_not_in_get_roots` decodes real cached blobs via `_tl_zdict_decompress` instead of raw `pickle.loads`. The four tests that hand-build fake `{"blob": ...}` snaps (`_tl_test_unfreeze_blob_path`, `_tl_test_unfreeze_blob_repeat_isolation`, `_tl_test_unfreeze_dispatch_routes_by_shape`, `_tl_test_snapshot_cache_mixed_shapes`) now compress the fake payload with `_tl_zdict_compress` before wrapping it, so they match what `_tl_unfreeze_from_snapshot` actually expects to decompress.
- **`timeline_hooks.rpy`** — two debug-logging sites (menu-snapshot capture, chapter-snapshot capture) decoded `snap["blob"]` directly for logging and broke once blobs became compressed. Fixed both to decompress via the cache's `"zdict"` first. The chapter-snapshot site was a real (not just cosmetic) bug: `_tl_cache_chapter_snapshot(...)` sat inside the same `try` block *after* the failing decode, so a raised exception there skipped the actual cache write — chapter snapshots would have silently stopped being cached.
- **`timeline_tests.rpy`** — `_tl_test_snapshot_capture_isolation` also decoded real captured blobs directly (twice, to prove re-decoding is unaffected by later mutation); both decode sites now go through `_tl_zdict_decompress` with the cache's live `"zdict"` (which may still be the bootstrap `None`/first-capture state if run before any menu has been visited — `_tl_zdict_decompress` handles that correctly since a bootstrap blob decodes fine against any dictionary, per its own compression contract).

### Refactor: deduplicate RollbackLog.unfreeze mocking across 8 tests

`timeline_tests.rpy` had 8 near-identical copies (~15-20 lines each) of the same `RollbackLog.unfreeze` monkeypatch-and-restore boilerplate, one per unfreeze-path test.

- **`timeline_tests.rpy`** — added `_TLMockedUnfreeze`, a context manager (matching the file's existing `_TLStateGuard` hand-written-CM style, no `contextlib`) that installs the monkeypatch once, always records `(log_inst, roots, label)` per intercepted call, and restores the real method on exit. All 8 sites now use it via `with _TLMockedUnfreeze(r, s) as m: m.call(fn, *args)`; each test's assertions and check messages are unchanged.

### Change: synthetic jump preserves rollback allowance instead of resetting it

`_tl_build_and_unfreeze` hardcoded `new_log.rollback_limit = 1`, discarding the player's actual rollback depth on every jump — unlike a real Ren'Py save/load, which only costs `-1` against whatever `rollback_limit` the save carried.

- **`backend/tl_snapshot_cache.rpy`** — `_tl_capture_snapshot()` now also captures `renpy.game.log.rollback_limit` into the blob (`(roots, ctx, rollback_limit)`); `_tl_build_and_unfreeze` takes it as a parameter and sets it on the synthetic log instead of hardcoding `1`. Legacy (pre-blob) snaps have no captured value, so `_tl_unfreeze_legacy` falls back to `config.hard_rollback_limit`.
- **`timeline_hooks.rpy`**, **`timeline_tests.rpy`** — updated blob unpacking to the new 3-tuple shape; tests updated to pin the captured/propagated value instead of the old constant.

### Fix: two test bugs found running the blob-format suite in-game

First in-game run reported 10 failures, both in the tests, not the implementation.

- **`cache_not_in_get_roots`** (8 failures) — predates the blob format, read `snap["roots"]`/`snap["context"]` directly instead of decoding `snap["blob"]`. Fixed with a `_decode(snap)` helper shared by the menu/chapter loops.
- **`capture_snapshot_blob_contract`** (2 failures) — `isinstance(x, dict)` used the bare name `dict`, which Ren'Py rebinds inside `store` scope to `RevertableDict` (`minstore.py`). `_tl_capture_snapshot()` deliberately returns a plain `builtins.dict`, so the check was against the wrong type. Fixed by checking against `_tl_builtins.dict` explicitly.

Also traced (not a bug): a debug log showing `get_roots()` returning 384 keys after only ~5 menus looked like possible leakage. `default` statement execution is chronologically gated (`ast.py`), and the game's own `default` count on disk sums to exactly 384 — 349 of them top-level in `characters.rpy` alone, which run unconditionally before any route branches. Expected, not a leak.

### Change: snapshot capture/restore moved from manual deepcopy to pickle blobs

The deepcopy-based isolation fix below (jump-back snapshots corrupted by shared live store references) enumerated `roots` and `context` as the two things needing a defensive copy. A follow-up design pass found this approach doesn't generalize: `context` carries other live-referenced fields (`scene_lists`, `music`, `movie`, `dynamic_stack`) that a shallow `rollback_copy()` + targeted deepcopy doesn't fully insulate from later mutation, and each new field found this way would need its own manual case.

Replaced with `renpy.compat.pickle.dumps((roots, ctx))` — the identical serialization `renpy.loadsave.save()` uses for every real save (`dump((roots, renpy.game.log), logf)`). A snapshot is now `{"blob": bytes}`; isolation from live mutation is structural (bytes can't alias anything) rather than a manually-maintained list of fields to copy.

- **`backend/tl_snapshot_cache.rpy`** — `_tl_capture_snapshot()` rewritten to return `{"blob": pickle.dumps((get_roots(), ctx))}`, dropping both `copy.deepcopy` calls. Shared tail logic (building the synthetic `Rollback`/`RollbackLog` and calling `unfreeze()`) extracted into `_tl_build_and_unfreeze(roots, ctx, log_prefix)`. The original deepcopy-based logic is preserved as `_tl_unfreeze_legacy(snap)` for snapshots cached inside saves made under the older mod version — every menu/chapter revisit naturally replaces the cache entry with the new blob shape, so this path only serves stale, not-yet-revisited nodes. `_tl_unfreeze_from_snapshot(snap)` now dispatches on shape: `"blob"` present → decode and go; absent → `_tl_unfreeze_legacy`.
- **`backend/tl_saveload.rpy`** — `_valid_snap()` updated to accept both the blob shape and the legacy `roots`/`context` shape.
- **`timeline_hooks.rpy`** — the two debug-logging call sites that read `snap["roots"]`/`snap["context"]` directly (menu and chapter snapshot capture logging) now decode the blob via `renpy.compat.pickle.loads()` first.
- **`timeline_tests.rpy`** — `_tl_test_snapshot_capture_isolation` rewritten around the blob shape (decode, mutate live store, re-decode, assert unaffected). Added `_tl_test_capture_snapshot_blob_contract`, `_tl_test_unfreeze_blob_path`, `_tl_test_unfreeze_blob_repeat_isolation`, `_tl_test_unfreeze_legacy_direct`, `_tl_test_unfreeze_dispatch_routes_by_shape`, `_tl_test_valid_snap_shapes`, `_tl_test_snapshot_cache_mixed_shapes` — written before the implementation per the project's test-first rule, pinning the exact new/legacy contract and the dispatcher's shape-routing behavior.
- Verified against Ren'Py source rather than the mod's own prior behavior: `Context.rollback_copy()` (`execution.py`) unconditionally forces `interacting = False` on every copy, and ordinary gameplay already pickles `rollback_copy()`'d `Context` objects constantly via `Rollback.__init__` (every checkpoint, including mid-menu) — confirming pickling `ctx` here is exactly what Ren'Py already does for every real save, not a new risk.

### Fix: jump-back snapshots corrupted by shared live store references

`_tl_unfreeze_from_snapshot` deep-copied `snap["context"]` but passed `snap["roots"]` straight through unmodified. Real Ren'Py's `RollbackLog.unfreeze()` installs roots values directly into `store_dicts` (`store[name] = value`, no copy), so after a jump, any store variable mutated in place (`dict[key] = x`, `list.append(x)`, rather than reassignment) was mutating the exact same object still referenced by the cached snapshot. A second jump back to the same menu node would then silently pick up the later mutation instead of the node's true historical state. Reproduced live: a store dict jumped to once, mutated in place, then jumped to again returned the post-mutation value instead of the value at capture time.

- **`backend/tl_snapshot_cache.rpy`** — `_tl_unfreeze_from_snapshot` now deep-copies `snap["roots"]` before handing it to `unfreeze()`, same treatment `ctx` already received. Falls back to the original (uncopied) roots on deepcopy failure, matching the existing ctx fallback pattern.
- **`timeline_tests.rpy`** — added `_tl_test_snapshot_roots_isolation`, mirroring `_tl_test_snapshot_ctx_isolation`: intercepts the real `_tl_unfreeze_from_snapshot` call via a mocked `RollbackLog.unfreeze` and asserts the roots handed to it are a distinct object from `snap["roots"]`, and that mutating one doesn't affect the other. `_tl_test_snapshot_ctx_isolation` itself was then rewritten to use the same mocked-unfreeze pattern (calling the real `_tl_unfreeze_from_snapshot` twice and comparing the two captured `context` copies) instead of re-implementing `copy.deepcopy` inline — the previous version never exercised the real function, so it wouldn't have caught a regression in its ctx-copy logic.

A follow-up audit against real Ren'Py source found the same bug class on the other end of the pipeline: `_tl_capture_snapshot()` stored `snap["roots"] = renpy.game.log.get_roots()` directly — `get_roots()` (per `rollback.py`) also returns live references into `store_dicts`, not copies. So a cached snapshot's roots could be silently corrupted by *ordinary forward gameplay* mutating a store var in place, with no jump involved at all — the unfreeze-side fix above only protected reuse *after* a jump, not the cache's baseline integrity.

- **`backend/tl_snapshot_cache.rpy`** — `_tl_capture_snapshot()` now deep-copies `renpy.game.log.get_roots()` before storing it in `snap["roots"]`, same fallback-on-failure pattern as the unfreeze-side fix.
- **`timeline_tests.rpy`** — added `_tl_test_snapshot_capture_isolation`: sets a throwaway store var, forces a rollback checkpoint cycle (`renpy.game.log.complete(True)`, needed because `get_roots()` only sees vars in `ever_been_changed`, which a plain `complete(False)` flush doesn't update), captures a real snapshot, mutates the live var in place afterward, and asserts the cached copy is unaffected.
- Snapshots cached inside saves made *before* this fix are not retroactively repaired — the corrupted value (if any) was already overwritten in place before it could be captured correctly, so there is no original value left to recover. Not addressed further per explicit decision to only fix forward-going captures.

### Fix: unseen-option dots and ghost seen state broken on Ren'Py 7 translated games

In Ren'Py 7, Say nodes inside menu option blocks (and after Scene/Jump targets) are wrapped in `Translate` AST nodes. `_tl_make_seen_fn`, `_tl_find_scene_seen_name`, and `_tl_follow_jump_seen_name` only checked for `"Say"` and `"TranslateSay"`, so all dialogue was silently skipped — leaving only Show/Scene image descriptors, which are shared across branches and always evaluate as seen after the first playthrough.

- **`backend/tl_seen_check.rpy`** — all three node-walking functions now handle `"Translate"` by diving into `node.block` and extracting the `Say` inside, then calling `_tl_say_seen_name` as normal.

### Fix: ghost clusters always merged with previous cluster

`_tl_on_if_execute` was checking the last emitted ghost node and merging new clusters with it via `_tl_should_cluster`. This caused unrelated sequential ifs to visually group together incorrectly. Each cluster is now emitted independently with `cluster_with_prev=False`.

- **`backend/tl_ghost_logic.rpy`** — removed `prev_ghost` inter-run merge logic from `_tl_on_if_execute`; `_tl_emit_ghost_cluster` is always called with `False`.

### Fix: init-phase crash and incorrect runtime filtering in execute patches

Both `_tl_if_execute_patched` and `_tl_python_execute_patched` were being called during Ren'Py's init phase (e.g. `init -1 python:` blocks in game scripts), before store defaults are applied. This caused a `TypeError` in `_tl_py_pre_var_snap` when `_tl_route_var_names` was not yet initialized.

- **`backend/tl_ghost_logic.rpy`** — `_tl_if_execute_patched`: bail out via `renpy.is_init_phase()` before any state access; combined with existing `_tl_is_game_file` check into a single early return.
- **`backend/tl_route_logic.rpy`** — `_tl_python_execute_patched`: same guard; removed `not route_names` early return from `_tl_py_pre_var_snap` (unreachable now that init phase is blocked at the wrapper); removed temp diagnostic log.

### Fix: ghost cards never appeared; remove dead `_tl_branch_id`

`_tl_branch_id` was declared as `default _tl_branch_id = ""` and never assigned a non-empty value. All three gate guards that checked it (`_tl_on_if_execute`, `_tl_on_screen_navigate`, `_tl_py_pre_var_snap`) therefore always returned early, permanently suppressing ghost cards and var-change notifications.

- **`backend/tl_ghost_logic.rpy`** — removed `_tl_branch_id` check from `_tl_on_if_execute` and `_tl_on_screen_navigate` gates; remaining guards (`_tl_replaying`, `config.skipping`) are sufficient.
- **`backend/tl_route_logic.rpy`** — removed `_tl_branch_id` check from `_tl_py_pre_var_snap` gate.
- **`timeline_init.rpy`** — deleted `default _tl_branch_id = ""`.
- **`timeline_hooks.rpy`** — removed from `global` declaration in `_tl_record_before`.
- **`ui/tl_debug.rpy`** — removed branch_id debug row.
- **`timeline_tests.rpy`** — removed stale `_tl_branch_id` store-default check and state-guard entries; added `_tl_test_ghost_gate_guards` and `_tl_test_ghost_on_if_execute` in-game tests.
- **`tests/test_route_logic.py`** — removed `_tl_branch_id` setup/teardown from var-hook test fixture.

### Refactor: backend quality pass — Round 2

Readability cleanup across all remaining backend files — no logic changes.

- **`backend/tl_ghost_logic.rpy`** — fixed banner; deleted dead `_tl_resolve_cluster_imgs` (zero callsites); fixed 3 bare `except: pass` → log; de-aliased `import ast as _ast` in two function-local scopes; renamed underscored locals throughout all functions.
- **`backend/tl_route_logic.rpy`** — de-aliased `import ast as _pyast` in two function-local scopes; renamed underscored locals throughout all functions; kept `_cache=[None, None]` mutable default arg (intentional session-persistent idiom).
- **`backend/tl_seen_check.rpy`** — fixed 5 bare `except` blocks → log; renamed underscored locals throughout.
- **`backend/tl_ast_utils.rpy`** — renamed underscored locals in `_tl_extract_compare_literals` and `_tl_walk_ast_blocks`.
- **`backend/tl_chapter.rpy`** — fixed bare `except: return {}` → log+return; renamed `_f`, `_ch_name`, `_ch_label`.
- **`backend/tl_menu_location.rpy`** — fixed bare `except: pass` → log; collapsed `_tl_derive_node_menu_site_key` into `_tl_node_menu_site_key` (deleted redundant one-liner wrapper); renamed underscored locals; updated `timeline_tests.rpy` callsite.
- **`backend/tl_coverage.rpy`** — renamed inner function `_tl_cov_visitor → visitor`; renamed underscored locals.
- **`backend/tl_assets.rpy`** — fixed banner; fixed 3 bare `except` blocks → log; de-aliased `import tempfile as _tf` and `import pygame as _pg` (function-local); renamed underscored locals throughout all functions.

### Refactor: 80/20 code quality pass across core files

Readability and maintainability cleanup — no logic changes.

- **`backend/tl_shadow_path.rpy`** — extracted `_entry_key(entry)` helper (de-duplicated backward-compat list→tuple coercion); moved match/no-match log statements into `_tl_consume_shadow_path` so all shadow diagnostics are co-located; renamed `orig_ci → orig_chosen`, `new_sp → remaining`.
- **`backend/tl_snapshot_cache.rpy`** — renamed local vars (`_cache → cache`, `_old → old_cache`, `_ie → e`, `_copy → copy`); trimmed `_tl_capture_snapshot` docstring to essential contract + mutation risks; converted `## comments → # comments` inside functions.
- **`backend/tl_saveload.rpy`** — renamed underscored locals throughout (`_iface → iface`, `_renpy_major → renpy_major`, `h6 → slot_hash`, `_os → os`, `_root → root`, `_ext → ext`, `_slot → slot`).
- **`timeline_init.rpy`** — extracted `_tl_load_thumb_dict(path)` from nested gzip/raw try-except block; renamed underscored locals in `_tl_log`, `_tl_runtime_cache_store`, `_tl_runtime_choice_returns`, `_tl_count_locked_branches`, `_tl_save_thumbs`; cleaned up module-level thumbnail init block.
- **`backend/tl_menu_options.rpy`** — extracted `_tl_parse_menu_items(items)` from `_tl_record_before`; owns all raw menu item parsing alongside existing filtering/indexing helpers.
- **`timeline_hooks.rpy`** — extracted `_tl_resolve_node_location()`, `_tl_resolve_img_name()`, `_tl_capture_thumb()` from `_tl_record_before`; extracted `_tl_replay_pick()` from `_tl_store_wrapper`; removed dead commented-out branch ID block; fixed bare `except: pass` → log; removed duplicate shadow path log statements from wrapper (now live in `_tl_consume_shadow_path`); simplified shadow block; renamed locals throughout.
- **`timeline_tests.rpy`** — added `_TLFakeChoice` module-level stub (replaces 4 local `FakeCR`/`FakeChoiceReturn` class definitions); added `_TLStateGuard` context manager (replaces manual save/restore boilerplate in `_tl_test_record_pipeline`, `_tl_test_locked_options`, `_tl_test_option_filtering`).

### Fix: "Cannot start an interaction" error on second jump to same menu

After a snapshot-based jump, Ren'Py sets the live game context to the `rb.context` object assigned during unfreeze. As gameplay continues, `rb.context.interacting` is set to `True`. Since the old code assigned `snap["context"]` directly to `rb.context` (no copy), the snapshot's context object was the same reference as the live context — it accumulated the `interacting=True` mutation and got pickled into any save made post-jump. On the next jump from such a save, `_tl_unfreeze_from_snapshot` would read `ctx.interacting=True` and pass it into the new Rollback entry, causing Ren'Py to raise "Cannot start an interaction in the middle of an interaction" during `unfreeze()`.

`rollback_copy()` already sets `rv.interacting = False`, but that only applies at capture time. The mutation window is between unfreeze and the next jump.

Fix: in `_tl_unfreeze_from_snapshot`, deepcopy `snap["context"]` before assigning it to `rb.context`. Each unfreeze gets an isolated copy; Ren'Py mutates the copy, not the snapshot. Additionally, `ctx.interacting = False` is set unconditionally after the copy to heal snapshots from old saves that were already corrupted.

- **`backend/tl_snapshot_cache.rpy`** — `_tl_unfreeze_from_snapshot`: deepcopy ctx from snap with `interacting=False` reset; added `_tl_test_snapshot_ctx_isolation` in-game test.
- **`timeline_tests.rpy`** — updated `_TLFakeCtx` with `interacting=False`; updated `_tl_test_unfreeze_builds_rollback_log` assertion (`rb.context is not fake_ctx`); added `_tl_test_snapshot_ctx_isolation`.

### Fix: stale overlay screens after snapshot-based jump break T key and quick_menu

After a snapshot-based jump, `before_restart()` (called inside `unfreeze()`) marks the live overlay ScreenDisplayables as `restarting=True` and leaves them with `phase=OLD`. These stale objects end up in the checkpoint context that gets baked into any save made during the post-jump session. When that save is loaded, `show_overlay_screens` finds the stale objects via `get_screen()` and skips `show_screen()`, leaving broken screens in place — `event()` silently drops all input and `_render()` returns empty.

Fix: in `_tl_on_load`, when `persistent._tl_synthetic_jump` is True (i.e. we just landed from a snapshot unfreeze), immediately hide all `config.overlay_screens` with `immediately=True` before the first interaction. `show_overlay_screens` then finds an empty overlay and creates fresh, functional ScreenDisplayables.

- **`timeline_hooks.rpy`** — `_tl_on_load`: added overlay hide loop under `is_synthetic` guard.
- **`timeline_init.rpy`** — removed `_tl_diff_saves` diagnostic helper and its call site (added during investigation).

### Cleanup: remove v1 save/jump system — snapshot-primary architecture only

- **`backend/tl_saveload.rpy`** — deleted entirely. All v1 public APIs (`_tl_begin_jump`, `_tl_begin_label_jump`, `_tl_synthetic_jump`, `_tl_cancel_replay`, `_tl_find_nearest_save`, `_tl_find_nearest_pre_save`, `_tl_find_nearest_any_save`, `_tl_path_has_danger`, `_tl_write_pre_save`, `_tl_should_save`) are gone. Slot-naming helpers (`_tl_save_slot`, `_tl_pre_save_slot`, `_tl_find_pre_save`, `_tl_save_no_screenshot`) are kept in `tl_saveload.rpy` as backward-compat disk-read infrastructure.
- **`timeline_hooks.rpy`** — removed both `TL_WRITE_PRE_SAVES`-guarded blocks: the pre-menu save write in `_tl_record_before` and the chapter-end save write in the chapter-end hook. The only disk write remaining is the recovery save in `_write_recovery()`.
- **`timeline_init.rpy`** — removed `TL_WRITE_PRE_SAVES`, `TL_SAVE_EVERY`, and `TL_DENSE_SAVES` constants. Removed `_tl_pending_shadow_path` persistent init guard (shadow transport now via `persistent._tl_replay_path` entries).
- **`timeline_save_hooks.rpy`** — removed `_tl_pending_shadow_path` validation from `_tl_validate_on_load`.
- **`tests/conftest.py`** — removed `_tl_pending_shadow_path` from persistent stub.
- **`tests/test_saveload.py`** — deleted 7 skipped v1-only test classes (`TestFindNearestSave`, `TestContextAccumulation`, `TestFindNearestSaveDensePattern`, `TestFindNearestPreSave`, `TestFindNearestPreSaveHistoryFirst`, `TestFindNearestAnySave`, `TestPathHasDanger`) and `TestSaveDecision`. Removed dead imports and `make_save_files` helper. All remaining classes pull from `_rpy_ns` directly. 53 tests pass.
- **`tests/test_shadow_path.py`** — deleted 3 skipped v1-only test classes (`TestBuildShadowPath`, `TestStageShadowPath`, `TestConsumeShadowPath`).
- **`timeline_tests.rpy`** — deleted 9 v1 in-game test functions (`_tl_test_label_jump_rollback`, `_tl_test_shadow_path_set_on_jump`, `_tl_test_shadow_path_empty_after_last_node`, `_tl_test_cancel_replay`, `_tl_test_pre_save_written`, `_tl_test_read_pre_save_roots`, `_tl_test_synthetic_jump_staging`, `_tl_test_chapter_jump_staging_synthetic`, `_tl_test_begin_jump_returns_snapshot_sentinel`) and their registry calls in `_tl_run_tests()`.
- **Why**: v2 snapshot-primary architecture has been live-verified across all 3 jump paths. No pre-saves are written in new sessions. v1 checkpoint-save and pre-save write paths are dead code. Removing them reduces the codebase by ~900 lines and eliminates the dual-system maintenance burden.

### Feat: snapshot-primary jump system (tl_saveload_v2) + shadow path redesign

- **`backend/tl_saveload.rpy`** — unified jump entry point `_tl_jump(node_index, option_index, chapter_label)` for both menu and chapter jumps. Snapshot is primary; disk saves are backward-compat fallback only. Jump flow: write recovery save → stage `persistent._tl_replay_path` + `_tl_replay_target` → look up snapshot → if valid, call `_dispatch_snap`; else fall back to `_find_slot` or chapter-end slot. `_tl_cancel_jump()` replaces `_tl_cancel_replay`. `_find_slot` walks history downward from the target (Tier 1: exact pre-save at target; Tier 2: closest pre-save, `_ch_*` checkpoint, or chapter-end marker; Tier 3: `_ch_start`).
- **`backend/tl_snapshot_cache.rpy`** — new file. `_tl_capture_snapshot()` calls `renpy.game.log.complete(False)` to flush pending store deltas, takes a `rollback_copy()` of the current context, deep-copies `ctx.info` (scene/music display state), and records `renpy.game.log.get_roots()` — the full Python object graph for rollback. Snapshots are stored on `renpy.game.log._tl_snapshot_cache` (keyed by `node_index` for menus, `label_name` for chapters), which puts them outside the store and therefore outside RenPy's `get_roots()` cycle. `_tl_unfreeze_from_snapshot()` builds a synthetic single-entry `RollbackLog` from the snapshot's roots and context, copies the cache to the new log, then calls `unfreeze()` to atomically replace the live game state — effectively teleporting the engine to the exact point of capture without replaying any script. `ctx.current` is patched to an enclosing label name when needed so `RollbackLog.rollback()` stops correctly at the synthetic entry in compiled `.rpyc` files.
- **`backend/tl_shadow_path.rpy`** — removed `_tl_build_shadow_path`, `_tl_stage_shadow_path`, `_tl_shadow_match_mode`. `_tl_consume_shadow_path` returns a 3-tuple `(new_path, diverged_ci, match_mode)` and matches on `ast_key` with a list→tuple coercion shim for old entries.
- **`timeline_hooks.rpy`** — `_tl_on_load` reconstructs `store._tl_shadow_path` from `persistent._tl_replay_path`: for menu jumps (`replaying=True`), entries after `target_index` become the shadow; for chapter jumps (`replaying=False`, `replay_target=None`), all entries are used as shadow and `replay_path` is cleared. Snapshot capture added to `_tl_record_before` (menu) and the chapter-end hook. `_tl_store_wrapper` unpacks the new 3-tuple from `_tl_consume_shadow_path`.
- **`ui/tl_modal.rpy`** — `Function(_tl_begin_jump, ...)` → `Function(_tl_jump, ...)`.
- **`timeline_screen.rpy`** — `Function(_tl_begin_label_jump, end_label)` → `Function(_tl_jump, chapter_label=end_label)`; `Function(_tl_cancel_replay)` → `Function(_tl_cancel_jump)`.
- **`tests/test_saveload.py`** — added `TestFindSlot` (8 tests covering all `_find_slot` tiers), `TestFindPreSave`, and `TestPreSaveSlot`.
- **`tests/test_shadow_path.py`** — added `TestShadowMatch` and `TestConsumeShadowPathV2` (3-tuple API, ast_key matching, list→tuple bw-compat).
- **`timeline_tests.rpy`** — added `_tl_test_jump_staging`, `_tl_test_jump_empty_shadow`, `_tl_test_cancel_jump`, `_tl_test_jump_chapter_staging`, `_tl_test_jump_uses_pre_save`.
- **Why**: snapshots stored in `_tl_history` nodes caused a self-referential `get_roots()` cycle (every snapshot's roots included `store._tl_history`, which included all prior snapshots), making save files grow O(N²). Moving snapshots to `renpy.game.log` breaks the cycle entirely. `_tl_unfreeze_from_snapshot` eliminates the replay wait: instead of loading a pre-save and fast-forwarding through all menus to the target, the engine is restored instantly to the exact captured state. The unified `_tl_jump` entry point eliminates the v1 two-function split and the `_tl_synthetic_jump` indirection layer.

### Perf: _tl_find_nearest_pre_save — history-first lookup, O(N) with early exit

- **`backend/tl_saveload.rpy`** — when `history` is provided, the function now sorts history descending by index and checks `os.path.exists` for each entry's expected slot name, breaking on first hit. Previously it did a full `os.listdir` scan and then linear-searched history for each file's ast_key: O(disk_files × history_length). New approach is O(history_length) with early exit. `history=None` falls back to the original disk scan (used by `_tl_thin_pre_saves`).

### Fix: jump tier preference — compete pre-saves and _ch_* saves by index

- **`backend/tl_saveload.rpy`** — added `_tl_find_nearest_any_save(target_index, context, history, chap_candidates)` that runs both `_tl_find_nearest_pre_save` and `_tl_find_nearest_save` and picks whichever returned the higher index. Both finders now accept `_meta=None`; when provided, they populate `_meta["index"]` with the winning slot's index so the caller can compare across pools. Chapter-end saves (slot names not index-parseable) are handled correctly since `_tl_find_nearest_save` tracks their index internally. Tiers 2 and 3 in `_tl_begin_jump` collapsed into a single Tier 2 call to `_tl_find_nearest_any_save`.
- **Why**: previously any pre-save beat any `_ch_*` save regardless of proximity. Playthroughs that only have `_ch_*` checkpoints (pre-update saves) would load a distant pre-save instead of a closer `_ch_*` save, causing unnecessarily long replay.

### Perf: move ghost node AST fields to persistent cache — reduces rollback log bloat

- **`backend/tl_ghost_logic.rpy`** — added `_tl_ghost_ast(ast_key)` helper that reads from `persistent._tl_ghost_node_cache`. Modified `_tl_emit_ghost_cluster` to split the appended dict: AST-derived fields (`conditions`, `seen_fns`, `affecting_vars`, `_regions`) are written to `persistent._tl_ghost_node_cache[str(ast_key)]` once (with invalidation check); `store._tl_ghost_nodes` now appends a slim dict with only 4 runtime fields (`ast_key`, `taken_index`, `branch_imgs`, `cluster_with_prev`). Dropped `type` ("branch" constant) and `member_ast_keys` (logging only) from the store dict entirely.
- **`timeline_init.rpy`** — added `persistent._tl_ghost_node_cache = {}` init guard.
- **`ui/tl_ghost_cards.rpy`** — `screen tl_ghost_card` pre-fetches AST data via `_tl_ghost_ast(ghost["ast_key"])`; reads `seen_fns` and `conditions` from cache. `screen tl_ghost_rows` uses `_tl_ghost_ast()` for branch count instead of `ghost["conditions"]`.
- **`ui/tl_route_screen.rpy`** — `affecting_vars` lookup uses `_tl_ghost_ast(_g["ast_key"])` instead of `_g.get("affecting_vars")`.
- **`tests/test_ghost_logic.py`** — added `TestGhostNodeCache` (4 tests).
- **`tests/conftest.py`** — added `_tl_ghost_node_cache={}` to persistent stub.
- **Why**: each `If.execute` append to `_tl_ghost_nodes` caused RenPy's rollback to snapshot the full list (O(N²) log growth, ~200 KB per inter-menu segment with 20 ghost nodes). AST-derived fields are static — same data every execution — so they belong in persistent, not the rollback log.

### Cleanup: log audit — remove performance instrumentation, guard verbose logs behind debug flags

- **`backend/tl_ghost_logic.rpy`** — removed `_if_execute slow` timing block (performance instrumentation). Verbose clustering and emit details already guarded by `TL_DEBUG_GHOST`.
- **`backend/tl_route_logic.rpy`** — moved `TL default skip: bytecode=None` and `TL default skip: eval error` behind `TL_DEBUG_ROUTE`. Summary walk log stays always-on.
- **`backend/tl_saveload.rpy`** — removed `check=`, `save=`, `total=` timing fields from `TL pre-save` log; removed `check=` timing field from `TL pre-save skip (exists)`.
- **`timeline_hooks.rpy`** — removed the `TL record_before` block (pre-save timing and seen_fn stats instrumentation). Moved `TL img_name` and `TL movie thumb fallback` behind `TL_DEBUG_MENU`.
- **`timeline_init.rpy`** — added `TL_DEBUG_MENU` and `TL_DEBUG_ASSET` flag constants alongside existing `TL_DEBUG_GHOST`, `TL_DEBUG_SEEN`, `TL_DEBUG_ROUTE`.
- **`backend/tl_assets.rpy`** — removed `TL_LOG_ASSET_THUMB_HITS` local constant; moved asset thumb hit/generated, scene img fallback attr, ast-walk miss, and menu_scene_map cache stats behind `TL_DEBUG_ASSET`.

### Perf: cache seen_fn descriptors in ghost card pipeline

- **`backend/tl_ghost_logic.rpy`** — added `_TL_SEEN_FN_CACHE` (module-level dict, outside rollback and save systems) and `_tl_make_seen_fn_cached` wrapper. Keyed by `_tl_builtin_id(branch_block)` — RenPy AST branch block objects are stable Python objects for the session lifetime, making `id()` a safe, permanent key.
- Replaced both `_tl_make_seen_fn(_blk)` call sites (line 323 in `_tl_build_ghost_payload`, line 571 in `_tl_if_execute_patched`) with the cached version.
- In sandbox games, the same If nodes fire repeatedly as the player navigates between locations. Without caching, each firing redoes the full AST walk (up to 30–80 `.next` hops + translator lookups) for every branch. With caching, subsequent firings of the same If node are a single dict lookup.

### Fix: _tl_cancel_replay was still writing to persistent._tl_thumb_cache

- **`backend/tl_saveload.rpy`** (`_tl_cancel_replay`) — thumbnail snapshot before recovery load now writes to `renpy.game._tl_thumb_cache` instead of `persistent._tl_thumb_cache`. This was the last remaining call site missed when migrating the cache. Also removed the stray `renpy.save_persistent()` call that followed (no longer needed — cache is not in persistent).

### Perf: move thumbnail caches out of persistent — fixes save_persistent() latency

- **`timeline_init.rpy`** — thumbnail caches (`_tl_thumb_cache`, `_tl_asset_thumb_cache`) moved from `persistent` to `renpy.game` module attributes. `renpy.game` is a Python module object whose attrs survive `renpy.load()` but are never serialised by `save_persistent()`. Caches are loaded from `_tl_thumbs.pkl` in the save dir at game start and written back at quit via `config.quit_callbacks`. One-time migration drains any existing persistent blobs into the new location.
- **`timeline_init.rpy`** — `_tl_thumbs.pkl` is written and read with gzip compression. Legacy uncompressed files are detected via `gzip.BadGzipFile` fallback and rewritten compressed at next quit. Reduces on-disk size from ~78 MB to ~44 MB.
- **`backend/tl_assets.rpy`** — `_tl_get_asset_thumb_bytes`, `_tl_node_thumb`, `_tl_clear_thumb_cache` updated to read/write `renpy.game._tl_asset_thumb_cache` / `renpy.game._tl_thumb_cache`.
- **`timeline_hooks.rpy`** — `_tl_record_before` updated to use `renpy.game._tl_thumb_cache`.
- **`tests/conftest.py`** — added `quit_callbacks=[]` to config stub.
- **Verified result**: persistent < 1 MB; `save_persistent()` ~109–127 ms (was ~1444 ms); full jump round-trip ~300 ms (was ~3 s); load timing ~53 ms.

### Perf: reduce jump and load latency

- **`backend/tl_saveload.rpy`** (`_tl_save_no_screenshot`) — restored `mutate_flag=False` on RenPy 8+. This was present in the original `_tl_write_pre_save` but accidentally dropped when extracting the helper. Without it, RenPy calls `location.scan()` (`os.listdir()` on the full save dir) after every `renpy.save()`. Applies to all mod-internal saves: pre-saves, `_ch_recovery`, `_ch_start`, chapter-end saves.
- **`timeline_hooks.rpy`** (`_tl_on_load`) — skip `_tl_migrate_img_names()` on replay loads. Pre-saves are written this session after AST is ready, so all history nodes already have `img_name` set. The O(history) migration walk was a no-op on every jump load.

### Fix: strip screenshots from all mod-internal saves (RenPy 7+8)

- **`backend/tl_saveload.rpy`** — new `_tl_save_no_screenshot(slot)` helper: uses `include_screenshot=False` on RenPy 8+; shadows `interface.get_screenshot` with a 1×1 black PNG on RenPy 7. Applied to `_ch_recovery` (×2), pre-saves via `_tl_write_pre_save`, and is the canonical save path for all mod-internal slots.
- **`timeline_hooks.rpy`** — `_ch_start` (×3) and `_chap_slot` chapter-end saves now use `_tl_save_no_screenshot`. Mod-internal saves never appear in the player's save UI so screenshots are pure waste (~153 KB per save).
- **`backend/tl_saveload.rpy`** (`_tl_write_pre_save`) — inline RenPy 7/8 version branch replaced with `_tl_save_no_screenshot` call; no behavior change.

### Fix: pre-save hash consistency — scan uses `_tl_pre_save_slot` directly

- **`backend/tl_saveload.rpy`** (`_tl_find_nearest_pre_save`) — replaced inline hash computation with a call to `_tl_pre_save_slot(_idx, context, _ast_key)`. Eliminates duplicate hash formula; write and scan are now guaranteed to agree even if the formula changes.
- **`tests/test_saveload.py`** — added 9 tests covering `ast_key` in `TestPreSaveSlot`, `TestFindPreSave`, and `TestFindNearestPreSave` (including history-based ast_key lookup path).

### Fix: clear ghost nodes on screen-navigate statements for sandbox location navigation

- **`backend/tl_ghost_logic.rpy`** — `_tl_on_call_screen` renamed to `_tl_on_screen_navigate` and expanded to handle both `"call screen"` and `"show screen"` statement types. Covers sandbox games that navigate via `call screen locN_*` (IC style) and those that navigate via `show screen locN` (PhotoHunt style). `renpy.show_screen()` called from Python does not fire `config.statement_callbacks`, so mod-internal notify calls are unaffected.
- **`tests/conftest.py`** — added `statement_callbacks=[]` to the config stub.

### Cleanup: remove TL_PROFILE_TIMELINE profiling system and _tl_save_space_report

- **`timeline_init.rpy`** — removed `TL_PROFILE_TIMELINE` flag, `_tl_timeline_perf_stats` dict, and `_tl_perf_mark` / `_tl_perf_add` / `_tl_perf_reset` / `_tl_perf_dump` helpers. The system was added to diagnose timeline screen open latency; the root cause (structural scene-dot path) was fixed by local dot mode. Dead code since then.
- **`timeline_init.rpy`** — removed `_tl_save_space_report()` and its call in `_tl_build_ast_map`. Was a console diagnostic for save file size breakdown; no longer needed.
- **`timeline_screen.rpy`** — removed `_tl_perf_reset`, `_tl_perf_mark`, `_tl_perf_add`, `_tl_perf_dump` call sites (3 instrumented blocks + final dump).
- **`backend/tl_assets.rpy`** — removed `_tl_perf_mark` / `_tl_perf_add` call sites from `_tl_img_thumb_displayable`; simplified function body (removed try/finally wrapper).

### Refactor: Python.execute dispatcher

- **`backend/tl_ast_utils.rpy`** — single `Python.execute` monkeypatch. Defines `_tl_python_execute_hooks` (list of `(pre_fn|None, post_fn|None)` tuples) and `_tl_python_execute_dispatch` which calls all pre-hooks, executes the original, then calls all post-hooks. Error handling lives in the dispatcher so individual hooks don't need try/except.
- **`backend/tl_route_logic.rpy`** — direct `Python.execute` monkeypatch restored (dispatcher removed — only one consumer). Logic split into `_tl_py_pre_var_snap` (guards + co_names snapshot) and `_tl_py_post_var_diff` (diffs snap, updates pending var changes); `_tl_python_execute_patched` wraps both and replaces `Python.execute` directly.
- **`backend/tl_ast_utils.rpy`** — removed `_tl_python_execute_hooks` dispatcher (no longer needed).
- **`tests/test_route_logic.py`** — `_run_var_hooks` helper updated: `_tl_py_post_var_diff` signature now takes only `snap` (no `node` arg).

### Revert: NoRollback containers for ghost node accumulators — breaks rollback semantics

- **`timeline_init.rpy`** — removed `_TlNoRollbackList`/`_TlNoRollbackSet` classes; `default _tl_ghost_nodes` and `default _tl_skip_ghost_ifs` reverted to `[]` / `set()`. NoRollback containers prevent ghost nodes from rolling back with game state — causing duplicate cards in IC (Ctrl+Z past a menu leaves stale ghost nodes) and wrong-location display in PhotoHunt (ghost nodes from loc N appear at loc N+1 because location navigation rolls back but ghost nodes don't). Same failure mode as the previously reverted `_TlNoSaveList`/`_TlNoSaveSet` attempt.
- **`timeline_hooks.rpy`** (`_tl_record_before`) — back to `store._tl_ghost_nodes = []` / `store._tl_skip_ghost_ifs = set()`.
- **`timeline_hooks.rpy`** (`_tl_on_load`) — removed the NoRollback reset block (no longer needed).
- **`timeline_tests.rpy`** — removed `_tl_test_no_rollback_containers` (tested the now-reverted approach).

### Fix: NoRollback containers for ghost node accumulators; foreground pre-saves; ast_key in pre-save hash

- **`timeline_init.rpy`** — added `_TlNoRollbackList(NoRollback, list)` and `_TlNoRollbackSet(NoRollback, set)` wrapper classes. Changed `default _tl_ghost_nodes` to `_TlNoRollbackList()` and `default _tl_skip_ghost_ifs` to `_TlNoRollbackSet()`. In sandbox games (PhotoHunt-style) with many sequential If nodes, the previous `RevertableList.append()` calls registered mutation deltas in the rollback log for every ghost node — in Python 2, pickling hundreds of chained `mutated` delta entries hits cPickle's ~1000-frame recursion limit and crashes saves. `NoRollback` instances have their `reached()` return immediately, preventing any delta registration.
- **`timeline_hooks.rpy`** (`_tl_record_before`) — ghost node reset now assigns `_TlNoRollbackList()` and `_TlNoRollbackSet()` directly (replaces prior full-list assignment).
- **`timeline_hooks.rpy`** (`_tl_on_load`) — added reset of `_tl_ghost_nodes` and `_tl_skip_ghost_ifs` to their NoRollback types after every load. Required because `default` declarations do not override values restored from saves predating this change — old saves store `RevertableList` for ghost nodes and would reintroduce the mutation-tracking bug.
- **`backend/tl_saveload.rpy`** — reverted pre-save writes from background thread to foreground (synchronous). Background approach introduced skip-mode interaction issues; synchronous writes in `_tl_record_before` (always at a menu, safe pause point) are simpler and have no observable latency at menu transitions. Removed: `_TL_PRESAVE_LOCK_KEY`, `_tl_presave_lock()`, thread spawn, lock wait in `_tl_begin_jump`.
- **`backend/tl_saveload.rpy`** (`_tl_pre_save_slot`) — added `ast_key` parameter to slot hash. Hash input changed from `repr(tuple(context[:N]))` to `repr((tuple(context[:N]), ast_key))`. In sandbox games, different menus can share the same `node_index` but have distinct `(filename, linenumber)` AST identities — without `ast_key` in the hash, `_tl_find_pre_save` could return the wrong save when two menus share a node_index. `_tl_write_pre_save` and `_tl_find_pre_save` both accept `ast_key=None` for backwards compatibility.
- **`backend/tl_saveload.rpy`** (`_tl_write_pre_save`) — RenPy 7 screenshot suppression fixed: `renpy.save()` on RenPy 7 does not accept `include_screenshot=False` (raises `TypeError`). Fix: shadow `renpy.game.interface.get_screenshot` with an instance attribute returning `_TL_EMPTY_PNG` (68-byte 1×1 black PNG) for the duration of the save; restored in `finally` via `del`. RenPy 8 path unchanged (`include_screenshot=False, mutate_flag=False`).
- **`timeline_tests.rpy`** (`_tl_test_no_rollback_containers`) — new in-game test: verifies `_TlNoRollbackList` and `_TlNoRollbackSet` work correctly (len, index, iter, contains, bool) and that `store._tl_ghost_nodes` / `store._tl_skip_ghost_ifs` are the correct NoRollback types after load. Uses `isinstance(obj, renpy.python.NoRollback)` rather than `id`-in-`mutated` (the latter is unreliable due to Python memory address reuse).
- **`timeline_tests.rpy`** (`_tl_test_pre_save_written`) — fixed: now extracts `ast_key` from each history node via `_tl_derive_node_menu_site_key` before calling `_tl_find_pre_save`. Previous version passed `ast_key=None`, computing a different hash than what the actual pre-save files are named with — caused 0/N found even when saves existed on disk.

### Feat: Pre-save cleanup — `_tl_thin_pre_saves` experimental console function

- **`backend/tl_ast_utils.rpy`** — `_tl_walk_ast_blocks` extended with `current_label` as a 3rd visitor argument. Work queue entries changed from `(block, state)` to `(block, state, label_name)`; label name is seeded from each `Label` node's `.name` and propagates unchanged into all `If`/`Menu` sub-blocks. All existing callers updated to accept `_label=None` as the 3rd visitor parameter.
- **`backend/tl_coverage.rpy`**, **`backend/tl_route_logic.rpy`**, **`backend/tl_assets.rpy`** — visitor signatures updated to `(node, state, _label=None)`.
- **`backend/tl_saveload.rpy`** — added `_tl_find_nearest_pre_save(target_index, context, save_dir)`: range scan of `_pre_*` files, hash-verified against `context[:idx]`, returns highest-index matching pre-save ≤ target. `_tl_begin_jump` updated to 3-tier fallback: (1) exact pre-save → zero skip, (2) nearest earlier pre-save → skip from there, (3) `_ch_*` scan. Added `_tl_read_pre_save_roots(slot_name, save_dir)`: opens save ZIP, unpickles `log` entry, returns roots dict without touching game state. Added `_tl_path_has_danger(start_block, roots, label_map, danger_labels)`: forward AST walk evaluating `If` conditions against save roots, returns `True` if a blocking interaction (`renpy.pause`, `renpy.input`, `renpy.call_screen`, `ui.interact`, `imagemap`, `call screen`) is reachable before any `Menu` node. Added `_tl_thin_pre_saves(keep_every=5, dry_run=True, save_dir)`: console-only cleanup function — reads each pre-save's own `store._tl_history`, uses `history[-1]` + `_tl_live_menu_lookup()` to identify the preceding menu, matches chosen option by label to find the AST block, marks the save essential if `_tl_path_has_danger` returns True; non-essential saves deleted (or logged in dry-run). False negatives (essential save deleted) are not OK; false positives (non-essential kept) are OK — conservative fallback on any lookup failure. Also added `_TL_BLOCK_PY` and `_TL_BLOCK_US` pattern lists for blocking-interaction detection.
- **`backend/tl_saveload.rpy`** (`_tl_write_pre_save`) — RenPy 7 compatibility: `renpy.save()` in RenPy 7.x does not accept `include_screenshot=False`. On `TypeError`, temporarily replaces `renpy.game.interface.screenshot` with `_TL_EMPTY_PNG` (a 68-byte 1×1 black PNG) so `get_screenshot()` returns minimal bytes instead of a full thumbnail; restored in `finally`. Screenshot suppression confirmed (67-byte screenshot in ZIP). Log truncation to 1 entry works on both versions; on RenPy 7, save size is dominated by `roots` (store snapshot of all ever-changed vars) rather than rollback entries — irreducible without excluding vars.
- **`timeline_init.rpy`** — added `_tl_save_space_report(save_dir=None)`: logs count, average KB, and total MB per save type (`_pre_*`, `_ch_*`, other) to `debug.txt`; called automatically at end of `_tl_build_ast_map` on every load and game start.
- **`tests/test_saveload.py`** — added `TestFindNearestPreSave` (9 tests) and `TestPathHasDanger` (14 tests).
- **`tests/test_ast_walk.py`** — added `TestWalkAstBlocksCurrentLabel` (4 tests); all existing visitor lambdas updated to accept `_l=None`.
- **`tests/test_route_logic.py`** — visitor lambdas updated to accept `_l=None`.
- **`timeline_tests.rpy`** — added `_tl_test_read_pre_save_roots` and `_tl_test_thin_pre_saves_dry_run` in-game tests. Replaced stale `_tl_test_interact_callback_deferred_save` (tested removed deferred-save behavior) with `_tl_test_interact_callback_var_flush` (tests current flush/discard behavior based on `_tl_var_notifs_enabled` flag).

### Refactor: Remove sparse post-choice checkpoint writes

- **`backend/tl_saveload.rpy`** — `_tl_should_save` and `_tl_save_slot` kept as legacy (existing `_ch_*` saves on disk remain loadable as fallback via `_tl_find_nearest_save`); no new sparse saves are written.
- **`timeline_hooks.rpy`** — checkpoint write block removed from `_tl_interact_callback`; early-save refresh block removed from `_tl_record_before`. `_tl_record_after` no longer sets `_tl_pending_save_index`.
- **`timeline_init.rpy`** — `_tl_pending_save_index` and `_tl_early_save_idx` defaults kept as legacy (referenced by in-game tests and old saves).

### Feat: Pre-menu checkpoint saves — zero-skip jumps

- **`backend/tl_saveload.rpy`** — added `_tl_pre_save_slot(node_index, context)`, `_tl_find_pre_save(node_index, context, save_dir)`, `_tl_write_pre_save(node_index, context)`. Pre-saves are stripped (no screenshot, 1 rollback entry, ~35–55 KB) and written before each menu fires. `_tl_begin_jump` checks for a pre-save first; if found, loads it directly (zero skip) — the existing `_tl_store_wrapper` auto-select intercept fires immediately on the menu. All mod saves use flat slot names in the root savedir (`_pre_*`, `_ch_*`, `_ch_chap_*`, `_ch_recovery`, `_ch_start`).
- **`timeline_hooks.rpy`** — `_tl_record_before` calls `_tl_write_pre_save` (guarded by `not _tl_replaying`) after clearing ghost/skip state and before early-save refresh. Skip guard removed so pre-saves are written during skip mode (players skip known content but still want to jump to it).
- **`timeline_init.rpy`** — removed `_tl_analyze_saves()` diagnostic block (temporary).
- **`tests/test_saveload.py`** — added `TestPreSaveSlot` (9 tests) and `TestFindPreSave` (6 tests).
- **`timeline_tests.rpy`** — added `_tl_test_log_truncation`, `_tl_test_pre_save_slot_format`, `_tl_test_pre_save_written` in-game tests.

### Refactor: `tl_ast_walk.rpy` renamed to `tl_ast_utils.rpy`; `_tl_strip_renpy_tags` moved there

- **`backend/tl_ast_utils.rpy`** (renamed from `tl_ast_walk.rpy`) — name better reflects its role as a shared utility module.
- **`backend/tl_ast_utils.rpy`** — `_tl_strip_renpy_tags` moved here from `timeline_init.rpy`; inline `import re` replaced with module-level `import re as _tl_re_util`. Used by both `tl_ghost_logic.rpy` and `tl_route_logic.rpy` — now lives in the file that loads first.
- **`timeline_init.rpy`** — `_tl_strip_renpy_tags` definition removed.

### Refactor: Stateful unified AST walk — `_tl_walk_ast_blocks` gains state threading; `_walk_menu_imgs` replaced by `_tl_build_menu_scene_index`

- **`backend/tl_ast_utils.rpy`** — `_tl_walk_ast_blocks` signature changed from `(nodes, visitor_fn)` to `(nodes, visitor_fn, initial_state=None)`. Worklist entries are now `(block, state)` tuples; visitor contract changed from `visitor_fn(node)` to `visitor_fn(node, state) → new_state`. State is threaded sequentially through each block; child blocks (If entries, Menu option blocks) inherit the state at the branch point. Stateless visitors (route, coverage) pass state through unchanged.
- **`backend/tl_coverage.rpy`** — `_tl_cov_visitor` updated to `(node, state) → state` signature.
- **`backend/tl_route_logic.rpy`** — `_visitor` in `_tl_ri_collect_assigned` updated to `(node, state) → state` signature.
- **`backend/tl_assets.rpy`** — new `_tl_build_menu_scene_index(nodes)`: builds `persistent._tl_menu_scene_map` via the shared stateful block walk. `last_img` is the state; Scene/Show nodes update it, Menu nodes record the current value for their site key (backfill only — existing entries not overwritten). Jump-following removed: gaps are covered by `_tl_resolve_live_menu_img_name` (runtime capture) and screenshot fallback.
- **`timeline_init.rpy`** — `_walk_menu_imgs` recursive closure and its per-label loop replaced with a single `_tl_build_menu_scene_index(nodes)` call in `_tl_build_ast_map`.
- **`tests/test_route_logic.py`** — `TestWalkAstBlocks` updated for new `(node, state) → state` visitor signature.
- **`tests/test_ast_walk.py`** (new) — `TestWalkAstBlocksStateful`: state threading, branch inheritance, branch isolation. `TestBuildMenuSceneIndex`: scene-before-menu recording, multi-menu sequencing, branch scene isolation, backfill guard, file filtering.

### Refactor: Canonical game-file filter — `_tl_is_game_file` replaces three scattered checks

- **`backend/tl_ast_utils.rpy`** — added `_tl_is_game_file(f)` as the single definition of "game script vs RenPy internal vs this mod". All mod files (including `timeline_*.rpy`) live under `renpy-chronology-mod/` so the mod-dir check covers them; the previously separate `timeline_*.rpy` basename guard in `_tl_should_track_if_node` was dead code and is removed.
- **`backend/tl_ghost_logic.rpy`** — deleted `_tl_should_track_if_node` (was a single-condition wrapper with dead code); both call sites now use `_tl_is_game_file` directly.
- **`backend/tl_route_logic.rpy`** — Python.execute patch guard replaced with `_tl_is_game_file`.
- **`backend/tl_ast_utils.rpy`** — `_tl_walk_ast_blocks` internal lambda replaced with `_tl_is_game_file`.

### Refactor: Codebase simplification — shared AST utilities, walk deduplication, screen-open caching

- **`backend/tl_ast_utils.rpy`** (new) — shared AST utility module that loads before all other `tl_*.rpy` files (alphabetical `init -2` order). Contains `_tl_ast_literal_value` (Python 2/3 compat literal extractor — replaces scattered `Constant`/`Str`/`Num` isinstance chains), `_tl_extract_compare_literals` (condition string → comparator literals), `_tl_walk_ast_blocks` (game-script-filtered iterative block walker with If/Menu recursion), and `_tl_prettify_var` (moved from `tl_route_logic.rpy`).
- **`backend/tl_coverage.rpy`** — `_tl_build_coverage_index` walk replaced with `_tl_walk_ast_blocks` + visitor. Removed duplicate `_game_file` lambda, `_visited` set, and 30-line worklist loop.
- **`backend/tl_route_logic.rpy`** — `_tl_build_route_index` walk replaced with `_tl_walk_ast_blocks` + visitor. Removed duplicate `_game_file` lambda, `_visited` set, and 70-line worklist loop. Three inline Python 2/3 compat chains (`Constant`/`Str`/`Num` ternaries) replaced with `_tl_ast_literal_value`. `_pyast_Constant` intermediate removed. `_tl_prettify_var` removed (now in `tl_ast_utils.rpy`). `_tl_build_route_index` decomposed into three phase functions: `_tl_ri_collect_assigned` (Python/If node walk), `_tl_ri_collect_defaults` (Default node walk), `_tl_ri_build_if_counts` (If condition walk); orchestrator is now 15 lines.
- **`backend/tl_ghost_logic.rpy`** — inline `Constant`/`Str`/`Num` triple-chain in `_tl_parse_regions` replaced with `_tl_ast_literal_value`.
- **`timeline_screen.rpy`** — locked branch count moved from inline `python:` block (O(N_branches) per render frame) to `default _tl_locked_count = _tl_count_locked_branches()` (evaluated once per screen open).
- **`timeline_init.rpy`** — added `_tl_count_locked_branches()` helper used by the screen default above.
- **`ui/tl_route_screen.rpy`** — `_tl_build_route_chips()` call moved from `python:` block (every render) to `default _tl_route_chips = _tl_build_route_chips()` (once per route screen open).
- **`tests/conftest.py`** — `tl_ast_utils.rpy` added as first entry in the shared `_rpy_ns` load list.
- **`tests/test_coverage.py`** (new) — baseline tests for `_tl_build_coverage_index`.
- **`tests/test_ghost_logic.py`** — added `TestExtractCompareLiterals` (Phase 0B) and two `TestParseRegions` baseline cases.
- **`tests/test_route_logic.py`** — added `TestWalkAstBlocks` (Phase 0B).

### Fix: Save recursion — ghost_nodes append via `.append()` instead of `+` concatenation

- **`backend/tl_ghost_logic.rpy`** — changed `store._tl_ghost_nodes = store._tl_ghost_nodes + [{...}]` to `store._tl_ghost_nodes.append({...})`. With concatenation, Ren'Py's rollback log stored a full copy of the growing list at every checkpoint; with `.append()`, `RevertableList` tracks only the delta (one element), dramatically reducing rollback log size in sandbox games with many ghost nodes.

### Fix: Route var set cache — function-level default arg instead of store var

- **`backend/tl_route_logic.rpy`** — `_tl_python_execute_patched` now caches the route var frozenset in a function-level mutable default arg (`_cache=[None, None]`), keyed by identity of `persistent._tl_route_var_names`. Replaces `store._tl_route_var_set` which was subject to Ren'Py rollback, causing `rset_size=0` misses after native rollback.
- **`timeline_init.rpy`** — removed `default _tl_route_var_set`.
- **`timeline_hooks.rpy`** — removed stale `_tl_on_load` workaround that rebuilt the set after load.

### Refactor: Python.execute patch — targeted co_names diff, moved to tl_route_logic.rpy

- **`backend/tl_route_logic.rpy`** — Python.execute monkeypatch moved here from `tl_ghost_logic.rpy` (correct ownership: var change detection is route tracking, not ghost synthesis). Patch rewritten to use `self.code.bytecode.co_names` to determine which route vars a block might touch, then snapshot and diff only those (~0–5) instead of all ~1000+ route vars. Cost per Python block drops from O(n_route_vars) to O(|co_names ∩ route_vars|) ≈ O(0–5). Hide-mode blocks skipped (they write to local dict, not store). Added `store._tl_route_var_set = frozenset(_route_vars)` at end of route index build for O(1) intersection. Removed `_tl_snapshot_route_vars` and `_tl_diff_route_vars` (logic inlined). Tinting (`_tl_recently_changed_vars`) updated always; pending delta only when notifs enabled — cleanly separating the two concerns at the source. Verified across RenPy 7.4 (Python 2), 8.3.2, and 8.5.2 — `co_names` accessible in all.
- **`backend/tl_ghost_logic.rpy`** — removed Python.execute patch registration (now in `tl_route_logic.rpy`).
- **`timeline_init.rpy`** — added `default _tl_route_var_set = frozenset()`; removed `_tl_save_diagnostics` (temporary diagnostic, no longer needed).
- **`tests/test_route_logic.py`** — replaced `TestDiffRouteVars` with `TestFlushVarChanges` (tests flag behavior, notification content, pending-clear); added flag regression tests to `TestFlushMenuSnap`.
- **`tests/test_ghost_logic.py`** — rewrote `TestPythonExecutePatched` to use co_names/tinting detection instead of `_tl_diff_route_vars` mock.
- **`tests/conftest.py`** — `Python` stub now compiles real bytecode from source so `co_names` is accessible in tests.
- **`docs/NON_INTRUSIVENESS.md`** — updated Python.execute patch file reference.

### Fix: Python 2 (RenPy 7) compatibility — route index, screen scoping, builtin shadowing, markup safety

- **`backend/tl_route_logic.rpy`** — guarded all three `ast.Constant` accesses (assignment RHS, If-condition comparator, domain comparator) behind `_pyast_Constant = getattr(_pyast, "Constant", None)`; added `ast.Name` id check for `"True"`/`"False"` in both literal extraction sites so Python 2 boolean values are collected into the domain (Python 2 represents `True`/`False` as `Name` nodes, not `Constant`); added `_TL_SCALAR_TYPES` including `unicode` on Python 2 so unicode-string store vars are correctly classified as scalars.
- **`ui/tl_route_screen.rpy`** — replaced genexp in screen `python:` block with listcomp to fix Python 2 scoping issue; replaced `min`/`max` calls with `_TL_MIN`/`_TL_MAX` to avoid game characters with those names shadowing builtins.
- **`timeline_init.rpy`** — added `_TL_MIN`/`_TL_MAX` pure-Python wrappers (picklable, shadow-safe); added `_tl_strip_renpy_tags(s)` using `re.sub(r'\{[^}]*\}', '', s)`.
- **`backend/tl_ghost_logic.rpy`** — applied `_tl_strip_renpy_tags` at both return paths of `_tl_prettify_condition`.
- **`backend/tl_route_logic.rpy`** — applied `_tl_strip_renpy_tags` to var values in `_tl_flush_var_changes` and `_tl_flush_menu_snap`.
- **`timeline_screen.rpy`** — applied `_tl_strip_renpy_tags` to domain tooltip value rows; replaced `min(...)` position clamp with `_TL_MIN(...)`.

### Revert: Remove `_TlNoSaveList`/`_TlNoSaveSet` — not the root cause of save recursion

- Diagnostics confirmed the recursion originates in `renpy.game.log` (the rollback log itself), not in ghost node contents. The co_names refactor reduces rollback log growth more effectively by limiting how often `_tl_ghost_nodes` changes. `_TlNoSaveList`/`_TlNoSaveSet` classes removed; `_tl_ghost_nodes` and `_tl_skip_ghost_ifs` reverted to plain `[]` / `set()`.

### Cleanup: Remove dead `_tl_ghost_highlight` state (orphaned from stashed causal hint system)

- **`backend/tl_ghost_logic.rpy`** — removed `_tl_toggle_ghost_highlight`.
- **`ui/tl_ghost_cards.rpy`** — removed `hl` parameter from `tl_ghost_card`; removed `ghost_highlight` parameter from `tl_ghost_rows`; condition label changed from clickable button to non-interactive frame.
- **`ui/tl_route_screen.rpy`**, **`timeline_init.rpy`**, **`timeline_hooks.rpy`**, **`timeline_save_hooks.rpy`** — removed all references to `_tl_ghost_highlight`.

### Feature: Var change notifs toggle

- **`timeline_screen.rpy`** — added "Var change notifs ✓/✗" button to the route tab header (hidden on cards tab). Uses `ToggleField(persistent, "_tl_var_notifs_enabled")`.
- **`timeline_init.rpy`** — added `persistent._tl_var_notifs_enabled` initialised to `False` (opt-in). Uses `hasattr` guard for save compatibility.
- **`timeline_hooks.rpy`** — both flush sites (`_tl_interact_callback` and `_tl_record_before`) now discard `_tl_pending_var_changes` and `_tl_menu_var_snap` when disabled instead of flushing. Ensures enabling mid-session starts clean with no backlog. `_tl_recently_changed_vars` (chip tinting) is unaffected — populated by the diff which runs unconditionally.
- **`ui/tl_theme.rpy`** — widened glyph range from U+2715 to U+2713–U+2717 to cover ✓ and ✗.

### Fix: Route var collection — union `default`-declared vars into `_tl_route_var_names`

- **`backend/tl_route_logic.rpy`** — after the Default-node walk, `_route_vars` is updated with `_defaults.keys()` before writing `persistent._tl_route_var_names`. Previously only `$`-assigned vars were collected; vars declared via `default varname = value` and only read in If conditions (never assigned) were absent from `_tl_route_var_names` and invisible to the chip bar entirely. The existing `_extra` path in `_tl_build_route_chips` (which appended highlighted default-only vars) is now redundant for this case but kept as a safety net for vars not captured by either walk.

### Fix: Game script filter — exclude `renpy/` internals instead of requiring `game/` prefix

- **`backend/tl_route_logic.rpy`**, **`backend/tl_ghost_logic.rpy`**, **`backend/tl_coverage.rpy`** — all `_game_file` / `_tl_should_track_if_node` / `_tl_python_execute_patched` filename filters changed from `startswith("game/")` to `not startswith("renpy/")`. RenPy stores AST filenames relative to the `game/` directory, so game scripts never carry a `game/` prefix — games that archive scripts under a subdirectory (e.g. `scripts.rpa` → `scripts/base/script.rpyc`) were being silently excluded, producing zero route vars, zero ghost cards, and zero coverage branches.
- **`tests/test_ghost_logic.py`** — added `test_game_script_no_game_prefix_diff_called` to cover `scripts/base/script.rpyc` style paths; updated `test_non_game_file_bypasses_diff` comment to reflect the new filter logic.

### Refactor: Font system — centralize into shared FontGroups in tl_theme.rpy

- **`ui/tl_theme.rpy`** — replaced the 35-line font resolution init block (which had a dead InterVariable/DejaVuSans fallback branch) with a clean 5-line resolution, then builds `_tl_fontgroup` and `_tl_bold_fontgroup` via `_tl_make_fontgroup(base)`. The helper adds DejaVuSans overrides for six glyph ranges (middle dot U+00B7, arrows U+2190–U+21FF, branch ⎇ U+2387, close ✕ U+2715, down-triangle ▾ U+25BE, filled circle ● U+25CF) before falling back to the game/Inter base font. `style tl_base`, `style tl_base_bold`, and `style tl_icon` all now use the shared fontgroups.
- **`ui/tl_route_screen.rpy`** — removed the local `_tl_notify_font` init block; `_tl_notify` screen now uses `_tl_fontgroup` from `tl_theme.rpy` (loads first alphabetically).
- **`backend/tl_ghost_logic.rpy`** — stripped `{font=DejaVuSans.ttf}⎇{/font}` tags from both `_tl_notify_branch` show_screen calls; bare `⎇` character now renders correctly via `_tl_fontgroup`.
- **`timeline_screen.rpy`** — removed two inline `font "DejaVuSans.ttf"` overrides on ↺ and → text nodes; covered by `style tl_base` FontGroup.
- **`ui/tl_cards.rpy`** — removed `{font=DejaVuSans.ttf}▾{/font}` tag from the "All options" button text; covered by `style tl_base` FontGroup.

### Fix: Var change notifications — batch via interact_callback instead of per-Python-block flush

- **`timeline_hooks.rpy`** — `_tl_interact_callback` now calls `_tl_flush_var_changes()` at the top of its body. Previously `_tl_python_execute_patched` flushed immediately after every Python block, so consecutive assignments within one script segment each replaced the previous notification — the player only saw the last one. Accumulating through `_tl_pending_var_changes` and flushing once per interaction means all changes in a segment appear in one batched notification.
- **`backend/tl_ghost_logic.rpy`** — removed the immediate `_tl_flush_var_changes()` call from `_tl_python_execute_patched`; now only calls `_tl_diff_route_vars` to accumulate.

### Fix: Route chip tooltip — include declared default value in domain

- **`backend/tl_route_logic.rpy`** — after the Default-node walk, each captured default value is now seeded into `_domain` via `_domain.setdefault(var, set()).add(str(default_val))`. Previously the tooltip only showed values collected from Python assignments and If-condition comparisons; vars whose starting value is only declared via `default varname = value` (and never explicitly assigned in a Python block or compared in a condition) would show an empty domain. The declared default is now always present as a domain entry.

### Fix: camelCase var extraction in ghost conditions — shift to AST parser

- **`backend/tl_ghost_logic.rpy`** — `_tl_extract_vars_from_conditions` replaced regex walk with `ast.parse(cond, mode="eval")` + `ast.Name` node walk. The previous regex `[a-z_][a-z0-9_]*` only matched all-lowercase sequences; camelCase vars (e.g. `wendyRat`) and bare truthy checks (e.g. `if wendyRat:`) were silently dropped, producing an empty `affecting_vars` list and hiding the chip even when highlighted. AST handles all expression forms correctly.
- **`backend/tl_ghost_logic.rpy`** — added always-on log when `affecting_vars` is empty despite non-trivial conditions, to catch future extraction regressions without needing debug flags.
- **`tests/test_ghost_logic.py`** — added three cases to `TestExtractVarsFromConditions`: bare truthy var, camelCase var in equality + bare truthy combination, and `not var` form.

### Fix: Route chips — show ghost-highlighted vars that are only declared via `default`

- **`backend/tl_route_logic.rpy`** — `_tl_build_route_chips` now appends highlighted vars that are present in `persistent._tl_var_defaults` but absent from `persistent._tl_route_var_names`. Such vars are declared via `default varname = value` and only read in If conditions — never `$`-assigned — so the Python-node walk never collected them into `_tl_route_var_names`. They are valid route vars and should appear as chips when a ghost card references them.
- **`backend/tl_route_logic.rpy`** — added `TL_DEBUG_ROUTE`-gated log listing vars added via this path.

### Fix: Conditional menu options — node["options"] now contains only available choices

- **`timeline_hooks.rpy`** — `_tl_record_before` now filters options by condition at record time. Prompt detected by `block is None` (entry[2]). Available options: `cond` truthy (`True`, `"True"`, `None`). Locked options: `cond` falsy (`False`, `"False"`) or `py_eval(cond_str)` returns False. Previously `entry[2]` (an integer AST index, never `False`) caused all options to pass regardless of lock state, misaligning `chosen_index` with the available list.
- **`timeline_hooks.rpy`** — removed `_option_conditions` field from node dict and the AST re-walk block that populated it.
- **`ui/tl_cards.rpy`** — removed `[condition_str]` subtitle row from option display.
- **`timeline_tests.rpy`** — replaced `_tl_test_option_conditions_alignment` with `_tl_test_option_filtering`, covering boolean True/False conditions, string `"True"`/`"False"` conditions, unconditional choices, all-locked menus, and prompt detection.

### Fix: Route chip filtering — hide vars still at declared default value

- **`backend/tl_route_logic.rpy`** — added `Default` AST node walk in `_tl_build_route_index`; captures scalar (`bool`, `int`, `float`, `str`) default values into `persistent._tl_var_defaults`. In `_tl_build_route_chips`, vars whose current value equals their declared default are hidden unless ghost-highlighted or recently-changed. Non-scalar defaults (Character objects, dicts, etc.) are skipped at eval time to avoid persistence errors.
- **`backend/tl_route_logic.rpy`** — moved default values dict from `store._tl_var_defaults` to `persistent._tl_var_defaults`. Store-declared vars are restored from the save file on load, overwriting values set during init; persistent survives the load cycle so defaults are available immediately after AST walk.
- **`timeline_init.rpy`** — removed `default _tl_var_defaults = {}` declaration (now persistent).
- **`tests/conftest.py`** — added `_tl_var_defaults={}` to persistent stub; updated `test_route_logic.py` references from `store` to `persistent`.

### Fix: AST scene-map walk crash when `persistent._tl_menu_scene_map` is None

- **`timeline_init.rpy`** — added guard before the `_mk not in persistent._tl_menu_scene_map` walk: if `persistent._tl_menu_scene_map is None`, initialize to `{}`. Prevents `TypeError: argument of type 'NoneType' is not iterable` on first launch before any persistent data exists.

### Fix: Route chip filtering — remove consumed/if_count hide rules

- **`backend/tl_route_logic.rpy`** — removed `_tl_var_consumed` check and `if_count == 0` hide rule from `_tl_build_route_chips`. Vars now show if assigned and scalar-valued; `val is None` and non-scalar are the only filters. Sort order (ghost/recently-changed first, then `if_count` desc) already pushes low-signal vars down — hiding them by consumed state was dropping vars that still had unseen conditions later in the game.

### Fix: Seen-state compatibility for RenPy 8.5.2 (`config.hash_seen = True`)

- **`backend/tl_seen_check.rpy`** — `_tl_say_seen_name` now version-branches: on RenPy 8.5.2+ (has `renpy.seen_translation`), returns the `node.identifier` string; on older RenPy, resolves through the translator and returns `node.name` tuple. `_tl_eval_seen_fn` dispatches on key type: string → `renpy.seen_translation()`, tuple → `_seen_ever` dict lookup. Fixes dots appearing on seen options in `config.hash_seen = True` games. Added `TL_DEBUG_SEEN`-gated log to the primary peek path result (was invisible before).

### Refactor: Remove dead `_tl_ast_map` fallback

- **`timeline_init.rpy`** — removed `default _tl_ast_map = {}` and the Menu-node walk that built it in `_tl_build_ast_map`. The route and coverage index walks that follow are unaffected.
- **`backend/tl_seen_check.rpy`** — removed the `ast_map` fallback block from `_tl_option_seen`. It was dead: `_tl_ast_map` and `_tl_live_menu_lookup` drew from the same `namemap`, so the peek path always succeeded when ast_map would have, and `persistent._chosen` covered the remaining cases.

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

- **`backend/tl_route_logic.rpy`** — added `_tl_format_numeric_change(label, old_val, new_val)`: formats numeric var changes as `↑N Label` or `↓N Label`. When the delta is exactly 1, the magnitude is omitted (`↑ Label`). `_tl_flush_var_changes` and `_tl_flush_menu_snap` both use this helper for vars in `persistent._tl_var_is_numeric`.

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
