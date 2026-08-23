---
description: Irodalom learatása PubMedből — 5D validációval és PRISMA/PROSPERO naplózással
allowed-tools: Bash, Read
---
Run a Composer harvest. What the user asked for: $ARGUMENTS

1. Work out the PubMed query. If the user gave a topic in prose, write real
   PubMed syntax for it (MeSH `[mh]`, `[tiab]`, `[dp]`, Booleans) and **show
   them the query string before running it** — a search they cannot read is a
   search they cannot defend in the methods section.
2. If the user is preparing a systematic/rapid/umbrella review, check for a
   protocol first (`prospero.py check`), and pass `--protocol`. If it is a
   narrative review, say once that PROSPERO will not register it and continue.
3. Run:

```
"${CLAUDE_PLUGIN_ROOT}/scripts/collect" --outdir ~/Documents/PubMed_Downloads \
    --query '<QUERY>' --query-name <SLUG> --raw --retmax <N> --xml-fallback
```

   Add `--protocol <file>` when one exists. Use `--raw` for anything other than
   narrative reviews. Start with a small `--retmax` and `--no-pdf` if the query
   is untested.
4. Report faithfully: the true PubMed hit count vs. how many were retrieved (say
   plainly when it was a sample, not an exhaustive search), then the gate —
   admitted / held / rejected — and walk the held records with their reasons.
   Never present a held record as part of the corpus.
5. Point at the search folder (`keresesek/<stamp>_<slug>/NAPLO.md`) as the
   methods-ready log, and offer the PRISMA step next.
