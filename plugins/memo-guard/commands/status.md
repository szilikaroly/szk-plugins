---
description: Show context-window usage, archives, memo state, and measured token savings
allowed-tools: Bash
---
Run this exact command with the Bash tool:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/status.py"
```

Then report its output to the user almost verbatim (keep the numbers), adding at most 2 sentences of interpretation — e.g. whether a checkpoint has fired, whether the measured average reduction meets the >= 95% target, and whether compression ran in local-model or deterministic mode. Do not re-read any archived or source files while doing this.
