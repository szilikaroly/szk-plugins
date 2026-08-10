---
description: Meglévő kézirat-mappák beolvasása és felvétele a nyilvántartásba
allowed-tools: Bash, Read
---
Scan the disk for manuscript projects and register them.

**Step 1 — dry run.** Run exactly:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" scan $ARGUMENTS
```

With no argument this scans the first entry of `scan_roots` from
`sm.py config` (set it with `sm.py config scan_roots ~/Documents,~/work`).
Show the user the proposed
list verbatim and ask whether to apply it. Registering is reversible
(`sm.py set SLUG --archive`), so a plain "igen" is enough — but do not apply
without asking.

**Step 2 — apply.** On approval, re-run the same command with `--apply`.

**Step 3 — make the titles real.** The scanner uses the directory name as a
placeholder title. For each newly added project, find the actual title: read the
project's main manuscript file (use the `doc-tools` skill for `.docx`/`.tex` —
read only the first page, you need the title and nothing else) or an obvious
`manuscript_*.md`. Then set it:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" set SLUG --title "..." --kind article --lang en
```

`--kind` is free text; use what fits (`article`, `review`, `systematic-review`,
`hypothesis`, `position`, `protocol`). Set `--lang hu` for Hungarian drafts.

**Step 4 — report.** List what was added, then tell the user that submission
data (journal, cover letter, submitted-or-not) is not on disk and has to come
from them — offer `/science-monitor:submit SLUG` for the first one.
