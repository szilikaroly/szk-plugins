---
description: Let compaction fire on its own at a chosen context %, with nothing lost when it does
---

Manage memo-guard's autopilot: archive → compress → compact, without you
running `/compact`.

Run the script and report what it says. `$ARGUMENTS` may contain `on`, `off`,
a bare percentage, or nothing (status).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py" --status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py" --enable --at 70
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/autopilot.py" --disable
```

What to tell the user, accurately:

- memo-guard does **not** run `/compact` — no hook can. It aims Claude Code's
  own automatic compaction by writing `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` into
  `settings.json`, and guarantees via `PreCompact` that the full context is
  archived and a memo is written **before** compaction takes it.
- The change applies from the **next session**. The environment is read when the
  process starts, so the current session keeps the threshold it booted with.
- The first automatic compaction will probably not land on the target, because
  Claude Code measures against an *effective* window that is smaller than the
  model's. memo-guard records where it fired and corrects the override — say
  this up front rather than letting the user discover it as a bug.

If `--status` reports blockers (`DISABLE_AUTO_COMPACT`, `autoCompactEnabled:
false`, an `autoCompactWindow` setting), name them; the override does nothing
while the first two are in force.
