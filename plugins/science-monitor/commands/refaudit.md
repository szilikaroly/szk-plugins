---
description: Hivatkozásjegyzék ellenőrzése Crossref és Europe PMC ellen
allowed-tools: Bash, Read
---
Resolve every DOI in a manuscript's reference list and compare the first author
and year against the registries.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" refaudit SLUG
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" refaudit --file path/to/manuscript.md
```

It reads Vancouver-style numbered entries ending in `doi: 10.…`, so a `.docx`
has to be converted first — use the **doc-tools** skill (`doctotext`) and pass
the text file with `--file`.

## Hogyan olvasd az eredményt

The output separates two things, and the difference matters:

- **✗ hiba** — the DOI does not resolve, or the year is wrong, or the first
  author disagrees with **Europe PMC/MEDLINE**. Fix these.
- **· megjegyzés** — Crossref and Europe PMC disagree with each other while the
  manuscript matches MEDLINE. **Do not "fix" these.** Crossref carries the
  publisher's deposit, which is sometimes partial (one journal deposits only
  the last author) or differently spelled. A Vancouver list is checked against
  MEDLINE, so the manuscript is right and the registry is not.

That distinction exists because acting on Crossref alone once turned a correct
name into an incorrect one here.

Report the errors with their reference numbers and the exact replacement text.
Never edit the manuscript without showing the user what changes first.
