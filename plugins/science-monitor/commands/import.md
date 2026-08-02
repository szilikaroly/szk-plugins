---
description: Claude Science munkaegység-export beolvasása a nyilvántartásba
allowed-tools: Bash, Read, Glob
---
Import a Claude Science work-unit export (`00_MANIFEST.json`, schema
`claude-science.work-unit-export-manifest/v2`) into the store.

`$ARGUMENTS` is the path to the manifest, or to the `.zip`. If it is a zip,
extract it first into `~/Documents/claude/claude-science-export/` — the
transcripts get registered by absolute path, so they must live somewhere stable,
not in `~/Downloads` where they will be cleaned up.

**Step 1 — dry run.**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" import-science /path/to/00_MANIFEST.json
```

It prints, per work unit, whether it would create a project, attach to an
existing one, or do nothing. Tooling/specialist-configuration units and the
platform's own example units are created **archived** — recorded, but kept out
of the active view and out of every gap list.

**Step 2 — find the overlaps before applying.** This is the part that matters.
Run `sm.py status` and compare titles: a work unit whose task description
matches a manuscript already in the store must be *attached*, not duplicated.
The match is usually obvious from the title (the same disease, the same
outcome, the same journal). Write the ones you are sure about into a map file:

```json
{ "15": "bmc-hsr-submission", "07": "dietary-axis-prevention" }
```

Only map what is unambiguous. A duplicate is annoying; a wrong merge silently
mixes two manuscripts' histories and is much worse. Show the user the proposed
map and the leftovers you were unsure about, and let them decide those.

**Step 3 — apply.**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" import-science MANIFEST --map map.json --apply
```

**Step 4 — make the new entries real.** Imported projects carry the work unit's
task description as their title, which is a task, not a manuscript title. For
each newly created *active* project, find the actual manuscript: search the
user's `~/Downloads` and project folders for a matching `.docx`/`.pdf` (use the
**doc-tools** skill to read the first lines and confirm the title). Then:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" set SLUG --title "..." --kind review
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" file add SLUG /path/to/ms.docx --role manuscript
```

Do not invent a target journal. A filename hinting at one (`..._MDPI_format`,
`..._WJD_EN`) goes in `--label` or `--notes`, never into `--journal`.

**Step 5 — report.** Say how many were created, attached and archived; list the
new active projects that still have no manuscript file or no target journal;
and flag any set of units that look like the same manuscript at different stages
(a draft unit, a revision unit, a peer-review-response unit). Offer to
consolidate those — do not merge them unasked.
