---
description: HTML áttekintő legenerálása és megnyitása
allowed-tools: Bash
---
Run this exact command with the Bash tool:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" dashboard --open $ARGUMENTS
```

It writes a self-contained HTML file to `~/.science-monitor/dashboard.html` and
opens it in the default browser. The file is local — it contains unpublished
manuscript titles, journal IDs and review state, so do not publish it as an
Artifact or upload it anywhere unless the user explicitly asks.

Tell the user the path and, in one sentence, what the dashboard is currently
flagging (the script's own `status` output is the quicker way to know that — run
it only if the user asks what is on the page).
