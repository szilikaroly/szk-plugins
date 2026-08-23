---
description: Find what is misconfigured, overlapping, or quietly broken
---

Run memo-guard's diagnostics and report what it says.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --root "$(pwd)"
```

It checks six things: overlap with the memo-index skill's hooks, unfilled
handoff templates left lying around, whether the model server actually answers
embeddings, whether the installed plugin copy matches the source, whether
autopilot's state and `settings.json` still agree, and when memory maintenance
last ran.

Report each finding with its suggested fix. Do **not** run a fix without asking
first — `--fix` edits the user's `settings.json`, and `--clean-handoffs` deletes
files. Both are narrow (`--fix` touches only the two keys it names;
`--clean-handoffs` skips any handoff someone actually wrote in), but they are
still the user's call.

If `$ARGUMENTS` names a fix explicitly, run that one:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --fix
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --clean-handoffs --root "$(pwd)"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --maintain
```
