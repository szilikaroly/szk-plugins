---
description: PRISMA 2020 folyamat — beolvasás, duplikátumok, szűrés, folyamatábra, export
allowed-tools: Bash, Read
---
Build or advance the PRISMA trail. Request: $ARGUMENTS

```
R="${CLAUDE_PLUGIN_ROOT}/scripts/prisma"
"$R" --project <slug> ingest        # search log + corpus + the 5D verdicts
"$R" --project <slug> dedup --auto  # by DOI, then normalised title
"$R" --project <slug> template      # -> decisions CSV of undecided records
"$R" --project <slug> screen --from-csv <file>
"$R" --project <slug> status
"$R" --project <slug> export --format all
```

Add a database the harvest did not run:
`add-source --source Embase --count 210 --date 2026-08-10 --query "..."`.

When screening, read titles and abstracts in batches for the rows still in play,
propose include/exclude with a one-line reason each, and let the user confirm
before writing decisions. State the exclusion reasons in the vocabulary the
paper will use — PRISMA requires the reasons at the eligibility phase to be
reported, so vague ones cost the user a revision.

Two warnings from `status` must be repeated to the user, not summarised away:
the retmax warning (the search was a sample, not exhaustive) and the count of
records still `fuggoben` in the 5D gate (not citable as verified).

`export` writes the methods paragraph, the PRISMA-S search appendix, a
`figure-forge` flowchart spec and the included set as RIS/CSV. Render the
diagram with the `figure-forge` plugin — the command is printed for you.
