---
description: Kiegészítő forrás-keresés — OpenAlex, Semantic Scholar, arXiv preprintek, ClinicalTrials.gov
allowed-tools: Bash, Read
---
Run a Composer supplementary-source sweep. What the user asked for: $ARGUMENTS

These four sources supplement the database search; none of them replaces it. If
the user has not run `/composer:harvest` yet, run that first — PRISMA-S counts
identification per source, and a corpus whose only source is OpenAlex is not a
defensible search base.

**Pick the sources deliberately, and say what each one is for.**

- **`openalex`** — journal articles, no key, the widest open index. This is the
  one that matters most: it covers the fields PubMed does not index at all
  (health economics, informatics, engineering), so on a non-biomedical question
  leaving it out is a real coverage gap, not a stylistic choice. Records pass
  the normal 5D gate unchanged.
- **`semanticscholar`** — metadata and the citation graph. Without an API key it
  is aggressively rate-limited and frequently returns HTTP 429; the script
  retries with backoff and then reports the branch as unavailable rather than
  pretending it found nothing. Treat a 429 as "not searched", not as "no hits".
- **`arxiv`** — **preprints**. Requires `--preprints` on purpose. They are not
  peer reviewed, they have no journal and no volume, and they would therefore
  fail the ordinary 5D gate by definition rather than by suspicion. They go into
  `preprintek.csv` in their own lane with their own gate (arXiv ID, version,
  submission date, first author, author list, title). A preprint that already
  carries a published DOI is routed to the ordinary 5D gate instead — the
  version of record wins.
- **`clinicaltrials`** — a registry, not literature. Goes to
  `regiszter_clinicaltrials.csv` with NCT number, status, phase, primary
  outcome, enrolment and whether results were posted. Its use is showing what
  was **registered but never published**.

1. **Write the query in natural language.** These APIs do not understand PubMed
   field tags. Show the user the exact string first.
2. Run:

```
"${CLAUDE_PLUGIN_ROOT}/scripts/lookup" --outdir ~/Documents/PubMed_Downloads \
    --query '<QUERY>' --query-name <SLUG> --sources openalex --retmax 50
```

   Add `--after <SEARCH FOLDER>` when this supplements a PubMed search — it
   stamps the parent `kereses.json` and `NAPLO.md` per source, which is what
   PRISMA-S asks for. Normally you arrive here from the question
   `/composer:harvest` asks at the end of every run. Add `--protocol <file>`
   when one exists, `--year-from` / `--year-to` to bound the window, and
   `--dry-run` first to see the hit counts before downloading anything.
3. **Report the gate honestly, per source.** Journal rows go through the normal
   5D gate; preprints through the preprint gate; trials through neither. Never
   merge those three numbers into one "found N papers".
4. Say which sources actually ran. A rate-limited Semantic Scholar branch and an
   empty Semantic Scholar result are different facts, and the log distinguishes
   them.
5. Point at `kereses_<stamp>_<slug>/NAPLO.md` and offer `/composer:prisma` next.
