---
description: Flag the tells of an AI-assisted draft — hype, formulaic openers, novelty padding, connective runs, citation dumps, overlong sentences (advisory, report only)
allowed-tools: Bash
---
Check the manuscript for AI-draft tells. Arguments: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" style MANUSCRIPT
```

The rules are the deterministic part of academic-humanizer (MIT; mapping of
each code to its layer in `skills/presubmit/references/academic-humanizer.md`).
They are advisory: nothing here is an ERROR, the category is not part of
`/presubmit:check`, and the readiness verdict is unchanged. English only — a
Hungarian manuscript gets one INFO saying so.

Reporting it back: lead with the counts, then the WARNs (patterns dense enough
that a referee will notice), then the INFOs in one line each. Phrases are
matched narrowly, so a quiet report on a good manuscript is expected; it is not
evidence that no AI was used, and the rules say nothing about whether the
science is right.

To fix what it finds without touching a number or citation, offer
`/presubmit:humanize`.
