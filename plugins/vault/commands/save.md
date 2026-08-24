---
description: Commit and push every project now, ignoring the debounce
---

Force an immediate autosave pass across all projects.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault.py" save --force
```

Normally the Stop hook does this by itself, at most once every five minutes per
project. Use this when the user wants everything on GitHub *now* -- before
shutting the machine down, or after a large edit.

To limit it to named projects, append them:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault.py" save --force tezis_projekt
```

Report only the projects that actually changed. A project that says
`committed 0 file, mar pusholva` needs no mention.
