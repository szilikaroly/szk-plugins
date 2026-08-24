---
description: Stop autosaving until resumed
---

Suspend the vault. The Stop hook keeps firing but does nothing, so no commits
and no pushes happen.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault.py" pause
```

Use it before a messy refactor the user does not want in the history, or while
working on something that must not leave the machine. Nothing is lost -- the
next `/vault:save` picks up everything that changed meanwhile, in one commit.

To start again:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault.py" resume
```

If the user asks to pause "for now", remind them once that it stays paused until
explicitly resumed -- there is no timer.
