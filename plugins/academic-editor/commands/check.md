---
description: Determinisztikus kézirat-ellenőrzés lektorálás előtt — számok, rövidítések, következetlenségek
allowed-tools: Bash, Read
---
Run the deterministic pass. Manuscript: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/manuscript_check.py" <MANUSCRIPT> --json check.json
```

Narrow it with `--only counts,abbreviations,consistency,spelling,register,sentences,passive`.

Report the JAVÍTANDÓ items first — they are mechanical and should be fixed before anyone
reads for style. Then give the MÉRÉS block as context, not as a target: a Methods section
with high passive density is normal, and a Results section with three long sentences is a
list of places to look, not three defects.

Three findings need a sentence of explanation rather than a fix:

- `p` vs `P`, `±` spacing and operator spacing are reported as *splits*. The reference edit
  was itself inconsistent on all three; unify within a passage, and put the global choice to
  the author.
- an abbreviation "defined but not used" is sometimes an author's initials or an ethics
  committee named once — check before proposing a deletion.
