---
description: Áttekintés — melyik kézirat hol tart, mi van beküldve, mi vár válaszra
allowed-tools: Bash
---
Run this exact command with the Bash tool:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" status $ARGUMENTS
```

Report the output to the user almost verbatim in Hungarian — keep every slug,
journal name, date and count exactly as printed. Then add at most three
sentences of interpretation, prioritising in this order:

1. anything past its deadline or due within 7 days,
2. manuscripts marked `ready` that are still not submitted (name the missing
   piece — usually the cover letter),
3. revision decisions with no reviewer letter loaded yet.

If a manuscript needs work, name the single command that starts it — e.g.
`/science-monitor:context SLUG` to load it, or `/science-monitor:review SLUG` to ingest a letter. Do not
read any manuscript files while producing this summary.
