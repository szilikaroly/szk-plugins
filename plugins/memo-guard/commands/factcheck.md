---
description: Mi van a memóriában — kitalált azonosítók, teszt-maradványok, cáfolt állítások
allowed-tools: Bash, Read
---
Audit the long-term memory store itself. Request: $ARGUMENTS

```
S="${CLAUDE_PLUGIN_ROOT}/scripts"
python3 "$S/factcheck.py"                 # offline report
python3 "$S/factcheck.py" --online        # also verify DOIs and PMIDs
python3 "$S/factcheck.py" --quarantine    # drop the errors out of recall
```

Recall serves whatever is in the store, in the authoritative voice of the user's
own notes. Nothing else asks whether a stored fact is still true, or ever was —
which is how an invented PROSPERO registration number and an invented rejection
reason sat in this store undetected until someone looked by hand.

Six checks, cheapest first: synthetic provenance (a fact tied to a test path or
a directory that never existed), dangling file references, text that restates an
already-REFUTED claim, malformed identifiers (a PROSPERO id whose registration
year is impossible, a DOI that cannot parse), unverifiable identifiers when
`--online` is given, and facts that are old and have never once been recalled.

Report the **error** findings individually with the fact's text — the user has
to be able to recognise it. Say plainly which category each falls into:
a fabricated identifier is a different problem from a file that moved.

`--quarantine` sets utility to 0, which takes a fact out of recall and **deletes
nothing**. Say that when you offer it. Deleting the evidence is how you lose the
ability to work out what went wrong; and never quarantine on the user's behalf
without showing them the list first.

`--online` verification treats *no answer* as *not disproven*: an offline machine
must not produce a report accusing every reference of being fabricated.
