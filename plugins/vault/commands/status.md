---
description: What is versioned, what is behind, what is held back
---

Show the vault's current state.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault.py" status
```

Report it as a table. Four things are worth calling out explicitly if they
appear, because each means something different:

- **nincs git repó** — the project was added after the last `init`; running
  `/vault:init` picks it up.
- **PUSH VISSZATARTVA (túl nagy)** — the project is committed locally but is
  over `max_repo_gb`, so it is deliberately not pushed. GitHub will not serve a
  repository that size. Do not "fix" this by forcing the push; say what the
  options are (split the project, exclude the bulk data, or accept local-only
  versioning).
- **N nagy fájl kihagyva** — individual files at or above 95 MB, which GitHub
  hard-rejects. They are listed by name and size in the project's
  `.vault/oversize.txt` and are still on disk, untouched.
- **HIBA: …** — a real failure. Run `/vault:doctor` before guessing.

If everything says `naprakesz`, say so in one line and stop.
