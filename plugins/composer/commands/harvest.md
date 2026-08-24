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
   methods-ready log.
6. **Ask about Google Scholar — every time, before offering PRISMA.** The run
   ends with a `DÖNTÉS KELL` block; act on it with a real clickable question
   (AskUserQuestion), not a prose aside. State these three things once, without
   softening them:
   - Scholar has no API. The script reads the public result pages, which
     Google's terms do not allow and which Google blocks after sustained
     querying.
   - A Scholar search is not reproducible: personalised ranking, an estimated
     "About N results", and only ~1000 results reachable.
   - Cochrane and PRISMA-S therefore treat it as **supplementary** — it does not
     replace the database search you just ran.

   Then record the answer, because PRISMA-S wants every source that was
   *considered*, not only the ones that ran:
   - **yes** → `scholar --query '<SCHOLAR SYNTAX>' --query-name <SLUG> --outdir
     <OUTDIR> --retmax 20 --no-pdf --after <SEARCH FOLDER>`. Rewrite the query
     into Scholar syntax first (PubMed field tags are rejected) and show it.
     `--after` back-references the two logs to each other.
   - **no** → rerun nothing; write the decision into the log with
     `--scholar no` on the next harvest of the same topic, or say plainly that
     the log still shows it undecided.

   If the user is tired of the question, `COMPOSER_SCHOLAR=no` in the
   environment settles it once; `--scholar yes|no` settles a single run.
7. Offer the PRISMA step next.
