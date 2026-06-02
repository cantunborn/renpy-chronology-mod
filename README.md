# Chronology Mod

A choice history tracker for Ren'Py visual novels. Records every decision you make, shows which paths you've seen and which are still locked, and lets you jump back to any past choice to try a different one.

---

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
| **R** | Open / close route tracker |
| **Esc** | Close |

---

## Features

### Choice Timeline

Every menu choice you make is recorded as a card in the timeline. Each card shows a thumbnail from when the choice appeared, the option you picked, and a dot if any option in that menu leads to content you haven't seen yet.

### New Content Indicators

The mod walks the game's script at startup to detect which options lead to unseen content. A dot (●) marks any card or option that still has unexplored paths. The header shows how many choices in your history have new paths available and how many branches across the game are still locked.

### All Options Modal

Click **All options** on any past card to see every choice that was available at that point:
- `→` marks the option you chose
- A muted `→` marks the option from the path your current save branched off from
- A dot marks options with unseen content

### Jump Back and Replay

In the modal, click any option to jump back to that point and play forward with a different choice. The mod saves a recovery point first, so you can always return to where you were.

**Playing what-if from a save.** If you want to try a different choice without losing your current progress, save to a new slot first — that keeps your current run intact. Then jump back to an earlier choice from your original save. Now you have two independent runs: one continuing as it was, one playing out differently from that point. You don't have to replay the whole game just to see what changes.

The new run carries hints from the original, so you know exactly where the two paths diverge:
- At each upcoming choice, a muted `→` shows what you picked on the original run. Follow it or go a different way.
- The point where you split off gets a `⎇` marker in your timeline.
- Further down, any choice where the two runs differ also shows `⎇` — open the modal on those cards to see what the original path took.

Hints persist across saves and loads. They clear as each matching choice is reached, and reset if you jump again.

### Chapter Markers

If the mod is configured with your game's chapters, the timeline shows a divider at the end of each chapter. Clicking the divider jumps directly to that chapter's ending — useful for catching up on a new update without replaying everything.

### Route Tracker

Press R to open the route tracker. It shows the story variables that gate content — route flags, relationship values, stat choices — and what they're currently set to. Variables tied to the most recent branch cards are highlighted at the top.

### Branch Cards

When the game evaluates a story branch between your choices, the route screen shows one card per path. A lock icon means you've never seen that path. A dim overlay means you've seen it on a previous playthrough. No overlay means you took it this run. Branch cards clear at the next choice.

### Branch Notifications

When you pass through a branching point, a brief toast appears: `⎇` if there are paths you haven't taken, `⎇ New path` if the branch you just took is itself new.

When a story variable changes mid-scene, a separate toast shows what changed — `↑ Affection`, `Route → romance`, etc. These are off by default. To enable them, open the route tracker (R) and toggle **Var change notifs** in the header.

### Save Compatibility

- **Installing mid-playthrough:** the mod starts recording from that point. Earlier choices show no history, which is expected.
- **Removing the mod:** existing saves load normally. Ren'Py ignores the unused `_tl_*` variables. A `_tl_thumbs.pkl` file in the save directory can be deleted manually — it is only used by the mod.
- **Loading a corrupted save:** history is validated and any malformed entries are dropped silently.

---

## Ren'Py Compatibility

Should work with most Ren'Py 7 and 8 versions. The background blur may not render on some Ren'Py 7 renderers, but all other features work normally. Chapter markers may not work with all Ren'Py 7 versions.

---

<details>
<summary>Developer reference</summary>

For file ownership, function signatures, variable lists, and test coverage — see [docs/DEV_NOTES.md](docs/DEV_NOTES.md).

</details>