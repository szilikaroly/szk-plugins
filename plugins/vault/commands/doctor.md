---
description: Find out why the vault is not saving
---

Diagnose the vault.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault.py" doctor
```

It reports whether `git` and `gh` are on PATH, whether `gh` is signed in, where
the config and log live, whether the configured root exists, how many projects
still have no repo, and the last ten log lines.

The two failures that account for almost everything:

- **`gh auth    a gh nincs bejelentkezve`** -- the remotes cannot be created or
  pushed to. The user has to run `gh auth login` themselves; do not attempt it
  on their behalf, it is an interactive browser sign-in.
- **`root ... NEM LETEZIK`** -- the config points somewhere that does not exist,
  typically after moving between machines. Fix `root` in the config file the
  command prints.

Read the log lines before offering a theory; they name the project and the exact
git or gh error.
