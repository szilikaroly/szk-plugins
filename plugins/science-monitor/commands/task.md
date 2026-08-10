---
description: Részfeladatok — mi van még hátra egy kéziratból, kire vár
allowed-tools: Bash
---
Sub-tasks are the work a submission still needs that is not a checklist item
and not a reviewer point — "figures redone", "PROBAST adjudication", "four
letters to write". Before this existed they lived in a free-text note, where
they could not be counted, ticked, assigned or chased.

`$ARGUMENTS`: `SLUG` to list, or `SLUG "task" "task"` to add.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" task list SLUG
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" task add SLUG "..." "..." --due 2026-08-12 --assignee CsD
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" task set SLUG ID --state done
```

States: `open`, `doing`, `done`, `dropped`. Use `dropped` — with a `--note`
saying why — rather than deleting; a task that was deliberately abandoned is
information, a deleted one is a gap in the record.

**When a manuscript's notes field contains a to-do list**, offer to convert it:
read the note, propose one task per item, and only write them after the user
agrees. Do not silently reinterpret a note as tasks.

Assign with `--assignee` when more than one author is involved. Report open
tasks grouped by assignee, and name whose turn it is.
