---
description: Irodalomkeresési napló — mit kerestél, hol, hány találat, mi maradt bent
allowed-tools: Bash, Read, Write, Glob, Skill
---
Record the literature-search audit trail for a manuscript, and emit a
paste-ready search-strategy paragraph for Materials and Methods.

Reviewers of narrative reviews routinely ask *"how were the studies identified
and selected?"* — and that question is unanswerable after the fact unless the
searches were logged while they were run. This command is the log.

`$ARGUMENTS`: `SLUG [action]`. Actions: `add`, `import`, `show`, `methods`.

The CLI takes them the other way round — `sm.py searchlog <action> <slug>` — so
`show pmos`, not `pmos show`. Getting it backwards is an argparse error, not a
silent wrong answer.

**Log a search as you run it.** Do this at the time, not afterwards.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" searchlog add SLUG \
  --source pubmed --purpose topic \
  --query '("gut microbiome"[tiab] AND "machine learning"[tiab])' \
  --filters "2021-2025, English, humans" --hits 412 --kept 18
```

`--source`: `pubmed`, `web`, `scopus`, `wos`, `embase`, `cochrane`, `europepmc`,
`crossref`, `clinicaltrials`, `other`.
`--purpose`: `topic` (evidence base), `verification` (checking a specific claim),
`journal-selection` (kept out of the Methods paragraph), `citation-chase`.

Re-running the same query on the same source **updates** its counts rather than
duplicating the row, so a re-run during revision is safe.

**Bulk import** — e.g. from a harvest, or reconstructed from a session log:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" searchlog import SLUG --json searches.json
```

Accepts `{"searches": [{query, hits, source, purpose, filters, kept, ran_at}]}`,
a bare list of those objects, or a plain `{"query": hits}` mapping. Reads stdin
if `--json` is omitted.

**Read it back / write the Methods paragraph:**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" searchlog show SLUG
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" searchlog methods SLUG
```

`methods` prints an English search-strategy sentence plus the full query list as
`%`-prefixed comments. `journal-selection` searches are counted separately and
excluded from the evidence base — a journal-shopping query is not part of how
the literature was identified.

**Honesty rules — these matter more than the tooling.**

- Log the query **actually issued**, verbatim. A Boolean string that was never
  run against a database must not be presented as if it were.
- If retrieval was web search rather than a database query, record
  `--source web`. The distinction is real and reviewers notice it; the
  "indexed journals only" rule is an *inclusion criterion*, not a search channel.
- Never invent hit counts or screening numbers to fill the table. If a figure
  was not recorded, leave it at 0 and say so in the manuscript.
- `kept` is per-query and is summed only within a purpose, never across all of
  them — otherwise an old sweep and a later verification search get conflated.

If the searches were run in an earlier session that was exported (Claude
Science, or a transcript), reconstruct the log from that export and import it —
that is a recovery, not a fabrication, as long as the numbers come from the log.
