---
description: Recommend how to visualise data before plotting — chart type + Nature-style checklist
allowed-tools: Bash
---
The user wants advice on how to visualise something: $ARGUMENTS

Run this exact command with the Bash tool:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" advise "$ARGUMENTS"
```

Relay the recommended chart type(s) and the Nature-style checklist to the user.
Then add your own judgement in at most four sentences: which single comparison
the reader must make, whether a panel should be split, and which `/ff:` command
builds it. If the data file is known, offer the exact command line to generate
the figure next (e.g. `/ff:forest --data ... --label ...`). Do not invent data.
