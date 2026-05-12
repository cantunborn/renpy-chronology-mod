# Ghost Cards

## What This Subsystem Is

Ghost cards are ephemeral timeline cards that appear in the timeline screen whenever the game
evaluates a player-relevant `if` condition between menu choices. They are "ghost" in the sense
that they are not history nodes — they exist only from the moment the condition fires until the
next menu, when they are cleared.

Each ghost card represents one `if/elif/else` statement the game just evaluated. The card shows
every branch of that statement, not just the one taken, so the player can see what paths exist
and whether they have seen each branch before.

Ghost cards sit below the current-choice row in the timeline screen and are rendered as a grid
matching the column width of the main card layout.

## Main Files

- `ui/tl_ghost_cards.rpy` — all ghost card logic: DNF parser, clustering helpers, payload builder, emission, `tl_ghost_rows` screen
- `timeline_init.rpy` — seen-state helpers (`_tl_make_seen_fn`, `_tl_eval_seen_fn`, `_tl_find_scene_seen_name`), state vars (`_tl_ghost_nodes`, `_tl_ghost_highlight`)
- `timeline_causal.rpy` — causal hint backend (`_tl_choice_diff_hints`, `_tl_causal_hint`)
- `timeline_flowchart.rpy`
- `causal_graph.json`

## Current Runtime Flow

```
renpy.ast.If.execute (monkey-patched)
    -> _tl_get_taken_branch()
    -> original RenPy execute
    -> _tl_on_if_execute()
        -> collect sequential sibling If run
        -> build one payload per sibling If
        -> partition run into mutually exclusive groups
        -> emit one ghost cluster per group
        -> record later sibling ast keys in _tl_skip_ghost_ifs
```

Ghost cards are no longer fundamentally “append one card when one `if` runs.” The hook now tries to synthesize the whole relevant sibling run immediately so mutually exclusive sequential `if`s can appear together.

At the next menu (`_tl_record_before`), `_tl_ghost_nodes` and `_tl_ghost_highlight` are cleared.

## What the UI Shows

Each ghost cluster is rendered below the main timeline rows. The UI flattens the cluster into branch rows.

Each branch row shows:

- the branch condition string (clickable — toggles causal highlight)
- the branch thumbnail image, if found

Overlay rules (applied to the thumbnail):

- Type-1 — branch taken this play: no overlay
- Type-2 — branch not taken, but seen in a previous play: lighter semi-transparent dark overlay (`#00000099`), no lock
- Type-3 — branch never seen: dark overlay (`#000000bb`) + white lock icon centered

The `→` and `●` text indicators have been removed. State is communicated entirely through overlay opacity and the lock icon.

Cluster separator: a 3 px left border rendered inside the first card of each new cluster. Zero layout-width impact — card width is always `card_w`. Inter-card gaps within a cluster are filled with a faint accent-colored frame; inter-cluster gaps use a transparent frame (`null` does not render correctly inside nested `if`/`for` in RenPy screen language, hence the transparent frame).

## Payload Shape

`store._tl_ghost_nodes` is a list of cluster dicts. A typical entry looks like:

```python
{
    "type": "branch",
    "ast_key": (filename, linenumber),
    "conditions": [...],
    "seen_fns": [...],
    "taken_index": ...,
    "affecting_vars": [...],
    "branch_imgs": [...],
    "causal_hints": [...],
    "causal_hl_keys": [...],
    "member_ast_keys": [...],
    "cluster_with_prev": False,
}
```

## Causal Hint Backend

The current runtime hint path is graph-based, not old `write_map`-based.

`_tl_choice_diff_hints(condition_str)` in `timeline_causal.rpy` reads `causal_graph.json`,
matches the target condition against the current history, and returns paired diff records:

- `kind`
  - `direct`
  - `path`
- `menu_ast_key`
- `original_idx`
- `required_idx`

Ghost-card rows use those results to highlight upstream timeline cards and to explain both:

- direct satisfier choice changes
- prerequisite path/split changes

## Seen Logic

Ghost cards do not use `seen_label` anymore.

Ghost branches use seen descriptors built by `_tl_make_seen_fn(block)` (in `timeline_init.rpy`). It walks the branch block looking for the first *named-character* `Say` node (narrator lines are skipped), then returns a descriptor tuple checked against `persistent._seen_ever` at render time via `_tl_eval_seen_fn`.

`_tl_make_scene_seen_fn` (scene-only variant) still exists but is no longer used for ghost payloads — it missed branches that start with a plain say, jump, or call before reaching a scene.

`_tl_build_ghost_payload` calls `_tl_make_seen_fn` directly.

The flowchart uses the same `_tl_make_seen_fn` helper, so ghost-card lock state and flowchart seen/unlocked state are aligned.

## Important Invariants

- Ghost cards are transient and clear at the next menu.
- Only player-relevant `if` regions that parse to valid DNF regions produce ghost payloads.
- Later sibling `if`s in a synthesized run must be added to `_tl_skip_ghost_ifs` so they do not duplicate when runtime reaches them.
- Ghost lock/overlay state is driven by `_tl_make_seen_fn`, not label-based seen checks.
- The taken branch shows no overlay and no lock; state is communicated through overlay type, not a text indicator.

## Known Limits

- `UserStatement` / image-menu style control flow is still not ghost-tracked like plain `If` nodes.
- Ghost cards are not persisted into history; they only exist until the next menu.
- Branches without a meaningful named-character say node currently fall back to unseen for ghost lock purposes.
- The sibling-run partitioning is intentionally conservative and driven by the current DNF parser; non-simple condition forms may stay unclustered.

## Where To Edit

- runtime hook / clustering behavior / ghost-card rendering
  - `ui/tl_ghost_cards.rpy`
- seen-state helpers (`_tl_make_seen_fn`, `_tl_eval_seen_fn`, `_tl_find_scene_seen_name`)
  - `timeline_init.rpy`
- causal hint backend (`_tl_choice_diff_hints`, `_tl_causal_hint`)
  - `timeline_causal.rpy`
- flowchart seen/unlock alignment
  - `timeline_flowchart.rpy`
- offline hint generation inputs
  - `tools/causal_analysis.py`
  - `causal_graph.json`
