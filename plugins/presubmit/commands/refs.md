---
description: Check only the references — duplicates, missing years/DOIs, and in-text citation cross-check
allowed-tools: Bash
---
Check the reference list and in-text citations. Arguments: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" refs MANUSCRIPT
```

This flags: duplicate references (by DOI and by near-identical text), entries
with no publication year, entries that mention a DOI but have none valid, very
short/incomplete entries, in-text numeric citations `[n]` that point past the
end of the list, and references that are never cited in the text.

Report every finding with its reference number so the user can jump straight to
it. Note that the author–year citation style is only partially checked (numeric
`[n]` cross-checking is exact; author–year is not).
