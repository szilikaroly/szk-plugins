---
description: Szakaszos folyamat- vagy architektúraábra — fejlécsávos oszlopok, dobozok, nyilak
allowed-tools: Bash, Read, Write, Glob
---
Build a staged pipeline or architecture figure: columns with coloured header
bars, stacked content boxes carrying a bold title and a grey detail line,
arrows within and between stages, and an optional status banner along the
bottom.

This is the shape journals expect when a paper proposes an architecture rather
than reporting data — the "stage 1 → stage 2 → stage 3" diagram.

`$ARGUMENTS`: path to a spec `.json`, plus any `ff.py` flags.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" panelflow --spec fig1.json \
  --out Figure1A --formats svg,png,tiff --dpi 600
```

**Spec shape.** `width_mm` is the *final printed width* — set it to the
journal's text width (170 mm for MDPI full page, 183 mm for Nature double
column) and the export honours it exactly.

```json
{
  "width_mm": 170,
  "banner": "Design proposal: no component has been evaluated on data.",
  "columns": [
    {"header": "1. Data acquisition", "boxes": [
      {"title": "Stool sample", "body": "gut microbial community"},
      {"title": "Host biomarkers", "body": "age, sex, BMI", "arrow_below": true}
    ]},
    {"header": "2. Model core", "boxes": [
      {"title": "Transformer encoder", "body": "self-attention", "style": "hi"}
    ]}
  ]
}
```

Box `style`: `plain` (default), `hi` (teal, for the stage's key box), `warn`
(orange, for a caveat or an untested element). A box may carry `title` only,
`body` only, or both. `arrow_below: true` draws a downward arrow to the next
box in the same column.

**The guarantee.** Every line is wrapped by *measuring* it in the real font, so
no text can overflow its box — the containment rule the flowchart renderer
applies to single labels, extended to multi-line prose. The command prints
`QC result: CLEAN` or lists each overflowing line with its width against the
space available, and writes the same to `<stem>.qc.json`.

If a line does overflow, the fix is one of: shorten the text, raise
`width_mm`, or move a box to a column with fewer entries. Do not silence it.

**Why exact width matters.** Unlike the plotting commands, this figure has no
data margins to trim, so it exports the canvas as sized rather than to a tight
bounding box. A figure built for 170 mm arrives at 170 mm, which is what keeps
the type size honest: 8 pt in the spec is 8 pt on the printed page.
