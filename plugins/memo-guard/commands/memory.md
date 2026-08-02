---
description: Long-term memory across projects — recall through a goal, or promote a fact into it
argument-hint: goal <what you are working on> | recall <query> | promote <fact> | projects
allowed-tools: Bash
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memory.py"` with the matching form.

**The access rule, and why it exists.** Without `--goal` you can only see facts from
the current project. State a goal and the whole store opens, across every project.
This is deliberate: reaching into unrelated projects should be an explicit act with
a recorded reason, not something that happens quietly. Never pass `--goal` just to
widen a search — pass it when the user has actually told you what they are working
toward, and use their words.

Parse "$ARGUMENTS":

- `goal <text>` → `--goal "<text>" --recall "<text>"`
  Opens the full store for this line of work. Use at the start of a task when
  earlier projects plausibly hold something relevant.
- `recall <query>` → `--recall "<query>"`
  Current project only. The default, and the right one most of the time.
- `recall <query> for <goal>` → `--recall "<query>" --goal "<goal>"`
- `promote <fact>` → `--promote "<fact>" --kind <kind>`
  Choose `--kind` deliberately: **decision** (a choice the user made), **constraint**
  (a rule that must hold — a journal policy, a submission limit), **finding** (something
  learned that was expensive to learn), **reference** (a pointer to an external resource).
  Add `--goal` if the current work has one, and `--anchor` with a file:line or archive
  path when one exists.
- `projects` → `--projects`
- `disable <slug>` / `enable <slug>` → `--disable <slug>` / `--enable <slug>`
  Disable a project whose facts must never be recalled elsewhere.
- `forget <id>` → `--forget <id>`

Nothing enters this store by itself. Promote only what would be expensive to
re-derive and that you would want a future session to know — not narration of what
you just did, and not anything the code or git history already records.

When reporting recalled facts: always show which project and date each came from.
A fact from another project read as current context is worse than not recalling it.
Facts the claim store has judged REFUTED are filtered out automatically, so if the
user expects something that does not appear, check `/memo-guard:claim list`.
