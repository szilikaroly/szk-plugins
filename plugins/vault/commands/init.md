---
description: Set up git and a private GitHub remote for every project
---

Bring every project under the configured root into the vault.

For each project this creates a git repo if there is none, writes a `.gitignore`,
excludes any file GitHub would reject (>=95 MB) while recording it in
`.vault/oversize.txt`, makes the first commit, and creates a **private** GitHub
repository as `origin`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault.py" init
```

To do everything except touch GitHub — useful for a first look, or on a machine
that is not signed in:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault.py" init --no-remote
```

This needs the GitHub CLI signed in (`gh auth login`). If it is not, the local
repos and commits are still created and only the remote step is skipped — say so
rather than reporting a failure.

Creating repositories is not reversible from here. If the run would create more
than a handful of new remotes, list what it is about to create and confirm with
the user first.
