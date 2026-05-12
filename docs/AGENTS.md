# AI Session Guardrails

This repo expects conservative edits.

## Required workflow

1. Inspect relevant files first.
2. Explain the intended change before writing code.
3. Prefer the smallest ownership-correct change.
4. Verify behavior after the change.
5. Update docs after successful changes.

## Primary context order

For a new session, read in this order:

1. `docs/AGENTS.md`
2. `docs/SESSION_GUIDE.md`
3. The relevant feature doc in `docs/`
4. The target code files

Do not start by reading the entire repo unless the task truly requires it.

## Editing rules

- Do not implement before you can state:
  - which files will change
  - why those files own the behavior
  - what control flow will change
  - what is explicitly not changing
- Prefer updating existing subsystem docs rather than inventing new docs.
- Avoid broad speculative rewrites.
- When uncertain, produce a short implementation plan before patching.
- Prefer working with Ren'Py's native semantics, identities, and persistence model.
- Do not introduce a parallel identity or seen-state layer unless:
  - Ren'Py-native state is demonstrably insufficient for the feature, and
  - the replacement model is explicitly documented before implementation.

## File ownership hints

- Runtime logic — top-level hooks/init: `timeline_*.rpy`
- Runtime logic — subsystem modules: `backend/`
- UI screens (no behavior logic): `ui/`
- Offline analysis and builders: `tools/*.py`
- Full function reference: `docs/DEV_NOTES.md`
- Architecture and subsystem flow: `docs/CODE_FLOW.md`
- Feature docs: `docs/*.md`
- Stashed / experimental approach docs: `docs/Experiments/`
- Stable high-level overview: `README.md`
- Short session entrypoint: `docs/SESSION_GUIDE.md`
- Installed game-mod dir for live verification:
  - `/Users/divyjain/Games/Personal/Imperial Chronicles.app/Contents/Resources/autorun/game/renpy-chronology-mod`

## Installed-copy rule

Do not copy files into the installed game-mod directory during implementation.

Only copy files to:

- `/Users/divyjain/Games/Personal/Imperial Chronicles.app/Contents/Resources/autorun/game/renpy-chronology-mod`

when the user has said they are satisfied with the implementation and want to move on to verification in the live game.

## Post-change doc update rule

After a successful implementation or bug fix, update:

1. `docs/changelog.md`
2. The relevant feature doc in `docs/`
3. `README.md` only if stable developer notes changed
4. `docs/SESSION_GUIDE.md` only if the project map changed materially