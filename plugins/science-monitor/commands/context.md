---
description: Egy kézirat teljes kontextusának behívása a sessionbe
allowed-tools: Bash, Read, Glob, Grep, Skill
---
Load one manuscript's working context into this session so work can continue on
it immediately.

**Step 1 — get the read plan.** Run exactly:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sm.py" context $ARGUMENTS
```

If `$ARGUMENTS` is empty, run `sm.py status` first and ask which manuscript.
The `ref` may be a slug, an id, or a distinctive fragment of the title.

**Step 2 — read what the plan marks with `→`.** Those are the files queued for
this session; the ones marked `·` (figures, large data) are inventory only —
list them, do not open them unless the task turns out to need one.

Follow the `how` column for each file:
- `doc-tools: …` — invoke the **doc-tools** skill and use the named CLI
  (`doctotext`, `pdftotext`, `xlstotext`, `latextotext`). Never try to Read a
  `.docx` directly.
- `Read` — read it normally.

If the plan is large (more than ~8 files queued, or a manuscript over ~300 kB),
use the **memo-index** skill instead of reading everything into context.

**Step 3 — state where things stand.** After reading, give the user a short
briefing in Hungarian, covering only what the printed state and the files
actually support:
- the submission: journal, attempt number, status, whether the cover letter
  exists and whether the package was actually submitted (both are printed
  separately — report both),
- any deadline and how many days are left,
- open reviewer points, if any, grouped by reviewer,
- what the obvious next action is.

Do not restate the whole manuscript. Do not invent submission facts that the
store does not contain — if a field is empty, say it is not recorded and offer
to fill it with `/sm:submit`.
