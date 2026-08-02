---
description: Archive the current context window now and build its compressed memo (use before a planned /compact or /clear)
allowed-tools: Bash
---
Run this exact command with the Bash tool:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/archive_now.py" --now
```

Tell the user: the archive path, that the compressed memo is building in the background, and that after they run /compact or /clear the resume index will be injected automatically. If they were mid-task, add one short sentence stating what is currently in flight (the RESUME auto-extracts this, but your one-line version is more precise). Then stop — do not run /compact yourself; that is the user's action.
