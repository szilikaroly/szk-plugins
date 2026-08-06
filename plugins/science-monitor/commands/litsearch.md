---
description: Irodalomkeresés több forráson — lefuttatja a keresést és be is naplózza
argument-hint: "<query>" [--slug SLUG] [--sources europepmc,openalex,crossref,embase]
allowed-tools: Bash
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/litsearch.py"`.

`searchlog` records what was searched; this **runs** it and writes the counts
itself, so the audit trail stops depending on numbers typed in from memory.

```
litsearch.py --query '(endometriosis) AND (cost OR "economic burden")' \
             --sources europepmc,openalex --limit 25 \
             --slug endo-econ --purpose topic --filters "2015-2026, English" --log
```

Sources: `europepmc` (MEDLINE + PMC + preprints, no key), `openalex` (broadest,
no key), `crossref` (DOI verification, **not** discovery), `embase` (Elsevier,
needs a key). `--keys` shows which are usable right now.

**Three things to get right when reporting results.**

1. **`kept` stays 0 until a human screens.** This command only retrieves. Never
   set `--kept` from a retrieval count, and do not tell the user a study was
   "selected" — nothing has been read yet.
2. **The "in only one source's top-N" figure is not coverage.** Each source
   returns its own top-ranked N and the rankings diverge hard — on one real
   query Europe PMC and OpenAlex returned 46 and 50 DOIs with *zero* in common.
   That number describes ranking overlap. Quoting it as "database X contributed
   N unique studies" in a Methods section would be a false claim.
3. **Crossref's total is corpus-wide**, not a search yield. Report Europe PMC
   and Embase totals as yields; report Crossref's only as "records screened".

Preprint/published pairs are collapsed automatically — the same paper carries
different DOIs on Preprints.org and in the journal, so DOI matching keeps them
apart and a review would count the study twice. The published record wins.

**Never put an API key in a command, a file in this repo, or the transcript.**
Keys come from the environment or `~/.science-monitor/keys.json`. If the user
pastes one in chat, tell them it is now in the session archive and should be
rotated.

After a search, offer `/science-monitor:searchlog SLUG methods` — it turns the
logged runs into the paste-ready search-strategy paragraph.
