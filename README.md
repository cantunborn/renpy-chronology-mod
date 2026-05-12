# Chronology Mod

A non-intrusive choice history tracker for RenPy visual novels. Records every decision you make, shows what you've seen and what's still unexplored, and lets you jump back to any past choice.

## Installation

Download the zip from the [latest release](../../releases/latest) and follow the steps for your platform.

### Windows

1. Open your game's install folder (right-click the shortcut → *Open file location*, or find it in Steam).
2. Right-click the zip → **Extract All**, and set the destination to the game's root folder.
3. The mod files will be copied into `game/` automatically.

### macOS

The game is packaged as a `.app` bundle, so the `game/` folder is hidden inside it.

1. Extract the zip — you'll get a `game/` folder.
2. Find the game in Finder, right-click the `.app` → **Show Package Contents**.
3. Navigate to `Contents/Resources/autorun/`.
4. Drag the `game/` folder from the zip into the `autorun/` folder. When prompted to merge, choose **Merge**.

Launch the game — no further setup needed. Works on existing saves; the mod starts recording from the point you install it.

---

## Controls

| Key | Action |
|-----|--------|
| **T** | Open / close timeline |
| **Esc** | Close timeline |

---

## Features

### Choice Timeline
Every menu choice you make is recorded as a card in the timeline. Each card shows:
- A thumbnail based on the game image shown when the choice appeared
- The option you picked
- Whether any options in that menu lead to content you haven't seen yet (dot indicator)

### New Content Indicators
The mod automatically detects which options lead to unseen content by walking the game's script at startup. A dot (●) marks any option — or any past card — that still has unexplored paths.

The header shows a count of how many past choices have at least one new path available.

### All Options Modal
Click **All options** on any past card to see every choice that was available at that point:
- `→` marks the option you chose
- A muted `→` marks the option you made on the path this save was forked from
- A dot marks options with unseen content

### Jump Back and Forking
In the modal, click any option to jump back to that point in the story and play from there with a different choice. The mod saves a recovery point before jumping so you can return to the original path if needed.

Jumps use a save + skip approach: the mod loads the nearest checkpoint save and fast-forwards through dialogue to reach the target choice automatically.

**Forking a save.** A common use is to duplicate a save before jumping, keeping the original intact. The duplicate becomes a fork — an independent run from that branch point. Hints from the original path carry over into the forked save, so you always know where the two paths differ:

- At each **upcoming menu**, a muted `→` marks the choice you made on the original path. You can follow it or go a different way — your call.
- The **jump point itself** gets a `⎇` marker in the timeline if you chose differently, making it easy to see where the fork started.
- **Further down the timeline**, any card where your new choices diverge from the original also shows `⎇`. Open the All Options modal on those cards to see which option the original path took.

Hints are tied to the save file, not the session — they persist across loads and carry over when you duplicate or share a save. They clear automatically as each matching menu is reached, and disappear entirely if you jump again (resetting the reference path to the current run).

### Thumbnail Cache
Timeline thumbnails now prefer game assets over screenshots. When a menu appears, the mod first tries to resolve the live image currently shown by the game and stores that image name in persistent data for that menu site. A structural AST walk backfills older or not-yet-reached menus with a best-effort image guess, and screenshots remain only as an explicit fallback when asset resolution misses. Timeline rendering only falls back to live `img_name` rendering for plain file-backed assets; dynamic image definitions stay on the safe screenshot/plain-background path.

The screenshot fallback cache is still stored in RenPy's persistent data file, so it survives mod reinstalls and carries over between sessions. Up to 500 fallback screenshots are kept; at the limit the persistent file grows by at most ~25 MB. Most games have far fewer unresolved choice screens, so typical usage should be much lower once asset-backed thumbnails cover the common paths.

### Chapter End Indicators
The mod ships with a sample `chapters.json`. If you populate it with your game's chapters, the timeline shows a divider at the end of each chapter. Clicking the divider jumps directly to that chapter's ending — useful for catching up on a new update without replaying everything.

The divider shows: `—— End of Chapter Name ——`

Edit `game/renpy-chronology-mod/chapters.json` and replace the sample entries with your game's chapter names and end labels:

```json
{
    "_comment": "...",
    "Prologue":  "prologue_end_label",
    "Chapter 1": "chapter_1_end_label"
}
```

Any key starting with `_` is ignored. To find a label name: open the RenPy console (Shift+O), navigate to the scene you want to mark, then run `renpy.game.context().current`.

### Save Compatibility
- **Installing mid-playthrough:** the mod starts recording from that point. Earlier choices show no history, which is expected.
- **Removing the mod:** existing saves load normally. RenPy ignores the unused `_tl_*` variables.
- **Loading a corrupted save:** history is validated and any malformed entries are dropped silently.

---

## Session Entry

For new AI/code-assistant chats, start with:

1. `docs/AGENTS.md`
2. `docs/SESSION_GUIDE.md`
3. the relevant feature doc in `docs/`

Those files are the lightweight session context layer. `README.md` remains the stable human-facing overview.

---

## RenPy Compatibility

Tested on **RenPy 7.5.3** and **RenPy 8.3.2**.

Compatibility holds across both versions for a few reasons:
- The mod hooks into `renpy.exports.menu` and `renpy.store.menu`, which have had a stable `(label, condition, value)` item tuple structure since RenPy 7.
- Save/load callbacks (`config.start_callbacks`, `config.after_load_callbacks`, `config.interact_callbacks`) are part of RenPy's public API and unchanged between major versions.
- The AST walker uses `type(node).__name__` string checks rather than importing RenPy AST classes directly, so it doesn't break if internal class paths change between 7 and 8.
- RenPy 8 is built on the same codebase as 7 with a Python 3 runtime; no API used here was removed in the transition.

**Exception:** chapter end indicators require `config.label_callbacks`, which was added in RenPy 7.6 / 8.1. On older versions the feature is silently disabled — the rest of the mod works normally.

**Exception:** screenshot fallback requires `renpy.screenshot_to_bytes`, added in RenPy 7.5. On older versions, asset-backed thumbnails still work when an image name can be resolved, but screenshot fallback is skipped — unresolved cards show a plain background instead. Choice tracking, dots, jump-back, and chapter markers all work normally.

---

For the full developer reference — file ownership, function signatures, variable lists, and test coverage — see [docs/DEV_NOTES.md](docs/DEV_NOTES.md).

