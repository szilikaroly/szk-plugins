---
description: 5D bibliográfiai validáció — DOI, első szerző, szerzőlista, folyóirat, kötet
allowed-tools: Bash, Read
---
Validate bibliographic records against Crossref, PubMed and Europe PMC. Target: $ARGUMENTS

Work out what is being validated:

- **A harvest or reference CSV** (has `pmid` and/or `doi` columns):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate5d.py" --records <CSV> \
    --out <CSV>-validacio.csv --cache .v5d-cache.json --no-fulltext-gate
```

- **A manuscript's reference list**: extract it first with the `doc-tools`
  skill (`doctotext manuscript.docx -f md`), turn the list into a CSV with
  `doi` (and `pmid` where known) columns, then run the same command.
- **A single reference**: `--doi 10.xxxx/yyyy`.

Drop `--no-fulltext-gate` only when a downloaded full text is genuinely required.

Then:

1. Report the three counts, and go through every non-admitted record
   individually — dimension, what each authority said, and which authority the
   majority rule believed.
2. **Confirm every flag against the actual reference text before proposing an
   edit.** A `variant` verdict on journal or volume usually means a renamed or
   translated journal title, not an error.
3. A `Crossref-adathiba gyanú` note means the publisher's deposit is malformed
   and the record is fine — worth telling the user, never worth "fixing" the
   reference to match the bad deposit.
4. Never silently correct a reference. Show the discrepancy, propose the fix,
   let the user decide.
