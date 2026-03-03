# Chronology Mod

Drop the contents of this folder into your `game/` directory.

## Files
- `timeline_init.rpy` — store variables, AST parser, seen-checking utilities
- `timeline_hooks.rpy` — wraps `renpy.exports.menu` to record choices
- `timeline_screen.rpy` — all UI screens
- `timeline_save_hooks.rpy` — new game reset

## Usage
- **T** — open/close timeline
- **`** (backtick) — toggle debug overlay

## How it works

### Choice recording
Intercepts `renpy.exports.menu` on every in-game menu. Records a node with
thumbnail, option labels, and which option was chosen. Thumbnails are stored
as bytes in the save file.

### Seen detection
At startup, walks RenPy's AST to find every menu in the game. For each option
block it finds the first meaningful statement (Jump, Call, Say) and registers
a seen-checker using `renpy.seen_label()` or `persistent._seen_ever`. This
runs on a background thread so it doesn't block the game.

### UI
- **Past cards** — thumbnail + chosen option subtitle + footer row
  - Footer left: gold dot if any option has unseen content
  - Footer right: "All options" button opens a centered modal
- **Current card** — thumbnail + all options as rows with gold dots for unseen
- **Header** — global count of menus with at least one unseen option
- **Modal** — shows all options with `>` for chosen, dot for unseen, dimmed for seen

## RenPy compatibility
Tested on RenPy 7.5.3. The item tuple structure `(label, condition, value)` is
confirmed from RenPy 7.5 `exports.py` source.
