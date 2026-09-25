---
description: Check only the references — duplicates, missing years/DOIs, and in-text citation cross-check
allowed-tools: Bash
---
Check the reference list and in-text citations. Arguments: $ARGUMENTS

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pc.py" refs MANUSCRIPT
```

Add `--online` when the user wants the references checked for **errata and
retractions**. It is the only check that touches the network, so it is never
on by default. It resolves each reference to a PubMed record — by DOI when one
is printed, otherwise through PubMed's citation matcher, which is what makes it
work on AMA-style lists that carry no DOIs — and reports any erratum,
retraction or expression of concern. A retraction is an error; an erratum is a
warning, because many corrections are bibliographic only. Either way the notice
has to be opened before anyone can say it does not touch the quoted number.
If the lookup cannot run it says so, and never reports a clean result it did
not verify.

This flags: duplicate references (by DOI and by near-identical text), entries
with no publication year, entries that mention a DOI but have none valid, very
short/incomplete entries, in-text numeric citations `[n]` that point past the
end of the list, and references that are never cited in the text.

Report every finding with its reference number so the user can jump straight to
it. Note that the author–year citation style is only partially checked (numeric
`[n]` cross-checking is exact; author–year is not).

**Journal blacklist.** Every reference is also checked against the MTMT *Norvég
lista* (`scripts/journal_blacklist.py`, data in `~/.szk-blacklist/`): the user
has banned those journals as cited sources and as venues. A hit is an error —
replace the source, do not keep it with a caveat. Refresh the list yearly
(January–February) with `journal_blacklist.py update`.
