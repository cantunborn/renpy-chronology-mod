# Ghost Cards

## What This Subsystem Is

Ghost cards are ephemeral cards that appear in the **route screen** (key `R`) whenever the game evaluates a player-relevant `if` condition between menu choices. They are "ghost" in the sense that they are not history nodes — they exist only from the moment the condition fires until the next menu, when they are cleared.

Each ghost card represents one `if/elif/else` statement the game just evaluated. The card shows every branch of that statement, not just the one taken, so the player can see what paths exist and whether they have seen each branch before.

Ghost cards appear below the chip bar in the route screen, rendered as a grid. Clusters are shown in reverse chronological order (most recent at top-left). Cards within a cluster maintain left-to-right order.

## Main Files

- `backend/tl_ghost_logic.rpy` — runtime hook, clustering, payload builder, emission, branch notification
- `backend/tl_seen_check.rpy` — seen descriptors (`_tl_make_seen_fn`, `_tl_eval_seen_fn`)
- `ui/tl_ghost_cards.rpy` — `tl_ghost_rows` and `tl_ghost_card` screens
- `ui/tl_cards.rpy` — `tl_thumbnail_frame` (shared with regular cards)
- `ui/tl_route_screen.rpy` — renders ghost rows below the chip bar

## Current Runtime Flow

```
renpy.ast.If.execute (monkey-patched via _tl_if_execute_patched)
    -> _tl_get_taken_branch()           — evaluate which branch is taken
    -> _tl_eval_seen_fn(taken_branch)   — snapshot seen state BEFORE execute
    -> original RenPy If.execute
    -> _tl_on_if_execute()
        -> collect sequential sibling If run (_tl_collect_if_run)
        -> build one payload per sibling If (_tl_build_ghost_payload)
        -> partition run into mutually exclusive groups (_tl_partition_if_run)
        -> emit one ghost cluster per group (_tl_emit_ghost_cluster)
        -> record later sibling ast keys in _tl_skip_ghost_ifs
        -> fire branch notification (_tl_notify_branch)
```

The hook synthesizes the whole relevant sibling run immediately so mutually exclusive sequential `if`s can appear together as one cluster. Each group is emitted with `cluster_with_prev=False` — no inter-run merging with the previous ghost node.

At the next menu (`_tl_record_before`), `_tl_ghost_nodes` and `_tl_ghost_highlight` are cleared.

## What the UI Shows

Each ghost cluster is a group of branch cards rendered in a grid row. Cards within the same cluster have a faint accent-colored gap between them (`TL["accent"] + "2a"`). Cards from different clusters have a transparent gap instead. A muted divider separates the ghost section from the chip bar above.

Each branch card shows:

- a thumbnail image (resolved from Scene/Show in the branch block, or a jump-hop fallback)
- the branch condition string as a label below the thumbnail (clickable — toggles highlight)

**Overlay rules** (applied to the thumbnail):

- **Taken** (`bi == taken_index`): no overlay, no lock
- **Seen but not taken** (previously played via a different save/branch): semi-transparent dark overlay (`#000000aa`), no lock
- **Never seen**: dark overlay (`#000000bb`) + lock icon centered (36×36, fit contain)

A 3px accent bar at the top edge is shown when a card is highlighted (toggled by clicking the condition label).

## Payload Shape

`store._tl_ghost_nodes` is a list of **slim** cluster dicts. Each entry contains only the 4 runtime fields that can change between executions:

```python
{
    "ast_key":           (filename, linenumber),   # root If node of the cluster
    "taken_index":       int or None,              # index of taken branch
    "branch_imgs":       [...],                    # one image name (or None) per branch
    "cluster_with_prev": bool,                     # True = visually grouped with previous cluster
}
```

AST-derived fields are stored once in `persistent._tl_ghost_node_cache[str(ast_key)]` and never roll back:

```python
{
    "conditions":        [...],                    # one condition string per branch
    "seen_fns":          [...],                    # one seen descriptor tuple per branch
    "affecting_vars":    [...],                    # vars referenced in conditions
    "_regions":          [...],                    # DNF region dicts for clustering logic
}
```

The helper `_tl_ghost_ast(ast_key)` returns the cache entry or `{}`. All UI read sites use the pattern `_tl_ghost_ast(key).get(field) or ghost.get(field)` for backward compatibility with saves predating the cache split.

## Seen Logic

Seen state uses descriptor tuples built by `_tl_make_seen_fn(block)` in `backend/tl_seen_check.rpy`. The descriptor is evaluated at render time via `_tl_eval_seen_fn`. Descriptor types:

- `("say", name)` — single Say node key in `persistent._seen_ever`
- `("say_range", first, last)` — fast-fail on first, confirm with last
- `("image", name_tuple)` — Scene bg or expr-Show; checked via `renpy.seen_image`
- `("label", target)` — fallback: `renpy.seen_label`
- `("never",)` — always unseen (unresolvable branch)

The taken branch descriptor is evaluated **before** `If.execute` runs (pre-execute snapshot) to avoid `_seen_images` pollution from synchronous `Scene.execute`. This is what `pre_taken_seen` carries into `_tl_notify_branch`.

## Branch Notification

`_tl_notify_branch` fires once per If-run via `renpy.show_screen("_tl_notify", ...)`:

- **suppress** — all branches seen (including taken): no notification
- **icon** — taken branch seen, ≥1 alternative never seen: `⎇` icon only
- **new_path** — taken branch itself was never taken before: `⎇ New path`

## Important Invariants

- Ghost cards are transient and clear at the next menu.
- Only player-relevant `if` regions that parse to valid DNF regions produce ghost payloads.
- Later sibling `if`s in a synthesized run are added to `_tl_skip_ghost_ifs` to prevent duplication.
- Ghost lock/overlay state is driven by `_tl_make_seen_fn` descriptors, not `renpy.seen_label`.
- The taken branch shows no overlay; state is communicated through overlay opacity and the lock icon only.

## Known Limits

- `UserStatement` / image-menu style control flow is not ghost-tracked.
- Ghost cards are not persisted into history; they clear at the next menu.
- Branches without a resolvable Say/Scene/Show/Jump fallback get `("never",)` and always show as locked.
- Sibling-run partitioning is intentionally conservative; non-simple condition forms may stay unclustered.

## Where To Edit

| Task | File |
|------|------|
| Runtime hook, clustering, payload build, emission | `backend/tl_ghost_logic.rpy` |
| Seen descriptors, eval logic | `backend/tl_seen_check.rpy` |
| Ghost card UI screens (`tl_ghost_rows`, `tl_ghost_card`) | `ui/tl_ghost_cards.rpy` |
| Thumbnail frame overlays (shared with regular cards) | `ui/tl_cards.rpy` |
| Ghost rows render location (below chip bar) | `ui/tl_route_screen.rpy` |