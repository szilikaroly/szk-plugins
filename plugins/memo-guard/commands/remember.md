---
description: Edit core memory — the always-in-context blocks for preferences and learned workflows
argument-hint: show | replace <label> | insert <label> <text> | rethink <label> | history <label>
allowed-tools: Bash
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/blocks.py"`.

Core memory is the tier injected into **every** session. It costs tokens on every
turn, which is exactly what buys its value: nobody has to know to go looking for
it. That also means it must stay small and true. Three default blocks:

- `user_preferences` — how this user wants to be worked with. Style, standing
  corrections, tools they prefer. **Not** facts about their projects.
- `workflows` — procedures learned by doing. Write them as instructions to a
  future session: the sequence that worked, the step that is always forgotten.
- `project_context` — what this project is and what must not be broken. Scoped
  to the current project.

Anything that is a *fact* rather than a preference or procedure belongs in
`/memo-guard:memory` instead, where it costs nothing until it is recalled.

Parse "$ARGUMENTS":

- `show` (or empty) → run with no flags; shows each block with its fill level.
- `replace <label> <old> :: <new>` → `--replace <label> --old "<old>" --new "<new>"`
- `insert <label> <text>` → `--insert <label> --text "<text>"`
- `rethink <label> <text>` → `--rethink <label> --text "<text>"`
- `history <label>` → `--history <label>`

**Before any replace, run `--show` and copy the target text exactly.** `--old` must
match exactly once; zero matches and several matches are both refused rather than
guessed at, and no line numbers may be included. If a string appears twice, extend
it with surrounding text until it is unique.

Prefer `replace` and `insert`. Reach for `rethink` only when the block has become a
pile of patches that needs reorganising — it discards the previous text wholesale,
and that is usually how a careful record turns into a confident summary of itself.
`--history <label>` shows what changed and when.

Edits that would exceed a block's char limit are refused, never truncated. When that
happens, shorten the addition or `rethink` the block; do not delete another entry to
make room without telling the user which one.
